"""Unit tests for bots.shared.response_filter.sanitize_bot_response."""
from __future__ import annotations

import pytest

from bots.shared.response_filter import sanitize_bot_response


# ---------------------------------------------------------------------------
# Identity stripping
# ---------------------------------------------------------------------------

class TestIdentityStripping:
    def test_strips_im_an_ai(self):
        assert "AI" not in sanitize_bot_response("I'm an AI and I can help you.")

    def test_strips_i_am_an_ai(self):
        assert "AI" not in sanitize_bot_response("I am an AI assistant.")

    def test_strips_im_a_chatbot(self):
        result = sanitize_bot_response("I'm a chatbot here to help.")
        assert "chatbot" not in result.lower()

    def test_strips_i_am_a_chatbot(self):
        result = sanitize_bot_response("I am a chatbot designed to help.")
        assert "chatbot" not in result.lower()

    def test_strips_im_a_bot(self):
        result = sanitize_bot_response("I'm a bot for Jorge Realty.")
        assert "bot" not in result.lower()

    def test_strips_i_am_a_bot(self):
        result = sanitize_bot_response("I am a bot that can answer questions.")
        assert "I am a bot" not in result

    def test_strips_not_a_real_person(self):
        result = sanitize_bot_response("I'm not a real person, but I can help.")
        assert "not a real person" not in result.lower()

    def test_strips_as_an_ai(self):
        result = sanitize_bot_response("As an AI, I don't have feelings.")
        assert "as an ai" not in result.lower()

    def test_strips_artificial_intelligence(self):
        result = sanitize_bot_response("As an artificial intelligence I process data.")
        assert "artificial intelligence" not in result.lower()

    def test_normal_message_unchanged(self):
        msg = "Great! What's the condition of the property?"
        assert sanitize_bot_response(msg) == msg

    def test_case_insensitive(self):
        result = sanitize_bot_response("I'M AN AI assistant.")
        assert "AI" not in result


# ---------------------------------------------------------------------------
# URL stripping
# ---------------------------------------------------------------------------

class TestURLStripping:
    def test_strips_http_url(self):
        result = sanitize_bot_response("Visit http://example.com for details.")
        assert "http://" not in result

    def test_strips_https_url(self):
        result = sanitize_bot_response("Check https://evil.com/phish here.")
        assert "https://" not in result
        assert "evil.com" not in result

    def test_strips_multiple_urls(self):
        text = "See https://a.com and http://b.org for info."
        result = sanitize_bot_response(text)
        assert "https://" not in result
        assert "http://" not in result


# ---------------------------------------------------------------------------
# Competitor stripping
# ---------------------------------------------------------------------------

_COMPETITORS = [
    "Opendoor", "Zillow Offers", "Redfin", "Offerpad",
    "We Buy Ugly Houses", "HomeVestors", "Knock", "Orchard", "Flyhomes",
]


class TestCompetitorStripping:
    @pytest.mark.parametrize("name", _COMPETITORS)
    def test_strips_competitor(self, name):
        result = sanitize_bot_response(f"You should try {name} instead.")
        assert name.lower() not in result.lower()

    def test_case_insensitive_competitor(self):
        result = sanitize_bot_response("Have you heard of OPENDOOR?")
        assert "opendoor" not in result.lower()


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncation:
    def test_long_text_truncated(self):
        long_text = "word " * 200  # 1000 chars
        result = sanitize_bot_response(long_text)
        assert len(result) <= 483  # 480 + "..."

    def test_truncation_ends_with_ellipsis(self):
        long_text = "word " * 200
        result = sanitize_bot_response(long_text)
        assert result.endswith("...")

    def test_truncation_at_word_boundary(self):
        long_text = "word " * 200
        result = sanitize_bot_response(long_text)
        # Should not cut mid-word
        assert not result.rstrip(".").endswith("wor")

    def test_short_text_not_truncated(self):
        short = "This is short."
        assert sanitize_bot_response(short) == short

    def test_exactly_480_not_truncated(self):
        text = "a" * 480
        assert sanitize_bot_response(text) == text


# ---------------------------------------------------------------------------
# Empty / None input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_string(self):
        assert sanitize_bot_response("") == ""

    def test_none_returns_empty(self):
        assert sanitize_bot_response(None) == ""


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------

class TestCombined:
    def test_identity_url_competitor_combined(self):
        text = "I'm an AI. Check https://evil.com or try Opendoor."
        result = sanitize_bot_response(text)
        assert "AI" not in result
        assert "https://" not in result
        assert "opendoor" not in result.lower()
        # Should still have some content
        assert len(result) > 0

    def test_double_spaces_cleaned(self):
        text = "Hello   there   friend."
        result = sanitize_bot_response(text)
        assert "  " not in result
