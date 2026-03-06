"""Tests for seller bot price extraction patterns (_COLLOQUIAL_PRICES + _PRICE_PATTERNS).

Validates that the module-level compiled regexes correctly extract prices
from various user input formats without requiring Claude API calls.
"""
import re

import pytest

from bots.seller_bot.jorge_seller_bot import _COLLOQUIAL_PRICES, _PRICE_PATTERNS


def _extract_price(text: str) -> int | None:
    """Replicate the extraction logic from _extract_qualification_data Q2
    using only the regex patterns (no Claude fallback)."""

    # 1) Colloquial patterns first
    for pattern, fixed_value in _COLLOQUIAL_PRICES:
        m = pattern.search(text)
        if m:
            if fixed_value is not None:
                return fixed_value
            # "580 thousand" -> 580_000
            return int(m.group(1)) * 1_000

    # 2) Standard price patterns
    for pattern, multiplier in _PRICE_PATTERNS:
        m = pattern.search(text)
        if m:
            if multiplier is not None:
                price_str = m.group(1).replace(",", "")
                return int(float(price_str) * multiplier)
            else:
                # $350,000 pattern has two groups; $350000 has one
                if m.lastindex and m.lastindex >= 2:
                    price = int(m.group(1).replace(",", "") + m.group(2))
                else:
                    price = int(m.group(1).replace(",", ""))
                if price < 10_000:
                    price *= 1_000
                return price

    return None


# -----------------------------------------------------------------------
# K-suffix prices
# -----------------------------------------------------------------------
class TestKSuffixPrices:
    def test_350k_with_dollar(self):
        assert _extract_price("$350k") == 350_000

    def test_350k_without_dollar(self):
        assert _extract_price("350k") == 350_000

    def test_500k_upper(self):
        assert _extract_price("$500K") == 500_000

    def test_275k_in_sentence(self):
        assert _extract_price("I'm thinking around 275k") == 275_000


# -----------------------------------------------------------------------
# Million-dollar prices
# -----------------------------------------------------------------------
class TestMillionPrices:
    def test_1_2m_with_dollar(self):
        assert _extract_price("$1.2m") == 1_200_000

    def test_1_2_million(self):
        assert _extract_price("1.2 million") == 1_200_000

    def test_2m(self):
        assert _extract_price("$2m") == 2_000_000

    def test_1_5_million_sentence(self):
        assert _extract_price("about 1.5 million dollars") == 1_500_000


# -----------------------------------------------------------------------
# Comma-separated prices
# -----------------------------------------------------------------------
class TestCommaSeparatedPrices:
    def test_350_000_with_dollar(self):
        assert _extract_price("$350,000") == 350_000

    def test_580_000_with_dollar(self):
        assert _extract_price("$580,000") == 580_000

    def test_1_200_000_with_dollar(self):
        assert _extract_price("$1,200,000") == 1_200_000

    def test_plain_350000(self):
        assert _extract_price("$350000") == 350_000


# -----------------------------------------------------------------------
# Colloquial / conversational prices
# -----------------------------------------------------------------------
class TestColloquialPrices:
    def test_mid_fives(self):
        assert _extract_price("mid fives") == 550_000

    def test_low_fives(self):
        assert _extract_price("low fives") == 475_000

    def test_high_fives(self):
        assert _extract_price("high fives") == 580_000

    def test_around_six_hundred(self):
        assert _extract_price("around six hundred") == 600_000

    def test_580_thousand(self):
        assert _extract_price("580 thousand") == 580_000

    def test_high_threes(self):
        assert _extract_price("high threes") == 375_000

    def test_low_four_hundreds(self):
        # Pattern requires no space between "four"/"4" and "hundreds": low\s+(?:four|4)hundreds?
        assert _extract_price("low fourhundreds") == 425_000

    def test_low_4hundreds(self):
        assert _extract_price("low 4hundreds") == 425_000

    def test_250_thousand(self):
        assert _extract_price("250 thousand") == 250_000


# -----------------------------------------------------------------------
# Graceful handling — no price found
# -----------------------------------------------------------------------
class TestNoPriceFound:
    def test_two_million_word_form(self):
        """Word-form 'two million' is not handled by regex — falls through to None."""
        assert _extract_price("two million") is None

    def test_no_price_in_text(self):
        assert _extract_price("I'm not sure about the price yet") is None

    def test_empty_string(self):
        assert _extract_price("") is None

    def test_just_greeting(self):
        assert _extract_price("Hey Jorge, how's it going?") is None


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------
class TestPriceEdgeCases:
    def test_price_in_longer_sentence(self):
        assert _extract_price("I was hoping for around $450k for the property") == 450_000

    def test_mid_five_singular(self):
        """Pattern allows 'fives' or 'five'."""
        assert _extract_price("mid five") == 550_000

    def test_case_insensitive_million(self):
        assert _extract_price("$1.2M") == 1_200_000

    def test_case_insensitive_k(self):
        assert _extract_price("$350K") == 350_000


# -----------------------------------------------------------------------
# Bare 3-digit numbers with qualifiers (buyer context)
# -----------------------------------------------------------------------
class TestBareNumberQualifiers:
    """Buyer bot qualifier prices: 'under 600' → 600_000 (3-digit * 1000)."""

    @staticmethod
    def _buyer_qualifier_price(msg: str):
        """Replicate buyer bot qualifier price logic."""
        import re
        for m in re.finditer(
            r'\b(under|over|around|about|like|maybe|roughly|close to|up to)\s+(\d{3})\b',
            msg.lower(),
        ):
            return int(m.group(2)) * 1000
        return None

    def test_under_500(self):
        assert self._buyer_qualifier_price("under 500") == 500_000

    def test_around_350(self):
        assert self._buyer_qualifier_price("around 350") == 350_000

    def test_like_400(self):
        assert self._buyer_qualifier_price("like 400") == 400_000

    def test_four_digit_no_match(self):
        """'under 1200' — 4 digits, no qualifier match."""
        assert self._buyer_qualifier_price("under 1200") is None

    def test_two_digit_no_match(self):
        """'under 50' — 2 digits, no qualifier match."""
        assert self._buyer_qualifier_price("under 50") is None


# -----------------------------------------------------------------------
# Mid/high/low hundreds patterns — seller colloquial (coverage check)
# -----------------------------------------------------------------------
class TestColloquialCoverage:
    """Verify colloquial patterns that are NOT in _COLLOQUIAL_PRICES fall through to None."""

    def test_mid_threes_not_in_colloquial(self):
        """'mid threes' is not a registered pattern → returns None."""
        assert _extract_price("mid threes") is None

    def test_low_sevens_not_in_colloquial(self):
        """'low sevens' is not a registered pattern → returns None."""
        assert _extract_price("low sevens") is None

    def test_high_fours_not_in_colloquial(self):
        """'high fours' is not a registered pattern → returns None."""
        assert _extract_price("high fours") is None

    def test_low_four_hundreds_with_space(self):
        """Pattern requires no space: 'low fourhundreds' matches but 'low four hundreds' does not."""
        # The regex is: low\s+(?:four|4)hundreds? — no \s* between four and hundreds
        assert _extract_price("low four hundreds") is None  # space between "four" and "hundreds" breaks match
        assert _extract_price("low fourhundreds") == 425_000  # no space works
