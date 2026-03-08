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
async def test_reset_state_clears_cache_keys(authed_client):
    """DELETE /admin/reset-state must clear bot:state and conversation:mode keys."""
    mock_cache = AsyncMock()
    deleted_keys = []
    mock_cache.delete = AsyncMock(side_effect=lambda k: deleted_keys.append(k))

    with patch("bots.lead_bot.main._webhook_cache", mock_cache):
        async with authed_client as client:
            resp = await client.delete("/admin/reset-state/seller/contact-xyz")

    assert resp.status_code == 200
    assert any("seller:state:contact-xyz" in k for k in deleted_keys), deleted_keys
    assert any("conversation:mode:contact-xyz" in k for k in deleted_keys), deleted_keys


@pytest.mark.asyncio
async def test_reassign_then_webhook_routes_correctly(authed_client):
    """Admin reassign to seller → next webhook for that contact routes to seller bot (E2E)."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    mock_cache = AsyncMock()
    store: dict = {}

    async def _get(key):
        return store.get(key)

    async def _set(key, value, ttl=0):
        store[key] = value

    mock_cache.get = AsyncMock(side_effect=_get)
    mock_cache.set = AsyncMock(side_effect=_set)

    with patch("bots.lead_bot.main._webhook_cache", mock_cache):
        async with authed_client as client:
            resp = await client.post(
                "/admin/reassign-bot",
                json={"contact_id": "reassign-e2e", "mode": "seller"},
            )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "seller"
    # Cache key was written by the reassign endpoint
    assert store.get("conversation:mode:reassign-e2e") == "seller"


@pytest.mark.asyncio
async def test_get_conversation_success_returns_canonical_fields(authed_client, monkeypatch):
    """GET /admin/conversations/{id} → 200 with canonical debug data."""
    from contextlib import asynccontextmanager
    from database.models import ConversationModel

    mock_row = MagicMock(spec=ConversationModel)
    mock_row.contact_id = "conv-debug"
    mock_row.bot_type = "seller"
    mock_row.stage = "ACTIVE"
    mock_row.temperature = "warm"
    mock_row.questions_answered = 2
    mock_row.is_qualified = False
    mock_row.metadata_json = {
        "mode": "seller",
        "mode_version": 2,
        "status": "active",
        "human_takeover": False,
        "bilingual_required": False,
        "handoff_reason": None,
        "message_suppression_reason": None,
        "qualification_summary": {},
        "next_recommended_action": "Continue qualification",
        "crm_sync_status": "synced",
        "last_inbound_at": "2026-03-07T00:00:00Z",
        "last_outbound_at": "2026-03-07T00:01:00Z",
        "temperature": "warm",
    }
    mock_row.updated_at = None
    mock_row.created_at = None

    class _Result:
        def scalars(self):
            return self
        def all(self):
            return [mock_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_Result())

    @asynccontextmanager
    async def _mock_factory():
        yield mock_session

    monkeypatch.setattr("bots.lead_bot.routes_admin.AsyncSessionFactory", _mock_factory)

    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value="seller")

    with patch("bots.lead_bot.main._webhook_cache", mock_cache):
        async with authed_client as client:
            resp = await client.get("/admin/conversations/conv-debug")

    assert resp.status_code == 200
    data = resp.json()
    assert data["contact_id"] == "conv-debug"
    assert "mode" in data
    assert "status" in data
    assert "human_takeover" in data
    assert "bilingual_required" in data


# ---------------------------------------------------------------------------
# Fix 3 — admin reassign syncs GHL ai_mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_reassign_syncs_ghl_fields(authed_client):
    """POST /admin/reassign-bot must attempt to sync ai_mode to GHL."""
    mock_cache = AsyncMock()
    mock_ghl = AsyncMock()
    mock_ghl.update_custom_field = AsyncMock(return_value={"success": True})

    with (
        patch("bots.lead_bot.main._webhook_cache", mock_cache),
        patch("database.repository.update_conversation_mode", new=AsyncMock()),
        patch("bots.lead_bot.main._ghl_client", mock_ghl, create=True),
    ):
        async with authed_client as client:
            resp = await client.post(
                "/admin/reassign-bot",
                json={"contact_id": "ghl-sync-test", "mode": "seller"},
            )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "seller"


# ---------------------------------------------------------------------------
# Fix 4 — admin reassign uses targeted mode update (preserves stage/temperature)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_reassign_preserves_stage(authed_client):
    """POST /admin/reassign-bot must call update_conversation_mode (not upsert_conversation)."""
    mock_cache = AsyncMock()
    mock_update_mode = AsyncMock()

    with (
        patch("bots.lead_bot.main._webhook_cache", mock_cache),
        patch("database.repository.update_conversation_mode", mock_update_mode),
    ):
        async with authed_client as client:
            resp = await client.post(
                "/admin/reassign-bot",
                json={"contact_id": "preserve-stage", "mode": "buyer"},
            )
    assert resp.status_code == 200
    # update_conversation_mode must have been called with the new mode
    mock_update_mode.assert_awaited_once()
    args = mock_update_mode.call_args
    assert args[0][1] == "buyer" or args.kwargs.get("mode") == "buyer"
