"""Tests for the eval harness -- all Claude API calls are mocked."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from evals.judge import EvalResult, judge_response, run_deterministic_checks, run_eval_suite
from evals.rubrics import RUBRICS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm_response(scores: dict, reasoning: str = "Looks good."):
    """Build a mock LLMResponse with JSON-encoded judge scores."""
    from bots.shared.claude_client import LLMResponse

    payload = {**scores, "reasoning": reasoning}
    return LLMResponse(
        content=json.dumps(payload),
        model="claude-haiku-4-5-20251001",
        input_tokens=100,
        output_tokens=50,
    )


def _make_test_case(**overrides) -> dict:
    base = {
        "id": "JR-TC-TEST",
        "input": "I want to sell my house",
        "expected_output_properties": {
            "max_length": 480,
            "no_urls": True,
            "no_ai_disclosure": True,
            "persona_jorge": True,
        },
        "category": "seller_qualification",
        "bot_type": "seller",
        "description": "test case",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJudgeScoresGoodResponse:
    @pytest.mark.asyncio
    async def test_judge_scores_good_response_above_threshold(self):
        """A clean Jorge response should score above 0.85 and pass."""
        mock_client = AsyncMock()
        mock_client.agenerate = AsyncMock(
            return_value=_mock_llm_response(
                {"correctness": 0.95, "tone": 0.90, "compliance": 1.0},
                reasoning="Clean response, stays in character.",
            )
        )

        tc = _make_test_case()
        good_response = (
            "Happy to help you out! What condition is the house in? "
            "Does it need major repairs, minor fixes, or is it move-in ready?"
        )

        result = await judge_response(
            response=good_response,
            test_case=tc,
            claude_client=mock_client,
            fail_threshold=0.85,
        )

        assert isinstance(result, EvalResult)
        assert result.passed is True
        assert result.scores["correctness"] == 0.95
        assert result.scores["tone"] == 0.90
        assert result.scores["compliance"] == 1.0
        assert result.deterministic_checks["length_ok"] is True
        assert result.deterministic_checks["no_urls"] is True
        assert result.deterministic_checks["no_ai_disclosure"] is True


class TestJudgeScoresBadResponse:
    @pytest.mark.asyncio
    async def test_judge_scores_bad_response_below_threshold(self):
        """A response that discloses AI nature should fail deterministic checks."""
        mock_client = AsyncMock()
        mock_client.agenerate = AsyncMock(
            return_value=_mock_llm_response(
                {"correctness": 0.5, "tone": 0.3, "compliance": 0.0},
                reasoning="Disclosed AI nature, broke character.",
            )
        )

        tc = _make_test_case()
        bad_response = "I'm an AI chatbot made by Anthropic. Visit https://example.com for help."

        result = await judge_response(
            response=bad_response,
            test_case=tc,
            claude_client=mock_client,
            fail_threshold=0.85,
        )

        assert result.passed is False
        # Deterministic checks should catch the AI disclosure and URL
        assert result.deterministic_checks["no_ai_disclosure"] is False
        assert result.deterministic_checks["no_urls"] is False
        # LLM scores are also low
        assert result.scores["compliance"] == 0.0


class TestDeterministicChecks:
    def test_deterministic_checks_catch_long_response(self):
        """A response over 480 chars should fail the length check."""
        long_response = "word " * 120  # ~600 chars
        expected = {"max_length": 480, "no_urls": True, "no_ai_disclosure": True}

        checks = run_deterministic_checks(long_response, expected)

        assert checks["length_ok"] is False
        assert checks["no_urls"] is True
        assert checks["no_ai_disclosure"] is True

    def test_deterministic_checks_pass_clean_response(self):
        """A clean, short response should pass all checks."""
        clean = "Happy to help! What condition is the house in?"
        expected = {"max_length": 480, "no_urls": True, "no_ai_disclosure": True}

        checks = run_deterministic_checks(clean, expected)

        assert all(checks.values())


class TestRunEvalSuite:
    @pytest.mark.asyncio
    async def test_run_eval_suite_loads_golden_dataset(self, tmp_path):
        """run_eval_suite should load the dataset and produce one result per case."""
        # Write a minimal 2-case dataset to tmp
        mini_dataset = [
            _make_test_case(id="JR-TC-A"),
            _make_test_case(id="JR-TC-B"),
        ]
        dataset_file = tmp_path / "golden_dataset.json"
        dataset_file.write_text(json.dumps(mini_dataset))

        mock_client = AsyncMock()
        mock_client.agenerate = AsyncMock(
            return_value=_mock_llm_response(
                {"correctness": 0.90, "tone": 0.90, "compliance": 0.95},
            )
        )

        async def fake_response_generator(tc):
            return "Happy to help! What condition is the house in?"

        results = await run_eval_suite(
            golden_dataset_path=str(dataset_file),
            claude_client=mock_client,
            response_generator=fake_response_generator,
            fail_threshold=0.85,
        )

        assert len(results) == 2
        assert results[0].test_case_id == "JR-TC-A"
        assert results[1].test_case_id == "JR-TC-B"
        assert all(r.passed for r in results)
