"""
Unit tests for GHLClient.get_free_slots().

Covers: success path, API error, exception, business-hours filter, 3-slot cap.
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


def _make_success_response(slots_by_date: dict) -> dict:
    return {"success": True, "data": {"slots": slots_by_date}}


# Business-hour slots (UTC for 9am-5pm PT = UTC+8 offset)
SLOT_9AM_PT = {"startTime": "2026-03-01T17:00:00Z", "endTime": "2026-03-01T17:30:00Z"}
SLOT_2PM_PT = {"startTime": "2026-03-01T22:00:00Z", "endTime": "2026-03-01T22:30:00Z"}
SLOT_4PM_PT = {"startTime": "2026-03-01T00:00:00Z", "endTime": "2026-03-01T00:30:00Z"}  # midnight UTC = 4pm PT-8
SLOT_6AM_PT = {"startTime": "2026-03-01T14:00:00Z", "endTime": "2026-03-01T14:30:00Z"}  # 6am PT — outside hours


@pytest.mark.asyncio
async def test_get_free_slots_success(ghl_client):
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response(
            {"2026-03-01": [SLOT_9AM_PT, SLOT_2PM_PT]}
        )
    )

    slots = await ghl_client.get_free_slots("cal-123")

    assert len(slots) == 2
    assert slots[0]["start"] == SLOT_9AM_PT["startTime"]
    assert slots[0]["end"] == SLOT_9AM_PT["endTime"]


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
    many_slots = [
        {"startTime": f"2026-03-01T{17 + i}:00:00Z", "endTime": f"2026-03-01T{17 + i}:30:00Z"}
        for i in range(6)
    ]
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response({"2026-03-01": many_slots})
    )

    slots = await ghl_client.get_free_slots("cal-123")

    assert len(slots) == 3


@pytest.mark.asyncio
async def test_get_free_slots_filters_outside_business_hours(ghl_client):
    # SLOT_6AM_PT is 14:00 UTC = 6am PT (outside 9am-5pm)
    ghl_client._make_request = AsyncMock(
        return_value=_make_success_response(
            {"2026-03-01": [SLOT_6AM_PT, SLOT_9AM_PT]}
        )
    )

    slots = await ghl_client.get_free_slots("cal-123")

    # Should include 9am but not 6am
    assert len(slots) == 1
    assert slots[0]["start"] == SLOT_9AM_PT["startTime"]
