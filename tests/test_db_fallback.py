"""Tests for DB fallback path restoring conversation:mode: cache (Fix 6)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.shared.conversation_contract import CONVERSATION_MODE_CACHE_PREFIX, ConversationMode


# ---------------------------------------------------------------------------
# Fix 6 — Seller DB fallback restores conversation:mode: cache
# ---------------------------------------------------------------------------


class TestSellerDBFallbackRestoresModeCache:
    @pytest.mark.asyncio
    async def test_seller_db_fallback_restores_mode_cache(self):
        """After restoring seller state from DB, conversation:mode: key is written."""
        from bots.seller_bot.jorge_seller_bot import JorgeSellerBot

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Redis miss
        mock_cache.set = AsyncMock()

        mock_db_row = MagicMock()
        mock_db_row.extracted_data = {}
        mock_db_row.conversation_history = []
        mock_db_row.last_activity = datetime.now(timezone.utc)
        mock_db_row.conversation_started = datetime.now(timezone.utc)
        mock_db_row.metadata_json = {}
        mock_db_row.current_question = 0
        mock_db_row.questions_answered = 0
        mock_db_row.is_qualified = False
        mock_db_row.stage = "Q0"

        with (
            patch("bots.seller_bot.jorge_seller_bot.get_cache_service", return_value=mock_cache),
            patch("bots.seller_bot.jorge_seller_bot.fetch_conversation", new=AsyncMock(return_value=mock_db_row)),
        ):
            bot = JorgeSellerBot()
            await bot._get_or_create_state("seller-fallback", "loc-test")

        # Check that conversation:mode: was set to "seller"
        mode_key = f"{CONVERSATION_MODE_CACHE_PREFIX}seller-fallback"
        set_calls = [(c.args, c.kwargs) for c in mock_cache.set.call_args_list]
        mode_writes = [
            (args, kwargs) for (args, kwargs) in set_calls
            if args and args[0] == mode_key
        ]
        assert mode_writes, f"Expected cache.set({mode_key!r}, 'seller', ...) — got: {set_calls}"
        written_value = mode_writes[0][0][1] if len(mode_writes[0][0]) > 1 else mode_writes[0][1].get("value")
        assert written_value == ConversationMode.SELLER.value


# ---------------------------------------------------------------------------
# Fix 6 — Buyer DB fallback restores conversation:mode: cache
# ---------------------------------------------------------------------------


class TestBuyerDBFallbackRestoresModeCache:
    @pytest.mark.asyncio
    async def test_buyer_db_fallback_restores_mode_cache(self):
        """After restoring buyer state from DB, conversation:mode: key is written."""
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Redis miss
        mock_cache.set = AsyncMock()

        mock_db_row = MagicMock()
        mock_db_row.extracted_data = {}
        mock_db_row.conversation_history = []
        mock_db_row.last_activity = datetime.now(timezone.utc)
        mock_db_row.conversation_started = datetime.now(timezone.utc)
        mock_db_row.metadata_json = {}
        mock_db_row.current_question = 0
        mock_db_row.questions_answered = 0
        mock_db_row.is_qualified = False
        mock_db_row.stage = "Q0"
        mock_db_row.bot_type = "buyer"

        with (
            patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=mock_cache),
            patch("bots.buyer_bot.buyer_bot.fetch_conversation", new=AsyncMock(return_value=mock_db_row)),
        ):
            bot = JorgeBuyerBot()
            await bot._get_or_create_state("buyer-fallback", "loc-test")

        mode_key = f"{CONVERSATION_MODE_CACHE_PREFIX}buyer-fallback"
        set_calls = [(c.args, c.kwargs) for c in mock_cache.set.call_args_list]
        mode_writes = [
            (args, kwargs) for (args, kwargs) in set_calls
            if args and args[0] == mode_key
        ]
        assert mode_writes, f"Expected cache.set({mode_key!r}, 'buyer', ...) — got: {set_calls}"
        written_value = mode_writes[0][0][1] if len(mode_writes[0][0]) > 1 else mode_writes[0][1].get("value")
        assert written_value == ConversationMode.BUYER.value
