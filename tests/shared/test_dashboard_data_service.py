"""
Unit tests for DashboardDataService.

Tests data orchestration, pagination, and conversation management functionality.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from bots.shared.dashboard_data_service import DashboardDataService, get_dashboard_data_service
from bots.shared.dashboard_models import (
    ConversationState,
    ConversationFilters,
    PaginatedConversations,
    ConversationStage,
    Temperature,
)


class TestDashboardDataService:
    """Test suite for DashboardDataService class."""

    @pytest.fixture
    def dashboard_service(self):
        """Create DashboardDataService instance for testing."""
        return DashboardDataService()

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service for testing."""
        mock = Mock()
        mock.get = AsyncMock()
        mock.set = AsyncMock()
        return mock

    @pytest.fixture
    def mock_metrics_service(self):
        """Mock metrics service for testing."""
        mock = Mock()
        mock.get_dashboard_summary = AsyncMock()
        mock.get_performance_metrics = AsyncMock()
        mock.get_cache_statistics = AsyncMock()
        mock.get_cost_savings = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_get_complete_dashboard_data_from_cache(self, dashboard_service, mock_cache_service):
        """Test getting complete dashboard data from cache."""
        # Mock cache hit
        cached_data = {
            'metrics': {'performance': {'cache_hit_rate': 85.0}},
            'active_conversations': {'total_count': 25},
            'hero_data': {'total_leads': 247},
            'generated_at': datetime.now().isoformat(),
            'refresh_interval': 30,
            'status': 'success'
        }
        mock_cache_service.get.return_value = cached_data

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_complete_dashboard_data()

            # Verify cache was checked
            mock_cache_service.get.assert_called_once_with("dashboard:complete_data")

            # Verify result structure
            assert result == cached_data
            assert result['status'] == 'success'
            assert 'metrics' in result

    @pytest.mark.asyncio
    async def test_get_complete_dashboard_data_fresh(self, dashboard_service, mock_cache_service, mock_metrics_service):
        """Test getting fresh dashboard data when cache miss."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock metrics service
        mock_metrics_service.get_dashboard_summary.return_value = {'performance': {'cache_hit_rate': 87.0}}

        with patch.object(dashboard_service, 'cache_service', mock_cache_service), \
             patch.object(dashboard_service, 'metrics_service', mock_metrics_service), \
             patch.object(dashboard_service, 'get_active_conversations') as mock_conversations, \
             patch.object(dashboard_service, '_get_hero_dashboard_data') as mock_hero:

            # Mock other data sources with actual dataclass instances
            mock_conversations.return_value = PaginatedConversations(
                conversations=[],
                total_count=0,
                page=1,
                page_size=20,
                total_pages=0,
                has_next=False,
                has_prev=False
            )
            mock_hero.return_value = {'total_leads': 250}

            result = await dashboard_service.get_complete_dashboard_data()

            # Verify all data sources were called
            mock_metrics_service.get_dashboard_summary.assert_called_once()
            mock_conversations.assert_called_once()
            mock_hero.assert_called_once()

            # Verify cache set
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 30

            # Verify result structure
            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert 'generated_at' in result

    @pytest.mark.asyncio
    async def test_get_active_conversations_success(self, dashboard_service, mock_cache_service):
        """Test getting active conversations successfully."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_active_conversations()

            # Verify cache set
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 60

            # Verify result structure
            assert isinstance(result, PaginatedConversations)
            assert result.page == 1
            assert result.page_size == 20
            assert len(result.conversations) <= 20

    @pytest.mark.asyncio
    async def test_get_active_conversations_with_filters(self, dashboard_service, mock_cache_service):
        """Test getting active conversations with filters."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Create filters
        filters = ConversationFilters(
            stage=ConversationStage.Q2,
            temperature=Temperature.HOT,
            search_term="main",
            sort_by="temperature",
            sort_order="desc"
        )

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_active_conversations(filters=filters)

            # Verify result filtering worked
            assert isinstance(result, PaginatedConversations)
            # All conversations should match the stage filter
            for conv in result.conversations:
                assert conv.stage == ConversationStage.Q2
                assert conv.temperature == Temperature.HOT

    @pytest.mark.asyncio
    async def test_get_active_conversations_pagination(self, dashboard_service, mock_cache_service):
        """Test conversation pagination."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            # Test first page
            result_page1 = await dashboard_service.get_active_conversations(page=1, page_size=10)
            assert result_page1.page == 1
        with patch.object(dashboard_service, "cache_service", mock_cache_service), \
             patch.object(dashboard_service, "_fetch_real_conversation_data") as mock_fetch:
            # Mock stable conversation data
            mock_fetch.return_value = [
                ConversationState(contact_id=f"contact_{i:03d}", seller_name=f"Seller {i}", stage=ConversationStage.Q1, temperature=Temperature.WARM, current_question=1, questions_answered=1, last_activity=datetime.now(), conversation_started=datetime.now(), is_qualified=False, property_address=None, condition=None, price_expectation=None, motivation=None, next_action="Wait", cma_triggered=False)
                for i in range(1, 26)
            ]

            # Test first page
            result_page1 = await dashboard_service.get_active_conversations(page=1, page_size=10)
            assert result_page1.page == 1
            assert len(result_page1.conversations) == 10

            # Test second page
            result_page2 = await dashboard_service.get_active_conversations(page=2, page_size=10)
            assert result_page2.page == 2
            assert len(result_page2.conversations) == 10

            # Verify different conversations on different pages
            page1_ids = {c.contact_id for c in result_page1.conversations}
            page2_ids = {c.contact_id for c in result_page2.conversations}
            assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_get_conversation_summary_success(self, dashboard_service, mock_cache_service):
        """Test getting conversation summary."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_conversation_summary()

            # Verify cache set with 2 min TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 120

            # Verify result structure
            assert isinstance(result, dict)
            assert 'total_active' in result
            assert 'by_stage' in result
            assert 'by_temperature' in result
            assert result['total_active'] >= 0

    @pytest.mark.asyncio
    async def test_get_hero_metrics_data_success(self, dashboard_service, mock_cache_service):
        """Test getting hero metrics data."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_hero_metrics_data()

            # Verify cache set with 5 min TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 300

            # Verify result structure
            assert isinstance(result, dict)
            assert 'total_leads' in result
            assert 'qualified_leads' in result
            assert 'revenue_30_day' in result

    @pytest.mark.asyncio
    async def test_get_performance_analytics_data_success(self, dashboard_service, mock_cache_service, mock_metrics_service):
        """Test getting performance analytics data."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock metrics service methods with actual dataclass instances
        from bots.shared.dashboard_models import (
            PerformanceDashboardMetrics,
            CacheStatistics,
            CostSavingsMetrics,
        )

        mock_metrics_service.get_performance_metrics.return_value = PerformanceDashboardMetrics(
            cache_avg_ms=10.0, cache_p95_ms=25.0, cache_hit_rate=85.0, cache_miss_rate=15.0,
            total_cache_hits=100, total_cache_misses=15, ai_avg_ms=1000.0, ai_p95_ms=2000.0,
            ai_total_calls=50, five_minute_rule_compliance=95.0, fallback_activations=1,
            ghl_avg_ms=400.0, ghl_p95_ms=800.0, ghl_total_calls=75, ghl_error_rate=2.0
        )
        mock_metrics_service.get_cache_statistics.return_value = CacheStatistics(
            hit_rate=85.0, miss_rate=15.0, avg_hit_time_ms=10.0, avg_miss_time_ms=1000.0,
            total_hits=100, total_misses=15, total_requests=115, cache_size_mb=25.5,
            ttl_expirations=10, hit_rate_by_hour=[]
        )
        mock_metrics_service.get_cost_savings.return_value = CostSavingsMetrics(
            total_saved_dollars=100.0, ai_calls_avoided=2000, pattern_matches=300,
            cache_hits=1700, avg_cost_per_ai_call=0.05, lead_bot_savings=85.0,
            seller_bot_savings=15.0
        )

        with patch.object(dashboard_service, 'cache_service', mock_cache_service), \
             patch.object(dashboard_service, 'metrics_service', mock_metrics_service):

            result = await dashboard_service.get_performance_analytics_data()

            # Verify all metrics methods were called
            mock_metrics_service.get_performance_metrics.assert_called_once()
            mock_metrics_service.get_cache_statistics.assert_called_once()
            mock_metrics_service.get_cost_savings.assert_called_once()

            # Verify cache set with 1 min TTL
            mock_cache_service.set.assert_called_once()
            call_args = mock_cache_service.set.call_args
            assert call_args[1]['ttl'] == 60

            # Verify result structure
            assert isinstance(result, dict)
            assert 'performance_metrics' in result
            assert 'cache_statistics' in result
            assert 'cost_savings' in result

    @pytest.mark.asyncio
    async def test_conversation_filters_all_fields(self, dashboard_service, mock_cache_service):
        """Test conversation filtering with all filter fields."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Create comprehensive filters
        filters = ConversationFilters(
            stage=ConversationStage.Q3,
            temperature=Temperature.WARM,
            search_term="seller",
            show_stalled_only=False,
            sort_by="stage",
            sort_order="asc"
        )

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_active_conversations(filters=filters)

            # Verify filtering worked
            assert isinstance(result, PaginatedConversations)
            for conv in result.conversations:
                assert conv.stage == ConversationStage.Q3
                assert conv.temperature == Temperature.WARM
                assert "seller" in conv.seller_name.lower()

    @pytest.mark.asyncio
    async def test_conversation_search_filtering(self, dashboard_service, mock_cache_service):
        """Test conversation search term filtering."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Search for specific address
        filters = ConversationFilters(search_term="123 Main St")

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_active_conversations(filters=filters)

            # Verify search filtering
            for conv in result.conversations:
                has_match = (
                    "123 Main St" in conv.seller_name.lower() or
                    (conv.property_address and "123 Main St" in conv.property_address)
                )
                assert has_match

    @pytest.mark.asyncio
    async def test_conversation_stalled_filtering(self, dashboard_service, mock_cache_service):
        """Test filtering for stalled conversations."""
        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Filter for stalled conversations
        filters = ConversationFilters(show_stalled_only=True)

        with patch.object(dashboard_service, 'cache_service', mock_cache_service):
            result = await dashboard_service.get_active_conversations(filters=filters)

            # Verify stalled filtering (last activity > 48 hours ago)
            stall_cutoff = datetime.now() - timedelta(hours=48)
            for conv in result.conversations:
                assert conv.last_activity < stall_cutoff

    @pytest.mark.asyncio
    async def test_error_handling_complete_dashboard_data(self, dashboard_service, mock_cache_service):
        """Test error handling for complete dashboard data."""
        # Mock cache miss and method exception
        mock_cache_service.get.return_value = None

        with patch.object(dashboard_service, 'cache_service', mock_cache_service), \
             patch.object(dashboard_service, 'metrics_service') as mock_metrics:

            # Mock metrics service exception
            mock_metrics.get_dashboard_summary.side_effect = Exception("Metrics error")

            result = await dashboard_service.get_complete_dashboard_data()

            # Verify fallback data
            assert isinstance(result, dict)
            assert result['status'] == 'error'
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_error_handling_active_conversations(self, dashboard_service, mock_cache_service):
        """Test error handling for active conversations."""
        # Mock cache miss and fetch exception
        mock_cache_service.get.return_value = None

        with patch.object(dashboard_service, 'cache_service', mock_cache_service), \
             patch.object(dashboard_service, '_fetch_active_conversations', side_effect=Exception("Fetch error")):

            result = await dashboard_service.get_active_conversations()

            # Verify fallback data
            assert isinstance(result, PaginatedConversations)
            assert result.total_count == 0
            assert result.conversations == []

    @pytest.mark.asyncio
    async def test_conversation_stage_distribution(self, dashboard_service):
        """Test that conversations are distributed across all stages."""
        with patch.object(dashboard_service, 'cache_service') as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)

            result = await dashboard_service.get_active_conversations(page_size=25)

            # Count conversations by stage
            stage_counts = {}
            for conv in result.conversations:
                stage = conv.stage.value
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

            # Verify we have conversations in multiple stages
            assert len(stage_counts) > 1
            assert any(stage.startswith('Q') for stage in stage_counts.keys())

    @pytest.mark.asyncio
    async def test_conversation_temperature_distribution(self, dashboard_service):
        """Test that conversations have different temperatures."""
        with patch.object(dashboard_service, 'cache_service') as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)

            result = await dashboard_service.get_active_conversations(page_size=25)

            # Count conversations by temperature
            temp_counts = {}
            for conv in result.conversations:
                temp = conv.temperature.value
                temp_counts[temp] = temp_counts.get(temp, 0) + 1

            # Verify we have conversations at different temperatures
            assert len(temp_counts) > 1
            assert 'HOT' in temp_counts or 'WARM' in temp_counts or 'COLD' in temp_counts


class TestDashboardDataServiceSingleton:
    """Test singleton pattern for DashboardDataService."""

    def test_get_dashboard_data_service_singleton(self):
        """Test that get_dashboard_data_service returns same instance."""
        service1 = get_dashboard_data_service()
        service2 = get_dashboard_data_service()

        assert service1 is service2
        assert isinstance(service1, DashboardDataService)


class TestDashboardDataServiceFallbacks:
    """Test fallback methods for DashboardDataService."""

    @pytest.fixture
    def dashboard_service(self):
        """Create DashboardDataService instance for testing."""
        return DashboardDataService()

    def test_fallback_dashboard_data(self, dashboard_service):
        """Test fallback dashboard data structure."""
        result = dashboard_service._get_fallback_dashboard_data()

        assert isinstance(result, dict)
        assert result['metrics'] is None
        assert result['status'] == 'error'
        assert 'error' in result

    def test_fallback_conversations(self, dashboard_service):
        """Test fallback conversations structure."""
        result = dashboard_service._get_fallback_conversations()

        assert isinstance(result, PaginatedConversations)
        assert result.total_count == 0
        assert result.conversations == []
        assert not result.has_next
        assert not result.has_prev

    def test_fallback_conversation_summary(self, dashboard_service):
        """Test fallback conversation summary structure."""
        result = dashboard_service._get_fallback_conversation_summary()

        assert isinstance(result, dict)
        assert result['total_active'] == 0
        assert 'error' in result

    def test_fallback_hero_metrics(self, dashboard_service):
        """Test fallback hero metrics structure."""
        result = dashboard_service._get_fallback_hero_metrics()

        assert isinstance(result, dict)
        assert result['total_leads'] == 0
        assert 'error' in result

    def test_fallback_performance_analytics(self, dashboard_service):
        """Test fallback performance analytics structure."""
        result = dashboard_service._get_fallback_performance_analytics()

        assert isinstance(result, dict)
        assert result['performance_metrics'] is None
        assert 'error' in result