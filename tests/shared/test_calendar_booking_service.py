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
async def test_offer_slots_formats_numbered_options(service):
    service.ghl_client.get_free_slots = AsyncMock(return_value=SAMPLE_SLOTS)

    result = await service.offer_appointment_slots("contact-1", "seller")

    assert result["fallback"] is False
    assert len(result["slots"]) == 3
    msg = result["message"]
    assert "1." in msg
    assert "2." in msg
    assert "3." in msg
    assert "reply with the number" in msg.lower()


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
        ("3", 2),
        ("  2  ", 1),
        ("slot 1", 0),
        ("slot 3", 2),
        ("#2", 1),
        ("option 1", 0),
        ("SLOT 2", 1),
    ],
)
def test_detect_slot_selection_valid(message, expected):
    assert CalendarBookingService.detect_slot_selection(message) == expected


@pytest.mark.parametrize(
    "message",
    ["yes", "no", "hello", "4", "0", "maybe tomorrow", "what times?"],
)
def test_detect_slot_selection_no_match(message):
    assert CalendarBookingService.detect_slot_selection(message) is None


# ─────────────────────────────────────────────────────────────────────────────
# has_pending_slots
# ─────────────────────────────────────────────────────────────────────────────

def test_has_pending_slots_false_when_empty(service):
    assert not service.has_pending_slots("contact-x")


def test_has_pending_slots_true_after_caching(service):
    service._pending_slots["contact-x"] = SAMPLE_SLOTS
    assert service.has_pending_slots("contact-x")
