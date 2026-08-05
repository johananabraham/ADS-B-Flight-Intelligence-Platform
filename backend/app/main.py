from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import register_api_routes
from .core.config import get_settings
from .core.database import engine, Base

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Real-time ADS-B flight tracking and anomaly detection",
    version="1.0.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes directly; nested APIRouters can be lazily cached by FastAPI.
register_api_routes(app)


@app.on_event("startup")
async def startup():
    # Create tables (for development - use alembic in production)
    Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
