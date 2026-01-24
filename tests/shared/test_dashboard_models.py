"""
Unit tests for dashboard models (Phase 3B).

Tests all 12 dataclasses:
- PerformanceDashboardMetrics
- CacheStatistics
- CostSavingsMetrics
- ConversationState
- ConversationFilters
- PaginatedConversations
- BudgetRange
- BudgetDistribution
- TimelineClassification
- TimelineDistribution
- CommissionMetrics

Ensures to_dict() serialization works correctly and
data integrity is maintained.
"""
import pytest
from datetime import datetime, timedelta
from bots.shared.dashboard_models import (
    PerformanceDashboardMetrics,
    CacheStatistics,
    CostSavingsMetrics,
    ConversationState,
    ConversationFilters,
    PaginatedConversations,
    BudgetRange,
    BudgetDistribution,
    TimelineClassification,
    TimelineDistribution,
    CommissionMetrics,
    Temperature,
    ConversationStage,
    Timeline,
)


class TestPerformanceDashboardMetrics:
    """Test PerformanceDashboardMetrics dataclass."""

    def test_creation(self):
        """Test creating PerformanceDashboardMetrics."""
        metrics = PerformanceDashboardMetrics(
            cache_avg_ms=0.19,
            cache_p95_ms=0.5,
            cache_hit_rate=95.0,
            cache_miss_rate=5.0,
            total_cache_hits=1247,
            total_cache_misses=65,
            ai_avg_ms=489.0,
            ai_p95_ms=750.0,
            ai_total_calls=45,
            five_minute_rule_compliance=100.0,
            fallback_activations=3,
            ghl_avg_ms=150.0,
            ghl_p95_ms=250.0,
            ghl_total_calls=120,
            ghl_error_rate=0.2,
        )

        assert metrics.cache_avg_ms == 0.19
        assert metrics.cache_hit_rate == 95.0
        assert metrics.ai_avg_ms == 489.0
        assert metrics.five_minute_rule_compliance == 100.0
        assert isinstance(metrics.timestamp, datetime)

    def test_to_dict(self):
        """Test to_dict() serialization."""
        metrics = PerformanceDashboardMetrics(
            cache_avg_ms=0.19,
            cache_p95_ms=0.5,
            cache_hit_rate=95.0,
            cache_miss_rate=5.0,
            total_cache_hits=1247,
            total_cache_misses=65,
            ai_avg_ms=489.0,
            ai_p95_ms=750.0,
            ai_total_calls=45,
            five_minute_rule_compliance=100.0,
            fallback_activations=3,
            ghl_avg_ms=150.0,
            ghl_p95_ms=250.0,
            ghl_total_calls=120,
            ghl_error_rate=0.2,
        )

        data = metrics.to_dict()
        assert data['cache_avg_ms'] == 0.19
        assert data['cache_hit_rate'] == 95.0
        assert 'timestamp' in data
        assert isinstance(data['timestamp'], str)  # ISO format


class TestCacheStatistics:
    """Test CacheStatistics dataclass."""

    def test_creation(self):
        """Test creating CacheStatistics."""
        stats = CacheStatistics(
            hit_rate=95.0,
            miss_rate=5.0,
            avg_hit_time_ms=0.19,
            avg_miss_time_ms=489.0,
            total_hits=1247,
            total_misses=65,
            total_requests=1312,
            cache_size_mb=24.5,
            ttl_expirations=120,
            hit_rate_by_hour=[
                {'hour': 0, 'rate': 92.0},
                {'hour': 1, 'rate': 94.5},
            ]
        )

        assert stats.hit_rate == 95.0
        assert stats.total_hits == 1247
        assert len(stats.hit_rate_by_hour) == 2

    def test_to_dict(self):
        """Test to_dict() serialization."""
        stats = CacheStatistics(
            hit_rate=95.0,
            miss_rate=5.0,
            avg_hit_time_ms=0.19,
            avg_miss_time_ms=489.0,
            total_hits=1247,
            total_misses=65,
            total_requests=1312,
            cache_size_mb=24.5,
            ttl_expirations=120,
        )

        data = stats.to_dict()
        assert data['hit_rate'] == 95.0
        assert data['total_hits'] == 1247


