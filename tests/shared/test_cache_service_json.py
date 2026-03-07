"""Tests for JSON-based serialisation in RedisCache (replacing pickle)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from bots.shared.cache_service import (
    MemoryCache,
    _cache_dumps,
    _cache_loads,
)


# ── JSON serialisation helpers ────────────────────────────────────────────────

def test_cache_dumps_loads_roundtrip_simple():
    """Basic Python primitives survive a dumps→loads roundtrip."""
    for value in [42, "hello", [1, 2, 3], {"a": 1}]:
        assert _cache_loads(_cache_dumps(value)) == value


def test_cache_dumps_loads_roundtrip_datetime():
    """datetime objects survive a dumps→loads roundtrip via __type__ hook."""
    dt = datetime(2026, 3, 5, 12, 0, 0)
    result = _cache_loads(_cache_dumps(dt))
    assert result == dt


def test_cache_dumps_loads_roundtrip_set():
    """Sets survive a dumps→loads roundtrip."""
    s = {"a", "b", "c"}
    result = _cache_loads(_cache_dumps(s))
    assert result == s


def test_cache_dumps_produces_bytes():
    assert isinstance(_cache_dumps({"key": "value"}), bytes)


def test_cache_loads_rejects_corrupt_data():
    with pytest.raises(Exception):
        _cache_loads(b"not-valid-json-or-pickle")


# ── MemoryCache basic operations ─────────────────────────────────────────────

async def test_memory_cache_set_and_get():
    cache = MemoryCache()
    await cache.set("k", {"score": 99}, ttl=60)
    result = await cache.get("k")
    assert result == {"score": 99}


async def test_redis_cache_returns_none_on_non_json_bytes():
    """RedisCache.get() returns None (not pickle) when cache has non-JSON binary data."""
    from unittest.mock import AsyncMock
    from bots.shared.cache_service import RedisCache

    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"\x80\x04\x95"  # raw pickle header bytes

    cache = RedisCache.__new__(RedisCache)
    cache.redis = mock_redis
    cache.enabled = True

    result = await cache.get("test-key")
    assert result is None


async def test_memory_cache_setnx_only_first_wins():
    cache = MemoryCache()
    first = await cache.setnx("k", "first", ttl=60)
    second = await cache.setnx("k", "second", ttl=60)
    assert first is True
    assert second is False
    assert await cache.get("k") == "first"
