"""Unit tests for conversation_contract — builder, deriver, extractor, normalizer."""
from __future__ import annotations

import pytest

from bots.shared.conversation_contract import (
    ConversationMode,
    ConversationStatus,
    HandoffReason,
    build_canonical_conversation,
    derive_status,
    extract_canonical_metadata,
    is_likely_spanish,
    mode_to_assignment,
    normalize_conversation_mode,
)


# ---------------------------------------------------------------------------
# normalize_conversation_mode
# ---------------------------------------------------------------------------
class TestNormalizeConversationMode:
    @pytest.mark.parametrize("raw,expected", [
        ("seller", ConversationMode.SELLER),
        ("seller_bot", ConversationMode.SELLER),
        ("seller-bot", ConversationMode.SELLER),
        ("buyer", ConversationMode.BUYER),
        ("buyer_bot", ConversationMode.BUYER),
        ("buyer-bot", ConversationMode.BUYER),
        ("lead", ConversationMode.LEAD_INTAKE),
        ("lead_bot", ConversationMode.LEAD_INTAKE),
        ("lead_intake", ConversationMode.LEAD_INTAKE),
        ("new_lead", ConversationMode.LEAD_INTAKE),
        ("bilingual_handoff", ConversationMode.BILINGUAL_HANDOFF),
        ("bilingual-handoff", ConversationMode.BILINGUAL_HANDOFF),
        ("human_handoff", ConversationMode.HUMAN_HANDOFF),
        ("human-handoff", ConversationMode.HUMAN_HANDOFF),
        # Substring fallback
        ("jorge_seller_bot_v2", ConversationMode.SELLER),
        ("my_buyer_flow", ConversationMode.BUYER),
        # Unknown → LEAD_INTAKE default
        ("", ConversationMode.LEAD_INTAKE),
        ("unknown_mode", ConversationMode.LEAD_INTAKE),
        (None, ConversationMode.LEAD_INTAKE),
    ])
    def test_mapping(self, raw, expected):
        assert normalize_conversation_mode(raw) == expected

    def test_case_insensitive(self):
        assert normalize_conversation_mode("SELLER") == ConversationMode.SELLER
        assert normalize_conversation_mode("Buyer") == ConversationMode.BUYER


# ---------------------------------------------------------------------------
# mode_to_assignment
# ---------------------------------------------------------------------------
class TestModeToAssignment:
    def test_seller_returns_seller(self):
        assert mode_to_assignment(ConversationMode.SELLER) == "seller"

    def test_buyer_returns_buyer(self):
        assert mode_to_assignment(ConversationMode.BUYER) == "buyer"

    def test_lead_returns_lead(self):
        assert mode_to_assignment(ConversationMode.LEAD_INTAKE) == "lead"

    def test_bilingual_returns_none(self):
        assert mode_to_assignment(ConversationMode.BILINGUAL_HANDOFF) is None

    def test_human_handoff_returns_none(self):
        assert mode_to_assignment(ConversationMode.HUMAN_HANDOFF) is None


# ---------------------------------------------------------------------------
# derive_status
# ---------------------------------------------------------------------------
class TestDeriveStatus:
    def test_suppressed_takes_priority(self):
        status = derive_status(
            current_stage="QUALIFIED",
            qualification_complete=True,
            appointment_booked=True,
            human_takeover=True,
            bilingual_required=True,
            suppressed=True,
        )
        assert status == ConversationStatus.SUPPRESSED

    def test_booked_when_appointment_booked(self):
        status = derive_status(
            current_stage="ACTIVE",
            qualification_complete=False,
            appointment_booked=True,
            suppressed=False,
        )
        assert status == ConversationStatus.BOOKED

    def test_awaiting_human_for_human_takeover(self):
        status = derive_status(
            current_stage="ACTIVE",
            qualification_complete=False,
            human_takeover=True,
        )
        assert status == ConversationStatus.AWAITING_HUMAN

    def test_awaiting_human_for_bilingual(self):
        status = derive_status(
            current_stage="ACTIVE",
            qualification_complete=False,
            bilingual_required=True,
        )
        assert status == ConversationStatus.AWAITING_HUMAN

    def test_stalled(self):
        status = derive_status(current_stage="STALLED", qualification_complete=False)
        assert status == ConversationStatus.STALLED

    def test_qualified_by_flag(self):
        status = derive_status(current_stage="ACTIVE", qualification_complete=True)
        assert status == ConversationStatus.QUALIFIED

    def test_qualified_by_stage(self):
        status = derive_status(current_stage="QUALIFIED", qualification_complete=False)
        assert status == ConversationStatus.QUALIFIED

    def test_active_default(self):
        status = derive_status(current_stage="Q2", qualification_complete=False)
        assert status == ConversationStatus.ACTIVE


