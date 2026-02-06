# Phase 3B - Phase 2 Handoff: Service Layer Implementation

**Date**: January 23, 2026
**Project**: Jorge Real Estate AI MVP - Phase 3B Dashboard
**Status**: Phase 1 Complete, Phase 2 Ready to Start
**Estimated Time**: 2 hours for Phase 2

---

## Quick Status Summary

### ✅ Phase 1 Foundation (COMPLETED)
- **bots/shared/dashboard_models.py**: 12 dataclasses for all dashboard data
- **bots/shared/performance_tracker.py**: Real-time metrics tracking service
- **Tests**: 42 tests passing (22 models + 20 tracker)
- **Time Taken**: ~1.5 hours

### ⏳ Phase 2 Service Layer (NEXT)
- **bots/shared/metrics_service.py**: Performance metrics aggregation
- **bots/shared/dashboard_data_service.py**: Data orchestration
- **Seller Bot Persistence**: Redis-backed state storage
- **Tests**: Comprehensive test coverage
- **Estimated Time**: 2 hours

### 📋 Phases 3-5 (UPCOMING)
- Phase 3: UI Components (2.5 hours)
- Phase 4: Integration (1 hour)
- Phase 5: Testing & Polish (0.5 hours)

---

## Phase 2 Architecture: Service Layer

### 1. MetricsService (`bots/shared/metrics_service.py`)

**Purpose**: Aggregate and serve performance metrics for dashboard visualization.

**Key Methods**:

```python
class MetricsService:
    """
    Aggregates performance metrics from PerformanceTracker.

    Provides cached, aggregated views of:
    - Cache performance (hit rates, response times)
    - AI analysis statistics
    - GHL API performance
    - Cost savings tracking
    """

    def __init__(self):
        self.tracker = get_performance_tracker()
        self.cache = get_cache_service()

    async def get_performance_metrics(self) -> PerformanceDashboardMetrics:
        """
        Get aggregated performance metrics.
        TTL: 30s (real-time dashboard)
        """
        pass

    async def get_cache_statistics(self) -> CacheStatistics:
        """
        Get detailed cache statistics with time-series.
        TTL: 5min (moderate freshness)
        """
        pass

    async def get_cost_savings(self) -> CostSavingsMetrics:
        """
        Get cost savings from caching/patterns.
        TTL: 1hr (historical data)
        """
        pass

    async def get_performance_time_series(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get time-series data for charts.
        Returns hourly aggregated metrics.
        """
        pass
```

**Caching Strategy**:
- `get_performance_metrics()`: 30s TTL (real-time)
- `get_cache_statistics()`: 5min TTL (moderate)
- `get_cost_savings()`: 1hr TTL (historical)

**Integration**:
- Uses `PerformanceTracker` for raw metrics
- Uses `CacheService` for result caching
- Handles tracker unavailability gracefully

---

### 2. DashboardDataService (`bots/shared/dashboard_data_service.py`)

**Purpose**: Orchestrate data from multiple sources for dashboard display.

**Key Methods**:

```python
class DashboardDataService:
    """
    Orchestrates data from multiple sources.

    Integrates:
    - PerformanceTracker (via MetricsService)
    - Seller Bot (conversation states)
    - Lead Intelligence (budget/timeline)
    - Business Rules (commission)
    """

    def __init__(self):
        self.metrics_service = MetricsService()
        self.cache = get_cache_service()
        self.business_rules = JorgeBusinessRules()

    async def get_dashboard_overview(self) -> Dict[str, Any]:
        """
        Get complete dashboard data in one call.
        Includes: metrics, conversations, budget, timeline, commission.
        TTL: 1min
        """
        pass

    async def get_budget_distribution(self) -> BudgetDistribution:
        """
        Get budget range analysis from cached lead data.
        Integrates with LeadIntelligence pattern extraction.
        TTL: 5min
        """
        pass

    async def get_timeline_distribution(self) -> TimelineDistribution:
        """
        Get timeline classification distribution.
        Integrates with LeadIntelligence timeline extraction.
        TTL: 5min
        """
        pass

    async def get_active_conversations(
        self,
        filters: Optional[ConversationFilters] = None,
        page: int = 1,
        page_size: int = 10
    ) -> PaginatedConversations:
        """
        Get paginated seller bot conversations.
        Reads from Redis persistence layer.
        TTL: 30s (real-time)
        """
        pass

    async def get_commission_metrics(self) -> CommissionMetrics:
        """
        Get commission tracking and forecasting.
        Integrates with JorgeBusinessRules.
        TTL: 1hr
        """
        pass
```

