"""Tests for webhook processing lock TTL and release behaviour."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.shared.cache_service import MemoryCache


async def test_lock_setnx_blocks_concurrent():
    """When lock is held, a second setnx on the same key returns False."""
    cache = MemoryCache()
    first = await cache.setnx("lock:contact123", "1", ttl=90)
    second = await cache.setnx("lock:contact123", "1", ttl=90)
    assert first is True
    assert second is False


async def test_lock_released_after_delete():
    """After explicit delete the lock can be re-acquired."""
    cache = MemoryCache()
    await cache.setnx("lock:contact123", "1", ttl=90)
    await cache.delete("lock:contact123")
    reacquired = await cache.setnx("lock:contact123", "1", ttl=90)
    assert reacquired is True


async def test_lock_ttl_is_90_seconds():
    """Verify the constant in routes_webhook uses 90s TTL (not 30s)."""
    import ast, pathlib
    src = pathlib.Path("bots/lead_bot/routes_webhook.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = getattr(node, 'func', None)
            if func and getattr(func, 'attr', None) == 'setnx':
                for kw in node.keywords:
                    if kw.arg == 'ttl':
                        assert isinstance(kw.value, ast.Constant)
                        assert kw.value.value == 90, (
                            f"Expected lock TTL=90 but got {kw.value.value}"
                        )
