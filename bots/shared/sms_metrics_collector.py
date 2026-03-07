"""
SMS Delivery Metrics Collector

Redis-backed, 7-day rolling window SMS delivery tracking.
Records delivery/failed/read events per contact and computes
aggregate delivery stats for alerting and dashboard display.

Usage:
    collector = SmsMetricsCollector()
    await collector.record_delivery(contact_id, "delivered", datetime.now(timezone.utc))
    stats = await collector.get_delivery_stats()
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from bots.shared.cache_service import CacheService

logger = logging.getLogger(__name__)

VALID_STATUSES = frozenset({"delivered", "failed", "read"})
_TTL_7_DAYS = 7 * 24 * 60 * 60  # 604800 seconds


class SmsMetricsCollector:
    """Redis-backed SMS delivery metrics with 7-day rolling window.

    Uses CacheService sorted-set-like storage via simple key/value pairs.
    Each delivery event is stored as a timestamped entry in a list keyed
    by status, enabling efficient aggregation and per-contact timeline.
    """

    _KEY_PREFIX = "sms_metrics"

    def __init__(self) -> None:
        self._cache = CacheService()

    async def record_delivery(
        self,
        contact_id: str,
        status: str,
        timestamp: datetime,
    ) -> None:
        """Record an SMS delivery event.

        Args:
            contact_id: GHL contact ID.
            status: One of "delivered", "failed", "read".
            timestamp: When the event occurred.

        Raises:
            ValueError: If status is not recognized.
        """
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
            )

        ts_iso = timestamp.isoformat()
        entry = json.dumps({
            "contact_id": contact_id,
            "status": status,
            "timestamp": ts_iso,
        })

        # Global counter per status
        counter_key = f"{self._KEY_PREFIX}:count:{status}"
        current = await self._cache.get(counter_key)
        count = int(current) if current is not None else 0
        await self._cache.set(counter_key, count + 1, ttl=_TTL_7_DAYS)

        # Per-contact timeline (append to list stored as JSON array)
        timeline_key = f"{self._KEY_PREFIX}:timeline:{contact_id}"
        raw = await self._cache.get(timeline_key)
        timeline: List[Dict[str, Any]] = json.loads(raw) if raw else []
        timeline.append({
            "status": status,
            "timestamp": ts_iso,
            "contact_id": contact_id,
        })
        await self._cache.set(timeline_key, json.dumps(timeline), ttl=_TTL_7_DAYS)

        # Global events list (capped at 1000)
        events_key = f"{self._KEY_PREFIX}:events"
        raw_events = await self._cache.get(events_key)
        events: List[str] = json.loads(raw_events) if raw_events else []
        events.append(entry)
        if len(events) > 1000:
            events = events[-1000:]
        await self._cache.set(events_key, json.dumps(events), ttl=_TTL_7_DAYS)

        logger.debug(
            "SMS metric recorded: contact=%s status=%s ts=%s",
            contact_id, status, ts_iso,
        )

    async def get_delivery_stats(self) -> Dict[str, Any]:
        """Get aggregate delivery statistics.

        Returns:
            Dict with delivered, failed, read counts and delivery_rate.
        """
        delivered = await self._get_count("delivered")
        failed = await self._get_count("failed")
        read = await self._get_count("read")

        total = delivered + failed
        delivery_rate = round(delivered / total, 4) if total > 0 else 0.0

        return {
            "delivered": delivered,
            "failed": failed,
            "read": read,
            "delivery_rate": delivery_rate,
        }

    async def get_per_contact_timeline(
        self, contact_id: str
    ) -> List[Dict[str, str]]:
        """Get delivery event timeline for a specific contact.

        Args:
            contact_id: GHL contact ID.

        Returns:
            List of dicts with status, timestamp, contact_id.
        """
        timeline_key = f"{self._KEY_PREFIX}:timeline:{contact_id}"
        raw = await self._cache.get(timeline_key)
        if not raw:
            return []
        timeline: List[Dict[str, str]] = json.loads(raw)
        return timeline

    async def _get_count(self, status: str) -> int:
        """Get the current count for a status."""
        counter_key = f"{self._KEY_PREFIX}:count:{status}"
        raw = await self._cache.get(counter_key)
        return int(raw) if raw is not None else 0
