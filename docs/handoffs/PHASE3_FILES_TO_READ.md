# Phase 3 UI Components: Files to Read Guide

**Read these files in order for efficient Streamlit component implementation**

---

## Priority 1: Implementation Context (Read First)

### 1. PHASE3_IMPLEMENTATION_HANDOFF.md ⭐⭐⭐
**Purpose**: Complete architecture and component specifications
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE3_IMPLEMENTATION_HANDOFF.md`
**What to Learn**:
- Component architecture and hierarchy
- Complete code examples for all 3 components
- Testing strategy and success criteria
- Common issues and solutions

---

## Priority 2: Data Source API (Understand Before Building)

### 2. bots/shared/dashboard_data_service.py ⭐⭐⭐
**Purpose**: Primary data source for all UI components
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/dashboard_data_service.py`
**Key Lines**:
- 42-46: `__init__` - Service initialization
- 52-102: `get_dashboard_data()` - Main API method (returns DashboardData)
- 108-170: `get_active_conversations()` - Conversation list with pagination
- 176-235: `get_hero_metrics()` - KPI metrics calculation
- 241-289: `get_performance_metrics()` - Performance analytics

**What to Learn**:
- How to call `get_dashboard_data()` to get all data at once
- DashboardData structure (hero_metrics, active_conversations, performance_metrics)
- Async/await patterns for service calls
- Caching strategy (30s/5min/1hr)

**Usage Pattern**:
```python
service = DashboardDataService()
data = await service.get_dashboard_data()
# data.hero_metrics -> HeroMetrics
# data.active_conversations -> ActiveConversationsResponse
# data.performance_metrics -> PerformanceMetrics
```

### 3. bots/shared/dashboard_models.py ⭐⭐⭐
**Purpose**: Data models used by UI components
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/dashboard_models.py`
**Key Lines**:
- 8-24: Temperature, ConversationStage enums
- 27-54: HeroMetrics dataclass (4 KPIs + deltas)
- 57-77: PerformanceMetrics dataclass (qualification, response time, budget)
- 128-166: ConversationState dataclass (seller conversation data)
- 169-181: ActiveConversationsResponse (paginated list)
- 184-198: DashboardData (top-level container)

**What to Learn**:
- Field names and types for each dataclass
- Temperature enum values (HOT, WARM, COLD)
- ConversationStage enum values (Q0, Q1, Q2, Q3, Q4, QUALIFIED, STALLED)
- Pagination structure (page, page_size, total, conversations)

---

## Priority 3: Service Layer Patterns (Reference)

### 4. bots/shared/metrics_service.py ⭐⭐
**Purpose**: Performance metrics calculation patterns
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/metrics_service.py`
**Key Lines**:
- 56-90: `get_performance_metrics()` - Main metrics calculation
- 92-146: `get_budget_performance()` - Budget tracking
- 455-473: Error handling with fallback data

**What to Learn**:
- How performance metrics are calculated
- Error handling patterns for UI components
- Fallback data strategies when services fail

### 5. bots/shared/performance_tracker.py ⭐
**Purpose**: Real-time metrics tracking (used by charts)
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/performance_tracker.py`
**Key Lines**:
- 39-47: `__init__` - 24h rolling window setup
- 49-84: `track_conversation_started()` - Event tracking
- 246-319: Temperature scoring algorithm

**What to Learn**:
- 24-hour rolling window for metrics
- Temperature calculation logic
- Event-based tracking patterns

---

## Priority 4: Existing UI Patterns (Streamlit Reference)

### 6. command_center/dashboard.py (if exists)
**Purpose**: Existing dashboard patterns to follow
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/command_center/dashboard.py`
**What to Learn**:
- Streamlit layout patterns
- Caching strategies
- Session state management
- Error handling in UI

---

## Quick Reference: Key Patterns

### Streamlit Caching
```python
@st.cache_data(ttl=30)  # Cache data for 30 seconds
def load_dashboard_data():
    service = DashboardDataService()
    return asyncio.run(service.get_dashboard_data())
```

### Async in Streamlit
```python
# ✅ CORRECT: Use asyncio.run() in cached function
@st.cache_data(ttl=30)
def load_data():
    return asyncio.run(service.get_data())

# ❌ WRONG: Don't use asyncio.run() in main render
data = asyncio.run(service.get_data())  # Will error if event loop running
```

### Session State for Pagination
```python
# Initialize at top of app
if 'page' not in st.session_state:
    st.session_state.page = 1

# Update on button click
if st.button("Next"):
    st.session_state.page += 1
    st.rerun()
```

