"""Read-only API for external cross-source corroboration evidence."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..models.observation import TrackObservationRecord
from ..services.corroboration import compare_observations
from ..services.corroboration_service import CorroborationService
from ..services.external_observations import OpenSkyConfig, OpenSkyObservationSource
from ..services.kinematic_persistence import record_to_observation


router = APIRouter(prefix="/corroboration", tags=["corroboration"])


class CorroborationResponse(BaseModel):
    state: Literal[
        "CORROBORATED",
        "LOCAL_ONLY",
        "EXTERNAL_ONLY",
        "CONFLICTING",
        "STALE",
        "UNAVAILABLE",
    ]
    policy_version: str
    icao_hex: str
    evaluated_at: datetime
    explanation: str
    local_observation_id: str | None
    external_observation_id: str | None
    time_delta_seconds: float | None
    position_distance_nm: float | None
    altitude_difference_ft: int | None


class SourceHealthResponse(BaseModel):
    provider: str
    enabled: bool
    circuit_state: str
    requests: int
    successes: int
    failures: int
    cache_hits: int
    rate_limit_events: int
    consecutive_failures: int
    last_success_at: datetime | None
    last_error: str | None
    retry_after: datetime | None
    credits_remaining: int | None


@lru_cache
def get_corroboration_service() -> CorroborationService:
    settings = get_settings()
    source = OpenSkyObservationSource(
        OpenSkyConfig(
            api_base_url=settings.opensky_api_base_url,
            auth_url=settings.opensky_auth_url,
            client_id=settings.opensky_client_id,
            client_secret=settings.opensky_client_secret,
        )
    )
    return CorroborationService(source)


@router.get("/source-health", response_model=SourceHealthResponse)
def get_source_health(
    service: CorroborationService = Depends(get_corroboration_service),
) -> SourceHealthResponse:
    health = asdict(service.source_health)
    health["enabled"] = get_settings().opensky_enabled
    return SourceHealthResponse(**health)


@router.get("/{icao_hex}", response_model=CorroborationResponse)
async def get_corroboration(
    icao_hex: str,
    db: Session = Depends(get_db),
    service: CorroborationService = Depends(get_corroboration_service),
) -> CorroborationResponse:
    normalized = icao_hex.strip().upper()
    if len(normalized) != 6 or any(
        character not in "0123456789ABCDEF" for character in normalized
    ):
        raise HTTPException(status_code=422, detail="ICAO address must be six hexadecimal characters")
    record = (
        db.query(TrackObservationRecord)
        .filter(
            TrackObservationRecord.icao_hex == normalized,
            TrackObservationRecord.source_type != "EXTERNAL_FEED",
        )
        .order_by(TrackObservationRecord.observed_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail="No provenance-bearing local observation exists for this aircraft",
        )
    if not get_settings().opensky_enabled:
        local = record_to_observation(record)
        result = compare_observations(
            local=local,
            external=None,
            evaluated_at=datetime.now(timezone.utc),
            source_available=False,
        )
    else:
        result = await service.corroborate(record_to_observation(record))
    return CorroborationResponse(**asdict(result))
