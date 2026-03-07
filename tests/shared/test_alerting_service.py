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


# ---------------------------------------------------------------------------
# T1: push_alert_outbound webhook delivery
# ---------------------------------------------------------------------------

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from bots.shared.alerting_service import push_alert_outbound


class TestPushAlertOutbound:
    """T1: push_alert_outbound POSTs a Slack-compatible payload to the webhook URL."""

    def _make_client_ctx(self, post_side_effect=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value=mock_resp if post_side_effect is None else None,
            side_effect=post_side_effect,
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    @pytest.mark.asyncio
    async def test_posts_to_webhook_url(self):
        """Happy path: POST is sent to the provided webhook URL."""
        alert = {
            "rule_name": "high_error_rate",
            "metric": "error_rate",
            "value": 0.05,
            "operator": "gt",
            "threshold": 0.01,
            "severity": "critical",
        }
        mock_client = self._make_client_ctx()

        with patch("bots.shared.alerting_service.httpx.AsyncClient", return_value=mock_client):
            await push_alert_outbound(alert, "https://hooks.slack.com/test")

        mock_client.post.assert_awaited_once()
        assert mock_client.post.call_args.args[0] == "https://hooks.slack.com/test"

    @pytest.mark.asyncio
    async def test_payload_contains_rule_name_and_severity(self):
        alert = {
            "rule_name": "high_error_rate",
            "metric": "error_rate",
            "value": 0.05,
            "operator": "gt",
            "threshold": 0.01,
            "severity": "critical",
        }
        mock_client = self._make_client_ctx()

        with patch("bots.shared.alerting_service.httpx.AsyncClient", return_value=mock_client):
            await push_alert_outbound(alert, "https://hooks.slack.com/test")

        payload = mock_client.post.call_args.kwargs["json"]
        assert "high_error_rate" in payload["text"]
        assert "critical" in payload["text"]
        assert "error_rate" in payload["text"]

    @pytest.mark.asyncio
    async def test_critical_uses_red_circle_emoji(self):
        alert = {
            "rule_name": "r",
            "metric": "m",
            "value": 1.0,
            "operator": "gt",
            "threshold": 0.0,
            "severity": "critical",
        }
        mock_client = self._make_client_ctx()
        with patch("bots.shared.alerting_service.httpx.AsyncClient", return_value=mock_client):
            await push_alert_outbound(alert, "https://x")
        assert ":red_circle:" in mock_client.post.call_args.kwargs["json"]["text"]

    @pytest.mark.asyncio
    async def test_warning_uses_warning_emoji(self):
        alert = {
            "rule_name": "r",
            "metric": "m",
            "value": 1.0,
            "operator": "gt",
            "threshold": 0.0,
            "severity": "warning",
        }
        mock_client = self._make_client_ctx()
        with patch("bots.shared.alerting_service.httpx.AsyncClient", return_value=mock_client):
            await push_alert_outbound(alert, "https://x")
        assert ":warning:" in mock_client.post.call_args.kwargs["json"]["text"]

    @pytest.mark.asyncio
    async def test_delivery_failure_logs_warning_not_raises(self, caplog):
        """Exception from httpx is caught and logged — function must not raise."""
        alert = {
            "rule_name": "test",
            "metric": "m",
            "value": 1.0,
            "operator": "gt",
            "threshold": 0.0,
            "severity": "info",
        }
        mock_client = self._make_client_ctx(post_side_effect=Exception("network down"))

        with patch("bots.shared.alerting_service.httpx.AsyncClient", return_value=mock_client):
            with caplog.at_level(logging.WARNING, logger="bots.shared.alerting_service"):
                await push_alert_outbound(alert, "https://hooks.slack.com/test")

        assert any("Alert webhook delivery failed" in r.message for r in caplog.records)
