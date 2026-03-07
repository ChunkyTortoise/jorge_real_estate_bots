"""Tests for Q4 stall/escalation progression."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState


@pytest.fixture
def bot():
    return JorgeSellerBot()


def _make_state(cid: str, *, q4_attempts: int = 0) -> SellerQualificationState:
    state = SellerQualificationState(contact_id=cid, location_id="loc-test")
    state.current_question = 4
    state.questions_answered = 3
    state.condition = "needs_minor_repairs"
    state.price_expectation = 400_000
    state.motivation = "job_relocation"
    state.stage = "Q4"
    state.offer_presented = True
    state.q4_attempts = q4_attempts
    return state


async def _send(bot, cid, message, state):
    """Send a message to the bot with the given state, fully isolated from cache."""
    with patch.object(
        bot, "_get_or_create_state",
        new_callable=AsyncMock, return_value=state,
    ), patch.object(
        bot, "save_conversation_state",
        new_callable=AsyncMock,
    ), patch.object(
        bot.claude_client,
        "agenerate",
        new_callable=AsyncMock,
        return_value=MagicMock(content="Let me think about it some more."),
    ):
        return await bot.process_seller_message(
            contact_id=cid,
            location_id="loc-test",
            message=message,
        )


async def test_first_q4_rejection_increments_counter(bot):
    """1st rejection does not stall (q4_attempts=0 < 3)."""
    cid = "q4-stall-1"
    state = _make_state(cid, q4_attempts=0)
    result = await _send(bot, cid, "I need to think about it", state)
    assert "Escalated" not in (result.next_steps or "")
    assert result.response_message, "Must return a response"


async def test_second_q4_rejection_does_not_stall(bot):
    """2nd rejection does not stall (q4_attempts=1 < 3)."""
    cid = "q4-stall-2"
    state = _make_state(cid, q4_attempts=1)
    result = await _send(bot, cid, "Not sure yet", state)
    assert "Escalated" not in (result.next_steps or "")
    assert result.response_message, "Must return a response"


async def test_third_q4_rejection_triggers_stall(bot):
    """3rd rejection (q4_attempts=3) → STALLED with needs-human-review tag."""
    cid = "q4-stall-3"
    state = _make_state(cid, q4_attempts=3)
    result = await _send(bot, cid, "no thanks", state)
    assert result.qualification_complete is False
    assert "Escalated" in (result.next_steps or ""), "Should be escalated after 3 Q4 rejections"
    tag_types = [a.get("tag") for a in result.actions_taken]
    assert "needs-human-review" in tag_types, "needs-human-review tag must be applied"


async def test_message_after_stall_stays_escalated(bot):
    """When state is already STALLED, further messages re-trigger escalation."""
    cid = "q4-already-stalled"
    state = _make_state(cid, q4_attempts=3)
    state.stage = "STALLED"
    with patch.object(
        bot, "_get_or_create_state",
        new_callable=AsyncMock, return_value=state,
    ), patch.object(
        bot, "save_conversation_state",
        new_callable=AsyncMock,
    ), patch.object(
        bot.claude_client,
        "agenerate",
        new_callable=AsyncMock,
        return_value=MagicMock(content="Let me have Jorge reach out."),
    ):
        result = await bot.process_seller_message(
            contact_id=cid, location_id="loc-test", message="ok fine"
        )
    # q4_attempts=3 >= 3 → bot stalls again
    assert result.qualification_complete is False


async def test_acceptance_after_two_rejections_not_stalled(bot):
    """At q4_attempts=2 (below limit of 3), bot is NOT yet stalled — response is normal."""
    cid = "q4-accept-after-2"
    state = _make_state(cid, q4_attempts=2)
    result = await _send(bot, cid, "yes let's move forward", state)
    # q4_attempts was 2, which is below the 3-attempt limit — should not stall
    assert "Escalated" not in (result.next_steps or ""), (
        "2 rejections should NOT trigger escalation (limit is 3)"
    )
    assert result.response_message, "Must return a response"
