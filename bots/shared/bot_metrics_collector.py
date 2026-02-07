"""
Jorge Bot Metrics Collector

Collects and aggregates operational metrics from bot interactions and
handoff events. Designed to be called inline from bot workflows with
minimal overhead. Accumulated metrics can be pushed to the AlertingService
for threshold evaluation.

Usage:
    collector = BotMetricsCollector()
    collector.record_bot_interaction("lead", duration_ms=450.0, success=True, cache_hit=True)
    collector.record_handoff("lead", "buyer", success=True, duration_ms=120.0)
    summary = collector.get_bot_summary("lead")
    collector.feed_to_alerting(alerting_service)
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_BOT_TYPES = frozenset({"lead", "buyer", "seller"})


@dataclass
class _BotInteraction:
    """A single bot interaction record."""

    bot_type: str
    duration_ms: float
    success: bool
    cache_hit: bool
    timestamp: float


@dataclass
class _HandoffRecord:
    """A single handoff event record."""

    source: str
    target: str
    success: bool
    duration_ms: float
    timestamp: float


class BotMetricsCollector:
    """Collects and aggregates bot operational metrics.

    Thread-safe, in-memory metrics collection that can feed aggregated
    values into the AlertingService for rule evaluation.
    """

    # ── Singleton ─────────────────────────────────────────────────────
    _instance: Optional["BotMetricsCollector"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "BotMetricsCollector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._interactions: List[_BotInteraction] = []
        self._handoffs: List[_HandoffRecord] = []
        self._data_lock = threading.Lock()
        self._initialized = True
        logger.info("BotMetricsCollector initialized")

    # ── Recording ─────────────────────────────────────────────────────

    def record_bot_interaction(
        self,
        bot_type: str,
        duration_ms: float,
        success: bool,
        cache_hit: bool = False,
    ) -> None:
        """Record a single bot interaction.

        Args:
            bot_type: One of "lead", "buyer", "seller".
            duration_ms: Response time in milliseconds.
            success: Whether the interaction completed without error.
            cache_hit: Whether a cache hit contributed to the response.

        Raises:
            ValueError: If bot_type is not recognized.
        """
        if bot_type not in VALID_BOT_TYPES:
            raise ValueError(
                f"Invalid bot_type '{bot_type}'. "
                f"Must be one of: {sorted(VALID_BOT_TYPES)}"
            )

        interaction = _BotInteraction(
            bot_type=bot_type,
            duration_ms=duration_ms,
            success=success,
            cache_hit=cache_hit,
            timestamp=time.time(),
        )

        with self._data_lock:
            self._interactions.append(interaction)

        logger.debug(
            "Recorded %s bot interaction: %sms, success=%s, cache_hit=%s",
            bot_type, duration_ms, success, cache_hit,
        )

    def record_handoff(
        self,
        source: str,
        target: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record a cross-bot handoff event.

        Args:
            source: Source bot type (e.g. "lead").
            target: Target bot type (e.g. "buyer").
            success: Whether the handoff completed successfully.
            duration_ms: Handoff latency in milliseconds.
        """
        record = _HandoffRecord(
            source=source,
            target=target,
            success=success,
            duration_ms=duration_ms,
            timestamp=time.time(),
        )

        with self._data_lock:
            self._handoffs.append(record)

        logger.debug(
            "Recorded handoff %s->%s: %sms, success=%s",
            source, target, duration_ms, success,
        )

    # ── Summaries ─────────────────────────────────────────────────────

    def get_bot_summary(
        self, bot_type: str, window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get aggregated metrics for a specific bot type.

        Args:
            bot_type: One of "lead", "buyer", "seller".
            window_minutes: How far back to look (default 60 minutes).

        Returns:
            Dict with total_interactions, success_rate, avg_duration_ms,
            p95_duration_ms, error_rate, and cache_hit_rate.

        Raises:
            ValueError: If bot_type is not recognized.
        """
        if bot_type not in VALID_BOT_TYPES:
            raise ValueError(
                f"Invalid bot_type '{bot_type}'. "
                f"Must be one of: {sorted(VALID_BOT_TYPES)}"
            )

        cutoff = time.time() - (window_minutes * 60)

        with self._data_lock:
            relevant = [
                i for i in self._interactions
                if i.bot_type == bot_type and i.timestamp >= cutoff
            ]

        return self._compute_interaction_summary(relevant)

    def get_system_summary(
        self, window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get aggregated metrics across all bots.

        Args:
            window_minutes: How far back to look (default 60 minutes).

        Returns:
            Dict with per-bot summaries, handoff summary, and overall totals.
        """
        cutoff = time.time() - (window_minutes * 60)

        with self._data_lock:
            all_interactions = [
                i for i in self._interactions
                if i.timestamp >= cutoff
            ]
            all_handoffs = [
                h for h in self._handoffs
                if h.timestamp >= cutoff
            ]

        # Per-bot breakdown
        bots: Dict[str, Dict[str, Any]] = {}
        for bot_type in VALID_BOT_TYPES:
            bot_interactions = [
                i for i in all_interactions
                if i.bot_type == bot_type
            ]
            bots[bot_type] = self._compute_interaction_summary(bot_interactions)

        # Handoff summary
        handoff_total = len(all_handoffs)
        handoff_successes = sum(1 for h in all_handoffs if h.success)
        handoff_durations = [h.duration_ms for h in all_handoffs]

        handoff_summary = {
            "total_handoffs": handoff_total,
            "success_rate": (
                round(handoff_successes / handoff_total, 4)
                if handoff_total > 0 else 0.0
            ),
            "failure_rate": (
                round(1.0 - handoff_successes / handoff_total, 4)
                if handoff_total > 0 else 0.0
            ),
            "avg_duration_ms": (
                round(sum(handoff_durations) / len(handoff_durations), 2)
                if handoff_durations else 0.0
            ),
            "p95_duration_ms": (
                self._percentile(handoff_durations, 95)
                if handoff_durations else 0.0
            ),
        }

        # Overall totals
        overall = self._compute_interaction_summary(all_interactions)

        return {
            "bots": bots,
            "handoffs": handoff_summary,
            "overall": overall,
        }

    # ── Alerting Integration ──────────────────────────────────────────

    def feed_to_alerting(self, alerting_service: Any) -> None:
        """Push current metric aggregates to the AlertingService.

        Computes summary metrics and records them in the alerting service
        so that threshold rules can be evaluated.

        Args:
            alerting_service: An AlertingService instance.
        """
        system = self.get_system_summary()

        # Overall error rate
        overall = system["overall"]
        alerting_service.record_metric("error_rate", overall["error_rate"])

        # Overall cache hit rate
        alerting_service.record_metric("cache_hit_rate", overall["cache_hit_rate"])

        # Per-bot response time p95
        bot_metric_map = {
            "lead": "lead_bot.response_time_p95",
            "buyer": "buyer_bot.response_time_p95",
            "seller": "seller_bot.response_time_p95",
        }
        for bot_type, metric_name in bot_metric_map.items():
            bot_summary = system["bots"].get(bot_type, {})
            p95 = bot_summary.get("p95_duration_ms", 0.0)
            alerting_service.record_metric(metric_name, p95)

        # Handoff metrics
        handoff = system["handoffs"]
        alerting_service.record_metric(
            "handoff.response_time_p95", handoff["p95_duration_ms"]
        )
        alerting_service.record_metric(
            "handoff.failure_rate", handoff["failure_rate"]
        )

        logger.info("Fed %d metrics to AlertingService", 7)

    # ── Internal Helpers ──────────────────────────────────────────────

    @staticmethod
    def _compute_interaction_summary(
        interactions: List[_BotInteraction],
    ) -> Dict[str, Any]:
        """Compute aggregate statistics from a list of interactions.

        Args:
            interactions: List of _BotInteraction records.

        Returns:
            Dict with total_interactions, success_rate, avg_duration_ms,
            p95_duration_ms, error_rate, and cache_hit_rate.
        """
        total = len(interactions)
        if total == 0:
            return {
                "total_interactions": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "p95_duration_ms": 0.0,
                "error_rate": 0.0,
                "cache_hit_rate": 0.0,
            }

        successes = sum(1 for i in interactions if i.success)
        cache_hits = sum(1 for i in interactions if i.cache_hit)
        durations = [i.duration_ms for i in interactions]

        return {
            "total_interactions": total,
            "success_rate": round(successes / total, 4),
            "avg_duration_ms": round(sum(durations) / total, 2),
            "p95_duration_ms": BotMetricsCollector._percentile(durations, 95),
            "error_rate": round(1.0 - successes / total, 4),
            "cache_hit_rate": round(cache_hits / total, 4),
        }

    @staticmethod
    def _percentile(values: List[float], pct: int) -> float:
        """Compute the pct-th percentile of a list of values.

        Uses nearest-rank method.

        Args:
            values: List of numeric values.
            pct: Percentile to compute (0-100).

        Returns:
            The percentile value, or 0.0 if the list is empty.
        """
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, int(len(sorted_vals) * pct / 100) - 1)
        return round(sorted_vals[idx], 2)

    # ── Testing Support ───────────────────────────────────────────────

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state. For testing only."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._interactions.clear()
                cls._instance._handoffs.clear()
                cls._instance._initialized = False
            cls._instance = None
