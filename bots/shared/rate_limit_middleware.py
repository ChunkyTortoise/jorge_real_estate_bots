"""IP-based rate limit middleware for FastAPI.

Adds standard rate limit response headers and returns 429 when exceeded.
Uses the shared cache service (Redis with in-memory fallback).
"""

import time
from typing import Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)

# In-memory fallback when cache is unavailable
_memory_counters: Dict[str, Tuple[int, float]] = {}


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global IP-based rate limiter with standard headers."""

    # Paths exempt from rate limiting (health checks, docs)
    EXEMPT_PATHS = frozenset({"/health", "/health/aggregate", "/docs", "/redoc", "/openapi.json"})

    def __init__(self, app, requests_per_minute: int = 0):
        super().__init__(app)
        self.rpm = requests_per_minute or settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = _get_client_ip(request)
        now = time.time()
        window_key = f"rl:{client_ip}:{int(now // 60)}"
        window_reset = int((now // 60 + 1) * 60)

        count = await self._increment(window_key)

        remaining = max(0, self.rpm - count)
        headers = {
            "X-RateLimit-Limit": str(self.rpm),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(window_reset),
        }

        if count > self.rpm:
            logger.warning(f"Rate limit exceeded: ip={client_ip}, count={count}/{self.rpm}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers=headers,
            )

        response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = v
        return response

    async def _increment(self, key: str) -> int:
        """Increment counter via cache or in-memory fallback."""
        try:
            from bots.shared.cache_service import get_cache_service
            cache = get_cache_service()
            return await cache.increment(key, 1, ttl=60)
        except Exception:
            # In-memory fallback
            now = time.time()
            entry = _memory_counters.get(key)
            if entry and now - entry[1] < 60:
                new_count = entry[0] + 1
            else:
                new_count = 1
            _memory_counters[key] = (new_count, now)
            # Garbage-collect old entries
            if len(_memory_counters) > 10000:
                cutoff = now - 120
                for k in list(_memory_counters):
                    if _memory_counters[k][1] < cutoff:
                        del _memory_counters[k]
            return new_count
