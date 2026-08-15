"""Tool implementations for the aviation safety research agent."""

import logging
from typing import Any, Callable

from sqlalchemy import extract, func, select

from ..models import Incident, SafetyIngestionRunRecord
from ..models.safety import format_cfr_reference
from ..core.database import SessionLocal
from ..core.vectorstore import search_faa_regulations, search_incident_narratives

logger = logging.getLogger(__name__)


def get_sync_session():
    """Get a synchronous database session."""
    return SessionLocal()


async def tool_search_incident_narratives(
    query: str,
    n_results: int = 5,
    aircraft_make: str | None = None,
    aircraft_model: str | None = None,
    event_state: str | None = None,
    weather_condition: str | None = None,
    phase_of_flight: str | None = None,
    min_fatal_injuries: int | None = None,
) -> dict[str, Any]:
    """
    Semantic search over NTSB incident narratives.

    Returns relevant narrative excerpts with metadata.
    """
    # Build metadata filter
    where_filter: dict[str, Any] = {}

    if aircraft_make:
        where_filter["aircraft_make"] = aircraft_make
    if aircraft_model:
        where_filter["aircraft_model"] = aircraft_model
    if event_state:
        where_filter["event_state"] = event_state.upper()
    if weather_condition:
        where_filter["weather_condition"] = weather_condition.upper()
    if phase_of_flight:
        where_filter["phase_of_flight"] = phase_of_flight.upper()
    if min_fatal_injuries is not None:
        where_filter["fatal_injuries"] = {"$gte": min_fatal_injuries}

    try:
        # Search ChromaDB with text query
        results = await search_incident_narratives(
            query_text=query,
            n_results=n_results,
            where=where_filter if where_filter else None,
        )

        # Format results
        formatted_results = []
        for i, doc in enumerate(results.get("documents", [])):
            document_id = results.get("ids", [])[i] if results.get("ids") else None
            metadata = results.get("metadatas", [])[i] if results.get("metadatas") else {}
            distance = results.get("distances", [])[i] if results.get("distances") else None

            formatted_results.append({
                "ntsb_id": metadata.get("ntsb_id", ""),
                "document_id": document_id,
                "excerpt": doc,
                "section": metadata.get("section"),
                "char_start": metadata.get("char_start"),
                "char_end": metadata.get("char_end"),
                "source_url": metadata.get("source_url"),
                "source_sha256": metadata.get("source_sha256"),
                "source_run_id": metadata.get("source_run_id"),
                "event_date": metadata.get("event_date", ""),
                "event_state": metadata.get("event_state", ""),
                "aircraft": f"{metadata.get('aircraft_make', '')} {metadata.get('aircraft_model', '')}".strip(),
                "weather": metadata.get("weather_condition", ""),
                "phase_of_flight": metadata.get("phase_of_flight", ""),
                "fatal_injuries": metadata.get("fatal_injuries", 0),
                "relevance_score": 1 - distance if distance is not None else None,
            })

        return {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"error": str(e), "results": []}


