"""Tests for the versioned aircraft observation contract."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.observation import (
    ObservationProvenance,
    ObservationQualityFlag,
    ObservationSourceType,
    TrackObservation,
)
from app.services.observation_adapters import sbs_state_to_observation


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def simulation_provenance() -> ObservationProvenance:
    return ObservationProvenance(
        source_type=ObservationSourceType.SIMULATION,
        source_id="columbus-demo",
    )


def test_normalizes_identity_and_accepts_partial_observation() -> None:
    observation = TrackObservation(
        provenance=simulation_provenance(),
        icao_hex=" a1b2c3 ",
        callsign=" dal1842 ",
        observed_at=NOW,
        received_at=NOW + timedelta(milliseconds=100),
    )

    assert observation.schema_version == "1.0"
    assert observation.icao_hex == "A1B2C3"
    assert observation.callsign == "DAL1842"
    assert observation.latitude is None


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(40.0, None), (None, -83.0), (91.0, -83.0), (40.0, -181.0)],
)
def test_rejects_incomplete_or_out_of_range_position(latitude, longitude) -> None:
    with pytest.raises(ValidationError):
        TrackObservation(
            provenance=simulation_provenance(),
            icao_hex="A1B2C3",
            observed_at=NOW,
            received_at=NOW,
            latitude=latitude,
            longitude=longitude,
        )


def test_rejects_timezone_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        TrackObservation(
            provenance=simulation_provenance(),
            icao_hex="A1B2C3",
            observed_at=datetime(2026, 7, 18, 12, 0),
            received_at=NOW,
        )


def test_source_specific_provenance_is_required() -> None:
    with pytest.raises(ValidationError, match="receiver_id"):
        ObservationProvenance(
            source_type=ObservationSourceType.LIVE_RF,
            source_id="roof-antenna",
        )

    with pytest.raises(ValidationError, match="recording_id"):
        ObservationProvenance(
            source_type=ObservationSourceType.RECORDED_REPLAY,
            source_id="replay-service",
        )

    with pytest.raises(ValidationError, match="provider"):
        ObservationProvenance(
            source_type=ObservationSourceType.EXTERNAL_FEED,
            source_id="external-adapter",
        )


def test_classifies_stale_out_of_order_and_clock_skew_evidence() -> None:
    observation = TrackObservation(
        provenance=simulation_provenance(),
        icao_hex="A1B2C3",
        observed_at=NOW - timedelta(seconds=45),
        received_at=NOW - timedelta(seconds=50),
    )

    flags = observation.timing_quality_flags(
        reference_time=NOW,
        previous_observed_at=NOW - timedelta(seconds=40),
    )

    assert flags == frozenset(
        {
            ObservationQualityFlag.CLOCK_SKEW,
            ObservationQualityFlag.OUT_OF_ORDER,
            ObservationQualityFlag.STALE,
        }
    )


def test_rejects_negative_timing_tolerance() -> None:
    observation = TrackObservation(
        provenance=simulation_provenance(),
        icao_hex="A1B2C3",
        observed_at=NOW,
        received_at=NOW,
    )

    with pytest.raises(ValueError, match="cannot be negative"):
        observation.timing_quality_flags(reference_time=NOW, stale_after_seconds=-1)


def test_maps_existing_sbs_state_to_shared_contract() -> None:
    observation = sbs_state_to_observation(
        {
            "hex": "a1b2c3",
            "flight": "DAL1842",
            "lat": 39.9612,
            "lon": -82.9988,
            "altitude": 12_500,
            "gs": 310.0,
            "track": 72.0,
            "vert_rate": 800,
            "squawk": "2431",
        },
        source_type=ObservationSourceType.SIMULATION,
        source_id="columbus-demo",
        observed_at=NOW,
        received_at=NOW + timedelta(milliseconds=50),
        raw_message_id="sequence-7",
    )

    assert observation.icao_hex == "A1B2C3"
    assert observation.latitude == 39.9612
    assert observation.altitude_ft == 12_500
    assert observation.quality_flags == frozenset()


def test_marks_sbs_state_without_position_as_partial() -> None:
    observation = sbs_state_to_observation(
        {"hex": "A1B2C3", "flight": "DAL1842"},
        source_type=ObservationSourceType.LIVE_RF,
        source_id="dump1090-sbs",
        receiver_id="roof-receiver",
        observed_at=NOW,
        received_at=NOW,
    )

    assert observation.quality_flags == frozenset({ObservationQualityFlag.PARTIAL})
