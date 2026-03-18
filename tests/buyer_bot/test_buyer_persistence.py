"""Tests for buyer bot DB exception handling (C5)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from bots.buyer_bot.buyer_bot import JorgeBuyerBot, BuyerQualificationState


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def buyer_service(mock_cache):
    with patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=mock_cache), \
         patch("bots.buyer_bot.buyer_bot.GHLClient"), \
         patch("bots.buyer_bot.buyer_bot.ClaudeClient"), \
         patch("bots.buyer_bot.buyer_bot.CalendarBookingService"):
        svc = JorgeBuyerBot()
        svc.cache = mock_cache
        return svc


@pytest.fixture
def sample_buyer_state():
    return BuyerQualificationState(
        contact_id="buyer_test_001",
        location_id="loc_test",
        current_question=2,
        questions_answered=2,
        stage="Q2",
        last_interaction=datetime.now(timezone.utc),
        conversation_started=datetime.now(timezone.utc),
    )


class TestBuyerDBExceptionHandling:
    """C5: DB errors in buyer bot are logged at ERROR level; non-DB errors propagate."""

    @pytest.mark.asyncio
    async def test_db_error_logs_error_not_warning(self, buyer_service, sample_buyer_state):
        """SQLAlchemyError during upsert_conversation is caught and logged at error level."""
        from sqlalchemy.exc import SQLAlchemyError

        with patch("bots.buyer_bot.buyer_bot.upsert_conversation", side_effect=SQLAlchemyError("DB down")), \
             patch.object(buyer_service.logger, "error") as mock_error, \
             patch.object(buyer_service.logger, "warning") as mock_warning:
            await buyer_service.save_conversation_state("buyer_test_001", sample_buyer_state)

        mock_error.assert_called_once()
        assert "contact_id" in mock_error.call_args[0][0]
        mock_warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_db_error_propagates(self, buyer_service, sample_buyer_state):
        """ValueError from upsert_conversation is not swallowed and propagates."""
        with patch("bots.buyer_bot.buyer_bot.upsert_conversation", side_effect=ValueError("unexpected")):
            with pytest.raises(ValueError, match="unexpected"):
                await buyer_service.save_conversation_state("buyer_test_001", sample_buyer_state)
