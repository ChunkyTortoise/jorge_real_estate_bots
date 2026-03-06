"""Unit tests for bots.shared.alerting_service.AlertingService."""
from __future__ import annotations

import time

import pytest

from bots.shared.alerting_service import (
    AlertingService,
    AlertRule,
    DEFAULT_RULES,
    MAX_STORED_ALERTS,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset singleton between tests."""
    AlertingService.reset()
    yield
    AlertingService.reset()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_returns_same_instance(self):
        a = AlertingService()
        b = AlertingService()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = AlertingService()
        AlertingService.reset()
        b = AlertingService()
        assert a is not b


# ---------------------------------------------------------------------------
# Rule management
# ---------------------------------------------------------------------------

class TestRuleManagement:
    def test_default_rules_loaded(self):
        svc = AlertingService()
        rules = svc.list_rules()
        assert len(rules) == len(DEFAULT_RULES)

    def test_add_rule(self):
        svc = AlertingService()
        rule = AlertRule("test_rule", "test_metric", "gt", 0.5, "warning")
        svc.add_rule(rule)
        names = [r.name for r in svc.list_rules()]
        assert "test_rule" in names

    def test_add_rule_invalid_operator(self):
        svc = AlertingService()
        rule = AlertRule("bad_op", "metric", "eq", 1.0, "warning")
        with pytest.raises(ValueError, match="Invalid operator"):
            svc.add_rule(rule)

    def test_add_rule_invalid_severity(self):
        svc = AlertingService()
        rule = AlertRule("bad_sev", "metric", "gt", 1.0, "panic")
        with pytest.raises(ValueError, match="Invalid severity"):
            svc.add_rule(rule)

    def test_remove_rule(self):
        svc = AlertingService()
        svc.remove_rule("high_error_rate")
        names = [r.name for r in svc.list_rules()]
        assert "high_error_rate" not in names

    def test_remove_nonexistent_rule(self):
        svc = AlertingService()
        with pytest.raises(KeyError, match="not found"):
            svc.remove_rule("nonexistent")

    def test_add_rule_overwrites(self):
        svc = AlertingService()
        original_count = len(svc.list_rules())
        rule = AlertRule("high_error_rate", "error_rate", "gt", 0.05, "info")
        svc.add_rule(rule)
        assert len(svc.list_rules()) == original_count
        updated = [r for r in svc.list_rules() if r.name == "high_error_rate"][0]
        assert updated.threshold == 0.05


# ---------------------------------------------------------------------------
# Metric recording
# ---------------------------------------------------------------------------

class TestMetricRecording:
    def test_record_and_retrieve(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.02)
        history = svc.get_metric_history("error_rate")
        assert len(history) == 1
        assert history[0]["value"] == 0.02

    def test_record_with_labels(self):
        svc = AlertingService()
        svc.record_metric("cpu", 0.8, labels={"host": "web1"})
        history = svc.get_metric_history("cpu")
        assert history[0]["labels"]["host"] == "web1"

    def test_window_filter(self):
        svc = AlertingService()
        svc.record_metric("metric_a", 1.0)
        # Force old timestamp
        svc._metrics["metric_a"][0].timestamp = time.time() - 7200
        history = svc.get_metric_history("metric_a", window_minutes=60)
        assert len(history) == 0

    def test_nonexistent_metric(self):
        svc = AlertingService()
        assert svc.get_metric_history("nonexistent") == []


# ---------------------------------------------------------------------------
# Alert evaluation
# ---------------------------------------------------------------------------

class TestAlertEvaluation:
    def test_triggers_on_threshold_breach(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.05)  # > 0.01 threshold
        triggered = svc.evaluate_rules()
        assert len(triggered) == 1
        assert triggered[0]["rule_name"] == "high_error_rate"
        assert triggered[0]["severity"] == "critical"

    def test_no_trigger_below_threshold(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.005)
        triggered = svc.evaluate_rules()
        rule_names = [a["rule_name"] for a in triggered]
        assert "high_error_rate" not in rule_names

    def test_cooldown_prevents_repeat(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.05)
        first = svc.evaluate_rules()
        assert len(first) == 1

        svc.record_metric("error_rate", 0.06)
        second = svc.evaluate_rules()
        error_alerts = [a for a in second if a["rule_name"] == "high_error_rate"]
        assert len(error_alerts) == 0  # Cooldown active

    def test_cooldown_expires(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.05)
        svc.evaluate_rules()
        # Expire cooldown
        svc._last_fired["high_error_rate"] = time.time() - 400
        svc.record_metric("error_rate", 0.06)
        triggered = svc.evaluate_rules()
        rule_names = [a["rule_name"] for a in triggered]
        assert "high_error_rate" in rule_names

    def test_no_metric_no_trigger(self):
        svc = AlertingService()
        triggered = svc.evaluate_rules()
        assert len(triggered) == 0

    def test_lt_operator(self):
        svc = AlertingService()
        svc.record_metric("cache_hit_rate", 0.5)  # < 0.70 threshold
        triggered = svc.evaluate_rules()
        rule_names = [a["rule_name"] for a in triggered]
        assert "low_cache_hit" in rule_names

    def test_prune_old_alerts(self):
        svc = AlertingService()
        # Stuff alerts beyond max
        for i in range(MAX_STORED_ALERTS + 20):
            svc._alerts.append({"id": str(i), "acknowledged": False, "rule_name": f"r{i}"})
        # Trigger one more evaluation to prune
        svc.record_metric("error_rate", 0.05)
        svc.evaluate_rules()
        assert len(svc._alerts) <= MAX_STORED_ALERTS


# ---------------------------------------------------------------------------
# Active alerts and acknowledgement
# ---------------------------------------------------------------------------

class TestActiveAlerts:
    def test_get_active_alerts(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.05)
        svc.evaluate_rules()
        active = svc.get_active_alerts()
        assert len(active) >= 1
        assert all(not a["acknowledged"] for a in active)

    def test_acknowledge_alert(self):
        svc = AlertingService()
        svc.record_metric("error_rate", 0.05)
        triggered = svc.evaluate_rules()
        alert_id = triggered[0]["id"]

        svc.acknowledge_alert(alert_id)
        active = svc.get_active_alerts()
        assert all(a["id"] != alert_id for a in active)

    def test_acknowledge_nonexistent_alert(self):
        svc = AlertingService()
        with pytest.raises(KeyError, match="not found"):
            svc.acknowledge_alert("nonexistent")


# ---------------------------------------------------------------------------
# Threshold operators
# ---------------------------------------------------------------------------

class TestCheckThreshold:
    @pytest.mark.parametrize("value,op,threshold,expected", [
        (5.0, "gt", 3.0, True),
        (3.0, "gt", 5.0, False),
        (5.0, "gt", 5.0, False),
        (3.0, "lt", 5.0, True),
        (5.0, "lt", 3.0, False),
        (5.0, "lt", 5.0, False),
        (5.0, "gte", 5.0, True),
        (5.0, "gte", 3.0, True),
        (3.0, "gte", 5.0, False),
        (5.0, "lte", 5.0, True),
        (3.0, "lte", 5.0, True),
        (5.0, "lte", 3.0, False),
        (5.0, "invalid", 3.0, False),
    ])
    def test_operator(self, value, op, threshold, expected):
        assert AlertingService._check_threshold(value, op, threshold) == expected
