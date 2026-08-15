"""Acceptance tests for the shared database-independent integrity core."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from integrity_core import (
    EvidenceKind,
    IntegrityEngine,
    PolicyError,
    TrackState,
    load_policy,
)
from integrity_core.policy import IntegrityPolicy, policy_from_dict


START = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
POLICY_PATH = Path(__file__).parents[1] / "integrity_core/policies/feeder-v1.json"


def observation(
    index: int,
    *,
    latitude: float | None = None,
    longitude: float | None = 0,
    source_type: ObservationSourceType = ObservationSourceType.SIMULATION,
    observed_offset: float | None = None,
    received_offset: float | None = None,
    raw_id: str | None = None,
) -> TrackObservation:
    seconds = float(index if observed_offset is None else observed_offset)
    received = seconds if received_offset is None else received_offset
    if latitude is None:
        latitude = index * (300 / 3600 / 60)
    recording_id = "golden-recording" if source_type is ObservationSourceType.RECORDED_REPLAY else None
    return TrackObservation(
        observation_id=uuid5(NAMESPACE_URL, f"core:{index}:{seconds}:{latitude}:{source_type}"),
        provenance=ObservationProvenance(
            source_type=source_type,
            source_id="core-test",
            recording_id=recording_id,
        ),
        icao_hex="A1B2C3",
        observed_at=START + timedelta(seconds=seconds),
        received_at=START + timedelta(seconds=received),
        latitude=latitude,
        longitude=longitude,
        altitude_ft=10_000,
        ground_speed_knots=300,
        track_degrees=0,
        raw_message_id=raw_id or f"message-{index}",
    )


def test_nominal_requires_minimum_data_and_never_claims_trusted() -> None:
    engine = IntegrityEngine(load_policy(POLICY_PATH))
    first, _ = engine.ingest(observation(0))
    second, _ = engine.ingest(observation(1))

    assert first.state is TrackState.INSUFFICIENT_DATA
    assert second.state is TrackState.NOMINAL
    assert "TRUSTED" not in str(second.public_dict())


def test_impossible_jump_opens_explainable_pair_evidence() -> None:
    engine = IntegrityEngine(load_policy(POLICY_PATH))
    engine.ingest(observation(0, latitude=0))
    snapshot, events = engine.ingest(observation(1, latitude=0.05))

    assert snapshot.state is TrackState.QUESTIONABLE
    assert EvidenceKind.PAIR_KINEMATIC in {item.kind for item in snapshot.active_evidence}
    assert any(event.event_type.value == "evidence_opened" for event in events)
    evidence = snapshot.active_evidence[0].public_dict()
    assert evidence["summary"]
    assert evidence["measured"]
    assert evidence["thresholds"]


def test_duplicate_non_increasing_out_of_order_gap_and_latency_are_distinct() -> None:
    policy = load_policy(POLICY_PATH)
    engine = IntegrityEngine(policy)
    engine.ingest(observation(0, raw_id="same"))
    duplicate, _ = engine.ingest(observation(1, observed_offset=0, raw_id="same"))
    engine.ingest(observation(2, observed_offset=10))
    reordered, _ = engine.ingest(observation(3, observed_offset=1))
    gap, _ = engine.ingest(observation(4, observed_offset=50, received_offset=100))
    kinds = {item.kind for item in (*duplicate.active_evidence, *reordered.active_evidence, *gap.active_evidence)}

    assert EvidenceKind.TIMING_DUPLICATE in kinds
    assert EvidenceKind.TIMING_NON_INCREASING in kinds
    assert EvidenceKind.TIMING_OUT_OF_ORDER in kinds
    assert EvidenceKind.TIMING_GAP in kinds
    assert EvidenceKind.TIMING_EXCESSIVE_LATENCY in kinds


def test_replay_clock_is_not_compared_with_wall_clock_latency() -> None:
    engine = IntegrityEngine(load_policy(POLICY_PATH))
    engine.ingest(
        observation(
            0,
            source_type=ObservationSourceType.RECORDED_REPLAY,
            received_offset=3600,
        )
    )
    snapshot, _ = engine.ingest(
        observation(
            1,
            source_type=ObservationSourceType.RECORDED_REPLAY,
            received_offset=3601,
        )
    )

    assert EvidenceKind.TIMING_EXCESSIVE_LATENCY not in {
        item.kind for item in snapshot.active_evidence
    }


def test_evidence_expires_then_state_returns_to_nominal() -> None:
    policy = replace(
        load_policy(POLICY_PATH),
        timing=replace(load_policy(POLICY_PATH).timing, evidence_ttl_seconds=2, gap_seconds=100),
    )
    engine = IntegrityEngine(policy)
    engine.ingest(observation(0, latitude=0))
    flagged, _ = engine.ingest(observation(1, latitude=0.05))
    recovered, events = engine.ingest(observation(4, latitude=0.0541667))

    assert flagged.state is TrackState.QUESTIONABLE
    assert recovered.state is TrackState.NOMINAL
    assert any(event.event_type.value == "evidence_closed" for event in events)


def test_golden_replay_produces_identical_snapshots_events_and_ids() -> None:
    policy = load_policy(POLICY_PATH)
    inputs = [observation(0, latitude=0), observation(1, latitude=0.05)]

    def replay():
        engine = IntegrityEngine(policy)
        return [
            (snapshot.public_dict(), [event.public_dict() for event in events])
            for snapshot, events in (engine.ingest(item) for item in inputs)
        ]

    assert replay() == replay()


def test_policy_rejects_unknown_fields_and_breaking_versions() -> None:
    with pytest.raises(PolicyError, match="unknown policy fields"):
        policy_from_dict({"schema_version": "1.0", "policy_version": "x", "surprise": 1})
    with pytest.raises(PolicyError, match="only integrity policy"):
        policy_from_dict({"schema_version": "2.0", "policy_version": "x"})


def test_track_cache_eviction_is_bounded_and_deterministic() -> None:
    policy = replace(
        IntegrityPolicy(),
        runtime=replace(IntegrityPolicy().runtime, maximum_tracks=2),
    )
    engine = IntegrityEngine(policy)
    first = observation(0)
    engine.ingest(first)
    engine.ingest(observation(1).model_copy(update={"icao_hex": "B1B2C3"}))
    engine.ingest(observation(2).model_copy(update={"icao_hex": "C1B2C3"}))

    assert len(engine.snapshots()) == 2
    assert engine.snapshot(engine.track_id(first)) is None
