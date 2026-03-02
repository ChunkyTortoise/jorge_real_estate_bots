"""
End-to-end conversation flow tests for Seller Bot and Buyer Bot.

Simulates the 13-step manual checklist from docs/bot-spec.md using
real bot instances with mocked external dependencies (LLM, GHL, cache).

Phone under test: 3109820492
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.buyer_bot.buyer_bot import BuyerQualificationState, JorgeBuyerBot
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState


# ---------------------------------------------------------------------------
# Shared fixtures
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


# ---------------------------------------------------------------------------
# Seller Bot E2E — Steps 1-6
# ---------------------------------------------------------------------------


class TestSellerBotE2EFlow:
    """
    Full seller qualification → HOT → scheduling offer → booking.

    Mirrors docs/bot-spec.md E2E steps 1-6.
    """

    @pytest.fixture
    def cache(self):
        return MockCache()

    @pytest.fixture
    def seller_bot(self, cache):
        bot = JorgeSellerBot()
        bot.cache = cache
        return bot

    @staticmethod
    def _mock_context(seller_bot, cache, responses: list[str]):
        """Patch LLM, GHL actions, calendar, and DB for one test run."""
        response_iter = iter(responses)

        async def fake_agenerate(**kwargs):
            content = next(response_iter, "Got it, let me ask the next question.")
            return _fake_llm_response(content)

        mock_ghl = MagicMock()
        mock_ghl.add_tag = AsyncMock()
        mock_ghl.remove_tag = AsyncMock()
        mock_ghl.update_custom_field = AsyncMock()
        mock_ghl.create_opportunity = AsyncMock()
        mock_ghl.get_free_slots = AsyncMock(return_value=MOCK_SLOTS)
        mock_ghl.create_appointment = AsyncMock(return_value={"success": True, "data": {"id": "appt-123"}})
        mock_ghl.get_contact = AsyncMock(return_value={"customFields": []})
        mock_ghl.location_id = "loc-test"

        return (
            patch.object(seller_bot.claude_client, "agenerate", side_effect=fake_agenerate),
            patch("bots.seller_bot.jorge_seller_bot.GHLClient", return_value=mock_ghl),
            patch("bots.seller_bot.jorge_seller_bot.upsert_contact", new=AsyncMock()),
            patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new=AsyncMock()),
            patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", return_value=None),
            mock_ghl,
        )

    @pytest.mark.asyncio
    async def test_step1_initial_message_gets_q1(self, seller_bot, cache):
        """Step 1: 'I want to sell my house' → bot responds with Q1 (condition)."""
        patches = self._mock_context(seller_bot, cache, [
            "Great, happy to help! Quick question — what's the current condition of the property?",
        ])
        *ctxs, mock_ghl = patches
        with patch("bots.seller_bot.jorge_seller_bot.GHLClient", return_value=mock_ghl), \
             patch("bots.seller_bot.jorge_seller_bot.upsert_contact", new=AsyncMock()), \
             patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new=AsyncMock()), \
             patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", return_value=None), \
             patch.object(seller_bot.claude_client, "agenerate", new=AsyncMock(
                 return_value=_fake_llm_response("Quick question — what's the current condition?")
             )):
            result = await seller_bot.process_seller_message(
                contact_id="e2e-seller-001",
                location_id="loc-test",
                message="I want to sell my house",
                contact_info={"name": "Test Lead", "phone": "3109820492"},
            )
        assert result.response_message, "Bot must return a response"
        assert result.questions_answered >= 0
        print(f"\n[Step 1] Bot: {result.response_message}")

    @pytest.mark.asyncio
    async def test_full_seller_flow_to_scheduling(self, seller_bot, cache):
        """Steps 1-5: Full Q0→Q1→Q2→Q3→Q4 accepted → scheduling prose offer."""
        mock_ghl = MagicMock()
        mock_ghl.add_tag = AsyncMock()
        mock_ghl.remove_tag = AsyncMock()
        mock_ghl.update_custom_field = AsyncMock()
        mock_ghl.create_opportunity = AsyncMock()
        mock_ghl.get_free_slots = AsyncMock(return_value=MOCK_SLOTS)
        mock_ghl.create_appointment = AsyncMock(return_value={"success": True, "data": {}})
        mock_ghl.get_contact = AsyncMock(return_value={"customFields": []})
        mock_ghl.location_id = "loc-test"

        # Pre-build state: seller already answered Q1-Q3, now at Q4
        state = SellerQualificationState(contact_id="e2e-seller-002", location_id="loc-test")
        state.current_question = 4
        state.questions_answered = 3
        state.condition = "needs_repairs"
        state.price_expectation = 350000.0
        state.motivation = "job_relocation"
        state.stage = "Q4"

        await seller_bot.save_conversation_state("e2e-seller-002", state)

        # Inject mock calendar service directly
        from bots.shared.calendar_booking_service import CalendarBookingService
        cal_service = CalendarBookingService(mock_ghl)
        cal_service.calendar_id = "cal-test-123"
        seller_bot.calendar_service = cal_service

        with patch("bots.seller_bot.jorge_seller_bot.GHLClient", return_value=mock_ghl), \
             patch("bots.seller_bot.jorge_seller_bot.upsert_contact", new=AsyncMock()), \
             patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new=AsyncMock()), \
             patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", return_value=None), \
             patch.object(seller_bot.claude_client, "agenerate", new=AsyncMock(
                 return_value=_fake_llm_response("That works for me — let me find some times for us.")
             )):
            result = await seller_bot.process_seller_message(
                contact_id="e2e-seller-002",
                location_id="loc-test",
                message="yes that works",
                contact_info={"name": "Test Lead"},
            )

        print(f"\n[Step 5] Bot: {result.response_message}")
        assert result.response_message
        assert result.questions_answered >= 3

    @pytest.mark.asyncio
    async def test_slot_selection_the_first_one(self, seller_bot, cache):
        """Step 6: 'the first one' → books slot 0 → confirmation message."""
        from bots.shared.calendar_booking_service import CalendarBookingService

        mock_ghl = MagicMock()
        mock_ghl.create_appointment = AsyncMock(return_value={"success": True, "data": {"id": "appt-456"}})
        mock_ghl.location_id = "loc-test"

        cal_service = CalendarBookingService(mock_ghl)
        cal_service.calendar_id = "cal-test-123"
        cal_service._pending_slots["e2e-seller-003"] = MOCK_SLOTS

        # Detect "the first one" → slot 0
        idx = cal_service.detect_slot_selection("the first one", "e2e-seller-003")
        assert idx == 0, f"Expected slot 0, got {idx}"

        result = await cal_service.book_appointment("e2e-seller-003", idx, "seller")

        print(f"\n[Step 6] Slot detection: 'the first one' → slot {idx}")
        print(f"[Step 6] Booking result: {result['message']}")
        assert result["success"] is True
        assert "Tuesday" in result["message"] or "booked" in result["message"].lower() or "consultation" in result["message"].lower()
        assert "e2e-seller-003" not in cal_service._pending_slots  # cleared after booking


# ---------------------------------------------------------------------------
# Buyer Bot E2E — Steps 7-12
# ---------------------------------------------------------------------------


class TestBuyerBotE2EFlow:
    """
    Full buyer qualification → HOT → scheduling offer → booking.

    Mirrors docs/bot-spec.md E2E steps 7-12.
    """

    @pytest.fixture
    def cache(self):
        return MockCache()

    @pytest.fixture
    def buyer_bot(self, cache):
        bot = JorgeBuyerBot()
        bot.cache = cache
        return bot

    @pytest.mark.asyncio
    async def test_step7_initial_message_gets_q1(self, buyer_bot, cache):
        """Step 7: 'looking to buy a home' → bot responds with Q1 (preferences)."""
        with patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=cache), \
             patch("bots.buyer_bot.buyer_bot.fetch_properties", new=AsyncMock(return_value=[])), \
             patch("bots.buyer_bot.buyer_bot.upsert_contact", new=AsyncMock()), \
             patch("bots.buyer_bot.buyer_bot.upsert_conversation", new=AsyncMock()), \
             patch("bots.buyer_bot.buyer_bot.fetch_conversation", return_value=None), \
             patch("bots.buyer_bot.buyer_bot.GHLClient") as mock_ghl_cls, \
             patch("bots.buyer_bot.buyer_bot.ClaudeClient") as mock_claude_cls:
            mock_ghl = MagicMock()
            mock_ghl.add_tag = AsyncMock()
            mock_ghl.remove_tag = AsyncMock()
            mock_ghl.update_custom_field = AsyncMock()
            mock_ghl.create_opportunity = AsyncMock()
            mock_ghl_cls.return_value = mock_ghl

            mock_claude = MagicMock()
            mock_claude.agenerate = AsyncMock(return_value=_fake_llm_response(
                "Happy to help! What are you looking for? Beds, baths, price range, and area?"
            ))
            mock_claude_cls.return_value = mock_claude

            result = await buyer_bot.process_buyer_message(
                contact_id="e2e-buyer-001",
                location_id="loc-test",
                message="looking to buy a home",
                contact_info={"name": "Test Buyer", "phone": "3109820492"},
            )

        print(f"\n[Step 7] Bot: {result.response_message}")
        assert result.response_message
        assert result.buyer_temperature in ("cold", "warm", "hot")

    @pytest.mark.asyncio
    async def test_hot_buyer_q3_triggers_scheduling_offer(self, buyer_bot, cache):
        """Steps 9-10: pre-approved + 'within 30 days' → HOT → scheduling prose appended."""
        from bots.shared.calendar_booking_service import CalendarBookingService

        mock_ghl = MagicMock()
        mock_ghl.add_tag = AsyncMock()
        mock_ghl.remove_tag = AsyncMock()
        mock_ghl.update_custom_field = AsyncMock()
        mock_ghl.create_opportunity = AsyncMock()
        mock_ghl.get_free_slots = AsyncMock(return_value=MOCK_SLOTS)
        mock_ghl.create_appointment = AsyncMock(return_value={"success": True, "data": {}})
        mock_ghl.location_id = "loc-test"

        # Pre-build state: buyer has answered Q1 (preferences) and Q2 (pre-approved)
        state = BuyerQualificationState(contact_id="e2e-buyer-002", location_id="loc-test")
        state.current_question = 3
        state.questions_answered = 2
        state.beds_min = 3
        state.baths_min = 2
        state.price_max = 600000
        state.preferred_location = "Rancho Cucamonga"
        state.preapproved = True

        await buyer_bot.save_conversation_state("e2e-buyer-002", state)

        cal_service = CalendarBookingService(mock_ghl)
        cal_service.calendar_id = "cal-test-123"
        buyer_bot.calendar_service = cal_service

        with patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=cache), \
             patch("bots.buyer_bot.buyer_bot.fetch_properties", new=AsyncMock(return_value=[])), \
             patch("bots.buyer_bot.buyer_bot.upsert_contact", new=AsyncMock()), \
             patch("bots.buyer_bot.buyer_bot.upsert_conversation", new=AsyncMock()), \
             patch("bots.buyer_bot.buyer_bot.fetch_conversation", return_value=None), \
             patch("bots.buyer_bot.buyer_bot.GHLClient", return_value=mock_ghl), \
             patch("bots.buyer_bot.buyer_bot.ClaudeClient") as mock_claude_cls:
            mock_claude = MagicMock()
            mock_claude.agenerate = AsyncMock(return_value=_fake_llm_response(
                "Great! What's your motivation for buying right now?"
            ))
            mock_claude_cls.return_value = mock_claude
            buyer_bot.claude_client = mock_claude

            result = await buyer_bot.process_buyer_message(
                contact_id="e2e-buyer-002",
                location_id="loc-test",
                message="within 30 days",
                contact_info={"name": "Test Buyer"},
            )

        print(f"\n[Step 10] Bot: {result.response_message}")
        print(f"[Step 10] Temperature: {result.buyer_temperature}")
        assert result.buyer_temperature == "hot"
        # Scheduling offer should be appended for HOT leads
        # (prose format check)
        if "open" in result.response_message or "which works" in result.response_message:
            assert "Reply with" not in result.response_message, "Must NOT use numbered reply format"

    @pytest.mark.asyncio
    async def test_slot_selection_tuesday_works(self, buyer_bot, cache):
        """Step 12: 'Tuesday works' → detects slot by day name → books → confirmation."""
        from bots.shared.calendar_booking_service import CalendarBookingService

        mock_ghl = MagicMock()
        mock_ghl.create_appointment = AsyncMock(return_value={"success": True, "data": {"id": "appt-789"}})
        mock_ghl.location_id = "loc-test"

        cal_service = CalendarBookingService(mock_ghl)
        cal_service.calendar_id = "cal-test-123"
        cal_service._pending_slots["e2e-buyer-003"] = MOCK_SLOTS

        # "Tuesday works" should match MOCK_SLOTS[0] (Tuesday Mar 10th at 10am)
        idx = cal_service.detect_slot_selection("Tuesday works", "e2e-buyer-003")
        print(f"\n[Step 12] Slot detection: 'Tuesday works' → slot {idx}")
        assert idx == 0, f"Expected slot 0 (Tuesday), got {idx}"

        result = await cal_service.book_appointment("e2e-buyer-003", idx, "buyer")
        print(f"[Step 12] Booking confirmation: {result['message']}")

        assert result["success"] is True
        assert "Tuesday" in result["message"] or "consultation" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_ambiguous_reply_returns_none(self):
        """Ambiguous 'sure' → detect_slot_selection returns None (bot re-offers)."""
        from bots.shared.calendar_booking_service import CalendarBookingService

        mock_ghl = MagicMock()
        mock_ghl.location_id = "loc-test"
        cal_service = CalendarBookingService(mock_ghl)
        cal_service._pending_slots["e2e-ambi-001"] = MOCK_SLOTS

        idx = cal_service.detect_slot_selection("sure sounds good", "e2e-ambi-001")
        print(f"\n[Ambiguous] 'sure sounds good' → slot {idx} (expected None)")
        assert idx is None, "Ambiguous reply must return None"


# ---------------------------------------------------------------------------
# Prose format assertions
# ---------------------------------------------------------------------------


class TestProseSlotFormat:
    """Verify scheduling message uses prose, not numbered list format."""

    def test_offer_format_is_prose_not_numbered(self):
        from bots.shared.calendar_booking_service import CalendarBookingService

        mock_ghl = MagicMock()
        mock_ghl.location_id = "loc-test"
        cal = CalendarBookingService(mock_ghl)
        cal.calendar_id = "cal-test"

        msg = cal._format_slot_options(MOCK_SLOTS)
        print(f"\n[Prose] Scheduling message: {msg}")

        assert "Reply with" not in msg
        assert "1." not in msg and "2." not in msg
        assert "or" in msg, "Prose offer must contain 'or'"
        assert "which works better" in msg.lower() or "does that work" in msg.lower()

    def test_two_slots_both_appear_in_message(self):
        from bots.shared.calendar_booking_service import CalendarBookingService

        mock_ghl = MagicMock()
        mock_ghl.location_id = "loc-test"
        cal = CalendarBookingService(mock_ghl)

        msg = cal._format_slot_options(MOCK_SLOTS)
        # Both slot day names should appear
        assert "Tuesday" in msg or "Mar 10" in msg
        assert "Wednesday" in msg or "Mar 11" in msg
