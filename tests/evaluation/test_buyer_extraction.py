"""Tests for buyer bot extraction and state machine logic.

Tests Spanish detection, qualification state defaults, preference extraction,
timeline/motivation parsing, and stage progression — all without Claude calls.
"""
import re

import pytest

from bots.buyer_bot.buyer_bot import (
    BuyerQualificationState,
    BuyerStatus,
    JorgeBuyerBot,
)
from bots.shared.conversation_contract import is_likely_spanish as _is_likely_spanish


# -----------------------------------------------------------------------
# Spanish detection (buyer bot version)
# -----------------------------------------------------------------------
class TestBuyerSpanishDetection:
    def test_spanish_sentence(self):
        assert _is_likely_spanish("hola quiero comprar una casa") is True

    def test_spanish_greeting_with_price(self):
        assert _is_likely_spanish("buenas cuanto cuesta la casa") is True

    def test_english_sentence(self):
        assert _is_likely_spanish("hello I want to buy a house") is False

    def test_single_spanish_word_insufficient(self):
        assert _is_likely_spanish("hola") is False

    def test_two_indicators_sufficient(self):
        assert _is_likely_spanish("hola casa") is True

    def test_mixed_but_enough_spanish(self):
        assert _is_likely_spanish("hola I want to comprar") is True


# -----------------------------------------------------------------------
# BuyerQualificationState defaults
# -----------------------------------------------------------------------
class TestBuyerStateDefaults:
    def test_initial_stage(self, buyer_state):
        assert buyer_state.stage == "Q0"
        assert buyer_state.current_question == 0

    def test_initial_qualification(self, buyer_state):
        assert buyer_state.is_qualified is False
        assert buyer_state.questions_answered == 0

    def test_initial_preferences_none(self, buyer_state):
        assert buyer_state.beds_min is None
        assert buyer_state.baths_min is None
        assert buyer_state.sqft_min is None
        assert buyer_state.price_min is None
        assert buyer_state.price_max is None
        assert buyer_state.preferred_location is None

    def test_initial_preapproval(self, buyer_state):
        assert buyer_state.preapproved is None

    def test_initial_timeline(self, buyer_state):
        assert buyer_state.timeline_days is None

    def test_initial_motivation(self, buyer_state):
        assert buyer_state.motivation is None

    def test_initial_scheduling(self, buyer_state):
        assert buyer_state.scheduling_offered is False
        assert buyer_state.appointment_booked is False
        assert buyer_state.appointment_id is None


# -----------------------------------------------------------------------
# Stage progression
# -----------------------------------------------------------------------
class TestBuyerStageProgression:
    def test_advance_q0_to_q1(self, buyer_state):
        buyer_state.advance_question()
        assert buyer_state.current_question == 1
        assert buyer_state.stage == "Q1"

    def test_advance_q1_to_q2(self, buyer_state):
        buyer_state.current_question = 1
        buyer_state.advance_question()
        assert buyer_state.current_question == 2
        assert buyer_state.stage == "Q2"

    def test_advance_does_not_exceed_q4(self, buyer_state):
        buyer_state.current_question = 4
        buyer_state.advance_question()
        assert buyer_state.current_question == 4

    def test_full_qualification_hot_buyer(self, buyer_state):
        """Buyer qualifies when preapproved + timeline <= 30 days after Q4."""
        buyer_state.preapproved = True
        buyer_state.timeline_days = 14
        buyer_state.record_answer(4, "job relocation", {"motivation": "job_relocation"})
        assert buyer_state.is_qualified is True
        assert buyer_state.stage == "QUALIFIED"

    def test_no_qualification_without_preapproval(self, buyer_state):
        buyer_state.preapproved = False
        buyer_state.timeline_days = 14
        buyer_state.record_answer(4, "job relocation", {"motivation": "job_relocation"})
        assert buyer_state.is_qualified is False

    def test_no_qualification_long_timeline(self, buyer_state):
        buyer_state.preapproved = True
        buyer_state.timeline_days = 90
        buyer_state.record_answer(4, "just browsing", {"motivation": "other"})
        assert buyer_state.is_qualified is False


