from fastapi import FastAPI
from .aircraft import router as aircraft_router
from .anomalies import router as anomalies_router
from .websocket import router as websocket_router
from .safety import router as safety_router
from .replay import router as replay_router
from .kinematics import router as kinematics_router
from .corroboration import router as corroboration_router
from .stations import router as stations_router
from .trust import router as trust_router
from .trust_events import router as trust_events_router

API_ROUTERS = (
    aircraft_router,
    anomalies_router,
    websocket_router,
    safety_router,
    replay_router,
    kinematics_router,
    corroboration_router,
    stations_router,
    trust_router,
    trust_events_router,
)


def register_api_routes(app: FastAPI, *, prefix: str = "/api/v1") -> None:
    """Register each router directly so lazy nested-router caches cannot omit routes."""
    for router in API_ROUTERS:
        app.include_router(router, prefix=prefix)


__all__ = ["register_api_routes"]
