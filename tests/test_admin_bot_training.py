"""
Tests for admin API key auth, buyer overrides, reset-state, and lead settings.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from types import SimpleNamespace

from bots.lead_bot.main import app
from bots.shared import bot_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(monkeypatch):
    """HTTP test client with admin_api_key configured and cache mocked."""
    monkeypatch.setattr("bots.shared.config.settings.admin_api_key", "test-admin-key-123")

    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()
    mock_cache.delete = AsyncMock()

    monkeypatch.setattr("bots.lead_bot.main._webhook_cache", mock_cache)

    # Reset any lingering overrides between tests
    bot_settings.reset()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, mock_cache

    bot_settings.reset()


# ---------------------------------------------------------------------------
# 1. API key auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_api_key_valid(client):
    c, _ = client
    resp = await c.get("/admin/settings", headers={"X-Admin-Key": "test-admin-key-123"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_api_key_wrong_returns_403(client):
    c, _ = client
    resp = await c.get("/admin/settings", headers={"X-Admin-Key": "wrong-key"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_no_auth_returns_401(client, monkeypatch):
    c, _ = client
    # JWT path will fail with 401 when no credentials are supplied
    resp = await c.get("/admin/settings")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Lead section in GET /admin/settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lead_settings_in_admin_get(client):
    c, _ = client
    resp = await c.get("/admin/settings", headers={"X-Admin-Key": "test-admin-key-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "lead" in data
    lead = data["lead"]
    assert "min_price" in lead
    assert "max_price" in lead
    assert "service_areas" in lead
    assert "preferred_timeline" in lead
    assert "standard_commission" in lead
    assert "minimum_commission" in lead


@pytest.mark.asyncio
async def test_lead_settings_reflects_override(client):
    c, _ = client
    bot_settings.update_settings("lead", {"min_price": 300000, "max_price": 900000})
    resp = await c.get("/admin/settings", headers={"X-Admin-Key": "test-admin-key-123"})
    assert resp.status_code == 200
    lead = resp.json()["lead"]
    assert lead["min_price"] == 300000
    assert lead["max_price"] == 900000


# ---------------------------------------------------------------------------
# 3. Reset state endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_reset_state_calls_cache_delete(client):
    c, mock_cache = client
    resp = await c.delete(
        "/admin/reset-state/buyer/contact-abc",
        headers={"X-Admin-Key": "test-admin-key-123"},
    )
    assert resp.status_code == 200
    deleted = [call.args[0] for call in mock_cache.delete.call_args_list]
    assert "buyer:state:contact-abc" in deleted
    assert "conversation:mode:contact-abc" in deleted


@pytest.mark.asyncio
async def test_admin_reset_state_invalid_bot(client):
    c, _ = client
    resp = await c.delete(
        "/admin/reset-state/lead/contact-abc",
        headers={"X-Admin-Key": "test-admin-key-123"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_reassign_accepts_canonical_mode(client):
    c, mock_cache = client
    resp = await c.post(
        "/admin/reassign-bot",
        headers={"X-Admin-Key": "test-admin-key-123"},
        json={"contact_id": "contact-xyz", "mode": "human_handoff"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "human_handoff"
    mock_cache.set.assert_called_with("conversation:mode:contact-xyz", "human_handoff", ttl=604_800)


@pytest.mark.asyncio
async def test_admin_get_conversation_returns_canonical_debug_fields(client, monkeypatch):
    c, mock_cache = client
    mock_cache.get = AsyncMock(side_effect=["seller", "buyer"])

    row = SimpleNamespace(
        contact_id="contact-debug",
        mode="seller",
        mode_version=1,
        status="active",
        handoff_reason=None,
        human_takeover=False,
        bilingual_required=False,
        message_suppression_reason=None,
        qualification_summary={"price_expectation": 450000},
        next_recommended_action="Continue seller qualification",
        crm_sync_status="pending",
        last_inbound_at=None,
        last_outbound_at=None,
        temperature="warm",
        bot_type="seller",
        stage="Q2",
        questions_answered=2,
        metadata_json={},
        updated_at=1,
        created_at=1,
    )

    class _Result:
        def scalars(self):
            return self
        def all(self):
            return [row]

    class _Session:
        async def execute(self, *_args, **_kwargs):
            return _Result()

    class _Factory:
        async def __aenter__(self):
            return _Session()
        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr("bots.lead_bot.routes_admin.AsyncSessionFactory", lambda: _Factory())

    resp = await c.get("/admin/conversations/contact-debug", headers={"X-Admin-Key": "test-admin-key-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "seller"
    assert data["mode_version"] == 1
    assert data["qualification_summary"] == {"price_expectation": 450000}
    assert data["canonical_cache_mode"] == "seller"
    assert data["assignment_cache_mode"] == "buyer"


# ---------------------------------------------------------------------------
# 4. Buyer bot override-awareness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_buyer_questions_property_uses_defaults():
    from bots.buyer_bot.buyer_bot import JorgeBuyerBot
    from bots.buyer_bot.buyer_prompts import BUYER_QUESTIONS

    bot_settings.reset()
    bot = JorgeBuyerBot.__new__(JorgeBuyerBot)
    assert bot._questions == BUYER_QUESTIONS


@pytest.mark.asyncio
async def test_buyer_questions_property_uses_override():
    from bots.buyer_bot.buyer_bot import JorgeBuyerBot

    bot_settings.reset()
    bot_settings.update_settings("buyer", {
        "questions": {"1": "Custom Q1?", "2": "Custom Q2?", "3": "Custom Q3?", "4": "Custom Q4?"}
    })
    bot = JorgeBuyerBot.__new__(JorgeBuyerBot)
    assert bot._questions[1] == "Custom Q1?"
    assert bot._questions[4] == "Custom Q4?"


@pytest.mark.asyncio
async def test_buyer_phrases_override():
    from bots.buyer_bot.buyer_bot import JorgeBuyerBot

    bot_settings.reset()
    bot_settings.update_settings("buyer", {"jorge_phrases": ["Custom phrase A!", "Custom phrase B!"]})
    bot = JorgeBuyerBot.__new__(JorgeBuyerBot)
    phrase = bot._get_random_jorge_phrase()
    assert phrase in ["Custom phrase A!", "Custom phrase B!"]


@pytest.mark.asyncio
async def test_buyer_phrases_fallback_to_defaults():
    from bots.buyer_bot.buyer_bot import JorgeBuyerBot
    from bots.buyer_bot.buyer_prompts import JORGE_BUYER_PHRASES

    bot_settings.reset()
    bot = JorgeBuyerBot.__new__(JorgeBuyerBot)
    phrase = bot._get_random_jorge_phrase()
    assert phrase in JORGE_BUYER_PHRASES


# ---------------------------------------------------------------------------
# 5. Lead analyzer override-awareness
# ---------------------------------------------------------------------------

def test_lead_analyzer_uses_override_in_system_prompt():
    from bots.lead_bot.services.lead_analyzer import LeadAnalyzer

    bot_settings.reset()
    bot_settings.update_settings("lead", {
        "min_price": 250000,
        "max_price": 950000,
        "service_areas": "Pomona,Claremont",
    })
    analyzer = LeadAnalyzer.__new__(LeadAnalyzer)
    prompt = analyzer._get_system_prompt()
    assert "250,000" in prompt
    assert "950,000" in prompt
    assert "Pomona,Claremont" in prompt


def test_lead_analyzer_uses_config_defaults_when_no_override():
    from bots.lead_bot.services.lead_analyzer import LeadAnalyzer
    from bots.shared.config import settings

    bot_settings.reset()
    analyzer = LeadAnalyzer.__new__(LeadAnalyzer)
    prompt = analyzer._get_system_prompt()
    assert f"{settings.jorge_min_price:,}" in prompt
    assert f"{settings.jorge_max_price:,}" in prompt
