"""Explainable station-health evaluation independent of aircraft evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..schemas.edge import (
    PresenceStatus,
    ReceiverConnection,
    ReceiverPipelineTelemetry,
    StationPresence,
    StationTelemetry,
)


class StationHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    NO_DATA = "NO_DATA"


@dataclass(frozen=True)
class StationHealthPolicy:
    version: str = "1.1"
    stale_after_seconds: float = 45.0
    weak_rssi_dbm: int = -80
    minimum_free_heap_bytes: int = 50_000
    pipeline_stale_after_seconds: float = 45.0
    receiver_silence_after_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        if not -127 <= self.weak_rssi_dbm <= 0:
            raise ValueError("weak_rssi_dbm must be between -127 and 0")
        if self.minimum_free_heap_bytes < 0:
            raise ValueError("minimum_free_heap_bytes cannot be negative")
        if self.pipeline_stale_after_seconds <= 0:
            raise ValueError("pipeline_stale_after_seconds must be positive")
        if self.receiver_silence_after_seconds <= 0:
            raise ValueError("receiver_silence_after_seconds must be positive")


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
    pipeline_message_id: str | None = None
    pipeline_age_seconds: float | None = None


def evaluate_station_health(
    *,
    telemetry: StationTelemetry | None,
    presence: StationPresence | None,
    evaluated_at: datetime,
    pipeline: ReceiverPipelineTelemetry | None = None,
    policy: StationHealthPolicy = StationHealthPolicy(),
) -> StationHealthResult:
    _require_aware(evaluated_at)
    node_id = _node_id(telemetry, presence, pipeline)
    if telemetry is None and presence is None:
        reason = (
            "Receiver pipeline is known but no station telemetry or presence message "
            "has been received."
            if pipeline
            else "No station telemetry or presence message has been received."
        )
        return _result(
            StationHealthState.NO_DATA,
            policy,
            node_id,
            evaluated_at,
            None,
            (reason,),
            telemetry,
            presence,
            pipeline,
        )
    if telemetry and presence and telemetry.node_id != presence.node_id:
        raise ValueError("telemetry and presence must belong to the same node")
    if pipeline and telemetry and pipeline.node_id != telemetry.node_id:
        raise ValueError("pipeline and telemetry must belong to the same node")
    if pipeline and presence and pipeline.node_id != presence.node_id:
        raise ValueError("pipeline and presence must belong to the same node")

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
            pipeline,
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
            pipeline,
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
            pipeline,
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
            pipeline,
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
    pipeline_age = _pipeline_age_seconds(pipeline, evaluated_at)
    if pipeline is not None:
        if pipeline_age is not None and (
            pipeline_age < -2 or pipeline_age > policy.pipeline_stale_after_seconds
        ):
            reasons.append("Receiver-pipeline telemetry exceeded the freshness limit.")
        elif pipeline.connection is not ReceiverConnection.CONNECTED:
            reasons.append(
                f"Receiver pipeline reports {pipeline.connection.value}."
            )
        if pipeline.queue_depth >= pipeline.queue_capacity:
            reasons.append("Receiver processing queue is at capacity.")
        if (
            pipeline.last_message_age_seconds is not None
            and pipeline.last_message_age_seconds > policy.receiver_silence_after_seconds
        ):
            reasons.append("Receiver source has not produced a message within the policy limit.")
    state = StationHealthState.DEGRADED if reasons else StationHealthState.HEALTHY
    if not reasons:
        reasons.append("The latest heartbeat is fresh and all reported limits pass.")
    return _result(
        state,
        policy,
        node_id,
        evaluated_at,
        age,
        tuple(reasons),
        telemetry,
        presence,
        pipeline,
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
    pipeline: ReceiverPipelineTelemetry | None,
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
        pipeline_message_id=str(pipeline.message_id) if pipeline else None,
        pipeline_age_seconds=_pipeline_age_seconds(pipeline, evaluated_at),
    )


def _node_id(
    telemetry: StationTelemetry | None,
    presence: StationPresence | None,
    pipeline: ReceiverPipelineTelemetry | None,
) -> str | None:
    if telemetry:
        return telemetry.node_id
    if presence:
        return presence.node_id
    return pipeline.node_id if pipeline else None


def _age_seconds(telemetry: StationTelemetry | None, now: datetime) -> float | None:
    return (now - telemetry.observed_at).total_seconds() if telemetry else None


def _pipeline_age_seconds(
    pipeline: ReceiverPipelineTelemetry | None, now: datetime
) -> float | None:
    return (now - pipeline.observed_at).total_seconds() if pipeline else None


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluated_at must include a timezone")
