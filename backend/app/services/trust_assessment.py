"""Explainable composition of independent aircraft-integrity evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .corroboration import CorroborationState
from .kinematics import EvaluationStatus
from .station_health import StationHealthState


class TrustState(str, Enum):
    TRUSTED = "TRUSTED"
    QUESTIONABLE = "QUESTIONABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class TrustAssessmentPolicy:
    version: str = "1.0-development"


@dataclass(frozen=True)
class TrustAssessmentInputs:
    icao_hex: str
    evaluated_at: datetime
    pair_status: EvaluationStatus | None
    window_status: EvaluationStatus | None
    corroboration_state: CorroborationState | None
    station_state: StationHealthState | None
    pair_evaluation_id: str | None = None
    window_evaluation_id: str | None = None
    local_observation_id: str | None = None
    external_observation_id: str | None = None
    station_node_id: str | None = None
    ml_probability: float | None = None
    ml_model_version: str | None = None


@dataclass(frozen=True)
class TrustAssessmentResult:
    state: TrustState
    policy_version: str
    icao_hex: str
    evaluated_at: datetime
    reasons: tuple[str, ...]
    inputs: TrustAssessmentInputs


def assess_trust(
    inputs: TrustAssessmentInputs,
    *,
    policy: TrustAssessmentPolicy = TrustAssessmentPolicy(),
) -> TrustAssessmentResult:
    """Combine evidence states without converting them into an uncalibrated score."""
    _validate(inputs)

    contradiction_reasons = _contradiction_reasons(inputs)
    if contradiction_reasons:
        return _result(TrustState.QUESTIONABLE, contradiction_reasons, inputs, policy)

    missing_reasons = _missing_reasons(inputs)
    if missing_reasons:
        return _result(TrustState.INSUFFICIENT_DATA, missing_reasons, inputs, policy)

    confidence_reasons = _confidence_reasons(inputs)
    if confidence_reasons:
        return _result(TrustState.LOW_CONFIDENCE, confidence_reasons, inputs, policy)

    return _result(
        TrustState.TRUSTED,
        (
            "Pair and window kinematic checks pass.",
            "A fresh external observation corroborates the local observation.",
            "The reporting station is healthy.",
        ),
        inputs,
        policy,
    )


def _contradiction_reasons(inputs: TrustAssessmentInputs) -> tuple[str, ...]:
    reasons = []
    if inputs.pair_status is EvaluationStatus.FLAGGED:
        reasons.append("The latest pairwise kinematic evaluation is flagged.")
    if inputs.window_status is EvaluationStatus.FLAGGED:
        reasons.append("The latest windowed kinematic evaluation is flagged.")
    if inputs.corroboration_state is CorroborationState.CONFLICTING:
        reasons.append("Fresh local and external observations conflict beyond policy limits.")
    return tuple(reasons)


def _missing_reasons(inputs: TrustAssessmentInputs) -> tuple[str, ...]:
    reasons = []
    if inputs.pair_status in {None, EvaluationStatus.INSUFFICIENT_DATA}:
        reasons.append("A conclusive pairwise kinematic evaluation is unavailable.")
    if inputs.window_status in {None, EvaluationStatus.INSUFFICIENT_DATA}:
        reasons.append("A conclusive windowed kinematic evaluation is unavailable.")
    if inputs.corroboration_state is None:
        reasons.append("Cross-source corroboration has not been evaluated.")
    if inputs.station_state is None:
        reasons.append("The reporting station cannot be associated with health evidence.")
    return tuple(reasons)


def _confidence_reasons(inputs: TrustAssessmentInputs) -> tuple[str, ...]:
    reasons = []
    if inputs.corroboration_state in {
        CorroborationState.LOCAL_ONLY,
        CorroborationState.EXTERNAL_ONLY,
        CorroborationState.STALE,
        CorroborationState.UNAVAILABLE,
    }:
        reasons.append(
            f"Cross-source corroboration is {inputs.corroboration_state.value}; "
            "this is an evidence limitation, not proof of suspicious activity."
        )
    if inputs.station_state is not StationHealthState.HEALTHY:
        reasons.append(
            f"The reporting station state is {inputs.station_state.value}; "
            "station health does not measure ADS-B RF quality."
        )
    return tuple(reasons)


def _validate(inputs: TrustAssessmentInputs) -> None:
    if len(inputs.icao_hex) != 6 or any(
        character not in "0123456789ABCDEF" for character in inputs.icao_hex.upper()
    ):
        raise ValueError("icao_hex must contain six hexadecimal characters")
    if inputs.evaluated_at.tzinfo is None or inputs.evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must include a timezone")
    if (inputs.ml_probability is None) != (inputs.ml_model_version is None):
        raise ValueError("ML probability and model version must be provided together")
    if inputs.ml_probability is not None and not 0 <= inputs.ml_probability <= 1:
        raise ValueError("ml_probability must be between zero and one")


def _result(
    state: TrustState,
    reasons: tuple[str, ...],
    inputs: TrustAssessmentInputs,
    policy: TrustAssessmentPolicy,
) -> TrustAssessmentResult:
    return TrustAssessmentResult(
        state=state,
        policy_version=policy.version,
        icao_hex=inputs.icao_hex.upper(),
        evaluated_at=inputs.evaluated_at,
        reasons=reasons,
        inputs=inputs,
    )