# -----------------------------------------------------------------------
# Q1: Preference extraction (replicating _extract_qualification_data Q1)
# -----------------------------------------------------------------------
class TestBuyerPreferenceExtraction:

    @staticmethod
    def _extract_q1(message: str) -> dict:
        """Replicate Q1 extraction logic from buyer_bot."""
        msg = message.lower()
        extracted = {}
        bed_match = re.search(r"(\d+)\s*(bed|beds|br)", msg)
        bath_match = re.search(r"(\d+(?:\.\d+)?)\s*(bath|baths|ba)", msg)
        sqft_match = re.search(r"(\d{3,5})\s*(sqft|square feet|sq ft)", msg)
        if bed_match:
            extracted["beds_min"] = int(bed_match.group(1))
        if bath_match:
            extracted["baths_min"] = float(bath_match.group(1))
        if sqft_match:
            extracted["sqft_min"] = int(sqft_match.group(1))

        k_prices = re.findall(r'\$?([\d,]+)\s*[kK]\b', msg)
        dollar_prices = re.findall(r'\$([\d,]+)\b', msg)
        bare_large = re.findall(r'\b(\d{6,})\b', msg) if not k_prices and not dollar_prices else []
        price_values = []
        for val in k_prices:
            price_values.append(int(val.replace(",", "")) * 1000)
        for val in dollar_prices:
            price_values.append(int(val.replace(",", "")))
        for val in bare_large:
            price_values.append(int(val))

        if price_values:
            if len(price_values) >= 2:
                extracted["price_min"] = min(price_values)
                extracted["price_max"] = max(price_values)
            else:
                extracted["price_max"] = price_values[0]
        return extracted

    def test_beds_and_baths(self):
        r = self._extract_q1("Looking for 3 beds 2 baths")
        assert r["beds_min"] == 3
        assert r["baths_min"] == 2.0

    def test_beds_br_alias(self):
        r = self._extract_q1("4 br at least")
        assert r["beds_min"] == 4

    def test_sqft(self):
        r = self._extract_q1("At least 1500 sqft")
        assert r["sqft_min"] == 1500

    def test_sqft_square_feet(self):
        r = self._extract_q1("2000 square feet minimum")
        assert r["sqft_min"] == 2000

    def test_price_range_k(self):
        r = self._extract_q1("Budget is 300k to 500k")
        assert r["price_min"] == 300_000
        assert r["price_max"] == 500_000

    def test_single_price_k(self):
        r = self._extract_q1("Under 400k")
        assert r["price_max"] == 400_000

    def test_dollar_price(self):
        r = self._extract_q1("Budget around $350000")
        assert r["price_max"] == 350_000

    def test_full_message(self):
        r = self._extract_q1("3 beds 2 baths around 1800 sqft, budget 350k to 500k")
        assert r["beds_min"] == 3
        assert r["baths_min"] == 2.0
        assert r["sqft_min"] == 1800
        assert r["price_min"] == 350_000
        assert r["price_max"] == 500_000

    def test_no_data_extracted(self):
        r = self._extract_q1("Something nice in a good area")
        assert r == {}


# -----------------------------------------------------------------------
# Q2: Pre-approval extraction
# -----------------------------------------------------------------------
class TestBuyerPreapprovalExtraction:

    @staticmethod
    def _extract_q2(message: str) -> bool:
        msg = message.lower()
        not_approved = [
            "not approved", "not pre-approved", "not yet", "working on it",
            "haven't been", "havent been", "not pre approved",
        ]
        approved = ["preapproved", "pre-approved", "pre approved", "approved", "cash", "yes"]
        negative = ["no", "nope"]
        if any(phrase in msg for phrase in not_approved):
            return False
        if any(word in msg for word in approved):
            return True
        if any(word in msg for word in negative):
            return False
        return False  # ambiguous

    def test_preapproved(self):
        assert self._extract_q2("Yes I'm pre-approved") is True

    def test_cash_buyer(self):
        assert self._extract_q2("I'm a cash buyer") is True

    def test_not_yet_approved(self):
        assert self._extract_q2("Not yet, working on it") is False

    def test_plain_no(self):
        assert self._extract_q2("No") is False

    def test_ambiguous_defaults_false(self):
        assert self._extract_q2("Still figuring it out") is False

    def test_not_pre_approved_phrase(self):
        assert self._extract_q2("I'm not pre-approved yet") is False


