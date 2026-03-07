"""
Canonical conversation contract helpers.

This module layers a single operator-facing conversation vocabulary on top of
the existing seller / buyer / lead implementations without requiring an
immediate database migration.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class ConversationMode(str, Enum):
    SELLER = "seller"
    BUYER = "buyer"
    LEAD_INTAKE = "lead_intake"
    BILINGUAL_HANDOFF = "bilingual_handoff"
    HUMAN_HANDOFF = "human_handoff"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    QUALIFIED = "qualified"
    STALLED = "stalled"
    AWAITING_HUMAN = "awaiting_human"
    BOOKED = "booked"
    CLOSED = "closed"
    SUPPRESSED = "suppressed"


class HandoffReason(str, Enum):
    JORGE_ACTIVE = "jorge_active"
    NEEDS_BILINGUAL = "needs_bilingual"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    LOW_CONFIDENCE = "low_confidence"
    MANUAL_OVERRIDE = "manual_override"
    AMBIGUOUS_INTAKE = "ambiguous_intake"


MODE_VERSION = 1
CONVERSATION_MODE_CACHE_PREFIX = "conversation:mode:"

_SPANISH_INDICATORS: frozenset = frozenset(
    {"hola", "casa", "vender", "comprar", "precio", "cuanto", "gracias", "buenas", "quiero", "tengo"}
)


def is_likely_spanish(text: str) -> bool:
    """Return True if the message contains 2+ Spanish indicator words."""
    cleaned = re.sub(r"[^a-záéíóúñü\s]", " ", text.lower())
    words = set(cleaned.split())
    return len(words & _SPANISH_INDICATORS) >= 2


def has_jorge_active_tag(tags: list[Any] | tuple[Any, ...] | set[Any] | None) -> bool:
    """Treat Jorge's manual takeover tag as case/format insensitive."""
    if not tags:
        return False
    normalized = {
        str(tag).strip().lower().replace("_", " ").replace("-", " ")
        for tag in tags
        if str(tag).strip()
    }
    return "jorge active" in normalized


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_conversation_mode(raw: Optional[str]) -> ConversationMode:
    value = (raw or "").strip().lower()
    mapping = {
        "seller": ConversationMode.SELLER,
        "seller_bot": ConversationMode.SELLER,
        "seller-bot": ConversationMode.SELLER,
        "buyer": ConversationMode.BUYER,
        "buyer_bot": ConversationMode.BUYER,
        "buyer-bot": ConversationMode.BUYER,
        "lead": ConversationMode.LEAD_INTAKE,
        "lead_bot": ConversationMode.LEAD_INTAKE,
        "lead-bot": ConversationMode.LEAD_INTAKE,
        "new_lead": ConversationMode.LEAD_INTAKE,
        "new-lead": ConversationMode.LEAD_INTAKE,
        "lead_intake": ConversationMode.LEAD_INTAKE,
        "lead-intake": ConversationMode.LEAD_INTAKE,
        "bilingual_handoff": ConversationMode.BILINGUAL_HANDOFF,
        "bilingual-handoff": ConversationMode.BILINGUAL_HANDOFF,
        "human_handoff": ConversationMode.HUMAN_HANDOFF,
        "human-handoff": ConversationMode.HUMAN_HANDOFF,
    }
    if value in mapping:
        return mapping[value]
    for token, mode in (
        ("seller", ConversationMode.SELLER),
        ("buyer", ConversationMode.BUYER),
        ("lead", ConversationMode.LEAD_INTAKE),
    ):
        if token in value:
            return mode
    return ConversationMode.LEAD_INTAKE


def mode_to_assignment(mode: ConversationMode) -> Optional[str]:
    if mode is ConversationMode.SELLER:
        return "seller"
    if mode is ConversationMode.BUYER:
        return "buyer"
    if mode is ConversationMode.LEAD_INTAKE:
        return "lead"
    return None


@dataclass
class CanonicalConversation:
    contact_id: str
    location_id: str
    mode: ConversationMode
    status: ConversationStatus
    current_stage: str
    questions_answered: int
    temperature: Optional[str]
    human_takeover: bool
    bilingual_required: bool
    handoff_reason: Optional[str]
    qualification_summary: Dict[str, Any]
    next_recommended_action: Optional[str]
    conversation_history: list[dict[str, Any]]
    crm_sync_status: str = "pending"
    last_inbound_at: Optional[str] = None
    last_outbound_at: Optional[str] = None
    message_suppression_reason: Optional[str] = None
    mode_version: int = MODE_VERSION

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "mode_version": self.mode_version,
            "mode": self.mode.value,
            "status": self.status.value,
            "current_stage": self.current_stage,
            "questions_answered": self.questions_answered,
            "temperature": self.temperature,
            "human_takeover": self.human_takeover,
            "bilingual_required": self.bilingual_required,
            "handoff_reason": self.handoff_reason,
            "qualification_summary": self.qualification_summary,
            "next_recommended_action": self.next_recommended_action,
            "conversation_history": self.conversation_history,
            "crm_sync_status": self.crm_sync_status,
            "last_inbound_at": self.last_inbound_at,
            "last_outbound_at": self.last_outbound_at,
            "message_suppression_reason": self.message_suppression_reason,
        }

    def to_columns(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "mode_version": self.mode_version,
            "status": self.status.value,
            "handoff_reason": self.handoff_reason,
            "human_takeover": self.human_takeover,
            "bilingual_required": self.bilingual_required,
            "message_suppression_reason": self.message_suppression_reason,
            "qualification_summary": self.qualification_summary,
            "next_recommended_action": self.next_recommended_action,
            "crm_sync_status": self.crm_sync_status,
            "last_inbound_at": _parse_iso(self.last_inbound_at),
            "last_outbound_at": _parse_iso(self.last_outbound_at),
        }