class TestCostSavingsMetrics:
    """Test CostSavingsMetrics dataclass."""

    def test_creation(self):
        """Test creating CostSavingsMetrics."""
        savings = CostSavingsMetrics(
            total_saved_dollars=127.50,
            ai_calls_avoided=2550,
            pattern_matches=1200,
            cache_hits=1350,
            lead_bot_savings=85.0,
            seller_bot_savings=42.50,
        )

        assert savings.total_saved_dollars == 127.50
        assert savings.ai_calls_avoided == 2550
        assert savings.lead_bot_savings == 85.0

    def test_to_dict(self):
        """Test to_dict() serialization."""
        savings = CostSavingsMetrics(
            total_saved_dollars=127.50,
            ai_calls_avoided=2550,
            pattern_matches=1200,
            cache_hits=1350,
        )

        data = savings.to_dict()
        assert data['total_saved_dollars'] == 127.50
        assert data['ai_calls_avoided'] == 2550


class TestConversationState:
    """Test ConversationState dataclass."""

    def test_creation(self):
        """Test creating ConversationState."""
        now = datetime.now()
        state = ConversationState(
            contact_id="contact_123",
            seller_name="John Smith",
            stage=ConversationStage.Q2,
            temperature=Temperature.WARM,
            current_question=2,
            questions_answered=2,
            last_activity=now,
            conversation_started=now - timedelta(hours=2),
            is_qualified=False,
            property_address="123 Main St",
            condition="needs_minor_repairs",
            price_expectation=450000,
        )

        assert state.contact_id == "contact_123"
        assert state.stage == ConversationStage.Q2
        assert state.temperature == Temperature.WARM
        assert state.current_question == 2

    def test_to_dict(self):
        """Test to_dict() serialization."""
        now = datetime.now()
        state = ConversationState(
            contact_id="contact_123",
            seller_name="John Smith",
            stage=ConversationStage.Q2,
            temperature=Temperature.WARM,
            current_question=2,
            questions_answered=2,
            last_activity=now,
            conversation_started=now - timedelta(hours=2),
            is_qualified=False,
        )

        data = state.to_dict()
        assert data['contact_id'] == "contact_123"
        assert data['stage'] == "Q2"
        assert data['temperature'] == "WARM"
        assert isinstance(data['last_activity'], str)


class TestConversationFilters:
    """Test ConversationFilters dataclass."""

    def test_creation(self):
        """Test creating ConversationFilters."""
        filters = ConversationFilters(
            stage=ConversationStage.Q2,
            temperature=Temperature.HOT,
            search_term="john",
            show_stalled_only=False,
            sort_by="temperature",
            sort_order="asc",
        )

        assert filters.stage == ConversationStage.Q2
        assert filters.temperature == Temperature.HOT
        assert filters.search_term == "john"

    def test_to_dict(self):
        """Test to_dict() serialization."""
        filters = ConversationFilters(
            stage=ConversationStage.Q2,
            temperature=Temperature.HOT,
        )

        data = filters.to_dict()
        assert data['stage'] == "Q2"
        assert data['temperature'] == "HOT"


class TestPaginatedConversations:
    """Test PaginatedConversations dataclass."""

    def test_creation(self):
        """Test creating PaginatedConversations."""
        now = datetime.now()
        conversations = [
            ConversationState(
                contact_id=f"contact_{i}",
                seller_name=f"Seller {i}",
                stage=ConversationStage.Q1,
                temperature=Temperature.WARM,
                current_question=1,
                questions_answered=1,
                last_activity=now,
                conversation_started=now,
                is_qualified=False,
            )
            for i in range(10)
        ]

        paginated = PaginatedConversations(
            conversations=conversations,
            total_count=47,
            page=1,
            page_size=10,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )

        assert len(paginated.conversations) == 10
        assert paginated.total_count == 47
        assert paginated.has_next is True

    def test_to_dict(self):
        """Test to_dict() serialization."""
        now = datetime.now()
        conversations = [
            ConversationState(
                contact_id="contact_1",
                seller_name="Seller 1",
                stage=ConversationStage.Q1,
                temperature=Temperature.WARM,
                current_question=1,
                questions_answered=1,
                last_activity=now,
                conversation_started=now,
                is_qualified=False,
            )
        ]

        paginated = PaginatedConversations(
            conversations=conversations,
            total_count=47,
            page=1,
            page_size=10,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )

        data = paginated.to_dict()
        assert len(data['conversations']) == 1
        assert data['total_count'] == 47


class TestBudgetRange:
    """Test BudgetRange dataclass."""

    def test_creation(self):
        """Test creating BudgetRange."""
        budget_range = BudgetRange(
            min_value=300000,
            max_value=400000,
            label="$300K-$400K",
            count=23,
            percentage=32.5,
            avg_lead_score=75.2,
        )

        assert budget_range.min_value == 300000
        assert budget_range.label == "$300K-$400K"
        assert budget_range.count == 23

    def test_to_dict(self):
        """Test to_dict() serialization."""
        budget_range = BudgetRange(
            min_value=300000,
            max_value=400000,
            label="$300K-$400K",
            count=23,
            percentage=32.5,
            avg_lead_score=75.2,
        )

        data = budget_range.to_dict()
        assert data['min_value'] == 300000
        assert data['label'] == "$300K-$400K"


