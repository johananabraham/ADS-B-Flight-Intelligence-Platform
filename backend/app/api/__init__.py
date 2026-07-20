from fastapi import APIRouter
from .aircraft import router as aircraft_router
from .anomalies import router as anomalies_router
from .websocket import router as websocket_router
from .safety import router as safety_router
from .replay import router as replay_router

api_router = APIRouter()
api_router.include_router(aircraft_router)
api_router.include_router(anomalies_router)
api_router.include_router(websocket_router)
api_router.include_router(safety_router)
api_router.include_router(replay_router)

__all__ = ["api_router"]
