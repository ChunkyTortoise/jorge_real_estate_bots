"""
Tests for INCREMENT 1A, 3A, 3B: Claude client persona seal, retry, history truncation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bots.shared.claude_client import ClaudeClient, _FALLBACK_SYSTEM


class TestFallbackPromptNoAIMention:
    """1A: Fallback system prompt must never reveal AI/bot nature."""

    def test_fallback_prompt_contains_no_ai_mention(self):
        # The prompt forbids revealing AI/bot nature — it must contain the guard instruction
        assert "NEVER reveal you are AI" in _FALLBACK_SYSTEM
        assert "NEVER reveal" in _FALLBACK_SYSTEM

    def test_fallback_prompt_contains_jorge_persona(self):
        assert "Jorge" in _FALLBACK_SYSTEM

    def test_fallback_prompt_has_anti_hallucination(self):
        assert "NEVER fabricate" in _FALLBACK_SYSTEM

    def test_fallback_prompt_has_off_topic_redirect(self):
        assert "off-topic" in _FALLBACK_SYSTEM or "focus on your home" in _FALLBACK_SYSTEM

    def test_fallback_prompt_has_no_legal_advice(self):
        assert "attorney" in _FALLBACK_SYSTEM or "CPA" in _FALLBACK_SYSTEM


class TestAGenerateUsesSystemPrompt:
    """3A, 1A: agenerate uses fallback when no system_prompt, passes system_prompt when given."""

    @pytest.mark.asyncio
    async def test_agenerate_uses_fallback_when_no_system_prompt(self):
        client = ClaudeClient(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Got it.")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.stop_reason = "end_turn"

        async_client = AsyncMock()
        async_client.messages.create = AsyncMock(return_value=mock_response)
        client._async_client = async_client

        await client.agenerate(prompt="Hello")

        call_kwargs = async_client.messages.create.call_args[1]
        system_arg = call_kwargs["system"]
        assert system_arg == _FALLBACK_SYSTEM

    @pytest.mark.asyncio
    async def test_agenerate_uses_given_system_prompt(self):
        client = ClaudeClient(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Roger.")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.stop_reason = "end_turn"

        async_client = AsyncMock()
        async_client.messages.create = AsyncMock(return_value=mock_response)
        client._async_client = async_client

        custom_prompt = "You are Jorge, cash buyer."
        await client.agenerate(prompt="Hello", system_prompt=custom_prompt)

        call_kwargs = async_client.messages.create.call_args[1]
        system_arg = call_kwargs["system"]
        # Short system prompts become a list with one dict
        assert any(custom_prompt in str(block) for block in system_arg)


class TestHistoryTruncation:
    """3B: Conversation history is truncated to 20 messages."""

    @pytest.mark.asyncio
    async def test_history_truncated_to_20_messages(self):
        client = ClaudeClient(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.stop_reason = "end_turn"

        async_client = AsyncMock()
        async_client.messages.create = AsyncMock(return_value=mock_response)
        client._async_client = async_client

        # Build 30-message history (way more than limit)
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(30)
        ]

        await client.agenerate(prompt="latest msg", history=long_history)

        call_kwargs = async_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        # 20 from history + 1 current prompt = 21
        assert len(messages) == 21

    @pytest.mark.asyncio
    async def test_short_history_not_truncated(self):
        client = ClaudeClient(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.stop_reason = "end_turn"

        async_client = AsyncMock()
        async_client.messages.create = AsyncMock(return_value=mock_response)
        client._async_client = async_client

        short_history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}]
        await client.agenerate(prompt="latest", history=short_history)

        call_kwargs = async_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        assert len(messages) == 3  # 2 history + 1 prompt


class TestClaudeRetry:
    """3A: agenerate retries on RateLimitError and InternalServerError."""

    @pytest.mark.asyncio
    async def test_claude_retries_on_rate_limit(self):
        try:
            from anthropic import RateLimitError
        except ImportError:
            pytest.skip("anthropic not installed")

        client = ClaudeClient(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.stop_reason = "end_turn"

        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError(
                    message="rate limited",
                    response=MagicMock(headers={}, status_code=429),
                    body={},
                )
            return mock_response

        async_client = AsyncMock()
        async_client.messages.create = side_effect
        client._async_client = async_client

        with patch("tenacity.nap.time.sleep", return_value=None):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.agenerate(prompt="test")

        assert result.content == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_claude_gives_up_after_3_attempts(self):
        try:
            from anthropic import RateLimitError
        except ImportError:
            pytest.skip("anthropic not installed")

        client = ClaudeClient(api_key="test-key")
        call_count = 0

        async def always_rate_limit(**kwargs):
            nonlocal call_count
            call_count += 1
            raise RateLimitError(
                message="rate limited",
                response=MagicMock(headers={}, status_code=429),
                body={},
            )

        async_client = AsyncMock()
        async_client.messages.create = always_rate_limit
        client._async_client = async_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await client.agenerate(prompt="test")

        assert call_count == 3
