"""Buyer bot regression tests.

Covers extraction regressions (BUG-01 bed shorthands, BUG-02 qualifier prices,
BUG-03 partial-data advance), price/bed/bath edge cases, temperature boundaries,
and multi-turn state progression.
"""

import pytest

from bots.buyer_bot.buyer_bot import (
    BuyerQualificationState,
    BuyerStatus,
    JorgeBuyerBot,
)


# ---------------------------------------------------------------------------
# Group 1: BUG-01 — Bed Shorthand Regression
# ---------------------------------------------------------------------------
class TestBug01BedShorthand:
    """Verify 'bd' suffix is recognised as bed count (BUG-01 fix)."""

    @pytest.mark.asyncio
    async def test_4bd(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("4bd", 1)
        assert extracted.get("beds_min") == 4

    @pytest.mark.asyncio
    async def test_3bd_2ba(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("3bd 2ba", 1)
        assert extracted.get("beds_min") == 3
        assert extracted.get("baths_min") == 2.0

    @pytest.mark.asyncio
    async def test_uppercase_4BD(self):
        """Message is lowercased before regex — uppercase should still match."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("4BD", 1)
        assert extracted.get("beds_min") == 4

    @pytest.mark.asyncio
    async def test_4_bd_with_space(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("4 bd", 1)
        assert extracted.get("beds_min") == 4

    @pytest.mark.asyncio
    async def test_4bd_slash_2ba(self):
        """Slash separator — bed regex still finds '4bd' prefix."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("4bd/2ba", 1)
        assert extracted.get("beds_min") == 4


# ---------------------------------------------------------------------------
# Group 2: BUG-02 — Qualifier Price Regression
# ---------------------------------------------------------------------------
class TestBug02QualifierPrices:
    """Qualifier words ('under', 'around', etc.) + 3-digit number → price * 1000."""

    @pytest.mark.asyncio
    async def test_under_600(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("under 600", 1)
        assert extracted.get("price_max") == 600_000

    @pytest.mark.asyncio
    async def test_around_450(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("around 450", 1)
        assert extracted.get("price_max") == 450_000

    @pytest.mark.asyncio
    async def test_like_500(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("like 500", 1)
        assert extracted.get("price_max") == 500_000

    @pytest.mark.asyncio
    async def test_about_750(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("about 750", 1)
        assert extracted.get("price_max") == 750_000

    @pytest.mark.asyncio
    async def test_maybe_400(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("maybe 400", 1)
        assert extracted.get("price_max") == 400_000

    @pytest.mark.asyncio
    async def test_up_to_550(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("up to 550", 1)
        assert extracted.get("price_max") == 550_000

    @pytest.mark.asyncio
    async def test_close_to_300(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("close to 300", 1)
        assert extracted.get("price_max") == 300_000

    @pytest.mark.asyncio
    async def test_under_1200_no_match(self):
        """4-digit number does not match qualifier pattern (requires exactly 3 digits)."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("under 1200", 1)
        assert extracted.get("price_max") is None


# ---------------------------------------------------------------------------
# Group 3: BUG-03 — Q1 Advance with Partial Data
# ---------------------------------------------------------------------------
class TestBug03PartialDataAdvance:
    """Q1 should advance if ANY of beds/baths/sqft/price is present."""

    def test_baths_only_advances(self):
        bot = JorgeBuyerBot()
        assert bot._should_advance_question({"baths_min": 2.0}, 1) is True

    def test_beds_only_advances(self):
        bot = JorgeBuyerBot()
        assert bot._should_advance_question({"beds_min": 3}, 1) is True

    def test_price_max_only_advances(self):
        bot = JorgeBuyerBot()
        assert bot._should_advance_question({"price_max": 500_000}, 1) is True

    def test_sqft_only_advances(self):
        bot = JorgeBuyerBot()
        assert bot._should_advance_question({"sqft_min": 1500}, 1) is True

    def test_empty_does_not_advance(self):
        bot = JorgeBuyerBot()
        assert bot._should_advance_question({}, 1) is False


# ---------------------------------------------------------------------------
# Group 4: Price Format Edge Cases
# ---------------------------------------------------------------------------
class TestPriceFormats:
    """Edge cases for k-suffix, dollar-prefix, bare-large, and range pricing."""

    @pytest.mark.asyncio
    async def test_dollar_450k(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("$450k", 1)
        assert extracted.get("price_max") == 450_000

    @pytest.mark.asyncio
    async def test_dollar_450_comma_000(self):
        """Dollar-prefixed with commas: $450,000."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("$450,000", 1)
        assert extracted.get("price_max") == 450_000

    @pytest.mark.asyncio
    async def test_range_450k_550k(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("450k-550k", 1)
        assert extracted.get("price_min") == 450_000
        assert extracted.get("price_max") == 550_000

    @pytest.mark.asyncio
    async def test_around_dollar_500k(self):
        """Qualifier + $k — k_prices takes precedence."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("around $500k", 1)
        assert extracted.get("price_max") == 500_000

    @pytest.mark.asyncio
    async def test_dollar_1_2m_limitation(self):
        """Buyer bot lacks million-suffix support; '$1.2m' captures only '$1'."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("$1.2m", 1)
        # dollar_prices matches "$1" (the '.' breaks digit group) → price_max=1
        assert extracted.get("price_max") == 1

    @pytest.mark.asyncio
    async def test_mid_400s_limitation(self):
        """Colloquial 'mid 400s' has no matching pattern in buyer bot."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("mid 400s", 1)
        assert extracted.get("price_max") is None

    @pytest.mark.asyncio
    async def test_bare_6digit(self):
        """Bare 6+ digit number matched when no k/dollar prices present."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("450000", 1)
        assert extracted.get("price_max") == 450_000

    @pytest.mark.asyncio
    async def test_500_600k_partial_range(self):
        """'500-600k' — only '600k' has k suffix; 500 is not captured."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("500-600k", 1)
        assert extracted.get("price_max") == 600_000
        # 500 has no k suffix and no $ prefix → not captured as a second price
        assert extracted.get("price_min") is None

    @pytest.mark.asyncio
    async def test_dollar_1_200_000(self):
        """Dollar-prefixed with commas for million-range."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("$1,200,000", 1)
        assert extracted.get("price_max") == 1_200_000


# ---------------------------------------------------------------------------
# Group 5: Bed/Bath Format Edge Cases
# ---------------------------------------------------------------------------
class TestBedBathFormats:
    """Various bed/bath input formats."""

    @pytest.mark.asyncio
    async def test_3_bed_2_bath(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("3 bed 2 bath", 1)
        assert extracted.get("beds_min") == 3
        assert extracted.get("baths_min") == 2.0

    @pytest.mark.asyncio
    async def test_3_beds_2_baths(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("3 beds 2 baths", 1)
        assert extracted.get("beds_min") == 3
        assert extracted.get("baths_min") == 2.0

    @pytest.mark.asyncio
    async def test_3br_2ba(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("3br 2ba", 1)
        assert extracted.get("beds_min") == 3
        assert extracted.get("baths_min") == 2.0

    @pytest.mark.asyncio
    async def test_bedroom_substring_match(self):
        """'bedroom' starts with 'bed' — regex matches without trailing \\b."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("3 bedroom 2 bathroom", 1)
        assert extracted.get("beds_min") == 3

    @pytest.mark.asyncio
    async def test_slash_notation_limitation(self):
        """'3/2' is not handled by buyer bed regex (no 'bed'/'br'/'bd' suffix)."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("3/2", 1)
        assert extracted.get("beds_min") is None

    @pytest.mark.asyncio
    async def test_word_number_limitation(self):
        """Word numbers like 'three' are not handled."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("three bed", 1)
        assert extracted.get("beds_min") is None

    @pytest.mark.asyncio
    async def test_4_bed_plus_suffix(self):
        """'4 bed+' — regex matches '4 bed' before the '+'."""
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("4 bed+", 1)
        assert extracted.get("beds_min") == 4

    @pytest.mark.asyncio
    async def test_1_5_bath(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("1.5 bath", 1)
        assert extracted.get("baths_min") == 1.5


# ---------------------------------------------------------------------------
# Group 6: Multi-Turn State Progression
# ---------------------------------------------------------------------------
class TestMultiTurnProgression:
    """Verify extraction across question numbers and state accumulation."""

    @pytest.mark.asyncio
    async def test_full_q1_q4_flow(self):
        bot = JorgeBuyerBot()
        q1 = await bot._extract_qualification_data("3 bed 2 bath under 500", 1)
        assert q1.get("beds_min") == 3
        assert q1.get("baths_min") == 2.0
        assert q1.get("price_max") == 500_000

        q2 = await bot._extract_qualification_data("yes pre-approved", 2)
        assert q2.get("preapproved") is True

        q3 = await bot._extract_qualification_data("within 2 months", 3)
        assert q3.get("timeline_days") == 60

        q4 = await bot._extract_qualification_data("growing family", 4)
        assert q4.get("motivation") == "growing_family"

    @pytest.mark.asyncio
    async def test_partial_q1_baths_only_advances(self):
        bot = JorgeBuyerBot()
        extracted = await bot._extract_qualification_data("2ba", 1)
        assert extracted.get("baths_min") == 2.0
        assert bot._should_advance_question(extracted, 1) is True

    @pytest.mark.asyncio
    async def test_gibberish_then_valid(self):
        """Gibberish input at Q1 should not advance; valid input should."""
        bot = JorgeBuyerBot()
        bad = await bot._extract_qualification_data("asdfghjkl", 1)
        assert bot._should_advance_question(bad, 1) is False

        good = await bot._extract_qualification_data("3 bed 2 bath", 1)
        assert bot._should_advance_question(good, 1) is True

    @pytest.mark.asyncio
    async def test_state_questions_answered_increment(self):
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        assert state.questions_answered == 0
        state.record_answer(1, "3 bed", {"beds_min": 3})
        assert state.questions_answered == 1
        state.record_answer(2, "yes", {"preapproved": True})
        assert state.questions_answered == 2

    @pytest.mark.asyncio
    async def test_temperature_changes_with_data(self):
        """Temperature shifts as preapproved and timeline are set."""
        bot = JorgeBuyerBot()
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")

        # No data → COLD
        assert bot._calculate_temperature(state) == BuyerStatus.COLD

        # timeline_days=60, no preapproval → WARM
        state.timeline_days = 60
        assert bot._calculate_temperature(state) == BuyerStatus.WARM

        # Add preapproval, still 60 days → WARM
        state.preapproved = True
        assert bot._calculate_temperature(state) == BuyerStatus.WARM

        # Shorten timeline to 20 days → HOT
        state.timeline_days = 20
        assert bot._calculate_temperature(state) == BuyerStatus.HOT


# ---------------------------------------------------------------------------
# Group 7: Temperature Boundary Conditions
# ---------------------------------------------------------------------------
class TestTemperatureBoundary:
    """Exact boundary tests for HOT/WARM/COLD temperature classification."""

    def test_preapproved_30_days_is_hot(self):
        bot = JorgeBuyerBot()
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.preapproved = True
        state.timeline_days = 30
        assert bot._calculate_temperature(state) == BuyerStatus.HOT

    def test_preapproved_31_days_is_warm(self):
        bot = JorgeBuyerBot()
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.preapproved = True
        state.timeline_days = 31
        assert bot._calculate_temperature(state) == BuyerStatus.WARM

    def test_not_preapproved_30_days_is_warm(self):
        """Without preapproval, <= 90 days → WARM (not HOT)."""
        bot = JorgeBuyerBot()
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.preapproved = False
        state.timeline_days = 30
        assert bot._calculate_temperature(state) == BuyerStatus.WARM

    def test_not_preapproved_91_days_is_cold(self):
        bot = JorgeBuyerBot()
        state = BuyerQualificationState(contact_id="c1", location_id="loc1")
        state.preapproved = False
        state.timeline_days = 91
        assert bot._calculate_temperature(state) == BuyerStatus.COLD
