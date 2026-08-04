"""Calibration metrics for captured or generated aircraft observations."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.observation import ObservationSourceType, TrackObservation
from app.services.kinematics import (
    EvaluationStatus,
    KinematicEvaluation,
    KinematicPolicy,
    evaluate_pair,
)
from app.services.windowed_kinematics import (
    WindowEvaluation,
    WindowPolicy,
    evaluate_window,
)


class DatasetClass(str, Enum):
    CAPTURED_RF = "CAPTURED_RF"
    GENERATED_CONTROL = "GENERATED_CONTROL"


class ReviewStatus(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    ROUTINE_TRAFFIC_REVIEWED = "ROUTINE_TRAFFIC_REVIEWED"


class CalibrationManifest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    dataset_class: DatasetClass
    review_status: ReviewStatus
    source_type: ObservationSourceType
    source_id: str = Field(min_length=1, max_length=100)
    receiver_id: str | None = Field(default=None, min_length=1, max_length=100)
    license_id: str = Field(min_length=1, max_length=100)
    attribution: str = Field(min_length=1, max_length=500)
    captured_from: datetime
    captured_to: datetime
    observation_count: int = Field(ge=1)
    observations_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_claim_context(self) -> "CalibrationManifest":
        if self.captured_to < self.captured_from:
            raise ValueError("captured_to must not precede captured_from")
        if self.dataset_class is DatasetClass.CAPTURED_RF:
            if self.source_type is not ObservationSourceType.LIVE_RF:
                raise ValueError("CAPTURED_RF datasets require LIVE_RF observations")
            if not self.receiver_id:
                raise ValueError("CAPTURED_RF datasets require receiver_id")
        if (
            self.review_status is ReviewStatus.ROUTINE_TRAFFIC_REVIEWED
            and self.dataset_class is not DatasetClass.CAPTURED_RF
        ):
            raise ValueError("only CAPTURED_RF data can be marked routine-traffic reviewed")
        return self

    @property
    def routine_alert_rate_eligible(self) -> bool:
        return (
            self.dataset_class is DatasetClass.CAPTURED_RF
            and self.source_type is ObservationSourceType.LIVE_RF
            and self.review_status is ReviewStatus.ROUTINE_TRAFFIC_REVIEWED
        )


@dataclass(frozen=True)
class CalibrationPolicy:
    version: str = "1.0"
    maximum_activity_gap_seconds: float = 30.0
    episode_gap_seconds: float = 30.0


@dataclass(frozen=True)
class AlertEvent:
    track_key: tuple[str, ...]
    observed_at: datetime
    evidence_type: str
    rules: tuple[str, ...]


@dataclass
class AlertEpisode:
    icao_hex: str
    source_type: str
    source_id: str
    receiver_id: str | None
    started_at: datetime
    ended_at: datetime
    evaluation_count: int
    evidence_types: set[str]
    rules: set[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "icao_hex": self.icao_hex,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "receiver_id": self.receiver_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "duration_seconds": round(
                (self.ended_at - self.started_at).total_seconds(), 3
            ),
            "evaluation_count": self.evaluation_count,
            "evidence_types": sorted(self.evidence_types),
            "rules": sorted(self.rules),
        }


def _track_key(observation: TrackObservation) -> tuple[str, ...]:
    provenance = observation.provenance
    return (
        observation.icao_hex,
        provenance.source_type.value,
        provenance.source_id,
        provenance.receiver_id or "",
        provenance.recording_id or "",
        provenance.provider or "",
        provenance.license_id or "",
    )


def _percentiles(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(values)

    def nearest_rank(percentile: float) -> float | None:
        if not ordered:
            return None
        index = max(0, math.ceil(percentile * len(ordered)) - 1)
        return round(ordered[index], 6)

    return {
        "p50": nearest_rank(0.50),
        "p95": nearest_rank(0.95),
        "p99": nearest_rank(0.99),
        "maximum": round(ordered[-1], 6) if ordered else None,
    }


def _status_counts(evaluations: Iterable[object]) -> dict[str, int]:
    counts = {status.value: 0 for status in EvaluationStatus}
    for evaluation in evaluations:
        counts[evaluation.status.value] += 1
    return counts


def _activity_seconds(
    tracks: Iterable[tuple[TrackObservation, ...]], policy: CalibrationPolicy
) -> float:
    total = 0.0
    for observations in tracks:
        for previous, current in zip(observations, observations[1:]):
            delta = (current.observed_at - previous.observed_at).total_seconds()
            if 0 < delta <= policy.maximum_activity_gap_seconds:
                total += delta
    return total


def _window_evaluations(
    observations: tuple[TrackObservation, ...], policy: WindowPolicy
) -> Iterator[WindowEvaluation]:
    active: deque[TrackObservation] = deque(maxlen=policy.maximum_observations)
    for observation in observations:
        cutoff = observation.observed_at.timestamp() - policy.maximum_duration_seconds
        while active and active[0].observed_at.timestamp() < cutoff:
            active.popleft()
        active.append(observation)
        if len(active) >= policy.minimum_observations:
            yield evaluate_window(tuple(active), policy=policy)


def _events(
    pairs: Iterable[KinematicEvaluation],
    windows: Iterable[WindowEvaluation],
    observation_index: dict[UUID, TrackObservation],
) -> list[AlertEvent]:
    events = []
    for evidence_type, evaluations in (("PAIR", pairs), ("WINDOW", windows)):
        for evaluation in evaluations:
            if evaluation.status is not EvaluationStatus.FLAGGED:
                continue
            current_observation_id = (
                evaluation.current_observation_id
                if isinstance(evaluation, KinematicEvaluation)
                else evaluation.observation_ids[-1]
            )
            current_observation = observation_index[current_observation_id]
            events.append(
                AlertEvent(
                    track_key=_track_key(current_observation),
                    observed_at=current_observation.observed_at,
                    evidence_type=evidence_type,
                    rules=tuple(rule.rule.value for rule in evaluation.failed_rules),
                )
            )
    return events


def group_alert_episodes(
    events: Iterable[AlertEvent], *, gap_seconds: float
) -> list[AlertEpisode]:
    grouped: dict[tuple[str, ...], list[AlertEvent]] = defaultdict(list)
    for event in events:
        grouped[event.track_key].append(event)

    episodes = []
    for key, track_events in sorted(grouped.items()):
        current: AlertEpisode | None = None
        for event in sorted(track_events, key=lambda item: item.observed_at):
            starts_new = (
                current is None
                or (event.observed_at - current.ended_at).total_seconds() > gap_seconds
            )
            if starts_new:
                current = AlertEpisode(
                    icao_hex=key[0],
                    source_type=key[1],
                    source_id=key[2],
                    receiver_id=key[3] or None,
                    started_at=event.observed_at,
                    ended_at=event.observed_at,
                    evaluation_count=1,
                    evidence_types={event.evidence_type},
                    rules=set(event.rules),
                )
                episodes.append(current)
                continue
            current.ended_at = event.observed_at
            current.evaluation_count += 1
            current.evidence_types.add(event.evidence_type)
            current.rules.update(event.rules)
    return episodes


def _rate(count: int, observed_track_hours: float) -> float | None:
    if observed_track_hours <= 0:
        return None
    return round(count / observed_track_hours, 6)


def build_calibration_report(
    manifest: CalibrationManifest,
    observations: Iterable[TrackObservation],
    *,
    calibration_policy: CalibrationPolicy | None = None,
    pair_policy: KinematicPolicy | None = None,
    window_policy: WindowPolicy | None = None,
) -> dict[str, object]:
    selected_calibration_policy = calibration_policy or CalibrationPolicy()
    selected_pair_policy = pair_policy or KinematicPolicy()
    selected_window_policy = window_policy or WindowPolicy()
    materialized = tuple(observations)
    validate_observations(manifest, materialized)

    grouped: dict[tuple[str, ...], list[TrackObservation]] = defaultdict(list)
    for observation in materialized:
        grouped[_track_key(observation)].append(observation)
    tracks = tuple(
        tuple(sorted(items, key=lambda item: (item.observed_at, str(item.observation_id))))
        for items in grouped.values()
    )
    pairs = [
        evaluate_pair(previous, current, policy=selected_pair_policy)
        for track in tracks
        for previous, current in zip(track, track[1:])
    ]
    windows = [
        evaluation
        for track in tracks
        for evaluation in _window_evaluations(track, selected_window_policy)
    ]
    observation_index = {item.observation_id: item for item in materialized}
    episodes = group_alert_episodes(
        _events(pairs, windows, observation_index),
        gap_seconds=selected_calibration_policy.episode_gap_seconds,
    )
    observed_track_hours = round(
        _activity_seconds(tracks, selected_calibration_policy) / 3600,
        6,
    )
    pair_flagged = sum(item.status is EvaluationStatus.FLAGGED for item in pairs)
    window_flagged = sum(item.status is EvaluationStatus.FLAGGED for item in windows)
    pair_speeds = [
        value
        for item in pairs
        if (value := item.measurements.get("implied_ground_speed_knots")) is not None
    ]
    window_residuals = [
        value
        for item in windows
        if (value := item.measurements.get("position_residual_nm")) is not None
    ]
    return {
        "report_schema_version": "1.0",
        "dataset": manifest.model_dump(mode="json"),
        "claim_scope": (
            "reviewed_routine_rf_alert_rate"
            if manifest.routine_alert_rate_eligible
            else "engineering_validation_only"
        ),
        "routine_alert_rate_eligible": manifest.routine_alert_rate_eligible,
        "policies": {
            "calibration": asdict(selected_calibration_policy),
            "pair": asdict(selected_pair_policy),
            "window": asdict(selected_window_policy),
        },
        "coverage": {
            "observations": len(materialized),
            "aircraft": len({item.icao_hex for item in materialized}),
            "source_tracks": len(tracks),
            "observed_track_hours": observed_track_hours,
        },
        "pair_evidence": {
            "evaluations": len(pairs),
            "status_counts": _status_counts(pairs),
            "flagged_evaluations_per_observed_track_hour": _rate(
                pair_flagged, observed_track_hours
            ),
            "implied_speed_knots": _percentiles(pair_speeds),
        },
        "window_evidence": {
            "evaluations": len(windows),
            "status_counts": _status_counts(windows),
            "flagged_evaluations_per_observed_track_hour": _rate(
                window_flagged, observed_track_hours
            ),
            "position_residual_nm": _percentiles(window_residuals),
        },
        "alert_episodes": {
            "count": len(episodes),
            "per_observed_track_hour": _rate(len(episodes), observed_track_hours),
            "items": [episode.to_dict() for episode in episodes],
        },
        "limitations": [
            "An alert episode is evidence of internal inconsistency, not proof of spoofing.",
            "Observed track hours sum only positive same-track gaps within the calibration policy limit.",
            "Routine RF alert rate is not a false-positive rate without authoritative ground truth.",
        ],
    }


def validate_observations(
    manifest: CalibrationManifest, observations: tuple[TrackObservation, ...]
) -> None:
    if len(observations) != manifest.observation_count:
        raise ValueError("observation count does not match manifest")
    if len({item.observation_id for item in observations}) != len(observations):
        raise ValueError("observation IDs must be unique")
    for observation in observations:
        provenance = observation.provenance
        if provenance.source_type is not manifest.source_type:
            raise ValueError("observation source_type does not match manifest")
        if provenance.source_id != manifest.source_id:
            raise ValueError("observation source_id does not match manifest")
        if provenance.receiver_id != manifest.receiver_id:
            raise ValueError("observation receiver_id does not match manifest")
        if not manifest.captured_from <= observation.observed_at <= manifest.captured_to:
            raise ValueError("observation timestamp falls outside manifest range")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_calibration_dataset(
    manifest_path: Path, observations_path: Path
) -> tuple[CalibrationManifest, tuple[TrackObservation, ...]]:
    manifest = CalibrationManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if file_sha256(observations_path) != manifest.observations_sha256:
        raise ValueError("observations_sha256 does not match JSONL file")
    observations = []
    with observations_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                observations.append(TrackObservation.model_validate_json(line))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid observation on JSONL line {line_number}") from exc
    materialized = tuple(observations)
    validate_observations(manifest, materialized)
    return manifest, materialized
