"""Deterministic tests for observation-to-observation plausibility evidence."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.dialects import postgresql

from app.schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from app.services.kinematics import (
    EvaluationStatus,
    KinematicPolicy,
    KinematicRule,
    evaluate_pair,
)
from app.services.kinematic_persistence import build_evaluation_insert_statement


START = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
PROVENANCE = ObservationProvenance(
    source_type=ObservationSourceType.SIMULATION,
    source_id="kinematic-test",
)


def observation(
    *,
    seconds: float,
    latitude: float,
    longitude: float = 0,
    altitude_ft: int = 10_000,
    speed_knots: float = 300,
    track_degrees: float = 0,
) -> TrackObservation:
    timestamp = START + timedelta(seconds=seconds)
    return TrackObservation(
        provenance=PROVENANCE,
        icao_hex="A1B2C3",
        observed_at=timestamp,
        received_at=timestamp,
        latitude=latitude,
        longitude=longitude,
        altitude_ft=altitude_ft,
        ground_speed_knots=speed_knots,
        track_degrees=track_degrees,
    )


def test_consistent_motion_passes_all_available_rules() -> None:
    previous = observation(seconds=0, latitude=0, altitude_ft=10_000)
    current = observation(seconds=1, latitude=0.0013889, altitude_ft=10_010)

    result = evaluate_pair(previous, current)

    assert result.status is EvaluationStatus.PASS
    assert result.delta_seconds == 1
    assert 299 < result.measurements["implied_ground_speed_knots"] < 301
    assert all(rule.status is EvaluationStatus.PASS for rule in result.rule_results)


def test_impossible_motion_returns_each_failed_rule_with_evidence() -> None:
    previous = observation(
        seconds=0,
        latitude=0,
        altitude_ft=10_000,
        speed_knots=200,
        track_degrees=0,
    )
    current = observation(
        seconds=1,
        latitude=0.05,
        altitude_ft=10_500,
        speed_knots=800,
        track_degrees=180,
    )

    result = evaluate_pair(previous, current)
    failures = {rule.rule: rule for rule in result.rule_results if rule.failed}

    assert result.status is EvaluationStatus.FLAGGED
    assert set(failures) == set(KinematicRule)
    assert failures[KinematicRule.IMPLIED_GROUND_SPEED].unit == "knots"
    assert failures[KinematicRule.REPORTED_ACCELERATION].value == 600
    assert failures[KinematicRule.TURN_RATE].value == 180
    assert failures[KinematicRule.DERIVED_VERTICAL_RATE].value == 30_000
    assert failures[KinematicRule.SPEED_DISAGREEMENT].observation_ids == (
        previous.observation_id,
        current.observation_id,
    )


def test_tiny_or_reversed_intervals_are_not_scored_as_attacks() -> None:
    previous = observation(seconds=1, latitude=0)
    same_time = observation(seconds=1, latitude=1)
    earlier = observation(seconds=0, latitude=1)

    same_result = evaluate_pair(previous, same_time)
    earlier_result = evaluate_pair(previous, earlier)

    assert same_result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert earlier_result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert same_result.rule_results == ()
    assert "positive" in same_result.reason


def test_long_gaps_are_recorded_but_not_scored() -> None:
    result = evaluate_pair(
        observation(seconds=0, latitude=0),
        observation(seconds=31, latitude=1),
    )

    assert result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert "30" in result.reason


def test_heading_wrap_uses_shortest_turn() -> None:
    previous = observation(seconds=0, latitude=0, track_degrees=359)
    current = observation(seconds=1, latitude=0.0013889, track_degrees=1)

    result = evaluate_pair(previous, current)

    assert result.measurements["turn_rate_degrees_per_second"] == 2


def test_evaluation_identity_and_insert_are_idempotent() -> None:
    previous = observation(seconds=0, latitude=0)
    current = observation(seconds=1, latitude=0.0013889)
    first = evaluate_pair(previous, current, policy=KinematicPolicy())
    retry = evaluate_pair(previous, current, policy=KinematicPolicy())

    assert isinstance(first.evaluation_id, UUID)
    assert first.evaluation_id == retry.evaluation_id

    statement = build_evaluation_insert_statement(first)
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (evaluation_id) DO NOTHING" in sql
