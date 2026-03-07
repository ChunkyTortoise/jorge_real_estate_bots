"""
Tests for GHL opportunity pipeline stage sync (F7).

Covers: buyer sync, seller sync, stage mapping, STALLED override,
        no-op when pipeline_id unconfigured, create vs update logic.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.buyer_bot.buyer_bot import BuyerQualificationState, JorgeBuyerBot
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _mock_ghl_for_sync():
    client = MagicMock()
    client.location_id = "loc-123"
    client.create_opportunity = AsyncMock(
        return_value={"data": {"id": "opp-new-1"}}
    )
    client.update_opportunity = AsyncMock(return_value={"success": True})
    return client


@pytest.fixture
def buyer_bot():
    ghl = _mock_ghl_for_sync()
    with patch("bots.shared.calendar_booking_service.settings") as ms:
        ms.jorge_calendar_id = ""
        ms.jorge_user_id = ""
        b = JorgeBuyerBot(ghl_client=ghl)
    return b


@pytest.fixture
def seller_bot():
    ghl = _mock_ghl_for_sync()
    with patch("bots.shared.calendar_booking_service.settings") as ms:
        ms.jorge_calendar_id = ""
        ms.jorge_user_id = ""
        b = JorgeSellerBot(ghl_client=ghl)
    return b


# ─────────────────────────────────────────────────────────────────────────────
# No-op when pipeline_id not configured
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_sync_noop_without_pipeline_id(buyer_bot):
    state = BuyerQualificationState(contact_id="c-1", location_id="loc-123")

    with patch("bots.buyer_bot.buyer_bot.settings") as ms:
        ms.buyer_pipeline_id = None
        await buyer_bot._sync_pipeline_stage("c-1", state, "cold")

    buyer_bot.ghl_client.create_opportunity.assert_not_called()
    buyer_bot.ghl_client.update_opportunity.assert_not_called()


@pytest.mark.asyncio
async def test_seller_sync_noop_without_pipeline_id(seller_bot):
    state = SellerQualificationState(contact_id="c-1", location_id="loc-123")

    with patch("bots.seller_bot.jorge_seller_bot.settings") as ms:
        ms.seller_pipeline_id = None
        await seller_bot._sync_pipeline_stage("c-1", state, "cold")

    seller_bot.ghl_client.create_opportunity.assert_not_called()
    seller_bot.ghl_client.update_opportunity.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Create on first call
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_creates_opportunity_on_first_sync(buyer_bot):
    state = BuyerQualificationState(contact_id="c-1", location_id="loc-123")
    assert state.opportunity_created is False

    with patch("bots.buyer_bot.buyer_bot.settings") as ms:
        ms.buyer_pipeline_id = "pipe-buy"
        ms.buyer_stage_new = "stage-new"
        ms.buyer_stage_preferences = None
        ms.buyer_stage_preapproved = None
        ms.buyer_stage_scheduling = None
        ms.buyer_stage_booked = None
        ms.buyer_stage_stalled = None
        await buyer_bot._sync_pipeline_stage("c-1", state, "cold")

    buyer_bot.ghl_client.create_opportunity.assert_called_once()
    payload = buyer_bot.ghl_client.create_opportunity.call_args[0][0]
    assert payload["pipelineId"] == "pipe-buy"
    assert payload["contactId"] == "c-1"
    assert state.opportunity_created is True
    assert state.opportunity_id == "opp-new-1"


@pytest.mark.asyncio
async def test_seller_creates_opportunity_on_first_sync(seller_bot):
    state = SellerQualificationState(contact_id="c-2", location_id="loc-123")
    assert state.opportunity_created is False

    with patch("bots.seller_bot.jorge_seller_bot.settings") as ms:
        ms.seller_pipeline_id = "pipe-sell"
        ms.seller_stage_new = "stage-sell-new"
        ms.seller_stage_conditions = None
        ms.seller_stage_pricing = None
        ms.seller_stage_offer = None
        ms.seller_stage_scheduling = None
        ms.seller_stage_booked = None
        ms.seller_stage_stalled = None
        await seller_bot._sync_pipeline_stage("c-2", state, "cold")

    seller_bot.ghl_client.create_opportunity.assert_called_once()
    assert state.opportunity_created is True


# ─────────────────────────────────────────────────────────────────────────────
# Update on subsequent calls
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_updates_opportunity_on_second_sync(buyer_bot):
    state = BuyerQualificationState(
        contact_id="c-1",
        location_id="loc-123",
        opportunity_created=True,
        opportunity_id="opp-existing",
        questions_answered=1,
    )

    with patch("bots.buyer_bot.buyer_bot.settings") as ms:
        ms.buyer_pipeline_id = "pipe-buy"
        ms.buyer_stage_new = None
        ms.buyer_stage_preferences = "stage-prefs"
        ms.buyer_stage_preapproved = None
        ms.buyer_stage_scheduling = None
        ms.buyer_stage_booked = None
        ms.buyer_stage_stalled = None
        await buyer_bot._sync_pipeline_stage("c-1", state, "warm")

    buyer_bot.ghl_client.create_opportunity.assert_not_called()
    buyer_bot.ghl_client.update_opportunity.assert_called_once_with(
        "opp-existing", {"pipelineStageId": "stage-prefs"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage mapping
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_stalled_maps_to_stalled_stage(buyer_bot):
    state = BuyerQualificationState(
        contact_id="c-1",
        location_id="loc-123",
        opportunity_created=True,
        opportunity_id="opp-stalled",
        stage="STALLED",
    )

    with patch("bots.buyer_bot.buyer_bot.settings") as ms:
        ms.buyer_pipeline_id = "pipe-buy"
        ms.buyer_stage_new = None
        ms.buyer_stage_preferences = None
        ms.buyer_stage_preapproved = None
        ms.buyer_stage_scheduling = None
        ms.buyer_stage_booked = None
        ms.buyer_stage_stalled = "stage-stalled"
        await buyer_bot._sync_pipeline_stage("c-1", state, "cold")

    buyer_bot.ghl_client.update_opportunity.assert_called_once_with(
        "opp-stalled", {"pipelineStageId": "stage-stalled"}
    )


@pytest.mark.asyncio
async def test_buyer_booked_maps_to_booked_stage(buyer_bot):
    state = BuyerQualificationState(
        contact_id="c-1",
        location_id="loc-123",
        opportunity_created=True,
        opportunity_id="opp-booked",
        appointment_booked=True,
    )

    with patch("bots.buyer_bot.buyer_bot.settings") as ms:
        ms.buyer_pipeline_id = "pipe-buy"
        ms.buyer_stage_new = None
        ms.buyer_stage_preferences = None
        ms.buyer_stage_preapproved = None
        ms.buyer_stage_scheduling = None
        ms.buyer_stage_booked = "stage-booked"
        ms.buyer_stage_stalled = None
        await buyer_bot._sync_pipeline_stage("c-1", state, "hot")

    buyer_bot.ghl_client.update_opportunity.assert_called_once_with(
        "opp-booked", {"pipelineStageId": "stage-booked"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fail silently on GHL errors
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buyer_sync_fails_silently_on_ghl_error(buyer_bot):
    buyer_bot.ghl_client.create_opportunity = AsyncMock(side_effect=RuntimeError("network"))
    state = BuyerQualificationState(contact_id="c-1", location_id="loc-123")

    with patch("bots.buyer_bot.buyer_bot.settings") as ms:
        ms.buyer_pipeline_id = "pipe-buy"
        ms.buyer_stage_new = None
        ms.buyer_stage_preferences = None
        ms.buyer_stage_preapproved = None
        ms.buyer_stage_scheduling = None
        ms.buyer_stage_booked = None
        ms.buyer_stage_stalled = None
        # Should not raise
        await buyer_bot._sync_pipeline_stage("c-1", state, "cold")


@pytest.mark.asyncio
async def test_seller_sync_fails_silently_on_ghl_error(seller_bot):
    seller_bot.ghl_client.create_opportunity = AsyncMock(side_effect=RuntimeError("timeout"))
    state = SellerQualificationState(contact_id="c-2", location_id="loc-123")

    with patch("bots.seller_bot.jorge_seller_bot.settings") as ms:
        ms.seller_pipeline_id = "pipe-sell"
        ms.seller_stage_new = None
        ms.seller_stage_conditions = None
        ms.seller_stage_pricing = None
        ms.seller_stage_offer = None
        ms.seller_stage_scheduling = None
        ms.seller_stage_booked = None
        ms.seller_stage_stalled = None
        await seller_bot._sync_pipeline_stage("c-2", state, "cold")
