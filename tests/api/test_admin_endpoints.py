"""Tests for admin endpoint correctness after v2 hardening."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.main import app
from bots.lead_bot.routes_admin import get_admin_or_apikey


@pytest.fixture
def authed_client():
    """Return an authed client context manager with auth bypassed."""
    app.dependency_overrides[get_admin_or_apikey] = lambda: None

    class _CM:
        async def __aenter__(self):
            self._c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            return await self._c.__aenter__()

        async def __aexit__(self, *args):
            await self._c.__aexit__(*args)
            app.dependency_overrides.clear()

    return _CM()


@pytest.mark.asyncio
async def test_reassign_bot_empty_body_returns_400(authed_client):
    """POST /admin/reassign-bot with {} must return 400 (no mode or bot_type given)."""
    async with authed_client as client:
        resp = await client.post("/admin/reassign-bot", json={})
    assert resp.status_code == 400
    assert "required" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_reassign_bot_no_contact_id_returns_400(authed_client):
    """POST /admin/reassign-bot with mode but no contact_id must return 400."""
    async with authed_client as client:
        resp = await client.post("/admin/reassign-bot", json={"mode": "seller"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reassign_bot_valid_body_succeeds(authed_client):
    """POST /admin/reassign-bot with valid contact_id + mode must return 200."""
    mock_cache = AsyncMock()

    with patch("bots.lead_bot.main._webhook_cache", mock_cache):
        async with authed_client as client:
            resp = await client.post(
                "/admin/reassign-bot",
                json={"contact_id": "c123", "mode": "seller"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "seller"
    assert data["contact_id"] == "c123"


@pytest.mark.asyncio
async def test_get_conversation_not_found_returns_404(authed_client, monkeypatch):
    """GET /admin/conversations/{id} returns 404 when no rows exist."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    class _EmptyResult:
        def scalars(self):
            return self
        def all(self):
            return []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_EmptyResult())

    @asynccontextmanager
    async def _mock_factory():
        yield mock_session

    monkeypatch.setattr("bots.lead_bot.routes_admin.AsyncSessionFactory", _mock_factory)
    async with authed_client as client:
        resp = await client.get("/admin/conversations/nonexistent-contact")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_state_clears_all_three_cache_keys(authed_client):
    """DELETE /admin/reset-state must clear bot:state, conversation:mode, AND assigned_bot."""
    mock_cache = AsyncMock()
    deleted_keys = []
    mock_cache.delete = AsyncMock(side_effect=lambda k: deleted_keys.append(k))

    with patch("bots.lead_bot.main._webhook_cache", mock_cache):
        async with authed_client as client:
            resp = await client.delete("/admin/reset-state/seller/contact-xyz")

    assert resp.status_code == 200
    assert any("seller:state:contact-xyz" in k for k in deleted_keys), deleted_keys
    assert any("conversation:mode:contact-xyz" in k for k in deleted_keys), deleted_keys
    assert any("assigned_bot:contact-xyz" in k for k in deleted_keys), deleted_keys
    # Must NOT have duplicate deletes for assigned_bot
    assigned_bot_deletes = [k for k in deleted_keys if "assigned_bot:contact-xyz" == k]
    assert len(assigned_bot_deletes) == 1, f"Duplicate delete detected: {deleted_keys}"
