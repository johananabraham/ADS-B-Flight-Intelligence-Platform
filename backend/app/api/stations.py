"""Read-only fleet-health API for edge monitoring stations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.edge import SensorNodeRecord, StationTelemetryRecord
from ..services.station_records import evaluate_station_record


router = APIRouter(prefix="/stations", tags=["stations"])


class StationHealthResponse(BaseModel):
    state: Literal["HEALTHY", "DEGRADED", "STALE", "OFFLINE", "NO_DATA"]
    policy_version: str
    node_id: str | None
    evaluated_at: datetime
    telemetry_age_seconds: float | None
    reasons: tuple[str, ...]
    telemetry_message_id: str | None
    presence_message_id: str | None


class StationResponse(BaseModel):
    node_id: str
    firmware_version: str | None
    last_received_at: datetime
    last_observed_at: datetime | None
    presence_status: str | None
    uptime_seconds: int | None
    reconnect_count: int | None
    rssi_dbm: int | None
    free_heap_bytes: int | None
    offline_queue_depth: int | None
    watchdog_reset_count: int | None
    temperature_c: float | None
    supply_voltage_v: float | None
    health: StationHealthResponse


class StationTelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: UUID
    schema_version: str
    node_id: str
    firmware_version: str
    boot_id: UUID
    sequence: int
    observed_at: datetime
    received_at: datetime
    uptime_seconds: int
    reconnect_count: int
    rssi_dbm: int
    free_heap_bytes: int
    offline_queue_depth: int
    watchdog_reset_count: int
    temperature_c: float | None
    supply_voltage_v: float | None


HealthFilter = Literal["HEALTHY", "DEGRADED", "STALE", "OFFLINE", "NO_DATA"]


@router.get("/", response_model=list[StationResponse])
def get_stations(
    state: HealthFilter | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[StationResponse]:
    records = (
        db.query(SensorNodeRecord)
        .order_by(SensorNodeRecord.last_received_at.desc())
        .limit(limit)
        .all()
    )
    now = datetime.now(timezone.utc)
    responses = [_station_response(record, now) for record in records]
    return [
        response
        for response in responses
        if state is None or response.health.state == state
    ]


@router.get("/{node_id}", response_model=StationResponse)
def get_station(node_id: str, db: Session = Depends(get_db)) -> StationResponse:
    record = (
        db.query(SensorNodeRecord).filter(SensorNodeRecord.node_id == node_id).first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Station not found")
    return _station_response(record, datetime.now(timezone.utc))


@router.get("/{node_id}/telemetry", response_model=list[StationTelemetryResponse])
def get_station_telemetry(
    node_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1_000),
    db: Session = Depends(get_db),
) -> list[StationTelemetryRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(StationTelemetryRecord)
        .filter(
            StationTelemetryRecord.node_id == node_id,
            StationTelemetryRecord.received_at >= cutoff,
        )
        .order_by(StationTelemetryRecord.received_at.desc())
        .limit(limit)
        .all()
    )


def _station_response(record: SensorNodeRecord, now: datetime) -> StationResponse:
    health = evaluate_station_record(record, evaluated_at=now)
    return StationResponse(
        node_id=record.node_id,
        firmware_version=record.firmware_version,
        last_received_at=record.last_received_at,
        last_observed_at=record.last_observed_at,
        presence_status=record.presence_status,
        uptime_seconds=record.uptime_seconds,
        reconnect_count=record.reconnect_count,
        rssi_dbm=record.rssi_dbm,
        free_heap_bytes=record.free_heap_bytes,
        offline_queue_depth=record.offline_queue_depth,
        watchdog_reset_count=record.watchdog_reset_count,
        temperature_c=record.temperature_c,
        supply_voltage_v=record.supply_voltage_v,
        health=StationHealthResponse(**asdict(health)),
    )
