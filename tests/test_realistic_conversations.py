"""
Realistic multi-turn conversation tests for buyer and seller bots.
Tests simulate messy real-world SMS inputs using extraction-layer tests.

Calls _extract_qualification_data() directly — pure regex/logic for buyer,
mock Claude for seller Q1/Q2/Q3 fallback paths.
"""
import pytest
from unittest.mock import AsyncMock, patch

from bots.buyer_bot.buyer_bot import BuyerQualificationState, JorgeBuyerBot
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState
from bots.shared.claude_client import LLMResponse


@pytest.fixture
def buyer_bot():
    bot = JorgeBuyerBot.__new__(JorgeBuyerBot)
    bot.claude_client = AsyncMock()
    bot.ghl_client = AsyncMock()
    bot.cache = AsyncMock()
    bot.logger = AsyncMock()
    bot.calendar_service = AsyncMock()
    return bot


@pytest.fixture
def seller_bot():
    bot = JorgeSellerBot.__new__(JorgeSellerBot)
    bot.claude_client = AsyncMock()
    bot.ghl_client = AsyncMock()
    bot.cache = AsyncMock()
    bot.logger = AsyncMock()
    bot.calendar_service = AsyncMock()
    return bot


# ---------------------------------------------------------------------------
# Scenario 1: Buyer — Spanish-English Mix (5 tests)
# ---------------------------------------------------------------------------
class TestBuyerSpanishEnglishMix:
    """Scenario 1: Spanish-English buyer — messy real SMS."""

    @pytest.mark.asyncio
    async def test_turn1_greeting_location(self, buyer_bot):
        """Q1: 'hola jorge, looking for a casa in fontana' — Fontana is a service area."""
        extracted = await buyer_bot._extract_qualification_data(
            "hola jorge, looking for a casa in fontana", 1
        )
        assert extracted.get("preferred_location") == "Fontana"

    @pytest.mark.asyncio
    async def test_turn2_recamaras_under_500(self, buyer_bot):
        """Q1: '4 recamaras, 2 baños, under 500' — 'recamaras' won't match bed regex,
        but 'under 500' (3-digit qualifier) → price_max=500000."""
        extracted = await buyer_bot._extract_qualification_data(
            "4 recamaras, 2 baños, under 500", 1
        )
        # "recamaras" not in regex (bed|beds|br|bd) — beds_min absent
        assert "beds_min" not in extracted
        # "under 500" → qualifier price → 500*1000
        assert extracted.get("price_max") == 500000

    @pytest.mark.asyncio
    async def test_turn3_preapproved_spanish(self, buyer_bot):
        """Q2: 'si, estoy pre-approved' → preapproved=True."""
        extracted = await buyer_bot._extract_qualification_data(
            "si, estoy pre-approved", 2
        )
        assert extracted["preapproved"] is True

    @pytest.mark.asyncio
    async def test_turn4_timeline_months(self, buyer_bot):
        """Q3: 'like 2 months' → 2*30=60 days."""
        extracted = await buyer_bot._extract_qualification_data(
            "like 2 months", 3
        )
        assert extracted["timeline_days"] == 60

    @pytest.mark.asyncio
    async def test_turn5_motivation_space(self, buyer_bot):
        """Q4: 'need more space for my family' → 'space' maps to 'upsizing'
        (checked before 'family'→'growing_family' in ordered dict)."""
        extracted = await buyer_bot._extract_qualification_data(
            "need more space for my family", 4
        )
        # "family" → growing_family appears before "space" → upsizing in the ordered dict?
        # Actually in the code, motivations dict iteration order matters.
        # "family" key appears at position ~11, "space" at ~17. "family" matches first.
        assert extracted["motivation"] == "growing_family"


