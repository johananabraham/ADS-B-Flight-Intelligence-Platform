"""Rate limiting middleware for API endpoints."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import asyncio


class RateLimiter:
    """Simple in-memory rate limiter.

    Note: In production, use Redis or a similar distributed cache
    for rate limiting across multiple instances.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        login_requests_per_minute: int = 5,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute for general endpoints
            login_requests_per_minute: Maximum login attempts per minute
        """
        self.requests_per_minute = requests_per_minute
        self.login_requests_per_minute = login_requests_per_minute

        # Store: {ip_address: [(timestamp, endpoint), ...]}
        self.request_history: Dict[str, list] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        client_ip: str,
        endpoint: str,
        is_login: bool = False,
    ) -> Tuple[bool, int]:
        """Check if request is within rate limit.

        Args:
            client_ip: Client IP address
            endpoint: Endpoint being accessed
            is_login: Whether this is a login endpoint

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        async with self.lock:
            now = datetime.now(timezone.utc)
            minute_ago = now - timedelta(minutes=1)

            # Clean old requests
            self.request_history[client_ip] = [
                (ts, ep)
                for ts, ep in self.request_history[client_ip]
                if ts > minute_ago
            ]

            # Count requests in the last minute
            recent_requests = self.request_history[client_ip]

            # Check login-specific rate limit
            if is_login:
                login_count = sum(1 for _, ep in recent_requests if "/login" in ep)
                limit = self.login_requests_per_minute
                if login_count >= limit:
                    return False, 0

                # Add current request
                self.request_history[client_ip].append((now, endpoint))
                return True, limit - login_count - 1

            # Check general rate limit
            general_count = len(recent_requests)
            limit = self.requests_per_minute
            if general_count >= limit:
                return False, 0

            # Add current request
            self.request_history[client_ip].append((now, endpoint))
            return True, limit - general_count - 1


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on API requests."""

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce rate limits.

        Args:
            request: The incoming request
            call_next: Next middleware or endpoint

        Returns:
            Response or rate limit error
        """
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for health checks and static files
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Check if this is a login endpoint
        is_login = "/auth/login" in request.url.path

        # Check rate limit
        is_allowed, remaining = await rate_limiter.check_rate_limit(
            client_ip,
            request.url.path,
            is_login,
        )

        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Limit": str(
                        rate_limiter.login_requests_per_minute
                        if is_login
                        else rate_limiter.requests_per_minute
                    ),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(
            rate_limiter.login_requests_per_minute
            if is_login
            else rate_limiter.requests_per_minute
        )

        return response
