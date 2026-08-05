"""Filter, inspect, annotate, acknowledge, and export persisted trust events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.trust import TrustAssessmentRecord, TrustOperatorActionRecord
from ..models.user import User
from ..services.trust_persistence import OperatorAction, insert_action
from ..auth.dependencies import require_operator


router = APIRouter(prefix="/trust-events", tags=["trust"])
TrustState = Literal["TRUSTED", "QUESTIONABLE", "LOW_CONFIDENCE", "INSUFFICIENT_DATA"]
ActionType = Literal["ACKNOWLEDGE", "ANNOTATE"]


class OperatorActionRequest(BaseModel):
    action_id: UUID
    action_type: ActionType
    actor: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2_000)

    @field_validator("actor")
    @classmethod
    def normalize_actor(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("actor cannot be blank")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("note cannot be blank")
        return normalized

    @model_validator(mode="after")
    def annotation_requires_note(self) -> "OperatorActionRequest":
        if self.action_type == "ANNOTATE" and not (self.note or "").strip():
            raise ValueError("ANNOTATE requires a note")
        return self


class OperatorActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: UUID
    assessment_id: UUID
    action_type: ActionType
    actor: str
    note: str | None
    created_at: datetime
    identity_assurance: Literal["SELF_ASSERTED"] = "SELF_ASSERTED"


class ActionCreatedResponse(BaseModel):
    inserted: bool
    action: OperatorActionResponse


class TrustEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: UUID
    policy_version: str
    icao_hex: str
    evaluated_at: datetime
    state: TrustState
    reasons: list[str]
    components: list[dict[str, object]]


class TrustEventDetailResponse(TrustEventResponse):
    actions: list[OperatorActionResponse]


@router.get("/", response_model=list[TrustEventResponse])
def list_trust_events(
    icao_hex: str | None = Query(default=None, pattern=r"^[0-9A-Fa-f]{6}$"),
    state: TrustState | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TrustAssessmentRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(TrustAssessmentRecord).filter(
        TrustAssessmentRecord.evaluated_at >= cutoff
    )
    if icao_hex:
        query = query.filter(TrustAssessmentRecord.icao_hex == icao_hex.upper())
    if state:
        query = query.filter(TrustAssessmentRecord.state == state)
    return query.order_by(TrustAssessmentRecord.evaluated_at.desc()).limit(limit).all()


@router.get("/{assessment_id}", response_model=TrustEventDetailResponse)
def get_trust_event(
    assessment_id: UUID, db: Session = Depends(get_db)
) -> TrustEventDetailResponse:
    assessment = _assessment_or_404(db, assessment_id)
    actions = (
        db.query(TrustOperatorActionRecord)
        .filter(TrustOperatorActionRecord.assessment_id == assessment_id)
        .order_by(TrustOperatorActionRecord.created_at.asc())
        .all()
    )
    return TrustEventDetailResponse(
        **TrustEventResponse.model_validate(assessment).model_dump(), actions=actions
    )


@router.post("/{assessment_id}/actions", response_model=ActionCreatedResponse)
def create_operator_action(
    assessment_id: UUID,
    request: OperatorActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ActionCreatedResponse:
    _assessment_or_404(db, assessment_id)
    existing = (
        db.query(TrustOperatorActionRecord)
        .filter(TrustOperatorActionRecord.action_id == request.action_id)
        .first()
    )
    if existing:
        if not _same_action(existing, assessment_id, request):
            raise HTTPException(
                status_code=409, detail="action_id already exists with different content"
            )
        return ActionCreatedResponse(inserted=False, action=existing)

    action = OperatorAction(
        action_id=request.action_id,
        assessment_id=assessment_id,
        action_type=request.action_type,
        actor=request.actor,
        note=request.note,
        created_at=datetime.now(timezone.utc),
    )
    inserted = insert_action(db, action)
    db.commit()
    if not inserted:
        concurrent = (
            db.query(TrustOperatorActionRecord)
            .filter(TrustOperatorActionRecord.action_id == request.action_id)
            .first()
        )
        if concurrent is None or not _same_action(concurrent, assessment_id, request):
            raise HTTPException(
                status_code=409, detail="action_id was concurrently reused"
            )
        return ActionCreatedResponse(inserted=False, action=concurrent)
    return ActionCreatedResponse(
        inserted=True,
        action=OperatorActionResponse(
            action_id=action.action_id,
            assessment_id=action.assessment_id,
            action_type=action.action_type,
            actor=action.actor,
            note=action.note,
            created_at=action.created_at,
        ),
    )


@router.get("/{assessment_id}/export")
def export_trust_event(
    assessment_id: UUID, db: Session = Depends(get_db)
) -> Response:
    detail = get_trust_event(assessment_id, db)
    payload = detail.model_dump(mode="json")
    payload["exported_at"] = datetime.now(timezone.utc).isoformat()
    payload["identity_warning"] = (
        "Operator labels are self-asserted until authentication is implemented."
    )
    return Response(
        content=json.dumps(payload, indent=2, sort_keys=True),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="trust-event-{assessment_id}.json"'
        },
    )


def _assessment_or_404(db: Session, assessment_id: UUID) -> TrustAssessmentRecord:
    assessment = (
        db.query(TrustAssessmentRecord)
        .filter(TrustAssessmentRecord.assessment_id == assessment_id)
        .first()
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Trust assessment not found")
    return assessment


def _same_action(
    existing: TrustOperatorActionRecord,
    assessment_id: UUID,
    request: OperatorActionRequest,
) -> bool:
    return (
        existing.assessment_id == assessment_id
        and existing.action_type == request.action_type
        and existing.actor == request.actor.strip()
        and existing.note == (request.note.strip() if request.note else None)
    )
