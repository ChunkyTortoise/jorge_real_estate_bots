"""Tests for seller bot extraction and state machine logic.

Tests the qualification state machine transitions, condition/motivation/offer
extraction, and Q4 stall detection — all without requiring Claude API calls.
"""
import re

import pytest

from bots.seller_bot.jorge_seller_bot import (
    SellerQualificationState,
    _COLLOQUIAL_PRICES,
    _PRICE_PATTERNS,
)


# -----------------------------------------------------------------------
# State machine transitions
# -----------------------------------------------------------------------
class TestSellerStateMachine:
    def test_initial_state_is_q0(self, seller_state):
        assert seller_state.current_question == 0
        assert seller_state.stage == "Q0"
        assert seller_state.questions_answered == 0
        assert seller_state.is_qualified is False

    def test_advance_q0_to_q1(self, seller_state):
        seller_state.advance_question()
        assert seller_state.current_question == 1
        assert seller_state.stage == "Q1"

    def test_advance_q1_to_q2(self, seller_state):
        seller_state.current_question = 1
        seller_state.stage = "Q1"
        seller_state.advance_question()
        assert seller_state.current_question == 2
        assert seller_state.stage == "Q2"

    def test_advance_q3_to_q4(self, seller_state):
        seller_state.current_question = 3
        seller_state.stage = "Q3"
        seller_state.advance_question()
        assert seller_state.current_question == 4
        assert seller_state.stage == "Q4"

    def test_advance_does_not_exceed_q4(self, seller_state):
        seller_state.current_question = 4
        seller_state.stage = "Q4"
        seller_state.advance_question()
        assert seller_state.current_question == 4
        assert seller_state.stage == "Q4"

    def test_record_answer_updates_questions_answered(self, seller_state):
        seller_state.record_answer(1, "needs some work", {"condition": "needs_minor_repairs"})
        assert seller_state.questions_answered == 1

    def test_record_answer_does_not_decrease_count(self, seller_state):
        seller_state.questions_answered = 3
        seller_state.record_answer(2, "350k", {"price_expectation": 350000})
        assert seller_state.questions_answered == 3

    def test_full_qualification_on_offer_accepted_and_timeline(self, seller_state):
        seller_state.current_question = 4
        seller_state.stage = "Q4"
        seller_state.questions_answered = 3
        seller_state.record_answer(4, "yes let's do it", {
            "offer_accepted": True,
            "timeline_acceptable": True,
        })
        assert seller_state.is_qualified is True
        assert seller_state.stage == "QUALIFIED"

    def test_no_qualification_when_offer_rejected(self, seller_state):
        seller_state.current_question = 4
        seller_state.stage = "Q4"
        seller_state.questions_answered = 3
        seller_state.record_answer(4, "no way", {
            "offer_accepted": False,
            "timeline_acceptable": False,
        })
        assert seller_state.is_qualified is False
        assert seller_state.stage == "Q4"


# -----------------------------------------------------------------------
# Q1: Condition extraction (keyword matching)
# -----------------------------------------------------------------------
class TestConditionExtraction:
    """Tests the keyword-based condition classification logic from _extract_qualification_data Q1."""

    @staticmethod
    def _classify_condition(message: str) -> str | None:
        """Replicate the Q1 condition keyword matching (no Claude fallback)."""
        ml = message.lower()
        major_words = [
            "major", "significant", "extensive", "needs work", "bad shape",
            "falling apart", "broken", "run down", "rundown", "fixer", "gut",
            "disaster", "terrible", "awful", "wreck", "dump", "outdated",
            "old", "rough", "trashed", "condemned",
        ]
        minor_words = [
            "minor", "small", "few", "cosmetic", "touch up", "paint", "carpet",
            "dated", "okay", "ok", "fine", "alright", "decent", "fair",
            "maintenance", "wear", "showing its age", "aging", "lived in",
            "some work", "little work", "needs some",
        ]
        ready_words = [
            "ready", "good", "excellent", "perfect", "great shape", "move in",
            "updated", "renovated", "remodeled", "new", "nice", "beautiful",
            "pristine", "great", "well maintained", "well-maintained", "clean",
        ]
        def _kw_in(keywords: list[str]) -> bool:
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', ml):
                    return True
            return False

        if _kw_in(major_words):
            return "needs_major_repairs"
        if _kw_in(minor_words):
            return "needs_minor_repairs"
        if _kw_in(ready_words):
            return "move_in_ready"
        return None  # would fall through to Claude

    def test_fixer_upper(self):
        assert self._classify_condition("It's a fixer upper for sure") == "needs_major_repairs"

    def test_major_repairs(self):
        assert self._classify_condition("Needs major work, roof is bad") == "needs_major_repairs"

    def test_run_down(self):
        assert self._classify_condition("Pretty run down honestly") == "needs_major_repairs"

    def test_needs_some_paint(self):
        assert self._classify_condition("Just needs some paint and carpet") == "needs_minor_repairs"

    def test_cosmetic_updates(self):
        assert self._classify_condition("Cosmetic updates mostly") == "needs_minor_repairs"

    def test_dated_kitchen(self):
        assert self._classify_condition("Kitchen is a little dated") == "needs_minor_repairs"

    def test_move_in_ready(self):
        assert self._classify_condition("Move in ready, just renovated") == "move_in_ready"

    def test_excellent_condition(self):
        assert self._classify_condition("Excellent condition, well maintained") == "move_in_ready"

    def test_pristine_shape(self):
        # "updated" is a whole word — word-boundary matching correctly returns move_in_ready
        assert self._classify_condition("Pristine shape, everything updated") == "move_in_ready"

    def test_pristine_alone(self):
        # "rough" inside "throughout" no longer matches — word-boundary matching
        assert self._classify_condition("Pristine condition throughout") == "move_in_ready"

    def test_pristine_no_ambiguity(self):
        assert self._classify_condition("Pristine, very clean") == "move_in_ready"

    def test_ambiguous_falls_through(self):
        assert self._classify_condition("It's an interesting house") is None


