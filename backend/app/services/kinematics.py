"""Deterministic kinematic checks over consecutive immutable observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid5

from ..schemas.observation import TrackObservation


EVALUATION_NAMESPACE = UUID("0a2fc740-486d-4dd1-a052-e00b08f64cee")
EARTH_RADIUS_NM = 3440.065


class EvaluationStatus(str, Enum):
    PASS = "PASS"
    FLAGGED = "FLAGGED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class KinematicRule(str, Enum):
    IMPLIED_GROUND_SPEED = "IMPLIED_GROUND_SPEED"
    REPORTED_ACCELERATION = "REPORTED_ACCELERATION"
    TURN_RATE = "TURN_RATE"
    DERIVED_VERTICAL_RATE = "DERIVED_VERTICAL_RATE"
    SPEED_DISAGREEMENT = "SPEED_DISAGREEMENT"


@dataclass(frozen=True)
class KinematicPolicy:
    """Conservative general-aircraft limits; not an aircraft performance model."""

    version: str = "1.0"
    minimum_interval_seconds: float = 0.5
    maximum_interval_seconds: float = 30.0
    maximum_implied_speed_knots: float = 750.0
    maximum_acceleration_knots_per_second: float = 20.0
    maximum_turn_rate_degrees_per_second: float = 12.0
    maximum_vertical_rate_fpm: float = 10_000.0
    minimum_speed_for_turn_check_knots: float = 40.0
    minimum_speed_disagreement_knots: float = 200.0
    speed_disagreement_fraction: float = 0.5


@dataclass(frozen=True)
class RuleResult:
    rule: KinematicRule
    status: EvaluationStatus
    value: float
    threshold: float
    unit: str
    explanation: str
    observation_ids: tuple[UUID, UUID]

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
class KinematicEvaluation:
    evaluation_id: UUID
    policy_version: str
    previous_observation_id: UUID
    current_observation_id: UUID
    source_type: str
    source_id: str
    icao_hex: str
    evaluated_at: datetime
    status: EvaluationStatus
    reason: str | None
    delta_seconds: float
    measurements: dict[str, float]
    rule_results: tuple[RuleResult, ...]

    @property
    def failed_rules(self) -> tuple[RuleResult, ...]:
        return tuple(rule for rule in self.rule_results if rule.failed)


def _round(value: float) -> float:
    return round(value, 3)


def _distance_nm(previous: TrackObservation, current: TrackObservation) -> float:
    previous_latitude = math.radians(previous.latitude or 0)
    current_latitude = math.radians(current.latitude or 0)
    latitude_delta = current_latitude - previous_latitude
    longitude_delta = math.radians((current.longitude or 0) - (previous.longitude or 0))
    haversine_value = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(previous_latitude)
        * math.cos(current_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return EARTH_RADIUS_NM * 2 * math.atan2(
        math.sqrt(haversine_value), math.sqrt(1 - haversine_value)
    )


def _turn_degrees(previous_track: float, current_track: float) -> float:
    return abs((current_track - previous_track + 180) % 360 - 180)


def _result(
    rule: KinematicRule,
    value: float,
    threshold: float,
    unit: str,
    observation_ids: tuple[UUID, UUID],
) -> RuleResult:
    failed = value > threshold
    comparison = "exceeds" if failed else "is within"
    return RuleResult(
        rule=rule,
        status=EvaluationStatus.FLAGGED if failed else EvaluationStatus.PASS,
        value=_round(value),
        threshold=_round(threshold),
        unit=unit,
        explanation=(
            f"Measured {rule.value.lower().replace('_', ' ')} {comparison} "
            f"the policy {threshold:g} {unit} limit."
        ),
        observation_ids=observation_ids,
    )


def evaluate_pair(
    previous: TrackObservation,
    current: TrackObservation,
    *,
    policy: KinematicPolicy | None = None,
) -> KinematicEvaluation:
    """Evaluate two same-source position reports without assigning intent."""
    selected_policy = policy or KinematicPolicy()
    identity = f"{previous.observation_id}:{current.observation_id}:{selected_policy.version}"
    evaluation_id = uuid5(EVALUATION_NAMESPACE, identity)
    delta_seconds = (current.observed_at - previous.observed_at).total_seconds()
    base = {
        "evaluation_id": evaluation_id,
        "policy_version": selected_policy.version,
        "previous_observation_id": previous.observation_id,
        "current_observation_id": current.observation_id,
        "source_type": current.provenance.source_type.value,
        "source_id": current.provenance.source_id,
        "icao_hex": current.icao_hex,
        "evaluated_at": current.received_at,
        "delta_seconds": _round(delta_seconds),
    }

    if previous.icao_hex != current.icao_hex or previous.provenance != current.provenance:
        return KinematicEvaluation(
            **base,
            status=EvaluationStatus.INSUFFICIENT_DATA,
            reason="Observations must have matching aircraft identity and provenance.",
            measurements={},
            rule_results=(),
        )
    if delta_seconds <= 0:
        return KinematicEvaluation(
            **base,
            status=EvaluationStatus.INSUFFICIENT_DATA,
            reason="Observation interval must be positive.",
            measurements={},
            rule_results=(),
        )
    if delta_seconds < selected_policy.minimum_interval_seconds:
        return KinematicEvaluation(
            **base,
            status=EvaluationStatus.INSUFFICIENT_DATA,
            reason=(
                "Observation interval is below the "
                f"{selected_policy.minimum_interval_seconds:g} second minimum."
            ),
            measurements={},
            rule_results=(),
        )
    if delta_seconds > selected_policy.maximum_interval_seconds:
        return KinematicEvaluation(
            **base,
            status=EvaluationStatus.INSUFFICIENT_DATA,
            reason=(
                "Observation interval exceeds the "
                f"{selected_policy.maximum_interval_seconds:g} second maximum."
            ),
            measurements={},
            rule_results=(),
        )
    if previous.latitude is None or current.latitude is None:
        return KinematicEvaluation(
            **base,
            status=EvaluationStatus.INSUFFICIENT_DATA,
            reason="Both observations require complete positions.",
            measurements={},
            rule_results=(),
        )

    observation_ids = (previous.observation_id, current.observation_id)
    distance_nm = _distance_nm(previous, current)
    implied_speed = distance_nm * 3600 / delta_seconds
    measurements = {
        "distance_nautical_miles": _round(distance_nm),
        "implied_ground_speed_knots": _round(implied_speed),
    }
    results = [
        _result(
            KinematicRule.IMPLIED_GROUND_SPEED,
            implied_speed,
            selected_policy.maximum_implied_speed_knots,
            "knots",
            observation_ids,
        )
    ]

    if previous.ground_speed_knots is not None and current.ground_speed_knots is not None:
        acceleration = abs(current.ground_speed_knots - previous.ground_speed_knots) / delta_seconds
        disagreement = abs(implied_speed - current.ground_speed_knots)
        disagreement_limit = max(
            selected_policy.minimum_speed_disagreement_knots,
            current.ground_speed_knots * selected_policy.speed_disagreement_fraction,
        )
        measurements["reported_acceleration_knots_per_second"] = _round(acceleration)
        measurements["speed_disagreement_knots"] = _round(disagreement)
        results.extend(
            [
                _result(
                    KinematicRule.REPORTED_ACCELERATION,
                    acceleration,
                    selected_policy.maximum_acceleration_knots_per_second,
                    "knots/second",
                    observation_ids,
                ),
                _result(
                    KinematicRule.SPEED_DISAGREEMENT,
                    disagreement,
                    disagreement_limit,
                    "knots",
                    observation_ids,
                ),
            ]
        )

    if (
        previous.track_degrees is not None
        and current.track_degrees is not None
        and max(previous.ground_speed_knots or 0, current.ground_speed_knots or 0)
        >= selected_policy.minimum_speed_for_turn_check_knots
    ):
        turn_rate = _turn_degrees(previous.track_degrees, current.track_degrees) / delta_seconds
        measurements["turn_rate_degrees_per_second"] = _round(turn_rate)
        results.append(
            _result(
                KinematicRule.TURN_RATE,
                turn_rate,
                selected_policy.maximum_turn_rate_degrees_per_second,
                "degrees/second",
                observation_ids,
            )
        )

    if previous.altitude_ft is not None and current.altitude_ft is not None:
        vertical_rate = abs(current.altitude_ft - previous.altitude_ft) * 60 / delta_seconds
        measurements["derived_vertical_rate_fpm"] = _round(vertical_rate)
        results.append(
            _result(
                KinematicRule.DERIVED_VERTICAL_RATE,
                vertical_rate,
                selected_policy.maximum_vertical_rate_fpm,
                "feet/minute",
                observation_ids,
            )
        )

    status = (
        EvaluationStatus.FLAGGED
        if any(result.failed for result in results)
        else EvaluationStatus.PASS
    )
    return KinematicEvaluation(
        **base,
        status=status,
        reason=None,
        measurements=measurements,
        rule_results=tuple(results),
    )