async def tool_query_incident_database(
    aircraft_make: str | None = None,
    aircraft_model: str | None = None,
    event_state: str | None = None,
    weather_condition: str | None = None,
    phase_of_flight: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    has_fatalities: bool | None = None,
    aggregation: str = "count",
    limit: int = 10,
) -> dict[str, Any]:
    """
    Structured query against the PostgreSQL incident database.

    Supports various aggregations: count, list, by_year, by_state, by_aircraft, by_phase.
    """
    session = get_sync_session()

    try:
        # Build base query filters
        filters = []

        if aircraft_make:
            filters.append(func.lower(Incident.aircraft_make).contains(aircraft_make.lower()))
        if aircraft_model:
            filters.append(func.lower(Incident.aircraft_model).contains(aircraft_model.lower()))
        if event_state:
            filters.append(Incident.event_state == event_state.upper())
        if weather_condition:
            filters.append(func.upper(Incident.weather_condition) == weather_condition.upper())
        if phase_of_flight:
            filters.append(func.upper(Incident.phase_of_flight).contains(phase_of_flight.upper()))
        if year_from:
            filters.append(extract("year", Incident.event_date) >= year_from)
        if year_to:
            filters.append(extract("year", Incident.event_date) <= year_to)
        if has_fatalities is True:
            filters.append(Incident.fatal_injuries > 0)
        elif has_fatalities is False:
            filters.append(Incident.fatal_injuries == 0)

        # Execute based on aggregation type
        if aggregation == "count":
            query = select(func.count(Incident.ntsb_id))
            for f in filters:
                query = query.where(f)
            result = session.execute(query).scalar()
            return {
                "aggregation": "count",
                "filters_applied": _format_filters(
                    aircraft_make, aircraft_model, event_state,
                    weather_condition, phase_of_flight, year_from, year_to, has_fatalities
                ),
                "total_count": result or 0,
            }

        elif aggregation == "list":
            query = select(Incident).limit(limit)
            for f in filters:
                query = query.where(f)
            query = query.order_by(Incident.event_date.desc())
            results = session.execute(query).scalars().all()

            return {
                "aggregation": "list",
                "filters_applied": _format_filters(
                    aircraft_make, aircraft_model, event_state,
                    weather_condition, phase_of_flight, year_from, year_to, has_fatalities
                ),
                "total_results": len(results),
                "incidents": [
                    {
                        "ntsb_id": inc.ntsb_id,
                        "event_date": str(inc.event_date) if inc.event_date else None,
                        "location": f"{inc.event_city or ''}, {inc.event_state or ''}".strip(", "),
                        "aircraft": f"{inc.aircraft_make or ''} {inc.aircraft_model or ''}".strip(),
                        "fatal_injuries": inc.fatal_injuries,
                        "weather": inc.weather_condition,
                        "phase_of_flight": inc.phase_of_flight,
                    }
                    for inc in results
                ],
            }

        elif aggregation == "by_year":
            year_col = extract("year", Incident.event_date).label("year")
            query = select(year_col, func.count(Incident.ntsb_id).label("count"))
            for f in filters:
                query = query.where(f)
            query = query.group_by(year_col).order_by(year_col.desc()).limit(limit)
            results = session.execute(query).all()

            return {
                "aggregation": "by_year",
                "filters_applied": _format_filters(
                    aircraft_make, aircraft_model, event_state,
                    weather_condition, phase_of_flight, year_from, year_to, has_fatalities
                ),
                "data": [{"year": int(r.year), "count": r.count} for r in results if r.year],
            }

        elif aggregation == "by_state":
            query = select(
                Incident.event_state,
                func.count(Incident.ntsb_id).label("count")
            )
            for f in filters:
                query = query.where(f)
            query = query.where(Incident.event_state.isnot(None))
            query = query.group_by(Incident.event_state).order_by(func.count(Incident.ntsb_id).desc()).limit(limit)
            results = session.execute(query).all()

            return {
                "aggregation": "by_state",
                "filters_applied": _format_filters(
                    aircraft_make, aircraft_model, event_state,
                    weather_condition, phase_of_flight, year_from, year_to, has_fatalities
                ),
                "data": [{"state": r.event_state, "count": r.count} for r in results],
            }

        elif aggregation == "by_aircraft":
            query = select(
                Incident.aircraft_make,
                Incident.aircraft_model,
                func.count(Incident.ntsb_id).label("count")
            )
            for f in filters:
                query = query.where(f)
            query = query.group_by(Incident.aircraft_make, Incident.aircraft_model)
            query = query.order_by(func.count(Incident.ntsb_id).desc()).limit(limit)
            results = session.execute(query).all()

            return {
                "aggregation": "by_aircraft",
                "filters_applied": _format_filters(
                    aircraft_make, aircraft_model, event_state,
                    weather_condition, phase_of_flight, year_from, year_to, has_fatalities
                ),
                "data": [
                    {
                        "aircraft": f"{r.aircraft_make or ''} {r.aircraft_model or ''}".strip(),
                        "count": r.count,
                    }
                    for r in results
                ],
            }

        elif aggregation == "by_phase":
            query = select(
                Incident.phase_of_flight,
                func.count(Incident.ntsb_id).label("count")
            )
            for f in filters:
                query = query.where(f)
            query = query.where(Incident.phase_of_flight.isnot(None))
            query = query.group_by(Incident.phase_of_flight)
            query = query.order_by(func.count(Incident.ntsb_id).desc()).limit(limit)
            results = session.execute(query).all()

            return {
                "aggregation": "by_phase",
                "filters_applied": _format_filters(
                    aircraft_make, aircraft_model, event_state,
                    weather_condition, phase_of_flight, year_from, year_to, has_fatalities
                ),
                "data": [{"phase": r.phase_of_flight, "count": r.count} for r in results],
            }

        else:
            return {"error": f"Unknown aggregation type: {aggregation}"}

    except Exception as e:
        logger.error(f"Database query error: {e}")
        return {"error": str(e)}
    finally:
        session.close()


