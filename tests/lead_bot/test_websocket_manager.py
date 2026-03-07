"""Unit tests for WebSocketManager reliability behavior."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocketDisconnect

from bots.lead_bot.websocket_manager import WebSocketManager
from bots.shared.event_models import BaseEvent


def _make_manager() -> WebSocketManager:
    manager = WebSocketManager()
    manager.active_connections = {}
    manager.client_metadata = {}
    manager.redis_client = None
    manager.pubsub = None
    manager._heartbeat_task = None
    manager._redis_listener_task = None
    manager._running = True
    manager.total_connections = 0
    manager.events_broadcast = 0
    manager.heartbeats_sent = 0
    return manager


def _event() -> BaseEvent:
    return BaseEvent(
        event_type="system.health",
        source="test",
        payload={"ok": True},
        timestamp=datetime.now(timezone.utc),
    )


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_broadcast_cleans_disconnected_clients(self):
        manager = _make_manager()
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = WebSocketDisconnect()

        manager.active_connections = {"good": good_ws, "bad": bad_ws}
        manager.client_metadata = {
            "good": {
                "connected_at": datetime.now(timezone.utc),
                "last_heartbeat": datetime.now(timezone.utc),
                "events_received": 0,
            },
            "bad": {
                "connected_at": datetime.now(timezone.utc),
                "last_heartbeat": datetime.now(timezone.utc),
                "events_received": 0,
            },
        }

        await manager.broadcast(_event())

        good_ws.send_json.assert_awaited_once()
        assert "bad" not in manager.active_connections
        assert manager.events_broadcast == 1

    @pytest.mark.asyncio
    async def test_send_to_missing_client_is_noop(self):
        manager = _make_manager()
        await manager.send_to_client("missing", _event())
        assert manager.active_connections == {}

    @pytest.mark.asyncio
    async def test_heartbeat_loop_cleans_failed_clients(self, monkeypatch):
        manager = _make_manager()
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = RuntimeError("gone")
        manager.active_connections = {"good": good_ws, "bad": bad_ws}
        manager.client_metadata = {
            "good": {
                "connected_at": datetime.now(timezone.utc),
                "last_heartbeat": datetime.now(timezone.utc),
                "events_received": 0,
            },
            "bad": {
                "connected_at": datetime.now(timezone.utc),
                "last_heartbeat": datetime.now(timezone.utc),
                "events_received": 0,
            },
        }

        calls = {"count": 0}

        async def _fast_sleep(_seconds: int):
            calls["count"] += 1
            if calls["count"] >= 2:
                manager._running = False

        monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

        await manager._heartbeat_loop()

        good_ws.send_json.assert_awaited()
        assert "bad" not in manager.active_connections
        assert manager.heartbeats_sent >= 1

    @pytest.mark.asyncio
    async def test_health_check_reports_redis_error(self):
        manager = _make_manager()
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.side_effect = ConnectionError("down")

        health = await manager.health_check()

        assert health["websocket_manager_running"] is True
        assert health["redis_connected"] is False
        assert "redis_error" in health
