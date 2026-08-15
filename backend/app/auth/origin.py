"""CSRF defense for cookie-authenticated state-changing requests."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..core.config import get_settings


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class OriginProtectionMiddleware(BaseHTTPMiddleware):
    """Reject unsafe requests without an explicitly approved browser origin."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method.upper() not in SAFE_METHODS:
            origin = (request.headers.get("origin") or "").rstrip("/")
            if not origin or origin not in get_settings().allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Origin is not allowed for this request"},
                )
        return await call_next(request)
