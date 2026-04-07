"""Webhook normalization and canonical routing decisions for inbound messages."""
from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from bots.shared.event_models import DecisionEvent
from bots.shared.ghl_client import unwrap_ghl_response
from bots.shared.logger import get_logger
from bots.shared.conversation_contract import (
    CONVERSATION_MODE_CACHE_PREFIX,
    ConversationMode,
    HandoffReason,
    is_likely_spanish,
    normalize_conversation_mode,
)

logger = get_logger(__name__)


def emit_decision_event(event: DecisionEvent) -> None:
    """Log a structured decision event via the existing JSON logger."""
    logger.info("decision_event", extra={"decision_event": asdict(event)})


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
        decision = RoutingDecision(mode=payload.explicit_mode, source="payload", explicit=True)
        emit_decision_event(DecisionEvent(
            event_type="mode_resolution",
            contact_id=payload.contact_id,
            decision=f"resolved_to_{payload.explicit_mode.value}",
            reason="explicit mode in payload",
            bot_type=payload.explicit_mode.value,
        ))
        return decision

    if cache:
        try:
            cached = await cache.get(f"{CONVERSATION_MODE_CACHE_PREFIX}{payload.contact_id}")
        except Exception:
            cached = None
        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            resolved = normalize_conversation_mode(cached)
            emit_decision_event(DecisionEvent(
                event_type="mode_resolution",
                contact_id=payload.contact_id,
                decision=f"resolved_to_{resolved.value}",
                reason="cached canonical mode",
                bot_type=resolved.value,
            ))
            return RoutingDecision(mode=resolved, source="canonical_cache")

    _ghl_contact: Optional[Dict[str, Any]] = None
    if ghl_client:
        try:
            contact_resp = await asyncio.wait_for(
                ghl_client.get_contact(payload.contact_id), timeout=5.0
            )
            _ghl_contact = contact_resp
            _inner = unwrap_ghl_response(contact_resp)
            custom_fields = _inner.get("contact", _inner).get("customFields", [])
            for cf in custom_fields:
                key = (cf.get("fieldKey") or cf.get("name") or "").lower().replace(" ", "_")
                if key in ("ai_mode", "bot_type"):
                    value = cf.get("value") or ""
                    if value:
                        ghl_mode = normalize_conversation_mode(value)
                        emit_decision_event(DecisionEvent(
                            event_type="mode_resolution",
                            contact_id=payload.contact_id,
                            decision=f"resolved_to_{ghl_mode.value}",
                            reason=f"GHL custom field {key}={value}",
                            bot_type=ghl_mode.value,
                        ))
                        return RoutingDecision(mode=ghl_mode, source="ghl_custom_field", contact_snapshot=contact_resp)
        except asyncio.TimeoutError:
            logger.warning(
                f"GHL get_contact timed out for {payload.contact_id} during mode resolution"
            )
        except Exception as _ghl_exc:
            logger.warning(
                f"GHL get_contact failed for {payload.contact_id} during mode resolution: {_ghl_exc}"
            )

    if is_likely_spanish(payload.message_body):
        emit_decision_event(DecisionEvent(
            event_type="mode_resolution",
            contact_id=payload.contact_id,
            decision="resolved_to_bilingual_handoff",
            reason="Spanish language detected in message",
            bot_type="bilingual_handoff",
        ))
        return RoutingDecision(
            mode=ConversationMode.BILINGUAL_HANDOFF,
            source="classifier",
            handoff_reason=HandoffReason.NEEDS_BILINGUAL.value,
            contact_snapshot=_ghl_contact,
        )
    if _has_seller_intent(payload.message_body):
        emit_decision_event(DecisionEvent(
            event_type="mode_resolution",
            contact_id=payload.contact_id,
            decision="resolved_to_seller",
            reason="seller intent keywords detected",
            bot_type="seller",
        ))
        return RoutingDecision(mode=ConversationMode.SELLER, source="classifier", contact_snapshot=_ghl_contact)
    if _has_buyer_intent(payload.message_body):
        emit_decision_event(DecisionEvent(
            event_type="mode_resolution",
            contact_id=payload.contact_id,
            decision="resolved_to_buyer",
            reason="buyer intent keywords detected",
            bot_type="buyer",
        ))
        return RoutingDecision(mode=ConversationMode.BUYER, source="classifier", contact_snapshot=_ghl_contact)
    emit_decision_event(DecisionEvent(
        event_type="mode_resolution",
        contact_id=payload.contact_id,
        decision="resolved_to_lead_intake",
        reason="no explicit mode or intent detected, defaulting to lead intake",
        bot_type="lead_intake",
    ))
    return RoutingDecision(
        mode=ConversationMode.LEAD_INTAKE,
        source="classifier",
        handoff_reason=HandoffReason.AMBIGUOUS_INTAKE.value,
        contact_snapshot=_ghl_contact,
    )
