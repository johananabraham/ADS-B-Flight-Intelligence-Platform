"""API contract tests for independently visible trust evidence."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from app.auth.dependencies import require_operator
from app.api.corroboration import get_corroboration_service
from app.api.trust import router
from app.core.database import get_db
from app.models.edge import SensorNodeRecord
from app.models.kinematics import KinematicEvaluationRecord, WindowKinematicEvaluationRecord
from app.models.observation import TrackObservationRecord


PAIR_ID = UUID("00000000-0000-4000-8000-000000000101")
WINDOW_ID = UUID("00000000-0000-4000-8000-000000000102")


class FakeQuery:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def filter(self, *_args) -> "FakeQuery":
        return self

    def order_by(self, *_args) -> "FakeQuery":
        return self

    def first(self) -> object | None:
        return self.records[0] if self.records else None


class FakeSession:
    def __init__(self, records: dict[type, list[object]]) -> None:
        self.records = records

    def query(self, model: type) -> FakeQuery:
        return FakeQuery(self.records.get(model, []))

    def execute(self, _statement):
        return SimpleNamespace(rowcount=1)

    def add(self, _record: object) -> None:
        return None

    def commit(self) -> None:
        return None


def evaluation(evaluation_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        evaluation_id=evaluation_id,
        policy_version="1.0",
        source_id="roof-node-1",
        evaluated_at=datetime.now(timezone.utc),
        status="PASS",
        reason=None,
    )


def station() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        node_id="roof-node-1",
        firmware_version="1.0.0",
        boot_id=UUID("00000000-0000-4000-8000-000000000103"),
        telemetry_message_id=UUID("00000000-0000-4000-8000-000000000104"),
        presence_message_id=UUID("00000000-0000-4000-8000-000000000105"),
        pipeline_message_id=None,
        last_sequence=7,
        last_observed_at=now,
        presence_status="ONLINE",
        presence_received_at=now,
        uptime_seconds=120,
        reconnect_count=0,
        rssi_dbm=-60,
        free_heap_bytes=100_000,
        offline_queue_depth=0,
        watchdog_reset_count=0,
        temperature_c=None,
        supply_voltage_v=None,
        pipeline_observed_at=None,
        pipeline_received_at=None,
        receiver_connection=None,
        receiver_policy_version=None,
        receiver_last_message_age_seconds=None,
        receiver_queue_depth=None,
        receiver_queue_capacity=None,
        receiver_dropped_messages_total=None,
        receiver_reconnects_total=None,
    )


def build_app() -> FastAPI:
    records = {
        KinematicEvaluationRecord: [evaluation(PAIR_ID)],
        WindowKinematicEvaluationRecord: [evaluation(WINDOW_ID)],
        TrackObservationRecord: [],
        SensorNodeRecord: [station()],
    }
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: FakeSession(records)
    app.dependency_overrides[get_corroboration_service] = lambda: None
    app.dependency_overrides[require_operator] = lambda: SimpleNamespace(
        id=7, username="local-operator", role="operator"
    )
    return app


@pytest.mark.asyncio
async def test_returns_each_component_without_a_magic_score():
    transport = httpx.ASGITransport(app=build_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/trust/abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "INSUFFICIENT_DATA"
    assert body["numeric_score"] is None
    assert [component["component"] for component in body["components"]] == [
        "PAIR_KINEMATICS",
        "WINDOW_KINEMATICS",
        "CORROBORATION",
        "STATION",
        "ML",
    ]
    assert body["components"][0]["evidence_ids"] == [str(PAIR_ID)]
    assert body["components"][2]["state"] == "NOT_EVALUATED"
    assert body["components"][3]["state"] == "HEALTHY"
    assert body["components"][4]["state"] == "NOT_PROMOTED"


@pytest.mark.asyncio
async def test_rejects_invalid_icao_address():
    transport = httpx.ASGITransport(app=build_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/trust/not-an-icao")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_persists_server_computed_assessment_with_evidence_id():
    transport = httpx.ASGITransport(app=build_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/trust/abc123/assessments")

    assert response.status_code == 200
    body = response.json()
    assert body["inserted"] is True
    assert UUID(body["assessment_id"])
    assert body["assessment"]["state"] == "INSUFFICIENT_DATA"
    assert body["assessment"]["numeric_score"] is None
