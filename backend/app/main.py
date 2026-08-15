from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import register_api_routes
from .core.config import get_settings
from .auth.origin import OriginProtectionMiddleware
from .auth.rate_limiter import RateLimitMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Real-time ADS-B flight tracking and anomaly detection",
    version="1.0.0",
)

# Rate limiting middleware (first to limit requests early)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(OriginProtectionMiddleware)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes directly; nested APIRouters can be lazily cached by FastAPI.
register_api_routes(app)

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
