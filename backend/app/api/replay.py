"""Backend proxy for the internal recorded-replay control service."""

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.config import get_settings
from ..models.user import User
from ..auth.dependencies import require_operator

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
    current_user: User = Depends(require_operator),
) -> dict:
    """Apply one validated playback command (requires operator or admin role)."""
    return await request_replay("POST", "/commands", command.model_dump())
