"""Cross-source aircraft observation association and corroboration states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import asin, cos, radians, sin, sqrt

from ..schemas.observation import TrackObservation


class CorroborationState(str, Enum):
    """Evidence state produced by comparing local and external observations."""

    CORROBORATED = "CORROBORATED"
    LOCAL_ONLY = "LOCAL_ONLY"
    EXTERNAL_ONLY = "EXTERNAL_ONLY"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class CorroborationPolicy:
    """Versioned tolerances for associating observations from two sources."""

    version: str = "1.0"
    max_age_seconds: float = 30.0
    max_future_skew_seconds: float = 2.0
    max_time_delta_seconds: float = 15.0
    max_position_distance_nm: float = 3.0
    max_altitude_difference_ft: int = 1_500

    def __post_init__(self) -> None:
        values = (
            self.max_age_seconds,
            self.max_future_skew_seconds,
            self.max_time_delta_seconds,
            self.max_position_distance_nm,
            self.max_altitude_difference_ft,
        )
        if any(value < 0 for value in values):
            raise ValueError("corroboration tolerances cannot be negative")


@dataclass(frozen=True)
class CorroborationResult:
    """Auditable result of one local/external observation comparison."""

    state: CorroborationState
    policy_version: str
    icao_hex: str
    evaluated_at: datetime
    explanation: str
    local_observation_id: str | None = None
    external_observation_id: str | None = None
    time_delta_seconds: float | None = None
    position_distance_nm: float | None = None
    altitude_difference_ft: int | None = None


def compare_observations(
    *,
    local: TrackObservation | None,
    external: TrackObservation | None,
    evaluated_at: datetime,
    source_available: bool,
    policy: CorroborationPolicy = CorroborationPolicy(),
) -> CorroborationResult:
    """Associate one local and external observation without inferring intent."""
    _require_aware(evaluated_at, "evaluated_at")
    icao_hex = _icao_hex(local, external)

    if not source_available:
        return _result(
            CorroborationState.UNAVAILABLE,
            policy,
            icao_hex,
            evaluated_at,
            "The external source is unavailable; local evidence is not classified as suspicious.",
            local,
            external,
        )
    if local is None:
        return _result(
            CorroborationState.EXTERNAL_ONLY,
            policy,
            icao_hex,
            evaluated_at,
            "The external source reported this ICAO address without a local observation.",
            local,
            external,
        )
    if external is None:
        return _result(
            CorroborationState.LOCAL_ONLY,
            policy,
            icao_hex,
            evaluated_at,
            "The local source reported this ICAO address without a fresh external match.",
            local,
            external,
        )
    if local.icao_hex != external.icao_hex:
        raise ValueError("observations must have the same ICAO address")

    local_age = (evaluated_at - local.observed_at).total_seconds()
    external_age = (evaluated_at - external.observed_at).total_seconds()
    time_delta = abs((local.observed_at - external.observed_at).total_seconds())
    if (
        local_age > policy.max_age_seconds
        or external_age > policy.max_age_seconds
        or local_age < -policy.max_future_skew_seconds
        or external_age < -policy.max_future_skew_seconds
        or time_delta > policy.max_time_delta_seconds
    ):
        return _result(
            CorroborationState.STALE,
            policy,
            icao_hex,
            evaluated_at,
            "One or both observations fall outside the freshness or association-time tolerance.",
            local,
            external,
            time_delta=time_delta,
        )

    position_distance = _position_distance_nm(local, external)
    altitude_difference = _altitude_difference_ft(local, external)
    position_conflict = (
        position_distance is not None
        and position_distance > policy.max_position_distance_nm
    )
    altitude_conflict = (
        altitude_difference is not None
        and altitude_difference > policy.max_altitude_difference_ft
    )
    if position_conflict or altitude_conflict:
        return _result(
            CorroborationState.CONFLICTING,
            policy,
            icao_hex,
            evaluated_at,
            "The associated observations disagree beyond a configured position or altitude tolerance.",
            local,
            external,
            time_delta=time_delta,
            position_distance=position_distance,
            altitude_difference=altitude_difference,
        )

    if position_distance is None and altitude_difference is None:
        return _result(
            CorroborationState.STALE,
            policy,
            icao_hex,
            evaluated_at,
            "The observations share an ICAO address but lack position and altitude evidence to compare.",
            local,
            external,
            time_delta=time_delta,
        )

    return _result(
        CorroborationState.CORROBORATED,
        policy,
        icao_hex,
        evaluated_at,
        "A fresh external observation agrees with the local position or altitude evidence.",
        local,
        external,
        time_delta=time_delta,
        position_distance=position_distance,
        altitude_difference=altitude_difference,
    )


def _result(
    state: CorroborationState,
    policy: CorroborationPolicy,
    icao_hex: str,
    evaluated_at: datetime,
    explanation: str,
    local: TrackObservation | None,
    external: TrackObservation | None,
    *,
    time_delta: float | None = None,
    position_distance: float | None = None,
    altitude_difference: int | None = None,
) -> CorroborationResult:
    return CorroborationResult(
        state=state,
        policy_version=policy.version,
        icao_hex=icao_hex,
        evaluated_at=evaluated_at,
        explanation=explanation,
        local_observation_id=str(local.observation_id) if local else None,
        external_observation_id=str(external.observation_id) if external else None,
        time_delta_seconds=time_delta,
        position_distance_nm=position_distance,
        altitude_difference_ft=altitude_difference,
    )


def _icao_hex(local: TrackObservation | None, external: TrackObservation | None) -> str:
    observation = local or external
    if observation is None:
        raise ValueError("at least one observation is required")
    return observation.icao_hex


def _position_distance_nm(
    local: TrackObservation, external: TrackObservation
) -> float | None:
    if local.latitude is None or external.latitude is None:
        return None
    earth_radius_nm = 3_440.065
    lat1, lat2 = radians(local.latitude), radians(external.latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(external.longitude - local.longitude)  # type: ignore[operator]
    haversine = (
        sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_nm * asin(sqrt(min(1.0, max(0.0, haversine))))


def _altitude_difference_ft(
    local: TrackObservation, external: TrackObservation
) -> int | None:
    if local.altitude_ft is None or external.altitude_ft is None:
        return None
    return abs(local.altitude_ft - external.altitude_ft)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
