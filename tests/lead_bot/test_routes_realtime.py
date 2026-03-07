"""Tests for real-time WebSocket and event polling routes."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import WebSocketDisconnect
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.main import app
from bots.lead_bot.routes_admin import get_admin_or_apikey
from bots.shared.config import settings
from bots.shared.rate_limit_middleware import _memory_counters


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit counters so tests aren't affected by prior runs."""
    _memory_counters.clear()
    yield
    _memory_counters.clear()


def _noop_auth():
    return None


@pytest_asyncio.fixture
async def client():
    """Async test client with auth bypassed."""
    app.dependency_overrides[get_admin_or_apikey] = _noop_auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_no_override():
    """Async test client WITHOUT auth bypass (for auth tests)."""
    app.dependency_overrides.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/events/recent — auth
# ---------------------------------------------------------------------------

class TestRecentEventsAuth:
    @pytest.mark.asyncio
    async def test_valid_admin_key(self, client_no_override):
        """Valid X-Admin-Key header returns 200."""
        mock_event = MagicMock()
        mock_event.event_id = "evt-1"
        mock_event.event_type = "lead.analyzed"
        mock_event.timestamp = datetime(2026, 3, 5, 12, 0, 0)
        mock_event.source = "lead_analyzer"
        mock_event.category.value = "leads"
        mock_event.sanitize_payload.return_value = {"score": 85}

        with patch.object(settings, "admin_api_key", "test-key-123"):
            with patch(
                "bots.shared.event_broker.event_broker.get_recent_events",
                new_callable=AsyncMock,
                return_value=[mock_event],
            ):
                resp = await client_no_override.get(
                    "/api/events/recent",
                    headers={"X-Admin-Key": "test-key-123"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["events"][0]["event_id"] == "evt-1"

    @pytest.mark.asyncio
    async def test_missing_auth_returns_403(self, client_no_override):
        """No auth header returns 403."""
        with patch.object(settings, "admin_api_key", "test-key-123"):
            resp = await client_no_override.get("/api/events/recent")

        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_invalid_admin_key_returns_403(self, client_no_override):
        """Wrong X-Admin-Key returns 403."""
        with patch.object(settings, "admin_api_key", "test-key-123"):
            resp = await client_no_override.get(
                "/api/events/recent",
                headers={"X-Admin-Key": "wrong-key"},
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/events/recent — query params
# ---------------------------------------------------------------------------

class TestRecentEventsParams:
    @pytest.mark.asyncio
    async def test_since_minutes_and_event_types(self, client):
        """since_minutes and event_types params are forwarded to broker."""
        with patch(
            "bots.shared.event_broker.event_broker.get_recent_events",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = await client.get(
                "/api/events/recent",
                params={"since_minutes": 10, "event_types": "lead.analyzed,ghl.tag_added"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["event_types_filter"] == ["lead.analyzed", "ghl.tag_added"]

        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["event_types"] == ["lead.analyzed", "ghl.tag_added"]
        assert call_kwargs.kwargs["limit"] == 100

    @pytest.mark.asyncio
    async def test_limit_capped_at_500(self, client):
        """limit param is capped at 500."""
        with patch(
            "bots.shared.event_broker.event_broker.get_recent_events",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = await client.get(
                "/api/events/recent",
                params={"limit": 1000},
            )

        assert resp.status_code == 200
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["limit"] == 500

    @pytest.mark.asyncio
    async def test_since_minutes_capped_at_60(self, client):
        """since_minutes param is capped at 60."""
        with patch(
            "bots.shared.event_broker.event_broker.get_recent_events",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = await client.get(
                "/api/events/recent",
                params={"since_minutes": 120},
            )

        assert resp.status_code == 200
        call_kwargs = mock_get.call_args
        since_time = call_kwargs.kwargs["since"]
        # The since time should be ~60 minutes ago, not 120
        now = datetime.now(timezone.utc)
        diff = now - since_time
        assert diff.total_seconds() < 3700  # ~61 minutes with tolerance

    @pytest.mark.asyncio
    async def test_default_params(self, client):
        """Default params: since_minutes=5, limit=100, no event_types filter."""
        with patch(
            "bots.shared.event_broker.event_broker.get_recent_events",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = await client.get("/api/events/recent")

        assert resp.status_code == 200
        data = resp.json()
        assert data["event_types_filter"] is None
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["event_types"] is None
        assert call_kwargs.kwargs["limit"] == 100


# ---------------------------------------------------------------------------
# GET /api/events/recent — response format
# ---------------------------------------------------------------------------

class TestRecentEventsResponse:
    @pytest.mark.asyncio
    async def test_event_formatting(self, client):
        """Events are formatted with expected keys."""
        mock_event = MagicMock()
        mock_event.event_id = "evt-42"
        mock_event.event_type = "ghl.tag_added"
        mock_event.timestamp = datetime(2026, 3, 5, 14, 30, 0)
        mock_event.source = "ghl_client"
        mock_event.category.value = "ghl"
        mock_event.sanitize_payload.return_value = {"tag": "hot-lead"}

        with patch(
            "bots.shared.event_broker.event_broker.get_recent_events",
            new_callable=AsyncMock,
            return_value=[mock_event],
        ):
            resp = await client.get("/api/events/recent")

        data = resp.json()
        event = data["events"][0]
        assert event["event_id"] == "evt-42"
        assert event["event_type"] == "ghl.tag_added"
        assert event["source"] == "ghl_client"
        assert event["category"] == "ghl"
        assert event["payload"] == {"tag": "hot-lead"}
        assert "timestamp" in event
        assert "since" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# GET /api/websocket/status
# ---------------------------------------------------------------------------

class TestWebsocketStatus:
    @pytest.mark.asyncio
    async def test_healthy_status(self, client):
        """Returns healthy status when websocket manager is running."""
        with patch(
            "bots.lead_bot.routes_realtime.websocket_manager"
        ) as mock_ws:
            mock_ws.health_check = AsyncMock(
                return_value={"websocket_manager_running": True}
            )
            mock_ws.get_metrics.return_value = {"connections": 2}

            resp = await client.get("/api/websocket/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["health"]["websocket_manager_running"] is True
        assert data["metrics"]["connections"] == 2

    @pytest.mark.asyncio
    async def test_unhealthy_status(self, client):
        """Returns unhealthy when websocket manager is not running."""
        with patch(
            "bots.lead_bot.routes_realtime.websocket_manager"
        ) as mock_ws:
            mock_ws.health_check = AsyncMock(
                return_value={"websocket_manager_running": False}
            )
            mock_ws.get_metrics.return_value = {}

            resp = await client.get("/api/websocket/status")

        assert resp.status_code == 200
        assert resp.json()["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# GET /api/events/health
# ---------------------------------------------------------------------------

class TestEventSystemHealth:
    @pytest.mark.asyncio
    async def test_healthy(self, client):
        """Returns healthy when both broker and ws manager are up."""
        with patch(
            "bots.lead_bot.routes_realtime.event_broker"
        ) as mock_broker, patch(
            "bots.lead_bot.routes_realtime.websocket_manager"
        ) as mock_ws:
            mock_broker.health_check = AsyncMock(
                return_value={"redis_connected": True}
            )
            mock_broker.get_metrics.return_value = {"events_published": 100}
            mock_ws.health_check = AsyncMock(
                return_value={"websocket_manager_running": True}
            )
            mock_ws.get_metrics.return_value = {"active": 3}

            resp = await client.get("/api/events/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "event_broker" in data
        assert "websocket_manager" in data

    @pytest.mark.asyncio
    async def test_degraded_when_redis_down(self, client):
        """Returns degraded when Redis is disconnected."""
        with patch(
            "bots.lead_bot.routes_realtime.event_broker"
        ) as mock_broker, patch(
            "bots.lead_bot.routes_realtime.websocket_manager"
        ) as mock_ws:
            mock_broker.health_check = AsyncMock(
                return_value={"redis_connected": False}
            )
            mock_broker.get_metrics.return_value = {}
            mock_ws.health_check = AsyncMock(
                return_value={"websocket_manager_running": True}
            )
            mock_ws.get_metrics.return_value = {}

            resp = await client.get("/api/events/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_error_handling(self, client):
        """Returns error status when health check throws."""
        with patch(
            "bots.lead_bot.routes_realtime.event_broker"
        ) as mock_broker:
            mock_broker.health_check = AsyncMock(
                side_effect=RuntimeError("Redis connection lost")
            )

            resp = await client.get("/api/events/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "error" in data


# ---------------------------------------------------------------------------
# WebSocket /ws/dashboard — basic auth
# ---------------------------------------------------------------------------

class TestWebsocketDashboard:
    def test_ws_rejects_missing_token(self):
        """WebSocket connection without token closes with 4401."""
        from starlette.testclient import TestClient

        with patch(
            "bots.lead_bot.routes_realtime.get_auth_service"
        ) as mock_auth_factory:
            mock_auth = MagicMock()
            mock_auth.validate_token = AsyncMock(return_value=False)
            mock_auth_factory.return_value = mock_auth

            sync_client = TestClient(app)
            with pytest.raises(Exception):
                with sync_client.websocket_connect("/ws/dashboard"):
                    pass

    def test_ws_rejects_invalid_token(self):
        """WebSocket connection with invalid token closes with 4401."""
        from starlette.testclient import TestClient

        with patch(
            "bots.lead_bot.routes_realtime.get_auth_service"
        ) as mock_auth_factory:
            mock_auth = MagicMock()
            mock_auth.validate_token = AsyncMock(return_value=False)
            mock_auth_factory.return_value = mock_auth

            sync_client = TestClient(app)
            with pytest.raises(Exception):
                with sync_client.websocket_connect(
                    "/ws/dashboard?token=bad-token"
                ):
                    pass

    @pytest.mark.asyncio
    async def test_ws_valid_token_calls_connect(self):
        """WebSocket with valid token calls websocket_manager.connect."""
        from starlette.websockets import WebSocket as StarletteWS

        # Verify valid token path by checking that get_auth_service().validate_token
        # returns True and websocket_manager.connect is called.
        # We test this via the route function directly to avoid TestClient hang.
        from bots.lead_bot.routes_realtime import websocket_dashboard

        mock_ws = AsyncMock(spec=StarletteWS)
        mock_ws.close = AsyncMock()
        # Simulate receive_text raising WebSocketDisconnect after connect
        mock_ws.receive_text = AsyncMock(
            side_effect=WebSocketDisconnect()
        )

        with patch(
            "bots.lead_bot.routes_realtime.get_auth_service"
        ) as mock_auth_factory, patch(
            "bots.lead_bot.routes_realtime.websocket_manager"
        ) as mock_ws_mgr:
            mock_auth = MagicMock()
            mock_auth.validate_token = AsyncMock(return_value=True)
            mock_auth_factory.return_value = mock_auth
            mock_ws_mgr.connect = AsyncMock(return_value="client-1")
            mock_ws_mgr.disconnect = AsyncMock()

            await websocket_dashboard(mock_ws, client_id="test", token="valid-jwt")

            mock_ws_mgr.connect.assert_called_once()
            mock_ws_mgr.disconnect.assert_called_once_with("client-1")
