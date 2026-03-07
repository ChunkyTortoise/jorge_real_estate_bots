"""Tests for Spanish language detection in seller/buyer bots."""
from __future__ import annotations

import pytest

from bots.shared.conversation_contract import is_likely_spanish

seller_spanish = is_likely_spanish
buyer_spanish = is_likely_spanish


@pytest.mark.parametrize("fn", [seller_spanish, buyer_spanish])
class TestSpanishDetection:
    """Both seller and buyer use the same ≥2 word threshold."""

    def test_single_spanish_word_no_trigger(self, fn):
        """One Spanish word is not enough — requires ≥ 2."""
        assert fn("hola") is False

    def test_two_spanish_words_triggers(self, fn):
        """Two known Spanish words → detected."""
        assert fn("hola quiero") is True

    def test_full_spanish_sentence_triggers(self, fn):
        """Full Spanish sentence → detected."""
        assert fn("hola quiero vender mi casa") is True

    def test_pure_english_no_trigger(self, fn):
        """Pure English does not trigger."""
        assert fn("I want to sell my house for cash") is False

    def test_english_with_one_loanword_no_trigger(self, fn):
        """English sentence with one accidental Spanish loanword → no trigger."""
        assert fn("I have a casa grande in California") is False

    def test_empty_string_no_trigger(self, fn):
        """Empty string does not crash or trigger."""
        assert fn("") is False

    def test_mixed_spanish_english_above_threshold_triggers(self, fn):
        """Mixed sentence with 2+ Spanish words triggers."""
        assert fn("I want to vender my casa please") is True

    def test_single_char_no_trigger(self, fn):
        """Single character doesn't trigger."""
        assert fn("h") is False
