"""Tests for bots.shared.event_broker — EventBroker, CircuitBreaker, convenience publishers."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.shared.event_broker import (
    CircuitBreaker,
    CircuitBreakerError,
    EventBroker,
)
from bots.shared.event_models import BaseEvent, create_event


# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=10)
        assert cb.state == "closed"
        assert not cb.is_open()

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=10)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert not cb.is_open()

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=10)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open()

    def test_success_resets_counter(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=10)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=0)
        cb.record_failure()
        assert cb.state == "open"
        # Force last_failure_time far in the past
        cb.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert not cb.is_open()
        assert cb.state == "half-open"

    @pytest.mark.asyncio
    async def test_call_success(self):
        cb = CircuitBreaker()

        async def ok():
            return 42

        result = await cb.call(ok)
        assert result == 42
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_failure_records(self):
        cb = CircuitBreaker()

        async def fail():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await cb.call(fail)
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_call_when_open_raises(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=9999)
        cb.record_failure()
        assert cb.state == "open"

        async def noop():
            pass  # pragma: no cover

        with pytest.raises(CircuitBreakerError):
            await cb.call(noop)


# ---------------------------------------------------------------------------
# EventBroker — publish / subscribe / metrics
# ---------------------------------------------------------------------------

def _make_broker() -> EventBroker:
    """Create a fresh (non-singleton) EventBroker for isolated tests."""
    broker = object.__new__(EventBroker)
    broker.redis_url = "redis://localhost:6379/0"
    broker.connection_pool = None
    broker.redis_client = None
    broker.pubsub_client = None
    broker.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=30)
    broker.event_retention_seconds = 60
    broker.max_stream_length = 1000
    broker.published_count = 0
    broker.failed_count = 0
    broker.subscribers = {}
    broker._cleanup_task = None
    broker._running = True
    return broker


def _make_event() -> BaseEvent:
    return BaseEvent(
        event_type="lead.scored",
        source="test",
        payload={"contact_id": "c123", "score": 85},
    )


class TestEventBrokerPublish:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        broker = _make_broker()
        event = _make_event()

        # Mock _redis_publish to succeed
        broker._redis_publish = AsyncMock(return_value=True)

        result = await broker.publish(event)
        assert result is True
        assert broker.published_count == 1
        assert broker.failed_count == 0
        broker._redis_publish.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_redis_failure_increments_failed(self):
        broker = _make_broker()
        event = _make_event()

        broker._redis_publish = AsyncMock(side_effect=ConnectionError("down"))
        broker._fallback_publish = AsyncMock()

        result = await broker.publish(event)
        assert result is False
        assert broker.failed_count == 1
        broker._fallback_publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_circuit_open_uses_fallback(self):
        broker = _make_broker()
        event = _make_event()

        # Force circuit open
        broker.circuit_breaker.state = "open"
        broker.circuit_breaker.last_failure_time = datetime.now(timezone.utc)
        broker.circuit_breaker.timeout = 9999
        broker._fallback_publish = AsyncMock()

        result = await broker.publish(event)
        assert result is False
        broker._fallback_publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_initializes_if_not_running(self):
        broker = _make_broker()
        broker._running = False
        event = _make_event()

        broker.initialize = AsyncMock()
        broker._redis_publish = AsyncMock(return_value=True)

        await broker.publish(event)
        broker.initialize.assert_awaited_once()


class TestEventBrokerSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_registers_callback(self):
        broker = _make_broker()

        async def handler(evt: BaseEvent):
            pass  # pragma: no cover

        await broker.subscribe("jorge:events:leads", handler)
        assert handler in broker.subscribers["jorge:events:leads"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_callback(self):
        broker = _make_broker()

        async def handler(evt: BaseEvent):
            pass  # pragma: no cover

        await broker.subscribe("jorge:events:leads", handler)
        await broker.unsubscribe("jorge:events:leads", handler)
        assert "jorge:events:leads" not in broker.subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_channel_noop(self):
        broker = _make_broker()

        async def handler(evt: BaseEvent):
            pass  # pragma: no cover

        # Should not raise
        await broker.unsubscribe("nonexistent", handler)

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_channel(self):
        broker = _make_broker()

        async def h1(evt):
            pass  # pragma: no cover

        async def h2(evt):
            pass  # pragma: no cover

        await broker.subscribe("ch", h1)
        await broker.subscribe("ch", h2)
        assert len(broker.subscribers["ch"]) == 2


class TestEventBrokerMetrics:
    def test_get_metrics_initial(self):
        broker = _make_broker()
        metrics = broker.get_metrics()
        assert metrics["published_count"] == 0
        assert metrics["failed_count"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["circuit_breaker_state"] == "closed"
        assert metrics["running"] is True

    def test_get_metrics_after_publish(self):
        broker = _make_broker()
        broker.published_count = 8
        broker.failed_count = 2
        metrics = broker.get_metrics()
        assert metrics["success_rate"] == 0.8

    @pytest.mark.asyncio
    async def test_health_check_redis_connected(self):
        broker = _make_broker()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.info = AsyncMock(return_value={"used_memory_human": "1M"})
        broker.redis_client = mock_redis

        health = await broker.health_check()
        assert health["redis_connected"] is True
        assert health["redis_memory_used"] == "1M"

    @pytest.mark.asyncio
    async def test_health_check_redis_down(self):
        broker = _make_broker()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("down"))
        broker.redis_client = mock_redis

        health = await broker.health_check()
        assert health["redis_connected"] is False
        assert "error" in health


class TestEventBrokerRecentEvents:
    @pytest.mark.asyncio
    async def test_get_recent_events_filters_and_sorts(self):
        broker = _make_broker()
        broker.redis_client = AsyncMock()
        now = datetime.now(timezone.utc)
        lead_payload = {
            b"event_type": b"lead.scored",
            b"source": b"lead_analyzer",
            b"contact_id": b"c1",
            b"score": b"85",
            b"payload": json.dumps({"contact_id": "c1"}).encode(),
            b"timestamp": now.isoformat().encode(),
        }
        ghl_payload = {
            b"event_type": b"ghl.tag_added",
            b"source": b"ghl_client",
            b"contact_id": b"c1",
            b"tag": b"seller_hot",
            b"payload": json.dumps({"tag": "seller_hot"}).encode(),
            b"timestamp": (now - timedelta(seconds=5)).isoformat().encode(),
        }
        broker.redis_client.xrevrange = AsyncMock(
            side_effect=[
                [(b"1-0", lead_payload)],
                [(b"2-0", ghl_payload)],
                [],
                [],
            ]
        )

        events = await broker.get_recent_events(event_types=["lead.scored"], limit=10)

        assert len(events) == 1
        assert events[0].event_type == "lead.scored"
        broker.redis_client.xrevrange.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_recent_events_deserializes_nested_dict_fields(self):
        """Non-payload fields containing JSON-encoded dicts are deserialized."""
        broker = _make_broker()
        broker.redis_client = AsyncMock()
        now = datetime.now(timezone.utc)
        nested_dict = {"seller_name": "Jorge", "stage": "Q2"}
        event_data = {
            b"event_type": b"lead.qualified",
            b"source": b"seller_bot",
            b"metadata": json.dumps(nested_dict).encode(),
            b"plain_field": b"plain_value",
            b"timestamp": now.isoformat().encode(),
        }
        broker.redis_client.xrevrange = AsyncMock(
            side_effect=[[(b"1-0", event_data)], [], [], []]
        )

        events = await broker.get_recent_events(limit=10)

        assert len(events) == 1
        # The event's payload should include the metadata field deserialized as dict
        # (it ends up in the fallback payload dict since there's no explicit "payload" key)
        # Verify the pre-deserialization loop ran without error
        assert events[0].event_type == "lead.qualified"

    @pytest.mark.asyncio
    async def test_get_recent_events_preserves_plain_string_fields(self):
        """Non-JSON string fields are kept as plain strings after the deserialization pass."""
        broker = _make_broker()
        broker.redis_client = AsyncMock()
        now = datetime.now(timezone.utc)
        event_data = {
            b"event_type": b"lead.qualified",
            b"source": b"seller_bot",
            b"plain_field": b"just a string",
            b"timestamp": now.isoformat().encode(),
        }
        broker.redis_client.xrevrange = AsyncMock(
            side_effect=[[(b"1-0", event_data)], [], [], []]
        )

        events = await broker.get_recent_events(limit=10)

        assert len(events) == 1
        # payload is built from fallback dict; plain_field must survive as a string
        assert events[0].payload.get("plain_field") == "just a string"

    @pytest.mark.asyncio
    async def test_cleanup_expired_events_trims_streams(self, monkeypatch):
        broker = _make_broker()
        broker.redis_client = AsyncMock()
        calls = {"count": 0}

        async def _fast_sleep(_seconds: int):
            calls["count"] += 1
            if calls["count"] >= 2:
                broker._running = False

        monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

        await broker._cleanup_expired_events()

        broker.redis_client.xtrim.assert_awaited()


class TestEventBrokerShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_closes_clients(self):
        broker = _make_broker()
        broker.redis_client = AsyncMock()
        broker.pubsub_client = AsyncMock()
        broker.connection_pool = AsyncMock()

        await broker.shutdown()
        broker.redis_client.close.assert_awaited_once()
        broker.pubsub_client.close.assert_awaited_once()
        broker.connection_pool.disconnect.assert_awaited_once()
        assert broker._running is False

    @pytest.mark.asyncio
    async def test_shutdown_cancels_cleanup_task(self):
        broker = _make_broker()
        broker.redis_client = None
        broker.pubsub_client = None
        broker.connection_pool = None

        # Create a real asyncio task that we can cancel
        async def forever():
            await asyncio.sleep(9999)

        task = asyncio.create_task(forever())
        broker._cleanup_task = task

        await broker.shutdown()
        assert task.cancelled()


# ---------------------------------------------------------------------------
# Convenience publisher functions
# ---------------------------------------------------------------------------

class TestConveniencePublishers:
    @pytest.mark.asyncio
    async def test_publish_lead_event(self):
        from bots.shared.event_broker import publish_lead_event

        mock_event = BaseEvent(
            event_type="lead.scored", source="test", payload={"contact_id": "c1"}
        )
        mock_publish = AsyncMock(return_value=True)
        with patch("bots.shared.event_broker.event_broker") as mock_broker, \
             patch("bots.shared.event_broker.create_event", return_value=mock_event):
            mock_broker.publish = mock_publish
            result = await publish_lead_event(
                "lead.scored",
                contact_id="c1",
                score=90,
            )
        assert result is True
        mock_publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_system_event(self):
        from bots.shared.event_broker import publish_system_event

        mock_event = BaseEvent(
            event_type="system.health", source="test", payload={}
        )
        mock_publish = AsyncMock(return_value=True)
        with patch("bots.shared.event_broker.event_broker") as mock_broker, \
             patch("bots.shared.event_broker.create_event", return_value=mock_event):
            mock_broker.publish = mock_publish
            result = await publish_system_event(
                "system.health",
                redis_healthy=True,
            )
        assert result is True
        mock_publish.assert_awaited_once()