**Data Sources**:
1. **PerformanceTracker** → Performance metrics
2. **Redis (seller states)** → Active conversations
3. **Redis (cached leads)** → Budget/timeline distributions
4. **JorgeBusinessRules** → Commission calculations

**Error Handling**:
```python
async def get_budget_distribution(self) -> BudgetDistribution:
    try:
        # Try to get from cache
        cached = await self.cache.get("dashboard:budget_dist")
        if cached:
            return BudgetDistribution(**cached)

        # Compute from lead data
        leads = await self._get_cached_leads()
        distribution = self._calculate_budget_distribution(leads)

        # Cache result
        await self.cache.set("dashboard:budget_dist", asdict(distribution), ttl=300)
        return distribution

    except Exception as e:
        logger.exception(f"Error getting budget distribution: {e}")
        # Return fallback data
        return BudgetDistribution(
            ranges=[],
            total_leads=0,
            avg_budget=0,
            median_budget=0,
            validation_pass_rate=0.0,
            out_of_service_area=0,
        )
```

---

### 3. Seller Bot Persistence

**Current State** (bots/seller_bot/jorge_seller_bot.py:198):
```python
# In-memory storage (NOT persistent)
self.conversation_states: Dict[str, SellerQualificationState] = {}
```

**New Persistent Implementation**:
```python
class SellerBotService:
    """Seller bot with Redis-backed persistence."""

    def __init__(self):
        self.cache = get_cache_service()
        # Remove in-memory dict

    async def get_conversation_state(
        self,
        contact_id: str
    ) -> Optional[SellerQualificationState]:
        """Load conversation state from Redis."""
        key = f"seller:state:{contact_id}"
        state_dict = await self.cache.get(key)

        if state_dict:
            return SellerQualificationState(**state_dict)
        return None

    async def save_conversation_state(
        self,
        contact_id: str,
        state: SellerQualificationState
    ):
        """Save conversation state to Redis (TTL: 7 days)."""
        key = f"seller:state:{contact_id}"
        state_dict = asdict(state)

        # Convert datetime to ISO string
        if state.last_interaction:
            state_dict['last_interaction'] = state.last_interaction.isoformat()

        await self.cache.set(key, state_dict, ttl=604800)  # 7 days

    async def get_all_active_conversations(
        self
    ) -> List[SellerQualificationState]:
        """
        Get all active conversations.

        NOTE: This requires Redis KEYS scan (expensive).
        For production, maintain a separate set index:
        "seller:active_contacts" → Set[contact_id]
        """
        # Implementation using Redis SCAN
        pass
```

**Key Pattern**: `seller:state:{contact_id}`
**TTL**: 7 days (604,800 seconds)
**Index Set**: `seller:active_contacts` (for efficient listing)

**Migration Steps**:
1. Update `SellerBotService.__init__()` to remove dict
2. Update all `self.conversation_states[contact_id]` reads → `await self.get_conversation_state(contact_id)`
3. Update all `self.conversation_states[contact_id] = state` writes → `await self.save_conversation_state(contact_id, state)`
4. Add active contacts index for efficient `get_all_active_conversations()`

---

## Implementation Checklist - Phase 2

### Step 1: MetricsService (30 min)
- [ ] Create `bots/shared/metrics_service.py`
- [ ] Implement `get_performance_metrics()` with 30s caching
- [ ] Implement `get_cache_statistics()` with 5min caching
- [ ] Implement `get_cost_savings()` with 1hr caching
- [ ] Add `get_performance_time_series()` for charts
- [ ] Write tests: `tests/shared/test_metrics_service.py` (15 tests)

