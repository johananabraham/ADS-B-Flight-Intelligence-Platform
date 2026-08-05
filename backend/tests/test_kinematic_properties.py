"""Property-based checks for geographic, timing, and heading boundaries."""

import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from hypothesis import given, settings, strategies as st

from app.schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from app.services.kinematics import EvaluationStatus, KinematicRule, evaluate_pair


PROVENANCE = ObservationProvenance(
    source_type=ObservationSourceType.SIMULATION,
    source_id="property-test",
)


def observation(
    *,
    timestamp: datetime,
    latitude: float,
    longitude: float,
    speed_knots: float = 0,
    track_degrees: float = 0,
) -> TrackObservation:
    return TrackObservation(
        observation_id=uuid4(),
        provenance=PROVENANCE,
        icao_hex="A1B2C3",
        observed_at=timestamp,
        received_at=timestamp,
        latitude=latitude,
        longitude=longitude,
        altitude_ft=10_000,
        ground_speed_knots=speed_knots,
        track_degrees=track_degrees,
    )


def normalized_heading(value: float) -> float:
    normalized = value % 360
    return 0 if normalized >= 360 else normalized


@settings(max_examples=100, deadline=None)
@given(
    latitude=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
    first_longitude=st.floats(
        min_value=-180, max_value=180, allow_nan=False, allow_infinity=False
    ),
    second_longitude=st.floats(
        min_value=-180, max_value=180, allow_nan=False, allow_infinity=False
    ),
)
def test_distance_is_finite_at_poles_and_date_line(
    latitude: float,
    first_longitude: float,
    second_longitude: float,
) -> None:
    start = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    result = evaluate_pair(
        observation(timestamp=start, latitude=latitude, longitude=first_longitude),
        observation(
            timestamp=start + timedelta(seconds=1),
            latitude=latitude,
            longitude=second_longitude,
        ),
    )

    assert result.status is not EvaluationStatus.INSUFFICIENT_DATA
    assert math.isfinite(result.measurements["distance_nautical_miles"])
    assert result.measurements["distance_nautical_miles"] >= 0


@settings(max_examples=100, deadline=None)
@given(
    interval=st.floats(
        min_value=0.5,
        max_value=30,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_inclusive_interval_boundaries_are_scored(interval: float) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = evaluate_pair(
        observation(timestamp=start, latitude=0, longitude=0),
        observation(timestamp=start + timedelta(seconds=interval), latitude=0, longitude=0),
    )

    assert result.status is EvaluationStatus.PASS


@settings(max_examples=100, deadline=None)
@given(
    initial_heading=st.floats(
        min_value=0,
        max_value=359.999,
        allow_nan=False,
        allow_infinity=False,
    ),
    heading_change=st.floats(
        min_value=-11.999,
        max_value=11.999,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_heading_wrap_and_subthreshold_noise_do_not_flag_turn_rate(
    initial_heading: float,
    heading_change: float,
) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = evaluate_pair(
        observation(
            timestamp=start,
            latitude=0,
            longitude=0,
            speed_knots=100,
            track_degrees=initial_heading,
        ),
        observation(
            timestamp=start + timedelta(seconds=1),
            latitude=0,
            longitude=0,
            speed_knots=100,
            track_degrees=normalized_heading(initial_heading + heading_change),
        ),
    )
    turn_result = next(
        rule for rule in result.rule_results if rule.rule is KinematicRule.TURN_RATE
    )

    assert turn_result.status is EvaluationStatus.PASS
    assert turn_result.value <= turn_result.threshold
