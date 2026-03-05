"""Webhook routes for Lead Bot — GHL new-lead and unified dispatcher."""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from bots.shared.config import settings
from bots.shared.funnel_attribution import FunnelEvent, FunnelTracker
from bots.shared.logger import get_logger
from bots.shared.response_filter import sanitize_bot_response
from bots.shared.sms_metrics_collector import SmsMetricsCollector

logger = get_logger(__name__)

# Module-level funnel tracker instance (in-memory, shared across requests)
_funnel_tracker = FunnelTracker()

router = APIRouter()

_ASSIGNED_BOT_TTL = 604_800  # 7 days


def _normalize_bot_type(raw: str) -> str:
    """Map raw bot_type values to canonical: 'seller', 'buyer', or 'lead'."""
    _VARIANTS: Dict[str, str] = {
        "seller_bot": "seller",
        "seller-bot": "seller",
        "buyer_bot": "buyer",
        "buyer-bot": "buyer",
        "lead_bot": "lead",
        "lead-bot": "lead",
        "new_lead": "lead",
        "new-lead": "lead",
    }
    lower = raw.strip().lower()
    if not lower:
        return "lead"
    if lower in ("seller", "buyer", "lead"):
        return lower
    if lower in _VARIANTS:
        return _VARIANTS[lower]
    for canonical in ("seller", "buyer", "lead"):
        if canonical in lower:
            logger.warning(f"Non-canonical bot_type {raw!r} matched to {canonical!r} by substring")
            return canonical
    logger.warning(f"Unknown bot_type {raw!r}, defaulting to 'lead'")
    return "lead"


async def _deferred_tag_apply(
    ghl_client: Any,
    contact_id: str,
    actions: List[Dict[str, Any]],
    delay_seconds: int = 30,
) -> None:
    """Apply add/remove tag actions after a delay so GHL workflows fire after SMS is delivered."""
    await asyncio.sleep(delay_seconds)
    for action in actions:
        try:
            if action.get("type") == "add_tag":
                await ghl_client.add_tag(contact_id, action["tag"])
            elif action.get("type") == "remove_tag":
                await ghl_client.remove_tag(contact_id, action["tag"])
        except Exception as e:
            logger.error(f"Deferred tag action failed for {contact_id}: {e}")


def _get_state():
    """Import runtime state lazily to avoid circular imports."""
    from bots.lead_bot import main as _m
    return _m


