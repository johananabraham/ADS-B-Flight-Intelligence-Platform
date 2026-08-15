"""Backend proxy for the internal recorded-replay control service."""

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.audit import record_audit_event
from ..auth.dependencies import require_operator
from ..core.config import get_settings
from ..core.database import get_db
from ..models.user import User

router = APIRouter(prefix="/replay", tags=["replay"])
settings = get_settings()


class ReplayStatus(BaseModel):
    recording_id: str
    title: str
    state: Literal["PLAYING", "PAUSED", "COMPLETED"]
    speed: float
    position_ms: int
    duration_ms: int
    event_index: int
    event_count: int
    loop: bool


class ReplayCommand(BaseModel):
    action: Literal["pause", "resume", "restart", "seek", "speed"]
    value: float | None = None


async def request_replay(method: str, path: str, payload: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.request(
                method,
                f"{settings.replay_control_url.rstrip('/')}{path}",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as exc:
        try:
            error_body = exc.response.json()
        except ValueError:
            error_body = None
        detail = (
            error_body.get("detail", "replay command rejected")
            if isinstance(error_body, dict)
            else "replay command rejected"
        )
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="recorded replay controls are unavailable in the current source mode",
        ) from exc
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="invalid replay service response")
    return result


@router.get("/status", response_model=ReplayStatus)
async def replay_status() -> dict:
    """Return authoritative recorded-replay state."""
    return await request_replay("GET", "/status")


@router.post("/commands", response_model=ReplayStatus)
async def replay_command(
    command: ReplayCommand,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> dict:
    """Apply one validated playback command (requires operator or admin role)."""
    result = await request_replay("POST", "/commands", command.model_dump())
    record_audit_event(
        db,
        event_type="replay.command",
        success=True,
        actor_user_id=current_user.id,
        target_type="replay",
        target_id=command.action,
        details={"action": command.action},
    )
    db.commit()
    return result
