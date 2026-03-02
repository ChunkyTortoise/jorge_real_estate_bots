"""Webhook routes for Lead Bot — GHL new-lead and unified dispatcher."""

import asyncio
import hashlib
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from bots.shared.config import settings
from bots.shared.logger import get_logger
from bots.shared.response_filter import sanitize_bot_response

logger = get_logger(__name__)

router = APIRouter()

_ASSIGNED_BOT_TTL = 604_800  # 7 days


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
        message_body = payload.get("body") or payload.get("message") or ""

        if not contact_id:
            logger.error("Unified webhook: missing contactId in payload")
            return {"status": "error", "detail": "missing contactId"}

        if not message_body.strip():
            logger.info(f"Unified webhook: empty message for {contact_id}, skipping")
            return {"status": "skipped", "reason": "empty message"}

        # Input length cap
        if len(message_body) > 2000:
            logger.warning(f"Long message truncated: contact={contact_id}, original_len={len(message_body)}")
            message_body = message_body[:2000]

        # Per-minute rate limiting
        _webhook_cache = state._webhook_cache
        if _webhook_cache:
            rate_key = f"rate:webhook:{datetime.now().strftime('%Y%m%d%H%M')}"
            rate_val = await _webhook_cache.get(rate_key)
            count = int(rate_val) if rate_val is not None else 0
            if count >= settings.rate_limit_per_minute:
                logger.warning(f"Webhook rate limit exceeded: {count} req/min for contact={contact_id}")
                return {"status": "throttled", "reason": "rate_limit"}
            await _webhook_cache.set(rate_key, str(count + 1), ttl=60)

        # Message deduplication (5-minute TTL)
        if _webhook_cache:
            dedup_key = f"dedup:{contact_id}:{hashlib.md5(message_body.encode()).hexdigest()}"
            if await _webhook_cache.get(dedup_key):
                logger.info(f"Duplicate message skipped: contact={contact_id}")
                return {"status": "skipped", "reason": "duplicate"}
            await _webhook_cache.set(dedup_key, "1", ttl=300)

        # Per-contact processing lock (30s TTL, wait up to 10s)
        _lock_acquired = False
        lock_key = f"lock:{contact_id}"
        if _webhook_cache:
            for _ in range(10):
                if not await _webhook_cache.get(lock_key):
                    break
                await asyncio.sleep(1)
            else:
                logger.warning(f"Processing lock held for contact={contact_id}, throttling")
                return {"status": "throttled", "reason": "processing_lock"}
            await _webhook_cache.set(lock_key, "1", ttl=30)
            _lock_acquired = True

        try:
            # Determine bot type
            custom_data: Dict = payload.get("customData") or {}
            bot_type: str = (
                custom_data.get("bot_type")
                or custom_data.get("Bot Type")
                or payload.get("bot_type")
                or ""
            )
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
                            break
                except Exception as e:
                    logger.warning(f"Could not fetch contact for bot_type lookup: {e}")

            bot_type_lower = (bot_type or "lead").lower()

            # Fix 3 — Bot exclusivity: one bot per contact (7-day assignment, explicit payload overrides)
            _assigned_key = f"assigned_bot:{contact_id}"
            if _webhook_cache:
                _assigned_bot = await _webhook_cache.get(_assigned_key)
                if _assigned_bot:
                    if not _bot_type_explicit:
                        # No explicit override in this webhook — honour the stored assignment
                        bot_type_lower = _assigned_bot
                    else:
                        # Explicit bot_type in payload — update stored assignment
                        await _webhook_cache.set(_assigned_key, bot_type_lower, ttl=_ASSIGNED_BOT_TTL)
                else:
                    await _webhook_cache.set(_assigned_key, bot_type_lower, ttl=_ASSIGNED_BOT_TTL)

            contact_info = {
                "name": payload.get("fullName") or custom_data.get("name"),
                "email": payload.get("email") or custom_data.get("email"),
                "phone": payload.get("phone") or custom_data.get("phone"),
            }

            logger.info(
                f"Unified webhook: contact={contact_id}, bot_type={bot_type_lower!r}, "
                f"msg={message_body[:60]!r}"
            )

            # Route to bot
            response_message: Optional[str] = None
            result_meta: Dict = {"bot_type": bot_type_lower}

            if "seller" in bot_type_lower:
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
                # Fix 4 — schedule tag application 30s after SMS is sent
                _tag_actions = [
                    a for a in result.actions_taken
                    if a.get("type") in ("add_tag", "remove_tag")
                ]
                if _tag_actions and state._ghl_client:
                    background_tasks.add_task(
                        _deferred_tag_apply, state._ghl_client, contact_id, _tag_actions
                    )

            elif "buyer" in bot_type_lower:
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
            response_message = sanitize_bot_response(response_message)
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
