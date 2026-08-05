"""Deterministic trajectory-residual evidence over a short observation window."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid5

from ..schemas.observation import TrackObservation
from .kinematics import EARTH_RADIUS_NM, EvaluationStatus


WINDOW_EVALUATION_NAMESPACE = UUID("ea2e0f6f-b0ea-4f54-8366-80be0ce0616b")


class WindowRule(str, Enum):
    CUMULATIVE_POSITION_RESIDUAL = "CUMULATIVE_POSITION_RESIDUAL"


@dataclass(frozen=True)
class WindowPolicy:
    """Development threshold pending calibration against benign captured RF."""

    version: str = "1.0-development"
    minimum_observations: int = 6
    maximum_observations: int = 31
    minimum_duration_seconds: float = 5.0
    maximum_duration_seconds: float = 30.0
    maximum_position_residual_nm: float = 0.002


@dataclass(frozen=True)
class WindowRuleResult:
    rule: WindowRule
    status: EvaluationStatus
    value: float
    threshold: float
    unit: str
    explanation: str
    observation_ids: tuple[UUID, ...]

    @property
    def failed(self) -> bool:
        return self.status is EvaluationStatus.FLAGGED

    def to_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule.value,
            "status": self.status.value,
            "value": self.value,
            "threshold": self.threshold,
            "unit": self.unit,
            "explanation": self.explanation,
            "observation_ids": [str(value) for value in self.observation_ids],
        }


@dataclass(frozen=True)
class WindowEvaluation:
    evaluation_id: UUID
    policy_version: str
    source_type: str
    source_id: str
    icao_hex: str
    evaluated_at: datetime
    status: EvaluationStatus
    reason: str | None
    duration_seconds: float
    measurements: dict[str, float]
    rule_results: tuple[WindowRuleResult, ...]
    observation_ids: tuple[UUID, ...]

    @property
    def failed_rules(self) -> tuple[WindowRuleResult, ...]:
        return tuple(result for result in self.rule_results if result.failed)


def _round(value: float) -> float:
    return round(value, 6)


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
    return math.degrees(next_latitude), (math.degrees(next_longitude) + 180) % 360 - 180


def _distance_nm(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    first_latitude_radians = math.radians(first_latitude)
    second_latitude_radians = math.radians(second_latitude)
    latitude_delta = second_latitude_radians - first_latitude_radians
    longitude_delta = math.radians(second_longitude - first_longitude)
    haversine_value = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(first_latitude_radians)
        * math.cos(second_latitude_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    return EARTH_RADIUS_NM * 2 * math.atan2(
        math.sqrt(haversine_value), math.sqrt(1 - haversine_value)
    )


def _insufficient(
    observations: tuple[TrackObservation, ...],
    policy: WindowPolicy,
    reason: str,
    duration_seconds: float,
) -> WindowEvaluation:
    return _evaluation(
        observations,
        policy,
        status=EvaluationStatus.INSUFFICIENT_DATA,
        reason=reason,
        duration_seconds=duration_seconds,
        measurements={},
        rule_results=(),
    )


def _evaluation(
    observations: tuple[TrackObservation, ...],
    policy: WindowPolicy,
    *,
    status: EvaluationStatus,
    reason: str | None,
    duration_seconds: float,
    measurements: dict[str, float],
    rule_results: tuple[WindowRuleResult, ...],
) -> WindowEvaluation:
    current = observations[-1]
    observation_ids = tuple(observation.observation_id for observation in observations)
    identity = ":".join(str(value) for value in (*observation_ids, policy.version))
    return WindowEvaluation(
        evaluation_id=uuid5(WINDOW_EVALUATION_NAMESPACE, identity),
        policy_version=policy.version,
        source_type=current.provenance.source_type.value,
        source_id=current.provenance.source_id,
        icao_hex=current.icao_hex,
        evaluated_at=current.received_at,
        status=status,
        reason=reason,
        duration_seconds=_round(duration_seconds),
        measurements=measurements,
        rule_results=rule_results,
        observation_ids=observation_ids,
    )


def evaluate_window(
    observations: tuple[TrackObservation, ...],
    *,
    policy: WindowPolicy | None = None,
) -> WindowEvaluation:
    """Compare a reported endpoint with one dead-reckoned from velocity reports."""
    selected_policy = policy or WindowPolicy()
    if not observations:
        raise ValueError("observations must not be empty")
    duration_seconds = (
        observations[-1].observed_at - observations[0].observed_at
    ).total_seconds()
    if len(observations) < selected_policy.minimum_observations:
        return _insufficient(
            observations,
            selected_policy,
            f"At least {selected_policy.minimum_observations} observations are required.",
            duration_seconds,
        )
    if len(observations) > selected_policy.maximum_observations:
        return _insufficient(
            observations,
            selected_policy,
            f"At most {selected_policy.maximum_observations} observations are allowed.",
            duration_seconds,
        )
    first = observations[0]
    if any(
        item.icao_hex != first.icao_hex or item.provenance != first.provenance
        for item in observations[1:]
    ):
        return _insufficient(
            observations,
            selected_policy,
            "Observations must have matching aircraft identity and provenance.",
            duration_seconds,
        )
    if duration_seconds < selected_policy.minimum_duration_seconds:
        return _insufficient(
            observations,
            selected_policy,
            "Observation window is shorter than the policy minimum.",
            duration_seconds,
        )
    if duration_seconds > selected_policy.maximum_duration_seconds:
        return _insufficient(
            observations,
            selected_policy,
            "Observation window exceeds the policy maximum.",
            duration_seconds,
        )
    for previous, current in zip(observations, observations[1:]):
        if current.observed_at <= previous.observed_at:
            return _insufficient(
                observations,
                selected_policy,
                "Observation timestamps must increase strictly.",
                duration_seconds,
            )
    if any(
        item.latitude is None
        or item.longitude is None
        or item.ground_speed_knots is None
        or item.track_degrees is None
        for item in observations
    ):
        return _insufficient(
            observations,
            selected_policy,
            "Every observation requires position, ground speed, and track.",
            duration_seconds,
        )

    predicted_latitude = observations[0].latitude or 0
    predicted_longitude = observations[0].longitude or 0
    for previous, current in zip(observations, observations[1:]):
        interval_seconds = (current.observed_at - previous.observed_at).total_seconds()
        distance_nm = (previous.ground_speed_knots or 0) * interval_seconds / 3600
        predicted_latitude, predicted_longitude = _destination(
            predicted_latitude,
            predicted_longitude,
            previous.track_degrees or 0,
            distance_nm,
        )

    current = observations[-1]
    residual_nm = _distance_nm(
        predicted_latitude,
        predicted_longitude,
        current.latitude or 0,
        current.longitude or 0,
    )
    failed = residual_nm > selected_policy.maximum_position_residual_nm
    result = WindowRuleResult(
        rule=WindowRule.CUMULATIVE_POSITION_RESIDUAL,
        status=EvaluationStatus.FLAGGED if failed else EvaluationStatus.PASS,
        value=_round(residual_nm),
        threshold=selected_policy.maximum_position_residual_nm,
        unit="nautical_miles",
        explanation=(
            "Dead-reckoned endpoint residual exceeds the development policy limit."
            if failed
            else "Dead-reckoned endpoint residual is within the development policy limit."
        ),
        observation_ids=tuple(item.observation_id for item in observations),
    )
    return _evaluation(
        observations,
        selected_policy,
        status=result.status,
        reason=None,
        duration_seconds=duration_seconds,
        measurements={
            "predicted_latitude": _round(predicted_latitude),
            "predicted_longitude": _round(predicted_longitude),
            "reported_latitude": _round(current.latitude or 0),
            "reported_longitude": _round(current.longitude or 0),
            "position_residual_nm": _round(residual_nm),
        },
        rule_results=(result,),
    )
