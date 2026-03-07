"""Tests for buyer_prompts.py — template rendering and content validation."""
from __future__ import annotations

import pytest

from bots.buyer_bot.buyer_prompts import (
    BUYER_QUESTIONS,
    BUYER_SYSTEM_PROMPT,
    JORGE_BUYER_PHRASES,
    build_buyer_prompt,
)


# ---------------------------------------------------------------------------
# BUYER_SYSTEM_PROMPT
# ---------------------------------------------------------------------------

class TestBuyerSystemPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(BUYER_SYSTEM_PROMPT, str)
        assert len(BUYER_SYSTEM_PROMPT) > 50

    def test_contains_persona_name(self):
        assert "Jorge" in BUYER_SYSTEM_PROMPT

    def test_contains_ai_disclosure_prohibition(self):
        assert "NEVER reveal you are AI" in BUYER_SYSTEM_PROMPT

    def test_contains_fabrication_prohibition(self):
        assert "NEVER fabricate" in BUYER_SYSTEM_PROMPT

    def test_contains_seller_guardrail(self):
        """Must block seller-adjacent questions (property condition, sell motivation)."""
        prompt_lower = BUYER_SYSTEM_PROMPT.lower()
        assert "seller" in prompt_lower or "sell" in prompt_lower

    def test_contains_word_limit(self):
        assert "100 words" in BUYER_SYSTEM_PROMPT

    def test_no_forbidden_strings(self):
        """System prompt must not leak implementation details."""
        forbidden = ["anthropic", "claude", "language model", "llm", "openai", "gpt"]
        prompt_lower = BUYER_SYSTEM_PROMPT.lower()
        for term in forbidden:
            assert term not in prompt_lower, f"Forbidden term '{term}' found in system prompt"


# ---------------------------------------------------------------------------
# JORGE_BUYER_PHRASES
# ---------------------------------------------------------------------------

class TestJorgeBuyerPhrases:
    def test_is_list(self):
        assert isinstance(JORGE_BUYER_PHRASES, list)

    def test_at_least_3_phrases(self):
        assert len(JORGE_BUYER_PHRASES) >= 3

    def test_all_strings(self):
        for phrase in JORGE_BUYER_PHRASES:
            assert isinstance(phrase, str)
            assert len(phrase) > 5


# ---------------------------------------------------------------------------
# BUYER_QUESTIONS
# ---------------------------------------------------------------------------

class TestBuyerQuestions:
    def test_has_four_questions(self):
        assert len(BUYER_QUESTIONS) == 4
        assert set(BUYER_QUESTIONS.keys()) == {1, 2, 3, 4}

    def test_q1_asks_about_property_preferences(self):
        q1 = BUYER_QUESTIONS[1].lower()
        assert "beds" in q1 or "bedroom" in q1
        assert "price" in q1

    def test_q2_asks_about_financing(self):
        q2 = BUYER_QUESTIONS[2].lower()
        assert "pre-approved" in q2 or "cash" in q2

    def test_q3_asks_about_timeline(self):
        q3 = BUYER_QUESTIONS[3].lower()
        assert "timeline" in q3 or "days" in q3

    def test_q4_asks_about_motivation(self):
        q4 = BUYER_QUESTIONS[4].lower()
        assert "motivation" in q4 or "why" in q4 or "reason" in q4 or "job" in q4

    def test_all_questions_are_nonempty_strings(self):
        for q_num, q_text in BUYER_QUESTIONS.items():
            assert isinstance(q_text, str), f"Q{q_num} is not a string"
            assert len(q_text) > 10, f"Q{q_num} is too short"


# ---------------------------------------------------------------------------
# build_buyer_prompt
# ---------------------------------------------------------------------------

class TestBuildBuyerPrompt:
    def test_renders_without_error(self):
        prompt = build_buyer_prompt(
            current_question=1,
            user_message="3 beds in Dallas under 500k",
            next_question="Are you pre-approved?",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_includes_user_message(self):
        prompt = build_buyer_prompt(
            current_question=1,
            user_message="4 bed 3 bath in Upland",
            next_question="Are you pre-approved?",
        )
        assert "4 bed 3 bath in Upland" in prompt

    def test_includes_next_question(self):
        prompt = build_buyer_prompt(
            current_question=2,
            user_message="Yes, pre-approved",
            next_question="What is your timeline?",
        )
        assert "What is your timeline?" in prompt

    def test_includes_current_question_text_when_provided(self):
        prompt = build_buyer_prompt(
            current_question=1,
            user_message="something",
            next_question="next",
            current_question_text="What are you looking for?",
        )
        assert "What are you looking for?" in prompt

    def test_uses_buyer_questions_dict_as_fallback(self):
        """When current_question_text is empty, falls back to BUYER_QUESTIONS."""
        prompt = build_buyer_prompt(
            current_question=1,
            user_message="test",
            next_question="next",
        )
        assert BUYER_QUESTIONS[1] in prompt or "beds" in prompt.lower()

    def test_contains_seller_prohibition(self):
        """The prompt template must include seller-question guardrails."""
        prompt = build_buyer_prompt(1, "test", "next")
        prompt_lower = prompt.lower()
        assert "sell" in prompt_lower or "condition" in prompt_lower

    def test_contains_qualification_sequence(self):
        prompt = build_buyer_prompt(1, "test", "next")
        assert "Q1" in prompt
        assert "Q2" in prompt
        assert "Q3" in prompt
        assert "Q4" in prompt

    def test_no_forbidden_strings_in_output(self):
        """Rendered prompt must not expose AI internals."""
        prompt = build_buyer_prompt(1, "test", "next")
        prompt_lower = prompt.lower()
        forbidden = ["anthropic", "claude", "language model", "openai"]
        for term in forbidden:
            assert term not in prompt_lower, f"Forbidden term '{term}' found in prompt"

    def test_all_questions_render(self):
        """Every question number (1-4) can be passed without errors."""
        for q in range(1, 5):
            prompt = build_buyer_prompt(
                current_question=q,
                user_message=f"answer for Q{q}",
                next_question=f"next after Q{q}",
            )
            assert isinstance(prompt, str)
            assert len(prompt) > 20
