"""
Dashboard data models for Phase 3B advanced analytics.

Contains dataclasses for:
- Performance metrics and caching statistics
- Seller conversation state tracking
- Budget and timeline distributions
- Commission tracking

All models follow the project pattern with to_dict() methods for JSON serialization.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Temperature(str, Enum):
    """Seller temperature classification."""
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class ConversationStage(str, Enum):
    """Seller bot Q0-Q4 conversation stages."""
    Q0 = "Q0"  # Initial greeting
    Q1 = "Q1"  # Property condition
    Q2 = "Q2"  # Price expectation
    Q3 = "Q3"  # Motivation to sell
    Q4 = "Q4"  # Offer acceptance
    QUALIFIED = "QUALIFIED"  # Completed Q4
    STALLED = "STALLED"  # No response >48h


class Timeline(str, Enum):
    """Lead timeline classification."""
    IMMEDIATE = "0-30 days"
    SHORT_TERM = "1-3 months"
    MEDIUM_TERM = "3-6 months"
    LONG_TERM = "6+ months"
    UNKNOWN = "Unknown"


@dataclass
class PerformanceDashboardMetrics:
    """
    Aggregated performance metrics for dashboard display.

    Tracks response times for cache, AI, and GHL operations
    over a time period (typically 24 hours).
    """
    cache_avg_ms: float
    cache_p95_ms: float
    cache_hit_rate: float
    cache_miss_rate: float
    total_cache_hits: int
    total_cache_misses: int

    ai_avg_ms: float
    ai_p95_ms: float
    ai_total_calls: int
    five_minute_rule_compliance: float  # Percentage (0-100)
    fallback_activations: int

    ghl_avg_ms: float
    ghl_p95_ms: float
    ghl_total_calls: int
    ghl_error_rate: float

    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class CacheStatistics:
    """
    Detailed cache statistics for performance monitoring.

    Provides insights into cache effectiveness and cost savings.
    """
    hit_rate: float  # Percentage (0-100)
    miss_rate: float  # Percentage (0-100)
    avg_hit_time_ms: float
    avg_miss_time_ms: float
    total_hits: int
    total_misses: int
    total_requests: int
    cache_size_mb: float
    ttl_expirations: int

    # Time-series data for charting
    hit_rate_by_hour: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CostSavingsMetrics:
    """
    Track cost savings from caching and pattern matching.

    Calculates savings by comparing cached/pattern responses
    vs full Claude API calls.
    """
    total_saved_dollars: float
    ai_calls_avoided: int
    pattern_matches: int
    cache_hits: int
    avg_cost_per_ai_call: float = 0.05  # $0.05 per API call estimate

    # Breakdown by bot type
    lead_bot_savings: float = 0.0
    seller_bot_savings: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ConversationState:
    """
    Represents a single seller bot conversation state.

    Used in the active conversations table for real-time monitoring.
    """
    contact_id: str
    seller_name: str
    stage: ConversationStage
    temperature: Temperature
    current_question: int  # 0-4
    questions_answered: int

    # Metadata
    last_activity: datetime
    conversation_started: datetime
    is_qualified: bool

    # Extracted data
    property_address: Optional[str] = None
    condition: Optional[str] = None
    price_expectation: Optional[int] = None
    motivation: Optional[str] = None
    urgency: Optional[str] = None

    # Actions
    next_action: str = "Wait for response"
    cma_triggered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['stage'] = self.stage.value
        data['temperature'] = self.temperature.value
        data['last_activity'] = self.last_activity.isoformat()
        data['conversation_started'] = self.conversation_started.isoformat()
        return data


@dataclass
class ConversationFilters:
    """
    Filters for active conversations table.

    Supports filtering by stage, temperature, and search term.
    """
    stage: Optional[ConversationStage] = None
    temperature: Optional[Temperature] = None
    search_term: Optional[str] = None
    show_stalled_only: bool = False
    sort_by: str = "last_activity"  # "last_activity", "stage", "temperature"
    sort_order: str = "desc"  # "asc", "desc"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.stage:
            data['stage'] = self.stage.value
        if self.temperature:
            data['temperature'] = self.temperature.value
        return data


@dataclass
class PaginatedConversations:
    """
    Paginated list of conversations with metadata.

    Used for table pagination in the UI.
    """
    conversations: List[ConversationState]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'conversations': [conv.to_dict() for conv in self.conversations],
            'total_count': self.total_count,
            'page': self.page,
            'page_size': self.page_size,
            'total_pages': self.total_pages,
            'has_next': self.has_next,
            'has_prev': self.has_prev,
        }


@dataclass
class BudgetRange:
    """
    Budget range for lead distribution analysis.
    """
    min_value: int
    max_value: int
    label: str  # e.g., "$300K-$400K"
    count: int
    percentage: float
    avg_lead_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class BudgetDistribution:
    """
    Complete budget distribution across all ranges.

    Used for interactive budget range charts.
    """
    ranges: List[BudgetRange]
    total_leads: int
    avg_budget: int
    median_budget: int

    # Budget validation metrics
    validation_pass_rate: float  # Percentage (0-100)
    out_of_service_area: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'ranges': [r.to_dict() for r in self.ranges],
            'total_leads': self.total_leads,
            'avg_budget': self.avg_budget,
            'median_budget': self.median_budget,
            'validation_pass_rate': self.validation_pass_rate,
            'out_of_service_area': self.out_of_service_area,
        }


@dataclass
class TimelineClassification:
    """
    Timeline classification for a single timeline category.
    """
    timeline: Timeline
    count: int
    percentage: float
    priority_score: int  # 1-4 (Immediate=4, Long-term=1)
    avg_lead_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timeline'] = self.timeline.value
        return data


@dataclass
class TimelineDistribution:
    """
    Complete timeline distribution across all categories.

    Used for timeline/Gantt view visualization.
    """
    classifications: List[TimelineClassification]
    total_leads: int
    immediate_count: int  # High priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'classifications': [c.to_dict() for c in self.classifications],
            'total_leads': self.total_leads,
            'immediate_count': self.immediate_count,
        }


@dataclass
class CommissionMetrics:
    """
    Commission tracking and forecasting metrics.

    Based on JorgeBusinessRules calculations.
    """
    total_commission_potential: float  # Total $ from all hot leads
    avg_commission_per_deal: float
    total_qualified_leads: int
    hot_leads_count: int

    # Validation metrics
    budget_validation_pass_rate: float  # Percentage (0-100)
    service_area_match_rate: float  # Percentage (0-100)

    # Forecasting (30-day projection)
    projected_monthly_commission: float
    projected_deals: int

    # Time-series for chart
    commission_trend: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class HeroMetrics:
    """
    Hero metrics for dashboard KPI display.

    Shows 4 key metrics with delta indicators for 24h change.
    """
    active_conversations: int
    active_conversations_change: int
    qualification_rate: float  # 0-1 (will be displayed as percentage)
    qualification_rate_change: float  # Delta as decimal
    avg_response_time_minutes: float
    response_time_change: float  # Delta in minutes
    hot_leads_count: int
    hot_leads_change: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """
    Performance analytics metrics for dashboard charts.

    Tracks qualification, response time, and performance indicators.
    """
    qualification_rate: float  # 0-1
    avg_response_time: float  # Minutes
    budget_performance: float  # 0-1+ (1.0 = 100% of target)
    timeline_performance: float  # 0-1+ (1.0 = on schedule)
    commission_performance: float  # 0-1+ (1.0 = 100% of target)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# Type alias for clarity
ActiveConversationsResponse = PaginatedConversations


@dataclass
class DashboardData:
    """
    Complete dashboard data container.

    Top-level structure returned by DashboardDataService.get_dashboard_data().
    Contains all data needed for dashboard UI rendering.
    """
    hero_metrics: HeroMetrics
    active_conversations: ActiveConversationsResponse
    performance_metrics: PerformanceMetrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'hero_metrics': self.hero_metrics.to_dict(),
            'active_conversations': self.active_conversations.to_dict(),
            'performance_metrics': self.performance_metrics.to_dict(),
        }
