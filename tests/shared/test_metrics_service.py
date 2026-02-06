"""
Unit tests for MetricsService.

Tests metrics aggregation, caching, and error handling functionality.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from bots.shared.metrics_service import MetricsService, get_metrics_service
from bots.shared.dashboard_models import (
    PerformanceDashboardMetrics,
    CacheStatistics,
    CostSavingsMetrics,
    BudgetDistribution,
    TimelineDistribution,
    CommissionMetrics,
)


class TestMetricsService:
    """Test suite for MetricsService class."""

    @pytest.fixture
    def metrics_service(self):
        """Create MetricsService instance for testing."""
        return MetricsService()

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service for testing."""
        mock = Mock()
        mock.get = AsyncMock()
        mock.set = AsyncMock()
        return mock

    @pytest.fixture
    def mock_performance_tracker(self):
        """Mock performance tracker for testing."""
        mock = Mock()
        mock.get_performance_metrics = AsyncMock()
        mock.get_cache_statistics = AsyncMock()
        mock.get_cost_savings = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_get_performance_metrics_from_cache(self, metrics_service, mock_cache_service):
        """Test getting performance metrics from cache."""
        # Mock cache hit
        cached_data = {
            'cache_avg_ms': 15.5,
            'cache_p95_ms': 45.2,
            'cache_hit_rate': 85.5,
            'cache_miss_rate': 14.5,
            'total_cache_hits': 1250,
            'total_cache_misses': 210,
            'ai_avg_ms': 1200.0,
            'ai_p95_ms': 2400.0,
            'ai_total_calls': 89,
            'five_minute_rule_compliance': 94.2,
            'fallback_activations': 3,
            'ghl_avg_ms': 450.0,
            'ghl_p95_ms': 890.0,
            'ghl_total_calls': 156,
            'ghl_error_rate': 2.1,
            'timestamp': datetime.now().isoformat()
        }
        mock_cache_service.get.return_value = cached_data

        with patch.object(metrics_service, 'cache_service', mock_cache_service):
            result = await metrics_service.get_performance_metrics()

            # Verify cache was checked
            mock_cache_service.get.assert_called_once_with("metrics:dashboard:performance")

            # Verify result structure
            assert isinstance(result, PerformanceDashboardMetrics)
            assert result.cache_avg_ms == 15.5
            assert result.cache_hit_rate == 85.5
            assert result.ai_total_calls == 89

    @pytest.mark.asyncio
    async def test_get_performance_metrics_fresh_data(self, metrics_service, mock_cache_service, mock_performance_tracker):
        """Test getting fresh performance metrics when cache miss."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock performance tracker data
        expected_metrics = PerformanceDashboardMetrics(
            cache_avg_ms=12.5,
            cache_p95_ms=35.0,
            cache_hit_rate=88.2,
            cache_miss_rate=11.8,
            total_cache_hits=1580,
            total_cache_misses=210,
            ai_avg_ms=1150.0,
            ai_p95_ms=2200.0,
            ai_total_calls=95,
            five_minute_rule_compliance=96.8,
            fallback_activations=2,
            ghl_avg_ms=420.0,
            ghl_p95_ms=780.0,
            ghl_total_calls=178,
            ghl_error_rate=1.7,
        )
        mock_performance_tracker.get_performance_metrics.return_value = expected_metrics

        with patch.object(metrics_service, 'cache_service', mock_cache_service), \
             patch.object(metrics_service, 'performance_tracker', mock_performance_tracker):

            result = await metrics_service.get_performance_metrics()

            # Verify cache miss
            mock_cache_service.get.assert_called_once()

            # Verify fresh data fetch
            mock_performance_tracker.get_performance_metrics.assert_called_once()

            # Verify cache set
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[0][0] == "metrics:dashboard:performance"
            assert call_args[1]['ttl'] == 30

            # Verify result
            assert result == expected_metrics

    @pytest.mark.asyncio
    async def test_get_cache_statistics_success(self, metrics_service, mock_cache_service, mock_performance_tracker):
        """Test getting cache statistics successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock performance tracker data
        expected_stats = CacheStatistics(
            hit_rate=87.5,
            miss_rate=12.5,
            avg_hit_time_ms=8.2,
            avg_miss_time_ms=1200.0,
            total_hits=1750,
            total_misses=250,
            total_requests=2000,
            cache_size_mb=45.6,
            ttl_expirations=89,
            hit_rate_by_hour=[
                {'hour': 0, 'rate': 85.0, 'hits': 170, 'misses': 30},
                {'hour': 1, 'rate': 90.0, 'hits': 180, 'misses': 20},
            ]
        )
        mock_performance_tracker.get_cache_statistics.return_value = expected_stats

        with patch.object(metrics_service, 'cache_service', mock_cache_service), \
             patch.object(metrics_service, 'performance_tracker', mock_performance_tracker):

            result = await metrics_service.get_cache_statistics()

            # Verify fresh data fetch
            mock_performance_tracker.get_cache_statistics.assert_called_once()

            # Verify cache set with 5 min TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 300

            # Verify result
            assert result == expected_stats
            assert result.hit_rate == 87.5
            assert len(result.hit_rate_by_hour) == 2

    @pytest.mark.asyncio
    async def test_get_cost_savings_success(self, metrics_service, mock_cache_service, mock_performance_tracker):
        """Test getting cost savings successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock performance tracker data
        expected_savings = CostSavingsMetrics(
            total_saved_dollars=245.50,
            ai_calls_avoided=4910,
            pattern_matches=1250,
            cache_hits=3660,
            avg_cost_per_ai_call=0.05,
            lead_bot_savings=183.00,
            seller_bot_savings=62.50
        )
        mock_performance_tracker.get_cost_savings.return_value = expected_savings

        with patch.object(metrics_service, 'cache_service', mock_cache_service), \
             patch.object(metrics_service, 'performance_tracker', mock_performance_tracker):

            result = await metrics_service.get_cost_savings()

            # Verify fresh data fetch
            mock_performance_tracker.get_cost_savings.assert_called_once()

            # Verify cache set with 1 hour TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 3600

            # Verify result
            assert result == expected_savings
            assert result.total_saved_dollars == 245.50

    @pytest.mark.asyncio
    async def test_get_budget_distribution_success(self, metrics_service, mock_cache_service):
        """Test getting budget distribution successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(metrics_service, 'cache_service', mock_cache_service):
            result = await metrics_service.get_budget_distribution()

            # Verify cache set with 5 min TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 300

            # Verify result structure
            assert isinstance(result, BudgetDistribution)
            assert result.total_leads > 0
            assert len(result.ranges) > 0
            assert all(r.label for r in result.ranges)

    @pytest.mark.asyncio
    async def test_get_timeline_distribution_success(self, metrics_service, mock_cache_service):
        """Test getting timeline distribution successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(metrics_service, 'cache_service', mock_cache_service):
            result = await metrics_service.get_timeline_distribution()

            # Verify cache set
            mock_cache_service.set.assert_called_once()

            # Verify result structure
            assert isinstance(result, TimelineDistribution)
            assert result.total_leads > 0
            assert len(result.classifications) > 0
            assert all(c.timeline for c in result.classifications)

    @pytest.mark.asyncio
    async def test_get_commission_metrics_success(self, metrics_service, mock_cache_service):
        """Test getting commission metrics successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(metrics_service, 'cache_service', mock_cache_service):
            result = await metrics_service.get_commission_metrics()

            # Verify cache set with 10 min TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 600

            # Verify result structure
            assert isinstance(result, CommissionMetrics)
            assert result.total_commission_potential > 0
            assert len(result.commission_trend) > 0

    @pytest.mark.asyncio
    async def test_get_dashboard_summary_success(self, metrics_service, mock_cache_service):
        """Test getting complete dashboard summary successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(metrics_service, 'cache_service', mock_cache_service), \
             patch.object(metrics_service, 'get_performance_metrics') as mock_perf, \
             patch.object(metrics_service, 'get_budget_distribution') as mock_budget, \
             patch.object(metrics_service, 'get_timeline_distribution') as mock_timeline, \
             patch.object(metrics_service, 'get_commission_metrics') as mock_commission, \
             patch.object(metrics_service, 'get_cost_savings') as mock_savings:

            # Mock all method calls with actual dataclass instances
            mock_perf.return_value = PerformanceDashboardMetrics(
                cache_avg_ms=10.0, cache_p95_ms=25.0, cache_hit_rate=85.0, cache_miss_rate=15.0,
                total_cache_hits=100, total_cache_misses=15, ai_avg_ms=1000.0, ai_p95_ms=2000.0,
                ai_total_calls=50, five_minute_rule_compliance=95.0, fallback_activations=1,
                ghl_avg_ms=400.0, ghl_p95_ms=800.0, ghl_total_calls=75, ghl_error_rate=2.0
            )
            mock_budget.return_value = BudgetDistribution(
                ranges=[], total_leads=10, avg_budget=350000, median_budget=320000,
                validation_pass_rate=85.0, out_of_service_area=2
            )
            mock_timeline.return_value = TimelineDistribution(
                classifications=[], total_leads=10, immediate_count=3
            )
            mock_commission.return_value = CommissionMetrics(
                total_commission_potential=150000.0, avg_commission_per_deal=15000.0,
                total_qualified_leads=10, hot_leads_count=5, budget_validation_pass_rate=85.0,
                service_area_match_rate=92.0, projected_monthly_commission=50000.0,
                projected_deals=3, commission_trend=[]
            )
            mock_savings.return_value = CostSavingsMetrics(
                total_saved_dollars=100.0, ai_calls_avoided=2000, pattern_matches=300,
                cache_hits=1700, avg_cost_per_ai_call=0.05, lead_bot_savings=85.0,
                seller_bot_savings=15.0
            )

            result = await metrics_service.get_dashboard_summary()

            # Verify all methods were called
            mock_perf.assert_called_once()
            mock_budget.assert_called_once()
            mock_timeline.assert_called_once()
            mock_commission.assert_called_once()
            mock_savings.assert_called_once()

            # Verify cache set with 30 sec TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 30

            # Verify result structure
            assert isinstance(result, dict)
            assert 'performance' in result
            assert 'budget_distribution' in result
            assert 'generated_at' in result

    @pytest.mark.asyncio
    async def test_performance_metrics_error_handling(self, metrics_service, mock_cache_service):
        """Test error handling for performance metrics."""
        # Mock cache miss and tracker exception
        mock_cache_service.get.return_value = None

        with patch.object(metrics_service, 'cache_service', mock_cache_service), \
             patch.object(metrics_service, 'performance_tracker') as mock_tracker:

            # Mock tracker exception
            mock_tracker.get_performance_metrics.side_effect = Exception("Tracker error")

            result = await metrics_service.get_performance_metrics()

            # Verify fallback data
            assert isinstance(result, PerformanceDashboardMetrics)
            assert result.cache_avg_ms == 0.0
            assert result.total_cache_hits == 0

    @pytest.mark.asyncio
    async def test_dashboard_summary_error_handling(self, metrics_service, mock_cache_service):
        """Test error handling for dashboard summary when individual method fails."""
        # Mock cache miss and method exception
        mock_cache_service.get.return_value = None

        with patch.object(metrics_service, 'cache_service', mock_cache_service), \
             patch.object(metrics_service, 'get_performance_metrics', side_effect=Exception("Error")):

            result = await metrics_service.get_dashboard_summary()

            # Verify partial success - performance is None due to exception, others succeed
            assert isinstance(result, dict)
            assert result['performance'] is None  # Failed method returns None
            assert result['budget_distribution'] is not None  # Other methods succeed
            assert 'generated_at' in result


class TestMetricsServiceSingleton:
    """Test singleton pattern for MetricsService."""

    def test_get_metrics_service_singleton(self):
        """Test that get_metrics_service returns same instance."""
        service1 = get_metrics_service()
        service2 = get_metrics_service()

        assert service1 is service2
        assert isinstance(service1, MetricsService)


class TestMetricsServiceFallbacks:
    """Test fallback methods for MetricsService."""

    @pytest.fixture
    def metrics_service(self):
        """Create MetricsService instance for testing."""
        return MetricsService()

    def test_fallback_performance_metrics(self, metrics_service):
        """Test fallback performance metrics structure."""
        result = metrics_service._get_fallback_performance_metrics()

        assert isinstance(result, PerformanceDashboardMetrics)
        assert result.cache_avg_ms == 0.0
        assert result.total_cache_hits == 0
        assert result.ai_total_calls == 0

    def test_fallback_cache_statistics(self, metrics_service):
        """Test fallback cache statistics structure."""
        result = metrics_service._get_fallback_cache_statistics()

        assert isinstance(result, CacheStatistics)
        assert result.hit_rate == 0.0
        assert result.total_requests == 0
        assert result.hit_rate_by_hour == []

    def test_fallback_cost_savings(self, metrics_service):
        """Test fallback cost savings structure."""
        result = metrics_service._get_fallback_cost_savings()

        assert isinstance(result, CostSavingsMetrics)
        assert result.total_saved_dollars == 0.0
        assert result.ai_calls_avoided == 0

    def test_fallback_budget_distribution(self, metrics_service):
        """Test fallback budget distribution structure."""
        result = metrics_service._get_fallback_budget_distribution()

        assert isinstance(result, BudgetDistribution)
        assert result.total_leads == 0
        assert result.ranges == []

    def test_fallback_timeline_distribution(self, metrics_service):
        """Test fallback timeline distribution structure."""
        result = metrics_service._get_fallback_timeline_distribution()

        assert isinstance(result, TimelineDistribution)
        assert result.total_leads == 0
        assert result.classifications == []

    def test_fallback_commission_metrics(self, metrics_service):
        """Test fallback commission metrics structure."""
        result = metrics_service._get_fallback_commission_metrics()

        assert isinstance(result, CommissionMetrics)
        assert result.total_commission_potential == 0.0
        assert result.commission_trend == []

    def test_fallback_dashboard_summary(self, metrics_service):
        """Test fallback dashboard summary structure."""
        result = metrics_service._get_fallback_dashboard_summary()

        assert isinstance(result, dict)
        assert result['performance'] is None
        assert 'error' in result
        assert 'generated_at' in result