async def tool_search_faa_regulations(
    query: str,
    n_results: int = 5,
    cfr_part: int | str | None = None,
) -> dict[str, Any]:
    """
    Semantic search over FAA regulations (14 CFR).
    """
    # Build metadata filter
    where_filter: dict[str, Any] = {}
    if cfr_part is not None:
        # Coerce to int in case LLM sends a string
        try:
            where_filter["cfr_part"] = int(cfr_part)
        except (ValueError, TypeError):
            pass

    try:
        # Search ChromaDB with text query
        results = await search_faa_regulations(
            query_text=query,
            n_results=n_results,
            where=where_filter if where_filter else None,
        )

        # Format results
        formatted_results = []
        for i, doc in enumerate(results.get("documents", [])):
            document_id = results.get("ids", [])[i] if results.get("ids") else None
            metadata = results.get("metadatas", [])[i] if results.get("metadatas") else {}
            distance = results.get("distances", [])[i] if results.get("distances") else None

            cfr_ref = format_cfr_reference(
                14,
                int(metadata.get("cfr_part", 0)),
                str(metadata.get("cfr_section", "")),
            )

            formatted_results.append({
                "cfr_reference": cfr_ref,
                "document_id": document_id,
                "section_title": metadata.get("section_title", ""),
                "text_excerpt": doc,
                "section": metadata.get("cfr_section"),
                "char_start": 0,
                "char_end": len(doc),
                "effective_date": metadata.get("effective_date"),
                "source_url": metadata.get("source_url"),
                "source_sha256": metadata.get("source_sha256"),
                "source_run_id": metadata.get("source_run_id"),
                "relevance_score": 1 - distance if distance is not None else None,
            })

        return {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Regulation search error: {e}")
        return {"error": str(e), "results": []}


async def tool_get_incident_detail(ntsb_id: str) -> dict[str, Any]:
    """
    Get full details for a specific incident by NTSB ID.
    """
    session = get_sync_session()

    try:
        incident = session.query(Incident).filter(Incident.ntsb_id == ntsb_id).first()

        if not incident:
            return {"error": f"Incident {ntsb_id} not found"}

        source_run = (
            session.get(SafetyIngestionRunRecord, incident.source_run_id)
            if incident.source_run_id
            else None
        )

        return {
            "ntsb_id": incident.ntsb_id,
            "event_date": str(incident.event_date) if incident.event_date else None,
            "location": {
                "city": incident.event_city,
                "state": incident.event_state,
                "country": incident.event_country,
            },
            "aircraft": {
                "make": incident.aircraft_make,
                "model": incident.aircraft_model,
                "category": incident.aircraft_category,
                "damage": incident.aircraft_damage,
                "registration": incident.registration_number,
            },
            "injuries": {
                "fatal": incident.fatal_injuries,
                "serious": incident.serious_injuries,
                "minor": incident.minor_injuries,
                "uninjured": incident.uninjured,
            },
            "conditions": {
                "weather": incident.weather_condition,
                "phase_of_flight": incident.phase_of_flight,
                "flight_purpose": incident.flight_purpose,
            },
            "pilot": {
                "certificate": incident.pilot_certificate,
                "total_hours": incident.pilot_total_hours,
            },
            "investigation": {
                "type": incident.investigation_type,
                "probable_cause": incident.probable_cause,
            },
            "narrative": incident.narrative,
            "document_id": f"{incident.ntsb_id}:detail",
            "section": "full_report",
            "char_start": 0,
            "char_end": len(incident.narrative or incident.probable_cause or ""),
            "source_url": incident.source_url,
            "source_run_id": str(incident.source_run_id) if incident.source_run_id else None,
            "source_sha256": source_run.source_sha256 if source_run else None,
            "effective_date": (
                source_run.effective_date.isoformat()
                if source_run and source_run.effective_date
                else None
            ),
        }

    except Exception as e:
        logger.error(f"Error fetching incident {ntsb_id}: {e}")
        return {"error": str(e)}
    finally:
        session.close()


async def tool_get_aircraft_safety_context(
    aircraft_make: str,
    aircraft_model: str | None = None,
    include_regulations: bool = True,
    n_incidents: int = 5,
) -> dict[str, Any]:
    """
    Get safety context for a specific aircraft type.

    This tool is designed for real-time flight tracking integration -
    given an aircraft type, it returns relevant historical incidents
    and applicable regulations.
    """
    results = {
        "aircraft": f"{aircraft_make} {aircraft_model or ''}".strip(),
        "incidents": {},
        "regulations": [],
        "risk_factors": [],
    }

    try:
        # Get incident statistics for this aircraft type
        stats = await tool_query_incident_database(
            aircraft_make=aircraft_make,
            aircraft_model=aircraft_model,
            aggregation="count",
        )
        results["incidents"]["total_count"] = stats.get("total_count", 0)

        # Get fatal incident count
        fatal_stats = await tool_query_incident_database(
            aircraft_make=aircraft_make,
            aircraft_model=aircraft_model,
            has_fatalities=True,
            aggregation="count",
        )
        results["incidents"]["fatal_count"] = fatal_stats.get("total_count", 0)

        # Get incidents by phase of flight
        phase_stats = await tool_query_incident_database(
            aircraft_make=aircraft_make,
            aircraft_model=aircraft_model,
            aggregation="by_phase",
            limit=5,
        )
        results["incidents"]["by_phase"] = phase_stats.get("data", [])

        # Search for common causal factors in narratives
        narrative_search = await tool_search_incident_narratives(
            query=f"Common accident causes for {aircraft_make} {aircraft_model or ''}",
            aircraft_make=aircraft_make,
            aircraft_model=aircraft_model,
            n_results=n_incidents,
        )
        results["incidents"]["recent_examples"] = narrative_search.get("results", [])

        # Identify risk factors from phase data
        if results["incidents"]["by_phase"]:
            top_phase = results["incidents"]["by_phase"][0]
            if top_phase["count"] > 10:
                results["risk_factors"].append({
                    "factor": f"High incident rate during {top_phase['phase']}",
                    "count": top_phase["count"],
                })

        # Get relevant regulations if requested
        if include_regulations:
            reg_search = await tool_search_faa_regulations(
                query=f"operating requirements for {aircraft_make} aircraft",
                n_results=3,
            )
            results["regulations"] = reg_search.get("results", [])

        return results

    except Exception as e:
        logger.error(f"Error getting safety context: {e}")
        return {"error": str(e)}


def _format_filters(
    aircraft_make: str | None,
    aircraft_model: str | None,
    event_state: str | None,
    weather_condition: str | None,
    phase_of_flight: str | None,
    year_from: int | None,
    year_to: int | None,
    has_fatalities: bool | None,
) -> dict[str, Any]:
    """Format applied filters for response."""
    filters = {}
    if aircraft_make:
        filters["aircraft_make"] = aircraft_make
    if aircraft_model:
        filters["aircraft_model"] = aircraft_model
    if event_state:
        filters["event_state"] = event_state
    if weather_condition:
        filters["weather_condition"] = weather_condition
    if phase_of_flight:
        filters["phase_of_flight"] = phase_of_flight
    if year_from:
        filters["year_from"] = year_from
    if year_to:
        filters["year_to"] = year_to
    if has_fatalities is not None:
        filters["has_fatalities"] = has_fatalities
    return filters


# Tool registry mapping function names to implementations
TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "search_incident_narratives": tool_search_incident_narratives,
    "query_incident_database": tool_query_incident_database,
    "search_faa_regulations": tool_search_faa_regulations,
    "get_incident_detail": tool_get_incident_detail,
    "get_aircraft_safety_context": tool_get_aircraft_safety_context,
}