# ---------------------------------------------------------------------------
# build_canonical_conversation
# ---------------------------------------------------------------------------
class TestBuildCanonicalConversation:
    def _build(self, **overrides):
        defaults = dict(
            contact_id="c1",
            location_id="loc1",
            mode=ConversationMode.SELLER,
            current_stage="Q2",
            questions_answered=2,
            temperature="warm",
            qualification_complete=False,
            next_recommended_action="Ask Q3",
        )
        defaults.update(overrides)
        return build_canonical_conversation(**defaults)

    def test_returns_canonical_conversation(self):
        cc = self._build()
        assert cc.contact_id == "c1"
        assert cc.mode == ConversationMode.SELLER
        assert cc.status == ConversationStatus.ACTIVE

    def test_suppressed_sets_status(self):
        cc = self._build(suppressed=True)
        assert cc.status == ConversationStatus.SUPPRESSED

    def test_human_takeover_sets_awaiting(self):
        cc = self._build(human_takeover=True)
        assert cc.status == ConversationStatus.AWAITING_HUMAN

    def test_qualification_complete_sets_qualified(self):
        cc = self._build(qualification_complete=True)
        assert cc.status == ConversationStatus.QUALIFIED

    def test_to_metadata_roundtrip(self):
        cc = self._build(handoff_reason=HandoffReason.NEEDS_HUMAN_REVIEW.value)
        meta = cc.to_metadata()
        assert meta["mode"] == ConversationMode.SELLER.value
        assert meta["handoff_reason"] == HandoffReason.NEEDS_HUMAN_REVIEW.value
        assert meta["status"] == ConversationStatus.ACTIVE.value

    def test_qualification_summary_defaults_to_empty_dict(self):
        cc = build_canonical_conversation(
            contact_id="x",
            location_id="y",
            mode=ConversationMode.BUYER,
            current_stage="Q0",
            questions_answered=0,
            temperature="cold",
            qualification_complete=False,
            next_recommended_action=None,
        )
        assert cc.qualification_summary == {}

    def test_conversation_history_defaults_to_empty(self):
        cc = self._build()
        assert cc.conversation_history == []

    def test_current_stage_defaults_to_q0_when_none(self):
        cc = self._build(current_stage=None)
        assert cc.current_stage == "Q0"


# ---------------------------------------------------------------------------
# extract_canonical_metadata
# ---------------------------------------------------------------------------
class TestExtractCanonicalMetadata:
    def test_empty_dict_returns_defaults(self):
        result = extract_canonical_metadata({})
        assert result["mode"] == ConversationMode.LEAD_INTAKE.value
        assert result["status"] == ConversationStatus.ACTIVE.value
        assert result["handoff_reason"] is None
        assert result["human_takeover"] is False
        assert result["bilingual_required"] is False

    def test_none_returns_defaults(self):
        result = extract_canonical_metadata(None)
        assert result["mode"] == ConversationMode.LEAD_INTAKE.value

    def test_extracts_mode_and_status(self):
        meta = {"mode": "seller", "status": "qualified"}
        result = extract_canonical_metadata(meta)
        assert result["mode"] == "seller"
        assert result["status"] == "qualified"

    def test_extracts_handoff_reason(self):
        meta = {"handoff_reason": HandoffReason.NEEDS_BILINGUAL.value}
        result = extract_canonical_metadata(meta)
        assert result["handoff_reason"] == HandoffReason.NEEDS_BILINGUAL.value

    def test_boolean_fields_coerced(self):
        meta = {"human_takeover": 1, "bilingual_required": "true"}
        result = extract_canonical_metadata(meta)
        assert result["human_takeover"] is True
        assert result["bilingual_required"] is True


# ---------------------------------------------------------------------------
# is_likely_spanish (centralized)
# ---------------------------------------------------------------------------
class TestIsLikelySpanish:
    def test_two_indicators_triggers(self):
        assert is_likely_spanish("hola casa") is True

    def test_full_spanish_sentence(self):
        assert is_likely_spanish("hola quiero comprar una casa") is True

    def test_one_indicator_insufficient(self):
        assert is_likely_spanish("hola") is False

    def test_pure_english_no_trigger(self):
        assert is_likely_spanish("I want to sell my house") is False

    def test_empty_string_no_trigger(self):
        assert is_likely_spanish("") is False

    def test_mixed_two_plus_triggers(self):
        assert is_likely_spanish("tengo gracias money") is True
