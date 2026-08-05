"""Scenario tests for the explainable trust-state policy."""

from datetime import datetime, timezone

import pytest

from app.services.corroboration import CorroborationState
from app.services.kinematics import EvaluationStatus
from app.services.station_health import StationHealthState
from app.services.trust_assessment import (
    TrustAssessmentInputs,
    TrustState,
    assess_trust,
)


NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


def inputs(**updates) -> TrustAssessmentInputs:
    values = {
        "icao_hex": "ABC123",
        "evaluated_at": NOW,
        "pair_status": EvaluationStatus.PASS,
        "window_status": EvaluationStatus.PASS,
        "corroboration_state": CorroborationState.CORROBORATED,
        "station_state": StationHealthState.HEALTHY,
    }
    values.update(updates)
    return TrustAssessmentInputs(**values)


def test_supportive_independent_evidence_is_trusted():
    result = assess_trust(inputs())

    assert result.state is TrustState.TRUSTED
    assert len(result.reasons) == 3


@pytest.mark.parametrize(
    ("updates", "expected_reason"),
    [
        ({"pair_status": EvaluationStatus.FLAGGED}, "pairwise"),
        ({"window_status": EvaluationStatus.FLAGGED}, "windowed"),
        ({"corroboration_state": CorroborationState.CONFLICTING}, "conflict"),
    ],
)
def test_strong_contradiction_is_questionable(updates, expected_reason):
    result = assess_trust(inputs(**updates))

    assert result.state is TrustState.QUESTIONABLE
    assert expected_reason in " ".join(result.reasons).lower()


@pytest.mark.parametrize(
    "updates",
    [
        {"pair_status": None},
        {"window_status": EvaluationStatus.INSUFFICIENT_DATA},
        {"corroboration_state": None},
        {"station_state": None},
    ],
)
def test_missing_required_component_is_insufficient_data(updates):
    assert assess_trust(inputs(**updates)).state is TrustState.INSUFFICIENT_DATA


@pytest.mark.parametrize(
    "updates",
    [
        {"corroboration_state": CorroborationState.UNAVAILABLE},
        {"corroboration_state": CorroborationState.LOCAL_ONLY},
        {"station_state": StationHealthState.DEGRADED},
        {"station_state": StationHealthState.OFFLINE},
    ],
)
def test_weak_source_or_station_evidence_is_low_confidence(updates):
    result = assess_trust(inputs(**updates))

    assert result.state is TrustState.LOW_CONFIDENCE
    assert "suspicious" in " ".join(result.reasons) or "does not measure" in " ".join(result.reasons)


def test_contradiction_takes_priority_over_missing_components():
    result = assess_trust(
        inputs(
            pair_status=EvaluationStatus.FLAGGED,
            corroboration_state=None,
            station_state=None,
        )
    )

    assert result.state is TrustState.QUESTIONABLE


def test_uncalibrated_ml_value_is_preserved_but_does_not_change_state():
    result = assess_trust(
        inputs(ml_probability=0.95, ml_model_version="offline-candidate-1")
    )

    assert result.state is TrustState.TRUSTED
    assert result.inputs.ml_probability == 0.95


def test_requires_aware_evaluation_time():
    with pytest.raises(ValueError, match="timezone"):
        assess_trust(inputs(evaluated_at=datetime(2026, 8, 4, 12, 0)))
