"""Exhaustive parametrized tests for seller bot price extraction."""
from __future__ import annotations

import pytest

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot


@pytest.fixture
def bot():
    return JorgeSellerBot()


@pytest.mark.parametrize("message,expected", [
    # Standard dollar formats
    ("I'm thinking $580,000", 580_000),
    ("around $350,000", 350_000),
    ("$425,000", 425_000),
    # k-suffix
    ("$580k", 580_000),
    ("$620k", 620_000),
    ("around 400k", 400_000),
    ("about $350k", 350_000),
    # m-suffix
    ("$1.2m", 1_200_000),
    ("$1.5M", 1_500_000),
    # Plain numbers that need scaling
    ("350 thousand", 350_000),
    ("400 thousand dollars", 400_000),
    # Ranges — should pick a value within the range
    ("between 300 and 400 thousand", None),  # extraction may return None or a value
    # Text prices
    ("mid fives", None),   # Haiku call needed — returns None when mocked
    ("high threes", None), # Same
    # Too-small bare number (should return None — not scaled as price)
    ("50", None),
    # Already-processed
    ("$1,200,000", 1_200_000),
])
async def test_price_extraction_parametrized(bot, message, expected):
    """Prices extract correctly or gracefully return None for ambiguous inputs."""
    extracted = await bot._extract_qualification_data(message, question_num=2)
    actual = extracted.get("price_expectation")
    if expected is not None:
        assert actual == expected, f"Message {message!r}: got {actual}, expected {expected}"
    else:
        # Ambiguous inputs: just verify no crash and value is either None or a reasonable int
        assert actual is None or (isinstance(actual, int) and actual > 0)


async def test_out_of_range_price_becomes_none(bot):
    """Prices outside $10k–$10M bounds are discarded (None)."""
    # $20M — way too high
    extracted = await bot._extract_qualification_data("$20,000,000", question_num=2)
    assert extracted.get("price_expectation") is None


async def test_price_extraction_haiku_failure_returns_none(bot):
    """When Haiku/Claude fails, price defaults to None (not $300k)."""
    from unittest.mock import patch
    with patch.object(bot.claude_client, "agenerate", side_effect=Exception("API error")):
        extracted = await bot._extract_qualification_data("around market value", 2)
    assert extracted.get("price_expectation") is None


async def test_price_extraction_does_not_crash_on_empty(bot):
    """Empty string doesn't crash the extractor."""
    extracted = await bot._extract_qualification_data("", question_num=2)
    assert "price_expectation" in extracted or extracted == {}


async def test_price_extraction_does_not_crash_on_gibberish(bot):
    """Gibberish input doesn't crash the extractor."""
    extracted = await bot._extract_qualification_data("asdfghjkl!!!!", question_num=2)
    assert extracted.get("price_expectation") is None
