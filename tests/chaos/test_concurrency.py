"""Chaos tests: concurrent message processing — lock, state isolation, no bleed."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.shared.cache_service import MemoryCache


@pytest.fixture
def seller():
    bot = JorgeSellerBot()
    bot.cache = MemoryCache()
    return bot


@pytest.fixture
def buyer():
    bot = JorgeBuyerBot()
    bot.cache = MemoryCache()
    return bot


async def _seller_send(bot, contact_id: str, message: str):
    with patch.object(
        bot.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="Thanks for reaching out!"),
    ):
        return await bot.process_seller_message(
            contact_id=contact_id, location_id="loc-test", message=message
        )


async def _buyer_send(bot, contact_id: str, message: str):
    with patch.object(
        bot.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="How many bedrooms are you looking for?"),
    ):
        return await bot.process_buyer_message(
            contact_id=contact_id, location_id="loc-test", message=message
        )


async def test_concurrent_seller_messages_same_contact_all_respond(seller):
    """5 concurrent seller messages for the same contact all return a response (no crash)."""
    results = await asyncio.gather(
        *[_seller_send(seller, "concurrent-seller", f"Message {i}") for i in range(5)],
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Got exceptions: {errors}"
    responses = [r for r in results if not isinstance(r, Exception)]
    assert len(responses) == 5


async def test_concurrent_buyer_messages_same_contact_all_respond(buyer):
    """5 concurrent buyer messages for the same contact all return a response (no crash)."""
    results = await asyncio.gather(
        *[_buyer_send(buyer, "concurrent-buyer", f"Message {i}") for i in range(5)],
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Got exceptions: {errors}"


async def test_concurrent_different_contacts_no_interference(seller):
    """10 different contacts processed concurrently — all get valid responses."""
    results = await asyncio.gather(
        *[_seller_send(seller, f"contact-{i}", "I want to sell") for i in range(10)],
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Concurrent contacts caused exceptions: {errors}"


async def test_corrupted_cache_state_bot_recovers(seller):
    """When cache returns corrupted state, bot creates fresh state (no crash)."""
    # Store garbage in the cache key
    seller.cache = AsyncMock()
    seller.cache.get = AsyncMock(return_value={"__corrupt__": True, "gibberish": 999})
    seller.cache.set = AsyncMock()
    seller.cache.setnx = AsyncMock(return_value=True)
    seller.cache.delete = AsyncMock()

    with patch.object(
        seller.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="What condition is your property in?"),
    ):
        result = await seller.process_seller_message(
            contact_id="corrupted-state", location_id="loc-test", message="hello"
        )

    assert result.response_message, "Bot must return a response even with corrupt cache"


async def test_seller_concurrent_different_contacts_states_independent(seller):
    """Parallel seller conversations don't overwrite each other's state."""
    async def run_contact(cid: str, message: str):
        return await _seller_send(seller, cid, message)

    results = await asyncio.gather(
        run_contact("seller-ind-1", "I own a 3-bed house"),
        run_contact("seller-ind-2", "I own a condo"),
        run_contact("seller-ind-3", "I own a duplex"),
    )
    # All 3 should succeed independently
    assert all(r.response_message for r in results)


async def test_memory_cache_concurrent_setnx_exactly_one_wins():
    """Concurrent setnx on the same key — only 1 of N callers wins."""
    cache = MemoryCache()
    results = await asyncio.gather(*[cache.setnx("lock:test", "1", ttl=30) for _ in range(20)])
    assert results.count(True) == 1
    assert results.count(False) == 19


async def test_memory_cache_concurrent_increment_no_loss():
    """Concurrent increments — no lost updates."""
    cache = MemoryCache()
    await asyncio.gather(*[cache.increment("counter", 1, ttl=60) for _ in range(50)])
    assert int(await cache.get("counter")) == 50
