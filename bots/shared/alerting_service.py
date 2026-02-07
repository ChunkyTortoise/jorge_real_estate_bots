"""
Jorge Bot Alerting Service

Monitors bot metrics against configurable threshold rules and fires alerts
when thresholds are breached. Each rule has a cooldown period to prevent
alert storms. Alerts are stored in-memory (last 100) and can be
acknowledged by operators.

Pre-configured rules align with the Jorge Bot Audit Spec performance targets:
  - Error rate < 1%
  - Lead Bot p95 < 2 000 ms
  - Buyer/Seller Bot p95 < 2 500 ms
  - Handoff p95 < 500 ms
  - Cache hit rate >= 70%
  - Handoff failure rate < 1%

Usage:
    service = AlertingService()
    service.record_metric("error_rate", 0.03)
    triggered = service.evaluate_rules()
    active = service.get_active_alerts()
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_STORED_ALERTS = 100

VALID_OPERATORS = frozenset({"gt", "lt", "gte", "lte"})
VALID_SEVERITIES = frozenset({"critical", "warning", "info"})


@dataclass
class AlertRule:
    """A single alerting rule that compares a metric against a threshold."""

    name: str
    metric: str  # e.g. "error_rate", "lead_bot.response_time_p95"
    operator: str  # "gt", "lt", "gte", "lte"
    threshold: float
    severity: str  # "critical", "warning", "info"
    cooldown_seconds: int = 300  # don't re-alert for 5 min


DEFAULT_RULES: List[AlertRule] = [
    AlertRule("high_error_rate", "error_rate", "gt", 0.01, "critical"),
    AlertRule("slow_lead_bot", "lead_bot.response_time_p95", "gt", 2000, "warning"),
    AlertRule("slow_buyer_bot", "buyer_bot.response_time_p95", "gt", 2500, "warning"),
    AlertRule("slow_seller_bot", "seller_bot.response_time_p95", "gt", 2500, "warning"),
    AlertRule("slow_handoff", "handoff.response_time_p95", "gt", 500, "warning"),
    AlertRule("low_cache_hit", "cache_hit_rate", "lt", 0.70, "warning"),
    AlertRule("high_handoff_failure", "handoff.failure_rate", "gt", 0.01, "critical"),
]


@dataclass
class _MetricPoint:
    """A single metric data point."""

    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


class AlertingService:
    """Metrics alerting engine for Jorge bot operations.

    Thread-safe, in-memory alert management with configurable rules,
    cooldown periods, and pre-configured thresholds from the audit spec.
    """

    # ── Singleton ─────────────────────────────────────────────────────
    _instance: Optional["AlertingService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AlertingService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._rules: Dict[str, AlertRule] = {}
        self._metrics: Dict[str, List[_MetricPoint]] = {}
        self._alerts: List[Dict[str, Any]] = []
        self._last_fired: Dict[str, float] = {}  # rule_name -> last fire timestamp
        self._data_lock = threading.Lock()
        self._initialized = True

        # Load default rules
        for rule in DEFAULT_RULES:
            self._rules[rule.name] = rule

        logger.info(
            "AlertingService initialized with %d default rules",
            len(DEFAULT_RULES),
        )

    # ── Rule Management ───────────────────────────────────────────────

    def add_rule(self, rule: AlertRule) -> None:
        """Register an alert rule.

        Args:
            rule: The AlertRule to add. Overwrites any existing rule with
                  the same name.

        Raises:
            ValueError: On invalid operator or severity.
        """
        if rule.operator not in VALID_OPERATORS:
            raise ValueError(
                f"Invalid operator '{rule.operator}'. "
                f"Must be one of: {sorted(VALID_OPERATORS)}"
            )
        if rule.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{rule.severity}'. "
                f"Must be one of: {sorted(VALID_SEVERITIES)}"
            )

        with self._data_lock:
            self._rules[rule.name] = rule

        logger.info(
            "Added alert rule '%s': %s %s %s (severity=%s, cooldown=%ds)",
            rule.name, rule.metric, rule.operator, rule.threshold,
            rule.severity, rule.cooldown_seconds,
        )

    def remove_rule(self, name: str) -> None:
        """Remove a rule by name.

        Args:
            name: The rule name to remove.

        Raises:
            KeyError: If the rule does not exist.
        """
        with self._data_lock:
            if name not in self._rules:
                raise KeyError(f"Alert rule '{name}' not found")
            del self._rules[name]
            self._last_fired.pop(name, None)

        logger.info("Removed alert rule '%s'", name)

    def list_rules(self) -> List[AlertRule]:
        """List all registered rules.

        Returns:
            List of AlertRule instances (copies).
        """
        with self._data_lock:
            return list(self._rules.values())

    # ── Metric Recording ──────────────────────────────────────────────

    def record_metric(
        self,
        metric: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric data point.

        Args:
            metric: Metric name (e.g. "error_rate", "lead_bot.response_time_p95").
            value: Numeric value for the data point.
            labels: Optional key-value labels for additional context.
        """
        point = _MetricPoint(
            value=value,
            timestamp=time.time(),
            labels=labels or {},
        )

        with self._data_lock:
            if metric not in self._metrics:
                self._metrics[metric] = []
            self._metrics[metric].append(point)

        logger.debug("Recorded metric '%s' = %s", metric, value)

    def get_metric_history(
        self, metric: str, window_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get recent metric values within a time window.

        Args:
            metric: Metric name to query.
            window_minutes: How far back to look (default 60 minutes).

        Returns:
            List of dicts with value, timestamp, and labels.
        """
        cutoff = time.time() - (window_minutes * 60)

        with self._data_lock:
            points = self._metrics.get(metric, [])
            return [
                {
                    "value": p.value,
                    "timestamp": p.timestamp,
                    "labels": p.labels,
                }
                for p in points
                if p.timestamp >= cutoff
            ]

    # ── Alert Evaluation ──────────────────────────────────────────────

    def evaluate_rules(self) -> List[Dict[str, Any]]:
        """Check all rules against the latest metric values.

        For each rule, the most recent data point for the rule's metric
        is compared against the threshold. If breached and the cooldown
        has elapsed, a new alert is created.

        Returns:
            List of newly triggered alert dicts.
        """
        now = time.time()
        triggered: List[Dict[str, Any]] = []

        with self._data_lock:
            for rule in self._rules.values():
                points = self._metrics.get(rule.metric)
                if not points:
                    continue

                latest = points[-1]

                if not self._check_threshold(
                    latest.value, rule.operator, rule.threshold
                ):
                    continue

                # Cooldown check
                last_fire = self._last_fired.get(rule.name, 0.0)
                if (now - last_fire) < rule.cooldown_seconds:
                    continue

                # Fire alert
                alert = {
                    "id": uuid.uuid4().hex[:8],
                    "rule_name": rule.name,
                    "metric": rule.metric,
                    "value": latest.value,
                    "threshold": rule.threshold,
                    "severity": rule.severity,
                    "triggered_at": now,
                    "acknowledged": False,
                }
                self._alerts.append(alert)
                self._last_fired[rule.name] = now
                triggered.append(alert)

                logger.warning(
                    "Alert fired: '%s' — %s=%s (threshold %s %s, severity=%s)",
                    rule.name, rule.metric, latest.value,
                    rule.operator, rule.threshold, rule.severity,
                )

            # Prune to last MAX_STORED_ALERTS
            if len(self._alerts) > MAX_STORED_ALERTS:
                self._alerts = self._alerts[-MAX_STORED_ALERTS:]

        return triggered

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all currently active (unacknowledged) alerts.

        Returns:
            List of alert dicts where acknowledged is False.
        """
        with self._data_lock:
            return [
                alert for alert in self._alerts
                if not alert["acknowledged"]
            ]

    def acknowledge_alert(self, alert_id: str) -> None:
        """Acknowledge an alert by its ID.

        Args:
            alert_id: The short hex ID of the alert to acknowledge.

        Raises:
            KeyError: If the alert ID is not found.
        """
        with self._data_lock:
            for alert in self._alerts:
                if alert["id"] == alert_id:
                    alert["acknowledged"] = True
                    logger.info("Acknowledged alert '%s'", alert_id)
                    return

        raise KeyError(f"Alert '{alert_id}' not found")

    # ── Internal Helpers ──────────────────────────────────────────────

    @staticmethod
    def _check_threshold(value: float, operator: str, threshold: float) -> bool:
        """Evaluate whether a value breaches a threshold.

        Args:
            value: The metric value.
            operator: Comparison operator (gt, lt, gte, lte).
            threshold: The threshold to compare against.

        Returns:
            True if the threshold is breached.
        """
        if operator == "gt":
            return value > threshold
        elif operator == "lt":
            return value < threshold
        elif operator == "gte":
            return value >= threshold
        elif operator == "lte":
            return value <= threshold
        return False

    # ── Testing Support ───────────────────────────────────────────────

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state. For testing only."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._rules.clear()
                cls._instance._metrics.clear()
                cls._instance._alerts.clear()
                cls._instance._last_fired.clear()
                cls._instance._initialized = False
            cls._instance = None
