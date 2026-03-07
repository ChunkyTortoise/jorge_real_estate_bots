"""Tests for the /health endpoint real-status behaviour."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health_returns_200_when_redis_ok(client):
    """When Redis pings successfully and bots are initialised, /health → 200 healthy."""
    with (
        patch("bots.lead_bot.main.seller_bot_instance", new=object()),
        patch("bots.lead_bot.main.buyer_bot_instance", new=object()),
        patch("bots.lead_bot.main.settings") as mock_settings,
        patch("redis.asyncio.from_url") as mock_redis_from_url,
    ):
        mock_settings.redis_url = "redis://localhost:6379"
        mock_settings.environment = "test"
        mock_settings.lead_response_timeout_seconds = 300
        mock_settings.lead_analysis_timeout_ms = 4000

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis

        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["redis"] == "ok"


async def test_health_returns_503_when_redis_down(client):
    """When Redis is unreachable, /health → 503 degraded."""
    with (
        patch("bots.lead_bot.main.seller_bot_instance", new=object()),
        patch("bots.lead_bot.main.buyer_bot_instance", new=object()),
        patch("bots.lead_bot.main.settings") as mock_settings,
        patch("redis.asyncio.from_url") as mock_redis_from_url,
    ):
        mock_settings.redis_url = "redis://localhost:6379"
        mock_settings.environment = "test"
        mock_settings.lead_response_timeout_seconds = 300
        mock_settings.lead_analysis_timeout_ms = 4000

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("refused"))
        mock_redis.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis

        resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert "unreachable" in body["checks"]["redis"]


async def test_health_returns_503_when_bots_not_initialised(client):
    """When bot instances are None, /health → 503 degraded."""
    with (
        patch("bots.lead_bot.main.seller_bot_instance", new=None),
        patch("bots.lead_bot.main.buyer_bot_instance", new=None),
        patch("bots.lead_bot.main.settings") as mock_settings,
    ):
        mock_settings.redis_url = None  # No Redis configured
        mock_settings.environment = "test"
        mock_settings.lead_response_timeout_seconds = 300
        mock_settings.lead_analysis_timeout_ms = 4000

        resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["seller_bot"] == "not_initialized"
    assert body["checks"]["buyer_bot"] == "not_initialized"


async def test_health_ok_without_redis_configured(client):
    """When no Redis URL is set (dev mode), /health → 200 healthy if bots are up."""
    with (
        patch("bots.lead_bot.main.seller_bot_instance", new=object()),
        patch("bots.lead_bot.main.buyer_bot_instance", new=object()),
        patch("bots.lead_bot.main.settings") as mock_settings,
    ):
        mock_settings.redis_url = None
        mock_settings.environment = "development"
        mock_settings.lead_response_timeout_seconds = 300
        mock_settings.lead_analysis_timeout_ms = 4000

        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["redis"] == "not_configured"
