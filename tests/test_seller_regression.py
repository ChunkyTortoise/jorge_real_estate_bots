"""Seller bot regression tests — hesitation detection, Q4 stall, price extraction,
condition keywords, offer math, and soft-close invariants."""
import re

import pytest
from unittest.mock import AsyncMock

from bots.seller_bot.jorge_seller_bot import (
    JorgeSellerBot,
    SellerQualificationState,
    _COLLOQUIAL_PRICES,
    _PRICE_PATTERNS,
    _Q4_HESITATION_PHRASES,
    _Q4_SOFT_CLOSE,
)
from bots.shared.claude_client import LLMResponse


# ---------------------------------------------------------------------------
# Helper: replicate the hesitation check used in process_seller_message
# ---------------------------------------------------------------------------
def _is_hesitation(msg: str) -> bool:
    return any(phrase in msg.lower() for phrase in _Q4_HESITATION_PHRASES)


# ---------------------------------------------------------------------------
# Group 1: BUG-04 Hesitation Soft Close Regression (8 tests)
# ---------------------------------------------------------------------------
class TestHesitationDetection:
    def test_let_me_think_about_it(self):
        assert _is_hesitation("let me think about it") is True

    def test_hmm_not_sure(self):
        assert _is_hesitation("hmm not sure") is True

    def test_need_to_think(self):
        assert _is_hesitation("I need to think") is True

    def test_maybe_later(self):
        assert _is_hesitation("maybe later") is True

    def test_get_back_to_you(self):
        assert _is_hesitation("I'll get back to you") is True

    def test_no_hesitation_wife(self):
        assert _is_hesitation("need to talk to my wife") is False

    def test_no_hesitation_sounds_good(self):
        assert _is_hesitation("sounds good let's do it") is False

    def test_no_hesitation_yeah(self):
        assert _is_hesitation("yeah that works") is False


# ---------------------------------------------------------------------------
# Group 2: Q4 Attempt Limit (4 tests)
# ---------------------------------------------------------------------------
class TestQ4AttemptLimit:
    """q4_attempts >= 3 triggers STALLED escalation."""

    def test_zero_attempts_not_stalled(self):
        state = SellerQualificationState(contact_id="c", location_id="l", q4_attempts=0)
        assert state.q4_attempts < 3

    def test_two_attempts_not_stalled(self):
        state = SellerQualificationState(contact_id="c", location_id="l", q4_attempts=2)
        assert state.q4_attempts < 3

    def test_three_attempts_stalled(self):
        state = SellerQualificationState(contact_id="c", location_id="l", q4_attempts=3)
        assert state.q4_attempts >= 3

    def test_four_attempts_stalled(self):
        state = SellerQualificationState(contact_id="c", location_id="l", q4_attempts=4)
        assert state.q4_attempts >= 3


# ---------------------------------------------------------------------------
# Group 3: Price Extraction — Bare Numbers (Haiku Fallback) (6 tests)
# ---------------------------------------------------------------------------
class TestPriceExtractionHaikuFallback:
    """Numbers without $ / k / m / 'thousand' fall through to Claude Haiku."""

    @pytest.fixture
    def bot(self):
        b = JorgeSellerBot()
        return b

    @pytest.mark.asyncio
    async def test_bare_350(self, bot):
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="350000", model="test")
        )
        result = await bot._extract_qualification_data("350", 2)
        assert result["price_expectation"] == 350_000

    @pytest.mark.asyncio
    async def test_maybe_350(self, bot):
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="350000", model="test")
        )
        result = await bot._extract_qualification_data("maybe 350", 2)
        assert result["price_expectation"] == 350_000

    @pytest.mark.asyncio
    async def test_idk_like_500(self, bot):
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="500000", model="test")
        )
        result = await bot._extract_qualification_data("idk like 500", 2)
        assert result["price_expectation"] == 500_000

    @pytest.mark.asyncio
    async def test_around_275(self, bot):
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="275000", model="test")
        )
        result = await bot._extract_qualification_data("around 275", 2)
        assert result["price_expectation"] == 275_000

    @pytest.mark.asyncio
    async def test_bare_1_point_2(self, bot):
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="1200000", model="test")
        )
        result = await bot._extract_qualification_data("1.2", 2)
        assert result["price_expectation"] == 1_200_000

    @pytest.mark.asyncio
    async def test_haiku_returns_85000(self, bot):
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="85000", model="test")
        )
        result = await bot._extract_qualification_data("like 85", 2)
        assert result["price_expectation"] == 85_000


