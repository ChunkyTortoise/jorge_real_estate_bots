"""Unit tests for conversation_orchestrator — normalize_payload and resolve_mode."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bots.lead_bot.conversation_orchestrator import (
    NormalizedInboundMessage,
    RoutingDecision,
    normalize_payload,
    resolve_mode,
)
from bots.shared.conversation_contract import (
    CONVERSATION_MODE_CACHE_PREFIX,
    ConversationMode,
    HandoffReason,
)


# ---------------------------------------------------------------------------
# normalize_payload
# ---------------------------------------------------------------------------
class TestNormalizePayload:
    def test_basic_payload(self):
        payload = {
            "contactId": "c1",
            "locationId": "loc1",
            "body": "hello world",
        }
        result = normalize_payload(payload, "default_loc")
        assert result.contact_id == "c1"
        assert result.location_id == "loc1"
        assert result.message_body == "hello world"
        assert result.explicit_mode is None

    def test_falls_back_to_contact_id(self):
        result = normalize_payload({"contact_id": "c2", "body": "hi"}, "loc")
        assert result.contact_id == "c2"

    def test_falls_back_to_id_field(self):
        result = normalize_payload({"id": "c3", "body": "hi"}, "loc")
        assert result.contact_id == "c3"

    def test_uses_default_location_when_missing(self):
        result = normalize_payload({"contactId": "c1", "body": "hi"}, "DEFAULT")
        assert result.location_id == "DEFAULT"

    def test_message_from_dict_body_key(self):
        payload = {"contactId": "c1", "message": {"body": "msg from dict", "type": "SMS"}}
        result = normalize_payload(payload, "loc")
        assert result.message_body == "msg from dict"

    def test_message_from_dict_text_key(self):
        payload = {"contactId": "c1", "message": {"text": "text from dict"}}
        result = normalize_payload(payload, "loc")
        assert result.message_body == "text from dict"

    def test_message_as_string(self):
        payload = {"contactId": "c1", "message": "plain string"}
        result = normalize_payload(payload, "loc")
        assert result.message_body == "plain string"

    def test_message_as_list_does_not_raise(self):
        """If message is a list, message_body must be a string (not a list)."""
        payload = {"contactId": "c1", "message": ["item1", "item2"]}
        result = normalize_payload(payload, "loc")
        # Must be a str, not raise AttributeError when .strip() is called later
        assert isinstance(result.message_body, str)

    def test_body_takes_priority_over_message(self):
        payload = {"contactId": "c1", "body": "direct body", "message": {"body": "msg body"}}
        result = normalize_payload(payload, "loc")
        assert result.message_body == "direct body"

    def test_explicit_mode_from_custom_data_ai_mode(self):
        payload = {
            "contactId": "c1",
            "body": "hi",
            "customData": {"ai_mode": "seller"},
        }
        result = normalize_payload(payload, "loc")
        assert result.explicit_mode == ConversationMode.SELLER

    def test_explicit_mode_from_bot_type(self):
        payload = {"contactId": "c1", "body": "hi", "bot_type": "buyer"}
        result = normalize_payload(payload, "loc")
        assert result.explicit_mode == ConversationMode.BUYER

    def test_contact_id_stripped_of_whitespace(self):
        result = normalize_payload({"contactId": "  c1  ", "body": "hi"}, "loc")
        assert result.contact_id == "c1"

    def test_empty_contact_id_stays_empty(self):
        result = normalize_payload({"body": "hi"}, "loc")
        assert result.contact_id == ""


# ---------------------------------------------------------------------------
# resolve_mode
# ---------------------------------------------------------------------------
class TestResolveMode:
    def _make_msg(self, *, contact_id="c1", message_body="", explicit_mode=None):
        return NormalizedInboundMessage(
            contact_id=contact_id,
            location_id="loc",
            message_body=message_body,
            explicit_mode=explicit_mode,
            contact_info={},
            custom_data={},
        )

    @pytest.mark.asyncio
    async def test_explicit_mode_in_payload_wins(self):
        msg = self._make_msg(explicit_mode=ConversationMode.SELLER)
        decision = await resolve_mode(payload=msg, cache=None, ghl_client=None)
        assert decision.mode == ConversationMode.SELLER
        assert decision.source == "payload"
        assert decision.explicit is True

    @pytest.mark.asyncio
    async def test_canonical_cache_takes_precedence_over_assignment_cache(self):
        cache = AsyncMock()
        # canonical_cache returns "buyer", assignment_cache returns "seller"
        canonical_key = f"{CONVERSATION_MODE_CACHE_PREFIX}c1"

        async def get_side_effect(key):
            if key == canonical_key:
                return "buyer"
            return "seller"

        cache.get = AsyncMock(side_effect=get_side_effect)
        msg = self._make_msg()
        decision = await resolve_mode(payload=msg, cache=cache, ghl_client=None)
        assert decision.mode == ConversationMode.BUYER
        assert decision.source == "canonical_cache"

    @pytest.mark.asyncio
    async def test_assignment_cache_used_when_canonical_miss(self):
        cache = AsyncMock()
        canonical_key = f"{CONVERSATION_MODE_CACHE_PREFIX}c1"

        async def get_side_effect(key):
            if key == canonical_key:
                return None
            return "seller"

        cache.get = AsyncMock(side_effect=get_side_effect)
        msg = self._make_msg()
        decision = await resolve_mode(payload=msg, cache=cache, ghl_client=None)
        assert decision.mode == ConversationMode.SELLER
        assert decision.source == "assignment_cache"

    @pytest.mark.asyncio
    async def test_cache_failure_continues_to_ghl(self):
        """Cache exception must not propagate — routing continues to next step."""
        cache = AsyncMock()
        cache.get = AsyncMock(side_effect=Exception("redis down"))
        ghl_client = AsyncMock()
        ghl_client.get_contact = AsyncMock(return_value={"customFields": []})
        msg = self._make_msg(message_body="I want to sell my house")
        decision = await resolve_mode(payload=msg, cache=cache, ghl_client=ghl_client)
        # Should fall through to classifier — seller intent detected
        assert decision.mode == ConversationMode.SELLER

    @pytest.mark.asyncio
    async def test_ghl_custom_field_ai_mode(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        ghl_client = AsyncMock()
        ghl_client.get_contact = AsyncMock(return_value={
            "customFields": [{"fieldKey": "ai_mode", "value": "buyer"}]
        })
        msg = self._make_msg()
        decision = await resolve_mode(payload=msg, cache=cache, ghl_client=ghl_client)
        assert decision.mode == ConversationMode.BUYER
        assert decision.source == "ghl_custom_field"

    @pytest.mark.asyncio
    async def test_ghl_failure_logs_warning_and_falls_through(self):
        """GHL exception must be logged (not silently swallowed) and routing continues."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        ghl_client = AsyncMock()
        ghl_client.get_contact = AsyncMock(side_effect=Exception("GHL 401"))
        msg = self._make_msg(message_body="want to buy a home")
        decision = await resolve_mode(payload=msg, cache=cache, ghl_client=ghl_client)
        assert decision.mode == ConversationMode.BUYER
        assert decision.source == "classifier"

    @pytest.mark.asyncio
    async def test_spanish_detection(self):
        msg = self._make_msg(message_body="hola quiero comprar una casa")
        decision = await resolve_mode(payload=msg, cache=None, ghl_client=None)
        assert decision.mode == ConversationMode.BILINGUAL_HANDOFF
        assert decision.handoff_reason == HandoffReason.NEEDS_BILINGUAL.value

    @pytest.mark.asyncio
    async def test_seller_intent(self):
        msg = self._make_msg(message_body="I want to sell my house")
        decision = await resolve_mode(payload=msg, cache=None, ghl_client=None)
        assert decision.mode == ConversationMode.SELLER
        assert decision.source == "classifier"

    @pytest.mark.asyncio
    async def test_buyer_intent(self):
        msg = self._make_msg(message_body="I'm looking to buy a home")
        decision = await resolve_mode(payload=msg, cache=None, ghl_client=None)
        assert decision.mode == ConversationMode.BUYER

    @pytest.mark.asyncio
    async def test_fallback_to_lead_intake(self):
        msg = self._make_msg(message_body="hey there")
        decision = await resolve_mode(payload=msg, cache=None, ghl_client=None)
        assert decision.mode == ConversationMode.LEAD_INTAKE
        assert decision.handoff_reason == HandoffReason.AMBIGUOUS_INTAKE.value

    @pytest.mark.asyncio
    async def test_seller_intent_not_false_positive_on_substring(self):
        """'counsell my household' should NOT trigger seller intent (old substring match bug)."""
        msg = self._make_msg(message_body="counsell my household budget")
        decision = await resolve_mode(payload=msg, cache=None, ghl_client=None)
        # With regex word-boundary, this should NOT match seller intent
        assert decision.mode != ConversationMode.SELLER
