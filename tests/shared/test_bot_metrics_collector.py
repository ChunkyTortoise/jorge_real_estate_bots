"""Unit tests for bots.shared.bot_metrics_collector.BotMetricsCollector."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from bots.shared.bot_metrics_collector import BotMetricsCollector, VALID_BOT_TYPES


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset singleton between tests."""
    BotMetricsCollector.reset()
    yield
    BotMetricsCollector.reset()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_returns_same_instance(self):
        a = BotMetricsCollector()
        b = BotMetricsCollector()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = BotMetricsCollector()
        BotMetricsCollector.reset()
        b = BotMetricsCollector()
        assert a is not b


# ---------------------------------------------------------------------------
# record_bot_interaction
# ---------------------------------------------------------------------------

class TestRecordBotInteraction:
    def test_records_valid_interaction(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("lead", duration_ms=100.0, success=True)
        summary = c.get_bot_summary("lead")
        assert summary["total_interactions"] == 1

    def test_rejects_invalid_bot_type(self):
        c = BotMetricsCollector()
        with pytest.raises(ValueError, match="Invalid bot_type"):
            c.record_bot_interaction("invalid", duration_ms=100.0, success=True)

    def test_records_cache_hit(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("buyer", duration_ms=50.0, success=True, cache_hit=True)
        summary = c.get_bot_summary("buyer")
        assert summary["cache_hit_rate"] == 1.0

    def test_records_failure(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("seller", duration_ms=200.0, success=False)
        summary = c.get_bot_summary("seller")
        assert summary["error_rate"] == 1.0
        assert summary["success_rate"] == 0.0

    @pytest.mark.parametrize("bot_type", sorted(VALID_BOT_TYPES))
    def test_all_valid_bot_types(self, bot_type):
        c = BotMetricsCollector()
        c.record_bot_interaction(bot_type, duration_ms=100.0, success=True)
        assert c.get_bot_summary(bot_type)["total_interactions"] == 1


# ---------------------------------------------------------------------------
# record_handoff
# ---------------------------------------------------------------------------

class TestRecordHandoff:
    def test_records_handoff(self):
        c = BotMetricsCollector()
        c.record_handoff("lead", "buyer", success=True, duration_ms=50.0)
        system = c.get_system_summary()
        assert system["handoffs"]["total_handoffs"] == 1

    def test_handoff_success_rate(self):
        c = BotMetricsCollector()
        c.record_handoff("lead", "buyer", success=True, duration_ms=50.0)
        c.record_handoff("lead", "seller", success=False, duration_ms=100.0)
        system = c.get_system_summary()
        assert system["handoffs"]["success_rate"] == 0.5
        assert system["handoffs"]["failure_rate"] == 0.5


# ---------------------------------------------------------------------------
# get_bot_summary
# ---------------------------------------------------------------------------

class TestGetBotSummary:
    def test_empty_summary(self):
        c = BotMetricsCollector()
        summary = c.get_bot_summary("lead")
        assert summary["total_interactions"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["avg_duration_ms"] == 0.0
        assert summary["p95_duration_ms"] == 0.0

    def test_rejects_invalid_bot_type(self):
        c = BotMetricsCollector()
        with pytest.raises(ValueError, match="Invalid bot_type"):
            c.get_bot_summary("bad")

    def test_avg_duration(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("lead", duration_ms=100.0, success=True)
        c.record_bot_interaction("lead", duration_ms=200.0, success=True)
        summary = c.get_bot_summary("lead")
        assert summary["avg_duration_ms"] == 150.0

    def test_window_filter(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("lead", duration_ms=100.0, success=True)
        # Force old timestamp
        c._interactions[0].timestamp = time.time() - 7200  # 2 hours ago
        summary = c.get_bot_summary("lead", window_minutes=60)
        assert summary["total_interactions"] == 0

    def test_does_not_mix_bot_types(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("lead", duration_ms=100.0, success=True)
        c.record_bot_interaction("buyer", duration_ms=200.0, success=True)
        assert c.get_bot_summary("lead")["total_interactions"] == 1
        assert c.get_bot_summary("buyer")["total_interactions"] == 1


# ---------------------------------------------------------------------------
# get_system_summary
# ---------------------------------------------------------------------------

class TestGetSystemSummary:
    def test_includes_all_bot_types(self):
        c = BotMetricsCollector()
        system = c.get_system_summary()
        for bt in VALID_BOT_TYPES:
            assert bt in system["bots"]

    def test_overall_totals(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("lead", duration_ms=100.0, success=True)
        c.record_bot_interaction("buyer", duration_ms=200.0, success=True)
        system = c.get_system_summary()
        assert system["overall"]["total_interactions"] == 2


# ---------------------------------------------------------------------------
# feed_to_alerting
# ---------------------------------------------------------------------------

class TestFeedToAlerting:
    def test_feeds_metrics(self):
        c = BotMetricsCollector()
        c.record_bot_interaction("lead", duration_ms=100.0, success=True, cache_hit=True)
        c.record_handoff("lead", "buyer", success=True, duration_ms=50.0)

        mock_alerting = MagicMock()
        c.feed_to_alerting(mock_alerting)
        assert mock_alerting.record_metric.call_count == 7


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_records(self):
        c = BotMetricsCollector()
        errors = []

        def record_batch(bot_type):
            try:
                for _ in range(100):
                    c.record_bot_interaction(bot_type, duration_ms=10.0, success=True)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=record_batch, args=(bt,))
            for bt in ["lead", "buyer", "seller"]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        system = c.get_system_summary()
        assert system["overall"]["total_interactions"] == 300


# ---------------------------------------------------------------------------
# Percentile
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_empty(self):
        assert BotMetricsCollector._percentile([], 95) == 0.0

    def test_single_value(self):
        assert BotMetricsCollector._percentile([42.0], 95) == 42.0

    def test_ordered_values(self):
        values = list(range(1, 101))
        p95 = BotMetricsCollector._percentile([float(v) for v in values], 95)
        assert p95 == 95.0
