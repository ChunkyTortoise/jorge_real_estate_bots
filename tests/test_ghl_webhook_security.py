"""Security regression tests for GHL webhook endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from bots.lead_bot import main as lead_main
from bots.lead_bot.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_unified_webhook_allows_when_no_secret_configured(client: AsyncClient) -> None:
    """When no signature config is set, requests are allowed (pass-through mode for MVP)."""
    payload = {"contactId": "c1", "message": "hello"}

    response = await client.post("/api/ghl/webhook", json=payload)

    # 200 or 500 (processing error) — not 401
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_unified_webhook_rejects_missing_signature_when_secret_set(client: AsyncClient, monkeypatch) -> None:
    """When a webhook secret IS configured, missing signatures must be rejected."""
    monkeypatch.setattr(lead_main.settings, "ghl_webhook_secret", "test-secret-abc")
    payload = {"contactId": "c1", "message": "hello"}

    response = await client.post("/api/ghl/webhook", json=payload)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unified_webhook_accepts_valid_signature_and_processes(client: AsyncClient, monkeypatch) -> None:
    payload = {"contactId": "c1", "message": "hello", "bot_type": "lead"}

    mock_analyzer = AsyncMock(return_value=({"score": 80, "temperature": "hot", "jorge_priority": "high"}, object()))
    monkeypatch.setattr(lead_main, "verify_ghl_signature", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(lead_main, "lead_analyzer", type("MockAnalyzer", (), {"analyze_lead": mock_analyzer})())

    response = await client.post(
        "/api/ghl/webhook",
        json=payload,
        headers={"x-wh-signature": "valid-signature"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["bot_type"] == "lead"
