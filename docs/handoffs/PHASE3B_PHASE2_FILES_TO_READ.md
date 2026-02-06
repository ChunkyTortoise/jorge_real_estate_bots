# Phase 3B Phase 2: Files to Read in New Chat Session

**Read these files in order for Phase 2 implementation**

---

## Priority 1: Phase 2 Context (Read First)

### 1. PHASE3B_PHASE2_HANDOFF.md ⭐⭐⭐
**Purpose**: Complete Phase 2 architecture and implementation guide
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3B_PHASE2_HANDOFF.md`
**What to Learn**:
- Service layer architecture
- MetricsService design
- DashboardDataService design
- Seller bot persistence strategy
- Implementation checklist

### 2. PHASE3B_CONTINUE_PHASE2_PROMPT.txt ⭐⭐
**Purpose**: Quick-start prompt for new chat session
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3B_CONTINUE_PHASE2_PROMPT.txt`
**What to Learn**: Task summary, what to build next

---

## Priority 2: Completed Phase 1 Code (Understand First)

### 3. bots/shared/dashboard_models.py ⭐⭐⭐
**Purpose**: All 12 dataclasses for dashboard (COMPLETED in Phase 1)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/dashboard_models.py`
**Key Lines**: All 350 lines
**What to Learn**:
- PerformanceDashboardMetrics structure
- ConversationState fields
- BudgetDistribution / TimelineDistribution
- CommissionMetrics structure
- to_dict() serialization pattern

### 4. bots/shared/performance_tracker.py ⭐⭐⭐
**Purpose**: Real-time metrics tracking (COMPLETED in Phase 1)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/performance_tracker.py`
**Key Lines**:
- 50-135: Event recording methods (record_cache_hit, record_ai_call, record_ghl_call)
- 140-220: Metrics calculation (get_performance_metrics, get_cache_statistics)
- 280-340: Cost savings calculation
- 370-410: Persistence (persist_snapshot, restore_from_snapshot)
**What to Learn**:
- How metrics are tracked
- Rolling window implementation
- P95 calculation
- Multi-tier caching strategy

### 5. tests/shared/test_dashboard_models.py
**Purpose**: Model tests (22 tests passing)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/tests/shared/test_dashboard_models.py`
**What to Learn**: Testing patterns for dataclasses

### 6. tests/shared/test_performance_tracker.py
**Purpose**: Tracker tests (20 tests passing)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/tests/shared/test_performance_tracker.py`
**What to Learn**:
- AsyncMock patterns
- Testing async methods
- Pytest fixtures for services

---

## Priority 3: Integration Points (Understand Patterns)

### 7. bots/shared/cache_service.py ⭐⭐
**Purpose**: Redis caching with in-memory fallback
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/cache_service.py`
**Key Lines**:
- 139-222: CacheService class (get, set, delete, increment)
- 223-302: cached_computation() method (cache-aside pattern)
- 310-374: PerformanceCache wrapper
**What to Learn**:
- Async caching patterns
- Cache-aside implementation
- Circuit breaker with fallback
- How to use CacheService in new services

### 8. bots/seller_bot/jorge_seller_bot.py ⭐⭐
**Purpose**: Seller bot Q1-Q4 qualification (needs persistence added)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/seller_bot/jorge_seller_bot.py`
**Key Lines**:
- 44-121: SellerQualificationState dataclass
- 198: `self.conversation_states: Dict` (IN-MEMORY - need to replace)
- 500-525: Temperature calculation
- 648-667: Analytics data structure
**What to Learn**:
- Current state management (in-memory dict)
- State structure to persist
- Where to add Redis persistence

### 9. bots/shared/business_rules.py ⭐
**Purpose**: Jorge's business rules and commission logic
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/business_rules.py`
**Key Lines**:
- 21-50: JorgeBusinessRules class
- 160-173: calculate_commission() method
**What to Learn**: How to calculate commission for CommissionMetrics

### 10. bots/shared/lead_intelligence_optimized.py ⭐
**Purpose**: Lead scoring and pattern extraction
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/lead_intelligence_optimized.py`
**Key Lines**:
- 200-234: Budget extraction with regex patterns
- 236-266: Timeline classification
**What to Learn**: How to extract budget/timeline for distributions

---

## Priority 4: Reference Documentation

### 11. PHASE3_DASHBOARD_SPECIFICATION.md
**Purpose**: Complete Phase 3 requirements
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3_DASHBOARD_SPECIFICATION.md`
**Key Sections**:
- Lines 290-324: Performance Analytics requirements
- Lines 492-576: Design System
**What to Learn**: What the dashboard should display

### 12. PHASE3B_IMPLEMENTATION_HANDOFF.md
**Purpose**: Original Phase 3B handoff (from Phase 1)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3B_IMPLEMENTATION_HANDOFF.md`
**What to Learn**: Overall Phase 3B architecture

