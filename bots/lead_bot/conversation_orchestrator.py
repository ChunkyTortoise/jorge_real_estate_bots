"""Webhook normalization and canonical routing decisions for inbound messages."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from bots.shared.logger import get_logger
from bots.shared.conversation_contract import (
    CONVERSATION_MODE_CACHE_PREFIX,
    ConversationMode,
    HandoffReason,
    is_likely_spanish,
    normalize_conversation_mode,
)

logger = get_logger(__name__)


@dataclass
class NormalizedInboundMessage:
    contact_id: str
    location_id: str
    message_body: str
    explicit_mode: Optional[ConversationMode]
    contact_info: Dict[str, Any]
    custom_data: Dict[str, Any]


@dataclass
class RoutingDecision:
    mode: ConversationMode
    source: str
    explicit: bool = False
    handoff_reason: Optional[str] = None
    contact_snapshot: Optional[Dict[str, Any]] = None


_SELLER_INTENT_RE = re.compile(
    r'\b(?:sell\s+my\s+(?:house|home|property)|want\s+to\s+sell|need\s+to\s+sell|selling\s+my\s+(?:house|home))\b',
    re.IGNORECASE,
)

_BUYER_INTENT_RE = re.compile(
    r'\b(?:buy\s+a\s+(?:house|home)|looking\s+to\s+buy|want\s+to\s+buy|need\s+to\s+buy|looking\s+for\s+a\s+(?:house|home))\b',
    re.IGNORECASE,
)


def _has_seller_intent(text: str) -> bool:
    return bool(_SELLER_INTENT_RE.search(text))


def _has_buyer_intent(text: str) -> bool:
    return bool(_BUYER_INTENT_RE.search(text))


def normalize_payload(payload: Dict[str, Any], default_location_id: str) -> NormalizedInboundMessage:
    contact_id = payload.get("contactId") or payload.get("contact_id") or ""
    if not contact_id:
        fallback = payload.get("id") or ""
        if fallback:
            logger.warning(f"normalize_payload: using 'id' fallback for contact_id={fallback!r} — verify this is a contact ID")
        contact_id = fallback
    location_id = payload.get("locationId") or payload.get("location_id") or default_location_id
    custom_data: Dict[str, Any] = payload.get("customData") or {}
    msg = payload.get("message")
    message_body = (
        payload.get("body")
        or ((msg.get("body") or msg.get("text") or "") if isinstance(msg, dict) else (msg if isinstance(msg, str) else ""))
        or ""
    )
    explicit_raw = custom_data.get("ai_mode") or custom_data.get("bot_type") or custom_data.get("Bot Type") or payload.get("bot_type")
    explicit_mode = normalize_conversation_mode(explicit_raw) if explicit_raw else None
    contact_info = {
        "name": payload.get("fullName") or custom_data.get("name"),
        "email": payload.get("email") or custom_data.get("email"),
        "phone": payload.get("phone") or custom_data.get("phone"),
    }
    return NormalizedInboundMessage(
        contact_id=str(contact_id).strip(),
        location_id=str(location_id).strip() if location_id else "",
        message_body=message_body,
        explicit_mode=explicit_mode,
        contact_info=contact_info,
        custom_data=custom_data,
    )


async def resolve_mode(
    *,
    payload: NormalizedInboundMessage,
    cache: Any,
    ghl_client: Any,
) -> RoutingDecision:
    if payload.explicit_mode:
        return RoutingDecision(mode=payload.explicit_mode, source="payload", explicit=True)

    if cache:
        for key, source in (
            (f"{CONVERSATION_MODE_CACHE_PREFIX}{payload.contact_id}", "canonical_cache"),
            (f"assigned_bot:{payload.contact_id}", "assignment_cache"),
        ):
            try:
                cached = await cache.get(key)
            except Exception:
                cached = None
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8")
                return RoutingDecision(mode=normalize_conversation_mode(cached), source=source)

    _ghl_contact: Optional[Dict[str, Any]] = None
    if ghl_client:
        try:
            contact_resp = await asyncio.wait_for(
                ghl_client.get_contact(payload.contact_id), timeout=5.0
            )
            _ghl_contact = contact_resp
            custom_fields = (contact_resp.get("contact", contact_resp).get("customFields", []))
            for cf in custom_fields:
                key = (cf.get("fieldKey") or cf.get("name") or "").lower().replace(" ", "_")
                if key in ("ai_mode", "bot_type"):
                    value = cf.get("value") or ""
                    if value:
                        return RoutingDecision(mode=normalize_conversation_mode(value), source="ghl_custom_field", contact_snapshot=contact_resp)
        except asyncio.TimeoutError:
            logger.warning(
                f"GHL get_contact timed out for {payload.contact_id} during mode resolution"
            )
        except Exception as _ghl_exc:
            logger.warning(
                f"GHL get_contact failed for {payload.contact_id} during mode resolution: {_ghl_exc}"
            )

    if is_likely_spanish(payload.message_body):
        return RoutingDecision(
            mode=ConversationMode.BILINGUAL_HANDOFF,
            source="classifier",
            handoff_reason=HandoffReason.NEEDS_BILINGUAL.value,
            contact_snapshot=_ghl_contact,
        )
    if _has_seller_intent(payload.message_body):
        return RoutingDecision(mode=ConversationMode.SELLER, source="classifier", contact_snapshot=_ghl_contact)
    if _has_buyer_intent(payload.message_body):
        return RoutingDecision(mode=ConversationMode.BUYER, source="classifier", contact_snapshot=_ghl_contact)
    return RoutingDecision(
        mode=ConversationMode.LEAD_INTAKE,
        source="classifier",
        handoff_reason=HandoffReason.AMBIGUOUS_INTAKE.value,
        contact_snapshot=_ghl_contact,
    )
