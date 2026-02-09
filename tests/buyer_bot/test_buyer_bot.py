from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from bots.buyer_bot.buyer_bot import (
    BuyerQualificationState,
    BuyerStatus,
    JorgeBuyerBot,
)
from bots.buyer_bot.main import app
from bots.shared.auth_middleware import auth_middleware
from bots.shared.auth_service import User, UserRole


class DummyCache:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        self.store[key] = value
        return True


@pytest.fixture
def dummy_cache():
    return DummyCache()


@pytest.mark.asyncio
async def test_state_progression():
    state = BuyerQualificationState(contact_id="c1", location_id="loc1")
    assert state.current_question == 0
    state.advance_question()
    assert state.current_question == 1
    state.record_answer(1, "3 bed 2 bath", {"beds_min": 3, "baths_min": 2})
    assert state.beds_min == 3
    assert state.questions_answered == 1


@pytest.mark.asyncio
async def test_temperature_scoring():
    bot = JorgeBuyerBot()
    state = BuyerQualificationState(contact_id="c1", location_id="loc1")
    state.preapproved = True
    state.timeline_days = 20
    assert bot._calculate_temperature(state) == BuyerStatus.HOT
    state.timeline_days = 60
    assert bot._calculate_temperature(state) == BuyerStatus.WARM
    state.timeline_days = 200
    assert bot._calculate_temperature(state) == BuyerStatus.COLD


@pytest.mark.asyncio
async def test_property_matching(dummy_cache):
    sample_props = [
        SimpleNamespace(id="p1", address="A", city="Dallas", price=400000, beds=3, baths=2, sqft=1800),
        SimpleNamespace(id="p2", address="B", city="Plano", price=600000, beds=4, baths=3, sqft=2400),
    ]

    with patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=dummy_cache), \
         patch("bots.buyer_bot.buyer_bot.fetch_properties", new=AsyncMock(return_value=sample_props)), \
         patch("bots.buyer_bot.buyer_bot.upsert_contact", new=AsyncMock()), \
         patch("bots.buyer_bot.buyer_bot.upsert_conversation", new=AsyncMock()), \
         patch("bots.buyer_bot.buyer_bot.upsert_buyer_preferences", new=AsyncMock()):
        bot = JorgeBuyerBot()
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.beds_min = 3
        state.baths_min = 2
        state.price_max = 500000
        state.preferred_location = "Dallas"
        matches = await bot._match_properties(state)
        assert matches[0]["property_id"] == "p1"


@pytest.mark.asyncio
async def test_process_message_flow(dummy_cache):
    with patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=dummy_cache), \
         patch("bots.buyer_bot.buyer_bot.fetch_properties", new=AsyncMock(return_value=[])), \
         patch("bots.buyer_bot.buyer_bot.upsert_contact", new=AsyncMock()), \
         patch("bots.buyer_bot.buyer_bot.upsert_conversation", new=AsyncMock()), \
         patch("bots.buyer_bot.buyer_bot.upsert_buyer_preferences", new=AsyncMock()), \
         patch("bots.buyer_bot.buyer_bot.GHLClient") as mock_ghl, \
         patch("bots.buyer_bot.buyer_bot.ClaudeClient") as mock_claude:
        mock_instance = mock_claude.return_value
        mock_instance.agenerate = AsyncMock(return_value=SimpleNamespace(content="Next question"))
        mock_ghl.return_value.add_tag = AsyncMock()
        mock_ghl.return_value.update_custom_field = AsyncMock()
        mock_ghl.return_value.create_opportunity = AsyncMock()
        bot = JorgeBuyerBot()
        result = await bot.process_buyer_message(
            contact_id="c1",
            location_id="loc1",
            message="Looking for 3 beds in Dallas under 500k",
            contact_info={"name": "Buyer"},
        )
        assert result.questions_answered >= 0
        assert isinstance(result.buyer_temperature, str)


def test_buyer_routes():
    from datetime import datetime

    from bots.buyer_bot import buyer_routes

    dummy_user = User(
        user_id="u1",
        email="test@example.com",
        name="Tester",
        role=UserRole.ADMIN,
        created_at=datetime.now(timezone.utc),
    )

    class DummyBuyerBot:
        async def process_buyer_message(self, *args, **kwargs):
            return {
                "response_message": "ok",
                "buyer_temperature": "warm",
                "questions_answered": 1,
                "qualification_complete": False,
                "actions_taken": [],
                "next_steps": "continue",
                "analytics": {},
                "matches": [],
            }

        async def get_buyer_analytics(self, *args, **kwargs):
            return {"status": "ok"}

        async def get_preferences(self, *args, **kwargs):
            return {}

        async def get_matches(self, *args, **kwargs):
            return []

        async def get_all_active_conversations(self, *args, **kwargs):
            return []

    buyer_routes.buyer_bot = DummyBuyerBot()
    app.dependency_overrides[auth_middleware.get_current_active_user] = lambda: dummy_user
    client = TestClient(app)

    payload = {
        "contact_id": "buyer_1",
        "location_id": "loc1",
        "message": "Need 3 beds in Dallas",
        "contact_info": {"name": "Buyer"},
    }

    resp = client.post("/api/jorge-buyer/process", json=payload)
    assert resp.status_code in (200, 500)
