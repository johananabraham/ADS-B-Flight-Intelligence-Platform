"""Idempotent storage for trust snapshots and append-only operator actions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models.trust import TrustAssessmentRecord, TrustOperatorActionRecord
from .trust_assessment import TrustAssessmentResult


TRUST_ASSESSMENT_NAMESPACE = UUID("bf8308f7-e9b9-4de4-8ca7-7db5f29b8402")


@dataclass(frozen=True)
class TrustSnapshot:
    assessment_id: UUID
    policy_version: str
    icao_hex: str
    evaluated_at: datetime
    state: str
    reasons: tuple[str, ...]
    components: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class OperatorAction:
    action_id: UUID
    assessment_id: UUID
    action_type: str
    actor: str
    note: str | None
    created_at: datetime


def create_snapshot(
    assessment: TrustAssessmentResult,
    components: tuple[dict[str, object], ...],
) -> TrustSnapshot:
    identity_components = [
        {
            key: value
            for key, value in component.items()
            if key not in {"age_seconds", "evaluated_at"}
        }
        for component in components
    ]
    identity = json.dumps(
        {
            "policy_version": assessment.policy_version,
            "icao_hex": assessment.icao_hex,
            "state": assessment.state.value,
            "reasons": assessment.reasons,
            "components": identity_components,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return TrustSnapshot(
        assessment_id=uuid5(TRUST_ASSESSMENT_NAMESPACE, identity),
        policy_version=assessment.policy_version,
        icao_hex=assessment.icao_hex,
        evaluated_at=assessment.evaluated_at,
        state=assessment.state.value,
        reasons=assessment.reasons,
        components=components,
    )


def snapshot_values(snapshot: TrustSnapshot) -> dict[str, object]:
    _require_aware(snapshot.evaluated_at, "evaluated_at")
    return {
        "assessment_id": snapshot.assessment_id,
        "policy_version": snapshot.policy_version,
        "icao_hex": snapshot.icao_hex,
        "evaluated_at": snapshot.evaluated_at,
        "state": snapshot.state,
        "reasons": list(snapshot.reasons),
        "components": list(snapshot.components),
    }


def build_snapshot_insert(snapshot: TrustSnapshot):
    return (
        insert(TrustAssessmentRecord)
        .values(**snapshot_values(snapshot))
        .on_conflict_do_nothing(index_elements=["assessment_id"])
    )


def insert_snapshot(db: Session, snapshot: TrustSnapshot) -> bool:
    return db.execute(build_snapshot_insert(snapshot)).rowcount == 1


def action_values(action: OperatorAction) -> dict[str, object]:
    _require_aware(action.created_at, "created_at")
    if action.action_type not in {"ACKNOWLEDGE", "ANNOTATE"}:
        raise ValueError("unsupported operator action")
    if not action.actor.strip():
        raise ValueError("actor cannot be blank")
    if action.note is not None and not action.note.strip():
        raise ValueError("note cannot be blank")
    return {
        "action_id": action.action_id,
        "assessment_id": action.assessment_id,
        "action_type": action.action_type,
        "actor": action.actor.strip(),
        "note": action.note.strip() if action.note else None,
        "created_at": action.created_at,
    }


def build_action_insert(action: OperatorAction):
    return (
        insert(TrustOperatorActionRecord)
        .values(**action_values(action))
        .on_conflict_do_nothing(index_elements=["action_id"])
    )


def insert_action(db: Session, action: OperatorAction) -> bool:
    return db.execute(build_action_insert(action)).rowcount == 1


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
