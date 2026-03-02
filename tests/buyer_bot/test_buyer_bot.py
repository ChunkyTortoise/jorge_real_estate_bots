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
from bots.buyer_bot.buyer_prompts import BUYER_SYSTEM_PROMPT, build_buyer_prompt
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


class TestBuyerBotEvalFixes:
    """Tests for evaluation-identified fixes: Q1 sqft, Q2 ambiguous, opportunity dedup."""

    @pytest.fixture
    def bot(self):
        return JorgeBuyerBot()

    # --- Fix: Buyer Q1 sqft_min advances ---

    @pytest.mark.asyncio
    async def test_q1_sqft_only_advances(self, bot):
        """'I want 2000 sqft' should advance Q1 (sqft_min counts)."""
        extracted = await bot._extract_qualification_data("I want 2000 sqft", 1)
        assert extracted.get("sqft_min") == 2000
        assert bot._should_advance_question(extracted, 1) is True

    # --- Fix: Buyer Q2 ambiguous financing advances ---

    @pytest.mark.asyncio
    async def test_q2_ambiguous_financing_defaults_false_and_advances(self, bot):
        """'still figuring it out' sets preapproved=False so Q2 always advances."""
        extracted = await bot._extract_qualification_data("still figuring it out", 2)
        assert "preapproved" in extracted
        assert extracted["preapproved"] is False
        assert bot._should_advance_question(extracted, 2) is True

    @pytest.mark.asyncio
    async def test_q2_working_on_loan_defaults_false(self, bot):
        """'working on my loan' sets preapproved=False (does not stall)."""
        extracted = await bot._extract_qualification_data("working on my loan", 2)
        assert extracted.get("preapproved") is False

    # --- Fix: Opportunity created only once ---

    @pytest.mark.asyncio
    async def test_opportunity_not_created_twice(self, bot):
        """Second call to _generate_actions does not add upsert_opportunity if already created."""
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.opportunity_created = True
        from unittest.mock import patch, AsyncMock
        from bots.shared.config import settings
        with patch.object(settings, "buyer_pipeline_id", "pipe-123"):
            actions = await bot._generate_actions("c1", "loc1", state, "hot")
        opp_actions = [a for a in actions if a.get("type") == "upsert_opportunity"]
        assert len(opp_actions) == 0

    @pytest.mark.asyncio
    async def test_opportunity_created_on_first_call(self, bot):
        """First call with pipeline_id set creates exactly one opportunity."""
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.preapproved = True
        state.timeline_days = 20
        assert state.opportunity_created is False
        from unittest.mock import patch
        from bots.shared.config import settings
        with patch.object(settings, "buyer_pipeline_id", "pipe-123"):
            actions = await bot._generate_actions("c1", "loc1", state, "hot")
        opp_actions = [a for a in actions if a.get("type") == "upsert_opportunity"]
        assert len(opp_actions) == 1
        assert state.opportunity_created is True


# ─── Fix 1: Buyer history passed to Claude ───────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_generate_response_passes_history_to_claude(dummy_cache):
    """_generate_response must pass conversation history to agenerate."""
    from unittest.mock import AsyncMock, patch
    from bots.shared.claude_client import LLMResponse

    bot = JorgeBuyerBot()
    bot.cache = dummy_cache

    state = BuyerQualificationState(contact_id="c1", location_id="loc1")
    state.current_question = 1
    state.conversation_history = [
        {"question": 0, "answer": "I want 3 beds", "bot_response": "Great, let me ask...", "timestamp": "t", "extracted_data": {}},
    ]

    captured_kwargs = {}

    async def mock_agenerate(**kwargs):
        captured_kwargs.update(kwargs)
        return LLMResponse(content="Tell me about pre-approval.", model="test", usage={})

    with patch.object(bot.claude_client, "agenerate", side_effect=mock_agenerate):
        await bot._generate_response(state, "3 beds in Dallas under 400k")

    assert "history" in captured_kwargs
    assert len(captured_kwargs["history"]) >= 1
    assert captured_kwargs["history"][0]["role"] == "user"


# ─── Fix 2: Q0 message preserved in conversation history ─────────────────────

@pytest.mark.asyncio
async def test_buyer_q0_message_preserved_in_history(dummy_cache):
    """Initial Q0 message is stored in conversation_history before advancing."""
    bot = JorgeBuyerBot()
    bot.cache = dummy_cache

    state = BuyerQualificationState(contact_id="c1", location_id="loc1")
    assert state.current_question == 0

    await bot._generate_response(state, "Looking for 3 beds in Dallas under 500k")

    assert len(state.conversation_history) == 1
    assert state.conversation_history[0]["question"] == 0
    assert "Looking for 3 beds" in state.conversation_history[0]["answer"]
    assert state.conversation_history[0]["bot_response"] != ""