# ---------------------------------------------------------------------------
# Scenario 2: Buyer — Typos and Abbreviations (5 tests)
# ---------------------------------------------------------------------------
class TestBuyerTyposAbbreviations:
    """Scenario 2: Buyer with typos and shorthand."""

    @pytest.mark.asyncio
    async def test_greeting_no_extraction(self, buyer_bot):
        """Q1: 'hey r u jorge?' — no preference keywords."""
        extracted = await buyer_bot._extract_qualification_data(
            "hey r u jorge?", 1
        )
        # No beds, baths, price, or location matched
        assert "beds_min" not in extracted
        assert "price_max" not in extracted

    @pytest.mark.asyncio
    async def test_abbreviations_3bd_2ba_400k(self, buyer_bot):
        """Q1: '3 bd 2 ba around 400k in ontario' — beds=3, baths=2, price=400000, loc=Ontario."""
        extracted = await buyer_bot._extract_qualification_data(
            "3 bd 2 ba around 400k in ontario", 1
        )
        assert extracted["beds_min"] == 3
        assert extracted["baths_min"] == 2.0
        assert extracted["price_max"] == 400000
        assert extracted["preferred_location"] == "Ontario"

    @pytest.mark.asyncio
    async def test_preapproved_no_hyphen(self, buyer_bot):
        """Q2: 'yea im preapproved w chase' → preapproved=True."""
        extracted = await buyer_bot._extract_qualification_data(
            "yea im preapproved w chase", 2
        )
        assert extracted["preapproved"] is True

    @pytest.mark.asyncio
    async def test_asap_timeline(self, buyer_bot):
        """Q3: 'asap like 2 weeks' → 'asap' matches first → timeline_days=30."""
        extracted = await buyer_bot._extract_qualification_data(
            "asap like 2 weeks", 3
        )
        assert extracted["timeline_days"] == 30

    @pytest.mark.asyncio
    async def test_divorce_motivation(self, buyer_bot):
        """Q4: 'divorcing need my own place' — 'divorcing' not in buyer motivations,
        but code uses word-boundary regex. Check what actually matches."""
        extracted = await buyer_bot._extract_qualification_data(
            "divorcing need my own place", 4
        )
        # Buyer motivation dict doesn't have "divorcing". No keyword matches.
        # Falls through to "other".
        assert extracted["motivation"] == "other"


# ---------------------------------------------------------------------------
# Scenario 3: Seller — Extremely Vague (5 tests)
# ---------------------------------------------------------------------------
class TestSellerExtremelyVague:
    """Scenario 3: Vague seller at every stage — Claude fallback mocked."""

    @pytest.mark.asyncio
    async def test_vague_condition_claude_fallback(self, seller_bot):
        """Q1: 'got a house might wanna sell' — no condition keywords → Claude fallback."""
        seller_bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="needs_minor_repairs", model="haiku")
        )
        extracted = await seller_bot._extract_qualification_data(
            "got a house might wanna sell", 1
        )
        assert extracted["condition"] == "needs_minor_repairs"

    @pytest.mark.asyncio
    async def test_ok_condition_minor_repairs(self, seller_bot):
        """Q1: 'its ok i guess' — 'ok' matches needs_minor_repairs keywords."""
        # 'ok' is in the minor_repairs keyword list with word-boundary matching
        extracted = await seller_bot._extract_qualification_data(
            "its ok i guess", 1
        )
        assert extracted["condition"] == "needs_minor_repairs"

    @pytest.mark.asyncio
    async def test_vague_price_claude_fallback(self, seller_bot):
        """Q2: 'idk' — no price patterns → Claude Haiku fallback → 300000."""
        seller_bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="300000", model="haiku")
        )
        extracted = await seller_bot._extract_qualification_data("idk", 2)
        assert extracted["price_expectation"] == 300000

    @pytest.mark.asyncio
    async def test_vague_motivation_claude_fallback(self, seller_bot):
        """Q3: 'just curious' — no motivation keywords → Claude classify."""
        seller_bot.claude_client.agenerate = AsyncMock(
            return_value=LLMResponse(content="other", model="haiku")
        )
        extracted = await seller_bot._extract_qualification_data("just curious", 3)
        # "just curious" has no keyword match → _classify_with_claude → mock returns "other"
        assert extracted["motivation"] == "other"
        assert extracted["urgency"] == "medium"

    @pytest.mark.asyncio
    async def test_nah_im_good_offer_rejected(self, seller_bot):
        """Q4: 'nah im good' — 'no' not in message literally? Check 'nah'.
        Actually 'nah' is not in reject_words. But wait — no accept_words match either.
        Else branch: offer_accepted=False."""
        extracted = await seller_bot._extract_qualification_data("nah im good", 4)
        assert extracted["offer_accepted"] is False
        assert extracted["timeline_acceptable"] is False


