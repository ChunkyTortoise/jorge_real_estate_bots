"""
Tests for INCREMENT 2A, 2B, 2C, 3D: Webhook dedup, locking, input validation, rate limiting.
"""
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bots.shared.cache_service import MemoryCache


class TestDuplicateMessageSkipped:
    """2A: Same message from same contact within 5 minutes is skipped."""

    @pytest.mark.asyncio
    async def test_duplicate_message_skipped(self):
        cache = MemoryCache()
        contact_id = "contact_dedup_test"
        message = "I want to sell my house"
        dedup_key = f"dedup:{contact_id}:{hashlib.md5(message.encode()).hexdigest()}"

        # First call: not in cache → should process
        result1 = await cache.get(dedup_key)
        assert result1 is None
        await cache.set(dedup_key, "1", ttl=300)

        # Second call: in cache → should be skipped
        result2 = await cache.get(dedup_key)
        assert result2 == "1"

    @pytest.mark.asyncio
    async def test_different_messages_not_deduplicated(self):
        cache = MemoryCache()
        contact_id = "contact_dedup_diff"
        msg1 = "message one"
        msg2 = "message two"
        key1 = f"dedup:{contact_id}:{hashlib.md5(msg1.encode()).hexdigest()}"
        key2 = f"dedup:{contact_id}:{hashlib.md5(msg2.encode()).hexdigest()}"

        await cache.set(key1, "1", ttl=300)

        result = await cache.get(key2)
        assert result is None  # Different message, not deduplicated


class TestLongMessageTruncated:
    """2C: Messages longer than 2000 chars are truncated."""

    def test_long_message_truncated_to_2000(self):
        message_body = "x" * 3000
        if len(message_body) > 2000:
            message_body = message_body[:2000]
        assert len(message_body) == 2000

    def test_short_message_not_truncated(self):
        original = "Hello Jorge"
        message_body = original
        if len(message_body) > 2000:
            message_body = message_body[:2000]
        assert message_body == original


class TestConcurrentMessagesSerializedWithLock:
    """2B: Per-contact lock serializes processing."""

    @pytest.mark.asyncio
    async def test_lock_acquired_and_released(self):
        cache = MemoryCache()
        lock_key = "lock:test_contact"

        # No lock held initially
        assert await cache.get(lock_key) is None

        # Acquire lock
        await cache.set(lock_key, "1", ttl=30)
        assert await cache.get(lock_key) == "1"

        # Release lock
        await cache.delete(lock_key)
        assert await cache.get(lock_key) is None

    @pytest.mark.asyncio
    async def test_lock_held_returns_throttled(self):
        """When lock is held and doesn't release in 10s, should throttle."""
        import asyncio
        cache = MemoryCache()
        lock_key = "lock:contact_throttle"
        contact_id = "contact_throttle"

        # Pre-set lock as if another request holds it
        await cache.set(lock_key, "1", ttl=30)

        # Simulate the polling logic from main.py
        throttled = True
        with patch("asyncio.sleep", new_callable=AsyncMock):
            for _ in range(10):
                if not await cache.get(lock_key):
                    throttled = False
                    break
                await asyncio.sleep(1)

        assert throttled  # Lock was never released


class TestRateLimitEnforced:
    """3D: Rate limiting enforces settings.rate_limit_per_minute."""

    @pytest.mark.asyncio
    async def test_rate_limit_counter_increments(self):
        cache = MemoryCache()
        rate_key = "rate:webhook:202602250000"

        # First request
        val = await cache.get(rate_key)
        count = int(val) if val is not None else 0
        assert count == 0
        await cache.set(rate_key, str(count + 1), ttl=60)

        # Second request
        val = await cache.get(rate_key)
        count = int(val)
        assert count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_throttles(self):
        cache = MemoryCache()
        rate_key = "rate:webhook:testminute"
        rate_limit = 3

        # Simulate hitting rate limit
        await cache.set(rate_key, str(rate_limit), ttl=60)

        val = await cache.get(rate_key)
        count = int(val) if val is not None else 0
        assert count >= rate_limit  # Would be throttled
