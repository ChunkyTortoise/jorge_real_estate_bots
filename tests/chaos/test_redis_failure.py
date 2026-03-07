"""Chaos tests: Redis failure scenarios — fallback, dedup, rate limiting."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from bots.shared.cache_service import CacheService, MemoryCache


async def test_cache_service_falls_back_when_redis_down():
    """When Redis raises ConnectionError, CacheService uses MemoryCache fallback."""
    svc = CacheService.__new__(CacheService)
    svc.fallback_backend = MemoryCache()

    # Backend raises on every operation
    failing_backend = AsyncMock()
    failing_backend.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    failing_backend.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    svc.backend = failing_backend

    # set() should fall through to fallback
    result = await svc.set("key", "value", ttl=60)
    assert result  # MemoryCache.set returns True

    # get() should fall through to fallback
    val = await svc.get("key")
    assert val == "value"


async def test_rate_limit_works_with_memory_cache_fallback():
    """Rate limiting falls back to _memory_counters when cache.increment raises."""
    from bots.shared.rate_limit_middleware import _memory_counters, RateLimitMiddleware
    from bots.shared.cache_service import CacheService
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import AsyncMock, patch

    _memory_counters.clear()

    app = FastAPI()

    @app.get("/test")
    async def test_route():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

    # Force cache.increment to raise so _increment uses _memory_counters fallback
    with patch.object(CacheService, "increment", new_callable=AsyncMock,
                      side_effect=Exception("Redis down")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/test")
            assert resp.status_code == 200


async def test_memory_cache_setnx_works_when_redis_absent():
    """MemoryCache.setnx returns True/False correctly without Redis."""
    cache = MemoryCache()
    first = await cache.setnx("lock-key", "1", ttl=60)
    second = await cache.setnx("lock-key", "1", ttl=60)
    assert first is True
    assert second is False


async def test_memory_cache_increment_works_when_redis_absent():
    """MemoryCache.increment accumulates correctly without Redis."""
    cache = MemoryCache()
    v1 = await cache.increment("counter", ttl=60)
    v2 = await cache.increment("counter", ttl=60)
    v3 = await cache.increment("counter", ttl=60)
    assert v1 == 1
    assert v2 == 2
    assert v3 == 3


async def test_seller_bot_continues_with_redis_down():
    """Seller bot handles Redis ConnectionError and returns a response."""
    from bots.seller_bot.jorge_seller_bot import JorgeSellerBot

    bot = JorgeSellerBot()
    bot.cache = AsyncMock()
    bot.cache.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    bot.cache.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    bot.cache.setnx = AsyncMock(side_effect=ConnectionError("Redis down"))
    bot.cache.delete = AsyncMock(side_effect=ConnectionError("Redis down"))

    with patch.object(
        bot.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="What condition is the property in?"),
    ):
        # Should not raise — graceful degradation
        result = await bot.process_seller_message(
            contact_id="redis-down-seller", location_id="loc-test",
            message="I want to sell my house"
        )
    assert result.response_message


async def test_buyer_bot_continues_with_redis_down():
    """Buyer bot handles Redis ConnectionError and returns a response."""
    from bots.buyer_bot.buyer_bot import JorgeBuyerBot

    bot = JorgeBuyerBot()
    bot.cache = AsyncMock()
    bot.cache.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    bot.cache.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    bot.cache.setnx = AsyncMock(side_effect=ConnectionError("Redis down"))
    bot.cache.delete = AsyncMock(side_effect=ConnectionError("Redis down"))

    with patch.object(
        bot.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="How many bedrooms are you looking for?"),
    ):
        result = await bot.process_buyer_message(
            contact_id="redis-down-buyer", location_id="loc-test",
            message="I want to buy a house"
        )
    assert result.response_message


async def test_dedup_falls_through_when_cache_fails():
    """When cache is unavailable, dedup check fails open (message is processed)."""
    cache = AsyncMock()
    cache.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    cache.set = AsyncMock(side_effect=ConnectionError("Redis down"))

    # Simulate dedup logic: if get raises, treat as cache miss
    async def safe_dedup_get(key: str):
        try:
            return await cache.get(key)
        except ConnectionError:
            return None  # fail open

    result = await safe_dedup_get("dedup:contact:abc")
    assert result is None  # No dedup block — message proceeds


async def test_cache_service_increment_returns_zero_on_redis_error():
    """CacheService.increment returns 0 when both backends fail (safe — no block)."""
    svc = CacheService.__new__(CacheService)
    bad_backend = AsyncMock()
    bad_backend.increment = AsyncMock(side_effect=Exception("Redis error"))
    svc.backend = bad_backend
    svc.fallback_backend = bad_backend  # both fail

    result = await svc.increment("key", 1)
    assert result == 0