class TestBudgetDistribution:
    """Test BudgetDistribution dataclass."""

    def test_creation(self):
        """Test creating BudgetDistribution."""
        ranges = [
            BudgetRange(300000, 400000, "$300K-$400K", 23, 32.5, 75.2),
            BudgetRange(400000, 500000, "$400K-$500K", 18, 25.4, 82.1),
        ]

        distribution = BudgetDistribution(
            ranges=ranges,
            total_leads=71,
            avg_budget=425000,
            median_budget=400000,
            validation_pass_rate=87.3,
            out_of_service_area=5,
        )

        assert len(distribution.ranges) == 2
        assert distribution.total_leads == 71
        assert distribution.avg_budget == 425000

    def test_to_dict(self):
        """Test to_dict() serialization."""
        ranges = [
            BudgetRange(300000, 400000, "$300K-$400K", 23, 32.5, 75.2),
        ]

        distribution = BudgetDistribution(
            ranges=ranges,
            total_leads=71,
            avg_budget=425000,
            median_budget=400000,
            validation_pass_rate=87.3,
            out_of_service_area=5,
        )

        data = distribution.to_dict()
        assert len(data['ranges']) == 1
        assert data['total_leads'] == 71


class TestTimelineClassification:
    """Test TimelineClassification dataclass."""

    def test_creation(self):
        """Test creating TimelineClassification."""
        classification = TimelineClassification(
            timeline=Timeline.IMMEDIATE,
            count=12,
            percentage=25.0,
            priority_score=4,
            avg_lead_score=85.3,
        )

        assert classification.timeline == Timeline.IMMEDIATE
        assert classification.count == 12
        assert classification.priority_score == 4

    def test_to_dict(self):
        """Test to_dict() serialization."""
        classification = TimelineClassification(
            timeline=Timeline.IMMEDIATE,
            count=12,
            percentage=25.0,
            priority_score=4,
            avg_lead_score=85.3,
        )

        data = classification.to_dict()
        assert data['timeline'] == "0-30 days"
        assert data['count'] == 12


class TestTimelineDistribution:
    """Test TimelineDistribution dataclass."""

    def test_creation(self):
        """Test creating TimelineDistribution."""
        classifications = [
            TimelineClassification(Timeline.IMMEDIATE, 12, 25.0, 4, 85.3),
            TimelineClassification(Timeline.SHORT_TERM, 18, 37.5, 3, 72.1),
        ]

        distribution = TimelineDistribution(
            classifications=classifications,
            total_leads=48,
            immediate_count=12,
        )

        assert len(distribution.classifications) == 2
        assert distribution.total_leads == 48
        assert distribution.immediate_count == 12

    def test_to_dict(self):
        """Test to_dict() serialization."""
        classifications = [
            TimelineClassification(Timeline.IMMEDIATE, 12, 25.0, 4, 85.3),
        ]

        distribution = TimelineDistribution(
            classifications=classifications,
            total_leads=48,
            immediate_count=12,
        )

        data = distribution.to_dict()
        assert len(data['classifications']) == 1
        assert data['total_leads'] == 48


class TestCommissionMetrics:
    """Test CommissionMetrics dataclass."""

    def test_creation(self):
        """Test creating CommissionMetrics."""
        metrics = CommissionMetrics(
            total_commission_potential=127000.0,
            avg_commission_per_deal=27000.0,
            total_qualified_leads=23,
            hot_leads_count=8,
            budget_validation_pass_rate=87.3,
            service_area_match_rate=92.1,
            projected_monthly_commission=85000.0,
            projected_deals=3,
            commission_trend=[
                {'date': '2026-01-01', 'amount': 27000},
                {'date': '2026-01-15', 'amount': 54000},
            ]
        )

        assert metrics.total_commission_potential == 127000.0
        assert metrics.avg_commission_per_deal == 27000.0
        assert len(metrics.commission_trend) == 2

    def test_to_dict(self):
        """Test to_dict() serialization."""
        metrics = CommissionMetrics(
            total_commission_potential=127000.0,
            avg_commission_per_deal=27000.0,
            total_qualified_leads=23,
            hot_leads_count=8,
            budget_validation_pass_rate=87.3,
            service_area_match_rate=92.1,
            projected_monthly_commission=85000.0,
            projected_deals=3,
        )

        data = metrics.to_dict()
        assert data['total_commission_potential'] == 127000.0
        assert data['avg_commission_per_deal'] == 27000.0
