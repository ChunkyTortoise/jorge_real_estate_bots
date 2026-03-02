"""
Multi-persona prospect tests — JorgeSellerBot and JorgeBuyerBot.

Stress-tests both bots across realistic seller/buyer personas, edge cases,
hostile behavior, off-topic pivots, and ambiguous language.  Surfaces
extraction gaps or system-prompt weaknesses before full production use.

All tests use real bot instances with mocked LLM, GHL, and MockCache.
No HTTP layer involved — tests call process_seller/buyer_message directly.

Phone under test: 3109820492
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.buyer_bot.buyer_bot import BuyerQualificationState, JorgeBuyerBot
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class MockCache:
    """In-memory stand-in for Redis cache."""

    def __init__(self):
        self.store: dict = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        self.store[key] = value
        return True

    async def delete(self, key):
        self.store.pop(key, None)


MOCK_SLOTS = [
    {
        "start": "2026-03-10T10:00:00Z",
        "end": "2026-03-10T10:30:00Z",
        "display": "Tuesday Mar 10th at 10am",
    },
    {
        "start": "2026-03-11T14:00:00Z",
        "end": "2026-03-11T14:30:00Z",
        "display": "Wednesday Mar 11th at 2pm",
    },
]


def _fake_llm_response(content: str):
    from bots.shared.claude_client import LLMResponse
    return LLMResponse(content=content, model="claude-test")


def _make_mock_ghl(slots=None):
    """Return a fully-mocked GHLClient instance."""
    ghl = MagicMock()
    ghl.add_tag = AsyncMock()
    ghl.remove_tag = AsyncMock()
    ghl.update_custom_field = AsyncMock()
    ghl.create_opportunity = AsyncMock()
    ghl.get_free_slots = AsyncMock(
        return_value=(slots if slots is not None else MOCK_SLOTS)
    )
    ghl.create_appointment = AsyncMock(
        return_value={"success": True, "data": {"id": "appt-x"}}
    )
    ghl.get_contact = AsyncMock(return_value={"customFields": [], "tags": []})
    ghl.location_id = "loc-test"
    return ghl


# ---------------------------------------------------------------------------
# P-S* — Seller Personas
# ---------------------------------------------------------------------------


class TestSellerPersonas:
    """
    Seller persona stress tests.

    State pre-building pattern:
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = N   # Q being answered (1-4)
        state.questions_answered = N - 1
        await seller_bot.save_conversation_state(cid, state)
    """

    @pytest.fixture
    def cache(self):
        return MockCache()

    @pytest.fixture
    def seller_bot(self, cache):
        mock_ghl = _make_mock_ghl()
        bot = JorgeSellerBot(ghl_client=mock_ghl)
        bot.cache = cache
        # Reinitialise calendar with the mock GHL and a valid calendar_id
        from bots.shared.calendar_booking_service import CalendarBookingService
        bot.calendar_service = CalendarBookingService(mock_ghl)
        bot.calendar_service.calendar_id = "cal-test-123"
        return bot

    async def _send(
        self,
        bot: JorgeSellerBot,
        contact_id: str,
        message: str,
        llm: str = "Got it, let me ask the next question.",
    ):
        """Helper: patch LLM + DB calls, then process one seller message."""
        with \
            patch.object(bot.claude_client, "agenerate", new=AsyncMock(
                return_value=_fake_llm_response(llm)
            )), \
            patch("bots.seller_bot.jorge_seller_bot.upsert_contact", new=AsyncMock()), \
            patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new=AsyncMock()), \
            patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", return_value=None):
            return await bot.process_seller_message(
                contact_id=contact_id,
                location_id="loc-test",
                message=message,
                contact_info={"name": "Test Seller"},
            )

    # ---- P-S1: Cooperative Standard Seller (baseline) ----------------------

    @pytest.mark.asyncio
    async def test_ps1_cooperative_hot_seller(self, seller_bot):
        """
        P-S1: All 4 Qs answered + offer accepted + timeline OK → HOT.
        Pre-build Q1-Q3 answered, send Q4 acceptance.
        """
        cid = "ps1-coop"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000
        state.motivation = "job_relocation"
        state.urgency = "high"
        state.stage = "Q4"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "yes that works")

        assert result.response_message, "Bot must return a response"
        assert result.questions_answered == 4
        assert result.seller_temperature == "hot"

    # ---- P-S2: Low-Ball Price Anchor ----------------------------------------

    @pytest.mark.asyncio
    async def test_ps2_low_ball_50k_no_k_multiplication_corruption(self, seller_bot):
        """
        P-S2: '$50k' → extracted as 50_000 (NOT 50_000_000).

        The regex captures '$50k' → group(1)='50', then multiplies by 1000 via
        the 'k' branch.  The <10k guard only fires in the bare-number branch, so
        there is no double-multiplication.  Q2 advances.
        """
        cid = "ps2-lowball"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 2
        state.questions_answered = 1
        state.condition = "needs_minor_repairs"
        state.stage = "Q2"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "$50k")

        assert result.questions_answered == 2, "Q2 must advance after price given"
        assert result.analytics["price_expectation"] == 50_000, (
            "$50k → 50 000, not 50 000 000 — k-suffix must not be double-multiplied"
        )

    # ---- P-S3: Hostile / Uncooperative Seller --------------------------------

    @pytest.mark.asyncio
    async def test_ps3_hostile_at_q0_no_crash_stays_cold(self, seller_bot):
        """
        P-S3: Hostile initial message (Q0 state) → bot responds gracefully.

        At Q0 the bot just asks Q1 regardless of message content; questions_answered
        stays 0 and temperature is cold.  No crash permitted.
        """
        cid = "ps3-hostile"
        # No pre-seeding → fresh Q0 state created automatically
        result = await self._send(
            seller_bot, cid,
            "This is a scam. I'm not answering your questions.",
        )

        assert result.response_message, "Bot must return a non-empty response"
        assert result.questions_answered == 0, (
            "No Q should advance — Q0 asks Q1 but does not extract / advance"
        )
        assert result.seller_temperature == "cold"

    # ---- P-S4: Evasive / Vague Answers ----------------------------------------

    @pytest.mark.asyncio
    async def test_ps4a_vague_q1_fine_matches_minor_repairs(self, seller_bot):
        """
        P-S4a: 'It's fine' at Q1 → keyword 'fine' → needs_minor_repairs → Q1 advances.
        """
        cid = "ps4a-fine"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 1
        state.questions_answered = 0
        state.stage = "Q1"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "It's fine")

        assert result.questions_answered == 1, (
            "Q1 must advance when 'fine' matches the minor-repairs keyword list"
        )

    @pytest.mark.asyncio
    async def test_ps4b_vague_q2_no_digits_uses_default_300k(self, seller_bot):
        """
        P-S4b: 'somewhere around what the market says' → no digits → Claude fallback
        (mock returns non-numeric text → ValueError) → default 300_000.  Q2 advances.
        """
        cid = "ps4b-vague-price"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 2
        state.questions_answered = 1
        state.condition = "needs_minor_repairs"
        state.stage = "Q2"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "somewhere around what the market says")

        assert result.questions_answered == 2, (
            "Q2 must advance even when price extraction falls through to default"
        )
        assert result.analytics["price_expectation"] == 300_000, (
            "Default 300 000 applied when Claude classification mock returns non-numeric text"
        )

    @pytest.mark.asyncio
    async def test_ps4c_vague_q3_no_keyword_uses_default_motivation(self, seller_bot):
        """
        P-S4c: 'I don't know, just need to sell' → no motivation keyword →
        Claude fallback (mock not in valid_values) → default 'financial_distress'.
        Q3 advances.
        """
        cid = "ps4c-vague-motivation"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000
        state.stage = "Q3"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "I don't know, just need to sell")

        assert result.questions_answered == 3, (
            "Q3 must advance (default motivation always set)"
        )

    # ---- P-S5: Seller Pivots to Buyer Intent ----------------------------------

    @pytest.mark.asyncio
    async def test_ps5_buyer_pivot_stays_in_seller_flow(self, seller_bot):
        """
        P-S5: 'I want to BUY' at Q1 → bot stays in seller flow, no crash.

        'buy' is not a condition keyword so Claude fallback fires → default
        'needs_minor_repairs'.  Q1 advances.  Response must not leak buyer
        qualification questions (pre-approval, timeline, etc.).
        """
        cid = "ps5-buyer-pivot"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 1
        state.questions_answered = 0
        state.stage = "Q1"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(
            seller_bot, cid,
            "actually I changed my mind, I want to BUY a home instead",
            llm="Got it — what condition is the property in?",
        )

        assert result.response_message, "Bot must respond even on buyer-pivot message"
        # Seller bot must NOT inject buyer questions into its own response
        assert "pre-approved" not in result.response_message.lower()
        assert "pre-approval" not in result.response_message.lower()

    # ---- P-S6: Off-Topic / Non-Real-Estate Questions -------------------------

    @pytest.mark.asyncio
    async def test_ps6_off_topic_at_q0_stays_cold(self, seller_bot):
        """
        P-S6: Off-topic message at fresh Q0 state.

        Bot asks Q1 (condition) unconditionally at Q0.  questions_answered stays 0,
        temperature=cold.  No crash.
        """
        cid = "ps6-offtopic"
        result = await self._send(
            seller_bot, cid,
            "What's the best restaurant near Rancho Cucamonga?",
        )

        assert result.response_message, "Bot must return a response to off-topic message"
        assert result.questions_answered == 0
        assert result.seller_temperature == "cold"

    # ---- P-S7: Very Short / Empty-ish Messages --------------------------------

    @pytest.mark.asyncio
    async def test_ps7a_ok_at_q1_advances(self, seller_bot):
        """
        P-S7a: 'ok' at Q1 → keyword 'ok' → needs_minor_repairs → Q1 advances.

        DOCUMENTS: single-word 'ok' IS sufficient to advance Q1 (keyword list
        includes 'ok').  If word-boundary anchoring is desired, this is the
        regression test to update.
        """
        cid = "ps7a-ok"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 1
        state.questions_answered = 0
        state.stage = "Q1"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "ok")

        assert not result.response_message == "", "Bot must not crash on 'ok'"
        assert result.questions_answered == 1, (
            "'ok' matches 'ok' keyword in minor-repairs list — Q1 advances"
        )

    @pytest.mark.asyncio
    async def test_ps7b_dot_at_q2_no_crash_advances(self, seller_bot):
        """P-S7b: '.' at Q2 → no digits, Claude fallback → default 300k → Q2 advances."""
        cid = "ps7b-dot"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 2
        state.questions_answered = 1
        state.condition = "needs_minor_repairs"
        state.stage = "Q2"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, ".")

        assert result.response_message, "Bot must not crash on '.'"
        assert result.questions_answered == 2

    @pytest.mark.asyncio
    async def test_ps7c_k_at_q3_no_crash_advances(self, seller_bot):
        """P-S7c: 'k' at Q3 → no keyword, Claude fallback → default motivation → Q3 advances."""
        cid = "ps7c-k"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000
        state.stage = "Q3"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "k")

        assert result.response_message, "Bot must not crash on 'k'"
        assert result.questions_answered == 3

    # ---- P-S8: Offer Accepted but Timeline Pushback --------------------------

    @pytest.mark.asyncio
    async def test_ps8_offer_accepted_timeline_pushback_is_warm_not_hot(self, seller_bot):
        """
        P-S8: 'yes but I need more time to close' at Q4.

        offer_accepted=True ('yes' keyword), timeline_acceptable=False ('more time'
        phrase in pushback list).  HOT requires both — result must be WARM.
        """
        cid = "ps8-timeline"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000   # within [200k, 800k]
        state.motivation = "job_relocation"
        state.urgency = "medium"
        state.stage = "Q4"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "yes but I need more time to close")

        assert result.seller_temperature != "hot", (
            "timeline_acceptable=False must prevent HOT classification"
        )
        assert result.seller_temperature == "warm", (
            "All Qs answered + price in range + motivation → WARM when timeline blocked"
        )

    # ---- P-S9: Warm Seller (Offer Not Accepted) --------------------------------

    @pytest.mark.asyncio
    async def test_ps9_offer_not_accepted_is_warm_with_fallback(self, seller_bot):
        """
        P-S9: 'I need to think about it' at Q4 → offer_accepted=False → WARM.

        WARM triggers scheduling fallback (not HOT calendar-slot offer).
        """
        cid = "ps9-warm"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000
        state.motivation = "job_relocation"
        state.urgency = "medium"
        state.stage = "Q4"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send(seller_bot, cid, "I need to think about it")

        assert result.seller_temperature == "warm"
        assert result.analytics.get("offer_accepted") is False
        assert result.response_message, "Non-empty response (scheduling fallback included)"


# ---------------------------------------------------------------------------
# P-B* — Buyer Personas
# ---------------------------------------------------------------------------


class TestBuyerPersonas:
    """
    Buyer persona stress tests.

    State pre-building pattern:
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = N
        state.questions_answered = N - 1
        await buyer_bot.save_conversation_state(cid, state)
    """

    @pytest.fixture
    def cache(self):
        return MockCache()

    @pytest.fixture
    def buyer_bot(self, cache):
        mock_ghl = _make_mock_ghl()
        bot = JorgeBuyerBot(ghl_client=mock_ghl)
        bot.cache = cache
        return bot

    async def _send(
        self,
        bot: JorgeBuyerBot,
        contact_id: str,
        message: str,
        llm: str = "Got it, let me ask the next question.",
    ):
        """Helper: patch LLM + DB calls, then process one buyer message."""
        with \
            patch.object(bot.claude_client, "agenerate", new=AsyncMock(
                return_value=_fake_llm_response(llm)
            )), \
            patch("bots.buyer_bot.buyer_bot.upsert_contact", new=AsyncMock()), \
            patch("bots.buyer_bot.buyer_bot.upsert_conversation", new=AsyncMock()), \
            patch("bots.buyer_bot.buyer_bot.fetch_conversation", return_value=None), \
            patch("bots.buyer_bot.buyer_bot.fetch_properties", new=AsyncMock(return_value=[])):
            return await bot.process_buyer_message(
                contact_id=contact_id,
                location_id="loc-test",
                message=message,
                contact_info={"name": "Test Buyer"},
            )

    # ---- P-B2: Pre-Approved but Long Timeline (Warm) -------------------------

    @pytest.mark.asyncio
    async def test_pb2_preapproved_3_to_6_months_is_warm(self, buyer_bot):
        """
        P-B2: pre-approved=True, '3-6 months out' → timeline_days=90 → WARM.

        HOT requires timeline_days ≤ 30.  90 days falls in WARM band (≤ 90).
        No numbered 'Reply with 1, 2, 3' format in response.
        """
        cid = "pb2-warm-timeline"
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.preapproved = True
        state.beds_min = 3
        state.price_max = 600_000
        state.stage = "Q3"
        await buyer_bot.save_conversation_state(cid, state)

        result = await self._send(buyer_bot, cid, "probably 3-6 months out")

        assert result.buyer_temperature == "warm", (
            "Pre-approved + 90-day timeline must be WARM, not HOT"
        )
        assert "Reply with" not in result.response_message, (
            "Scheduling must use prose format, not numbered list"
        )

    # ---- P-B3: Cash Buyer, Immediate (Hot) -----------------------------------

    @pytest.mark.asyncio
    async def test_pb3_cash_buyer_2_weeks_is_hot(self, buyer_bot):
        """
        P-B3: 'paying cash' at Q2 → preapproved=True.
        '2 weeks' at Q3 → timeline_days=14 → HOT (≤ 30 days + pre-approved).
        """
        cid = "pb3-cash-hot"
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.preapproved = True   # 'cash' branch sets preapproved=True at Q2
        state.beds_min = 3
        state.price_max = 600_000
        state.stage = "Q3"
        await buyer_bot.save_conversation_state(cid, state)

        result = await self._send(buyer_bot, cid, "I need to close in 2 weeks")

        assert result.buyer_temperature == "hot", (
            "Cash buyer + 14-day timeline must be HOT"
        )
        assert result.analytics.get("timeline_days") == 14

    # ---- P-B4: Not Pre-Approved, Urgent (Warm, Not Hot) ---------------------

    @pytest.mark.asyncio
    async def test_pb4a_not_yet_preapproved_sets_false(self, buyer_bot):
        """
        P-B4a: 'Not yet, I'm still renting' at Q2 → preapproved=False.

        'not yet' phrase fires the not-approved branch first.  Q2 advances.
        """
        cid = "pb4a-not-preapproved"
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 2
        state.questions_answered = 1
        state.beds_min = 3
        state.price_max = 500_000
        state.stage = "Q2"
        await buyer_bot.save_conversation_state(cid, state)

        result = await self._send(buyer_bot, cid, "Not yet, I'm still renting")

        assert result.questions_answered == 2
        assert result.analytics.get("preapproved") is False

    @pytest.mark.asyncio
    async def test_pb4b_urgent_but_not_preapproved_is_warm(self, buyer_bot):
        """
        P-B4b: preapproved=False + 30-day timeline → WARM, NOT hot.

        HOT requires BOTH pre-approval AND ≤ 30-day timeline.
        """
        cid = "pb4b-urgent-no-preapproval"
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.preapproved = False
        state.beds_min = 3
        state.price_max = 500_000
        state.stage = "Q3"
        await buyer_bot.save_conversation_state(cid, state)

        result = await self._send(buyer_bot, cid, "I want to buy within 30 days")

        assert result.buyer_temperature == "warm", (
            "Urgent but un-approved lead must be WARM, not HOT"
        )
        assert result.analytics.get("preapproved") is False

    # ---- P-B5: Just Browsing (Cold) -----------------------------------------

    @pytest.mark.asyncio
    async def test_pb5_just_browsing_is_cold(self, buyer_bot):
        """
        P-B5: 'just browsing for now, no rush' → timeline_days=180 → COLD.

        Even a pre-approved buyer with a 180-day window is cold.
        Bot continues nurturing (response_message non-empty).
        """
        cid = "pb5-browsing"
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.preapproved = True
        state.beds_min = 3
        state.price_max = 600_000
        state.stage = "Q3"
        await buyer_bot.save_conversation_state(cid, state)

        result = await self._send(buyer_bot, cid, "just browsing for now, no rush")

        assert result.buyer_temperature == "cold", (
            "180-day timeline must classify as cold"
        )
        assert result.response_message, "Bot must still respond (nurturing, not silence)"

    # ---- P-B6: Buyer Asks Seller-Type Questions ------------------------------

    @pytest.mark.asyncio
    async def test_pb6_seller_question_redirected_no_offer_language(self, buyer_bot):
        """
        P-B6: Buyer asks 'Can you make a cash offer on my home?' (seller intent).

        At Q0 the bot asks Q1 (buyer preferences) unconditionally.  The mocked
        LLM response contains a redirect.  The bot's own extraction logic must
        not inject offer language.

        Also verifies BUYER_SYSTEM_PROMPT contains the seller-guardrail clause.
        """
        from bots.buyer_bot.buyer_prompts import BUYER_SYSTEM_PROMPT

        # Validate system prompt has the guardrail
        assert "NEVER ask about property condition" in BUYER_SYSTEM_PROMPT, (
            "BUYER_SYSTEM_PROMPT must block seller questions explicitly"
        )
        assert "Let's stay focused on finding you the right home to buy" in BUYER_SYSTEM_PROMPT, (
            "BUYER_SYSTEM_PROMPT must contain the off-topic redirect phrase"
        )

        cid = "pb6-seller-question"
        result = await self._send(
            buyer_bot, cid,
            "Can you make a cash offer on my home?",
            llm="Let's stay focused on finding you the right home to buy. What are you looking for?",
        )

        assert result.response_message, "Bot must respond (not crash)"
        # Bot's own logic must not add offer language to the response
        assert "cash offer on" not in result.response_message.lower()
        assert "what condition" not in result.response_message.lower()

    # ---- P-B7: Buyer Claims to Be a Realtor / Agent -------------------------

    @pytest.mark.asyncio
    async def test_pb7_realtor_buyer_no_crash_continues_flow(self, buyer_bot):
        """
        P-B7: 'I'm a real estate agent looking for an investment property' at Q0.

        No special realtor handling is implemented.  Bot continues buyer flow
        (asks Q1).  Documents that agent-role detection is a future gap.
        """
        cid = "pb7-realtor"
        result = await self._send(
            buyer_bot, cid,
            "I'm a real estate agent myself looking for an investment property",
        )

        assert result.response_message, "Bot must respond to realtor buyer"
        assert result.buyer_temperature in ("cold", "warm", "hot")
        # questions_answered=0 at Q0 — Q1 prompt returned, no extraction yet
        assert result.questions_answered == 0, (
            "No Q extraction at Q0 — agent-role detection is a future gap (documented)"
        )

    # ---- P-B8: Fragmented Q1 Answers / State Accumulation ------------------

    @pytest.mark.asyncio
    async def test_pb8_state_accumulates_across_calls(self, buyer_bot):
        """
        P-B8: State accumulates across two calls for the same contact.

        Call 1 (Q1): '3 bedrooms under 600k in Rancho' →
            beds_min=3, price_max=600_000, location='Rancho Cucamonga'.
            Q1 advances (beds_min satisfies _should_advance_question).

        Call 2 (Q2): 'yes pre-approved' →
            preapproved=True, Q2 advances.

        After call 2, state retains Q1 preferences alongside Q2 financing.
        """
        cid = "pb8-accumulate"
        # Call 1 at fresh Q0 → bot asks Q1
        await self._send(buyer_bot, cid, "looking to buy a home")

        # Now at Q1 — use full city name so SERVICE_AREAS lookup matches
        r1 = await self._send(buyer_bot, cid, "3 bedrooms under 600k in Rancho Cucamonga")

        assert r1.analytics["preferences"]["beds_min"] == 3
        assert r1.analytics["preferences"]["price_max"] == 600_000
        assert r1.analytics["preferences"]["preferred_location"] == "Rancho Cucamonga"
        assert r1.questions_answered >= 1, "Q1 must advance on beds+price"

        # Call 2 at Q2
        r2 = await self._send(buyer_bot, cid, "yes pre-approved")

        # Q1 state must still be present (not overwritten)
        assert r2.analytics["preferences"]["beds_min"] == 3, (
            "beds_min from Q1 must persist after Q2 call"
        )
        assert r2.analytics["preferences"]["price_max"] == 600_000, (
            "price_max from Q1 must persist after Q2 call"
        )
        assert r2.analytics.get("preapproved") is True, (
            "Q2 preapproved=True must be present after second call"
        )

    # ---- P-B9: Contradictory Financing (no pre-approval + urgent) -----------

    @pytest.mark.asyncio
    async def test_pb9_contradictory_financing_urgent_without_preapproval_is_warm(self, buyer_bot):
        """
        P-B9: preapproved=False (Q2) + 'within 7 days' (Q3) → WARM, not HOT.

        urgency cannot override the pre-approval requirement.
        No scheduling slot offer (not HOT).
        """
        cid = "pb9-contradiction"
        state = BuyerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.preapproved = False
        state.beds_min = 3
        state.price_max = 600_000
        state.stage = "Q3"
        await buyer_bot.save_conversation_state(cid, state)

        result = await self._send(buyer_bot, cid, "I need to move within 7 days")

        assert result.analytics.get("preapproved") is False
        assert result.analytics.get("timeline_days") is not None
        assert result.buyer_temperature == "warm", (
            "Urgent but un-approved buyer must be WARM, not HOT"
        )

    # ---- P-B10: Ambiguous Pre-Approval Language ------------------------------

    @pytest.mark.asyncio
    async def test_pb10a_working_on_it_is_false(self, buyer_bot):
        """
        P-B10a: 'I'm still working on it' → preapproved=False.

        Phrase 'working on it' fires the not-approved branch.
        """
        extracted = await buyer_bot._extract_qualification_data(
            "I'm still working on it", 2
        )
        assert extracted.get("preapproved") is False

    @pytest.mark.asyncio
    async def test_pb10b_lender_says_good_defaults_to_false(self, buyer_bot):
        """
        P-B10b: 'My lender says I should be good' → preapproved=False.

        No keyword from either branch matches → fallback else clause sets False.
        DOCUMENTS: this ambiguous phrase is treated as not-approved.
        """
        extracted = await buyer_bot._extract_qualification_data(
            "My lender says I should be good", 2
        )
        assert extracted.get("preapproved") is False, (
            "Ambiguous lender approval phrase defaults to False — documented behavior"
        )

    @pytest.mark.asyncio
    async def test_pb10c_expired_preapproval_returns_true_gap_documented(self, buyer_bot):
        """
        P-B10c: 'I was pre-approved but it expired' → preapproved=True.

        DOCUMENTS CODE GAP: 'pre-approved' substring matches the positive branch
        before any negative context can be checked.  Hardening requires
        negative-context detection (e.g. 'expired', 'but it').
        Current behavior: True.  Future hardening target.
        """
        extracted = await buyer_bot._extract_qualification_data(
            "I was pre-approved but it expired", 2
        )
        # Document current (imperfect) behavior — update this assertion after hardening
        assert extracted.get("preapproved") is True, (
            "CODE GAP: 'pre-approved' matches positive branch even with expiry context. "
            "Future hardening should detect 'expired' qualifier → False."
        )


# ---------------------------------------------------------------------------
# P-C* — Calendar Edge Cases
# ---------------------------------------------------------------------------


class TestCalendarEdgeCases:
    """Calendar booking service edge cases."""

    @pytest.fixture
    def cache(self):
        return MockCache()

    @pytest.fixture
    def seller_bot(self, cache):
        mock_ghl = _make_mock_ghl()
        bot = JorgeSellerBot(ghl_client=mock_ghl)
        bot.cache = cache
        from bots.shared.calendar_booking_service import CalendarBookingService
        bot.calendar_service = CalendarBookingService(mock_ghl)
        bot.calendar_service.calendar_id = "cal-test-123"
        return bot

    async def _send_seller(
        self,
        bot: JorgeSellerBot,
        contact_id: str,
        message: str,
        llm: str = "Got it.",
    ):
        with \
            patch.object(bot.claude_client, "agenerate", new=AsyncMock(
                return_value=_fake_llm_response(llm)
            )), \
            patch("bots.seller_bot.jorge_seller_bot.upsert_contact", new=AsyncMock()), \
            patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new=AsyncMock()), \
            patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", return_value=None):
            return await bot.process_seller_message(
                contact_id=contact_id,
                location_id="loc-test",
                message=message,
                contact_info={"name": "Test Seller"},
            )

    # ---- P-C1: Empty Slots Returned -------------------------------------------

    @pytest.mark.asyncio
    async def test_pc1_empty_slots_returns_fallback_message(self, seller_bot):
        """
        P-C1: HOT lead triggers calendar → get_free_slots returns [] →
        FALLBACK_MESSAGE appended.  No crash.
        """
        from bots.shared.calendar_booking_service import FALLBACK_MESSAGE

        # Override get_free_slots to return no availability
        seller_bot.ghl_client.get_free_slots = AsyncMock(return_value=[])
        # Re-bind calendar service to use updated ghl_client mock
        from bots.shared.calendar_booking_service import CalendarBookingService
        seller_bot.calendar_service = CalendarBookingService(seller_bot.ghl_client)
        seller_bot.calendar_service.calendar_id = "cal-test-123"

        cid = "pc1-no-slots"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000
        state.motivation = "job_relocation"
        state.urgency = "high"
        state.stage = "Q4"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send_seller(seller_bot, cid, "yes that works")

        assert result.response_message, "Bot must respond even with no calendar slots"
        assert result.seller_temperature == "hot"
        # Scheduling fallback text must appear (calendar unavailable → prose fallback)
        fallback_fragment = "morning or afternoon"  # from FALLBACK_MESSAGE
        assert fallback_fragment in result.response_message, (
            f"FALLBACK_MESSAGE ({FALLBACK_MESSAGE!r}) must appear when no slots available"
        )

    # ---- P-C2: Unmatched Day in Slot Reply ------------------------------------

    def test_pc2_unmatched_day_returns_none(self):
        """
        P-C2: Slots offered are Tue/Wed; lead replies 'Thursday works for me'.
        detect_slot_selection must return None (no booking triggered).
        """
        from bots.shared.calendar_booking_service import CalendarBookingService

        ghl = _make_mock_ghl()
        cal = CalendarBookingService(ghl)
        cal._pending_slots["pc2-contact"] = MOCK_SLOTS

        idx = cal.detect_slot_selection("Thursday works for me", "pc2-contact")
        assert idx is None, (
            "'Thursday' not in offered slots — must return None, not a slot index"
        )

    # ---- P-C3: Ambiguous Slot Replies -----------------------------------------

    def test_pc3_ambiguous_replies_return_none(self):
        """
        P-C3: 'sure, either works', 'ok', 'yes' → all return None.
        Ambiguous replies must NOT book a slot.
        """
        from bots.shared.calendar_booking_service import CalendarBookingService

        ghl = _make_mock_ghl()
        cal = CalendarBookingService(ghl)
        cal._pending_slots["pc3-contact"] = MOCK_SLOTS

        for ambiguous in ("sure, either works", "ok", "yes"):
            idx = cal.detect_slot_selection(ambiguous, "pc3-contact")
            assert idx is None, (
                f"Ambiguous reply {ambiguous!r} must return None (not slot {idx})"
            )

    # ---- P-C4: Single-Slot Offer Format ---------------------------------------

    def test_pc4_single_slot_no_or_in_message(self):
        """
        P-C4: When only 1 slot is available, _format_slot_options produces
        'I have X available — does that work for you?' with no 'or'.
        """
        from bots.shared.calendar_booking_service import CalendarBookingService

        ghl = _make_mock_ghl()
        cal = CalendarBookingService(ghl)

        single = [MOCK_SLOTS[0]]
        msg = cal._format_slot_options(single)

        assert "does that work for you" in msg.lower(), (
            "Single-slot message must ask 'does that work for you?'"
        )
        # Must NOT include 'or' (which implies a second option)
        assert " or " not in msg, (
            "Single-slot message must NOT contain ' or ' (no second option)"
        )

    # ---- P-C5: Scheduling Offered Only Once (Idempotency) -------------------

    @pytest.mark.asyncio
    async def test_pc5_scheduling_offered_only_once(self, seller_bot):
        """
        P-C5: scheduling_offered=True prevents a second scheduling append.

        Even if the lead sends another message and remains HOT, the flag
        suppresses the second offer.
        """
        from bots.shared.calendar_booking_service import FALLBACK_MESSAGE

        cid = "pc5-idempotent"
        state = SellerQualificationState(contact_id=cid, location_id="loc-test")
        state.current_question = 4
        state.questions_answered = 4
        state.condition = "needs_minor_repairs"
        state.price_expectation = 350_000
        state.motivation = "job_relocation"
        state.urgency = "high"
        state.offer_accepted = True
        state.timeline_acceptable = True
        state.scheduling_offered = True   # already offered once
        state.stage = "QUALIFIED"
        await seller_bot.save_conversation_state(cid, state)

        result = await self._send_seller(seller_bot, cid, "Let me think about it")

        # Scheduling fallback must NOT be appended again
        assert FALLBACK_MESSAGE not in result.response_message, (
            "scheduling_offered=True must prevent a second scheduling append"
        )
        # Slot offer prose also must not re-appear
        assert "which works better" not in result.response_message.lower(), (
            "Calendar slot offer must not be re-sent after scheduling_offered=True"
        )