def derive_status(
    *,
    current_stage: Optional[str],
    qualification_complete: bool,
    appointment_booked: bool = False,
    human_takeover: bool = False,
    bilingual_required: bool = False,
    suppressed: bool = False,
) -> ConversationStatus:
    if suppressed:
        return ConversationStatus.SUPPRESSED
    if appointment_booked:
        return ConversationStatus.BOOKED
    if human_takeover or bilingual_required:
        return ConversationStatus.AWAITING_HUMAN
    if (current_stage or "").upper() == "STALLED":
        return ConversationStatus.STALLED
    if qualification_complete or (current_stage or "").upper() == "QUALIFIED":
        return ConversationStatus.QUALIFIED
    return ConversationStatus.ACTIVE


def build_canonical_conversation(
    *,
    contact_id: str,
    location_id: str,
    mode: ConversationMode,
    current_stage: Optional[str],
    questions_answered: int,
    temperature: Optional[str],
    qualification_complete: bool,
    next_recommended_action: Optional[str],
    qualification_summary: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[list[dict[str, Any]]] = None,
    human_takeover: bool = False,
    bilingual_required: bool = False,
    handoff_reason: Optional[str] = None,
    appointment_booked: bool = False,
    suppressed: bool = False,
    last_inbound_at: Optional[str] = None,
    last_outbound_at: Optional[str] = None,
    message_suppression_reason: Optional[str] = None,
    crm_sync_status: str = "pending",
) -> CanonicalConversation:
    return CanonicalConversation(
        contact_id=contact_id,
        location_id=location_id,
        mode=mode,
        status=derive_status(
            current_stage=current_stage,
            qualification_complete=qualification_complete,
            appointment_booked=appointment_booked,
            human_takeover=human_takeover,
            bilingual_required=bilingual_required,
            suppressed=suppressed,
        ),
        current_stage=current_stage or "Q0",
        questions_answered=questions_answered,
        temperature=temperature,
        human_takeover=human_takeover,
        bilingual_required=bilingual_required,
        handoff_reason=handoff_reason,
        qualification_summary=qualification_summary or {},
        next_recommended_action=next_recommended_action,
        conversation_history=conversation_history or [],
        crm_sync_status=crm_sync_status,
        last_inbound_at=last_inbound_at or _now_iso(),
        last_outbound_at=last_outbound_at,
        message_suppression_reason=message_suppression_reason,
    )


def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _iso_or_none(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.isoformat()
    return str(raw)


def extract_canonical_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = metadata or {}
    return {
        "mode_version": meta.get("mode_version", MODE_VERSION),
        "mode": meta.get("mode", ConversationMode.LEAD_INTAKE.value),
        "status": meta.get("status", ConversationStatus.ACTIVE.value),
        "handoff_reason": meta.get("handoff_reason"),
        "human_takeover": bool(meta.get("human_takeover")),
        "bilingual_required": bool(meta.get("bilingual_required")),
        "message_suppression_reason": meta.get("message_suppression_reason"),
        "last_inbound_at": meta.get("last_inbound_at"),
        "last_outbound_at": meta.get("last_outbound_at"),
        "next_recommended_action": meta.get("next_recommended_action"),
        "qualification_summary": meta.get("qualification_summary") or {},
    }


def extract_canonical_view(conversation: Any) -> Dict[str, Any]:
    metadata = getattr(conversation, "metadata_json", None) or {}
    fallback = extract_canonical_metadata(metadata)
    def _col(attr: str) -> Any:
        v = getattr(conversation, attr, None)
        return v if v is not None else None

    def _first_non_none(*values: Any) -> Any:
        for v in values:
            if v is not None:
                return v
        return None

    return {
        "mode_version": _first_non_none(_col("mode_version"), fallback["mode_version"]),
        "mode": _first_non_none(_col("mode"), fallback["mode"]),
        "status": _first_non_none(_col("status"), fallback["status"]),
        "handoff_reason": _first_non_none(_col("handoff_reason"), fallback["handoff_reason"]),
        "human_takeover": bool(
            _first_non_none(_col("human_takeover"), fallback["human_takeover"])
        ),
        "bilingual_required": bool(
            _first_non_none(_col("bilingual_required"), fallback["bilingual_required"])
        ),
        "message_suppression_reason": _first_non_none(
            _col("message_suppression_reason"), fallback["message_suppression_reason"]
        ),
        "last_inbound_at": _first_non_none(
            _iso_or_none(_col("last_inbound_at")), fallback["last_inbound_at"]
        ),
        "last_outbound_at": _first_non_none(
            _iso_or_none(_col("last_outbound_at")), fallback["last_outbound_at"]
        ),
        "next_recommended_action": _first_non_none(
            _col("next_recommended_action"), fallback["next_recommended_action"]
        ),
        "qualification_summary": _first_non_none(_col("qualification_summary"), fallback["qualification_summary"]) or {},
        "crm_sync_status": _first_non_none(_col("crm_sync_status"), metadata.get("crm_sync_status"), "pending"),
        "temperature": _first_non_none(_col("temperature"), metadata.get("temperature")),
    }
