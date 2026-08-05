from fastapi import APIRouter
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

api_router = APIRouter()
api_router.include_router(aircraft_router)
api_router.include_router(anomalies_router)
api_router.include_router(websocket_router)
api_router.include_router(safety_router)
api_router.include_router(replay_router)
api_router.include_router(kinematics_router)
api_router.include_router(corroboration_router)
api_router.include_router(stations_router)
api_router.include_router(trust_router)
api_router.include_router(trust_events_router)

__all__ = ["api_router"]
