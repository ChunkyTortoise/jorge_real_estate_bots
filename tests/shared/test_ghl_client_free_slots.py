"""
Unit tests for GHLClient.get_free_slots().

Covers: success path, API error, exception, business-hours filter, 3-slot cap.
Tests use the real GHL response format: {"date": {"slots": ["ISO-string", ...]}}
"""
from unittest.mock import AsyncMock, patch

import pytest

from bots.shared.ghl_client import GHLClient


@pytest.fixture
def ghl_client():
    with patch.object(GHLClient, "__init__", lambda self, *a, **kw: None):
        client = GHLClient.__new__(GHLClient)
        client.api_key = "test-key"
        client.location_id = "loc-123"
        client.headers = {}
        client._client = None
    return client


def _make_success_response(dates_data: dict) -> dict:
    """Wrap date->slots data as _make_request would."""
    return {"success": True, "data": dates_data}


# Business-hour slots in PT (GHL returns local timezone)
SLOT_9AM = "2026-03-01T09:00:00-08:00"
SLOT_2PM = "2026-03-01T14:00:00-08:00"
SLOT_4PM = "2026-03-01T16:00:00-08:00"
SLOT_6AM = "2026-03-01T06:00:00-08:00"  # outside 9am-5pm


@pytest.mark.asyncio
async def test_get_free_slots_success(ghl_client):
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response(
            {"2026-03-01": {"slots": [SLOT_9AM, SLOT_2PM]}}
        )
    )

    slots = await ghl_client.get_free_slots("cal-123")

    assert len(slots) == 2
    assert slots[0]["start"] == SLOT_9AM
    assert slots[1]["start"] == SLOT_2PM


@pytest.mark.asyncio
async def test_get_free_slots_returns_empty_on_api_error(ghl_client):
    ghl_client._make_request = AsyncMock(
        return_value={"success": False, "error": "Not found"}
    )

    slots = await ghl_client.get_free_slots("cal-123")

    assert slots == []


@pytest.mark.asyncio
async def test_get_free_slots_returns_empty_on_exception(ghl_client):
    ghl_client._make_request = AsyncMock(side_effect=RuntimeError("network error"))

    slots = await ghl_client.get_free_slots("cal-123")

    assert slots == []


@pytest.mark.asyncio
async def test_get_free_slots_caps_at_three(ghl_client):
    many_slots = [f"2026-03-01T{9 + i}:00:00-08:00" for i in range(6)]
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response({"2026-03-01": {"slots": many_slots}})
    )

    slots = await ghl_client.get_free_slots("cal-123")

    assert len(slots) == 3


@pytest.mark.asyncio
async def test_get_free_slots_filters_outside_business_hours(ghl_client):
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response(
            {"2026-03-01": {"slots": [SLOT_6AM, SLOT_9AM]}}
        )
    )

    slots = await ghl_client.get_free_slots("cal-123")

    # Should include 9am but not 6am
    assert len(slots) == 1
    assert slots[0]["start"] == SLOT_9AM


@pytest.mark.asyncio
async def test_get_free_slots_handles_dict_slots(ghl_client):
    """Backward compat: slots can also be dicts with startTime/endTime."""
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response(
            {"2026-03-01": {"slots": [
                {"startTime": "2026-03-01T10:00:00-08:00", "endTime": "2026-03-01T10:30:00-08:00"},
            ]}}
        )
    )

    slots = await ghl_client.get_free_slots("cal-123")

    assert len(slots) == 1
    assert slots[0]["start"] == "2026-03-01T10:00:00-08:00"
    assert slots[0]["end"] == "2026-03-01T10:30:00-08:00"
