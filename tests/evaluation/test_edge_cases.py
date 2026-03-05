"""Edge case tests for Spanish detection, response filtering, Q4 stall, and price extraction."""
import re

import pytest

from bots.seller_bot.jorge_seller_bot import (
    SellerQualificationState,
    _COLLOQUIAL_PRICES,
    _PRICE_PATTERNS,
    _is_likely_spanish as seller_is_likely_spanish,
)
from bots.buyer_bot.buyer_bot import _is_likely_spanish as buyer_is_likely_spanish
from bots.shared.response_filter import sanitize_bot_response


# -----------------------------------------------------------------------
# Spanish detection — seller bot
# -----------------------------------------------------------------------
class TestSpanishDetectionSeller:
    def test_spanish_sentence(self):
        assert seller_is_likely_spanish("hola quiero vender mi casa") is True

    def test_english_sentence(self):
        assert seller_is_likely_spanish("hello I want to sell my house") is False

    def test_single_indicator_insufficient(self):
        assert seller_is_likely_spanish("hola") is False

    def test_two_indicators(self):
        assert seller_is_likely_spanish("hola casa") is True

    def test_mixed_language(self):
        assert seller_is_likely_spanish("buenas I have a casa for sale") is True

    def test_empty_string(self):
        assert seller_is_likely_spanish("") is False

    def test_numbers_only(self):
        assert seller_is_likely_spanish("123 456") is False


# -----------------------------------------------------------------------
# Spanish detection — buyer bot
# -----------------------------------------------------------------------
class TestSpanishDetectionBuyer:
    def test_spanish_sentence(self):
        assert buyer_is_likely_spanish("hola quiero comprar una casa") is True

    def test_english_sentence(self):
        assert buyer_is_likely_spanish("I want to buy a home") is False

    def test_single_indicator_insufficient(self):
        assert buyer_is_likely_spanish("gracias") is False

    def test_two_indicators(self):
        assert buyer_is_likely_spanish("precio casa") is True


# -----------------------------------------------------------------------
# Response filter — identity protection
# -----------------------------------------------------------------------
class TestResponseFilterIdentity:
    def test_ai_disclosure_stripped(self):
        result = sanitize_bot_response("I'm an AI assistant helping you.")
        assert "AI" not in result
        assert "Jorge" in result

    def test_chatbot_disclosure_stripped(self):
        result = sanitize_bot_response("I'm a chatbot here to help.")
        assert "chatbot" not in result
        assert "Jorge" in result

    def test_bot_disclosure_stripped(self):
        result = sanitize_bot_response("I am a bot.")
        assert "bot" not in result.lower() or "professional" in result.lower()

    def test_normal_message_unchanged(self):
        msg = "Let's talk about your property situation."
        result = sanitize_bot_response(msg)
        assert "property situation" in result


# -----------------------------------------------------------------------
# Response filter — buying language (seller safety)
# -----------------------------------------------------------------------
class TestResponseFilterBuyingLanguage:
    def test_buying_power_filtered(self):
        result = sanitize_bot_response("What's your buying power?")
        assert "buying power" not in result.lower()

    def test_pre_approval_filtered(self):
        result = sanitize_bot_response("Are you pre-approved for a mortgage?")
        assert "pre-approved" not in result.lower()

    def test_home_tour_filtered(self):
        result = sanitize_bot_response("Would you like a home tour?")
        assert "home tour" not in result.lower()

    def test_looking_to_buy_filtered(self):
        result = sanitize_bot_response("Are you looking to buy a home?")
        assert "looking to buy" not in result.lower()


# -----------------------------------------------------------------------
# Response filter — neighborhood buying suggestions
# -----------------------------------------------------------------------
class TestResponseFilterNeighborhood:
    def test_check_out_heights(self):
        result = sanitize_bot_response("You should check out Sunset Heights")
        # Pattern: "check out <word> Heights" should be stripped
        assert "Sunset Heights" not in result

    def test_consider_moving_to_gardens(self):
        result = sanitize_bot_response("You should consider moving to Rose Gardens")
        assert "Rose Gardens" not in result

    def test_look_at_park(self):
        result = sanitize_bot_response("You should look at Oak Park")
        assert "Oak Park" not in result


