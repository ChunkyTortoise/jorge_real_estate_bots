"""Tests for MemoryCache atomicity — no TOCTOU races in setnx/increment."""
from __future__ import annotations

import asyncio

import pytest

from bots.shared.cache_service import MemoryCache


async def test_setnx_concurrent_only_one_wins():
    """10 concurrent setnx on the same key — exactly 1 succeeds."""
    cache = MemoryCache()
    results = await asyncio.gather(*[cache.setnx("shared_key", i, ttl=60) for i in range(10)])
    assert results.count(True) == 1
    assert results.count(False) == 9


async def test_increment_concurrent_no_lost_updates():
    """10 concurrent increments — final value must be exactly 10."""
    cache = MemoryCache()
    await asyncio.gather(*[cache.increment("counter", 1, ttl=60) for _ in range(10)])
    final = await cache.get("counter")
    assert int(final) == 10


async def test_setnx_different_keys_all_succeed():
    """setnx on distinct keys — all 5 must succeed."""
    cache = MemoryCache()
    results = await asyncio.gather(
        *[cache.setnx(f"key:{i}", i, ttl=60) for i in range(5)]
    )
    assert all(results)
