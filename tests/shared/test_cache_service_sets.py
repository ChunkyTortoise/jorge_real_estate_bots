"""Tests for set operations in cache backends."""

from __future__ import annotations

import pytest

from bots.shared.cache_service import MemoryCache


@pytest.mark.asyncio
async def test_memory_cache_set_operations_round_trip() -> None:
    cache = MemoryCache()

    added = await cache.sadd("seller:active_contacts", "c1", "c2")
    members = await cache.smembers("seller:active_contacts")
    removed = await cache.srem("seller:active_contacts", "c1")
    after = await cache.smembers("seller:active_contacts")

    assert added == 2
    assert members == {"c1", "c2"}
    assert removed == 1
    assert after == {"c2"}


@pytest.mark.asyncio
async def test_memory_cache_set_operations_expire() -> None:
    cache = MemoryCache()

    await cache.sadd("buyer:active_contacts", "c1", ttl=1)
    assert await cache.smembers("buyer:active_contacts") == {"c1"}

    # expire immediately for deterministic assertion
    cache._expiry["buyer:active_contacts"] = 0
    assert await cache.smembers("buyer:active_contacts") == set()


# ========== get / set / delete round-trip ==========


@pytest.mark.asyncio
async def test_memory_cache_get_set_delete_round_trip() -> None:
    """get/set/delete round-trip on plain key-value."""
    cache = MemoryCache()

    # Initially empty
    assert await cache.get("mykey") is None

    # Set and retrieve
    await cache.set("mykey", {"price": 375000}, ttl=300)
    result = await cache.get("mykey")
    assert result == {"price": 375000}

    # Delete and confirm gone
    deleted = await cache.delete("mykey")
    assert deleted is True
    assert await cache.get("mykey") is None


@pytest.mark.asyncio
async def test_memory_cache_delete_nonexistent_key() -> None:
    """delete returns False for a key that does not exist."""
    cache = MemoryCache()
    assert await cache.delete("nonexistent") is False


# ========== setnx atomicity ==========


@pytest.mark.asyncio
async def test_memory_cache_setnx_first_set_returns_true() -> None:
    """setnx returns True on first set."""
    cache = MemoryCache()
    result = await cache.setnx("lock:contact_1", "owner_a", ttl=60)
    assert result is True


@pytest.mark.asyncio
async def test_memory_cache_setnx_second_set_returns_false() -> None:
    """setnx returns False when key already exists."""
    cache = MemoryCache()
    first = await cache.setnx("lock:contact_1", "owner_a", ttl=60)
    second = await cache.setnx("lock:contact_1", "owner_b", ttl=60)
    assert first is True
    assert second is False
    # Original value preserved
    assert await cache.get("lock:contact_1") == "owner_a"


@pytest.mark.asyncio
async def test_memory_cache_setnx_after_expiry_returns_true() -> None:
    """setnx succeeds again after key expires."""
    cache = MemoryCache()
    await cache.setnx("lock:contact_1", "owner_a", ttl=60)
    # Force expiry
    cache._expiry["lock:contact_1"] = 0
    result = await cache.setnx("lock:contact_1", "owner_b", ttl=60)
    assert result is True
    assert await cache.get("lock:contact_1") == "owner_b"


# ========== increment with TTL ==========


@pytest.mark.asyncio
async def test_memory_cache_increment_basic() -> None:
    """increment starts at 0 and increments."""
    cache = MemoryCache()
    val = await cache.increment("counter:msgs", amount=1, ttl=300)
    assert val == 1
    val = await cache.increment("counter:msgs", amount=1, ttl=300)
    assert val == 2


@pytest.mark.asyncio
async def test_memory_cache_increment_with_amount() -> None:
    """increment supports arbitrary amounts."""
    cache = MemoryCache()
    val = await cache.increment("counter:msgs", amount=5, ttl=300)
    assert val == 5
    val = await cache.increment("counter:msgs", amount=3, ttl=300)
    assert val == 8


@pytest.mark.asyncio
async def test_memory_cache_increment_respects_ttl() -> None:
    """increment value disappears after TTL."""
    cache = MemoryCache()
    await cache.increment("counter:rate", amount=1, ttl=60)
    assert await cache.get("counter:rate") == 1
    # Force expiry
    cache._expiry["counter:rate"] = 0
    assert await cache.get("counter:rate") is None


# ========== MemoryCache used when Redis URL not configured ==========


@pytest.mark.asyncio
async def test_cache_service_uses_memory_when_no_redis() -> None:
    """CacheService falls back to MemoryCache when redis_url is empty."""
    from unittest.mock import patch

    from bots.shared.cache_service import CacheService, MemoryCache

    # Reset singleton
    CacheService._instance = None

    with patch("bots.shared.cache_service.settings") as mock_settings:
        mock_settings.redis_url = ""
        svc = CacheService()
        assert isinstance(svc.backend, MemoryCache)

    # Clean up singleton
    CacheService._instance = None


# ========== Dual-write verification ==========


@pytest.mark.asyncio
async def test_cache_service_dual_write() -> None:
    """CacheService.set() stores in both primary and fallback backends."""
    from unittest.mock import AsyncMock, patch

    from bots.shared.cache_service import CacheService, MemoryCache

    # Reset singleton
    CacheService._instance = None

    with patch("bots.shared.cache_service.settings") as mock_settings:
        mock_settings.redis_url = ""
        svc = CacheService()

    # Inject a mock primary that is different from fallback
    mock_primary = AsyncMock()
    mock_primary.set = AsyncMock(return_value=True)
    mock_primary.get = AsyncMock(return_value=None)
    svc.backend = mock_primary
    # fallback_backend is the real MemoryCache from __init__
    assert isinstance(svc.fallback_backend, MemoryCache)

    await svc.set("dual:key", "dual_value", ttl=120)

    # Primary was written
    mock_primary.set.assert_called_once_with("dual:key", "dual_value", 120)
    # Fallback also has the value
    assert await svc.fallback_backend.get("dual:key") == "dual_value"

    # Clean up singleton
    CacheService._instance = None


@pytest.mark.asyncio
async def test_cache_service_fallback_on_primary_miss() -> None:
    """CacheService.get() falls back when primary returns None."""
    from unittest.mock import AsyncMock, patch

    from bots.shared.cache_service import CacheService, MemoryCache

    CacheService._instance = None

    with patch("bots.shared.cache_service.settings") as mock_settings:
        mock_settings.redis_url = ""
        svc = CacheService()

    # Inject mock primary that always misses
    mock_primary = AsyncMock()
    mock_primary.set = AsyncMock(return_value=True)
    mock_primary.get = AsyncMock(return_value=None)
    svc.backend = mock_primary

    # Pre-populate fallback
    await svc.fallback_backend.set("fb:key", "fb_value", ttl=120)

    result = await svc.get("fb:key")
    assert result == "fb_value"

    CacheService._instance = None
