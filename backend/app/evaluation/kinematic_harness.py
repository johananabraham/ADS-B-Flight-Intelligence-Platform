"""Leakage-safe synthetic scenarios for the deterministic kinematic policy."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable
from uuid import UUID, uuid5

from app.schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from app.services.kinematics import EvaluationStatus, KinematicPolicy, evaluate_pair


GENERATOR_VERSION = "1.0"
SCENARIO_NAMESPACE = UUID("f8be37ef-1a4e-459e-a532-42a9df0f4571")
EARTH_RADIUS_NM = 3440.065


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class ScenarioType(str, Enum):
    CLEAN = "CLEAN"
    ABRUPT_POSITION = "ABRUPT_POSITION"
    ABRUPT_ALTITUDE = "ABRUPT_ALTITUDE"
    ABRUPT_VELOCITY = "ABRUPT_VELOCITY"
    ABRUPT_HEADING = "ABRUPT_HEADING"
    GRADUAL_POSITION_DRIFT = "GRADUAL_POSITION_DRIFT"
    REPLAYED_TIMESTAMP = "REPLAYED_TIMESTAMP"


@dataclass(frozen=True)
class DetectionWindow:
    start_index: int
    end_index: int


@dataclass(frozen=True)
class KinematicScenario:
    scenario_id: str
    source_session_id: str
    split: DatasetSplit
    scenario_type: ScenarioType
    generator_version: str
    seed: int
    source_sha256: str
    attack_parameters: dict[str, float | int | str]
    detection_window: DetectionWindow | None
    observations: tuple[TrackObservation, ...]


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    source_session_id: str
    split: DatasetSplit
    scenario_type: ScenarioType
    pair_count: int
    flagged_pair_count: int
    insufficient_pair_count: int
    detected: bool
    time_to_detect_seconds: float | None


def split_for_session(source_session_id: str) -> DatasetSplit:
    """Assign an entire source session before any attacked variants are created."""
    bucket = int.from_bytes(
        hashlib.sha256(source_session_id.encode("utf-8")).digest()[:8], "big"
    ) % 10
    if bucket < 6:
        return DatasetSplit.TRAIN
    if bucket < 8:
        return DatasetSplit.VALIDATION
    return DatasetSplit.TEST


def _destination(
    latitude: float,
    longitude: float,
    bearing_degrees: float,
    distance_nm: float,
) -> tuple[float, float]:
    angular_distance = distance_nm / EARTH_RADIUS_NM
    latitude_radians = math.radians(latitude)
    longitude_radians = math.radians(longitude)
    bearing_radians = math.radians(bearing_degrees)
    next_latitude = math.asin(
        math.sin(latitude_radians) * math.cos(angular_distance)
        + math.cos(latitude_radians)
        * math.sin(angular_distance)
        * math.cos(bearing_radians)
    )
    next_longitude = longitude_radians + math.atan2(
        math.sin(bearing_radians)
        * math.sin(angular_distance)
        * math.cos(latitude_radians),
        math.cos(angular_distance)
        - math.sin(latitude_radians) * math.sin(next_latitude),
    )
    normalized_longitude = (math.degrees(next_longitude) + 180) % 360 - 180
    return math.degrees(next_latitude), normalized_longitude


def _observation_id(scenario_id: str, index: int) -> UUID:
    return uuid5(SCENARIO_NAMESPACE, f"{scenario_id}:{index}")


def _make_observation(
    *,
    scenario_id: str,
    source_session_id: str,
    index: int,
    observed_at: datetime,
    latitude: float,
    longitude: float,
    altitude_ft: int,
    speed_knots: float,
    track_degrees: float,
) -> TrackObservation:
    return TrackObservation(
        observation_id=_observation_id(scenario_id, index),
        provenance=ObservationProvenance(
            source_type=ObservationSourceType.SIMULATION,
            source_id=f"kinematic-eval-{source_session_id}",
        ),
        icao_hex=f"{int(source_session_id.split('-')[-1]):06X}",
        observed_at=observed_at,
        received_at=observed_at,
        latitude=latitude,
        longitude=longitude,
        altitude_ft=altitude_ft,
        ground_speed_knots=speed_knots,
        track_degrees=track_degrees,
    )


def _clean_observations(source_session_id: str, seed: int) -> tuple[TrackObservation, ...]:
    random_source = random.Random(seed)
    scenario_id = f"{source_session_id}-source"
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=seed)
    latitude = random_source.uniform(-70, 70)
    longitude = random_source.uniform(-170, 170)
    altitude = random_source.randint(5_000, 35_000)
    speed = random_source.uniform(120, 480)
    track = random_source.uniform(0, 360)
    observations = []
    for index in range(12):
        observations.append(
            _make_observation(
                scenario_id=scenario_id,
                source_session_id=source_session_id,
                index=index,
                observed_at=timestamp + timedelta(seconds=index),
                latitude=latitude,
                longitude=longitude,
                altitude_ft=altitude,
                speed_knots=speed,
                track_degrees=track,
            )
        )
        latitude, longitude = _destination(latitude, longitude, track, speed / 3600)
    return tuple(observations)


def _source_hash(observations: Iterable[TrackObservation]) -> str:
    source = [
        observation.model_dump(mode="json", exclude={"observation_id"})
        for observation in observations
    ]
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _variant_observations(
    source: tuple[TrackObservation, ...],
    scenario_id: str,
    scenario_type: ScenarioType,
    attack_start: int,
) -> tuple[TrackObservation, ...]:
    variant = []
    for index, observation in enumerate(source):
        update: dict[str, object] = {"observation_id": _observation_id(scenario_id, index)}
        if scenario_type is ScenarioType.ABRUPT_POSITION and index == attack_start:
            update["latitude"] = (observation.latitude or 0) + 0.05
        elif scenario_type is ScenarioType.ABRUPT_ALTITUDE and index == attack_start:
            update["altitude_ft"] = (observation.altitude_ft or 0) + 500
        elif scenario_type is ScenarioType.ABRUPT_VELOCITY and index == attack_start:
            update["ground_speed_knots"] = (observation.ground_speed_knots or 0) + 100
        elif scenario_type is ScenarioType.ABRUPT_HEADING and index == attack_start:
            update["track_degrees"] = ((observation.track_degrees or 0) + 90) % 360
        elif scenario_type is ScenarioType.GRADUAL_POSITION_DRIFT and index >= attack_start:
            update["longitude"] = (observation.longitude or 0) + (index - attack_start + 1) * 0.00002
        elif scenario_type is ScenarioType.REPLAYED_TIMESTAMP and index == attack_start:
            replayed_at = source[index - 1].observed_at
            update["observed_at"] = replayed_at
            update["received_at"] = replayed_at
            update["ground_speed_knots"] = None
        variant.append(observation.model_copy(update=update))
    return tuple(variant)


def _attack_parameters(scenario_type: ScenarioType, attack_start: int) -> dict[str, float | int | str]:
    shared: dict[str, float | int | str] = {"attack_start_index": attack_start}
    specific: dict[ScenarioType, tuple[str, float | int | str]] = {
        ScenarioType.ABRUPT_POSITION: ("position_jump_degrees", 0.05),
        ScenarioType.ABRUPT_ALTITUDE: ("altitude_jump_feet", 500),
        ScenarioType.ABRUPT_VELOCITY: ("velocity_jump_knots", 100),
        ScenarioType.ABRUPT_HEADING: ("heading_jump_degrees", 90),
        ScenarioType.GRADUAL_POSITION_DRIFT: (
            "drift_degrees_per_observation",
            0.00002,
        ),
        ScenarioType.REPLAYED_TIMESTAMP: ("replayed_observations", 1),
    }
    name, value = specific[scenario_type]
    return {**shared, name: value}


def generate_dataset(*, seed: int = 20260720, session_count: int = 90) -> tuple[KinematicScenario, ...]:
    """Generate deterministic variants while preserving source-session isolation."""
    if session_count < 1:
        raise ValueError("session_count must be positive")
    scenarios = []
    for session_index in range(session_count):
        source_session_id = f"session-{session_index:04d}"
        session_seed = seed + session_index
        source = _clean_observations(source_session_id, session_seed)
        source_sha256 = _source_hash(source)
        split = split_for_session(source_session_id)
        attack_start = 5
        for scenario_type in ScenarioType:
            scenario_id = f"{source_session_id}-{scenario_type.value.lower()}"
            attacked = scenario_type is not ScenarioType.CLEAN
            observations = (
                _variant_observations(source, scenario_id, scenario_type, attack_start)
                if attacked
                else tuple(
                    observation.model_copy(
                        update={"observation_id": _observation_id(scenario_id, index)}
                    )
                    for index, observation in enumerate(source)
                )
            )
            parameters = _attack_parameters(scenario_type, attack_start) if attacked else {}
            scenarios.append(
                KinematicScenario(
                    scenario_id=scenario_id,
                    source_session_id=source_session_id,
                    split=split,
                    scenario_type=scenario_type,
                    generator_version=GENERATOR_VERSION,
                    seed=session_seed,
                    source_sha256=source_sha256,
                    attack_parameters=parameters,
                    detection_window=(
                        DetectionWindow(attack_start, len(observations) - 1)
                        if attacked
                        else None
                    ),
                    observations=observations,
                )
            )
    return tuple(scenarios)


def evaluate_scenario(
    scenario: KinematicScenario,
    *,
    policy: KinematicPolicy | None = None,
) -> ScenarioResult:
    evaluations = [
        evaluate_pair(previous, current, policy=policy)
        for previous, current in zip(scenario.observations, scenario.observations[1:])
    ]
    flagged_indices = [
        index
        for index, evaluation in enumerate(evaluations, start=1)
        if evaluation.status is EvaluationStatus.FLAGGED
    ]
    detected_indices = flagged_indices
    if scenario.detection_window is not None:
        detected_indices = [
            index
            for index in flagged_indices
            if scenario.detection_window.start_index <= index <= scenario.detection_window.end_index
        ]
    detected = bool(detected_indices)
    time_to_detect = None
    if detected and scenario.detection_window is not None:
        attack_time = scenario.observations[scenario.detection_window.start_index].observed_at
        detection_time = scenario.observations[detected_indices[0]].observed_at
        time_to_detect = (detection_time - attack_time).total_seconds()
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        source_session_id=scenario.source_session_id,
        split=scenario.split,
        scenario_type=scenario.scenario_type,
        pair_count=len(evaluations),
        flagged_pair_count=len(flagged_indices),
        insufficient_pair_count=sum(
            evaluation.status is EvaluationStatus.INSUFFICIENT_DATA
            for evaluation in evaluations
        ),
        detected=detected,
        time_to_detect_seconds=time_to_detect,
    )


def build_report(
    scenarios: Iterable[KinematicScenario],
    *,
    split: DatasetSplit = DatasetSplit.TEST,
    policy: KinematicPolicy | None = None,
) -> dict[str, object]:
    """Evaluate one held-out split and return machine-readable synthetic metrics."""
    selected_policy = policy or KinematicPolicy()
    selected = [scenario for scenario in scenarios if scenario.split is split]
    results = [evaluate_scenario(scenario, policy=selected_policy) for scenario in selected]
    by_type: dict[str, dict[str, object]] = {}
    for scenario_type in ScenarioType:
        type_results = [result for result in results if result.scenario_type is scenario_type]
        detections = sum(result.detected for result in type_results)
        delays = [
            result.time_to_detect_seconds
            for result in type_results
            if result.time_to_detect_seconds is not None
        ]
        by_type[scenario_type.value] = {
            "scenarios": len(type_results),
            "detected": detections,
            "detection_rate": round(detections / len(type_results), 4) if type_results else None,
            "flagged_pairs": sum(result.flagged_pair_count for result in type_results),
            "insufficient_pairs": sum(result.insufficient_pair_count for result in type_results),
            "median_time_to_detect_seconds": statistics.median(delays) if delays else None,
        }
    clean = by_type[ScenarioType.CLEAN.value]
    attacked_results = [
        result for result in results if result.scenario_type is not ScenarioType.CLEAN
    ]
    return {
        "report_schema_version": "1.0",
        "scope": "synthetic_scenarios_only",
        "limitations": [
            "Synthetic clean alert rate is not a real-world false-positive rate.",
            "The rules-only engine evaluates consecutive pairs and is expected to miss subtle gradual drift.",
            "INSUFFICIENT_DATA is reported separately and never counted as detection.",
        ],
        "generator": {
            "version": GENERATOR_VERSION,
            "seeds": sorted({scenario.seed for scenario in selected}),
            "source_session_count": len({scenario.source_session_id for scenario in selected}),
        },
        "policy_version": selected_policy.version,
        "evaluated_split": split.value,
        "scenario_count": len(results),
        "pair_count": sum(result.pair_count for result in results),
        "synthetic_clean_sequence_alert_rate": clean["detection_rate"],
        "attack_detection_rate": round(
            sum(result.detected for result in attacked_results) / len(attacked_results), 4
        )
        if attacked_results
        else None,
        "metrics_by_scenario_type": by_type,
        "scenario_manifest": [
            {
                "scenario_id": scenario.scenario_id,
                "source_session_id": scenario.source_session_id,
                "split": scenario.split.value,
                "scenario_type": scenario.scenario_type.value,
                "generator_version": scenario.generator_version,
                "seed": scenario.seed,
                "source_sha256": scenario.source_sha256,
                "attack_parameters": scenario.attack_parameters,
                "detection_window": (
                    asdict(scenario.detection_window)
                    if scenario.detection_window is not None
                    else None
                ),
                "observation_count": len(scenario.observations),
            }
            for scenario in selected
        ],
        "scenarios": [asdict(result) for result in results],
    }


def validate_no_split_leakage(scenarios: Iterable[KinematicScenario]) -> None:
    """Fail if variants from one original session cross dataset splits."""
    session_splits: dict[str, DatasetSplit] = {}
    for scenario in scenarios:
        existing = session_splits.setdefault(scenario.source_session_id, scenario.split)
        if existing is not scenario.split:
            raise ValueError(
                f"source session {scenario.source_session_id} crosses dataset splits"
            )
