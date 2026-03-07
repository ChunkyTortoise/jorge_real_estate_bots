"""
Tests for buyer → seller intent detection and auto-handoff (F4).

Covers: early switch (Q0-Q1), mid-flow tag (Q2+), no false positives,
        pattern matching, cache operations.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.buyer_bot.buyer_bot import (
    BuyerQualificationState,
    JorgeBuyerBot,
    _has_seller_intent,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pattern unit tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "I want to sell my house",
    "need to sell my home",
    "I'm selling my property",
    "sell my place fast",
    "list my property",
    "WANT TO SELL my house",  # case insensitive
])
def test_seller_intent_detected(msg):
    assert _has_seller_intent(msg) is True


@pytest.mark.parametrize("msg", [
    "I want to buy a house",
    "looking for a home to purchase",
    "need 3 beds and 2 baths",
    "preapproved for $450k",
    "moving to Rancho Cucamonga",
    "sell me on this neighborhood",  # "sell" but not "sell my X"
])
def test_no_false_positives(msg):
    assert _has_seller_intent(msg) is False


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ghl():
    client = MagicMock()
    client.location_id = "loc-123"
    client.add_tag = AsyncMock(return_value=True)
    client.get_contact = AsyncMock(return_value={"tags": []})
    client.update_custom_field = AsyncMock(return_value=True)
    client.trigger_workflow = AsyncMock(return_value={"success": True})
    client.create_opportunity = AsyncMock(return_value={"success": True})
    client.get_free_slots = AsyncMock(return_value=[])
    client.create_appointment = AsyncMock(return_value={"success": False})
    return client


@pytest.fixture
def bot(mock_ghl):
    with patch("bots.shared.calendar_booking_service.settings") as ms:
        ms.jorge_calendar_id = ""
        ms.jorge_user_id = ""
        b = JorgeBuyerBot(ghl_client=mock_ghl)
    return b


def _early_state(contact_id: str = "c-1") -> BuyerQualificationState:
    return BuyerQualificationState(
        contact_id=contact_id,
        location_id="loc-123",
        current_question=1,
        questions_answered=0,
    )


def _mid_state(contact_id: str = "c-1") -> BuyerQualificationState:
    return BuyerQualificationState(
        contact_id=contact_id,
        location_id="loc-123",
        current_question=2,
        questions_answered=1,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Early switch (Q0-Q1)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_early_seller_intent_switches_bot(bot):
    state = _early_state()

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot.cache, "delete", AsyncMock()),
        patch.object(bot.cache, "set", AsyncMock()),
    ):
        result = await bot.process_buyer_message("c-1", "loc-123", "I want to sell my house")

    assert result.buyer_temperature == "cold"
    assert result.next_steps == "Switched to seller bot"
    assert any(a.get("tag") == "buyer-to-seller-handoff" for a in result.actions_taken)
    assert "sell" in result.response_message.lower()


@pytest.mark.asyncio
async def test_early_switch_purges_buyer_state(bot):
    state = _early_state()
    deleted_keys = []
    set_keys = {}

    async def mock_delete(key):
        deleted_keys.append(key)

    async def mock_set(key, val, **kw):
        set_keys[key] = val

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot.cache, "delete", mock_delete),
        patch.object(bot.cache, "set", mock_set),
    ):
        await bot.process_buyer_message("c-1", "loc-123", "need to sell my home")

    assert "buyer:state:c-1" in deleted_keys
    assert set_keys.get("conversation:mode:c-1") == "seller"
    assert set_keys.get("assigned_bot:c-1") == "seller"


@pytest.mark.asyncio
async def test_early_switch_at_q0(bot):
    """Q0 (initial message) also triggers early switch."""
    state = BuyerQualificationState(
        contact_id="c-q0",
        location_id="loc-123",
        current_question=0,
        questions_answered=0,
    )

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot.cache, "delete", AsyncMock()),
        patch.object(bot.cache, "set", AsyncMock()),
    ):
        result = await bot.process_buyer_message("c-q0", "loc-123", "I'm selling my property")

    assert result.next_steps == "Switched to seller bot"


# ─────────────────────────────────────────────────────────────────────────────
# Mid-flow tag (Q2+) — don't interrupt, just tag
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mid_flow_seller_intent_tags_and_continues(bot, mock_ghl):
    state = _mid_state()

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "_generate_response", AsyncMock(return_value={
            "message": "Are you pre-approved?",
            "extracted_data": {"preapproved": False},
            "should_advance": True,
        })),
        patch.object(bot, "save_conversation_state", AsyncMock()),
        patch.object(bot, "_match_properties", AsyncMock(return_value=[])),
    ):
        result = await bot.process_buyer_message(
            "c-1", "loc-123", "I want to sell my house too but mostly buying"
        )

    # Bot continues buyer flow
    assert result.buyer_temperature in ("cold", "warm", "hot")
    # Tag applied via GHL client
    mock_ghl.add_tag.assert_called_once_with("c-1", "needs-seller-consult")


@pytest.mark.asyncio
async def test_mid_flow_does_not_switch_bot(bot, mock_ghl):
    """At Q2+, intent is noted but bot assignment is NOT changed."""
    state = _mid_state()
    set_calls = {}

    async def mock_set(key, val, **kw):
        set_calls[key] = val

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "_generate_response", AsyncMock(return_value={
            "message": "Got it.",
            "extracted_data": {"preapproved": True},
            "should_advance": True,
        })),
        patch.object(bot, "save_conversation_state", AsyncMock()),
        patch.object(bot, "_match_properties", AsyncMock(return_value=[])),
        patch.object(bot.cache, "set", mock_set),
    ):
        await bot.process_buyer_message(
            "c-1", "loc-123", "need to sell my home but also buying"
        )

    assert set_calls.get("assigned_bot:c-1") != "seller"