### Step 2: DashboardDataService (45 min)
- [ ] Create `bots/shared/dashboard_data_service.py`
- [ ] Implement `get_dashboard_overview()` (aggregates all data)
- [ ] Implement `get_budget_distribution()` (from cached leads)
- [ ] Implement `get_timeline_distribution()` (from cached leads)
- [ ] Implement `get_active_conversations()` with pagination
- [ ] Implement `get_commission_metrics()` (from business rules)
- [ ] Add error handling with fallback data
- [ ] Write tests: `tests/shared/test_dashboard_data_service.py` (20 tests)

### Step 3: Seller Bot Persistence (30 min)
- [ ] Update `bots/seller_bot/jorge_seller_bot.py`
- [ ] Add `get_conversation_state(contact_id)` method
- [ ] Add `save_conversation_state(contact_id, state)` method
- [ ] Update all state reads to use async get
- [ ] Update all state writes to use async save
- [ ] Add `seller:active_contacts` set index
- [ ] Write tests: `tests/seller_bot/test_persistence.py` (10 tests)

### Step 4: Integration Testing (15 min)
- [ ] Run all Phase 1 + Phase 2 tests
- [ ] Verify 80%+ coverage
- [ ] Manual testing with real data
- [ ] Performance check (<200ms for dashboard load)

---

## Key Files Reference

### Already Built (Phase 1)
1. `bots/shared/dashboard_models.py` (350 lines)
   - All 12 dataclasses
   - Enum types (Temperature, ConversationStage, Timeline)
   - Serialization methods

2. `bots/shared/performance_tracker.py` (450 lines)
   - Real-time metrics tracking
   - Rolling 24-hour window
   - Cost savings calculation
   - Snapshot persistence

### To Build (Phase 2)
3. `bots/shared/metrics_service.py` (~250 lines)
   - Aggregation layer over PerformanceTracker
   - Multi-tier caching

4. `bots/shared/dashboard_data_service.py` (~400 lines)
   - Data orchestration
   - Budget/timeline distributions
   - Active conversations with pagination
   - Commission metrics

5. Enhanced `bots/seller_bot/jorge_seller_bot.py` (+100 lines)
   - Redis persistence
   - Async state management

### Existing to Integrate With
6. `bots/shared/cache_service.py` (374 lines)
   - CacheService class (lines 139-222)
   - cached_computation() method (lines 223-302)

7. `bots/shared/business_rules.py` (173 lines)
   - JorgeBusinessRules class (lines 21-173)
   - calculate_commission() (lines 160-173)

8. `bots/shared/lead_intelligence_optimized.py` (510 lines)
   - Budget extraction (lines 200-234)
   - Timeline classification (lines 236-266)

---

## Testing Strategy

### Test Organization
```
tests/shared/
├── test_dashboard_models.py (22 tests) ✅
├── test_performance_tracker.py (20 tests) ✅
├── test_metrics_service.py (15 tests) ⏳
└── test_dashboard_data_service.py (20 tests) ⏳

tests/seller_bot/
└── test_persistence.py (10 tests) ⏳
```

### Test Patterns
```python
@pytest.mark.asyncio
async def test_get_performance_metrics(mock_cache, mock_tracker):
    """Test MetricsService.get_performance_metrics()."""
    service = MetricsService()
    service.cache = mock_cache
    service.tracker = mock_tracker

    # Mock tracker response
    mock_tracker.get_performance_metrics.return_value = PerformanceDashboardMetrics(
        cache_avg_ms=0.19,
        cache_hit_rate=95.0,
        # ... other fields
    )

    # Call service
    metrics = await service.get_performance_metrics()

    # Verify
    assert metrics.cache_avg_ms == 0.19
    assert metrics.cache_hit_rate == 95.0

    # Verify caching
    mock_cache.set.assert_called_once()
```

---

## Common Patterns to Follow

