"""Idempotent persistence for edge-station telemetry and presence events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models.edge import (
    SensorNodeRecord,
    StationPresenceRecord,
    StationTelemetryRecord,
)
from ..schemas.edge import StationPresence, StationTelemetry


def telemetry_values(
    telemetry: StationTelemetry, received_at: datetime
) -> dict[str, object]:
    _require_aware(received_at)
    return {
        **telemetry.model_dump(),
        "received_at": received_at,
    }


def presence_values(
    presence: StationPresence, received_at: datetime
) -> dict[str, object]:
    _require_aware(received_at)
    values = presence.model_dump()
    values["status"] = presence.status.value
    values["received_at"] = received_at
    return values


def build_telemetry_event_insert(telemetry: StationTelemetry, received_at: datetime):
    return (
        insert(StationTelemetryRecord)
        .values(**telemetry_values(telemetry, received_at))
        .on_conflict_do_nothing()
    )


def build_presence_event_insert(presence: StationPresence, received_at: datetime):
    return (
        insert(StationPresenceRecord)
        .values(**presence_values(presence, received_at))
        .on_conflict_do_nothing()
    )


def build_telemetry_node_upsert(telemetry: StationTelemetry, received_at: datetime):
    statement = insert(SensorNodeRecord).values(
        node_id=telemetry.node_id,
        firmware_version=telemetry.firmware_version,
        boot_id=telemetry.boot_id,
        last_sequence=telemetry.sequence,
        first_seen_at=received_at,
        last_received_at=received_at,
        last_observed_at=telemetry.observed_at,
        uptime_seconds=telemetry.uptime_seconds,
        reconnect_count=telemetry.reconnect_count,
        rssi_dbm=telemetry.rssi_dbm,
        free_heap_bytes=telemetry.free_heap_bytes,
        offline_queue_depth=telemetry.offline_queue_depth,
        watchdog_reset_count=telemetry.watchdog_reset_count,
        temperature_c=telemetry.temperature_c,
        supply_voltage_v=telemetry.supply_voltage_v,
    )
    excluded = statement.excluded
    return statement.on_conflict_do_update(
        index_elements=["node_id"],
        set_={
            "firmware_version": excluded.firmware_version,
            "boot_id": excluded.boot_id,
            "last_sequence": excluded.last_sequence,
            "last_received_at": excluded.last_received_at,
            "last_observed_at": excluded.last_observed_at,
            "uptime_seconds": excluded.uptime_seconds,
            "reconnect_count": excluded.reconnect_count,
            "rssi_dbm": excluded.rssi_dbm,
            "free_heap_bytes": excluded.free_heap_bytes,
            "offline_queue_depth": excluded.offline_queue_depth,
            "watchdog_reset_count": excluded.watchdog_reset_count,
            "temperature_c": excluded.temperature_c,
            "supply_voltage_v": excluded.supply_voltage_v,
        },
        where=excluded.last_received_at > SensorNodeRecord.last_received_at,
    )


def build_presence_node_upsert(presence: StationPresence, received_at: datetime):
    statement = insert(SensorNodeRecord).values(
        node_id=presence.node_id,
        first_seen_at=received_at,
        last_received_at=received_at,
        presence_status=presence.status.value,
        presence_received_at=received_at,
    )
    excluded = statement.excluded
    return statement.on_conflict_do_update(
        index_elements=["node_id"],
        set_={
            "last_received_at": excluded.last_received_at,
            "presence_status": excluded.presence_status,
            "presence_received_at": excluded.presence_received_at,
        },
        where=or_(
            SensorNodeRecord.presence_received_at.is_(None),
            excluded.presence_received_at > SensorNodeRecord.presence_received_at,
        ),
    )


def persist_telemetry(
    db: Session, telemetry: StationTelemetry, received_at: datetime
) -> bool:
    db.execute(build_telemetry_node_upsert(telemetry, received_at))
    result = db.execute(build_telemetry_event_insert(telemetry, received_at))
    return result.rowcount == 1


def persist_presence(
    db: Session, presence: StationPresence, received_at: datetime
) -> bool:
    db.execute(build_presence_node_upsert(presence, received_at))
    result = db.execute(build_presence_event_insert(presence, received_at))
    return result.rowcount == 1


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("received_at must include a timezone")
