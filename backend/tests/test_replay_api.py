"""Tests for the backend's recorded-replay proxy boundary."""

import httpx
import pytest
from fastapi import HTTPException

from app.api import replay as replay_api


STATUS = {
    "recording_id": "columbus-generated-v1",
    "title": "Generated Columbus Two-Aircraft Fixture",
    "state": "PAUSED",
    "speed": 1.0,
    "position_ms": 1_000,
    "duration_ms": 2_000,
    "event_index": 2,
    "event_count": 6,
    "loop": True,
}


class FakeResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        self.request = httpx.Request("POST", "http://replay/commands")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request, json=self.body)
            raise httpx.HTTPStatusError("rejected", request=self.request, response=response)

    def json(self) -> dict:
        return self.body


class FakeClient:
    def __init__(self, response: FakeResponse | Exception, **_kwargs) -> None:
        self.response = response

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def request(self, *_args, **_kwargs) -> FakeResponse:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_proxies_replay_status(monkeypatch) -> None:
    monkeypatch.setattr(
        replay_api.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(FakeResponse(200, STATUS), **kwargs),
    )

    result = await replay_api.request_replay("GET", "/status")

    assert result == STATUS


@pytest.mark.asyncio
async def test_preserves_control_service_validation_error(monkeypatch) -> None:
    monkeypatch.setattr(
        replay_api.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(FakeResponse(422, {"detail": "unsupported replay speed"}), **kwargs),
    )

    with pytest.raises(HTTPException) as error:
        await replay_api.request_replay("POST", "/commands", {"action": "speed", "value": 3})

    assert error.value.status_code == 422
    assert error.value.detail == "unsupported replay speed"


@pytest.mark.asyncio
async def test_reports_unavailable_replay_service(monkeypatch) -> None:
    request = httpx.Request("GET", "http://replay/status")
    monkeypatch.setattr(
        replay_api.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(httpx.ConnectError("offline", request=request), **kwargs),
    )

    with pytest.raises(HTTPException) as error:
        await replay_api.request_replay("GET", "/status")

    assert error.value.status_code == 503