---

## Quick Reference: File Locations

### Phase 1 Completed Files (To Reference)
```
✅ bots/shared/dashboard_models.py (350 lines)
✅ bots/shared/performance_tracker.py (450 lines)
✅ tests/shared/test_dashboard_models.py (22 tests)
✅ tests/shared/test_performance_tracker.py (20 tests)
```

### Phase 2 Files to Create
```
⏳ bots/shared/metrics_service.py (~250 lines)
⏳ bots/shared/dashboard_data_service.py (~400 lines)
⏳ tests/shared/test_metrics_service.py (15 tests)
⏳ tests/shared/test_dashboard_data_service.py (20 tests)
⏳ tests/seller_bot/test_persistence.py (10 tests)

📝 bots/seller_bot/jorge_seller_bot.py (enhance existing, +100 lines)
```

---

## Reading Strategy

### Quick Approach (20 minutes)

1. **Skim handoff** (5 min):
   - PHASE3B_PHASE2_HANDOFF.md (architecture overview)

2. **Review completed code** (10 min):
   - bots/shared/dashboard_models.py (understand data structures)
   - bots/shared/performance_tracker.py (understand metrics tracking)

3. **Check patterns** (5 min):
   - bots/shared/cache_service.py (lines 139-302)
   - tests/shared/test_performance_tracker.py (testing patterns)

### Comprehensive Approach (45 minutes)

Read all files in order listed above, focusing on:
- Data models and their usage
- Performance tracker implementation
- Caching patterns from cache_service.py
- Seller bot current state management
- Testing patterns from existing tests

---

## Implementation Order

After reading files, implement in this order:

### Step 1: MetricsService (30 min + 15 min tests)
1. Create `bots/shared/metrics_service.py`
2. Write tests first: `tests/shared/test_metrics_service.py`
3. Implement service methods
4. Run tests: `pytest tests/shared/test_metrics_service.py -v`

### Step 2: DashboardDataService (45 min + 20 min tests)
1. Create `bots/shared/dashboard_data_service.py`
2. Write tests first: `tests/shared/test_dashboard_data_service.py`
3. Implement orchestration methods
4. Run tests: `pytest tests/shared/test_dashboard_data_service.py -v`

### Step 3: Seller Bot Persistence (30 min + 10 min tests)
1. Update `bots/seller_bot/jorge_seller_bot.py`
2. Write tests: `tests/seller_bot/test_persistence.py`
3. Replace in-memory dict with Redis
4. Run tests: `pytest tests/seller_bot/test_persistence.py -v`

---

## Testing Commands

```bash
# Activate environment
cd ~/Documents/GitHub/jorge_real_estate_bots
source venv/bin/activate

# Run specific test file
pytest tests/shared/test_metrics_service.py -v

# Run all Phase 1 + Phase 2 tests
pytest tests/shared/test_dashboard_models.py \
       tests/shared/test_performance_tracker.py \
       tests/shared/test_metrics_service.py \
       tests/shared/test_dashboard_data_service.py -v

# Coverage for all services
pytest tests/shared/ --cov=bots.shared --cov-report=html

# View coverage
open htmlcov/index.html
```

---

## Key Patterns to Remember

### 1. Service Layer Pattern
```python
class MetricsService:
    def __init__(self):
        self.tracker = get_performance_tracker()
        self.cache = get_cache_service()

    async def get_metrics(self) -> Metrics:
        # Check cache
        cached = await self.cache.get("key")
        if cached:
            return Metrics(**cached)

        # Compute from tracker
        metrics = await self.tracker.get_performance_metrics()

        # Cache result
        await self.cache.set("key", asdict(metrics), ttl=30)
        return metrics
```

### 2. Error Handling
```python
async def get_data(self) -> DataModel:
    try:
        return await self._fetch_real_data()
    except Exception as e:
        logger.exception(f"Error: {e}")
        return self._get_fallback_data()
```

### 3. Async Testing
```python
@pytest.mark.asyncio
async def test_async_method(mock_cache):
    service = MetricsService()
    service.cache = mock_cache

    result = await service.get_metrics()

    assert result is not None
    mock_cache.get.assert_called_once()
```

---

## Next Steps After Reading

1. ✅ Understand Phase 2 architecture
2. ✅ Review Phase 1 completed code
3. ✅ Identify caching patterns to follow
4. 🎯 Create `tests/shared/test_metrics_service.py` (TDD)
5. 🎯 Implement `bots/shared/metrics_service.py`
6. 🎯 Continue with checklist

**Ready to build Phase 2!** 🚀
