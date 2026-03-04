"""
Tests for admin API key auth, buyer overrides, reset-state, and lead settings.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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
    mock_cache.delete.assert_called_once_with("buyer:state:contact-abc")


@pytest.mark.asyncio
async def test_admin_reset_state_invalid_bot(client):
    c, _ = client
    resp = await c.delete(
        "/admin/reset-state/lead/contact-abc",
        headers={"X-Admin-Key": "test-admin-key-123"},
    )
    assert resp.status_code == 400


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
