"""Lazy schema exports keep database-free consumers free of ORM imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORT_MODULES = {
    "AircraftBase": ".aircraft",
    "AircraftCreate": ".aircraft",
    "AircraftResponse": ".aircraft",
    "AircraftPositionResponse": ".aircraft",
    "FlightTrailResponse": ".aircraft",
    "AnomalyResponse": ".aircraft",
    "AnomalyAcknowledge": ".aircraft",
    "DailySummaryResponse": ".aircraft",
    "StatsResponse": ".aircraft",
    "BoundsRequest": ".aircraft",
    "ObservationProvenance": ".observation",
    "ObservationQualityFlag": ".observation",
    "ObservationSourceType": ".observation",
    "TrackObservation": ".observation",
    "UserBase": ".auth",
    "UserCreate": ".auth",
    "UserLogin": ".auth",
    "UserResponse": ".auth",
    "SessionResponse": ".auth",
    "TokenData": ".auth",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
