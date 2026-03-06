"""Tests for bots.shared.rate_limit_middleware — RateLimitMiddleware."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from fastapi import FastAPI, Request

from bots.shared.rate_limit_middleware import (
    RateLimitMiddleware,
    _get_client_ip,
    _memory_counters,
)


# ---------------------------------------------------------------------------
# _get_client_ip helper
# ---------------------------------------------------------------------------

class TestGetClientIp:
    def test_direct_connection(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        assert _get_client_ip(request) == "10.0.0.1"

    def test_x_forwarded_for_single(self):
        request = MagicMock(spec=Request)
        request.headers = {"x-forwarded-for": "1.2.3.4"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_x_forwarded_for_multiple(self):
        request = MagicMock(spec=Request)
        request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_no_client_returns_unknown(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) == "unknown"


# ---------------------------------------------------------------------------
# FastAPI test app with middleware
# ---------------------------------------------------------------------------

def _create_test_app(rpm: int = 5) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rpm)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


# ---------------------------------------------------------------------------
# Rate limiting behaviour
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    def test_under_limit_passes(self):
        """Requests under rate limit should succeed."""
        app = _create_test_app(rpm=10)
        increment_mock = AsyncMock(return_value=1)
        with patch.object(RateLimitMiddleware, "_increment", increment_mock):
            client = TestClient(app)
            resp = client.get("/test")
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}

    def test_rate_limit_headers_present(self):
        """X-RateLimit-* headers should be set on every response."""
        app = _create_test_app(rpm=10)
        increment_mock = AsyncMock(return_value=3)
        with patch.object(RateLimitMiddleware, "_increment", increment_mock):
            client = TestClient(app)
            resp = client.get("/test")
            assert "X-RateLimit-Limit" in resp.headers
            assert "X-RateLimit-Remaining" in resp.headers
            assert "X-RateLimit-Reset" in resp.headers
            assert resp.headers["X-RateLimit-Limit"] == "10"
            assert resp.headers["X-RateLimit-Remaining"] == "7"

    def test_over_limit_returns_429(self):
        """Exceeding rate limit should return 429."""
        app = _create_test_app(rpm=5)
        increment_mock = AsyncMock(return_value=6)
        with patch.object(RateLimitMiddleware, "_increment", increment_mock):
            client = TestClient(app)
            resp = client.get("/test")
            assert resp.status_code == 429
            assert resp.json()["detail"] == "Rate limit exceeded. Try again later."
            assert resp.headers["X-RateLimit-Remaining"] == "0"

    def test_exempt_path_not_limited(self):
        """Health check paths should bypass rate limiting."""
        app = _create_test_app(rpm=1)
        increment_mock = AsyncMock(return_value=999)
        with patch.object(RateLimitMiddleware, "_increment", increment_mock):
            client = TestClient(app)
            resp = client.get("/health")
            # Should succeed even though count is way over limit
            assert resp.status_code == 200
            # Health endpoint should NOT have rate limit headers
            assert "X-RateLimit-Limit" not in resp.headers

    def test_exact_limit_passes(self):
        """Count == rpm should pass (only > rpm triggers 429)."""
        app = _create_test_app(rpm=5)
        increment_mock = AsyncMock(return_value=5)
        with patch.object(RateLimitMiddleware, "_increment", increment_mock):
            client = TestClient(app)
            resp = client.get("/test")
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Remaining"] == "0"


# ---------------------------------------------------------------------------
# In-memory fallback (_increment with cache failure)
# ---------------------------------------------------------------------------

class TestInMemoryFallback:
    def test_increment_falls_back_to_memory(self):
        """When cache raises, in-memory counter should be used."""
        _memory_counters.clear()
        app = _create_test_app(rpm=100)
        # get_cache_service is imported locally inside _increment
        with patch("bots.shared.cache_service.get_cache_service", side_effect=RuntimeError("no cache")):
            client = TestClient(app)
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_memory_fallback_counts_up(self):
        """In-memory fallback should increment properly across calls."""
        _memory_counters.clear()
        app = _create_test_app(rpm=2)
        with patch("bots.shared.cache_service.get_cache_service", side_effect=RuntimeError("no cache")):
            client = TestClient(app)
            # First request -> count=1
            resp1 = client.get("/test")
            assert resp1.status_code == 200
            # Second request -> count=2 (== rpm, still passes)
            resp2 = client.get("/test")
            assert resp2.status_code == 200
            # Third request -> count=3 (> rpm, 429)
            resp3 = client.get("/test")
            assert resp3.status_code == 429


# ---------------------------------------------------------------------------
# Burst allowance (rpm boundary)
# ---------------------------------------------------------------------------

class TestBurstAllowance:
    def test_burst_at_boundary(self):
        """Requests at exactly the limit should still pass."""
        app = _create_test_app(rpm=3)
        call_count = 0

        original_increment = RateLimitMiddleware._increment

        async def counting_increment(self, key):
            nonlocal call_count
            call_count += 1
            return call_count

        with patch.object(RateLimitMiddleware, "_increment", counting_increment):
            client = TestClient(app)
            results = [client.get("/test").status_code for _ in range(4)]
            # First 3 pass (counts 1,2,3), 4th fails (count 4 > 3)
            assert results == [200, 200, 200, 429]
