"""
Tests for INCREMENT 1B, 1D: Seller bot persona seal and Jorge-voice fallbacks.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bots.seller_bot.jorge_seller_bot import (
    JorgeSellerBot,
    SELLER_SYSTEM_PROMPT,
    SellerQualificationState,
)
from bots.shared.claude_client import LLMResponse


class TestSellerSystemPrompt:
    """1B: Seller bot passes explicit system_prompt to Claude."""

    def test_seller_system_prompt_contains_no_ai_mention(self):
        # The prompt forbids revealing AI/bot nature — it must contain the guard instruction
        assert "NEVER reveal you are AI" in SELLER_SYSTEM_PROMPT
        assert "NEVER reveal" in SELLER_SYSTEM_PROMPT

    def test_seller_system_prompt_has_anti_hallucination(self):
        assert "NEVER fabricate" in SELLER_SYSTEM_PROMPT

    def test_seller_system_prompt_has_off_topic_redirect(self):
        assert "off-topic" in SELLER_SYSTEM_PROMPT or "home situation" in SELLER_SYSTEM_PROMPT

    def test_seller_system_prompt_has_no_legal_advice_guard(self):
        assert "attorney" in SELLER_SYSTEM_PROMPT or "CPA" in SELLER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_seller_bot_passes_system_prompt_to_claude(self):
        """agenerate must receive SELLER_SYSTEM_PROMPT when generating responses."""
        bot = JorgeSellerBot()

        # Mock Claude client
        mock_llm_response = LLMResponse(content="What condition is the house in?", model="test")
        captured_kwargs = {}

        async def mock_agenerate(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_llm_response

        bot.claude_client.agenerate = mock_agenerate

        # Mock cache (Redis)
        bot.cache = AsyncMock()
        bot.cache.get = AsyncMock(return_value=None)
        bot.cache.set = AsyncMock()
        bot.cache.delete = AsyncMock()

        # Create a state at Q1 so Claude is invoked (Q0 returns immediately)
        state = SellerQualificationState(
            contact_id="test_contact",
            location_id="test_loc",
            current_question=1,
            stage="Q1",
        )
        bot.cache.get = AsyncMock(return_value={
            "contact_id": "test_contact",
            "location_id": "test_loc",
            "current_question": 1,
            "questions_answered": 0,
            "is_qualified": False,
            "stage": "Q1",
            "condition": None,
            "price_expectation": None,
            "motivation": None,
            "urgency": None,
            "offer_accepted": None,
            "timeline_acceptable": None,
            "conversation_history": [],
            "extracted_data": {},
            "last_interaction": None,
            "conversation_started": "2026-01-01T00:00:00",
        })

        with patch("bots.seller_bot.jorge_seller_bot.upsert_contact", new_callable=AsyncMock):
            with patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new_callable=AsyncMock):
                with patch.object(bot, "_apply_ghl_actions", new_callable=AsyncMock):
                    await bot.process_seller_message(
                        contact_id="test_contact",
                        location_id="test_loc",
                        message="It needs some repairs",
                    )

        assert "system_prompt" in captured_kwargs
        assert captured_kwargs["system_prompt"] == SELLER_SYSTEM_PROMPT


class TestSellerFallbackMessages:
    """1D: Fallback messages must sound like Jorge, not corporate."""

    def test_get_fallback_response_last_question_sounds_like_jorge(self):
        bot = JorgeSellerBot()
        # When question_num+1 is out of range (question 4 = last), should return Jorge fallback
        msg = bot._get_fallback_response(4)
        assert "Our team" not in msg
        assert "interest" not in msg.lower() or "jorge" in msg.lower() or "text" in msg.lower()

    def test_create_fallback_result_sounds_like_jorge(self):
        bot = JorgeSellerBot()
        result = bot._create_fallback_result()
        assert "Our team" not in result.response_message
        assert "shortly" in result.response_message or "back" in result.response_message
        # Should NOT contain corporate language
        assert "interest in selling" not in result.response_message

    def test_fallback_result_does_not_say_our_team(self):
        bot = JorgeSellerBot()
        result = bot._create_fallback_result()
        assert "Our team" not in result.response_message

    def test_fallback_response_for_no_next_question_is_jorge_voice(self):
        bot = JorgeSellerBot()
        msg = bot._get_fallback_response(4)
        # Should have Jorge-style text
        assert len(msg) > 0
        assert "Our team will review" not in msg


class TestJorgeActiveTakeover:
    """Jorge-Active tag causes bot to go silent (manual takeover)."""

    @pytest.mark.asyncio
    async def test_jorge_active_tag_in_contact_info_returns_empty_response(self):
        """Bot skips processing and returns empty response_message when tag is in contact_info."""
        bot = JorgeSellerBot()
        bot.cache = AsyncMock()
        bot.cache.get = AsyncMock(return_value=None)
        bot.cache.set = AsyncMock()
        bot.ghl_client = AsyncMock()

        result = await bot.process_seller_message(
            contact_id="test_contact",
            location_id="test_location",
            message="I want to sell",
            contact_info={"tags": ["Jorge-Active", "Needs Qualifying"]},
        )

        assert result.response_message == ""
        assert "Jorge" in result.next_steps
        # GHL client should NOT have been called to fetch contact (tags already in contact_info)
        bot.ghl_client.get_contact.assert_not_called()

    @pytest.mark.asyncio
    async def test_jorge_active_tag_fetched_from_ghl_when_not_in_contact_info(self):
        """Bot fetches contact from GHL to check tags when contact_info lacks them."""
        bot = JorgeSellerBot()
        bot.cache = AsyncMock()
        bot.cache.get = AsyncMock(return_value=None)
        bot.cache.set = AsyncMock()
        bot.ghl_client = AsyncMock()
        bot.ghl_client.get_contact = AsyncMock(return_value={"tags": ["Jorge-Active"]})

        result = await bot.process_seller_message(
            contact_id="test_contact",
            location_id="test_location",
            message="I want to sell",
            contact_info={"name": "John"},  # no tags key
        )

        assert result.response_message == ""
        bot.ghl_client.get_contact.assert_called_once_with("test_contact")

    @pytest.mark.asyncio
    async def test_no_jorge_active_tag_proceeds_normally(self):
        """Bot processes normally when Jorge-Active tag is absent."""
        bot = JorgeSellerBot()
        bot.cache = AsyncMock()
        bot.cache.get = AsyncMock(return_value=None)
        bot.cache.set = AsyncMock()
        bot.ghl_client = AsyncMock()
        bot.ghl_client.get_contact = AsyncMock(return_value={"tags": ["Needs Qualifying"]})
        bot.ghl_client.add_tag = AsyncMock(return_value=True)
        bot.ghl_client.update_contact = AsyncMock(return_value={})
        bot.claude_client = AsyncMock()

        from bots.shared.claude_client import LLMResponse
        bot.claude_client.agenerate = AsyncMock(return_value=LLMResponse(
            content='{"message": "What condition is the house in?", "should_advance": false, "extracted_data": {}}',
            model="test",
        ))

        result = await bot.process_seller_message(
            contact_id="test_contact",
            location_id="test_location",
            message="Hi",
            contact_info={"name": "John"},
        )

        # Bot should reply (not empty)
        assert result.response_message != ""
