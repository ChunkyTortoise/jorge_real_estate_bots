"""Tests for dashboard API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.main import app
from bots.lead_bot.routes_admin import get_admin_or_apikey


def _noop_auth():
    return None


@pytest_asyncio.fixture
async def client():
    """Provide an async test client with auth bypassed."""
    app.dependency_overrides[get_admin_or_apikey] = _noop_auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/dashboard/metrics
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dashboard_metrics(client):
    """Metrics endpoint returns system + performance data."""
    mock_perf = MagicMock()
    mock_perf.to_dict.return_value = {
        "cache_avg_ms": 1.0,
        "cache_hit_rate": 80.0,
        "ai_avg_ms": 200.0,
    }

    with patch(
        "bots.lead_bot.routes_dashboard.BotMetricsCollector"
    ) as MockCollector, patch(
        "bots.lead_bot.routes_dashboard.PerformanceTracker"
    ) as MockTracker:
        MockCollector.return_value.get_system_summary.return_value = {
            "bots": {}, "handoffs": {}, "overall": {}
        }
        MockTracker.return_value.get_performance_metrics = AsyncMock(
            return_value=mock_perf
        )

        resp = await client.get("/api/dashboard/metrics")

    assert resp.status_code == 200
    data = resp.json()
    assert "system" in data
    assert "performance" in data
    assert data["performance"]["cache_avg_ms"] == 1.0


# ---------------------------------------------------------------------------
# GET /api/dashboard/leads/summary
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dashboard_leads_summary(client):
    """Leads summary endpoint returns hero + conversation summary."""
    with patch(
        "bots.lead_bot.routes_dashboard.DashboardDataService"
    ) as MockSvc:
        instance = MockSvc.return_value
        instance.get_hero_metrics_data = AsyncMock(return_value={"total_leads": 5})
        instance.get_conversation_summary = AsyncMock(
            return_value={"total_active": 3}
        )

        resp = await client.get("/api/dashboard/leads/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["hero"]["total_leads"] == 5
    assert data["conversation_summary"]["total_active"] == 3


# ---------------------------------------------------------------------------
# GET /api/dashboard/leads (paginated, uses mocked DB session from conftest)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dashboard_leads_empty(client):
    """Leads endpoint returns empty list when no data."""
    resp = await client.get("/api/dashboard/leads")
    assert resp.status_code == 200
    data = resp.json()
    assert data["leads"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/dashboard/leads/{contact_id}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dashboard_lead_detail_not_found(client):
    """Lead detail returns 404 for unknown contact."""
    resp = await client.get("/api/dashboard/leads/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/dashboard/handoffs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dashboard_handoffs(client):
    """Handoffs endpoint returns list."""
    with patch(
        "bots.lead_bot.routes_dashboard.BotMetricsCollector"
    ) as MockCollector:
        import threading

        instance = MockCollector.return_value
        instance._data_lock = threading.Lock()
        instance._handoffs = []

        resp = await client.get("/api/dashboard/handoffs")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_dashboard_handoffs_with_data(client):
    """Handoffs endpoint returns recent handoffs."""
    with patch(
        "bots.lead_bot.routes_dashboard.BotMetricsCollector"
    ) as MockCollector:
        import threading
        from dataclasses import dataclass

        @dataclass
        class FakeHandoff:
            source: str = "lead"
            target: str = "buyer"
            success: bool = True
            duration_ms: float = 150.0
            timestamp: float = 1000.0

        instance = MockCollector.return_value
        instance._data_lock = threading.Lock()
        instance._handoffs = [FakeHandoff(), FakeHandoff(source="buyer", target="seller")]

        resp = await client.get("/api/dashboard/handoffs?limit=5")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["source"] == "buyer"  # reversed — most recent first
    assert data[1]["source"] == "lead"


# ---------------------------------------------------------------------------
# GET /api/dashboard/conversations/{contact_id}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dashboard_conversation_not_found(client):
    """Conversation detail returns 404 for unknown contact."""
    resp = await client.get("/api/dashboard/conversations/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/alerts/active
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_alerts_active(client):
    """Active alerts endpoint returns list."""
    with patch(
        "bots.lead_bot.routes_dashboard.AlertingService"
    ) as MockAlerting:
        MockAlerting.return_value.get_active_alerts.return_value = [
            {"id": "abc123", "rule_name": "high_error_rate", "acknowledged": False}
        ]

        resp = await client.get("/api/alerts/active")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "abc123"


# ---------------------------------------------------------------------------
# POST /api/alerts/{id}/acknowledge
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_alert_acknowledge_success(client):
    """Acknowledge alert returns 200 on success."""
    with patch(
        "bots.lead_bot.routes_dashboard.AlertingService"
    ) as MockAlerting:
        MockAlerting.return_value.acknowledge_alert.return_value = None

        resp = await client.post("/api/alerts/abc123/acknowledge")

    assert resp.status_code == 200
    data = resp.json()
    assert data["acknowledged"] is True
    assert data["alert_id"] == "abc123"


@pytest.mark.asyncio
async def test_alert_acknowledge_not_found(client):
    """Acknowledge alert returns 404 for unknown alert ID."""
    with patch(
        "bots.lead_bot.routes_dashboard.AlertingService"
    ) as MockAlerting:
        MockAlerting.return_value.acknowledge_alert.side_effect = KeyError("not found")

        resp = await client.post("/api/alerts/unknown-id/acknowledge")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metrics_requires_auth(monkeypatch):
    """Endpoints return 403 with wrong admin key when a key is configured."""
    from bots.shared.config import settings as _settings

    monkeypatch.setattr(_settings, "admin_api_key", "real-secret-key")
    app.dependency_overrides.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.get(
            "/api/dashboard/metrics",
            headers={"X-Admin-Key": "wrong-key"},
        )
    assert resp.status_code == 403