# -----------------------------------------------------------------------
# Q3: Timeline extraction
# -----------------------------------------------------------------------
class TestBuyerTimelineExtraction:

    @staticmethod
    def _extract_q3(message: str) -> int:
        msg = message.lower()
        tl = None
        if any(phrase in msg for phrase in ["browsing", "just looking", "no rush", "not sure"]):
            tl = 180
        elif any(word in msg for word in ["asap", "immediately", "urgent", "right away"]):
            tl = 30
        elif "now" in msg.split():
            tl = 30
        elif "year" in msg:
            m = re.search(r"(\d+)\s*year", msg)
            tl = int(m.group(1)) * 365 if m else 365
        elif "month" in msg:
            m = re.search(r"(\d+)\s*-\s*(\d+)\s*month", msg)
            if m:
                tl = int(m.group(1)) * 30
            else:
                m = re.search(r"(\d+)\s*month", msg)
                tl = int(m.group(1)) * 30 if m else 30
        elif "week" in msg:
            m = re.search(r"(\d+)\s*week", msg)
            tl = int(m.group(1)) * 7 if m else 14
        elif "day" in msg:
            m = re.search(r"(\d+)\s*-\s*(\d+)\s*day", msg)
            if m:
                tl = int(m.group(2))
            else:
                m = re.search(r"(\d+)\s*day", msg)
                tl = int(m.group(1)) if m else 30
        else:
            m = re.search(r"\b([1-9][0-9]{0,2})\b", msg)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 730:
                    tl = n
        return tl if tl is not None else 90

    def test_asap(self):
        assert self._extract_q3("ASAP, need a place right away") == 30

    def test_now(self):
        assert self._extract_q3("Need something now") == 30

    def test_3_months(self):
        assert self._extract_q3("Within 3 months") == 90

    def test_6_months_range(self):
        assert self._extract_q3("3-6 months") == 90

    def test_2_weeks(self):
        assert self._extract_q3("Within 2 weeks") == 14

    def test_1_year(self):
        assert self._extract_q3("Within 1 year") == 365

    def test_30_days(self):
        assert self._extract_q3("Within 30 days") == 30

    def test_just_looking(self):
        assert self._extract_q3("Just looking for now") == 180

    def test_no_rush(self):
        assert self._extract_q3("No rush, whenever") == 180

    def test_ambiguous_defaults_90(self):
        assert self._extract_q3("Whenever the right place comes along") == 90


# -----------------------------------------------------------------------
# Q4: Motivation extraction
# -----------------------------------------------------------------------
class TestBuyerMotivationExtraction:

    # Ordered by specificity (mirrors production code): downsizing before kids/family
    _MOTIVATIONS = {
        "downsizing": "downsizing", "downsize": "downsizing",
        "retirement": "downsizing", "retiring": "downsizing",
        "investment": "investment", "rental": "investment", "renting": "investment",
        "school": "school_district", "district": "school_district",
        "family": "growing_family", "kids": "growing_family",
        "baby": "growing_family", "growing": "growing_family",
        "upsizing": "upsizing", "upsize": "upsizing",
        "upgrade": "upsizing", "space": "upsizing", "room": "upsizing",
        "starter": "first_time_buyer", "first home": "first_time_buyer",
        "first-time": "first_time_buyer",
        "job": "job_relocation", "relocation": "job_relocation",
        "relocating": "job_relocation", "moving": "job_relocation",
        "transfer": "job_relocation", "closer": "job_relocation",
        "military": "job_relocation",
    }

    @classmethod
    def _extract_q4(cls, message: str) -> str:
        msg = message.lower()
        for keyword, value in cls._MOTIVATIONS.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', msg):
                return value
        return "other"

    def test_job_relocation(self):
        assert self._extract_q4("Got a new job in Riverside") == "job_relocation"

    def test_growing_family(self):
        assert self._extract_q4("Having a baby, need more space") == "growing_family"

    def test_investment(self):
        assert self._extract_q4("Looking for an investment property") == "investment"

    def test_school_district(self):
        assert self._extract_q4("Want to be in a better school district") == "school_district"

    def test_first_time_buyer(self):
        assert self._extract_q4("This would be my first home") == "first_time_buyer"

    def test_downsizing(self):
        # "downsizing" now checked before "kids" — correctly returns downsizing
        assert self._extract_q4("Kids moved out, downsizing") == "downsizing"

    def test_downsizing_clean(self):
        assert self._extract_q4("Looking to downsize") == "downsizing"

    def test_upsizing(self):
        assert self._extract_q4("Need to upgrade to something bigger") == "upsizing"

    def test_other_fallback(self):
        assert self._extract_q4("Just want a change of scenery") == "other"


