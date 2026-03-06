"""Tests for bots.shared.bot_settings — in-memory override store."""
from __future__ import annotations

import pytest

from bots.shared import bot_settings
from bots.shared.bot_settings import (
    KNOWN_BOTS,
    get_all_overrides,
    get_override,
    reset,
    update_settings,
)


@pytest.fixture(autouse=True)
def _clean_overrides():
    """Reset overrides before and after every test."""
    reset()
    yield
    reset()


# ---------------------------------------------------------------------------
# KNOWN_BOTS
# ---------------------------------------------------------------------------

class TestKnownBots:
    def test_known_bots_contains_expected(self):
        assert "seller" in KNOWN_BOTS
        assert "buyer" in KNOWN_BOTS
        assert "lead" in KNOWN_BOTS

    def test_known_bots_is_set(self):
        assert isinstance(KNOWN_BOTS, set)
        assert len(KNOWN_BOTS) == 3


# ---------------------------------------------------------------------------
# get_override
# ---------------------------------------------------------------------------

class TestGetOverride:
    def test_returns_empty_dict_when_not_set(self):
        assert get_override("seller") == {}

    def test_returns_empty_dict_for_unknown_bot(self):
        assert get_override("nonexistent") == {}

    def test_returns_overrides_after_update(self):
        update_settings("seller", {"tone": "friendly"})
        assert get_override("seller") == {"tone": "friendly"}


# ---------------------------------------------------------------------------
# update_settings
# ---------------------------------------------------------------------------

class TestUpdateSettings:
    def test_sets_new_override(self):
        update_settings("buyer", {"max_retries": 3})
        assert get_override("buyer") == {"max_retries": 3}

    def test_partial_update_merges(self):
        update_settings("seller", {"tone": "friendly"})
        update_settings("seller", {"language": "es"})
        result = get_override("seller")
        assert result == {"tone": "friendly", "language": "es"}

    def test_overwrites_existing_key(self):
        update_settings("seller", {"tone": "friendly"})
        update_settings("seller", {"tone": "professional"})
        assert get_override("seller") == {"tone": "professional"}

    def test_works_for_unknown_bot(self):
        update_settings("custom_bot", {"key": "value"})
        assert get_override("custom_bot") == {"key": "value"}


# ---------------------------------------------------------------------------
# get_all_overrides
# ---------------------------------------------------------------------------

class TestGetAllOverrides:
    def test_empty_when_no_overrides(self):
        result = get_all_overrides()
        assert result == {"seller": {}, "buyer": {}, "lead": {}}

    def test_includes_only_known_bots(self):
        update_settings("seller", {"tone": "warm"})
        update_settings("custom_bot", {"x": 1})  # not in KNOWN_BOTS
        result = get_all_overrides()
        assert "seller" in result
        assert "buyer" in result
        assert "lead" in result
        assert "custom_bot" not in result

    def test_returns_overrides_for_set_bots(self):
        update_settings("seller", {"tone": "warm"})
        update_settings("buyer", {"max_q": 5})
        result = get_all_overrides()
        assert result["seller"] == {"tone": "warm"}
        assert result["buyer"] == {"max_q": 5}
        assert result["lead"] == {}


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_specific_bot(self):
        update_settings("seller", {"tone": "warm"})
        update_settings("buyer", {"max_q": 5})
        reset("seller")
        assert get_override("seller") == {}
        assert get_override("buyer") == {"max_q": 5}

    def test_reset_all(self):
        update_settings("seller", {"tone": "warm"})
        update_settings("buyer", {"max_q": 5})
        reset()
        assert get_override("seller") == {}
        assert get_override("buyer") == {}

    def test_reset_nonexistent_bot_no_error(self):
        reset("nonexistent")  # should not raise

    def test_reset_none_clears_all(self):
        update_settings("lead", {"x": 1})
        reset(None)
        assert get_override("lead") == {}