# ---------------------------------------------------------------------------
# Group 4: Colloquial Price Coverage (8 tests)
# ---------------------------------------------------------------------------
class TestColloquialPrices:
    @pytest.fixture
    def bot(self):
        b = JorgeSellerBot()
        # Mock Haiku so it doesn't fire for patterns that DO match
        b.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="0", model="test")
        )
        return b

    @pytest.mark.asyncio
    async def test_mid_fives(self, bot):
        result = await bot._extract_qualification_data("mid fives", 2)
        assert result["price_expectation"] == 550_000

    @pytest.mark.asyncio
    async def test_high_threes(self, bot):
        result = await bot._extract_qualification_data("high threes", 2)
        assert result["price_expectation"] == 375_000

    @pytest.mark.asyncio
    async def test_low_fourhundreds(self, bot):
        """Regex requires no space: 'low fourhundreds' (not 'low four hundreds')."""
        result = await bot._extract_qualification_data("low fourhundreds", 2)
        assert result["price_expectation"] == 425_000

    @pytest.mark.asyncio
    async def test_around_six_hundred(self, bot):
        result = await bot._extract_qualification_data("around six hundred", 2)
        assert result["price_expectation"] == 600_000

    @pytest.mark.asyncio
    async def test_high_fives(self, bot):
        result = await bot._extract_qualification_data("high fives", 2)
        assert result["price_expectation"] == 580_000

    @pytest.mark.asyncio
    async def test_low_fives(self, bot):
        result = await bot._extract_qualification_data("low fives", 2)
        assert result["price_expectation"] == 475_000

    @pytest.mark.asyncio
    async def test_580_thousand(self, bot):
        result = await bot._extract_qualification_data("580 thousand", 2)
        assert result["price_expectation"] == 580_000

    @pytest.mark.asyncio
    async def test_mid_threes_resolved_by_regex(self, bot):
        """'mid threes' is now in _COLLOQUIAL_PRICES → resolved without Claude."""
        bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="350000", model="test")
        )
        result = await bot._extract_qualification_data("mid threes", 2)
        assert result["price_expectation"] == 350_000
        # Regex resolves it — Claude should NOT be called
        bot.claude_client.agenerate.assert_not_awaited()


# ---------------------------------------------------------------------------
# Group 5: Condition Keyword Coverage (6 tests)
# ---------------------------------------------------------------------------
class TestConditionExtraction:
    @pytest.fixture
    def bot(self):
        b = JorgeSellerBot()
        b.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="needs_minor_repairs", model="test")
        )
        return b

    @pytest.mark.asyncio
    async def test_move_in_ready(self, bot):
        result = await bot._extract_qualification_data("it's move in ready", 1)
        assert result["condition"] == "move_in_ready"

    @pytest.mark.asyncio
    async def test_needs_some_work(self, bot):
        """'some work' maps to needs_minor_repairs."""
        result = await bot._extract_qualification_data("needs some work", 1)
        assert result["condition"] == "needs_minor_repairs"

    @pytest.mark.asyncio
    async def test_fixer(self, bot):
        result = await bot._extract_qualification_data("it's a fixer upper", 1)
        assert result["condition"] == "needs_major_repairs"

    @pytest.mark.asyncio
    async def test_cosmetic(self, bot):
        result = await bot._extract_qualification_data("just cosmetic stuff", 1)
        assert result["condition"] == "needs_minor_repairs"

    @pytest.mark.asyncio
    async def test_remodeled(self, bot):
        result = await bot._extract_qualification_data("just remodeled last year", 1)
        assert result["condition"] == "move_in_ready"

    @pytest.mark.asyncio
    async def test_run_down(self, bot):
        result = await bot._extract_qualification_data("pretty run down honestly", 1)
        assert result["condition"] == "needs_major_repairs"


# ---------------------------------------------------------------------------
# Group 6: Offer Math (5 tests)
# ---------------------------------------------------------------------------
class TestOfferMath:
    """Cash offer = int(price_expectation * 0.75). Default price = 300_000."""

    def test_500k(self):
        assert int(500_000 * 0.75) == 375_000

    def test_350k(self):
        assert int(350_000 * 0.75) == 262_500

    def test_1m(self):
        assert int(1_000_000 * 0.75) == 750_000

    def test_default_price(self):
        """When price_expectation is None, default is 300_000."""
        price = None
        assert int((price or 300_000) * 0.75) == 225_000

    def test_275k(self):
        assert int(275_000 * 0.75) == 206_250


# ---------------------------------------------------------------------------
# Group 7: Soft Close Invariants (3 tests)
# ---------------------------------------------------------------------------
class TestSoftCloseInvariants:
    def test_soft_close_no_dollar(self):
        assert "$" not in _Q4_SOFT_CLOSE

    def test_soft_close_no_offer_word(self):
        assert "offer" not in _Q4_SOFT_CLOSE.lower()

    def test_soft_close_under_480_chars(self):
        assert len(_Q4_SOFT_CLOSE) < 480


# ---------------------------------------------------------------------------
# Group 8: _PRICE_PATTERNS regex coverage (5 tests)
# ---------------------------------------------------------------------------
class TestPricePatterns:
    """Direct regex matching against _PRICE_PATTERNS."""

    def _extract_price(self, text: str) -> int | None:
        for pattern, multiplier in _PRICE_PATTERNS:
            m = pattern.search(text)
            if m:
                if multiplier is not None:
                    return int(float(m.group(1).replace(",", "")) * multiplier)
                if m.lastindex and m.lastindex >= 2:
                    return int(m.group(1).replace(",", "") + m.group(2))
                price = int(m.group(1).replace(",", ""))
                if price < 10_000:
                    price *= 1_000
                return price
        return None

    def test_350k(self):
        assert self._extract_price("$350k") == 350_000

    def test_1_2_million(self):
        assert self._extract_price("$1.2m") == 1_200_000

    def test_comma_separated(self):
        assert self._extract_price("$450,000") == 450_000

    def test_plain_dollar(self):
        assert self._extract_price("$375000") == 375_000

    def test_1_point_5_million(self):
        assert self._extract_price("1.5 million") == 1_500_000
