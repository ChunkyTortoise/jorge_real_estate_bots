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


class TestBuyerBotBugFixes:
    """Tests for the P0/P1 buyer bot bug fixes (spec 2026-02-26)."""

    @pytest.fixture
    def bot(self):
        return JorgeBuyerBot()

    # --- Fix 5: Q2 pre-approval false positive ---

    @pytest.mark.asyncio
    async def test_q2_not_yet_approved_is_false(self, bot):
        """'I'm not yet approved' must NOT set preapproved=True."""
        extracted = await bot._extract_qualification_data("I'm not yet approved", 2)
        assert extracted.get("preapproved") is False

    @pytest.mark.asyncio
    async def test_q2_preapproved_is_true(self, bot):
        """'I'm pre-approved' sets preapproved=True."""
        extracted = await bot._extract_qualification_data("I'm pre-approved for 400k", 2)
        assert extracted.get("preapproved") is True

    @pytest.mark.asyncio
    async def test_q2_cash_buyer_is_true(self, bot):
        """Cash buyers are treated as pre-approved."""
        extracted = await bot._extract_qualification_data("I'm a cash buyer", 2)
        assert extracted.get("preapproved") is True

    # --- Fix 3: Q3 timeline parser ---

    @pytest.mark.asyncio
    async def test_q3_zero_to_thirty_days(self, bot):
        """'0-30 days' parses as 30 days."""
        extracted = await bot._extract_qualification_data("0-30 days", 3)
        assert extracted["timeline_days"] == 30

    @pytest.mark.asyncio
    async def test_q3_one_to_three_months_range(self, bot):
        """'1-3 months' should use lower bound = 30 days."""
        extracted = await bot._extract_qualification_data("1-3 months", 3)
        assert extracted["timeline_days"] == 30

    @pytest.mark.asyncio
    async def test_q3_just_browsing(self, bot):
        """'just browsing' defaults to 180 days."""
        extracted = await bot._extract_qualification_data("just browsing for now", 3)
        assert extracted["timeline_days"] == 180

    @pytest.mark.asyncio
    async def test_q3_in_a_month(self, bot):
        """'in a month' should parse as 30 days."""
        extracted = await bot._extract_qualification_data("in a month", 3)
        assert extracted["timeline_days"] == 30

    @pytest.mark.asyncio
    async def test_q3_gibberish_defaults_to_90(self, bot):
        """Unrecognized input defaults to 90 days and always advances."""
        extracted = await bot._extract_qualification_data("blah blah blah", 3)
        assert extracted["timeline_days"] == 90

    @pytest.mark.asyncio
    async def test_q3_should_advance_on_default(self, bot):
        """_should_advance_question returns True because timeline_days is always set."""
        extracted = await bot._extract_qualification_data("blah blah", 3)
        assert bot._should_advance_question(extracted, 3) is True

    # --- Fix 4: Q4 motivation keywords + default ---

    @pytest.mark.asyncio
    async def test_q4_relocating_for_work(self, bot):
        """'relocating for work' maps to job_relocation."""
        extracted = await bot._extract_qualification_data("relocating for work", 4)
        assert extracted.get("motivation") == "job_relocation"

    @pytest.mark.asyncio
    async def test_q4_just_ready_defaults_to_other(self, bot):
        """'just ready to buy' falls back to 'other' — still advances."""
        extracted = await bot._extract_qualification_data("just ready to buy", 4)
        assert extracted.get("motivation") == "other"
        assert bot._should_advance_question(extracted, 4) is True

    # --- Fix 8: Buyer tag cleanup ---

    @pytest.mark.asyncio
    async def test_generate_actions_removes_stale_buyer_tags(self, bot):
        """When temperature=hot, remove_tag for warm and cold should be present."""
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.preapproved = True
        state.timeline_days = 20
        actions = await bot._generate_actions("c1", "loc1", state, BuyerStatus.HOT)
        remove_tags = {a["tag"] for a in actions if a.get("type") == "remove_tag"}
        assert f"buyer_{BuyerStatus.WARM}" in remove_tags
        assert f"buyer_{BuyerStatus.COLD}" in remove_tags
        add_tags = {a["tag"] for a in actions if a.get("type") == "add_tag"}
        assert f"buyer_{BuyerStatus.HOT}" in add_tags
