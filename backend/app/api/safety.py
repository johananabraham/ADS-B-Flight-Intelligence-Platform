"""Safety research API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Optional

from ..safety import (
    run_agent,
    tool_get_aircraft_safety_context,
    tool_query_incident_database,
    get_ingestion_status,
)

router = APIRouter(prefix="/safety", tags=["safety"])


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    tool_calls: list[dict] = []
    iterations: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


@router.post("/query", response_model=QueryResponse)
async def safety_query(request: QueryRequest):
    """Natural language query over NTSB incidents and FAA regulations."""
    result = await run_agent(request.query)
    return QueryResponse(
        answer=result.answer,
        tool_calls=[{"name": tc.name, "arguments": tc.arguments, "duration_ms": tc.duration_ms} for tc in result.tool_calls],
        iterations=result.iterations,
        total_tokens=result.total_tokens,
        error=result.error,
    )


@router.get("/aircraft/{aircraft_make}/context")
async def get_aircraft_context(
    aircraft_make: str,
    aircraft_model: Optional[str] = None,
):
    """Get safety context for an aircraft type (for real-time tracking integration)."""
    return await tool_get_aircraft_safety_context(
        aircraft_make=aircraft_make,
        aircraft_model=aircraft_model,
    )


@router.get("/incidents/stats")
async def get_incident_stats(
    aircraft_make: Optional[str] = None,
    aircraft_model: Optional[str] = None,
    event_state: Optional[str] = None,
    has_fatalities: Optional[bool] = None,
    aggregation: str = "count",
):
    """Get incident statistics with filters."""
    return await tool_query_incident_database(
        aircraft_make=aircraft_make,
        aircraft_model=aircraft_model,
        event_state=event_state,
        has_fatalities=has_fatalities,
        aggregation=aggregation,
    )


@router.get("/ingestion/status")
async def ingestion_status() -> dict[str, Any]:
    """Get current NTSB/eCFR ingestion status and collection stats."""
    return get_ingestion_status()
