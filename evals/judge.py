"""LLM-as-judge eval harness for Jorge Real Estate Bots.

Uses Claude Haiku as a cheap judge to score bot responses against rubrics,
plus deterministic checks reused from the production response_filter.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from bots.shared.response_filter import (
    _IDENTITY_PATTERNS,
    _URL_PATTERN,
    _MAX_LENGTH,
)
from evals.rubrics import RUBRICS

# Haiku model for cheap judging
_JUDGE_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class EvalResult:
    """Result from evaluating a single test case."""

    test_case_id: str
    scores: dict[str, float]  # rubric_name -> 0.0-1.0
    passed: bool
    deterministic_checks: dict[str, bool]
    reasoning: str


def run_deterministic_checks(response: str, expected: dict) -> dict[str, bool]:
    """Run rule-based checks reusing production response_filter patterns.

    Returns a dict of check_name -> passed (True = OK).
    """
    checks: dict[str, bool] = {}

    # Length check
    if "max_length" in expected:
        checks["length_ok"] = len(response) <= expected["max_length"]
    else:
        checks["length_ok"] = len(response) <= _MAX_LENGTH

    # URL check
    if expected.get("no_urls", False):
        checks["no_urls"] = _URL_PATTERN.search(response) is None

    # AI disclosure check -- reuse the 26 identity patterns from response_filter
    if expected.get("no_ai_disclosure", False):
        disclosed = False
        for pattern, _ in _IDENTITY_PATTERNS:
            if pattern.search(response):
                disclosed = True
                break
        checks["no_ai_disclosure"] = not disclosed

    return checks


def _build_judge_prompt(
    response: str,
    test_case: dict,
    rubrics: dict[str, str],
) -> str:
    """Build the prompt for the LLM judge."""
    rubric_text = "\n".join(
        f"- {name}: {description}" for name, description in rubrics.items()
    )
    return f"""You are an eval judge for a real estate SMS chatbot named Jorge.

CONTEXT:
- Bot type: {test_case.get("bot_type", "unknown")}
- Category: {test_case.get("category", "unknown")}
- Test description: {test_case.get("description", "")}
- User message: "{test_case.get("input", "")}"

BOT RESPONSE TO EVALUATE:
"{response}"

RUBRICS (score each 0.0 to 1.0):
{rubric_text}

Return ONLY valid JSON with this exact structure, no other text:
{{
  "correctness": <float 0.0-1.0>,
  "tone": <float 0.0-1.0>,
  "compliance": <float 0.0-1.0>,
  "reasoning": "<one sentence explaining your scores>"
}}"""


def _parse_judge_response(raw: str) -> dict:
    """Extract JSON from judge response, handling markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Strip ```json ... ``` fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


async def judge_response(
    response: str,
    test_case: dict,
    rubrics: Optional[dict[str, str]] = None,
    *,
    claude_client=None,
    fail_threshold: float = 0.85,
) -> EvalResult:
    """Use Claude Haiku as judge to score a response against rubrics.

    Args:
        response: The bot response to evaluate.
        test_case: Test case dict from golden_dataset.json.
        rubrics: Rubric dict (defaults to RUBRICS).
        claude_client: ClaudeClient instance (created if None).
        fail_threshold: Minimum average score to pass.

    Returns:
        EvalResult with scores, deterministic checks, and pass/fail.
    """
    rubrics = rubrics or RUBRICS
    expected = test_case.get("expected_output_properties", {})

    # 1. Deterministic checks (free, no API call)
    det_checks = run_deterministic_checks(response, expected)

    # 2. LLM judge call via Claude Haiku
    if claude_client is None:
        from bots.shared.claude_client import ClaudeClient, TaskComplexity

        claude_client = ClaudeClient()

    from bots.shared.claude_client import TaskComplexity

    prompt = _build_judge_prompt(response, test_case, rubrics)
    llm_response = await claude_client.agenerate(
        prompt=prompt,
        system_prompt="You are a strict eval judge. Return only valid JSON.",
        max_tokens=256,
        temperature=0.0,
        complexity=TaskComplexity.ROUTINE,  # Uses Haiku
    )

    parsed = _parse_judge_response(llm_response.content)
    scores = {
        name: float(parsed.get(name, 0.0))
        for name in rubrics
    }
    reasoning = parsed.get("reasoning", "")

    # 3. Pass/fail: average LLM score >= threshold AND all deterministic checks pass
    avg_score = sum(scores.values()) / len(scores) if scores else 0.0
    all_det_passed = all(det_checks.values())
    passed = avg_score >= fail_threshold and all_det_passed

    return EvalResult(
        test_case_id=test_case["id"],
        scores=scores,
        passed=passed,
        deterministic_checks=det_checks,
        reasoning=reasoning,
    )


async def run_eval_suite(
    golden_dataset_path: str = "evals/golden_dataset.json",
    fail_threshold: float = 0.85,
    *,
    claude_client=None,
    response_generator=None,
) -> list[EvalResult]:
    """Run all test cases and return results.

    Args:
        golden_dataset_path: Path to golden dataset JSON.
        fail_threshold: Minimum average score to pass each case.
        claude_client: ClaudeClient instance for judge calls.
        response_generator: Async callable(test_case) -> str that produces
            the bot response to evaluate. If None, uses a placeholder.

    Returns:
        List of EvalResult for each test case.
    """
    dataset_path = Path(golden_dataset_path)
    with open(dataset_path) as f:
        test_cases = json.load(f)

    if claude_client is None:
        from bots.shared.claude_client import ClaudeClient

        claude_client = ClaudeClient()

    results: list[EvalResult] = []
    for tc in test_cases:
        if response_generator:
            response = await response_generator(tc)
        else:
            # Placeholder: in production, wire this to the actual bot
            response = ""

        result = await judge_response(
            response=response,
            test_case=tc,
            claude_client=claude_client,
            fail_threshold=fail_threshold,
        )
        results.append(result)

    return results