### Error Handling
```python
try:
    data = load_dashboard_data()
    render_component(data)
except Exception as e:
    st.error(f"Error: {e}")
    st.info("Using fallback data...")
    render_fallback_ui()
```

### Temperature Color Coding
```python
def format_temperature(temp: Temperature) -> str:
    emoji_map = {
        Temperature.HOT: "🔥",
        Temperature.WARM: "⚡",
        Temperature.COLD: "❄️"
    }
    return f"{emoji_map.get(temp, '')} {temp.value.upper()}"
```

### Datetime Formatting
```python
# Display format
last_activity.strftime("%Y-%m-%d %H:%M")  # "2026-01-23 15:30"

# Time ago calculation
minutes_ago = (datetime.now() - last_activity).total_seconds() / 60
st.write(f"({minutes_ago:.0f}m ago)")
```

---

## File Locations Reference

### Files to Create
```
command_center/components/
├── __init__.py                      # Empty (package marker)
├── hero_metrics_card.py             # Component 1
├── active_conversations_table.py    # Component 2
└── performance_chart.py             # Component 3

command_center/
└── dashboard_v3.py                  # Main integration app

tests/command_center/
├── __init__.py                      # Empty (package marker)
├── test_hero_metrics_card.py        # 5 tests
├── test_active_conversations_table.py  # 7 tests
└── test_performance_chart.py        # 6 tests
```

### Files to Reference (Read-Only)
```
bots/shared/
├── dashboard_data_service.py       # Primary data source
├── dashboard_models.py             # Data models
├── metrics_service.py              # Metrics calculation
└── performance_tracker.py          # Real-time tracking
```

---

## Reading Strategy

### Quick Approach (20 minutes)

1. **Skim handoff** (10 min):
   - PHASE3_IMPLEMENTATION_HANDOFF.md (focus on code examples)

2. **Review data API** (5 min):
   - dashboard_data_service.py:52-102 (`get_dashboard_data()`)
   - dashboard_models.py:1-200 (all dataclasses)

3. **Start building** (5 min):
   - Copy component templates from handoff
   - Adjust imports and field names

### Comprehensive Approach (40 minutes)

Read all files in order listed above, focusing on:
- DashboardDataService API and return types
- Dataclass field names and types
- Streamlit caching patterns
- Error handling strategies
- Session state management

---

## Implementation Order

After reading files, implement in this order:

### Step 1: Setup (5 min)
1. Create directory structure (command_center/components/, tests/command_center/)
2. Create __init__.py files
3. Install dependencies if needed (streamlit, plotly)

### Step 2: Component 1 - HeroMetricsCard (15 min)
1. Create `hero_metrics_card.py`
2. Implement `render_hero_metrics()` function
3. Write 5 tests in `test_hero_metrics_card.py`
4. Run tests: `pytest tests/command_center/test_hero_metrics_card.py -v`

### Step 3: Component 2 - ActiveConversationsTable (20 min)
1. Create `active_conversations_table.py`
2. Implement `render_active_conversations()` function
3. Add search, filter, pagination logic
4. Write 7 tests in `test_active_conversations_table.py`
5. Run tests: `pytest tests/command_center/test_active_conversations_table.py -v`

### Step 4: Component 3 - PerformanceChart (15 min)
1. Create `performance_chart.py`
2. Implement `render_performance_chart()` with Plotly
3. Write 6 tests in `test_performance_chart.py`
4. Run tests: `pytest tests/command_center/test_performance_chart.py -v`

### Step 5: Integration Dashboard (10 min)
1. Create `dashboard_v3.py`
2. Integrate all 3 components
3. Add auto-refresh logic
4. Add error handling

### Step 6: Test & Verify (10 min)
1. Run all tests: `pytest tests/command_center/ -v`
2. Manual testing: `streamlit run command_center/dashboard_v3.py`
3. Verify all features work
4. Check for errors in browser console

---

## Testing Commands

```bash
# Run specific component tests
pytest tests/command_center/test_hero_metrics_card.py -v
pytest tests/command_center/test_active_conversations_table.py -v
pytest tests/command_center/test_performance_chart.py -v

# Run all component tests
pytest tests/command_center/ -v

# Run with coverage
pytest tests/command_center/ --cov=command_center.components --cov-report=html

# Manual testing
cd ~/Documents/GitHub/jorge_real_estate_bots
source venv/bin/activate
streamlit run command_center/dashboard_v3.py
```

---

**Ready to build!** 🚀

Start by reading PHASE3_IMPLEMENTATION_HANDOFF.md for complete component specifications, then reference the data API files to understand the data structures.
