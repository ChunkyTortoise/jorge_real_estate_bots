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
from bots.shared.logger import get_logger

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

    Overwrites the assigned_bot Redis key so the next inbound message
    is routed to the new bot immediately.
    """
    from bots.lead_bot import main as _m

    body = await request.json()
    contact_id: str = body.get("contact_id", "").strip()
    new_bot_type: str = body.get("bot_type", "").strip().lower()

    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id is required")
    if new_bot_type not in ("seller", "buyer", "lead"):
        raise HTTPException(status_code=400, detail="bot_type must be 'seller', 'buyer', or 'lead'")

    cache = _m._webhook_cache
    if cache:
        await cache.delete(f"assigned_bot:{contact_id}")
        await cache.set(f"assigned_bot:{contact_id}", new_bot_type, ttl=604_800)

    logger.info(f"Admin: reassigned contact {contact_id!r} to bot '{new_bot_type}'")
    return {"status": "ok", "contact_id": contact_id, "bot_type": new_bot_type}


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

    logger.info(f"Admin: reset {bot} bot state for contact {contact_id!r}")
    return {"status": "ok", "bot": bot, "contact_id": contact_id}
