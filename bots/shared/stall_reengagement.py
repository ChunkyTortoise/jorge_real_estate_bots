"""Stall re-engagement -- sends contextual follow-up SMS when a conversation goes STALLED."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from bots.shared.config import settings
from bots.shared.event_models import DecisionEvent
from bots.shared.ghl_client import GHLClient
from bots.shared.logger import get_logger

logger = get_logger(__name__)

_MESSAGES = {
    "Q0": "Hey {name}, just checking in -- still thinking about your home situation?",
    "Q1": "Hey {name}, just checking in -- still thinking about your home situation?",
    "Q2": "Hey {name}, wanted to follow up on our conversation about your property.",
    "Q3": "Hey {name}, wanted to follow up on our conversation about your property at {address}.",
    "Q4": "Hey {name}, I know we were discussing an offer timeline. Want to pick back up?",
}


class StallReengagementService:
    """Sends contextual follow-up SMS when a conversation goes STALLED.

    Tracks per-contact attempt counts and cooldown windows in Redis.
    """

    MAX_ATTEMPTS = 2
    MIN_HOURS_BETWEEN = 48

    def __init__(self, redis_client: Optional[object] = None, ghl_client: Optional[GHLClient] = None) -> None:
        if redis_client is not None:
            self._redis = redis_client
        else:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._ghl = ghl_client or GHLClient()

    def _redis_key(self, contact_id: str) -> str:
        return f"stall_reengagement:{contact_id}"

    async def trigger_reengagement(
        self,
        contact_id: str,
        stage: str,
        name: str,
        location_id: str,
        address: str = "",
    ) -> bool:
        """Send re-engagement SMS if under attempt limit and enough time has passed."""
        key = self._redis_key(contact_id)
        raw = await self._redis.get(key)
        data = json.loads(raw) if raw else {"attempts": 0, "last_sent": None}

        if await self.is_opted_out(contact_id):
            logger.info("Re-engagement skipped — opted out: %s", contact_id)
            return False

        if data["attempts"] >= self.MAX_ATTEMPTS:
            logger.info("Re-engagement limit reached for %s", contact_id)
            return False

        if data["last_sent"]:
            last = datetime.fromisoformat(data["last_sent"])
            if (datetime.now(timezone.utc) - last) < timedelta(hours=self.MIN_HOURS_BETWEEN):
                logger.info("Too soon for re-engagement for %s", contact_id)
                return False

        # Choose message template based on stage
        stage_key = stage if stage in _MESSAGES else "Q0"
        message = _MESSAGES[stage_key].format(name=name, address=address or "your property")

        try:
            await self._ghl.send_message(
                contact_id=contact_id,
                message=message,
                message_type="SMS",
            )
            data["attempts"] += 1
            data["last_sent"] = datetime.now(timezone.utc).isoformat()
            await self._redis.set(key, json.dumps(data), ex=86400 * 30)  # 30 days TTL
            event = DecisionEvent(
                event_type="stall_reengagement",
                contact_id=contact_id,
                decision="reengagement_sent",
                reason=f"stalled at stage {stage}, attempt {data['attempts']}",
            )
            logger.info("decision_event", extra={"decision_event": asdict(event)})
            logger.info("Sent re-engagement SMS to %s (attempt %d)", contact_id, data["attempts"])
            return True
        except Exception as e:
            logger.error("Failed to send re-engagement SMS to %s: %s", contact_id, e)
            return False

    _OPT_OUT_KEYWORDS = frozenset({"stop", "unsubscribe", "opt out", "optout", "cancel", "quit", "end"})

    async def record_opt_out(self, contact_id: str) -> None:
        """Mark a contact as opted out of re-engagement messages."""
        key = f"stall_optout:{contact_id}"
        await self._redis.set(key, "1", ex=86400 * 365)
        logger.info("Stall re-engagement opt-out recorded for %s", contact_id)

    async def is_opted_out(self, contact_id: str) -> bool:
        """Return True if the contact has opted out of re-engagement."""
        key = f"stall_optout:{contact_id}"
        val = await self._redis.get(key)
        return val in ("1", b"1")

    def is_opt_out_message(self, text: str) -> bool:
        """Return True if the message text is an opt-out request.

        Checks exact match first, then word-boundary match for TCPA compliance
        (e.g. "STOP please", "please stop texting me" all trigger opt-out).
        """
        normalized = text.strip().lower()
        # Exact match (single keyword only)
        if normalized in self._OPT_OUT_KEYWORDS:
            return True
        # Word-boundary match for standalone opt-out words (TCPA requirement)
        words = set(normalized.split())
        return bool(words & {"stop", "unsubscribe", "cancel", "quit", "end"})

    async def record_reply(self, contact_id: str) -> None:
        """Record that a stalled contact replied (for success rate tracking)."""
        key = f"stall_reply:{contact_id}"
        await self._redis.set(key, "1", ex=86400 * 7)

    async def get_stats(self) -> dict:
        """Get re-engagement success stats."""
        keys = []
        async for k in self._redis.scan_iter(match="stall_reengagement:*", count=100):
            keys.append(k)
        total_attempts = 0
        for k in keys:
            raw = await self._redis.get(k)
            if raw:
                d = json.loads(raw)
                total_attempts += d.get("attempts", 0)
        reply_keys = []
        async for k in self._redis.scan_iter(match="stall_reply:*", count=100):
            reply_keys.append(k)
        optout_keys = []
        async for k in self._redis.scan_iter(match="stall_optout:*", count=100):
            optout_keys.append(k)
        return {
            "total_contacts_reached": len(keys),
            "total_attempts": total_attempts,
            "replies": len(reply_keys),
            "reply_rate": len(reply_keys) / len(keys) if keys else 0.0,
            "opted_out": len(optout_keys),
        }