@router.post("/ghl/webhook/new-lead")
async def handle_new_lead(request: Request):
    """
    GHL Webhook: New Lead Created.

    CRITICAL: Must complete within 5 minutes for 10x conversion.
    """
    state = _get_state()
    start_time = time.time()

    try:
        payload_bytes = await request.body()
        signature = request.headers.get("x-wh-signature") or request.headers.get("X-HighLevel-Signature")
        if not state.verify_ghl_signature(payload_bytes, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        payload = json.loads(payload_bytes.decode("utf-8"))
        logger.info(f"New lead webhook received: {payload.get('id', 'unknown')}")

        contact_id = payload.get("id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Missing contact ID")

        analysis_start = time.time()
        analysis_result, metrics = await state.lead_analyzer.analyze_lead(payload)
        analysis_time_ms = (time.time() - analysis_start) * 1000

        if metrics.cache_hit:
            state.performance_stats["cache_hits"] += 1

        if analysis_time_ms > settings.lead_analysis_timeout_ms:
            logger.warning(
                f"Lead analysis took {analysis_time_ms:.1f}ms "
                f"(target: {settings.lead_analysis_timeout_ms}ms)"
            )
        else:
            logger.info(f"Lead analysis: {analysis_time_ms:.1f}ms ({metrics.analysis_type})")

        total_time_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Lead {contact_id} processed in {total_time_ms:.1f}ms "
            f"(Score: {analysis_result.get('score', 0)}, Temp: {analysis_result.get('temperature', 'unknown')})"
        )

        # Lock this contact to the lead bot for 7 days so follow-up replies
        # don't fall through to the GHL API and get misrouted to seller/buyer.
        _webhook_cache = state._webhook_cache
        if _webhook_cache:
            await _webhook_cache.set(
                f"assigned_bot:{contact_id}", "lead", ttl=_ASSIGNED_BOT_TTL,
            )

        return {
            "status": "processed",
            "contact_id": contact_id,
            "score": analysis_result.get("score", 0),
            "temperature": analysis_result.get("temperature", "warm"),
            "jorge_priority": analysis_result.get("jorge_priority", "normal"),
            "meets_jorge_criteria": analysis_result.get("meets_jorge_criteria", False),
            "estimated_commission": analysis_result.get("estimated_commission", 0.0),
            "processing_time_ms": total_time_ms,
            "within_5_minute_rule": metrics.five_minute_rule_compliant,
            "cache_hit": metrics.cache_hit,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing new lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ghl/webhook")
async def unified_ghl_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Unified GHL webhook dispatcher.

    Routes to Lead / Seller / Buyer based on bot_type in payload.
    Always returns HTTP 200 so GHL does not retry.
    """
    state = _get_state()

    try:
        payload_bytes = await request.body()
        signature = request.headers.get("x-wh-signature") or request.headers.get("X-HighLevel-Signature")
        if not state.verify_ghl_signature(payload_bytes, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        payload = json.loads(payload_bytes.decode("utf-8"))

        contact_id = payload.get("contactId") or payload.get("contact_id") or payload.get("id")
        location_id = (
            payload.get("locationId")
            or payload.get("location_id")
            or settings.ghl_location_id
        )
        _msg = payload.get("message")
        message_body = (
            payload.get("body")
            or ((_msg.get("body") or _msg.get("text") or "") if isinstance(_msg, dict) else _msg)
            or ""
        )

        if not contact_id:
            logger.error("Unified webhook: missing contactId in payload")
            return {"status": "error", "detail": "missing contactId"}

        # Funnel: AWARENESS — new message received for this contact
        try:
            _funnel_tracker.record_event(FunnelEvent(
                contact_id=contact_id,
                stage="awareness",
                bot_name="webhook",
                timestamp=datetime.now(),
            ))
        except Exception:
            pass

        if not message_body.strip():
            logger.info(f"Unified webhook: empty message for {contact_id}, skipping")
            return {"status": "skipped", "reason": "empty message"}

        # Input length cap
        if len(message_body) > 2000:
            logger.warning(f"Long message truncated: contact={contact_id}, original_len={len(message_body)}")
            message_body = message_body[:2000]

        # Per-minute rate limiting (atomic increment — C4)
        _webhook_cache = state._webhook_cache
        if _webhook_cache:
            rate_key = f"rate:webhook:{datetime.now().strftime('%Y%m%d%H%M')}"
            count = await _webhook_cache.increment(rate_key, ttl=60)
            if count > settings.rate_limit_per_minute:
                logger.warning(f"Webhook rate limit exceeded: {count} req/min for contact={contact_id}")
                return {"status": "throttled", "reason": "rate_limit"}

        # Message deduplication (5-minute TTL)
        if _webhook_cache:
            dedup_key = f"dedup:{contact_id}:{hashlib.md5(message_body.encode()).hexdigest()}"
            if await _webhook_cache.get(dedup_key):
                logger.info(f"Duplicate message skipped: contact={contact_id}")
                return {"status": "skipped", "reason": "duplicate"}
            await _webhook_cache.set(dedup_key, "1", ttl=300)

        # Per-contact rate limit (10 messages/minute)
        if _webhook_cache:
            contact_rate_key = f"rate:contact:{contact_id}:{datetime.now().strftime('%Y%m%d%H%M')}"
            contact_count = await _webhook_cache.increment(contact_rate_key, ttl=60)
            if contact_count > 10:
                logger.warning(f"Per-contact rate limit exceeded for {contact_id}")
                return {"status": "throttled", "reason": "per_contact_rate_limit"}

        # Per-contact processing lock (atomic setnx — C3)
        _lock_acquired = False
        lock_key = f"lock:{contact_id}"
        if _webhook_cache:
            _lock_acquired = await _webhook_cache.setnx(lock_key, "1", ttl=30)
            if not _lock_acquired:
                logger.warning(f"Processing lock held for contact={contact_id}, throttling")
                return {"status": "throttled", "reason": "processing_lock"}

        try:
            # Determine bot type — track source for diagnostics
            custom_data: Dict = payload.get("customData") or {}
            _bot_type_source = "default"
            bot_type: str = ""

            if custom_data.get("bot_type"):
                bot_type = custom_data["bot_type"]
                _bot_type_source = "customData.bot_type"
            elif custom_data.get("Bot Type"):
                bot_type = custom_data["Bot Type"]
                _bot_type_source = "customData.Bot_Type"
            elif payload.get("bot_type"):
                bot_type = payload["bot_type"]
                _bot_type_source = "payload.bot_type"

            # Track whether the payload explicitly specifies a bot (vs. GHL API fallback)
            _bot_type_explicit = bool(bot_type)

            if not bot_type and state._ghl_client:
                try:
                    contact_resp = await state._ghl_client.get_contact(contact_id)
                    custom_fields = (
                        contact_resp.get("contact", contact_resp).get("customFields", [])
                    )
                    for cf in custom_fields:
                        key = (cf.get("fieldKey") or cf.get("name") or "").lower().replace(" ", "_")
                        if key in ("bot_type", "bot type"):
                            bot_type = cf.get("value") or ""
                            if bot_type:
                                _bot_type_source = "ghl_api_custom_field"
                            break
                except Exception as e:
                    logger.warning(f"Could not fetch contact for bot_type lookup: {e}")

            bot_type_lower = _normalize_bot_type(bot_type)

            # Fix 3 — Bot exclusivity: one bot per contact (7-day assignment, explicit payload overrides)
            _assigned_key = f"assigned_bot:{contact_id}"
            if _webhook_cache:
                _assigned_bot = await _webhook_cache.get(_assigned_key)
                if _assigned_bot:
                    if not _bot_type_explicit:
                        # No explicit override in this webhook — honour the stored assignment
                        bot_type_lower = _assigned_bot
                        _bot_type_source = "redis_cache"
                    else:
                        # Explicit bot_type in payload — bot switch detected, purge old state
                        if _assigned_bot != bot_type_lower:
                            old_state_key = f"{_assigned_bot}:state:{contact_id}"
                            await _webhook_cache.delete(old_state_key)
                            logger.info(
                                f"[BOT-SWITCH] {contact_id}: {_assigned_bot!r} → {bot_type_lower!r}, "
                                f"cleared {old_state_key}"
                            )
                            # Record handoff in BotMetricsCollector
                            try:
                                from bots.shared.bot_metrics_collector import BotMetricsCollector
                                BotMetricsCollector().record_handoff(
                                    source=_assigned_bot,
                                    target=bot_type_lower,
                                    success=True,
                                    duration_ms=0,
                                )
                            except Exception:
                                pass
                        await _webhook_cache.set(_assigned_key, bot_type_lower, ttl=_ASSIGNED_BOT_TTL)
                else:
                    await _webhook_cache.set(_assigned_key, bot_type_lower, ttl=_ASSIGNED_BOT_TTL)

            contact_info = {
                "name": payload.get("fullName") or custom_data.get("name"),
                "email": payload.get("email") or custom_data.get("email"),
                "phone": payload.get("phone") or custom_data.get("phone"),
            }

            # Funnel: INTEREST — bot assigned to contact
            try:
                _funnel_tracker.record_event(FunnelEvent(
                    contact_id=contact_id,
                    stage="interest",
                    bot_name=bot_type_lower,
                    timestamp=datetime.now(),
                ))
            except Exception:
                pass

            logger.info(
                f"Unified webhook: contact={contact_id}, bot_type={bot_type_lower!r}, "
                f"source={_bot_type_source!r}, msg={message_body[:60]!r}"
            )

            # Route to bot
            response_message: Optional[str] = None
            result_meta: Dict = {"bot_type": bot_type_lower}

            if bot_type_lower == "seller":
                if not state.seller_bot_instance:
                    logger.error("Seller bot not initialized")
                    return {"status": "error", "detail": "seller bot unavailable"}
                result = await state.seller_bot_instance.process_seller_message(
                    contact_id=contact_id,
                    location_id=location_id,
                    message=message_body,
                    contact_info=contact_info,
                )
                response_message = result.response_message
                result_meta.update(
                    {
                        "temperature": result.seller_temperature,
                        "questions_answered": result.questions_answered,
                        "qualification_complete": result.qualification_complete,
                    }
                )
                # Funnel: CONSIDERATION (Q2+), INTENT (qualified), CONVERSION (appointment)
                try:
                    if result.questions_answered >= 2:
                        _funnel_tracker.record_event(FunnelEvent(
                            contact_id=contact_id, stage="consideration",
                            bot_name="seller", timestamp=datetime.now(),
                        ))
                    if result.qualification_complete:
                        _funnel_tracker.record_event(FunnelEvent(
                            contact_id=contact_id, stage="intent",
                            bot_name="seller", timestamp=datetime.now(),
                        ))
                    if "Appointment booked" in (result.next_steps or ""):
                        _funnel_tracker.record_event(FunnelEvent(
                            contact_id=contact_id, stage="purchase",
                            bot_name="seller", timestamp=datetime.now(),
                        ))
                except Exception:
                    pass
                # Fix 4 — schedule tag application 30s after SMS is sent
                _tag_actions = [
                    a for a in result.actions_taken
                    if a.get("type") in ("add_tag", "remove_tag")
                ]
                if _tag_actions and state._ghl_client:
                    background_tasks.add_task(
                        _deferred_tag_apply, state._ghl_client, contact_id, _tag_actions
                    )

            elif bot_type_lower == "buyer":
                if not state.buyer_bot_instance:
                    logger.error("Buyer bot not initialized")
                    return {"status": "error", "detail": "buyer bot unavailable"}
                result = await state.buyer_bot_instance.process_buyer_message(
                    contact_id=contact_id,
                    location_id=location_id,
                    message=message_body,
                    contact_info=contact_info,
                )
                response_message = result.response_message
                result_meta.update(
                    {
                        "temperature": result.buyer_temperature,
                        "questions_answered": result.questions_answered,
                        "qualification_complete": result.qualification_complete,
                    }
                )
                # Funnel: CONSIDERATION (Q2+), INTENT (qualified), CONVERSION (appointment)
                try:
                    if result.questions_answered >= 2:
                        _funnel_tracker.record_event(FunnelEvent(
                            contact_id=contact_id, stage="consideration",
                            bot_name="buyer", timestamp=datetime.now(),
                        ))
                    if result.qualification_complete:
                        _funnel_tracker.record_event(FunnelEvent(
                            contact_id=contact_id, stage="intent",
                            bot_name="buyer", timestamp=datetime.now(),
                        ))
                except Exception:
                    pass
                # Fix 4 — schedule tag application 30s after SMS is sent
                _tag_actions = [
                    a for a in result.actions_taken
                    if a.get("type") in ("add_tag", "remove_tag")
                ]
                if _tag_actions and state._ghl_client:
                    background_tasks.add_task(
                        _deferred_tag_apply, state._ghl_client, contact_id, _tag_actions
                    )

            else:
                lead_data = {"id": contact_id, "message": message_body, **contact_info}
                analysis, metrics = await state.lead_analyzer.analyze_lead(lead_data)
                result_meta.update(
                    {
                        "score": analysis.get("score", 0),
                        "temperature": analysis.get("temperature", "warm"),
                        "jorge_priority": analysis.get("jorge_priority", "normal"),
                    }
                )
                return {"status": "processed", **result_meta}

            # Send reply via GHL SMS (seller / buyer bots)
            response_message = sanitize_bot_response(response_message, bot_type=bot_type_lower)
            if response_message and state._ghl_client:
                try:
                    await state._ghl_client.send_message(contact_id, response_message, "SMS")
                    logger.info(f"Reply sent to {contact_id} via GHL SMS")
                except Exception as e:
                    logger.error(f"Failed to send GHL reply to {contact_id}: {e}")

            return {"status": "processed", **result_meta}

        finally:
            if _lock_acquired and _webhook_cache:
                await _webhook_cache.delete(lock_key)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified webhook unhandled error: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


@router.post("/api/ghl/webhook/message-status")
async def webhook_message_status(request: Request):
    """Handles GHL message delivery status callbacks."""
    state = _get_state()
    payload_bytes = await request.body()
    signature = request.headers.get("x-wh-signature") or request.headers.get("X-HighLevel-Signature")
    if not state.verify_ghl_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(payload_bytes.decode("utf-8"))
    event_type = payload.get("type", "")
    contact_id = payload.get("contactId", "")
    timestamp = datetime.now(timezone.utc)

    status_map = {
        "message.delivered": "delivered",
        "message.failed": "failed",
        "message.read": "read",
    }

    if event_type in status_map and contact_id:
        collector = SmsMetricsCollector()
        await collector.record_delivery(contact_id, status_map[event_type], timestamp)

    return {"status": "ok"}
