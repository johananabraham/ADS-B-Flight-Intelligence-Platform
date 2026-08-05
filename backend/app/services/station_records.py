"""Restore station contracts and health evidence from current-state records."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.edge import SensorNodeRecord
from ..schemas.edge import PresenceStatus, StationPresence, StationTelemetry
from .station_health import StationHealthResult, evaluate_station_health


def record_to_telemetry(record: SensorNodeRecord) -> StationTelemetry | None:
    required = (
        record.firmware_version,
        record.boot_id,
        record.telemetry_message_id,
        record.last_sequence,
        record.last_observed_at,
        record.uptime_seconds,
        record.reconnect_count,
        record.rssi_dbm,
        record.free_heap_bytes,
        record.offline_queue_depth,
        record.watchdog_reset_count,
    )
    if any(value is None for value in required):
        return None
    return StationTelemetry(
        message_id=record.telemetry_message_id,
        node_id=record.node_id,
        firmware_version=record.firmware_version,
        boot_id=record.boot_id,
        sequence=record.last_sequence,
        observed_at=_as_utc(record.last_observed_at),
        uptime_seconds=record.uptime_seconds,
        reconnect_count=record.reconnect_count,
        rssi_dbm=record.rssi_dbm,
        free_heap_bytes=record.free_heap_bytes,
        offline_queue_depth=record.offline_queue_depth,
        watchdog_reset_count=record.watchdog_reset_count,
        temperature_c=record.temperature_c,
        supply_voltage_v=record.supply_voltage_v,
    )


def record_to_presence(record: SensorNodeRecord) -> StationPresence | None:
    if (
        record.presence_status is None
        or record.presence_received_at is None
        or record.presence_message_id is None
    ):
        return None
    status = PresenceStatus(record.presence_status)
    return StationPresence(
        message_id=record.presence_message_id,
        node_id=record.node_id,
        status=status,
        observed_at=_as_utc(record.presence_received_at),
        reason="mqtt-last-will" if status is PresenceStatus.OFFLINE else "connected",
    )


def evaluate_station_record(
    record: SensorNodeRecord, *, evaluated_at: datetime
) -> StationHealthResult:
    return evaluate_station_health(
        telemetry=record_to_telemetry(record),
        presence=record_to_presence(record),
        evaluated_at=evaluated_at,
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
