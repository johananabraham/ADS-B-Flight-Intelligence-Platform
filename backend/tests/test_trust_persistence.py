"""Persistence tests for trust snapshots and operator actions."""

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.services.corroboration import CorroborationState
from app.services.kinematics import EvaluationStatus
from app.services.station_health import StationHealthState
from app.services.trust_assessment import TrustAssessmentInputs, assess_trust
from app.services.trust_persistence import (
    OperatorAction,
    build_action_insert,
    build_snapshot_insert,
    create_snapshot,
    insert_action,
    insert_snapshot,
)


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
ACTION_ID = UUID("00000000-0000-4000-8000-000000000201")


def assessment():
    return assess_trust(
        TrustAssessmentInputs(
            icao_hex="ABC123",
            evaluated_at=NOW,
            pair_status=EvaluationStatus.PASS,
            window_status=EvaluationStatus.PASS,
            corroboration_state=CorroborationState.CORROBORATED,
            station_state=StationHealthState.HEALTHY,
        )
    )


def components(age: float = 1.0):
    return (
        {
            "component": "PAIR_KINEMATICS",
            "state": "PASS",
            "policy_version": "1.0",
            "evaluated_at": NOW.isoformat(),
            "age_seconds": age,
            "evidence_ids": ["pair-1"],
            "reasons": ["Passed."],
        },
    )


def compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_snapshot_identity_ignores_request_time_age_but_preserves_components():
    first = create_snapshot(assessment(), components(age=1.0))
    retry = create_snapshot(assessment(), components(age=9.0))

    assert first.assessment_id == retry.assessment_id
    assert first.components[0]["age_seconds"] == 1.0
    assert "ON CONFLICT (assessment_id) DO NOTHING" in compiled(
        build_snapshot_insert(first)
    )


def test_operator_action_insert_is_idempotent_by_client_action_id():
    snapshot = create_snapshot(assessment(), components())
    action = OperatorAction(
        action_id=ACTION_ID,
        assessment_id=snapshot.assessment_id,
        action_type="ANNOTATE",
        actor="operator@example.com",
        note="Reviewed against replay fixture.",
        created_at=NOW,
    )

    assert "ON CONFLICT (action_id) DO NOTHING" in compiled(
        build_action_insert(action)
    )


def test_insert_helpers_report_new_or_duplicate_rows():
    db = Mock()
    db.execute.return_value = Mock(rowcount=1)
    snapshot = create_snapshot(assessment(), components())
    assert insert_snapshot(db, snapshot) is True

    db.execute.return_value = Mock(rowcount=0)
    action = OperatorAction(
        action_id=ACTION_ID,
        assessment_id=snapshot.assessment_id,
        action_type="ACKNOWLEDGE",
        actor="operator",
        note=None,
        created_at=NOW,
    )
    assert insert_action(db, action) is False


@pytest.mark.parametrize(
    "updates",
    [
        {"action_type": "DELETE"},
        {"actor": " "},
        {"note": " "},
        {"created_at": datetime(2026, 8, 4, 12)},
    ],
)
def test_operator_action_rejects_invalid_values(updates):
    snapshot = create_snapshot(assessment(), components())
    values = {
        "action_id": ACTION_ID,
        "assessment_id": snapshot.assessment_id,
        "action_type": "ANNOTATE",
        "actor": "operator",
        "note": "reviewed",
        "created_at": NOW,
    }
    values.update(updates)

    with pytest.raises(ValueError):
        build_action_insert(OperatorAction(**values))
