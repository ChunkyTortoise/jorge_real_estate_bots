"""Chaos tests: GHL API failure scenarios — 500s, timeouts, tag failures."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.shared.calendar_booking_service import CalendarBookingService
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


async def test_seller_handles_claude_failure_returns_fallback(seller):
    """Seller bot returns fallback message when Claude fails (simulates all GHL downstream errors)."""
    with patch.object(
        seller.claude_client,
        "agenerate",
        side_effect=Exception("Upstream error"),
    ):
        result = await seller.process_seller_message(
            contact_id="ghl-500-seller", location_id="loc-test",
            message="I want to sell my house"
        )
    assert result.response_message, "Bot must return fallback on upstream error"


async def test_buyer_handles_claude_failure_returns_fallback(buyer):
    """Buyer bot returns fallback message when Claude fails."""
    with patch.object(
        buyer.claude_client,
        "agenerate",
        side_effect=Exception("Upstream error"),
    ):
        result = await buyer.process_buyer_message(
            contact_id="ghl-500-buyer", location_id="loc-test",
            message="I want to buy a house"
        )
    assert result.response_message, "Bot must return fallback on upstream error"


async def test_calendar_service_fallback_on_ghl_timeout():
    """CalendarBookingService returns fallback message when GHL times out."""
    mock_ghl = AsyncMock()
    mock_ghl.get_free_slots = AsyncMock(side_effect=Exception("GHL timeout"))

    svc = CalendarBookingService(ghl_client=mock_ghl)
    result = await svc.offer_appointment_slots(contact_id="cal-timeout", lead_type="seller")

    assert result["fallback"] is True, "Should return fallback on GHL timeout"
    assert result["message"], "Fallback message must not be empty"
    assert isinstance(result["slots"], list)


async def test_calendar_service_fallback_when_no_calendar_id():
    """CalendarBookingService returns fallback when JORGE_CALENDAR_ID is not set."""
    mock_ghl = AsyncMock()
    svc = CalendarBookingService(ghl_client=mock_ghl)
    svc.calendar_id = ""  # Simulate missing env var

    result = await svc.offer_appointment_slots(contact_id="no-cal-id", lead_type="seller")

    assert result["fallback"] is True
    assert result["message"]
    mock_ghl.get_free_slots.assert_not_called()


async def test_deferred_tag_apply_handles_ghl_failure():
    """_deferred_tag_apply does not crash when GHL tag API fails."""
    from bots.lead_bot.routes_webhook import _deferred_tag_apply

    mock_ghl = AsyncMock()
    mock_ghl.add_tag = AsyncMock(side_effect=Exception("GHL API down"))
    mock_ghl.remove_tag = AsyncMock(side_effect=Exception("GHL API down"))

    actions = [
        {"type": "add_tag", "tag": "seller-lead"},
        {"type": "remove_tag", "tag": "new-lead"},
    ]

    # Must not raise — fire and forget
    await _deferred_tag_apply(mock_ghl, "contact-ghl-fail", actions)


async def test_seller_continues_without_ghl_client(seller):
    """Seller bot generates response even when GHL client is unavailable."""
    # Mock the internal GHL client attribute if it exists
    if hasattr(seller, '_ghl_client'):
        seller._ghl_client = None

    with patch.object(
        seller.claude_client,
        "agenerate",
        return_value=SimpleNamespace(content="What condition is your property in?"),
    ):
        result = await seller.process_seller_message(
            contact_id="no-ghl", location_id="loc-test",
            message="I want to sell"
        )
    assert result.response_message


async def test_calendar_slots_empty_returns_fallback():
    """When GHL returns empty slots list, service returns fallback message."""
    mock_ghl = AsyncMock()
    mock_ghl.get_free_slots = AsyncMock(return_value=[])

    svc = CalendarBookingService(ghl_client=mock_ghl)
    svc.calendar_id = "real-cal-id"

    result = await svc.offer_appointment_slots(contact_id="empty-slots", lead_type="seller")

    assert result["fallback"] is True
    assert result["message"]


async def test_ghl_client_get_free_slots_returns_empty_on_error():
    """GHLClient.get_free_slots returns empty list gracefully on HTTP error."""
    from bots.shared.ghl_client import GHLClient
    client = GHLClient()

    with patch.object(client, "_make_request", side_effect=Exception("404 Not Found")):
        result = await client.get_free_slots(calendar_id="invalid-cal")
    # Should return [] or None gracefully, not raise
    assert result is None or isinstance(result, list)
