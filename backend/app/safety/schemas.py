"""OpenAI function definitions for agent tools."""

from typing import Any


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get OpenAI function definitions for all agent tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_incident_narratives",
                "description": "Search NTSB incident narratives using semantic search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "n_results": {"type": "integer", "default": 5},
                        "aircraft_make": {"type": "string"},
                        "aircraft_model": {"type": "string"},
                        "event_state": {"type": "string"},
                        "weather_condition": {"type": "string"},
                        "phase_of_flight": {"type": "string"},
                        "min_fatal_injuries": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_incident_database",
                "description": "Query incident database for counts and statistics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aircraft_make": {"type": "string"},
                        "aircraft_model": {"type": "string"},
                        "event_state": {"type": "string"},
                        "weather_condition": {"type": "string"},
                        "phase_of_flight": {"type": "string"},
                        "year_from": {"type": "integer"},
                        "year_to": {"type": "integer"},
                        "has_fatalities": {"type": "boolean"},
                        "aggregation": {
                            "type": "string",
                            "enum": ["count", "list", "by_year", "by_state", "by_aircraft", "by_phase"],
                            "default": "count",
                        },
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_faa_regulations",
                "description": "Search FAA regulations (14 CFR).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "n_results": {"type": "integer", "default": 5},
                        "cfr_part": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_incident_detail",
                "description": "Get full details for a specific NTSB incident.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ntsb_id": {"type": "string"},
                    },
                    "required": ["ntsb_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_aircraft_safety_context",
                "description": "Get safety context for an aircraft type (for real-time tracking).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aircraft_make": {"type": "string"},
                        "aircraft_model": {"type": "string"},
                        "include_regulations": {"type": "boolean", "default": True},
                        "n_incidents": {"type": "integer", "default": 5},
                    },
                    "required": ["aircraft_make"],
                },
            },
        },
    ]
