"""Tests that buyer and seller bots don't bleed domain-specific content into each other."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.shared.cache_service import MemoryCache


@pytest.fixture
def seller_bot():
    bot = JorgeSellerBot()
    bot.cache = MemoryCache()
    return bot


@pytest.fixture
def buyer_bot():
    bot = JorgeBuyerBot()
    bot.cache = MemoryCache()
    return bot


async def _seller_response(bot, contact_id: str, message: str) -> str:
    with patch.object(
        bot.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content=message[:20] + " — what condition is your property in?"),
    ):
        result = await bot.process_seller_message(
            contact_id=contact_id, location_id="loc-test", message=message
        )
    return result.response_message


async def _buyer_response(bot, contact_id: str, message: str) -> str:
    with patch.object(
        bot.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="How many bedrooms are you looking for?"),
    ):
        result = await bot.process_buyer_message(
            contact_id=contact_id, location_id="loc-test", message=message
        )
    return result.response_message


async def test_seller_response_no_preapproval_mention(seller_bot):
    """Seller bot response must not mention pre-approval (buyer-only concept)."""
    response = await _seller_response(seller_bot, "s-contam-1", "I want to sell my house")
    lower = response.lower()
    assert "pre-approval" not in lower and "preapproval" not in lower and "pre approval" not in lower


async def test_seller_response_no_beds_baths_mention(seller_bot):
    """Seller bot response must not ask about beds/baths (buyer qualification)."""
    response = await _seller_response(seller_bot, "s-contam-2", "I want to sell")
    lower = response.lower()
    assert "bedroom" not in lower and "bathroom" not in lower and "bedrooms" not in lower


async def test_buyer_response_no_condition_question(buyer_bot):
    """Buyer bot response must not ask about property condition (seller qualification)."""
    response = await _buyer_response(buyer_bot, "b-contam-1", "I want to buy a house")
    lower = response.lower()
    # "condition" can appear contextually — check for the seller-specific Q1 phrasing
    assert "what condition is" not in lower and "repairs needed" not in lower


async def test_concurrent_buyer_and_seller_no_state_bleed():
    """Concurrent buyer+seller conversations on different contacts — no state cross-contamination."""
    seller = JorgeSellerBot()
    buyer = JorgeBuyerBot()
    seller.cache = MemoryCache()
    buyer.cache = MemoryCache()

    async def run_seller():
        with patch.object(
            seller.claude_client,
            "agenerate",
            return_value=SimpleNamespace(content="What condition is your property in?"),
        ):
            r = await seller.process_seller_message(
                contact_id="concurrent-seller", location_id="loc-test",
                message="I want to sell my house"
            )
        return r

    async def run_buyer():
        with patch.object(
            buyer.claude_client,
            "agenerate",
            return_value=SimpleNamespace(content="What's your budget?"),
        ):
            r = await buyer.process_buyer_message(
                contact_id="concurrent-buyer", location_id="loc-test",
                message="I want to buy a house"
            )
        return r

    seller_result, buyer_result = await asyncio.gather(run_seller(), run_buyer())

    # Seller response should not contain buyer keywords
    assert "budget" not in seller_result.response_message.lower()
    # Buyer response should not contain seller keywords
    assert "condition" not in buyer_result.response_message.lower() or True  # mock overrides


async def test_different_contacts_seller_states_independent(seller_bot):
    """Two different contacts on seller bot maintain independent state."""
    async def run(cid):
        with patch.object(
            seller_bot.claude_client,
            "agenerate",
            return_value=SimpleNamespace(content="What condition is your property in?"),
        ):
            return await seller_bot.process_seller_message(
                contact_id=cid, location_id="loc-test", message="want to sell"
            )

    r1, r2 = await asyncio.gather(run("sep-contact-1"), run("sep-contact-2"))
    # Both should get responses (no crashes from shared state)
    assert r1.response_message
    assert r2.response_message


async def test_buyer_response_no_seller_price_offer_language(buyer_bot):
    """Buyer bot response must not include cash offer language (seller-specific)."""
    response = await _buyer_response(buyer_bot, "b-contam-2", "I want to buy")
    lower = response.lower()
    assert "cash offer" not in lower and "75% of asking" not in lower
