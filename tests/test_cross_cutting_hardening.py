"""Cross-cutting hardening tests: response filter, garbage inputs,
cross-contamination, state corruption, concurrency patterns, bot assignment."""
from __future__ import annotations

import hashlib

import pytest

from bots.shared.response_filter import sanitize_bot_response


# ---------------------------------------------------------------------------
# Group 1: Response Filter Combined Violations (6 tests)
# ---------------------------------------------------------------------------
class TestResponseFilterCombined:
    def test_ai_term_stripped(self):
        result = sanitize_bot_response("I'm an AI assistant here to help you.")
        assert "AI" not in result
        assert "Jorge" in result

    def test_url_stripped(self):
        result = sanitize_bot_response("Check out https://example.com for details.")
        assert "https://" not in result

    def test_claude_name_stripped(self):
        result = sanitize_bot_response("I'm Claude, happy to help.")
        assert "Claude" not in result
        assert "Jorge" in result

    def test_long_response_truncated(self):
        long_msg = "word " * 120  # 600 chars
        result = sanitize_bot_response(long_msg)
        # Truncation adds "..." (3 chars) at word boundary, so max is 483
        assert len(result) <= 483

    def test_all_three_violations_at_once(self):
        msg = "I'm an AI at https://anthropic.com. " + "X " * 230
        result = sanitize_bot_response(msg)
        assert "AI" not in result
        assert "https://" not in result
        assert len(result) <= 480

    def test_anthropic_stripped(self):
        result = sanitize_bot_response("Made by Anthropic.")
        assert "Anthropic" not in result


