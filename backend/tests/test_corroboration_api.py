"""API contract tests for operator-visible cross-source evidence."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api import corroboration as corroboration_api
from app.core.database import get_db
from app.services.corroboration import CorroborationResult, CorroborationState
from app.services.external_observations import SourceHealth


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


class FakeQuery:
    def __init__(self, record: object | None) -> None:
        self.record = record

    def filter(self, *_args) -> "FakeQuery":
        return self

    def order_by(self, *_args) -> "FakeQuery":
        return self

    def first(self) -> object | None:
        return self.record


class FakeSession:
    def __init__(self, record: object | None) -> None:
        self.record = record

    def query(self, *_args) -> FakeQuery:
        return FakeQuery(self.record)


class FakeService:
    def __init__(self, result: CorroborationResult) -> None:
        self.result = result
        self.calls = 0
        self.source_health = SourceHealth(
            provider="test-provider",
            circuit_state="CLOSED",
            requests=1,
            successes=1,
            failures=0,
            cache_hits=0,
            rate_limit_events=0,
            consecutive_failures=0,
            last_success_at=NOW,
            last_error=None,
            retry_after=NOW,
            credits_remaining=399,
        )

    async def corroborate(self, _local) -> CorroborationResult:
        self.calls += 1
        return self.result


def observation_record() -> SimpleNamespace:
    return SimpleNamespace(
        schema_version="1.0",
        observation_id=uuid4(),
        source_type="RECORDED_REPLAY",
        source_id="checked-in-recording",
        receiver_id=None,
        recording_id="recording-1",
        provider=None,
        license_id=None,
        icao_hex="ABC123",
        observed_at=NOW,
        received_at=NOW,
        callsign="TEST123",
        latitude=40.5,
        longitude=-74.5,
        altitude_ft=10_000,
        ground_speed_knots=250.0,
        track_degrees=90.0,
        vertical_rate_fpm=0,
        squawk="1200",
        quality_flags=[],
        raw_message_id="recording:1",
    )


def result() -> CorroborationResult:
    return CorroborationResult(
        state=CorroborationState.CORROBORATED,
        policy_version="1.0",
        icao_hex="ABC123",
        evaluated_at=NOW,
        explanation="Fresh sources agree.",
        local_observation_id=str(uuid4()),
        external_observation_id=str(uuid4()),
        time_delta_seconds=2.0,
        position_distance_nm=0.5,
        altitude_difference_ft=100,
    )


def build_test_app(record: object | None, service: FakeService) -> FastAPI:
    app = FastAPI()
    app.include_router(corroboration_api.router)
    app.dependency_overrides[get_db] = lambda: FakeSession(record)
    app.dependency_overrides[corroboration_api.get_corroboration_service] = lambda: service
    return app


@pytest.mark.asyncio
async def test_returns_corroboration_evidence(monkeypatch) -> None:
    service = FakeService(result())
    monkeypatch.setattr(
        corroboration_api,
        "get_settings",
        lambda: SimpleNamespace(opensky_enabled=True),
    )
    transport = httpx.ASGITransport(app=build_test_app(observation_record(), service))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/corroboration/abc123")

    assert response.status_code == 200
    assert response.json()["state"] == "CORROBORATED"
    assert response.json()["position_distance_nm"] == 0.5
    assert service.calls == 1


@pytest.mark.asyncio
async def test_disabled_external_source_is_unavailable_not_suspicious(monkeypatch) -> None:
    service = FakeService(result())
    monkeypatch.setattr(
        corroboration_api,
        "get_settings",
        lambda: SimpleNamespace(opensky_enabled=False),
    )
    transport = httpx.ASGITransport(app=build_test_app(observation_record(), service))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/corroboration/ABC123")

    assert response.status_code == 200
    assert response.json()["state"] == "UNAVAILABLE"
    assert "unavailable" in response.json()["explanation"].lower()
    assert service.calls == 0


@pytest.mark.asyncio
async def test_requires_a_provenance_bearing_local_observation(monkeypatch) -> None:
    service = FakeService(result())
    monkeypatch.setattr(
        corroboration_api,
        "get_settings",
        lambda: SimpleNamespace(opensky_enabled=True),
    )
    transport = httpx.ASGITransport(app=build_test_app(None, service))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/corroboration/ABC123")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rejects_invalid_icao_address(monkeypatch) -> None:
    service = FakeService(result())
    monkeypatch.setattr(
        corroboration_api,
        "get_settings",
        lambda: SimpleNamespace(opensky_enabled=True),
    )
    transport = httpx.ASGITransport(app=build_test_app(observation_record(), service))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/corroboration/not-hex")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_exposes_source_health_without_credentials(monkeypatch) -> None:
    service = FakeService(result())
    monkeypatch.setattr(
        corroboration_api,
        "get_settings",
        lambda: SimpleNamespace(opensky_enabled=True),
    )
    transport = httpx.ASGITransport(app=build_test_app(observation_record(), service))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/corroboration/source-health")

    assert response.status_code == 200
    assert response.json()["provider"] == "test-provider"
    assert response.json()["credits_remaining"] == 399
    assert response.json()["enabled"] is True
