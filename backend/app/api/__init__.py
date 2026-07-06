from fastapi import APIRouter
from .aircraft import router as aircraft_router
from .anomalies import router as anomalies_router

api_router = APIRouter()
api_router.include_router(aircraft_router)
api_router.include_router(anomalies_router)

__all__ = ["api_router"]
