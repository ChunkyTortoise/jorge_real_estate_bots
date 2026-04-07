"""Tests for structured decision event logging at key routing/handoff decision points."""
from __future__ import annotations

import logging
from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import pytest

from bots.lead_bot.conversation_orchestrator import (
    NormalizedInboundMessage,
    emit_decision_event,
    resolve_mode,
)
from bots.shared.conversation_contract import ConversationMode
from bots.shared.event_models import DecisionEvent

_ORCHESTRATOR_LOGGER = "bots.lead_bot.conversation_orchestrator"


@pytest.fixture(autouse=True)
def _enable_propagation():
    """Temporarily enable propagation so caplog can capture log records."""
    lgr = logging.getLogger(_ORCHESTRATOR_LOGGER)
    orig = lgr.propagate
    lgr.propagate = True
    yield
    lgr.propagate = orig


class TestModeResolutionEmitsEvent:
    """Mode resolution in resolve_mode() should emit a decision_event log."""

    @pytest.mark.asyncio
    async def test_mode_resolution_emits_event(self, caplog):
        payload = NormalizedInboundMessage(
            contact_id="c-100",
            location_id="loc-1",
            message_body="I want to sell my house",
            explicit_mode=None,
            contact_info={},
            custom_data={},
        )
        with caplog.at_level(logging.INFO, logger=_ORCHESTRATOR_LOGGER):
            decision = await resolve_mode(payload=payload, cache=None, ghl_client=None)

        assert decision.mode == ConversationMode.SELLER
        event_logs = [r for r in caplog.records if r.message == "decision_event"]
        assert len(event_logs) >= 1
        event_data = event_logs[0].__dict__.get("decision_event", {})
        assert event_data["event_type"] == "mode_resolution"
        assert event_data["contact_id"] == "c-100"
        assert "seller" in event_data["decision"]


class TestBotRoutingEmitsEvent:
    """Bot routing event should be emitted when emit_decision_event is called."""

    def test_bot_routing_emits_event(self, caplog):
        event = DecisionEvent(
            event_type="bot_routing",
            contact_id="c-200",
            decision="routed_to_seller_bot",
            reason="mode=seller resolved via classifier",
            bot_type="seller",
        )
        with caplog.at_level(logging.INFO, logger=_ORCHESTRATOR_LOGGER):
            emit_decision_event(event)

        event_logs = [r for r in caplog.records if r.message == "decision_event"]
        assert len(event_logs) == 1
        event_data = event_logs[0].__dict__.get("decision_event", {})
        assert event_data["event_type"] == "bot_routing"
        assert event_data["contact_id"] == "c-200"
        assert event_data["decision"] == "routed_to_seller_bot"
        assert event_data["bot_type"] == "seller"


class TestHandoffEmitsEvent:
    """Handoff trigger should emit a decision_event log during bilingual resolution."""

    @pytest.mark.asyncio
    async def test_handoff_emits_event(self, caplog):
        payload = NormalizedInboundMessage(
            contact_id="c-300",
            location_id="loc-1",
            message_body="hola quiero vender mi casa",
            explicit_mode=None,
            contact_info={},
            custom_data={},
        )
        with caplog.at_level(logging.INFO, logger=_ORCHESTRATOR_LOGGER):
            decision = await resolve_mode(payload=payload, cache=None, ghl_client=None)

        assert decision.mode == ConversationMode.BILINGUAL_HANDOFF
        event_logs = [r for r in caplog.records if r.message == "decision_event"]
        assert len(event_logs) >= 1
        event_data = event_logs[0].__dict__.get("decision_event", {})
        assert event_data["event_type"] == "mode_resolution"
        assert event_data["contact_id"] == "c-300"
        assert "bilingual" in event_data["decision"]


class TestOptOutEmitsEvent:
    """Opt-out detection should emit a decision_event log."""

    def test_opt_out_emits_event(self, caplog):
        event = DecisionEvent(
            event_type="opt_out_detection",
            contact_id="c-400",
            decision="opt_out_recorded",
            reason="opt-out keyword detected in message: STOP",
        )
        with caplog.at_level(logging.INFO, logger=_ORCHESTRATOR_LOGGER):
            emit_decision_event(event)

        event_logs = [r for r in caplog.records if r.message == "decision_event"]
        assert len(event_logs) == 1
        event_data = event_logs[0].__dict__.get("decision_event", {})
        assert event_data["event_type"] == "opt_out_detection"
        assert event_data["contact_id"] == "c-400"
        assert event_data["decision"] == "opt_out_recorded"
