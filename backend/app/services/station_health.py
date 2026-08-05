"""Explainable station-health evaluation independent of aircraft evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..schemas.edge import PresenceStatus, StationPresence, StationTelemetry


class StationHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    NO_DATA = "NO_DATA"


@dataclass(frozen=True)
class StationHealthPolicy:
    version: str = "1.0"
    stale_after_seconds: float = 45.0
    weak_rssi_dbm: int = -80
    minimum_free_heap_bytes: int = 50_000

    def __post_init__(self) -> None:
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        if not -127 <= self.weak_rssi_dbm <= 0:
            raise ValueError("weak_rssi_dbm must be between -127 and 0")
        if self.minimum_free_heap_bytes < 0:
            raise ValueError("minimum_free_heap_bytes cannot be negative")


@dataclass(frozen=True)
class StationHealthResult:
    state: StationHealthState
    policy_version: str
    node_id: str | None
    evaluated_at: datetime
    telemetry_age_seconds: float | None
    reasons: tuple[str, ...]
    telemetry_message_id: str | None = None
    presence_message_id: str | None = None


def evaluate_station_health(
    *,
    telemetry: StationTelemetry | None,
    presence: StationPresence | None,
    evaluated_at: datetime,
    policy: StationHealthPolicy = StationHealthPolicy(),
) -> StationHealthResult:
    _require_aware(evaluated_at)
    node_id = _node_id(telemetry, presence)
    if telemetry is None and presence is None:
        return _result(
            StationHealthState.NO_DATA,
            policy,
            None,
            evaluated_at,
            None,
            ("No station telemetry or presence message has been received.",),
            telemetry,
            presence,
        )
    if telemetry and presence and telemetry.node_id != presence.node_id:
        raise ValueError("telemetry and presence must belong to the same node")

    if (
        presence
        and presence.status is PresenceStatus.OFFLINE
        and (telemetry is None or presence.observed_at >= telemetry.observed_at)
    ):
        return _result(
            StationHealthState.OFFLINE,
            policy,
            node_id,
            evaluated_at,
            _age_seconds(telemetry, evaluated_at),
            (f"Broker presence reports OFFLINE: {presence.reason}.",),
            telemetry,
            presence,
        )
    if telemetry is None:
        return _result(
            StationHealthState.NO_DATA,
            policy,
            node_id,
            evaluated_at,
            None,
            ("Presence is known but no telemetry heartbeat is available.",),
            telemetry,
            presence,
        )

    age = _age_seconds(telemetry, evaluated_at)
    if age < -2:
        return _result(
            StationHealthState.STALE,
            policy,
            node_id,
            evaluated_at,
            age,
            ("Telemetry timestamp is ahead of the evaluator clock.",),
            telemetry,
            presence,
        )
    if age > policy.stale_after_seconds:
        return _result(
            StationHealthState.STALE,
            policy,
            node_id,
            evaluated_at,
            age,
            ("The latest telemetry heartbeat exceeded the freshness limit.",),
            telemetry,
            presence,
        )

    reasons = []
    if telemetry.rssi_dbm <= policy.weak_rssi_dbm:
        reasons.append(f"Wi-Fi RSSI is weak at {telemetry.rssi_dbm} dBm.")
    if telemetry.free_heap_bytes < policy.minimum_free_heap_bytes:
        reasons.append(f"Free heap is low at {telemetry.free_heap_bytes} bytes.")
    if telemetry.offline_queue_depth > 0:
        reasons.append(
            f"The bounded offline queue contains {telemetry.offline_queue_depth} message(s)."
        )
    if telemetry.watchdog_reset_count > 0:
        reasons.append(
            f"The node reports {telemetry.watchdog_reset_count} watchdog reset(s)."
        )
    state = StationHealthState.DEGRADED if reasons else StationHealthState.HEALTHY
    if not reasons:
        reasons.append("The latest heartbeat is fresh and all reported limits pass.")
    return _result(
        state, policy, node_id, evaluated_at, age, tuple(reasons), telemetry, presence
    )


def _result(
    state: StationHealthState,
    policy: StationHealthPolicy,
    node_id: str | None,
    evaluated_at: datetime,
    age: float | None,
    reasons: tuple[str, ...],
    telemetry: StationTelemetry | None,
    presence: StationPresence | None,
) -> StationHealthResult:
    return StationHealthResult(
        state=state,
        policy_version=policy.version,
        node_id=node_id,
        evaluated_at=evaluated_at,
        telemetry_age_seconds=age,
        reasons=reasons,
        telemetry_message_id=str(telemetry.message_id) if telemetry else None,
        presence_message_id=str(presence.message_id) if presence else None,
    )


def _node_id(
    telemetry: StationTelemetry | None, presence: StationPresence | None
) -> str | None:
    return telemetry.node_id if telemetry else presence.node_id if presence else None


def _age_seconds(telemetry: StationTelemetry | None, now: datetime) -> float | None:
    return (now - telemetry.observed_at).total_seconds() if telemetry else None


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluated_at must include a timezone")