### 1. Async/Await Pattern
```python
async def get_data(self) -> DataModel:
    try:
        # Check cache first
        cached = await self.cache.get("key")
        if cached:
            return DataModel(**cached)

        # Compute if cache miss
        data = await self._compute_data()

        # Cache result
        await self.cache.set("key", asdict(data), ttl=300)
        return data

    except Exception as e:
        logger.exception(f"Error: {e}")
        return self._get_fallback_data()
```

### 2. Error Handling with Fallbacks
```python
async def get_metrics(self) -> Metrics:
    try:
        return await self._fetch_real_metrics()
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        # Return safe fallback
        return Metrics(
            value=0,
            timestamp=datetime.now()
        )
```

### 3. Pagination Pattern
```python
async def get_paginated_data(
    self,
    page: int = 1,
    page_size: int = 10
) -> PaginatedResult:
    # Get all items
    all_items = await self._get_all_items()

    # Calculate pagination
    total = len(all_items)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size

    items = all_items[start:end]

    return PaginatedResult(
        items=items,
        total_count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
```

---

## Git Workflow

### Commits After Each Component
```bash
# After MetricsService
git add bots/shared/metrics_service.py tests/shared/test_metrics_service.py
git commit -m "feat(dashboard): Add MetricsService for performance aggregation

- Implement get_performance_metrics() with 30s caching
- Add get_cache_statistics() with 5min caching
- Add get_cost_savings() with 1hr caching
- Include time-series data for charts
- Comprehensive tests (15 tests, 100% coverage)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# After DashboardDataService
git add bots/shared/dashboard_data_service.py tests/shared/test_dashboard_data_service.py
git commit -m "feat(dashboard): Add DashboardDataService for data orchestration

- Implement get_dashboard_overview() (all data in one call)
- Add budget/timeline distribution analysis
- Add active conversations with pagination
- Add commission metrics calculation
- Graceful error handling with fallbacks
- Comprehensive tests (20 tests, 90% coverage)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# After Seller Bot Persistence
git add bots/seller_bot/jorge_seller_bot.py tests/seller_bot/test_persistence.py
git commit -m "feat(seller-bot): Add Redis-backed conversation persistence

- Replace in-memory dict with CacheService storage
- Add get/save_conversation_state() methods
- TTL: 7 days for active conversations
- Add seller:active_contacts index
- Comprehensive tests (10 tests, 85% coverage)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Success Criteria - Phase 2

### Functionality
- [ ] MetricsService returns aggregated metrics from PerformanceTracker
- [ ] DashboardDataService orchestrates data from multiple sources
- [ ] Seller bot persists conversation states to Redis
- [ ] All services handle errors gracefully with fallbacks
- [ ] Pagination works correctly for conversations table
- [ ] Commission metrics calculate accurately

### Performance
- [ ] get_performance_metrics() completes in <50ms (cached)
- [ ] get_dashboard_overview() completes in <200ms
- [ ] Seller state persistence is reliable (no data loss)
- [ ] Multi-tier caching reduces Redis load

### Testing
- [ ] All Phase 1 tests still pass (42 tests)
- [ ] All Phase 2 tests pass (45 new tests)
- [ ] Total: 87+ tests passing
- [ ] Coverage ≥80% for new code

---

## Troubleshooting

### Issue: Import Errors
**Solution**: Ensure you're in the jorge_real_estate_bots project, not EnterpriseHub
```bash
pwd  # Should show: /Users/cave/Documents/GitHub/jorge_real_estate_bots
```

### Issue: Async Test Failures
**Solution**: Use pytest-asyncio and @pytest.mark.asyncio
```python
@pytest.mark.asyncio
async def test_async_method():
    result = await some_async_function()
    assert result is not None
```

### Issue: Mock AsyncMock
**Solution**: Use unittest.mock.AsyncMock for async methods
```python
from unittest.mock import AsyncMock

mock_cache = AsyncMock()
mock_cache.get.return_value = {"data": "value"}
```

---

## Ready to Continue?

**Next Action**: Start Phase 2 by creating `bots/shared/metrics_service.py`

**First Task**: Write test file `tests/shared/test_metrics_service.py` (TDD approach), then implement MetricsService.

Good luck! 🚀