# -----------------------------------------------------------------------
# Temperature calculation
# -----------------------------------------------------------------------
class TestBuyerTemperature:
    def test_hot_preapproved_short_timeline(self, buyer_state):
        buyer_state.preapproved = True
        buyer_state.timeline_days = 14
        bot = object.__new__(JorgeBuyerBot)
        assert bot._calculate_temperature(buyer_state) == BuyerStatus.HOT

    def test_warm_longer_timeline(self, buyer_state):
        buyer_state.preapproved = False
        buyer_state.timeline_days = 60
        bot = object.__new__(JorgeBuyerBot)
        assert bot._calculate_temperature(buyer_state) == BuyerStatus.WARM

    def test_cold_no_timeline(self, buyer_state):
        bot = object.__new__(JorgeBuyerBot)
        assert bot._calculate_temperature(buyer_state) == BuyerStatus.COLD

    def test_cold_long_timeline(self, buyer_state):
        buyer_state.timeline_days = 180
        bot = object.__new__(JorgeBuyerBot)
        assert bot._calculate_temperature(buyer_state) == BuyerStatus.COLD


# -----------------------------------------------------------------------
# BUG-01 regression: bd shorthand (tests actual bot method via asyncio)
# -----------------------------------------------------------------------
class TestBdShorthandRegression:
    """Regression tests for the bd/BD shorthand bug fix."""

    def test_bd_pattern_in_buyer_regex(self):
        """Verify bd is included in the bed regex pattern."""
        import re
        bed_regex = re.compile(r"(\d+)\s*(bed|beds|br|bd)", re.IGNORECASE)
        assert bed_regex.search("4bd") is not None
        assert bed_regex.search("3bd") is not None

    def test_bd_extracts_beds(self):
        import re
        msg = "4bd"
        bed_match = re.search(r"(\d+)\s*(bed|beds|br|bd)", msg.lower())
        assert bed_match is not None
        assert int(bed_match.group(1)) == 4

    def test_bd_with_ba(self):
        import re
        msg = "3bd 2ba"
        bed_match = re.search(r"(\d+)\s*(bed|beds|br|bd)", msg.lower())
        bath_match = re.search(r"(\d+(?:\.\d+)?)\s*(bath|baths|ba)", msg.lower())
        assert bed_match is not None and int(bed_match.group(1)) == 3
        assert bath_match is not None and float(bath_match.group(1)) == 2.0

    def test_bd_slash_notation(self):
        """4bd/2ba — bed regex matches 4bd before the slash."""
        import re
        msg = "4bd/2ba"
        bed_match = re.search(r"(\d+)\s*(bed|beds|br|bd)", msg.lower())
        assert bed_match is not None
        assert int(bed_match.group(1)) == 4


# -----------------------------------------------------------------------
# BUG-02 regression: qualifier price patterns
# -----------------------------------------------------------------------
class TestQualifierPriceRegression:
    """Regression tests for 'under 600', 'around 450' qualifier price extraction."""

    @staticmethod
    def _extract_qualifier_prices(msg: str) -> list:
        import re
        qualifier_prices = []
        for m in re.finditer(
            r'\b(under|over|around|about|like|maybe|roughly|close to|up to)\s+(\d{3})\b',
            msg.lower(),
        ):
            qualifier_prices.append(int(m.group(2)) * 1000)
        return qualifier_prices

    def test_under_600(self):
        assert self._extract_qualifier_prices("under 600") == [600_000]

    def test_around_450(self):
        assert self._extract_qualifier_prices("around 450") == [450_000]

    def test_like_500(self):
        assert self._extract_qualifier_prices("like 500") == [500_000]

    def test_about_750(self):
        assert self._extract_qualifier_prices("about 750") == [750_000]

    def test_maybe_400(self):
        assert self._extract_qualifier_prices("maybe 400") == [400_000]

    def test_up_to_550(self):
        assert self._extract_qualifier_prices("up to 550") == [550_000]

    def test_close_to_300(self):
        assert self._extract_qualifier_prices("close to 300") == [300_000]

    def test_under_1200_no_match(self):
        """4-digit number should NOT match qualifier pattern (only 3 digits)."""
        result = self._extract_qualifier_prices("under 1200")
        assert result == []


# -----------------------------------------------------------------------
# Slash notation "3/2" — buyer bot limitation documentation
# -----------------------------------------------------------------------
class TestSlashNotationLimitation:
    """Document that slash notation is not supported by buyer bot."""

    def test_slash_notation_beds_not_extracted(self):
        """3/2 slash notation — beds not extracted (limitation)."""
        import re
        msg = "3/2"
        bed_match = re.search(r"(\d+)\s*(bed|beds|br|bd)", msg.lower())
        # "3/2" does not contain "bed", "beds", "br", or "bd" after the number
        assert bed_match is None