# ---------------------------------------------------------------------------
# Scenario 4: Buyer — Oversharer (3 tests — same message, different Q)
# ---------------------------------------------------------------------------
class TestBuyerOversharer:
    """Scenario 4: Buyer gives all info in one long message."""

    OVERSHARER_MSG = (
        "Hey Jorge we need a 4 bed 3 bath in Rancho, "
        "pre-approved for 600k, need to move in 60 days because of job transfer"
    )

    @pytest.mark.asyncio
    async def test_oversharer_q1_extraction(self, buyer_bot):
        """Q1 extraction: beds=4, baths=3, price_max=600000.
        Location: 'Rancho' alone doesn't match 'Rancho Cucamonga' (full string match)."""
        extracted = await buyer_bot._extract_qualification_data(self.OVERSHARER_MSG, 1)
        assert extracted["beds_min"] == 4
        assert extracted["baths_min"] == 3.0
        assert extracted["price_max"] == 600000
        # "rancho" alone doesn't match SERVICE_AREAS ("Rancho Cucamonga")
        assert "preferred_location" not in extracted

    @pytest.mark.asyncio
    async def test_oversharer_q2_preapproved(self, buyer_bot):
        """Q2 extraction: 'pre-approved' → preapproved=True."""
        extracted = await buyer_bot._extract_qualification_data(self.OVERSHARER_MSG, 2)
        assert extracted["preapproved"] is True

    @pytest.mark.asyncio
    async def test_oversharer_q3_timeline(self, buyer_bot):
        """Q3 extraction: '60 days' → timeline_days=60."""
        extracted = await buyer_bot._extract_qualification_data(self.OVERSHARER_MSG, 3)
        assert extracted["timeline_days"] == 60


# ---------------------------------------------------------------------------
# Scenario 5: Seller — Unrealistic Price (1 test)
# ---------------------------------------------------------------------------
class TestSellerUnrealisticPrice:
    """Scenario 5: Seller claims 50 million — out of bounds."""

    @pytest.mark.asyncio
    async def test_50_million_out_of_bounds(self, seller_bot):
        """Q2: 'I think its worth like 50 million' → 50*1_000_000=50_000_000 > 10_000_000 → None."""
        extracted = await seller_bot._extract_qualification_data(
            "I think its worth like 50 million", 2
        )
        assert extracted["price_expectation"] is None


# ---------------------------------------------------------------------------
# Scenario 6: Buyer — Single Message Extracts Multiple Q1 Fields (1 test)
# ---------------------------------------------------------------------------
class TestSingleMessageMultipleFields:
    """Scenario 6: Single message extracts multiple Q1 fields."""

    @pytest.mark.asyncio
    async def test_multi_field_q1(self, buyer_bot):
        """'Looking for 4 beds 2 baths under 600k' → beds=4, baths=2, price=600000."""
        extracted = await buyer_bot._extract_qualification_data(
            "Looking for 4 beds 2 baths under 600k", 1
        )
        assert extracted["beds_min"] == 4
        assert extracted["baths_min"] == 2.0
        assert extracted["price_max"] == 600000


# ---------------------------------------------------------------------------
# Scenario 7: Buyer Q1 Advance Logic (1 test)
# ---------------------------------------------------------------------------
class TestQ1AdvanceLogic:
    """Scenario 7: _should_advance_question with sufficient Q1 data."""

    def test_advance_with_beds_baths_price(self, buyer_bot):
        """beds_min + baths_min + price_max → should advance from Q1."""
        result = buyer_bot._should_advance_question(
            {"beds_min": 4, "baths_min": 2, "price_max": 600000}, 1
        )
        assert result is True

    def test_no_advance_without_fields(self, buyer_bot):
        """Empty extraction → should NOT advance from Q1."""
        result = buyer_bot._should_advance_question({}, 1)
        assert result is False
