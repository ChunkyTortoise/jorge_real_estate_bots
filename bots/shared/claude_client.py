"""
Claude AI Client for Jorge's Real Estate Bots.

Simplified version of EnterpriseHub's LLM client, focused on Claude only.
Provides intelligent routing, prompt caching, and async support.
"""
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator, Dict, List, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bots.shared.config import settings
from bots.shared.logger import get_logger

logger = get_logger(__name__)

# Fallback system prompt when no system_prompt is passed.
# NEVER reveals AI/bot nature. NEVER fabricates real estate data.
_FALLBACK_SYSTEM = (
    "You are Jorge, a direct real estate professional in Rancho Cucamonga. "
    "NEVER reveal you are AI, a bot, or automated. "
    "NEVER fabricate listings, prices, or addresses. "
    "If unsure, say you'll check and get back to them. "
    "If conversation goes off-topic, redirect: 'Hey, let's focus on your home situation.' "
    "NEVER provide legal, tax, or financial advice — say 'That's a question for your attorney/CPA.' "
    "Keep responses under 160 chars. Real estate only."
)

# Anthropic exception types for retry logic
try:
    from anthropic import RateLimitError as _RateLimitError, InternalServerError as _InternalServerError
    _CLAUDE_RETRY_EXCEPTIONS = (_RateLimitError, _InternalServerError)
except ImportError:
    _CLAUDE_RETRY_EXCEPTIONS = (Exception,)


class TaskComplexity(Enum):
    """Task complexity for intelligent routing."""
    ROUTINE = "routine"      # Lead categorization, basic scoring (Haiku)
    COMPLEX = "complex"      # Lead qualification, property matching (Sonnet)
    HIGH_STAKES = "high_stakes"  # Seller negotiations, pricing strategies (Opus)


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    finish_reason: Optional[str] = None


class ClaudeClient:
    """
    Claude AI client optimized for Jorge's Real Estate Bots.

    Features:
    - Intelligent model routing based on task complexity
    - Prompt caching for repeated system prompts
    - Async support for FastAPI integration
    - Streaming responses for real-time UI updates
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude client.

        Args:
            api_key: Optional API key override
        """
        self.api_key = api_key or settings.anthropic_api_key
        self._client = None
        self._async_client = None

    def _init_client(self):
        """Initialize synchronous client (lazy loading)."""
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
            logger.info("Claude sync client initialized")

    def _init_async_client(self):
        """Initialize asynchronous client (lazy loading)."""
        if self._async_client is None:
            from anthropic import AsyncAnthropic
            self._async_client = AsyncAnthropic(api_key=self.api_key)
            logger.info("Claude async client initialized")

    def _get_routed_model(self, complexity: Optional[TaskComplexity] = None) -> str:
        """
        Determine the best model based on task complexity.

        Routing Strategy:
        - ROUTINE: Haiku (fast, cheap) - lead categorization, updates
        - COMPLEX: Sonnet (default) - qualification, analysis
        - HIGH_STAKES: Opus (premium) - negotiations, pricing

        Args:
            complexity: Task complexity level

        Returns:
            Model name to use
        """
        if not complexity:
            return settings.claude_sonnet_model

        if complexity == TaskComplexity.ROUTINE:
            return settings.claude_haiku_model
        elif complexity == TaskComplexity.HIGH_STAKES:
            return settings.claude_opus_model
        else:
            return settings.claude_sonnet_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(_CLAUDE_RETRY_EXCEPTIONS),
        reraise=True,
    )
    async def agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        complexity: Optional[TaskComplexity] = None,
        enable_caching: bool = True,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from Claude (Asynchronous).

        Args:
            prompt: User prompt/question
            system_prompt: System instructions
            history: Conversation history
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            complexity: Task complexity for model routing
            enable_caching: Enable prompt caching for long system prompts

        Returns:
            LLMResponse with content and metadata
        """
        self._init_async_client()

        # Route to appropriate model
        target_model = self._get_routed_model(complexity)

        # Truncate history to 20 messages (10 turns) to avoid context bloat
        if history and len(history) > 20:
            history = history[-20:]

        # Build messages
        messages = history.copy() if history else []
        messages.append({"role": "user", "content": prompt})

        # Build system prompt with optional caching
        system_blocks = []
        if system_prompt:
            # Cache long system prompts (>1024 chars ≈ 250 tokens)
            if enable_caching and len(system_prompt) > 1024:
                system_blocks.append({
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                })
                logger.debug(f"Prompt caching enabled for {len(system_prompt)} char system prompt")
            else:
                system_blocks.append({"type": "text", "text": system_prompt})

        try:
            response = await self._async_client.messages.create(
                model=target_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_blocks if system_blocks else _FALLBACK_SYSTEM,
                messages=messages,
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
            )

            # Extract metrics
            input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else None
            output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else None
            cache_creation = getattr(response.usage, 'cache_creation_input_tokens', 0)
            cache_read = getattr(response.usage, 'cache_read_input_tokens', 0)

            # Log cache performance
            if cache_read > 0:
                savings_pct = (cache_read / (input_tokens or 1)) * 100
                logger.info(f"Cache hit! Read {cache_read} tokens ({savings_pct:.1f}% savings)")

            return LLMResponse(
                content=response.content[0].text,
                model=target_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_input_tokens=cache_creation,
                cache_read_input_tokens=cache_read,
                finish_reason=response.stop_reason
            )

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def astream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        complexity: Optional[TaskComplexity] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream response chunks from Claude (Asynchronous).

        Args:
            prompt: User prompt
            system_prompt: System instructions
            complexity: Task complexity for model routing

        Yields:
            Response chunks as they're generated
        """
        self._init_async_client()

        target_model = self._get_routed_model(complexity)

        async with self._async_client.messages.stream(
            model=target_model,
            max_tokens=2048,
            system=system_prompt or _FALLBACK_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        complexity: Optional[TaskComplexity] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from Claude (Synchronous).

        Args:
            prompt: User prompt/question
            system_prompt: System instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            complexity: Task complexity for model routing

        Returns:
            LLMResponse with content and metadata
        """
        self._init_client()

        target_model = self._get_routed_model(complexity)

        response = self._client.messages.create(
            model=target_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or _FALLBACK_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )

        input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else None
        output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else None

        return LLMResponse(
            content=response.content[0].text,
            model=target_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=response.stop_reason
        )


# Global client instance
def get_claude_client() -> ClaudeClient:
    """Get a Claude client instance."""
    return ClaudeClient()
