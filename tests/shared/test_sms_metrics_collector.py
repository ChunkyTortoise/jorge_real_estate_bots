"""Tests for bots.shared.sms_metrics_collector — SmsMetricsCollector."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from bots.shared.sms_metrics_collector import SmsMetricsCollector, VALID_STATUSES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collector() -> SmsMetricsCollector:
    """Build collector with a mocked CacheService."""
    collector = SmsMetricsCollector()
    collector._cache = AsyncMock()
    # Default: all gets return None (empty state)
    collector._cache.get = AsyncMock(return_value=None)
    collector._cache.set = AsyncMock(return_value=True)
    return collector


def _ts() -> datetime:
    return datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# record_delivery
# ---------------------------------------------------------------------------

class TestRecordDelivery:
    @pytest.mark.asyncio
    async def test_record_delivered_success(self):
        c = _make_collector()
        await c.record_delivery("contact1", "delivered", _ts())

        # Should call cache.set for counter, timeline, and events
        assert c._cache.set.await_count == 3

    @pytest.mark.asyncio
    async def test_record_failed_success(self):
        c = _make_collector()
        await c.record_delivery("contact1", "failed", _ts())
        assert c._cache.set.await_count == 3

    @pytest.mark.asyncio
    async def test_record_read_success(self):
        c = _make_collector()
        await c.record_delivery("contact1", "read", _ts())
        assert c._cache.set.await_count == 3

    @pytest.mark.asyncio
    async def test_invalid_status_raises(self):
        c = _make_collector()
        with pytest.raises(ValueError, match="Invalid status 'bounced'"):
            await c.record_delivery("contact1", "bounced", _ts())

    @pytest.mark.asyncio
    async def test_counter_increments_from_existing(self):
        c = _make_collector()
        # Simulate existing counter = 5
        c._cache.get = AsyncMock(side_effect=lambda key: "5" if ":count:" in key else None)

        await c.record_delivery("contact1", "delivered", _ts())

        # The counter set should be called with 6
        counter_call = [
            call for call in c._cache.set.call_args_list
            if "count:delivered" in str(call)
        ]
        assert len(counter_call) == 1
        assert counter_call[0][0][1] == 6  # value = 6

    @pytest.mark.asyncio
    async def test_timeline_appends_to_existing(self):
        c = _make_collector()
        existing_timeline = json.dumps([
            {"status": "delivered", "timestamp": "2026-03-04T12:00:00+00:00", "contact_id": "c1"}
        ])

        def mock_get(key):
            if ":timeline:" in key:
                return existing_timeline
            return None

        c._cache.get = AsyncMock(side_effect=mock_get)
        await c.record_delivery("c1", "read", _ts())

        # Find the timeline set call
        timeline_call = [
            call for call in c._cache.set.call_args_list
            if "timeline:" in str(call)
        ]
        assert len(timeline_call) == 1
        saved = json.loads(timeline_call[0][0][1])
        assert len(saved) == 2
        assert saved[1]["status"] == "read"

    @pytest.mark.asyncio
    async def test_events_list_capped_at_1000(self):
        c = _make_collector()
        # Simulate 1000 existing events
        existing = json.dumps(["e"] * 1000)

        def mock_get(key):
            if key == "sms_metrics:events":
                return existing
            return None

        c._cache.get = AsyncMock(side_effect=mock_get)
        await c.record_delivery("c1", "delivered", _ts())

        events_call = [
            call for call in c._cache.set.call_args_list
            if call[0][0] == "sms_metrics:events"
        ]
        assert len(events_call) == 1
        saved = json.loads(events_call[0][0][1])
        assert len(saved) == 1000  # Capped


# ---------------------------------------------------------------------------
# get_delivery_stats
# ---------------------------------------------------------------------------

class TestGetDeliveryStats:
    @pytest.mark.asyncio
    async def test_zero_records(self):
        c = _make_collector()
        stats = await c.get_delivery_stats()
        assert stats == {
            "delivered": 0,
            "failed": 0,
            "read": 0,
            "delivery_rate": 0.0,
        }

    @pytest.mark.asyncio
    async def test_all_delivered(self):
        c = _make_collector()

        def mock_get(key):
            if "count:delivered" in key:
                return "10"
            if "count:failed" in key:
                return "0"
            if "count:read" in key:
                return "3"
            return None

        c._cache.get = AsyncMock(side_effect=mock_get)
        stats = await c.get_delivery_stats()
        assert stats["delivered"] == 10
        assert stats["failed"] == 0
        assert stats["read"] == 3
        assert stats["delivery_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_all_failures(self):
        c = _make_collector()

        def mock_get(key):
            if "count:delivered" in key:
                return "0"
            if "count:failed" in key:
                return "10"
            return None

        c._cache.get = AsyncMock(side_effect=mock_get)
        stats = await c.get_delivery_stats()
        assert stats["delivered"] == 0
        assert stats["failed"] == 10
        assert stats["delivery_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_mixed_delivery_rate(self):
        c = _make_collector()

        def mock_get(key):
            if "count:delivered" in key:
                return "7"
            if "count:failed" in key:
                return "3"
            if "count:read" in key:
                return "2"
            return None

        c._cache.get = AsyncMock(side_effect=mock_get)
        stats = await c.get_delivery_stats()
        assert stats["delivery_rate"] == 0.7


# ---------------------------------------------------------------------------
# get_per_contact_timeline
# ---------------------------------------------------------------------------

class TestPerContactTimeline:
    @pytest.mark.asyncio
    async def test_empty_timeline(self):
        c = _make_collector()
        result = await c.get_per_contact_timeline("c_unknown")
        assert result == []

    @pytest.mark.asyncio
    async def test_existing_timeline(self):
        c = _make_collector()
        entries = [
            {"status": "delivered", "timestamp": "2026-03-05T12:00:00+00:00", "contact_id": "c1"},
            {"status": "read", "timestamp": "2026-03-05T12:05:00+00:00", "contact_id": "c1"},
        ]
        c._cache.get = AsyncMock(return_value=json.dumps(entries))
        result = await c.get_per_contact_timeline("c1")
        assert len(result) == 2
        assert result[0]["status"] == "delivered"
        assert result[1]["status"] == "read"


# ---------------------------------------------------------------------------
# VALID_STATUSES constant
# ---------------------------------------------------------------------------

class TestValidStatuses:
    def test_valid_statuses_contents(self):
        assert VALID_STATUSES == {"delivered", "failed", "read"}

    def test_valid_statuses_frozen(self):
        assert isinstance(VALID_STATUSES, frozenset)
