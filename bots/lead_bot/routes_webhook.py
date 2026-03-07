"""Webhook routes for Lead Bot — GHL new-lead and unified dispatcher."""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from bots.lead_bot.conversation_orchestrator import normalize_payload, resolve_mode
from bots.shared.config import settings
from bots.shared.conversation_contract import (
    CONVERSATION_MODE_CACHE_PREFIX,
    ConversationMode,
    HandoffReason,
    build_canonical_conversation,
    has_jorge_active_tag,
    mode_to_assignment,
    normalize_conversation_mode,
)
import redis.asyncio as _redis_lib

from bots.shared.funnel_attribution import FunnelEvent, FunnelTracker
from bots.shared.stall_reengagement import StallReengagementService
from bots.shared.logger import get_logger
from bots.shared.response_filter import sanitize_bot_response
from bots.shared.sms_metrics_collector import SmsMetricsCollector
from database.repository import (
    merge_conversation_metadata,
    update_conversation_outbound_at,
    upsert_conversation,
)

logger = get_logger(__name__)

# Funnel tracker backed by Redis for cross-restart durability
_funnel_tracker = FunnelTracker(redis_client=_redis_lib.from_url(settings.redis_url))

router = APIRouter()

_ASSIGNED_BOT_TTL = 604_800  # 7 days


def _normalize_bot_type(raw: str) -> str:
    """Map raw bot_type values to canonical: 'seller', 'buyer', or 'lead'."""
    mode = normalize_conversation_mode(raw)
    return mode_to_assignment(mode) or "lead"


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
            elif action.get("type") == "trigger_workflow":
                await ghl_client.trigger_workflow(contact_id, action["workflow_id"])
        except Exception as e:
            logger.error(f"Deferred tag action failed for {contact_id}: {e}")


