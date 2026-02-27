"""
Integration tests for buyer bot calendar scheduling.

Covers: HOT gets slot offer, slot reply books appointment, WARM gets fallback,
        COLD gets nothing, booking failure message, no double-offer.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.buyer_bot.buyer_bot import BuyerQualificationState, BuyerStatus, JorgeBuyerBot


@pytest.fixture
def mock_ghl():
    client = MagicMock()
    client.location_id = "loc-123"
    client.add_tag = AsyncMock(return_value=True)
    client.remove_tag = AsyncMock(return_value=True)
    client.update_custom_field = AsyncMock(return_value=True)
    client.trigger_workflow = AsyncMock(return_value={"success": True})
    client.create_opportunity = AsyncMock(return_value={"success": True})
    client.get_free_slots = AsyncMock(return_value=[
        {"start": "2026-03-01T17:00:00Z", "end": "2026-03-01T17:30:00Z"},
        {"start": "2026-03-03T22:00:00Z", "end": "2026-03-03T22:30:00Z"},
    ])
    client.create_appointment = AsyncMock(
        return_value={"success": True, "data": {"id": "appt-77"}}
    )
    return client


@pytest.fixture
def bot(mock_ghl):
    with patch("bots.shared.calendar_booking_service.settings") as mock_settings:
        mock_settings.jorge_calendar_id = "cal-abc"
        mock_settings.jorge_user_id = "user-xyz"
        b = JorgeBuyerBot(ghl_client=mock_ghl)
    return b


def _hot_state(contact_id: str = "contact-buyer") -> BuyerQualificationState:
    return BuyerQualificationState(
        contact_id=contact_id,
        location_id="loc-123",
        questions_answered=4,
        current_question=4,
        stage="QUALIFIED",
        is_qualified=True,
        preapproved=True,
        timeline_days=14,  # <= 30 → HOT
    )


def _warm_state(contact_id: str = "contact-buyer") -> BuyerQualificationState:
    return BuyerQualificationState(
        contact_id=contact_id,
        location_id="loc-123",
        questions_answered=4,
        current_question=4,
        stage="QUALIFIED",
        is_qualified=True,
        preapproved=True,
        timeline_days=60,  # 30 < 60 <= 90 → WARM
    )


@pytest.mark.asyncio
async def test_hot_buyer_gets_slot_offer(bot, mock_ghl):
    state = _hot_state()
    assert bot._calculate_temperature(state) == BuyerStatus.HOT

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "_generate_response", AsyncMock(return_value={
            "message": "Great, let's find you a home!",
            "extracted_data": {},
            "should_advance": False,
        })),
        patch.object(bot, "save_conversation_state", AsyncMock()),
        patch.object(bot, "_match_properties", AsyncMock(return_value=[])),
    ):
        result = await bot.process_buyer_message("contact-buyer", "loc-123", "I'm ready")

    assert "1." in result.response_message or "reply with the number" in result.response_message.lower()
    assert state.scheduling_offered is True


@pytest.mark.asyncio
async def test_warm_buyer_gets_fallback_text(bot, mock_ghl):
    state = _warm_state()
    assert bot._calculate_temperature(state) == BuyerStatus.WARM

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "_generate_response", AsyncMock(return_value={
            "message": "Let's keep in touch.",
            "extracted_data": {},
            "should_advance": False,
        })),
        patch.object(bot, "save_conversation_state", AsyncMock()),
        patch.object(bot, "_match_properties", AsyncMock(return_value=[])),
    ):
        result = await bot.process_buyer_message("contact-buyer", "loc-123", "okay")

    assert "morning or afternoon" in result.response_message.lower()
    assert state.scheduling_offered is True


@pytest.mark.asyncio
async def test_cold_buyer_gets_no_scheduling(bot):
    state = BuyerQualificationState(
        contact_id="contact-cold",
        location_id="loc-123",
        questions_answered=1,
        timeline_days=200,  # COLD
    )
    assert bot._calculate_temperature(state) == BuyerStatus.COLD

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "_generate_response", AsyncMock(return_value={
            "message": "What are you looking for?",
            "extracted_data": {},
            "should_advance": False,
        })),
        patch.object(bot, "save_conversation_state", AsyncMock()),
        patch.object(bot, "_match_properties", AsyncMock(return_value=[])),
    ):
        result = await bot.process_buyer_message("contact-cold", "loc-123", "hi")

    assert "morning or afternoon" not in result.response_message.lower()
    assert "reply with the number" not in result.response_message.lower()
    assert state.scheduling_offered is False


@pytest.mark.asyncio
async def test_slot_reply_books_buyer_appointment(bot, mock_ghl):
    state = _hot_state()
    state.scheduling_offered = True
    bot.calendar_service._pending_slots["contact-buyer"] = [
        {"start": "2026-03-01T17:00:00Z", "end": "2026-03-01T17:30:00Z"},
    ]

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "save_conversation_state", AsyncMock()),
    ):
        result = await bot.process_buyer_message("contact-buyer", "loc-123", "1")

    assert "booked" in result.response_message.lower()
    assert state.appointment_booked is True
    assert state.appointment_id == "appt-77"


@pytest.mark.asyncio
async def test_buyer_booking_failure_gives_retry_message(bot, mock_ghl):
    state = _hot_state()
    state.scheduling_offered = True
    bot.calendar_service._pending_slots["contact-buyer"] = [
        {"start": "2026-03-01T17:00:00Z", "end": "2026-03-01T17:30:00Z"},
    ]
    mock_ghl.create_appointment = AsyncMock(
        return_value={"success": False, "error": "unavailable"}
    )

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "save_conversation_state", AsyncMock()),
    ):
        result = await bot.process_buyer_message("contact-buyer", "loc-123", "1")

    assert "wasn't able to book" in result.response_message.lower()
    assert state.appointment_booked is False


@pytest.mark.asyncio
async def test_buyer_scheduling_offered_only_once(bot, mock_ghl):
    state = _hot_state()
    state.scheduling_offered = True  # Already offered

    get_free_slots_calls = 0

    async def count_calls(cal_id):
        nonlocal get_free_slots_calls
        get_free_slots_calls += 1
        return []

    bot.calendar_service.ghl_client.get_free_slots = count_calls

    with (
        patch.object(bot, "_get_or_create_state", AsyncMock(return_value=state)),
        patch.object(bot, "_generate_response", AsyncMock(return_value={
            "message": "Keep in touch!",
            "extracted_data": {},
            "should_advance": False,
        })),
        patch.object(bot, "save_conversation_state", AsyncMock()),
        patch.object(bot, "_match_properties", AsyncMock(return_value=[])),
    ):
        await bot.process_buyer_message("contact-buyer", "loc-123", "something else")

    assert get_free_slots_calls == 0
