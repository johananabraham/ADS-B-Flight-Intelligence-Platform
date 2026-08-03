"""Tests for short-window trajectory residual evidence."""

from datetime import datetime, timedelta, timezone
from uuid import uuid5, NAMESPACE_URL

from app.schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from app.services.kinematics import EvaluationStatus
from app.services.windowed_kinematics import WindowPolicy, WindowRule, evaluate_window


START = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
PROVENANCE = ObservationProvenance(
    source_type=ObservationSourceType.SIMULATION,
    source_id="window-test",
)


def observation(index: int, *, longitude_offset: float = 0) -> TrackObservation:
    return TrackObservation(
        observation_id=uuid5(NAMESPACE_URL, f"window-test:{index}:{longitude_offset}"),
        provenance=PROVENANCE,
        icao_hex="A1B2C3",
        observed_at=START + timedelta(seconds=index),
        received_at=START + timedelta(seconds=index),
        latitude=index * (300 / 3600 / 60),
        longitude=longitude_offset,
        altitude_ft=10_000,
        ground_speed_knots=300,
        track_degrees=0,
    )


def test_consistent_window_passes() -> None:
    result = evaluate_window(tuple(observation(index) for index in range(6)))

    assert result.status is EvaluationStatus.PASS
    assert result.duration_seconds == 5
    assert result.measurements["position_residual_nm"] < WindowPolicy().maximum_position_residual_nm


def test_gradual_lateral_drift_accumulates_into_explainable_flag() -> None:
    observations = tuple(
        observation(index, longitude_offset=index * 0.00002) for index in range(6)
    )

    result = evaluate_window(observations)

    assert result.status is EvaluationStatus.FLAGGED
    assert result.failed_rules[0].rule is WindowRule.CUMULATIVE_POSITION_RESIDUAL
    assert result.failed_rules[0].value > result.failed_rules[0].threshold
    assert result.failed_rules[0].observation_ids == tuple(
        item.observation_id for item in observations
    )


def test_missing_velocity_returns_insufficient_data() -> None:
    observations = list(observation(index) for index in range(6))
    observations[2] = observations[2].model_copy(update={"ground_speed_knots": None})

    result = evaluate_window(tuple(observations))

    assert result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert result.rule_results == ()
    assert "ground speed" in result.reason


def test_duplicate_time_returns_insufficient_data() -> None:
    observations = list(observation(index) for index in range(6))
    observations[3] = observations[3].model_copy(
        update={"observed_at": observations[2].observed_at}
    )

    result = evaluate_window(tuple(observations))

    assert result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert "strictly" in result.reason


def test_identity_is_deterministic_for_policy_and_observations() -> None:
    observations = tuple(observation(index) for index in range(6))

    first = evaluate_window(observations, policy=WindowPolicy())
    retry = evaluate_window(observations, policy=WindowPolicy())

    assert first.evaluation_id == retry.evaluation_id
