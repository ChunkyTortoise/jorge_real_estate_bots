"""Chaos tests: Claude API failure scenarios — timeouts, 500s, rate limits."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.buyer_bot.buyer_bot import JorgeBuyerBot


@pytest.fixture
def seller():
    return JorgeSellerBot()


@pytest.fixture
def buyer():
    return JorgeBuyerBot()


async def test_seller_fallback_on_claude_timeout(seller):
    """When Claude times out, seller bot returns a graceful fallback message."""
    with patch.object(
        seller.claude_client,
        "agenerate",
        side_effect=asyncio.TimeoutError("Claude timeout"),
    ):
        result = await seller.process_seller_message(
            contact_id="claude-timeout-seller", location_id="loc-test",
            message="I want to sell my house"
        )
    assert result.response_message, "Must return fallback message on timeout"
    assert isinstance(result.response_message, str)


async def test_seller_fallback_on_claude_500(seller):
    """When Claude returns a 500 error, seller bot returns a graceful fallback."""
    with patch.object(
        seller.claude_client,
        "agenerate",
        side_effect=Exception("Claude API 500: Internal Server Error"),
    ):
        result = await seller.process_seller_message(
            contact_id="claude-500-seller", location_id="loc-test",
            message="I want to sell"
        )
    assert result.response_message, "Must return fallback message on 500"


async def test_buyer_fallback_on_claude_timeout(buyer):
    """When Claude times out, buyer bot returns a graceful fallback message."""
    with patch.object(
        buyer.claude_client,
        "agenerate",
        side_effect=asyncio.TimeoutError("Claude timeout"),
    ):
        result = await buyer.process_buyer_message(
            contact_id="claude-timeout-buyer", location_id="loc-test",
            message="I want to buy a house"
        )
    assert result.response_message, "Must return fallback message on timeout"


async def test_buyer_fallback_on_claude_500(buyer):
    """When Claude returns 500, buyer bot returns a graceful fallback."""
    with patch.object(
        buyer.claude_client,
        "agenerate",
        side_effect=Exception("HTTP 500"),
    ):
        result = await buyer.process_buyer_message(
            contact_id="claude-500-buyer", location_id="loc-test",
            message="Looking for a home"
        )
    assert result.response_message


async def test_price_extraction_returns_none_not_300k_on_haiku_error(seller):
    """When Haiku fails during price extraction, result is None (not $300k)."""
    with patch.object(
        seller.claude_client,
        "agenerate",
        side_effect=Exception("Haiku API error"),
    ):
        extracted = await seller._extract_qualification_data("around market value", 2)
    assert extracted.get("price_expectation") is None


async def test_seller_response_not_empty_on_consecutive_failures(seller):
    """Seller bot recovers after multiple consecutive Claude failures."""
    for i in range(3):
        with patch.object(
            seller.claude_client,
            "agenerate",
            side_effect=Exception(f"failure {i}"),
        ):
            result = await seller.process_seller_message(
                contact_id=f"consecutive-fail-{i}", location_id="loc-test",
                message="Hello"
            )
        assert result.response_message, f"Iteration {i} returned empty response"


async def test_seller_claude_rate_limit_returns_graceful_message(seller):
    """Seller bot handles rate limit (429-like) exception gracefully."""
    with patch.object(
        seller.claude_client,
        "agenerate",
        side_effect=Exception("rate_limit_error: Too many requests"),
    ):
        result = await seller.process_seller_message(
            contact_id="rate-limited", location_id="loc-test",
            message="I want to sell"
        )
    assert result.response_message