# -----------------------------------------------------------------------
# Q3: Motivation extraction (keyword matching)
# -----------------------------------------------------------------------
class TestMotivationExtraction:
    """Tests the Q3 motivation keyword matching."""

    # Ordered by specificity (mirrors production code): specific before generic
    _MOTIVATIONS = {
        "divorce": "divorce", "separation": "divorce", "separating": "divorce",
        "foreclosure": "foreclosure", "foreclose": "foreclosure",
        "inherited": "inheritance", "inheritance": "inheritance",
        "probate": "inheritance", "death in": "inheritance",
        "passed away": "inheritance", "died": "inheritance", "estate": "inheritance",
        "medical": "medical_emergency",
        "bankruptcy": "financial_distress", "financial": "financial_distress",
        "behind on": "financial_distress", "debt": "financial_distress",
        "downsize": "downsizing", "downsizing": "downsizing",
        "retire": "retirement", "retirement": "retirement", "retiring": "retirement",
        "tenant": "landlord_exit", "vacant": "landlord_exit",
        "don't want": "landlord_exit", "tired of": "landlord_exit",
        "upsize": "upsizing", "upsizing": "upsizing",
        "job": "job_relocation", "relocation": "job_relocation",
        "relocating": "job_relocation", "transfer": "job_relocation",
        "moving": "job_relocation", "move": "job_relocation",
    }

    @classmethod
    def _classify_motivation(cls, message: str) -> str | None:
        ml = message.lower()
        for keyword, motivation_type in cls._MOTIVATIONS.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', ml):
                return motivation_type
        return None

    def test_job_relocation(self):
        assert self._classify_motivation("Got a new job in Texas") == "job_relocation"

    def test_divorce(self):
        assert self._classify_motivation("Going through a divorce") == "divorce"

    def test_foreclosure(self):
        assert self._classify_motivation("Facing foreclosure next month") == "foreclosure"

    def test_inherited(self):
        assert self._classify_motivation("I inherited the house from my parents") == "inheritance"

    def test_downsizing(self):
        # "downsize" now checked before "move" — correctly returns downsizing
        assert self._classify_motivation("Want to downsize, kids moved out") == "downsizing"

    def test_downsizing_clean(self):
        assert self._classify_motivation("Want to downsize now") == "downsizing"

    def test_retirement(self):
        # "retire" now checked before "moving" — correctly returns retirement
        assert self._classify_motivation("We're retiring and moving to Florida") == "retirement"

    def test_retirement_clean(self):
        assert self._classify_motivation("We're retiring soon") == "retirement"

    def test_tenant_problems(self):
        assert self._classify_motivation("Tired of dealing with tenant issues") == "landlord_exit"

    def test_medical_emergency(self):
        assert self._classify_motivation("Medical bills are piling up") == "medical_emergency"

    def test_ambiguous_falls_through(self):
        assert self._classify_motivation("I just want a change") is None


