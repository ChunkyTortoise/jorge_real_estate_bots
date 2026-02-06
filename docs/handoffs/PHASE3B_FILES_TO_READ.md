# Phase 3B: Files to Read in New Chat Session

**Read these files in order for Phase 3B implementation**

---

## Priority 1: Critical Context (Read First)

### 1. PHASE3B_IMPLEMENTATION_HANDOFF.md
**Purpose**: Complete handoff document from architecture session
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3B_IMPLEMENTATION_HANDOFF.md`
**What to Learn**: Architecture decisions, implementation sequence, patterns

### 2. PHASE3_DASHBOARD_SPECIFICATION.md
**Purpose**: Complete Phase 3 requirements and design specifications
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3_DASHBOARD_SPECIFICATION.md`
**Key Sections**:
- Section 4: Performance Analytics (lines 290-324)
- Design System (lines 492-576)
- Implementation Priority (lines 579-602)

### 3. PHASE3B_PROMPT.txt
**Purpose**: Original Phase 3B task description
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3B_PROMPT.txt`
**What to Learn**: Deliverables, step-by-step workflow, success criteria

---

## Priority 2: Existing Implementation

### 4. command_center/dashboard.py
**Purpose**: Current MVP dashboard (mock data)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/command_center/dashboard.py`
**Key Lines**:
- 39-50: JorgeKPIDashboard class
- 87-137: Key metrics rendering
- 139-169: Plotly funnel chart pattern
- 241-259: Plotly pie chart pattern

**What to Learn**:
- Streamlit component patterns
- Plotly chart configurations
- Mock data structure

### 5. bots/shared/cache_service.py
**Purpose**: Redis caching with in-memory fallback
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/cache_service.py`
**Key Lines**:
- 138-220: CacheService class (unified interface)
- 222-268: cached_computation() method
- 277-341: PerformanceCache wrapper
- 416-431: get_performance_metrics() (existing method)
- 793-809: get_cache_stats() (existing method)

**What to Learn**:
- Async caching patterns
- Cache-aside pattern
- Circuit breaker with fallback

### 6. bots/seller_bot/jorge_seller_bot.py
**Purpose**: Seller bot Q1-Q4 qualification flow
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/seller_bot/jorge_seller_bot.py`
**Key Lines**:
- 44-121: SellerQualificationState dataclass
- 198: In-memory state storage (need to persist)
- 500-525: Temperature calculation logic
- 648-667: Analytics data structure

**What to Learn**:
- Conversation state management
- Q0-Q4 progression logic
- Temperature (HOT/WARM/COLD) calculation

---

## Priority 3: Data Sources

### 7. bots/shared/lead_intelligence_optimized.py
**Purpose**: Lead scoring and pattern extraction
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/lead_intelligence_optimized.py`
**Key Lines**:
- 49: PredictiveLeadScorerV2Optimized class
- 200-234: Budget extraction with regex patterns
- 236-266: Timeline classification
- 428-510: Main entry point (get_enhanced_lead_intelligence)
- 461-468: Score calculation formula

**What to Learn**:
- Lead scoring algorithm
- Budget/timeline extraction patterns
- Data structure for dashboard aggregation

### 8. bots/shared/business_rules.py
**Purpose**: Jorge's business rules and commission logic
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/business_rules.py`
**Key Lines**:
- 21-50: JorgeBusinessRules class and constants
- 52-120: validate_lead() method
- 122-138: get_temperature() method
- 160-173: calculate_commission() method

**What to Learn**:
- Commission calculation logic
- Budget/service area validation
- Temperature thresholds (HOT: 80+, WARM: 60-79, COLD: <60)

### 9. bots/lead_bot/services/lead_analyzer.py
**Purpose**: AI analysis with performance tracking
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/lead_bot/services/lead_analyzer.py`
**Key Lines**:
- 29-55: LeadAnalyzer class initialization
- 55-139: analyze_lead() method
- 79-102: Cache integration
- 111-119: 5-minute rule compliance checking

**What to Learn**:
- Performance metrics tracking patterns
- Cache integration for AI analysis
- 5-minute rule monitoring

### 10. bots/shared/models.py
**Purpose**: Existing data models
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/models.py`
**Key Lines**:
- 12-39: PerformanceMetrics dataclass

**What to Learn**:
- Dataclass patterns for data structures

---

## Priority 4: Testing Patterns

### 11. tests/ (any existing test file)
**Purpose**: Understanding testing standards
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/tests/`

**Example files to examine**:
- `tests/test_seller_bot.py` (if exists)
- `tests/test_cache_service.py` (if exists)
- Any test file to understand patterns

**What to Learn**:
- Pytest fixtures
- AsyncMock patterns
- Coverage standards (80%+ target)

---

## Optional: Additional Context

### 12. PHASE1_COMPLETION_REPORT.md
**Purpose**: Understanding Phase 1 implementation
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE1_COMPLETION_REPORT.md`

### 13. PHASE2_COMPLETION_REPORT.md
**Purpose**: Understanding Phase 2 implementation
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE2_COMPLETION_REPORT.md`

### 14. BUILD_SUMMARY.md
**Purpose**: Overall project structure and status
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/BUILD_SUMMARY.md`

---

## Quick Reference: Key Patterns

### Async/Await
```python
async def get_data():
    try:
        data = await self.service.fetch()
        return data
    except Exception as e:
        logger.exception(f"Error: {e}")
        return fallback_data()
```

### Dataclass
```python
from dataclasses import dataclass, asdict

@dataclass
class PerformanceMetrics:
    cache_avg_ms: float
    ai_avg_ms: float
    timestamp: datetime
```

### Caching
```python
@st.cache_data(ttl=60)
async def get_metrics():
    cache_key = "metrics:performance"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    metrics = await compute_metrics()
    await cache.set(cache_key, metrics, ttl=60)
    return metrics
```

### Plotly
```python
import plotly.express as px

fig = px.bar(df, x='category', y='value')
fig.update_layout(height=400, template="plotly_white")
st.plotly_chart(fig, use_container_width=True)
```

---

## Reading Strategy

### Efficient Approach (30-45 minutes reading)

1. **Quick Scan** (5 min):
   - PHASE3B_IMPLEMENTATION_HANDOFF.md (skim architecture)
   - PHASE3B_PROMPT.txt (skim deliverables)

2. **Deep Read - Requirements** (10 min):
   - PHASE3_DASHBOARD_SPECIFICATION.md (Section 4, Design System)

3. **Deep Read - Existing Code** (15 min):
   - command_center/dashboard.py (understand current state)
   - bots/shared/cache_service.py (understand caching patterns)

4. **Skim - Data Sources** (10 min):
   - bots/seller_bot/jorge_seller_bot.py (state management)
   - bots/shared/lead_intelligence_optimized.py (scoring)
   - bots/shared/business_rules.py (commission logic)

5. **Reference - Testing** (5 min):
   - Look at any test file for patterns

### Comprehensive Approach (60-90 minutes reading)

Read all 14 files in order listed above.

---

## Next Steps After Reading

1. ✅ Understand the architecture
2. ✅ Identify existing patterns to follow
3. ✅ Locate data sources for dashboard
4. 🎯 Start Phase 1: Create `ghl_real_estate_ai/models/dashboard_models.py`
5. 🎯 Write tests first (TDD)
6. 🎯 Implement dataclasses
7. 🎯 Continue with checklist

---

**Ready to build!** 🚀
