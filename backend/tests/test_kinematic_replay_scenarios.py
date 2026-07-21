"""Golden replay scenarios for clean and intentionally impossible motion."""

from collections import defaultdict
from pathlib import Path

from app.schemas.observation import ObservationSourceType, TrackObservation
from app.services.kinematics import EvaluationStatus, KinematicRule, evaluate_pair
from app.services.observation_adapters import sbs_state_to_observation
from services.ingestion.ingest import parse_sbs_message
from services.replay.recording import Recording


RECORDINGS = Path("services/replay/recordings")


def observations_from_recording(filename: str) -> dict[str, list[TrackObservation]]:
    recording = Recording.load(RECORDINGS / filename)
    observations: dict[str, list[TrackObservation]] = defaultdict(list)
    for event in recording.events:
        parsed = parse_sbs_message(event.sbs_message)
        assert parsed is not None
        observation = sbs_state_to_observation(
            parsed,
            source_type=ObservationSourceType.RECORDED_REPLAY,
            source_id="golden-scenario",
            recording_id=recording.recording_id,
            observed_at=event.observed_at,
            received_at=event.observed_at,
            raw_message_id=parsed["_raw_message_id"],
        )
        observations[observation.icao_hex].append(observation)
    return observations


def test_clean_recording_has_zero_kinematic_flags() -> None:
    aircraft = observations_from_recording("columbus_generated_v2.json")

    evaluations = [
        evaluate_pair(previous, current)
        for observations in aircraft.values()
        for previous, current in zip(observations, observations[1:])
    ]

    assert len(evaluations) == 4
    assert all(evaluation.status is EvaluationStatus.PASS for evaluation in evaluations)


def test_attack_recording_triggers_every_rule() -> None:
    observations = observations_from_recording("kinematic_attack_generated_v2.json")[
        "A0B0C0"
    ]

    evaluation = evaluate_pair(observations[0], observations[1])
    failed_rules = {result.rule for result in evaluation.failed_rules}

    assert evaluation.status is EvaluationStatus.FLAGGED
    assert failed_rules == set(KinematicRule)
