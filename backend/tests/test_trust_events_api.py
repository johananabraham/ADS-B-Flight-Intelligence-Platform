"""Operator workflow API tests for persisted trust events."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from app.api.trust_events import router
from app.core.database import get_db
from app.models.trust import TrustAssessmentRecord, TrustOperatorActionRecord


ASSESSMENT_ID = UUID("00000000-0000-4000-8000-000000000301")
ACTION_ID = UUID("00000000-0000-4000-8000-000000000302")
NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


class FakeQuery:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def filter(self, *_args) -> "FakeQuery":
        return self

    def order_by(self, *_args) -> "FakeQuery":
        return self

    def limit(self, *_args) -> "FakeQuery":
        return self

    def first(self):
        return self.records[0] if self.records else None

    def all(self):
        return self.records


class FakeSession:
    def __init__(self, actions: list[object] | None = None) -> None:
        self.records = {
            TrustAssessmentRecord: [assessment_record()],
            TrustOperatorActionRecord: actions or [],
        }
        self.committed = False

    def query(self, model: type) -> FakeQuery:
        return FakeQuery(self.records.get(model, []))

    def execute(self, _statement):
        return SimpleNamespace(rowcount=1)

    def commit(self) -> None:
        self.committed = True


def assessment_record() -> SimpleNamespace:
    return SimpleNamespace(
        assessment_id=ASSESSMENT_ID,
        policy_version="1.0-development",
        icao_hex="ABC123",
        evaluated_at=NOW,
        state="LOW_CONFIDENCE",
        reasons=["External source unavailable."],
        components=[{"component": "CORROBORATION", "state": "UNAVAILABLE"}],
    )


def action_record(note: str | None = "Reviewed.") -> SimpleNamespace:
    return SimpleNamespace(
        action_id=ACTION_ID,
        assessment_id=ASSESSMENT_ID,
        action_type="ANNOTATE" if note else "ACKNOWLEDGE",
        actor="local-operator",
        note=note,
        created_at=NOW,
    )


def build_app(session: FakeSession) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    return app


@pytest.mark.asyncio
async def test_filters_and_inspects_persisted_events_with_actions():
    transport = httpx.ASGITransport(app=build_app(FakeSession([action_record()])))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get("/trust-events/", params={"state": "LOW_CONFIDENCE"})
        detail = await client.get(f"/trust-events/{ASSESSMENT_ID}")

    assert listed.status_code == 200
    assert listed.json()[0]["assessment_id"] == str(ASSESSMENT_ID)
    assert detail.status_code == 200
    assert detail.json()["actions"][0]["identity_assurance"] == "SELF_ASSERTED"


@pytest.mark.asyncio
async def test_creates_server_timestamped_annotation_and_commits():
    session = FakeSession()
    transport = httpx.ASGITransport(app=build_app(session))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/trust-events/{ASSESSMENT_ID}/actions",
            json={
                "action_id": str(ACTION_ID),
                "action_type": "ANNOTATE",
                "actor": " local-operator ",
                "note": " Reviewed. ",
            },
        )

    assert response.status_code == 200
    assert response.json()["inserted"] is True
    assert response.json()["action"]["actor"] == "local-operator"
    assert session.committed is True


@pytest.mark.asyncio
async def test_retry_returns_existing_action_and_conflict_rejects_reuse():
    session = FakeSession([action_record()])
    transport = httpx.ASGITransport(app=build_app(session))
    matching = {
        "action_id": str(ACTION_ID),
        "action_type": "ANNOTATE",
        "actor": "local-operator",
        "note": "Reviewed.",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        retry = await client.post(f"/trust-events/{ASSESSMENT_ID}/actions", json=matching)
        conflict = await client.post(
            f"/trust-events/{ASSESSMENT_ID}/actions",
            json={**matching, "note": "Different review."},
        )

    assert retry.status_code == 200
    assert retry.json()["inserted"] is False
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_annotation_requires_note_and_export_warns_about_identity():
    transport = httpx.ASGITransport(app=build_app(FakeSession([action_record()])))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        invalid = await client.post(
            f"/trust-events/{ASSESSMENT_ID}/actions",
            json={
                "action_id": str(ACTION_ID),
                "action_type": "ANNOTATE",
                "actor": "operator",
            },
        )
        blank_actor = await client.post(
            f"/trust-events/{ASSESSMENT_ID}/actions",
            json={
                "action_id": str(ACTION_ID),
                "action_type": "ACKNOWLEDGE",
                "actor": "   ",
            },
        )
        exported = await client.get(f"/trust-events/{ASSESSMENT_ID}/export")

    assert invalid.status_code == 422
    assert blank_actor.status_code == 422
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].startswith("attachment;")
    assert exported.json()["identity_warning"].startswith("Operator labels")