async def _apply_post_send_updates(
    ghl_client: Any,
    contact_id: str,
    actions: List[Dict[str, Any]],
) -> None:
    """Apply non-tag actions after the outbound send path completes."""
    for action in actions:
        action_type = action.get("type")
        if action_type in ("add_tag", "remove_tag", "trigger_workflow"):
            continue
        try:
            if action_type == "update_custom_field":
                await ghl_client.update_custom_field(contact_id, action["field"], action["value"])
            elif action_type == "upsert_opportunity":
                await ghl_client.create_opportunity(action["payload"])
        except Exception as e:
            logger.error(f"Post-send CRM action failed for {contact_id}: {e}")


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
            await _webhook_cache.set(
                f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}",
                ConversationMode.LEAD_INTAKE.value,
                ttl=_ASSIGNED_BOT_TTL,
            )

        return {
            "status": "processed",
            "contact_id": contact_id,
            "mode": ConversationMode.LEAD_INTAKE.value,
            "conversation_status": "active",
            "score": analysis_result.get("score", 0),
            "temperature": analysis_result.get("temperature", "warm"),
            "jorge_priority": analysis_result.get("jorge_priority", "normal"),
            "meets_jorge_criteria": analysis_result.get("meets_jorge_criteria", False),
            "estimated_commission": analysis_result.get("estimated_commission", 0.0),
            "processing_time_ms": total_time_ms,
            "within_5_minute_rule": metrics.five_minute_rule_compliant,
            "cache_hit": metrics.cache_hit,
            "timestamp": datetime.now(timezone.utc).isoformat()
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
        normalized = normalize_payload(payload, settings.ghl_location_id)
        contact_id = normalized.contact_id
        location_id = normalized.location_id
        message_body = normalized.message_body

        if not contact_id:
            logger.error("Unified webhook: missing contactId in payload")
            return {"status": "error", "detail": "missing contactId"}

        # Opt-out detection: record and skip re-engagement for future stall messages
        if message_body:
            try:
                _srs = StallReengagementService()
                if _srs.is_opt_out_message(message_body):
                    await _srs.record_opt_out(contact_id)
                    logger.info("Opt-out recorded for %s — continuing with normal processing", contact_id)
            except Exception as _oe:
                logger.debug("Opt-out check failed: %s", _oe)

        # Funnel: AWARENESS — new message received for this contact
        try:
            await _funnel_tracker.record_event_async(FunnelEvent(
                contact_id=contact_id,
                stage="awareness",
                bot_name="webhook",
                timestamp=datetime.now(timezone.utc),
            ))
        except Exception as _e:
            logger.debug(f"Funnel tracker awareness event failed: {_e}")

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
            try:
                rate_key = f"rate:webhook:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
                count = await _webhook_cache.increment(rate_key, ttl=60)
                if count > settings.rate_limit_per_minute:
                    logger.warning(f"Webhook rate limit exceeded: {count} req/min for contact={contact_id}")
                    return {"status": "throttled", "reason": "rate_limit"}
            except Exception as _rl_err:
                logger.warning(f"Rate limit check failed (allowing through): {_rl_err}")

        # Message deduplication — two-phase:
        # Phase 1: 30s guard before processing (prevents concurrent GHL retries during AI call)
        # Phase 2: 300s guard written on success (prevents replays in GHL's 5-min retry window)
        dedup_key: Optional[str] = None
        if _webhook_cache:
            try:
                dedup_key = f"dedup:{contact_id}:{hashlib.sha256(message_body.encode()).hexdigest()}"
                if await _webhook_cache.get(dedup_key):
                    logger.info(f"Duplicate message skipped: contact={contact_id}")
                    return {"status": "skipped", "reason": "duplicate"}
                await _webhook_cache.set(dedup_key, "1", ttl=30)
            except Exception as _dd_err:
                logger.warning(f"Dedup check failed (allowing through): {_dd_err}")
                dedup_key = None

        # Per-contact rate limit (10 messages/minute)
        if _webhook_cache:
            try:
                contact_rate_key = f"rate:contact:{contact_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
                contact_count = await _webhook_cache.increment(contact_rate_key, ttl=60)
                if contact_count > 10:
                    logger.warning(f"Per-contact rate limit exceeded for {contact_id}")
                    return {"status": "throttled", "reason": "per_contact_rate_limit"}
            except Exception as _cr_err:
                logger.warning(f"Per-contact rate check failed (allowing through): {_cr_err}")

        # Per-contact processing lock (atomic setnx — C3)
        _lock_acquired = False
        lock_key = f"lock:{contact_id}"
        if _webhook_cache:
            try:
                _lock_acquired = await _webhook_cache.setnx(lock_key, "1", ttl=90)
                if not _lock_acquired:
                    logger.warning(f"Processing lock held for contact={contact_id}, throttling")
                    return {"status": "throttled", "reason": "processing_lock"}
            except Exception as _lk_err:
                logger.warning(f"Lock check failed (allowing through): {_lk_err}")
                _lock_acquired = True  # Treat as acquired to avoid blocking

        try:
            routing = await resolve_mode(
                payload=normalized,
                cache=_webhook_cache,
                ghl_client=state._ghl_client,
            )
            mode = routing.mode
            bot_type_lower = mode_to_assignment(mode) or "lead"
            _bot_type_source = routing.source
            contact_info = dict(normalized.contact_info)

            # Canonical mode cache + compat assignment cache
            if _webhook_cache:
                await _webhook_cache.set(
                    f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}",
                    mode.value,
                    ttl=_ASSIGNED_BOT_TTL,
                )
                assignment = mode_to_assignment(mode)
                if assignment:
                    await _webhook_cache.set(f"assigned_bot:{contact_id}", assignment, ttl=_ASSIGNED_BOT_TTL)
                else:
                    await _webhook_cache.delete(f"assigned_bot:{contact_id}")

            manual_takeover = False
            if state._ghl_client:
                try:
                    contact_snapshot = routing.contact_snapshot or await state._ghl_client.get_contact(contact_id)
                    # _make_request wraps responses as {"success": True, "data": {...}}
                    _inner = contact_snapshot.get("data", contact_snapshot)
                    tags = (
                        _inner.get("tags")
                        or _inner.get("contact", {}).get("tags")
                        or contact_snapshot.get("tags")
                        or contact_snapshot.get("contact", {}).get("tags")
                        or []
                    )
                    if has_jorge_active_tag(tags):
                        manual_takeover = True
                        mode = ConversationMode.HUMAN_HANDOFF
                        bot_type_lower = "lead"
                        contact_info["tags"] = tags
                        if _webhook_cache:
                            await _webhook_cache.set(
                                f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}",
                                ConversationMode.HUMAN_HANDOFF.value,
                                ttl=_ASSIGNED_BOT_TTL,
                            )
                            await _webhook_cache.delete(f"assigned_bot:{contact_id}")
                except Exception as e:
                    logger.warning(f"Could not fetch contact tags for {contact_id}: {e}")

            # Funnel: INTEREST — bot assigned to contact
            try:
                await _funnel_tracker.record_event_async(FunnelEvent(
                    contact_id=contact_id,
                    stage="interest",
                    bot_name=mode.value,
                    timestamp=datetime.now(timezone.utc),
                ))
            except Exception as _e:
                logger.debug(f"Funnel tracker interest event failed: {_e}")

            logger.info(
                f"Unified webhook: contact={contact_id}, mode={mode.value!r}, bot_type={bot_type_lower!r}, "
                f"source={_bot_type_source!r}, msg={message_body[:60]!r}"
            )

            if manual_takeover:
                canonical = build_canonical_conversation(
                    contact_id=contact_id,
                    location_id=location_id,
                    mode=ConversationMode.HUMAN_HANDOFF,
                    current_stage="SUPPRESSED",
                    questions_answered=0,
                    temperature="cold",
                    qualification_complete=False,
                    next_recommended_action="Jorge handling manually",
                    human_takeover=True,
                    handoff_reason=HandoffReason.JORGE_ACTIVE.value,
                    suppressed=True,
                    message_suppression_reason=HandoffReason.JORGE_ACTIVE.value,
                    qualification_summary={},
                    last_inbound_at=datetime.now(timezone.utc).isoformat(),
                )
                try:
                    await upsert_conversation(
                        contact_id=contact_id,
                        bot_type=bot_type_lower,
                        stage="SUPPRESSED",
                        temperature="cold",
                        current_question=0,
                        questions_answered=0,
                        is_qualified=False,
                        conversation_history=None,
                        extracted_data={},
                        last_activity=datetime.now(timezone.utc),
                        conversation_started=datetime.now(timezone.utc),
                        metadata_json={"location_id": location_id, **canonical.to_metadata()},
                        **canonical.to_columns(),
                    )
                except Exception as db_err:
                    logger.warning(f"DB upsert skipped for manual_takeover {contact_id}: {db_err}")
                return {
                    "status": "processed",
                    "bot_type": bot_type_lower,
                    "mode": canonical.mode.value,
                    "conversation_status": canonical.status.value,
                    "handoff_reason": canonical.handoff_reason,
                    "temperature": canonical.temperature,
                    "message_suppression_reason": canonical.message_suppression_reason,
                }

            response_message: Optional[str] = None
            result_meta: Dict = {"bot_type": bot_type_lower, "mode": mode.value}
            deferred_actions: List[Dict[str, Any]] = []
            post_send_actions: List[Dict[str, Any]] = []
            canonical = None

            if mode == ConversationMode.SELLER:
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
                deferred_actions = [a for a in result.actions_taken if a.get("type") in ("add_tag", "remove_tag", "trigger_workflow")]
                post_send_actions = [a for a in result.actions_taken if a.get("type") not in ("add_tag", "remove_tag", "trigger_workflow")]
                if result.qualification_complete:
                    deferred_actions.append({"type": "add_tag", "tag": "jorge-qualified-seller"})
                    temp = result.seller_temperature or "warm"
                    deferred_actions.append({"type": "add_tag", "tag": f"jorge-temp-{temp}"})
                    for stale_temp in ("hot", "warm", "cold"):
                        if stale_temp != temp:
                            deferred_actions.append({"type": "remove_tag", "tag": f"jorge-temp-{stale_temp}"})
                handoff_reason = None
                if any(a.get("tag") == "needs-human-review" for a in result.actions_taken):
                    handoff_reason = HandoffReason.NEEDS_HUMAN_REVIEW.value
                canonical = build_canonical_conversation(
                    contact_id=contact_id,
                    location_id=location_id,
                    mode=ConversationMode.SELLER,
                    current_stage="STALLED" if handoff_reason else ("QUALIFIED" if result.qualification_complete else "ACTIVE"),
                    questions_answered=result.questions_answered,
                    temperature=result.seller_temperature,
                    qualification_complete=result.qualification_complete,
                    next_recommended_action=result.next_steps,
                    handoff_reason=handoff_reason,
                    human_takeover=handoff_reason is not None,
                    qualification_summary=result.analytics,
                    conversation_history=[],
                    last_inbound_at=datetime.now(timezone.utc).isoformat(),
                )
                # Funnel: CONSIDERATION (Q2+), INTENT (qualified), CONVERSION (appointment)
                try:
                    if result.questions_answered >= 2:
                        await _funnel_tracker.record_event_async(FunnelEvent(
                            contact_id=contact_id, stage="consideration",
                            bot_name="seller", timestamp=datetime.now(timezone.utc),
                        ))
                    if result.qualification_complete:
                        await _funnel_tracker.record_event_async(FunnelEvent(
                            contact_id=contact_id, stage="intent",
                            bot_name="seller", timestamp=datetime.now(timezone.utc),
                        ))
                    if "Appointment booked" in (result.next_steps or ""):
                        await _funnel_tracker.record_event_async(FunnelEvent(
                            contact_id=contact_id, stage="purchase",
                            bot_name="seller", timestamp=datetime.now(timezone.utc),
                        ))
                except Exception as _e:
                    logger.debug(f"Funnel tracker seller event failed: {_e}")

            elif mode == ConversationMode.BUYER:
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
                deferred_actions = [a for a in result.actions_taken if a.get("type") in ("add_tag", "remove_tag", "trigger_workflow")]
                post_send_actions = [a for a in result.actions_taken if a.get("type") not in ("add_tag", "remove_tag", "trigger_workflow")]
                if result.qualification_complete:
                    deferred_actions.append({"type": "add_tag", "tag": "jorge-qualified-buyer"})
                    temp = result.buyer_temperature or "warm"
                    deferred_actions.append({"type": "add_tag", "tag": f"jorge-temp-{temp}"})
                    for stale_temp in ("hot", "warm", "cold"):
                        if stale_temp != temp:
                            deferred_actions.append({"type": "remove_tag", "tag": f"jorge-temp-{stale_temp}"})
                handoff_reason = None
                if any(a.get("tag") == "needs-human-review" for a in result.actions_taken):
                    handoff_reason = HandoffReason.NEEDS_HUMAN_REVIEW.value
                elif any(a.get("tag") == "needs-bilingual" for a in result.actions_taken):
                    handoff_reason = HandoffReason.NEEDS_BILINGUAL.value
                canonical = build_canonical_conversation(
                    contact_id=contact_id,
                    location_id=location_id,
                    mode=ConversationMode.BUYER,
                    current_stage="STALLED" if handoff_reason == HandoffReason.NEEDS_HUMAN_REVIEW.value else ("QUALIFIED" if result.qualification_complete else "ACTIVE"),
                    questions_answered=result.questions_answered,
                    temperature=result.buyer_temperature,
                    qualification_complete=result.qualification_complete,
                    next_recommended_action=result.next_steps,
                    handoff_reason=handoff_reason,
                    human_takeover=handoff_reason == HandoffReason.NEEDS_HUMAN_REVIEW.value,
                    bilingual_required=handoff_reason == HandoffReason.NEEDS_BILINGUAL.value,
                    qualification_summary=result.analytics,
                    conversation_history=[],
                    last_inbound_at=datetime.now(timezone.utc).isoformat(),
                )
                # Funnel: CONSIDERATION (Q2+), INTENT (qualified), CONVERSION (appointment)
                try:
                    if result.questions_answered >= 2:
                        await _funnel_tracker.record_event_async(FunnelEvent(
                            contact_id=contact_id, stage="consideration",
                            bot_name="buyer", timestamp=datetime.now(timezone.utc),
                        ))
                    if result.qualification_complete:
                        await _funnel_tracker.record_event_async(FunnelEvent(
                            contact_id=contact_id, stage="intent",
                            bot_name="buyer", timestamp=datetime.now(timezone.utc),
                        ))
                except Exception as _e:
                    logger.debug(f"Funnel tracker buyer event failed: {_e}")

            elif mode == ConversationMode.BILINGUAL_HANDOFF:
                response_message = (
                    "Hola! Soy Jorge. Lamentablemente no hablo espanol bien. "
                    "Voy a tener a mi asistente bilingue que se comunique contigo. / "
                    "Hi! I'm Jorge — I'll have my bilingual assistant reach out to you shortly."
                )
                deferred_actions = [{"type": "add_tag", "tag": "needs-bilingual"}]
                canonical = build_canonical_conversation(
                    contact_id=contact_id,
                    location_id=location_id,
                    mode=ConversationMode.BILINGUAL_HANDOFF,
                    current_stage="HANDOFF",
                    questions_answered=0,
                    temperature="cold",
                    qualification_complete=False,
                    next_recommended_action="Route to bilingual assistant",
                    bilingual_required=True,
                    handoff_reason=HandoffReason.NEEDS_BILINGUAL.value,
                    suppressed=True,
                    message_suppression_reason=HandoffReason.NEEDS_BILINGUAL.value,
                    qualification_summary={},
                    conversation_history=[],
                    last_inbound_at=datetime.now(timezone.utc).isoformat(),
                )
                try:
                    await upsert_conversation(
                        contact_id=contact_id,
                        bot_type="lead",
                        stage="HANDOFF",
                        temperature="cold",
                        current_question=0,
                        questions_answered=0,
                        is_qualified=False,
                        conversation_history=None,
                        extracted_data={},
                        last_activity=datetime.now(timezone.utc),
                        conversation_started=datetime.now(timezone.utc),
                        metadata_json={"location_id": location_id, **canonical.to_metadata()},
                        **canonical.to_columns(),
                    )
                except Exception as db_err:
                    logger.warning(f"DB upsert skipped for bilingual_handoff {contact_id}: {db_err}")
                if _webhook_cache:
                    await _webhook_cache.set(
                        f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}",
                        ConversationMode.HUMAN_HANDOFF.value,
                        ttl=_ASSIGNED_BOT_TTL,
                    )
                    await _webhook_cache.delete(f"assigned_bot:{contact_id}")
                result_meta.update({"temperature": "cold", "questions_answered": 0, "qualification_complete": False})
            elif mode == ConversationMode.HUMAN_HANDOFF:
                canonical = build_canonical_conversation(
                    contact_id=contact_id,
                    location_id=location_id,
                    mode=ConversationMode.HUMAN_HANDOFF,
                    current_stage="SUPPRESSED",
                    questions_answered=0,
                    temperature="cold",
                    qualification_complete=False,
                    next_recommended_action="Await Jorge follow-up",
                    human_takeover=True,
                    handoff_reason=routing.handoff_reason or HandoffReason.MANUAL_OVERRIDE.value,
                    suppressed=True,
                    message_suppression_reason=routing.handoff_reason or HandoffReason.MANUAL_OVERRIDE.value,
                    qualification_summary={},
                    conversation_history=[],
                    last_inbound_at=datetime.now(timezone.utc).isoformat(),
                )
                try:
                    await upsert_conversation(
                        contact_id=contact_id,
                        bot_type=bot_type_lower,
                        stage="SUPPRESSED",
                        temperature="cold",
                        current_question=0,
                        questions_answered=0,
                        is_qualified=False,
                        conversation_history=None,
                        extracted_data={},
                        last_activity=datetime.now(timezone.utc),
                        conversation_started=datetime.now(timezone.utc),
                        metadata_json={"location_id": location_id, **canonical.to_metadata()},
                        **canonical.to_columns(),
                    )
                except Exception as db_err:
                    logger.warning(f"DB upsert skipped for human_handoff {contact_id}: {db_err}")
                result_meta.update(
                    {
                        "temperature": canonical.temperature,
                        "questions_answered": 0,
                        "qualification_complete": False,
                        "conversation_status": canonical.status.value,
                        "handoff_reason": canonical.handoff_reason,
                        "message_suppression_reason": canonical.message_suppression_reason,
                    }
                )
                if _webhook_cache and dedup_key:
                    await _webhook_cache.set(dedup_key, "1", ttl=300)
                return {"status": "processed", **result_meta}
            else:
                lead_data = {"id": contact_id, "message": message_body, **contact_info}
                analysis, metrics = await state.lead_analyzer.analyze_lead(lead_data)
                canonical = build_canonical_conversation(
                    contact_id=contact_id,
                    location_id=location_id,
                    mode=ConversationMode.LEAD_INTAKE,
                    current_stage="Q0",
                    questions_answered=0,
                    temperature=analysis.get("temperature", "warm"),
                    qualification_complete=False,
                    next_recommended_action=analysis.get("recommended_action", "Continue intake qualification"),
                    handoff_reason=routing.handoff_reason,
                    qualification_summary=analysis,
                    conversation_history=[],
                    last_inbound_at=datetime.now(timezone.utc).isoformat(),
                )
                try:
                    await upsert_conversation(
                        contact_id=contact_id,
                        bot_type="lead",
                        stage="Q0",
                        temperature=analysis.get("temperature", "warm"),
                        current_question=0,
                        questions_answered=0,
                        is_qualified=False,
                        conversation_history=[],
                        extracted_data=analysis,
                        last_activity=datetime.now(timezone.utc),
                        conversation_started=datetime.now(timezone.utc),
                        metadata_json={"location_id": location_id, **canonical.to_metadata()},
                        **canonical.to_columns(),
                    )
                except Exception as db_err:
                    logger.warning(f"DB upsert skipped for lead_intake {contact_id}: {db_err}")
                result_meta.update(
                    {
                        "score": analysis.get("score", 0),
                        "temperature": analysis.get("temperature", "warm"),
                        "jorge_priority": analysis.get("jorge_priority", "normal"),
                        "conversation_status": canonical.status.value,
                        "handoff_reason": canonical.handoff_reason,
                        "message_suppression_reason": canonical.message_suppression_reason,
                    }
                )
                if _webhook_cache and dedup_key:
                    await _webhook_cache.set(dedup_key, "1", ttl=300)
                return {"status": "processed", **result_meta}

            # Send reply via GHL SMS (seller / buyer bots)
            response_message = sanitize_bot_response(response_message, bot_type=bot_type_lower)
            if response_message and state._ghl_client:
                try:
                    await state._ghl_client.send_message(contact_id, response_message, "SMS")
                    logger.info(f"Reply sent to {contact_id} via GHL SMS")
                    if canonical:
                        canonical.last_outbound_at = datetime.now(timezone.utc).isoformat()
                except Exception as e:
                    logger.error(f"Failed to send GHL reply to {contact_id}: {e}")

            if state._ghl_client and post_send_actions:
                await _apply_post_send_updates(state._ghl_client, contact_id, post_send_actions)
            if state._ghl_client and deferred_actions:
                background_tasks.add_task(_deferred_tag_apply, state._ghl_client, contact_id, deferred_actions)
            if canonical:
                try:
                    if mode in (ConversationMode.SELLER, ConversationMode.BUYER):
                        # Bot is the authoritative DB writer for seller/buyer state.
                        # Only update last_outbound_at — don't overwrite bot's granular stage.
                        await update_conversation_outbound_at(
                            contact_id, bot_type_lower, canonical.last_outbound_at
                        )
                    else:
                        # Bilingual: bot already called upsert; merge is idempotent here.
                        await merge_conversation_metadata(contact_id, bot_type_lower, canonical.to_metadata())
                except Exception as e:
                    logger.warning(f"Could not persist canonical state for {contact_id}: {e}")
                try:
                    if state._ghl_client:
                        summary_value = json.dumps(canonical.qualification_summary)[:255]
                        await _apply_post_send_updates(
                            state._ghl_client,
                            contact_id,
                            [
                                {"type": "update_custom_field", "field": "ai_mode", "value": canonical.mode.value},
                                {"type": "update_custom_field", "field": "ai_status", "value": canonical.status.value},
                                {"type": "update_custom_field", "field": "ai_temperature", "value": canonical.temperature or ""},
                                {"type": "update_custom_field", "field": "ai_last_summary", "value": summary_value},
                                {"type": "update_custom_field", "field": "ai_last_handoff_reason", "value": canonical.handoff_reason or ""},
                                {"type": "update_custom_field", "field": "ai_last_response_at", "value": canonical.last_outbound_at or ""},
                            ],
                        )
                except Exception as e:
                    logger.warning(f"Could not sync canonical custom fields for {contact_id}: {e}")
                result_meta.update(
                    {
                        "conversation_status": canonical.status.value,
                        "handoff_reason": canonical.handoff_reason,
                        "message_suppression_reason": canonical.message_suppression_reason,
                    }
                )
            if _webhook_cache and dedup_key:
                await _webhook_cache.set(dedup_key, "1", ttl=300)
            return {"status": "processed", **result_meta}

        finally:
            if _lock_acquired and _webhook_cache:
                await _webhook_cache.delete(lock_key)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified webhook unhandled error: {e}", exc_info=True)
        return {"status": "error", "detail": "internal server error"}


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