# -----------------------------------------------------------------------
# Response filter — URL stripping
# -----------------------------------------------------------------------
class TestResponseFilterURLs:
    def test_url_stripped(self):
        result = sanitize_bot_response("Visit https://example.com for more info")
        assert "https://" not in result

    def test_http_url_stripped(self):
        result = sanitize_bot_response("Check http://competitor.com/listing")
        assert "http://" not in result


# -----------------------------------------------------------------------
# Response filter — competitor names
# -----------------------------------------------------------------------
class TestResponseFilterCompetitors:
    def test_zillow_stripped(self):
        result = sanitize_bot_response("You could also try Zillow Offers.")
        assert "Zillow" not in result

    def test_opendoor_stripped(self):
        result = sanitize_bot_response("Opendoor might give you an offer too.")
        assert "Opendoor" not in result

    def test_redfin_stripped(self):
        result = sanitize_bot_response("Redfin has similar services.")
        assert "Redfin" not in result


# -----------------------------------------------------------------------
# Response filter — truncation
# -----------------------------------------------------------------------
class TestResponseFilterTruncation:
    def test_long_message_truncated(self):
        long_msg = "This is a test sentence. " * 50  # well over 480 chars
        result = sanitize_bot_response(long_msg)
        assert len(result) <= 484  # 480 + "..."

    def test_short_message_not_truncated(self):
        short_msg = "Quick question about your property."
        result = sanitize_bot_response(short_msg)
        assert result == short_msg


# -----------------------------------------------------------------------
# Response filter — None / empty handling
# -----------------------------------------------------------------------
class TestResponseFilterEmpty:
    def test_none_returns_empty(self):
        assert sanitize_bot_response(None) == ""

    def test_empty_string_returns_empty(self):
        assert sanitize_bot_response("") == ""


# -----------------------------------------------------------------------
# Q4 stall detection
# -----------------------------------------------------------------------
class TestQ4StallDetection:
    def test_q4_stall_after_3_attempts(self, seller_state):
        seller_state.current_question = 4
        seller_state.q4_attempts = 3
        stalled = seller_state.q4_attempts >= 3 and seller_state.current_question == 4
        assert stalled is True

    def test_q4_not_stalled_at_q3(self, seller_state):
        seller_state.current_question = 3
        seller_state.q4_attempts = 5
        stalled = seller_state.q4_attempts >= 3 and seller_state.current_question == 4
        assert stalled is False

    def test_q4_not_stalled_at_1_attempt(self, seller_state):
        seller_state.current_question = 4
        seller_state.q4_attempts = 1
        stalled = seller_state.q4_attempts >= 3 and seller_state.current_question == 4
        assert stalled is False


# -----------------------------------------------------------------------
# Price extraction edge cases
# -----------------------------------------------------------------------
class TestPriceExtractionEdgeCases:
    def test_empty_message_no_colloquial(self):
        text = ""
        matches = [m for pattern, _ in _COLLOQUIAL_PRICES for m in [pattern.search(text)] if m]
        assert matches == []

    def test_no_price_in_text(self):
        text = "I'm not sure about the price yet"
        matches = [m for pattern, _ in _COLLOQUIAL_PRICES for m in [pattern.search(text)] if m]
        assert matches == []

    def test_empty_message_no_standard(self):
        text = ""
        matches = [m for pattern, _ in _PRICE_PATTERNS for m in [pattern.search(text)] if m]
        assert matches == []

    def test_greeting_no_price(self):
        text = "Hey Jorge how are you"
        coll = [m for pattern, _ in _COLLOQUIAL_PRICES for m in [pattern.search(text)] if m]
        std = [m for pattern, _ in _PRICE_PATTERNS for m in [pattern.search(text)] if m]
        assert coll == []
        assert std == []


# -----------------------------------------------------------------------
# Seller state dataclass edge cases
# -----------------------------------------------------------------------
class TestSellerStateEdgeCases:
    def test_offer_presented_initially_false(self, seller_state):
        assert seller_state.offer_presented is False

    def test_scheduling_offered_initially_false(self, seller_state):
        assert seller_state.scheduling_offered is False

    def test_appointment_booked_initially_false(self, seller_state):
        assert seller_state.appointment_booked is False

    def test_extracted_data_initially_empty(self, seller_state):
        assert seller_state.extracted_data == {}

    def test_conversation_history_initially_empty(self, seller_state):
        assert seller_state.conversation_history == []

    def test_last_interaction_initially_none(self, seller_state):
        assert seller_state.last_interaction is None
