"""
Unit tests for CalendarBookingService.

~15 tests covering: slot offering, booking, slot detection, fallback, formatting.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.shared.calendar_booking_service import (
    FALLBACK_MESSAGE,
    CalendarBookingService,
)


@pytest.fixture
def mock_ghl_client():
    client = MagicMock()
    client.location_id = "loc-123"
    client.get_free_slots = AsyncMock(return_value=[])
    client.create_appointment = AsyncMock(return_value={"success": False})
    return client


@pytest.fixture
def service(mock_ghl_client):
    with patch(
        "bots.shared.calendar_booking_service.settings"
    ) as mock_settings:
        mock_settings.jorge_calendar_id = "cal-abc"
        mock_settings.jorge_user_id = "user-xyz"
        svc = CalendarBookingService(mock_ghl_client)
    return svc


@pytest.fixture
def service_no_calendar(mock_ghl_client):
    with patch(
        "bots.shared.calendar_booking_service.settings"
    ) as mock_settings:
        mock_settings.jorge_calendar_id = ""
        mock_settings.jorge_user_id = ""
        svc = CalendarBookingService(mock_ghl_client)
    return svc


SAMPLE_SLOTS = [
    {"start": "2026-03-01T17:00:00Z", "end": "2026-03-01T17:30:00Z"},  # 9am PT
    {"start": "2026-03-03T22:00:00Z", "end": "2026-03-03T22:30:00Z"},  # 2pm PT
    {"start": "2026-03-04T19:00:00Z", "end": "2026-03-04T19:30:00Z"},  # 11am PT
]


# ─────────────────────────────────────────────────────────────────────────────
# offer_appointment_slots
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_offer_slots_returns_fallback_when_no_calendar_id(service_no_calendar):
    result = await service_no_calendar.offer_appointment_slots("contact-1", "seller")

    assert result["fallback"] is True
    assert result["slots"] == []
    assert FALLBACK_MESSAGE in result["message"]


@pytest.mark.asyncio
async def test_offer_slots_returns_fallback_when_api_returns_empty(service):
    service.ghl_client.get_free_slots = AsyncMock(return_value=[])

    result = await service.offer_appointment_slots("contact-1", "seller")

    assert result["fallback"] is True
    assert result["slots"] == []
    assert FALLBACK_MESSAGE in result["message"]


@pytest.mark.asyncio
async def test_offer_slots_returns_fallback_on_api_exception(service):
    service.ghl_client.get_free_slots = AsyncMock(side_effect=RuntimeError("network"))

    result = await service.offer_appointment_slots("contact-1", "seller")

    assert result["fallback"] is True
    assert result["slots"] == []


@pytest.mark.asyncio
async def test_offer_slots_formats_prose_options(service):
    service.ghl_client.get_free_slots = AsyncMock(return_value=SAMPLE_SLOTS)

    result = await service.offer_appointment_slots("contact-1", "seller")

    assert result["fallback"] is False
    # Only 2 slots offered (prose format works best with 2)
    assert len(result["slots"]) == 2
    msg = result["message"]
    assert " or " in msg
    assert "open" in msg
    assert "1." not in msg
    assert "reply with the number" not in msg.lower()


@pytest.mark.asyncio
async def test_offer_slots_caches_pending(service):
    service.ghl_client.get_free_slots = AsyncMock(return_value=SAMPLE_SLOTS)

    await service.offer_appointment_slots("contact-1", "seller")

    assert service.has_pending_slots("contact-1")


# ─────────────────────────────────────────────────────────────────────────────
# book_appointment
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_book_appointment_success(service):
    service._pending_slots["contact-1"] = SAMPLE_SLOTS
    service.ghl_client.create_appointment = AsyncMock(
        return_value={"success": True, "data": {"id": "appt-99"}}
    )

    result = await service.book_appointment("contact-1", 1, "seller")

    assert result["success"] is True
    assert result["appointment"] == {"id": "appt-99"}
    assert "booked" in result["message"].lower()
    # Pending slots cleared after booking
    assert not service.has_pending_slots("contact-1")


@pytest.mark.asyncio
async def test_book_appointment_no_pending_slots(service):
    result = await service.book_appointment("contact-unknown", 0, "seller")

    assert result["success"] is False
    assert "No pending slots" in result["message"]


@pytest.mark.asyncio
async def test_book_appointment_invalid_index(service):
    service._pending_slots["contact-1"] = SAMPLE_SLOTS

    result = await service.book_appointment("contact-1", 5, "seller")

    assert result["success"] is False
    assert "valid option" in result["message"]


@pytest.mark.asyncio
async def test_book_appointment_api_failure(service):
    service._pending_slots["contact-1"] = SAMPLE_SLOTS
    service.ghl_client.create_appointment = AsyncMock(
        return_value={"success": False, "error": "timeout"}
    )

    result = await service.book_appointment("contact-1", 0, "seller")

    assert result["success"] is False
    assert "wasn't able to book" in result["message"]


@pytest.mark.asyncio
async def test_book_appointment_api_exception(service):
    service._pending_slots["contact-1"] = SAMPLE_SLOTS
    service.ghl_client.create_appointment = AsyncMock(side_effect=RuntimeError("boom"))

    result = await service.book_appointment("contact-1", 0, "seller")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_book_appointment_uses_lead_type_for_title(service):
    service._pending_slots["contact-buyer"] = SAMPLE_SLOTS
    captured: dict = {}

    async def capture(data):
        captured.update(data)
        return {"success": True, "data": {"id": "appt-1"}}

    service.ghl_client.create_appointment = capture

    await service.book_appointment("contact-buyer", 0, "buyer")
    assert captured.get("title") == "Buyer Consultation"


# ─────────────────────────────────────────────────────────────────────────────
# detect_slot_selection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "message, expected",
    [
        ("1", 0),
        ("2", 1),
        ("  2  ", 1),
        ("option 1", 0),
        # ordinal / positional
        ("first", 0),
        ("the first one", 0),
        ("second", 1),
        ("second works for me", 1),
        ("morning is better", 0),
        ("afternoon", 1),
        ("option 2", 1),
    ],
)
def test_detect_slot_selection_valid(service, message, expected):
    assert service.detect_slot_selection(message) == expected


@pytest.mark.parametrize(
    "message",
    ["yes", "no", "hello", "4", "0", "3", "maybe tomorrow", "what times?", "sure"],
)
def test_detect_slot_selection_no_match(service, message):
    assert service.detect_slot_selection(message) is None


def test_detect_slot_selection_display_text(service):
    """Day names in the reply match against pending slots."""
    service._pending_slots["contact-1"] = SAMPLE_SLOTS[:2]
    # SAMPLE_SLOTS[0] starts 2026-03-01 17:00Z → "Sunday, March 01 at 05:00 PM"
    # SAMPLE_SLOTS[1] starts 2026-03-03 22:00Z → "Tuesday, March 03 at 10:00 PM"
    assert service.detect_slot_selection("sunday works", "contact-1") == 0
    assert service.detect_slot_selection("let's do tuesday", "contact-1") == 1


def test_natural_language_slot_selection(service):
    """Full suite of natural-language selection patterns."""
    service._pending_slots["contact-nl"] = SAMPLE_SLOTS[:2]
    assert service.detect_slot_selection("the first one sounds good", "contact-nl") == 0
    assert service.detect_slot_selection("second works for me", "contact-nl") == 1
    assert service.detect_slot_selection("morning is better", "contact-nl") == 0
    assert service.detect_slot_selection("sure", "contact-nl") is None  # ambiguous → re-offer


# ─────────────────────────────────────────────────────────────────────────────
# has_pending_slots
# ─────────────────────────────────────────────────────────────────────────────

def test_has_pending_slots_false_when_empty(service):
    assert not service.has_pending_slots("contact-x")


def test_has_pending_slots_true_after_caching(service):
    service._pending_slots["contact-x"] = SAMPLE_SLOTS
    assert service.has_pending_slots("contact-x")
