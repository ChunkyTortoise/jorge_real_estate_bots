"""
Unit tests for PerformanceTracker (Phase 3B).

Tests performance metrics tracking including:
- Cache hit/miss recording
- AI call tracking
- GHL API call tracking
- Metrics calculation (avg, P95, rates)
- Cost savings calculation
- Snapshot persistence and restoration
"""
from unittest.mock import AsyncMock

import pytest

from bots.shared.dashboard_models import (
    CacheStatistics,
    CostSavingsMetrics,
    PerformanceDashboardMetrics,
)
from bots.shared.performance_tracker import PerformanceTracker, get_performance_tracker


@pytest.fixture
def tracker():
    """Create a fresh PerformanceTracker instance for each test."""
    return PerformanceTracker(window_hours=24)


@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    return mock


class TestPerformanceTracker:
    """Test PerformanceTracker initialization and basic functionality."""

    def test_initialization(self, tracker):
        """Test PerformanceTracker initialization."""
        assert tracker.window_hours == 24
        assert tracker._total_cache_hits == 0
        assert tracker._total_cache_misses == 0
        assert tracker._total_ai_calls == 0
        assert tracker._total_ghl_calls == 0

    @pytest.mark.asyncio
    async def test_record_cache_hit(self, tracker):
        """Test recording cache hit events."""
        await tracker.record_cache_hit(
            response_time_ms=0.19,
            data_size_bytes=1024
        )

        assert tracker._total_cache_hits == 1
        assert tracker._ai_calls_avoided == 1
        assert len(tracker._cache_hits) == 1

        # Verify event structure
        event = tracker._cache_hits[0]
        assert event['response_time_ms'] == 0.19
        assert event['data_size_bytes'] == 1024
        assert 'timestamp' in event

    @pytest.mark.asyncio
    async def test_record_cache_miss(self, tracker):
        """Test recording cache miss events."""
        await tracker.record_cache_miss(cache_key="lead:12345")

        assert tracker._total_cache_misses == 1
        assert len(tracker._cache_misses) == 1

        event = tracker._cache_misses[0]
        assert event['cache_key'] == "lead:12345"
        assert 'timestamp' in event

    @pytest.mark.asyncio
    async def test_record_ai_call(self, tracker):
        """Test recording AI call events."""
        await tracker.record_ai_call(
            response_time_ms=489.0,
            five_minute_compliant=True,
            was_pattern_match=False
        )

        assert tracker._total_ai_calls == 1
        assert len(tracker._ai_calls) == 1
        assert tracker._fallback_activations == 0

        event = tracker._ai_calls[0]
        assert event['response_time_ms'] == 489.0
        assert event['five_minute_compliant'] is True

    @pytest.mark.asyncio
    async def test_record_ai_call_pattern_match(self, tracker):
        """Test recording AI call with pattern match."""
        await tracker.record_ai_call(
            response_time_ms=50.0,
            five_minute_compliant=True,
            was_pattern_match=True
        )

        assert tracker._total_ai_calls == 1
        assert tracker._pattern_matches == 1
        assert tracker._ai_calls_avoided == 1  # Pattern match avoids full AI

    @pytest.mark.asyncio
    async def test_record_ai_call_non_compliant(self, tracker):
        """Test recording non-compliant AI call."""
        await tracker.record_ai_call(
            response_time_ms=350000.0,  # > 5 minutes
            five_minute_compliant=False
        )

        assert tracker._total_ai_calls == 1
        assert tracker._fallback_activations == 1

    @pytest.mark.asyncio
    async def test_record_ghl_call_success(self, tracker):
        """Test recording successful GHL call."""
        await tracker.record_ghl_call(
            response_time_ms=150.0,
            success=True,
            endpoint="/contacts/123"
        )

        assert tracker._total_ghl_calls == 1
        assert tracker._ghl_errors == 0
        assert len(tracker._ghl_calls) == 1

    @pytest.mark.asyncio
    async def test_record_ghl_call_error(self, tracker):
        """Test recording failed GHL call."""
        await tracker.record_ghl_call(
            response_time_ms=5000.0,
            success=False,
            endpoint="/contacts/123"
        )

        assert tracker._total_ghl_calls == 1
        assert tracker._ghl_errors == 1


