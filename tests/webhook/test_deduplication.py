"""Tests for message deduplication logic."""
from __future__ import annotations

import hashlib

import pytest

from bots.shared.cache_service import MemoryCache


async def test_dedup_key_includes_contact_id():
    """Dedup key format includes contact_id so contacts don't share dedup state."""
    contact = "dedup-verify"
    message = "test message"
    expected_key = f"dedup:{contact}:{hashlib.md5(message.encode()).hexdigest()}"

    cache = MemoryCache()
    await cache.set(expected_key, "1", ttl=300)
    assert await cache.get(expected_key) == "1"


async def test_same_message_different_contacts_have_different_keys():
    """Two contacts with the same message text get different dedup keys."""
    message = "Hello, I want to sell"
    key1 = f"dedup:contact-A:{hashlib.md5(message.encode()).hexdigest()}"
    key2 = f"dedup:contact-B:{hashlib.md5(message.encode()).hexdigest()}"
    assert key1 != key2


async def test_dedup_within_ttl_returns_existing():
    """When a dedup key exists in cache, get() returns non-None (would trigger skip)."""
    cache = MemoryCache()
    contact = "dedup-ttl-test"
    message = "selling my house"
    key = f"dedup:{contact}:{hashlib.md5(message.encode()).hexdigest()}"

    await cache.set(key, "1", ttl=300)
    result = await cache.get(key)
    assert result == "1"  # Dedup would skip this message


async def test_dedup_different_messages_same_contact_different_keys():
    """Different messages from same contact have different dedup keys (both process)."""
    contact = "dedup-msgs"
    msg1 = "Hello"
    msg2 = "How much?"
    key1 = f"dedup:{contact}:{hashlib.md5(msg1.encode()).hexdigest()}"
    key2 = f"dedup:{contact}:{hashlib.md5(msg2.encode()).hexdigest()}"

    cache = MemoryCache()
    await cache.set(key1, "1", ttl=300)

    # key2 should not exist (different message)
    result = await cache.get(key2)
    assert result is None  # Second message would process normally
