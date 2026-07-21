"""API contract tests for operator-visible kinematic evidence."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api.kinematics import router
from app.core.database import get_db


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


class FakeSession:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def query(self, *_args) -> FakeQuery:
        return FakeQuery(self.records)


def evaluation_record() -> SimpleNamespace:
    previous_id = uuid4()
    current_id = uuid4()
    return SimpleNamespace(
        evaluation_id=uuid4(),
        policy_version="1.0",
        previous_observation_id=previous_id,
        current_observation_id=current_id,
        source_type="RECORDED_REPLAY",
        source_id="checked-in-recording",
        icao_hex="A1B2C3",
        evaluated_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        status="FLAGGED",
        reason=None,
        delta_seconds=1,
        measurements={"implied_ground_speed_knots": 10_000.0},
        rule_results=[
            {
                "rule": "IMPLIED_GROUND_SPEED",
                "status": "FLAGGED",
                "value": 10_000.0,
                "threshold": 750.0,
                "unit": "knots",
                "explanation": "Measured speed exceeds policy limit.",
                "observation_ids": [str(previous_id), str(current_id)],
            }
        ],
    )


@pytest.mark.asyncio
async def test_lists_serialized_kinematic_evidence() -> None:
    app = FastAPI()
    app.include_router(router)
    record = evaluation_record()
    app.dependency_overrides[get_db] = lambda: FakeSession([record])
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/kinematics/evaluations",
            params={"icao_hex": "a1b2c3", "status": "FLAGGED"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["evaluation_id"] == str(record.evaluation_id)
    assert body[0]["rule_results"][0]["threshold"] == 750.0


@pytest.mark.asyncio
async def test_rejects_invalid_aircraft_identity_filter() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: FakeSession([])
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/kinematics/evaluations", params={"icao_hex": "invalid"}
        )

    assert response.status_code == 422
