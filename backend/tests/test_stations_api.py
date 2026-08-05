"""API contract tests for explainable edge-station fleet health."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from app.api.stations import router
from app.core.database import get_db


NOW = datetime.now(timezone.utc)
TELEMETRY_ID = UUID("00000000-0000-4000-8000-000000000010")
PRESENCE_ID = UUID("00000000-0000-4000-8000-000000000020")
BOOT_ID = UUID("00000000-0000-4000-8000-000000000001")


class FakeQuery:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def filter(self, *_args) -> "FakeQuery":
        return self

    def order_by(self, *_args) -> "FakeQuery":
        return self

    def limit(self, *_args) -> "FakeQuery":
        return self

    def all(self) -> list[object]:
        return self.records

    def first(self) -> object | None:
        return self.records[0] if self.records else None


class FakeSession:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def query(self, *_args) -> FakeQuery:
        return FakeQuery(self.records)


def station_record(**updates) -> SimpleNamespace:
    current_time = datetime.now(timezone.utc)
    values = {
        "node_id": "roof-node-1",
        "firmware_version": "1.0.0",
        "boot_id": BOOT_ID,
        "telemetry_message_id": TELEMETRY_ID,
        "presence_message_id": PRESENCE_ID,
        "last_sequence": 42,
        "first_seen_at": current_time,
        "last_received_at": current_time,
        "last_observed_at": current_time,
        "presence_status": "ONLINE",
        "presence_received_at": current_time,
        "uptime_seconds": 3_600,
        "reconnect_count": 1,
        "rssi_dbm": -60,
        "free_heap_bytes": 100_000,
        "offline_queue_depth": 0,
        "watchdog_reset_count": 0,
        "temperature_c": 24.5,
        "supply_voltage_v": 5.0,
    }
    values.update(updates)
    return SimpleNamespace(**values)


def telemetry_record() -> SimpleNamespace:
    return SimpleNamespace(
        message_id=TELEMETRY_ID,
        schema_version="1.0",
        node_id="roof-node-1",
        firmware_version="1.0.0",
        boot_id=BOOT_ID,
        sequence=42,
        observed_at=NOW,
        received_at=NOW,
        uptime_seconds=3_600,
        reconnect_count=1,
        rssi_dbm=-60,
        free_heap_bytes=100_000,
        offline_queue_depth=0,
        watchdog_reset_count=0,
        temperature_c=24.5,
        supply_voltage_v=5.0,
    )


def build_test_app(records: list[object]) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: FakeSession(records)
    return app


@pytest.mark.asyncio
async def test_lists_station_with_explainable_health():
    transport = httpx.ASGITransport(app=build_test_app([station_record()]))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stations/")

    assert response.status_code == 200
    body = response.json()[0]
    assert body["node_id"] == "roof-node-1"
    assert body["health"]["state"] == "HEALTHY"
    assert body["health"]["telemetry_message_id"] == str(TELEMETRY_ID)


@pytest.mark.asyncio
async def test_health_filter_excludes_other_states():
    transport = httpx.ASGITransport(app=build_test_app([station_record(rssi_dbm=-95)]))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stations/", params={"state": "HEALTHY"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_station_detail_reports_broker_last_will_offline():
    record = station_record(presence_status="OFFLINE")
    transport = httpx.ASGITransport(app=build_test_app([record]))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stations/roof-node-1")

    assert response.status_code == 200
    assert response.json()["health"]["state"] == "OFFLINE"
    assert "last-will" in response.json()["health"]["reasons"][0]


@pytest.mark.asyncio
async def test_missing_station_returns_404():
    transport = httpx.ASGITransport(app=build_test_app([]))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stations/missing")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lists_immutable_telemetry_events():
    transport = httpx.ASGITransport(app=build_test_app([telemetry_record()]))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/stations/roof-node-1/telemetry")

    assert response.status_code == 200
    assert response.json()[0]["message_id"] == str(TELEMETRY_ID)
    assert response.json()[0]["sequence"] == 42
