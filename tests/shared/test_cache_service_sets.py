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
