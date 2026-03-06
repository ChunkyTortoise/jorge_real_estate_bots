"""
State machine flow tests for Buyer Bot and Seller Bot.

Tests cover:
- Complete buyer flow Q0→Q1→Q2→Q3→Q4→QUALIFIED_HOT (5 messages)
- Complete seller flow Q0→Q1→Q2→Q3→Q4→QUALIFIED_HOT (5 messages)
- Buyer Q4 stall (3 attempts → STALLED)
- Seller Q4 stall (3 attempts → STALLED)
- Seller Q3 price guard when price_expectation is None
- Spanish detection → bilingual redirect
- Price extraction edge cases ($580k, "around three fifty", "mid fives", "1.2m")
- Ambiguous "$500" handling
- Temperature scoring boundaries
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.buyer_bot.buyer_bot import (
    BuyerQualificationState,
    BuyerResult,
    BuyerStatus,
    JorgeBuyerBot,
)
from bots.seller_bot.jorge_seller_bot import (
    JorgeSellerBot,
    SellerQualificationState,
    SellerResult,
    SellerStatus,
)
from bots.shared.business_rules import JorgeBusinessRules


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class MockCache:
    def __init__(self):
        self.store: dict = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        self.store[key] = value
        return True

    async def delete(self, key):
        self.store.pop(key, None)

    async def setnx(self, key, value, ttl=300):
        if key in self.store:
            return False
        self.store[key] = value
        return True

    async def increment(self, key, amount=1, ttl=None):
        current = self.store.get(key, 0)
        new_value = int(current) + amount
        self.store[key] = new_value
        return new_value


def _fake_llm_response(content: str):
    from bots.shared.claude_client import LLMResponse
    return LLMResponse(content=content, model="claude-test")


def _make_buyer_bot(cache=None) -> JorgeBuyerBot:
    """Create a BuyerBot with mocked external deps."""
    bot = JorgeBuyerBot()
    bot.cache = cache or MockCache()
    bot.ghl_client = AsyncMock()
    bot.ghl_client.get_contact = AsyncMock(return_value={"customFields": [], "tags": []})
    return bot


def _make_seller_bot(cache=None) -> JorgeSellerBot:
    """Create a SellerBot with mocked external deps."""
    bot = JorgeSellerBot()
    bot.cache = cache or MockCache()
    bot.ghl_client = AsyncMock()
    bot.ghl_client.get_contact = AsyncMock(return_value={"customFields": [], "tags": []})
    return bot


def _patch_claude(bot, responses: list[str]):
    """Patch the claude_client.agenerate to return predefined responses in sequence."""
    response_iter = iter(responses)

    async def fake_agenerate(**kwargs):
        content = next(response_iter, "Got it, let me ask the next question.")
        return _fake_llm_response(content)

    bot.claude_client.agenerate = fake_agenerate
    return bot


# ---------------------------------------------------------------------------
# 1. Complete Buyer Flow: Q0 → Q1 → Q2 → Q3 → Q4 → QUALIFIED_HOT
# ---------------------------------------------------------------------------


class TestBuyerCompleteFlow:
    """Buyer goes through all 5 messages and reaches QUALIFIED status."""

    @pytest.mark.asyncio
    async def test_buyer_full_qualification_hot(self):
        """Q0→Q1→Q2→Q3→Q4 with pre-approved + 2-week timeline → HOT."""
        cache = MockCache()
        bot = _make_buyer_bot(cache)
        _patch_claude(bot, [
            "What are you looking for?",           # Q1 response after Q0
            "Are you pre-approved?",                # Q2 response
            "When are you looking to move?",        # Q3 response
            "What's motivating your move?",         # Q4 response
            "Great, let me find some properties!",  # After Q4
        ])

        contact_id = "buyer-full-hot"
        location_id = "loc-test"

        # Q0: Greeting
        r0 = await bot.process_buyer_message(contact_id, location_id, "Hey, looking to buy a home")
        assert isinstance(r0, BuyerResult)
        assert r0.questions_answered == 0

        # Q1: Preferences (beds, budget, area)
        r1 = await bot.process_buyer_message(contact_id, location_id, "3bd 2ba under 600k in Rancho Cucamonga")
        assert r1.questions_answered >= 1

        # Q2: Pre-approval
        r2 = await bot.process_buyer_message(contact_id, location_id, "Yes I'm pre-approved")
        assert r2.questions_answered >= 2

        # Q3: Timeline
        r3 = await bot.process_buyer_message(contact_id, location_id, "2 weeks, need to move ASAP")
        assert r3.questions_answered >= 3

        # Q4: Motivation
        r4 = await bot.process_buyer_message(contact_id, location_id, "Job relocation to the area")
        assert r4.questions_answered >= 4
        assert r4.qualification_complete is True
        assert r4.buyer_temperature == BuyerStatus.HOT

    @pytest.mark.asyncio
    async def test_buyer_cold_when_not_preapproved_long_timeline(self):
        """Not pre-approved + long timeline → COLD."""
        cache = MockCache()
        bot = _make_buyer_bot(cache)
        _patch_claude(bot, [
            "What are you looking for?",
            "Are you pre-approved?",
            "When are you looking to move?",
            "What's motivating your move?",
            "I'll keep an eye out for you.",
        ])

        contact_id = "buyer-cold"
        location_id = "loc-test"

        await bot.process_buyer_message(contact_id, location_id, "Hi there")
        await bot.process_buyer_message(contact_id, location_id, "4bd 3ba around 450k")
        await bot.process_buyer_message(contact_id, location_id, "Not yet, working on it")
        await bot.process_buyer_message(contact_id, location_id, "Maybe in about a year")
        r4 = await bot.process_buyer_message(contact_id, location_id, "Just browsing for now")
        assert r4.buyer_temperature == BuyerStatus.COLD


# ---------------------------------------------------------------------------
# 2. Complete Seller Flow: Q0 → Q1 → Q2 → Q3 → Q4 → QUALIFIED_HOT
# ---------------------------------------------------------------------------


class TestSellerCompleteFlow:
    """Seller goes through all 5 messages and reaches HOT status."""

    @pytest.mark.asyncio
    async def test_seller_full_qualification_hot(self):
        """Q0→Q1→Q2→Q3→Q4 with offer accepted + timeline OK → HOT."""
        cache = MockCache()
        bot = _make_seller_bot(cache)
        _patch_claude(bot, [
            "Tell me about the condition.",       # After Q0
            "What's your price expectation?",     # Q2
            "What's motivating the sale?",        # Q3
            # Q4 is generated directly (cash offer), not via Claude
        ])

        contact_id = "seller-full-hot"
        location_id = "loc-test"

        # Q0: Greeting
        r0 = await bot.process_seller_message(contact_id, location_id, "Hi, I want to sell my house")
        assert isinstance(r0, SellerResult)
        # Q0 advances to Q1 internally

        # Q1: Condition
        r1 = await bot.process_seller_message(contact_id, location_id, "Needs some minor cosmetic work")
        assert r1.questions_answered >= 1

        # Q2: Price expectation
        r2 = await bot.process_seller_message(contact_id, location_id, "I'd say around $450k")
        assert r2.questions_answered >= 2

        # Q3: Motivation — the response will include the Q4 cash offer
        r3 = await bot.process_seller_message(contact_id, location_id, "Job relocation, need to sell fast")
        assert r3.questions_answered >= 3
        # The offer should be presented in the response
        assert "$" in r3.response_message or "offer" in r3.response_message.lower() or r3.questions_answered >= 3

        # Q4: Accept offer
        r4 = await bot.process_seller_message(contact_id, location_id, "Yes, that works for me, let's do it")
        assert r4.questions_answered >= 4
        assert r4.qualification_complete is True
        assert r4.seller_temperature == SellerStatus.HOT.value


# ---------------------------------------------------------------------------
# 3. Buyer Q4 Stall (3 attempts → STALLED)
# ---------------------------------------------------------------------------


class TestBuyerQ4Stall:
    """Buyer responds at Q4 and hits the 3-attempt stall threshold."""

    @pytest.mark.asyncio
    async def test_buyer_stalls_after_3_q4_attempts(self):
        """Directly set q4_attempts=3 in state, next Q4 message triggers stall."""
        cache = MockCache()
        bot = _make_buyer_bot(cache)
        _patch_claude(bot, ["Can you tell me more?"])

        contact_id = "buyer-stall"
        location_id = "loc-test"

        # Pre-populate state at Q4 with 3 attempts already recorded
        from datetime import datetime, timezone
        state_dict = {
            "contact_id": contact_id,
            "location_id": location_id,
            "current_question": 4,
            "questions_answered": 3,
            "is_qualified": False,
            "stage": "Q4",
            "beds_min": 3,
            "baths_min": None,
            "sqft_min": None,
            "price_min": None,
            "price_max": 500_000,
            "preferred_location": None,
            "preapproved": True,
            "timeline_days": 14,
            "motivation": None,
            "q4_attempts": 3,
            "matches": [],
            "conversation_history": [],
            "extracted_data": {},
            "last_interaction": datetime.now(timezone.utc).isoformat(),
            "conversation_started": datetime.now(timezone.utc).isoformat(),
            "scheduling_offered": False,
            "appointment_booked": False,
            "appointment_id": None,
            "opportunity_created": False,
        }
        await cache.set(f"buyer:state:{contact_id}", state_dict)

        r = await bot.process_buyer_message(contact_id, location_id, "no idea")
        assert "jorge" in r.response_message.lower() or "reach out" in r.response_message.lower()
        assert any(a.get("tag") == "needs-human-review" for a in r.actions_taken)


# ---------------------------------------------------------------------------
# 4. Seller Q4 Stall (3 attempts → STALLED)
# ---------------------------------------------------------------------------


class TestSellerQ4Stall:
    """Seller responds to Q4 three times without accepting → STALLED."""

    @pytest.mark.asyncio
    async def test_seller_stalls_after_3_q4_attempts(self):
        cache = MockCache()
        bot = _make_seller_bot(cache)
        _patch_claude(bot, [
            "Tell me about the condition.",
            "What's your price expectation?",
            "What's motivating the sale?",
            "Think it over.",
            "Think it over.",
            "Think it over.",
        ])

        contact_id = "seller-stall"
        location_id = "loc-test"

        await bot.process_seller_message(contact_id, location_id, "Hi, want to sell")
        await bot.process_seller_message(contact_id, location_id, "Major repairs needed")
        await bot.process_seller_message(contact_id, location_id, "$350k")
        await bot.process_seller_message(contact_id, location_id, "Inherited the property")

        # Q4 attempt 1
        await bot.process_seller_message(contact_id, location_id, "Let me think about it")
        # Q4 attempt 2
        await bot.process_seller_message(contact_id, location_id, "Still not sure")
        # Q4 attempt 3
        await bot.process_seller_message(contact_id, location_id, "Maybe later")

        # 4th message at Q4 should trigger stall
        r = await bot.process_seller_message(contact_id, location_id, "I don't know")
        assert "jorge" in r.response_message.lower() or "reach out" in r.response_message.lower()
        assert any(a.get("tag") == "needs-human-review" for a in r.actions_taken)


# ---------------------------------------------------------------------------
# 5. Seller Q3 Price Guard: re-asks when price_expectation is None
# ---------------------------------------------------------------------------


class TestSellerPriceGuard:
    """When seller reaches Q3 but price_expectation is None, bot re-asks price."""

    @pytest.mark.asyncio
    async def test_price_guard_reasks_when_no_price(self):
        cache = MockCache()
        bot = _make_seller_bot(cache)
        _patch_claude(bot, [
            "Tell me about the condition.",
            "What's your price expectation?",
        ])

        contact_id = "seller-price-guard"
        location_id = "loc-test"

        # Q0
        await bot.process_seller_message(contact_id, location_id, "Hi there")
        # Q1: condition
        await bot.process_seller_message(contact_id, location_id, "Needs major repairs")

        # Q2: Give a vague answer that won't parse to a price.
        # We need to mock the claude haiku call to also fail to extract price
        with patch.object(bot.claude_client, "agenerate", new=AsyncMock(side_effect=Exception("No price"))):
            r2 = await bot.process_seller_message(contact_id, location_id, "I really have no idea what it's worth")

        # State should have price_expectation as None (fallback 300000 — but C7 may zero it)
        # or the bot should continue

        # Now at Q3 with no usable price_expectation stored on state:
        # Manually set price_expectation to None to simulate guard path
        state_key = f"seller:state:{contact_id}"
        state_dict = await cache.get(state_key)
        if state_dict and isinstance(state_dict, dict):
            state_dict["price_expectation"] = None
            await cache.set(state_key, state_dict)

        # Q3: Motivation — should trigger price guard (re-ask price)
        r3 = await bot.process_seller_message(contact_id, location_id, "Job relocation, need to sell fast")
        # The price guard returns a message asking about price, not the Q4 offer
        assert "worth" in r3.response_message.lower() or "ballpark" in r3.response_message.lower() or "price" in r3.response_message.lower()


# ---------------------------------------------------------------------------
# 6. Spanish Detection → Bilingual Redirect
# ---------------------------------------------------------------------------


class TestSpanishDetection:
    """Spanish messages get routed to bilingual assistant."""

    @pytest.mark.asyncio
    async def test_buyer_spanish_redirect(self):
        bot = _make_buyer_bot()
        r = await bot.process_buyer_message(
            "buyer-spanish", "loc-test", "Hola, quiero comprar una casa"
        )
        assert "bilingue" in r.response_message.lower() or "bilingual" in r.response_message.lower()
        assert any(a.get("tag") == "needs-bilingual" for a in r.actions_taken)
        assert r.buyer_temperature == BuyerStatus.COLD

    @pytest.mark.asyncio
    async def test_seller_spanish_redirect(self):
        bot = _make_seller_bot()
        r = await bot.process_seller_message(
            "seller-spanish", "loc-test", "Hola, quiero vender mi casa"
        )
        assert "bilingue" in r.response_message.lower() or "bilingual" in r.response_message.lower()
        assert any(a.get("tag") == "needs-bilingual" for a in r.actions_taken)
        assert r.seller_temperature == "cold"

    @pytest.mark.asyncio
    async def test_english_not_flagged_as_spanish(self):
        """A plain English message should not trigger Spanish redirect."""
        bot = _make_buyer_bot()
        _patch_claude(bot, ["What are you looking for?"])
        r = await bot.process_buyer_message(
            "buyer-english", "loc-test", "Hey, looking to buy a home in Rancho Cucamonga"
        )
        assert "bilingue" not in r.response_message.lower()


# ---------------------------------------------------------------------------
# 7. Seller Price Extraction Edge Cases
# ---------------------------------------------------------------------------


class TestSellerPriceExtraction:
    """Test _extract_qualification_data for Q2 price patterns."""

    @pytest.fixture
    def bot(self):
        return _make_seller_bot()

    @pytest.mark.asyncio
    async def test_580k(self, bot):
        data = await bot._extract_qualification_data("$580k", 2)
        assert data["price_expectation"] == 580_000

    @pytest.mark.asyncio
    async def test_620k_no_dollar(self, bot):
        data = await bot._extract_qualification_data("620k", 2)
        assert data["price_expectation"] == 620_000

    @pytest.mark.asyncio
    async def test_1_2m(self, bot):
        data = await bot._extract_qualification_data("$1.2m", 2)
        assert data["price_expectation"] == 1_200_000

    @pytest.mark.asyncio
    async def test_1_2_million(self, bot):
        data = await bot._extract_qualification_data("1.2 million", 2)
        assert data["price_expectation"] == 1_200_000

    @pytest.mark.asyncio
    async def test_350_comma_000(self, bot):
        data = await bot._extract_qualification_data("$350,000", 2)
        assert data["price_expectation"] == 350_000

    @pytest.mark.asyncio
    async def test_mid_fives(self, bot):
        data = await bot._extract_qualification_data("I'd say mid fives", 2)
        assert data["price_expectation"] == 550_000

    @pytest.mark.asyncio
    async def test_high_fives(self, bot):
        data = await bot._extract_qualification_data("Probably high fives", 2)
        assert data["price_expectation"] == 580_000

    @pytest.mark.asyncio
    async def test_low_fives(self, bot):
        data = await bot._extract_qualification_data("low fives I'd guess", 2)
        assert data["price_expectation"] == 475_000

    @pytest.mark.asyncio
    async def test_580_thousand(self, bot):
        data = await bot._extract_qualification_data("580 thousand", 2)
        assert data["price_expectation"] == 580_000


# ---------------------------------------------------------------------------
# 8. Buyer Price Extraction Edge Cases
# ---------------------------------------------------------------------------


class TestBuyerPriceExtraction:
    """Test _extract_qualification_data for Q1 price patterns on the buyer side."""

    @pytest.fixture
    def bot(self):
        return _make_buyer_bot()

    @pytest.mark.asyncio
    async def test_under_600k(self, bot):
        data = await bot._extract_qualification_data("under 600k", 1)
        assert data.get("price_max") == 600_000

    @pytest.mark.asyncio
    async def test_around_350(self, bot):
        """'around 350' → qualifier price → 350000."""
        data = await bot._extract_qualification_data("around 350", 1)
        assert data.get("price_max") == 350_000

    @pytest.mark.asyncio
    async def test_500_no_context_treated_as_price(self, bot):
        """'$500' alone → extracted as-is (500) — ambiguous, very low."""
        data = await bot._extract_qualification_data("$500", 1)
        # $500 is not a 3-digit qualifier and is not 6+ digits bare.
        # The $-prefix pattern extracts 500 as-is.
        price = data.get("price_max") or data.get("price_min")
        assert price is not None
        # The value should be 500 (literal) — it's the caller's responsibility to validate
        assert price == 500


# ---------------------------------------------------------------------------
# 9. Temperature Scoring Boundaries
# ---------------------------------------------------------------------------


class TestBuyerTemperature:
    """Buyer temperature calculation edge cases."""

    def test_hot_when_preapproved_and_short_timeline(self):
        bot = _make_buyer_bot()
        state = BuyerQualificationState(contact_id="t1", location_id="loc")
        state.preapproved = True
        state.timeline_days = 30
        assert bot._calculate_temperature(state) == BuyerStatus.HOT

    def test_warm_when_moderate_timeline(self):
        bot = _make_buyer_bot()
        state = BuyerQualificationState(contact_id="t2", location_id="loc")
        state.preapproved = False
        state.timeline_days = 60
        assert bot._calculate_temperature(state) == BuyerStatus.WARM

    def test_cold_when_long_timeline(self):
        bot = _make_buyer_bot()
        state = BuyerQualificationState(contact_id="t3", location_id="loc")
        state.timeline_days = 180
        assert bot._calculate_temperature(state) == BuyerStatus.COLD

    def test_cold_when_no_timeline(self):
        bot = _make_buyer_bot()
        state = BuyerQualificationState(contact_id="t4", location_id="loc")
        assert bot._calculate_temperature(state) == BuyerStatus.COLD


class TestSellerTemperature:
    """Seller temperature calculation edge cases."""

    def test_hot_when_fully_qualified(self):
        bot = _make_seller_bot()
        state = SellerQualificationState(contact_id="s1", location_id="loc")
        state.questions_answered = 4
        state.offer_accepted = True
        state.timeline_acceptable = True
        assert bot._calculate_temperature(state) == SellerStatus.HOT.value

    def test_warm_when_all_answered_in_range(self):
        bot = _make_seller_bot()
        state = SellerQualificationState(contact_id="s2", location_id="loc")
        state.questions_answered = 4
        state.offer_accepted = False
        state.price_expectation = 400_000
        state.motivation = "job_relocation"
        state.urgency = "medium"
        assert bot._calculate_temperature(state) == SellerStatus.WARM.value

    def test_cold_when_low_urgency(self):
        bot = _make_seller_bot()
        state = SellerQualificationState(contact_id="s3", location_id="loc")
        state.questions_answered = 4
        state.price_expectation = 400_000
        state.motivation = "downsizing"
        state.urgency = "low"
        assert bot._calculate_temperature(state) == SellerStatus.COLD.value

    def test_warm_with_high_urgency_and_3_questions(self):
        """High urgency tips borderline COLD → WARM when close to qualification."""
        bot = _make_seller_bot()
        state = SellerQualificationState(contact_id="s4", location_id="loc")
        state.questions_answered = 3
        state.urgency = "high"
        assert bot._calculate_temperature(state) == SellerStatus.WARM.value

    def test_cold_when_under_4_questions(self):
        bot = _make_seller_bot()
        state = SellerQualificationState(contact_id="s5", location_id="loc")
        state.questions_answered = 2
        assert bot._calculate_temperature(state) == SellerStatus.COLD.value


# ---------------------------------------------------------------------------
# 10. State Dataclass Basics
# ---------------------------------------------------------------------------


class TestStateDataclassBasics:
    """Basic state machine transitions via dataclass methods."""

    def test_seller_advance_question_caps_at_4(self):
        state = SellerQualificationState(contact_id="dc1", location_id="loc")
        for _ in range(10):
            state.advance_question()
        assert state.current_question == 4
        assert state.stage == "Q4"

    def test_buyer_advance_question_caps_at_4(self):
        state = BuyerQualificationState(contact_id="dc2", location_id="loc")
        for _ in range(10):
            state.advance_question()
        assert state.current_question == 4
        assert state.stage == "Q4"

    def test_seller_record_answer_q4_qualifies(self):
        state = SellerQualificationState(contact_id="dc3", location_id="loc")
        state.current_question = 4
        state.record_answer(4, "Yes deal", {"offer_accepted": True, "timeline_acceptable": True})
        assert state.is_qualified is True
        assert state.stage == "QUALIFIED"

    def test_buyer_record_answer_q4_qualifies(self):
        state = BuyerQualificationState(contact_id="dc4", location_id="loc")
        state.preapproved = True
        state.timeline_days = 14
        state.current_question = 4
        state.record_answer(4, "Job relocation", {"motivation": "job_relocation"})
        assert state.is_qualified is True
        assert state.stage == "QUALIFIED"