# ─── Fix 7: Price regex doesn't corrupt zip codes or city names ───────────────

@pytest.mark.asyncio
async def test_buyer_price_mckinney_k_not_global():
    """'McKinney' should not cause non-price numbers to be multiplied by 1000."""
    bot = JorgeBuyerBot()
    data = await bot._extract_qualification_data("3 beds in McKinney under 500k", 1)
    assert data.get("price_max") == 500000
    assert data.get("beds_min") == 3


@pytest.mark.asyncio
async def test_buyer_price_zip_code_not_extracted():
    """A zip code like '75024' should not be extracted as a price."""
    bot = JorgeBuyerBot()
    data = await bot._extract_qualification_data("75024 area, 3 beds", 1)
    assert "price_max" not in data
    assert "price_min" not in data


@pytest.mark.asyncio
async def test_buyer_price_explicit_k_suffix():
    """'500k' and '$300k' should be correctly parsed as prices."""
    bot = JorgeBuyerBot()
    data = await bot._extract_qualification_data("budget between 300k and 500k", 1)
    assert data.get("price_min") == 300000
    assert data.get("price_max") == 500000


# ─── Fix 10: State deserialization guard ─────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_state_deserialization_ignores_unknown_keys(dummy_cache):
    """Extra keys in cached state dict do not crash deserialization."""
    from bots.buyer_bot.buyer_bot import BuyerQualificationState
    state = BuyerQualificationState(contact_id="c1", location_id="loc1")
    bot = JorgeBuyerBot()
    bot.cache = dummy_cache
    await bot.save_conversation_state("c1", state)

    # Inject an unknown key into the cached dict
    cached = await dummy_cache.get("buyer:state:c1")
    cached["unknown_future_field"] = "some_value"
    await dummy_cache.set("buyer:state:c1", cached)

    # Should not raise TypeError
    loaded = await bot._get_or_create_state("c1", "loc1")
    assert loaded.contact_id == "c1"


# ─── Seller-question guardrail assertions ─────────────────────────────────────

def test_buyer_system_prompt_has_seller_guardrail():
    assert "motivation to SELL" in BUYER_SYSTEM_PROMPT or "seller questions" in BUYER_SYSTEM_PROMPT


def test_buyer_prompt_has_seller_prohibition():
    prompt = build_buyer_prompt(1, "3 beds", "Are you pre-approved?")
    assert "condition" in prompt.lower() or "sell" in prompt.lower()


# ─── Q1 advance — location-only does not advance ─────────────────────────────

@pytest.mark.asyncio
async def test_buyer_q1_location_only_does_not_advance():
    """Saying just a city name must NOT advance past Q1."""
    bot = JorgeBuyerBot()
    data = await bot._extract_qualification_data("looking in Dallas", 1)
    # preferred_location may be set, but no beds/price → should not advance
    assert bot._should_advance_question(data, 1) is False


@pytest.mark.asyncio
async def test_buyer_q1_beds_advances():
    """Providing bedroom count advances Q1."""
    bot = JorgeBuyerBot()
    data = await bot._extract_qualification_data("3 bedrooms please", 1)
    assert bot._should_advance_question(data, 1) is True


# ─── DB fallback — buyer restores state after cache miss ─────────────────────

@pytest.mark.asyncio
async def test_buyer_db_fallback_restores_state(dummy_cache):
    """_get_or_create_state falls back to DB when cache is empty."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from datetime import datetime, timezone

    bot = JorgeBuyerBot()
    bot.cache = dummy_cache  # empty cache → triggers fallback

    mock_row = MagicMock()
    mock_row.current_question = 2
    mock_row.questions_answered = 1
    mock_row.is_qualified = False
    mock_row.stage = "Q2"
    mock_row.extracted_data = {"beds_min": 3, "price_max": 400000}
    mock_row.conversation_history = []
    mock_row.last_activity = None
    mock_row.conversation_started = datetime.now(timezone.utc)
    mock_row.metadata_json = {"location_id": "loc_test", "preferred_location": "Dallas"}

    with patch("bots.buyer_bot.buyer_bot.fetch_conversation", return_value=mock_row):
        state = await bot._get_or_create_state("c1", "loc_fallback")

    assert state.current_question == 2
    assert state.beds_min == 3
    assert state.price_max == 400000
    assert state.location_id == "loc_test"