class TestMetricsCalculation:
    """Test metrics calculation methods."""

    @pytest.mark.asyncio
    async def test_get_performance_metrics_empty(self, tracker, mock_cache_service):
        """Test getting metrics with no data."""
        tracker.cache_service = mock_cache_service

        metrics = await tracker.get_performance_metrics()

        assert isinstance(metrics, PerformanceDashboardMetrics)
        assert metrics.cache_avg_ms == 0.0
        assert metrics.cache_hit_rate == 0.0
        assert metrics.total_cache_hits == 0

    @pytest.mark.asyncio
    async def test_get_performance_metrics_with_data(self, tracker, mock_cache_service):
        """Test getting metrics with sample data."""
        tracker.cache_service = mock_cache_service

        # Record some events
        await tracker.record_cache_hit(0.19, 1024)
        await tracker.record_cache_hit(0.25, 2048)
        await tracker.record_cache_miss("key1")

        await tracker.record_ai_call(489.0, five_minute_compliant=True)
        await tracker.record_ai_call(520.0, five_minute_compliant=True)

        await tracker.record_ghl_call(150.0, success=True)
        await tracker.record_ghl_call(200.0, success=False)

        metrics = await tracker.get_performance_metrics()

        # Cache metrics
        assert metrics.total_cache_hits == 2
        assert metrics.total_cache_misses == 1
        assert 0.19 <= metrics.cache_avg_ms <= 0.25
        assert metrics.cache_hit_rate == pytest.approx(66.67, rel=0.1)

        # AI metrics
        assert metrics.ai_total_calls == 2
        assert 489.0 <= metrics.ai_avg_ms <= 520.0
        assert metrics.five_minute_rule_compliance == 100.0

        # GHL metrics
        assert metrics.ghl_total_calls == 2
        assert metrics.ghl_error_rate == 50.0

    @pytest.mark.asyncio
    async def test_get_cache_statistics(self, tracker, mock_cache_service):
        """Test getting cache statistics."""
        tracker.cache_service = mock_cache_service

        # Record cache events
        await tracker.record_cache_hit(0.19, 1024)
        await tracker.record_cache_hit(0.22, 2048)
        await tracker.record_cache_miss("key1")

        stats = await tracker.get_cache_statistics()

        assert isinstance(stats, CacheStatistics)
        assert stats.total_hits == 2
        assert stats.total_misses == 1
        assert stats.total_requests == 3
        assert stats.hit_rate == pytest.approx(66.67, rel=0.1)
        assert stats.avg_hit_time_ms > 0

    @pytest.mark.asyncio
    async def test_get_cost_savings(self, tracker, mock_cache_service):
        """Test getting cost savings metrics."""
        tracker.cache_service = mock_cache_service

        # Record events that save costs
        await tracker.record_cache_hit(0.19, 1024)  # Avoids AI call
        await tracker.record_cache_hit(0.22, 2048)  # Avoids AI call
        await tracker.record_ai_call(50.0, True, was_pattern_match=True)  # Pattern match

        savings = await tracker.get_cost_savings()

        assert isinstance(savings, CostSavingsMetrics)
        assert savings.ai_calls_avoided == 3  # 2 cache + 1 pattern
        assert savings.cache_hits == 2
        assert savings.pattern_matches == 1
        assert savings.total_saved_dollars == pytest.approx(3 * 0.05, rel=0.01)

    def test_calculate_avg(self, tracker):
        """Test average calculation."""
        # Add events to deque
        tracker._cache_hits.append({'response_time_ms': 0.19})
        tracker._cache_hits.append({'response_time_ms': 0.25})
        tracker._cache_hits.append({'response_time_ms': 0.30})

        avg = tracker._calculate_avg(tracker._cache_hits, 'response_time_ms')
        expected = (0.19 + 0.25 + 0.30) / 3
        assert avg == pytest.approx(expected, rel=0.01)

    def test_calculate_p95(self, tracker):
        """Test P95 calculation."""
        # Add 100 events with values 1-100
        for i in range(1, 101):
            tracker._ai_calls.append({'response_time_ms': float(i)})

        p95 = tracker._calculate_p95(tracker._ai_calls, 'response_time_ms')
        # P95 of 1-100 should be 95
        assert p95 == pytest.approx(95.0, rel=0.1)

    def test_calculate_rate(self, tracker):
        """Test rate calculation."""
        rate = tracker._calculate_rate(8, 10)
        assert rate == 80.0

        rate = tracker._calculate_rate(0, 0)
        assert rate == 0.0


class TestPersistence:
    """Test snapshot persistence and restoration."""

    @pytest.mark.asyncio
    async def test_persist_snapshot(self, tracker, mock_cache_service):
        """Test persisting metrics snapshot."""
        tracker.cache_service = mock_cache_service

        # Set some counters
        tracker._total_cache_hits = 100
        tracker._total_ai_calls = 50
        tracker._ai_calls_avoided = 75

        await tracker.persist_snapshot()

        # Verify cache.set was called
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args

        # Verify snapshot structure
        snapshot = call_args[0][1]  # Second positional arg
        assert snapshot['total_cache_hits'] == 100
        assert snapshot['total_ai_calls'] == 50
        assert snapshot['ai_calls_avoided'] == 75

    @pytest.mark.asyncio
    async def test_restore_from_snapshot(self, tracker, mock_cache_service):
        """Test restoring metrics from snapshot."""
        tracker.cache_service = mock_cache_service

        # Mock snapshot data
        snapshot = {
            'total_cache_hits': 100,
            'total_cache_misses': 10,
            'total_ai_calls': 50,
            'total_ghl_calls': 200,
            'ai_calls_avoided': 75,
            'pattern_matches': 25,
            'fallback_activations': 3,
            'ghl_errors': 5,
        }
        mock_cache_service.get.return_value = snapshot

        await tracker.restore_from_snapshot()

        # Verify counters restored
        assert tracker._total_cache_hits == 100
        assert tracker._total_cache_misses == 10
        assert tracker._total_ai_calls == 50
        assert tracker._ai_calls_avoided == 75

    @pytest.mark.asyncio
    async def test_restore_no_snapshot(self, tracker, mock_cache_service):
        """Test restoring when no snapshot exists."""
        tracker.cache_service = mock_cache_service
        mock_cache_service.get.return_value = None

        await tracker.restore_from_snapshot()

        # Verify counters remain at zero
        assert tracker._total_cache_hits == 0
        assert tracker._total_ai_calls == 0


class TestGlobalInstance:
    """Test global tracker instance management."""

    def test_get_performance_tracker(self):
        """Test getting global tracker instance."""
        tracker1 = get_performance_tracker()
        tracker2 = get_performance_tracker()

        # Should return same instance
        assert tracker1 is tracker2

    @pytest.mark.asyncio
    async def test_global_tracker_state_persistence(self):
        """Test that global tracker maintains state."""
        tracker = get_performance_tracker()

        # Record an event
        await tracker.record_cache_hit(0.19, 1024)

        # Get instance again
        tracker2 = get_performance_tracker()

        # Should have same state
        assert tracker2._total_cache_hits == tracker._total_cache_hits
