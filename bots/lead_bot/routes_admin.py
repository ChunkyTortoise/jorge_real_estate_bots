"""Admin settings routes for Lead Bot — bot tone configuration."""
from __future__ import annotations

import hmac

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bots.shared.auth_middleware import auth_middleware
from bots.shared.bot_settings import (
    get_all_overrides as _settings_get_all,
    get_override as _get_override,
    update_settings as _settings_update,
    KNOWN_BOTS as _known_bots,
)
from bots.shared.config import settings
from bots.shared.conversation_contract import (
    CONVERSATION_MODE_CACHE_PREFIX,
    extract_canonical_view,
    mode_to_assignment,
    normalize_conversation_mode,
)
from bots.shared.logger import get_logger
from database.models import ConversationModel
from database.session import AsyncSessionFactory
from sqlalchemy import select, text as _text

logger = get_logger(__name__)

router = APIRouter()

_SETTINGS_CACHE_KEY = "admin:bot_settings"
_SETTINGS_CACHE_TTL = 7_776_000  # 90 days

_security = HTTPBearer(auto_error=False)


async def get_admin_or_apikey(
    x_admin_key: Optional[str] = Header(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    """Accept either X-Admin-Key header or valid JWT Bearer token."""
    if x_admin_key is not None:
        if not settings.admin_api_key:
            raise HTTPException(status_code=503, detail="Admin API key not configured")
        if hmac.compare_digest(x_admin_key, settings.admin_api_key):
            return
        raise HTTPException(status_code=403, detail="Invalid admin key")
    # No API key supplied — fall back to JWT Bearer
    await auth_middleware.get_admin_user(credentials)


async def settings_load(cache) -> None:
    """Restore bot settings overrides from cache on startup."""
    try:
        data = await cache.get(_SETTINGS_CACHE_KEY)
        if data:
            for bot, overrides in data.items():
                if overrides:
                    _settings_update(bot, overrides)
            restored = [b for b, v in data.items() if v]
            logger.info(f"Restored bot settings from cache: {restored}")
    except Exception as e:
        logger.warning(f"Could not restore bot settings from cache: {e}")


async def settings_save(cache) -> None:
    """Persist all bot settings overrides to cache."""
    try:
        await cache.set(_SETTINGS_CACHE_KEY, _settings_get_all(), ttl=_SETTINGS_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Could not persist bot settings to cache: {e}")


@router.get("/admin/settings")
async def admin_get_settings(_=Depends(get_admin_or_apikey)):
    """Return current effective settings -- bot defaults merged with any live overrides."""
    from bots.seller_bot.jorge_seller_bot import SELLER_SYSTEM_PROMPT, JorgeSellerBot
    from bots.buyer_bot.buyer_prompts import BUYER_SYSTEM_PROMPT, BUYER_QUESTIONS, JORGE_BUYER_PHRASES

    seller_override = _get_override("seller")
    buyer_override = _get_override("buyer")
    lead_override = _get_override("lead")
    return {
        "seller": {
            "system_prompt": seller_override.get("system_prompt", SELLER_SYSTEM_PROMPT),
            "jorge_phrases": seller_override.get("jorge_phrases", JorgeSellerBot.JORGE_PHRASES),
            "questions": {
                str(k): seller_override.get("questions", {}).get(str(k), v)
                for k, v in JorgeSellerBot.QUALIFICATION_QUESTIONS.items()
            },
        },
        "buyer": {
            "system_prompt": buyer_override.get("system_prompt", BUYER_SYSTEM_PROMPT),
            "jorge_phrases": buyer_override.get("jorge_phrases", JORGE_BUYER_PHRASES),
            "questions": {
                str(k): buyer_override.get("questions", {}).get(str(k), v)
                for k, v in BUYER_QUESTIONS.items()
            },
        },
        "lead": {
            "min_price": lead_override.get("min_price", settings.jorge_min_price),
            "max_price": lead_override.get("max_price", settings.jorge_max_price),
            "service_areas": lead_override.get("service_areas", settings.jorge_service_areas),
            "preferred_timeline": lead_override.get("preferred_timeline", settings.jorge_preferred_timeline),
            "standard_commission": lead_override.get("standard_commission", settings.jorge_standard_commission),
            "minimum_commission": lead_override.get("minimum_commission", settings.jorge_minimum_commission),
        },
    }


@router.post("/admin/reassign-bot")
async def admin_reassign_bot(request: Request, _=Depends(get_admin_or_apikey)):
    """
    Reassign a contact to a different bot type.

    Body: {"contact_id": "...", "bot_type": "seller" | "buyer" | "lead"}
       or {"contact_id": "...", "mode": "seller" | "buyer" | "lead_intake" |
                                  "bilingual_handoff" | "human_handoff"}

    Overwrites the canonical conversation:mode Redis key so the next inbound message
    is routed to the new bot immediately.
    """
    from bots.lead_bot import main as _m

    body = await request.json()
    contact_id: str = body.get("contact_id", "").strip()
    raw_mode = body.get("mode") or body.get("bot_type") or ""
    mode = normalize_conversation_mode(raw_mode)
    new_bot_type = mode_to_assignment(mode)

    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id is required")
    if not body.get("mode") and not body.get("bot_type"):
        raise HTTPException(status_code=400, detail="mode or bot_type is required")

    cache = _m._webhook_cache
    if cache:
        await cache.set(f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}", mode.value, ttl=604_800)

    # Sync new mode to DB (targeted — preserves stage/temperature)
    try:
        from database.repository import update_conversation_mode
        await update_conversation_mode(contact_id, mode.value, new_bot_type or "lead")
    except Exception as e:
        logger.warning(f"Admin: DB sync for reassign failed: {e}")

    # Sync new mode to GHL (best-effort)
    try:
        from bots.lead_bot import main as _m
        ghl_client = getattr(_m, "_ghl_client", None) or getattr(_m, "state", None) and getattr(_m.state, "_ghl_client", None)
        if ghl_client:
            await ghl_client.update_custom_field(contact_id, "ai_mode", mode.value)
    except Exception as e:
        logger.warning(f"Admin: GHL sync for reassign failed: {e}")

    logger.info(f"Admin: reassigned contact {contact_id!r} to mode '{mode.value}'")
    return {"status": "ok", "contact_id": contact_id, "bot_type": new_bot_type, "mode": mode.value}


@router.put("/admin/settings/{bot}")
async def admin_update_settings(bot: str, request: Request, _=Depends(get_admin_or_apikey)):
    """
    Update tone settings for a bot (seller | buyer | lead).

    Body: partial settings dict -- only supplied keys are overridden.
    """
    from bots.lead_bot import main as _m

    if bot not in _known_bots:
        raise HTTPException(status_code=404, detail=f"Unknown bot: {bot}. Valid: {sorted(_known_bots)}")
    body = await request.json()
    _settings_update(bot, body)
    await settings_save(_m._webhook_cache)
    logger.info(f"Admin: updated {bot} settings -- keys: {list(body)}")
    return {"status": "ok", "bot": bot, "updated_keys": list(body)}


@router.delete("/admin/reset-state/{bot}/{contact_id}")
async def admin_reset_state(bot: str, contact_id: str, _=Depends(get_admin_or_apikey)):
    """
    Clear Redis conversation state for a contact so the bot starts fresh.

    Clears: seller:state:{contact_id} or buyer:state:{contact_id}
    """
    from bots.lead_bot import main as _m

    if bot not in ("seller", "buyer"):
        raise HTTPException(status_code=400, detail="bot must be 'seller' or 'buyer'")

    cache = _m._webhook_cache
    if cache:
        await cache.delete(f"{bot}:state:{contact_id}")
        await cache.delete(f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}")

    logger.info(f"Admin: reset {bot} bot state for contact {contact_id!r}")
    return {"status": "ok", "bot": bot, "contact_id": contact_id}


@router.get("/admin/conversations/{contact_id}")
async def admin_get_conversation(contact_id: str, _=Depends(get_admin_or_apikey)):
    """Return canonical conversation mode/state summary for a contact."""
    from bots.lead_bot import main as _m

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(ConversationModel).where(ConversationModel.contact_id == contact_id)
        )
        conversations = result.scalars().all()

    if not conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversations.sort(key=lambda c: c.updated_at or c.created_at, reverse=True)
    latest = conversations[0]
    canonical = extract_canonical_view(latest)
    cache = _m._webhook_cache
    canonical_cache_mode = None
    if cache:
        try:
            canonical_cache_mode = await cache.get(f"{CONVERSATION_MODE_CACHE_PREFIX}{contact_id}")
        except Exception:
            canonical_cache_mode = None
    return {
        "contact_id": contact_id,
        "mode": canonical["mode"],
        "mode_version": canonical["mode_version"],
        "status": canonical["status"],
        "handoff_reason": canonical.get("handoff_reason"),
        "human_takeover": canonical["human_takeover"],
        "bilingual_required": canonical["bilingual_required"],
        "message_suppression_reason": canonical.get("message_suppression_reason"),
        "qualification_summary": canonical.get("qualification_summary"),
        "next_recommended_action": canonical.get("next_recommended_action"),
        "crm_sync_status": canonical.get("crm_sync_status"),
        "last_inbound_at": canonical.get("last_inbound_at"),
        "last_outbound_at": canonical.get("last_outbound_at"),
        "temperature": canonical.get("temperature"),
        "canonical_cache_mode": canonical_cache_mode,
        "latest_bot_type": latest.bot_type,
        "latest_stage": latest.stage,
        "questions_answered": latest.questions_answered,
    }


@router.get("/admin/calendar-debug")
async def admin_calendar_debug(_=Depends(get_admin_or_apikey)):
    """
    Diagnose GHL calendar integration.

    Tests read access (get_free_slots) and write access (create_appointment),
    surfaces exact errors, and auto-cancels any test appointment created.
    """
    from bots.shared.config import settings as cfg
    from bots.shared.ghl_client import GHLClient

    result: dict = {
        "calendar_id": cfg.jorge_calendar_id or "(not set)",
        "user_id": cfg.jorge_user_id or "(not set)",
        "read_ok": False,
        "write_ok": False,
        "slots_found": 0,
        "read_error": None,
        "write_error": None,
        "appointment_id": None,
    }

    if not cfg.jorge_calendar_id:
        result["read_error"] = "JORGE_CALENDAR_ID env var is not set"
        return result

    client = GHLClient()

    # -- Read test --
    try:
        slots = await client.get_free_slots(cfg.jorge_calendar_id)
        result["read_ok"] = True
        result["slots_found"] = len(slots)
    except Exception as exc:
        result["read_error"] = str(exc)
        return result

    # -- Write test (requires at least one slot) --
    if not slots:
        result["write_error"] = "No slots returned — cannot test write access"
        return result

    slot = slots[0]
    start_time = slot.get("start", "")
    end_time = slot.get("end", start_time)
    test_payload = {
        "calendarId": cfg.jorge_calendar_id,
        "locationId": client.location_id,
        "contactId": "test-calendar-debug",
        "startTime": start_time,
        "endTime": end_time,
        "title": "DEBUG TEST — auto-cancel",
        "appointmentStatus": "new",
        "selectedTimezone": "America/Los_Angeles",
        "selectedSlot": start_time,
    }
    if cfg.jorge_user_id:
        test_payload["assignedUserId"] = cfg.jorge_user_id

    try:
        appt_result = await client.create_appointment(test_payload)
        if appt_result.get("success"):
            result["write_ok"] = True
            appt = appt_result.get("data") or appt_result.get("appointment") or {}
            appt_id = str(appt.get("id") or appt.get("appointmentId") or "")
            result["appointment_id"] = appt_id
            # Auto-cancel
            if appt_id and hasattr(client, "delete_appointment"):
                try:
                    await client.delete_appointment(appt_id)
                    result["appointment_id"] = f"{appt_id} (deleted)"
                except Exception:
                    result["appointment_id"] = f"{appt_id} (delete failed — cancel manually)"
        else:
            result["write_error"] = appt_result
    except Exception as exc:
        result["write_error"] = str(exc)

    return result


@router.get("/health/schema-check")
async def schema_check(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    """Check that required DB tables and columns exist."""
    if not x_admin_key or not hmac.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")

    required_tables = [
        "contacts", "conversations", "leads", "deals", "commissions",
        "properties", "buyer_preferences", "playbook_applications", "roi_reports",
    ]
    results = {}
    try:
        async with AsyncSessionFactory() as session:
            for table in required_tables:
                row = await session.execute(
                    _text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :t"),
                    {"t": table},
                )
                exists = row.scalar() > 0
                results[table] = {"exists": exists}
    except Exception as e:
        return {"status": "error", "detail": str(e), "tables": results}

    all_ok = all(v["exists"] for v in results.values())
    return {"status": "ok" if all_ok else "degraded", "tables": results}


# ---------------------------------------------------------------------------
# Seller bot admin actions (ported from standalone bots/seller_bot/main.py)
# ---------------------------------------------------------------------------

def _seller_next_stage(current: str) -> str:
    progression = {"Q0": "Q1", "Q1": "Q2", "Q2": "Q3", "Q3": "Q4", "Q4": "QUALIFIED"}
    return progression.get(current, current)


@router.post("/admin/seller/trigger-cma")
async def admin_trigger_cma(
    request: Request,
    _=Depends(get_admin_or_apikey),
):
    """Trigger CMA generation for a contact (dashboard action)."""
    body = await request.json()
    contact_id = body.get("contact_id")
    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id required")
    from bots.lead_bot import main as _m
    state = await _m.seller_bot_instance.get_conversation_state(contact_id)
    if not state:
        raise HTTPException(status_code=404, detail="Contact not found in seller bot")
    from bots.shared.ghl_client import GHLClient
    ghl = GHLClient()
    await ghl.add_tag(contact_id, "cma_requested")
    logger.info(f"CMA triggered for contact {contact_id}")
    return {"status": "ok", "contact_id": contact_id, "action": "cma_requested"}


@router.post("/admin/seller/{contact_id}/advance-stage")
async def admin_advance_stage(
    contact_id: str,
    request: Request,
    _=Depends(get_admin_or_apikey),
):
    """Advance a contact's seller bot conversation stage (dashboard action)."""
    body = await request.json()
    from bots.lead_bot import main as _m
    state = await _m.seller_bot_instance.get_conversation_state(contact_id)
    if not state:
        raise HTTPException(status_code=404, detail="Contact not found in seller bot")
    stage_order = ["Q0", "Q1", "Q2", "Q3", "Q4", "QUALIFIED"]
    target = body.get("stage") or _seller_next_stage(state.stage)
    if target not in stage_order:
        raise HTTPException(status_code=400, detail=f"Invalid stage: {target}")
    state.stage = target
    await _m.seller_bot_instance.save_conversation_state(contact_id, state)
    logger.info(f"Stage advanced to {target} for contact {contact_id}")
    return {"status": "ok", "contact_id": contact_id, "stage": target}