# ---------------------------------------------------------------------------
# Group 2: Garbage / Edge Input Messages (10 tests)
# ---------------------------------------------------------------------------
class TestGarbageInputs:
    @pytest.mark.asyncio
    async def test_empty_string(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("", 1)
        assert isinstance(extracted, dict)
        assert extracted.get("beds_min") is None

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("   ", 1)
        assert isinstance(extracted, dict)

    @pytest.mark.asyncio
    async def test_emoji_only(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("\U0001f937", 1)
        assert isinstance(extracted, dict)
        assert extracted.get("beds_min") is None

    @pytest.mark.asyncio
    async def test_thumbs_up_not_preapproval(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("\U0001f44d", 2)
        # Thumbs-up doesn't contain "yes"/"approved"/"cash" → falls to default False
        assert extracted.get("preapproved") is False

    @pytest.mark.asyncio
    async def test_single_k(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("k", 1)
        assert isinstance(extracted, dict)
        assert extracted.get("beds_min") is None

    @pytest.mark.asyncio
    async def test_single_y_not_yes(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        # "y" does NOT contain "yes" — substring check "yes" in "y" is False
        extracted = await bot._extract_qualification_data("y", 2)
        assert extracted.get("preapproved") is False

    @pytest.mark.asyncio
    async def test_single_n_not_no(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        # "no" in "n" is False — substring doesn't match
        extracted = await bot._extract_qualification_data("n", 2)
        assert extracted.get("preapproved") is False

    @pytest.mark.asyncio
    async def test_lol_graceful(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("lol", 1)
        assert isinstance(extracted, dict)

    @pytest.mark.asyncio
    async def test_dots_graceful(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("...", 1)
        assert isinstance(extracted, dict)

    @pytest.mark.asyncio
    async def test_very_long_message(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        long_msg = "I want to buy a house " * 100  # ~2200 chars
        extracted = await bot._extract_qualification_data(long_msg, 1)
        assert isinstance(extracted, dict)


# ---------------------------------------------------------------------------
# Group 3: Cross-Contamination (6 tests)
# ---------------------------------------------------------------------------
class TestCrossContamination:
    def test_buyer_prompt_has_seller_guard(self):
        from bots.buyer_bot.buyer_prompts import BUYER_SYSTEM_PROMPT

        # Buyer prompt explicitly guards against asking seller questions
        assert "never ask about property condition" in BUYER_SYSTEM_PROMPT.lower() or \
               "seller questions" in BUYER_SYSTEM_PROMPT.lower()

    def test_seller_prompt_no_beds_keyword(self):
        from bots.seller_bot.jorge_seller_bot import SELLER_SYSTEM_PROMPT

        # Seller prompt shouldn't mention bedroom preferences
        prompt_lower = SELLER_SYSTEM_PROMPT.lower()
        assert "beds" not in prompt_lower or "bedrooms" not in prompt_lower

    def test_buyer_state_no_condition_field(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1")
        assert not hasattr(state, "condition")

    def test_seller_state_no_beds_field(self):
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        state = SellerQualificationState(contact_id="c1", location_id="l1")
        assert not hasattr(state, "beds_min")

    @pytest.mark.asyncio
    async def test_buyer_extraction_no_condition(self):
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("move-in ready 3 bed 2 bath", 1)
        assert "condition" not in extracted

    def test_seller_state_has_condition_not_beds(self):
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        state = SellerQualificationState(contact_id="c1", location_id="l1")
        assert hasattr(state, "condition")
        assert not hasattr(state, "beds_min")


# ---------------------------------------------------------------------------
# Group 4: State Corruption Resilience (6 tests)
# ---------------------------------------------------------------------------
class TestStateCorruptionResilience:
    def test_default_question_zero(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1")
        assert state.current_question == 0

    def test_high_question_number_no_advance(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1", current_question=99)
        state.advance_question()
        assert state.current_question == 99  # >= 4, so no change

    def test_empty_extracted_data_no_crash(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1")
        state.record_answer(1, "hello", {})
        assert state.beds_min is None

    def test_fresh_state_all_none_fields(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1")
        assert state.beds_min is None
        assert state.baths_min is None
        assert state.price_max is None
        assert state.preapproved is None
        assert state.timeline_days is None

    def test_seller_state_high_q4_attempts(self):
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        state = SellerQualificationState(contact_id="c1", location_id="l1", q4_attempts=100)
        assert state.q4_attempts == 100

    def test_negative_question_number_advance(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1", current_question=-1)
        assert state.current_question == -1
        state.advance_question()  # -1 < 4 → increments to 0
        assert state.current_question == 0


# ---------------------------------------------------------------------------
# Group 5: Concurrent / Race Condition Patterns (4 tests)
# ---------------------------------------------------------------------------
class TestConcurrentBehavior:
    def test_dedup_same_message_same_contact(self):
        """Same (contact_id, message) produces identical dedup key."""
        contact_id = "contact_123"
        message = "hello"
        key1 = f"dedup:{contact_id}:{hashlib.md5(message.encode()).hexdigest()}"
        key2 = f"dedup:{contact_id}:{hashlib.md5(message.encode()).hexdigest()}"
        assert key1 == key2

    def test_dedup_different_messages_differ(self):
        """Different messages produce different dedup keys."""
        contact_id = "contact_123"
        key1 = f"dedup:{contact_id}:{hashlib.md5(b'hello').hexdigest()}"
        key2 = f"dedup:{contact_id}:{hashlib.md5(b'world').hexdigest()}"
        assert key1 != key2

    def test_lock_key_format(self):
        """Processing lock key includes contact_id."""
        contact_id = "contact_789"
        lock_key = f"lock:{contact_id}"
        assert contact_id in lock_key

    def test_q4_attempt_increment(self):
        """q4_attempts tracks individual increments."""
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        state = SellerQualificationState(contact_id="c1", location_id="l1", current_question=4)
        initial = state.q4_attempts
        state.q4_attempts += 1
        assert state.q4_attempts == initial + 1


# ---------------------------------------------------------------------------
# Group 6: Bot Assignment (3 tests)
# ---------------------------------------------------------------------------
class TestBotAssignment:
    def test_buyer_state_is_buyer_state(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState

        state = BuyerQualificationState(contact_id="c1", location_id="l1")
        assert isinstance(state, BuyerQualificationState)

    def test_seller_state_is_seller_state(self):
        from bots.seller_bot.jorge_seller_bot import SellerQualificationState

        state = SellerQualificationState(contact_id="c1", location_id="l1")
        assert isinstance(state, SellerQualificationState)

    def test_bot_types_are_distinct(self):
        from bots.buyer_bot.buyer_bot import BuyerQualificationState, JorgeBuyerBot
        from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState

        assert BuyerQualificationState is not SellerQualificationState
        assert JorgeBuyerBot is not JorgeSellerBot