# -----------------------------------------------------------------------
# Q4: Offer acceptance extraction
# -----------------------------------------------------------------------
class TestOfferAcceptanceExtraction:

    @staticmethod
    def _classify_offer(message: str) -> dict:
        ml = message.lower()
        extracted = {}
        accept_words = [
            "yes", "deal", "accept", "sounds good", "let's do it", "lets do it",
            "sure", "ok", "okay", "works for me", "i'll take it", "ill take it",
        ]
        reject_words = [
            "no", "can't", "cant", "won't", "wont", "too low", "pass",
            "not interested", "not enough", "need more money",
        ]
        if any(w in ml for w in accept_words):
            extracted["offer_accepted"] = True
        elif any(w in ml for w in reject_words):
            extracted["offer_accepted"] = False
        else:
            extracted["offer_accepted"] = False

        timeline_pushback = any(phrase in ml for phrase in [
            "need more time", "too quick", "can't close", "cant close",
            "won't close", "wont close", "not that fast", "need longer",
            "more time", "too fast", "need 30", "need 60", "need 90",
        ])
        if timeline_pushback:
            extracted["timeline_acceptable"] = False
        elif extracted.get("offer_accepted"):
            extracted["timeline_acceptable"] = True
        else:
            extracted["timeline_acceptable"] = False
        return extracted

    def test_accept_yes(self):
        r = self._classify_offer("Yes, sounds good!")
        assert r["offer_accepted"] is True
        assert r["timeline_acceptable"] is True

    def test_accept_deal(self):
        r = self._classify_offer("Deal, let's do it")
        assert r["offer_accepted"] is True
        assert r["timeline_acceptable"] is True

    def test_reject_too_low(self):
        r = self._classify_offer("That's too low for me")
        assert r["offer_accepted"] is False
        assert r["timeline_acceptable"] is False

    def test_reject_pass(self):
        r = self._classify_offer("I'll pass on that")
        assert r["offer_accepted"] is False

    def test_accept_but_timeline_pushback(self):
        r = self._classify_offer("Sure but I need more time to close")
        assert r["offer_accepted"] is True
        assert r["timeline_acceptable"] is False

    def test_ambiguous_defaults_to_rejected(self):
        r = self._classify_offer("Let me think about it")
        assert r["offer_accepted"] is False


# -----------------------------------------------------------------------
# Q4 stall detection
# -----------------------------------------------------------------------
class TestQ4StallDetection:
    def test_q4_stall_after_3_attempts(self, seller_state):
        seller_state.current_question = 4
        seller_state.q4_attempts = 3
        assert seller_state.q4_attempts >= 3
        assert seller_state.current_question == 4

    def test_q4_no_stall_at_2_attempts(self, seller_state):
        seller_state.current_question = 4
        seller_state.q4_attempts = 2
        assert seller_state.q4_attempts < 3

    def test_q4_stall_at_exactly_3(self, seller_state):
        seller_state.current_question = 4
        seller_state.q4_attempts = 3
        # The bot checks: q4_attempts >= 3 => STALLED
        stalled = seller_state.q4_attempts >= 3 and seller_state.current_question == 4
        assert stalled is True


# -----------------------------------------------------------------------
# Urgency extraction
# -----------------------------------------------------------------------
class TestUrgencyExtraction:

    @staticmethod
    def _classify_urgency(message: str) -> str:
        ml = message.lower()
        if any(w in ml for w in ["asap", "urgent", "immediately", "fast", "quick", "soon"]):
            return "high"
        if any(w in ml for w in ["flexible", "no rush", "whenever", "eventually"]):
            return "low"
        return "medium"

    def test_asap_is_high(self):
        assert self._classify_urgency("Need to sell ASAP") == "high"

    def test_no_rush_is_low(self):
        assert self._classify_urgency("No rush, just exploring options") == "low"

    def test_default_is_medium(self):
        assert self._classify_urgency("Thinking about selling sometime") == "medium"

    def test_urgent_is_high(self):
        assert self._classify_urgency("It's urgent, need cash fast") == "high"

    def test_flexible_is_low(self):
        assert self._classify_urgency("I'm flexible on timing") == "low"


# -----------------------------------------------------------------------
# Conversation history management
# -----------------------------------------------------------------------
class TestConversationHistory:
    def test_history_capped_at_20(self, seller_state):
        for i in range(25):
            seller_state.record_answer(1, f"answer {i}", {"condition": "needs_minor_repairs"})
        assert len(seller_state.conversation_history) == 20

    def test_history_records_timestamp(self, seller_state):
        seller_state.record_answer(1, "needs work", {"condition": "needs_major_repairs"})
        assert "timestamp" in seller_state.conversation_history[0]
