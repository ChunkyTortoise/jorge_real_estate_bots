# Phase 2 Persistence: Files to Read Guide

**Read these files in order for efficient seller bot persistence implementation**

---

## Priority 1: Implementation Context (Read First)

### 1. PHASE2_PERSISTENCE_HANDOFF.md ⭐⭐⭐
**Purpose**: Complete architecture and implementation guide
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/PHASE2_PERSISTENCE_HANDOFF.md`
**What to Learn**:
- Current vs. target architecture
- Step-by-step implementation checklist
- Code examples for all methods
- Testing strategy
- Common issues and solutions

### 2. tests/seller_bot/test_persistence.py ⭐⭐⭐
**Purpose**: Test expectations and requirements
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/tests/seller_bot/test_persistence.py`
**Key Lines**: All 240 lines
**What to Learn**:
- Expected method signatures
- Redis key patterns ("seller:state:{contact_id}")
- TTL requirements (7 days = 604,800 seconds)
- Active contacts set ("seller:active_contacts")
- Datetime serialization expectations
- Error handling requirements

---

## Priority 2: Current Implementation (Understand Before Modifying)

### 3. bots/seller_bot/jorge_seller_bot.py (Part 1: Dataclass) ⭐⭐⭐
**Purpose**: Current SellerQualificationState structure
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/seller_bot/jorge_seller_bot.py`
**Key Lines**: 43-121
**What to Learn**:
- Current fields (missing: contact_id, location_id, stage, conversation_started)
- Field types and defaults
- advance_question() method
- record_answer() method

**Fields to Add**:
```python
contact_id: str  # Required
location_id: str  # Required
stage: str = "Q0"  # Q0, Q1, Q2, Q3, Q4, QUALIFIED, STALLED
conversation_started: datetime = field(default_factory=datetime.now)
extracted_data: Dict[str, Any] = field(default_factory=dict)
```

### 4. bots/seller_bot/jorge_seller_bot.py (Part 2: Class Init) ⭐⭐
**Purpose**: JorgeSellerBot initialization and in-memory state
**Location**: Same file
**Key Lines**: 135-240
**What to Learn**:
- Current `__init__` method (line ~185-198)
- In-memory `self._states` dict (line 198)
- `_get_or_create_state()` method (needs async conversion)
- `process_seller_message()` method (needs state persistence calls)

**Changes Needed**:
```python
# In __init__:
self.cache = get_cache_service()  # Add this
# Remove: self._states = {}

# Convert _get_or_create_state to async
# Add: await self.save_conversation_state() after state updates
```

### 5. bots/seller_bot/jorge_seller_bot.py (Part 3: State Usage) ⭐
**Purpose**: Find all places where state is read/written
**Location**: Same file
**Key Lines**: 200-600 (entire class)
**What to Learn**:
- All `self._states[contact_id]` reads
- All `self._states[contact_id] = state` writes
- Where to add `await self.save_conversation_state()`

**Pattern to Find**:
```bash
# Search for state dict usage
grep -n "self._states" bots/seller_bot/jorge_seller_bot.py
```

---

## Priority 3: Integration Patterns (Reference)

### 6. bots/shared/cache_service.py ⭐⭐
**Purpose**: Learn async Redis patterns
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/cache_service.py`
**Key Lines**:
- 139-222: CacheService class (get, set, delete, increment)
- 178-187: async get() method
- 188-201: async set() method with TTL
- 202-212: async delete() method

**Patterns to Copy**:
```python
# Get from Redis
cached = await self.cache.get("key")

# Set with TTL
await self.cache.set("key", value_dict, ttl=604800)

# Delete
await self.cache.delete("key")
```

### 7. bots/shared/dashboard_models.py ⭐
**Purpose**: Reference for dashboard integration fields
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/dashboard_models.py`
**Key Lines**: 128-166 (ConversationState dataclass)
**What to Learn**:
- Required fields for dashboard display
- Stage and Temperature enums
- Datetime serialization with to_dict()

**Fields Used by Dashboard**:
```python
contact_id: str
stage: ConversationStage  # Maps to SellerQualificationState.stage
temperature: Temperature
current_question: int
questions_answered: int
last_activity: datetime  # Maps to last_interaction
conversation_started: datetime
is_qualified: bool
```

---

## Priority 4: Completed Phase 2 Components (Context)

### 8. bots/shared/metrics_service.py ⭐
**Purpose**: Example of service layer with caching
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/metrics_service.py`
**Key Lines**:
- 46-51: __init__ with cache_service
- 56-90: get_performance_metrics() with cache-aside pattern
- 455-473: Error handling with fallback data

**Patterns to Learn**:
- Try-except with logging
- Cache miss → compute → cache result
- Fallback data on errors

### 9. bots/shared/dashboard_data_service.py ⭐
**Purpose**: Example of data orchestration with multiple sources
**Location**: `/Users/cave/Documents/GitHub/jorge_real_estate_bots/bots/shared/dashboard_data_service.py`
**Key Lines**:
- 42-46: __init__ with multiple services
- 108-170: get_active_conversations() (will call seller bot persistence)
- 292-370: _fetch_active_conversations() (mock data - will use real persistence)

**Integration Point**:
```python
# DashboardDataService will call:
seller_bot = JorgeSellerBot()
conversations = await seller_bot.get_all_active_conversations()
# Convert to dashboard ConversationState models
```

---

## Quick Reference: File Locations

### Files to Modify
```
✏️ bots/seller_bot/jorge_seller_bot.py (PRIMARY)
   - Lines 43-121: Add fields to SellerQualificationState
   - Line ~195: Update __init__ to use CacheService
   - Line ~198: Remove self._states dict
   - Add new methods after __init__:
     - get_conversation_state()
     - save_conversation_state()
     - get_all_active_conversations()
     - delete_conversation_state()
   - Line ~220: Update _get_or_create_state() to async
   - Throughout: Replace state dict access with Redis calls
```

### Files to Reference (Read-Only)
```
📖 tests/seller_bot/test_persistence.py
📖 bots/shared/cache_service.py
📖 bots/shared/dashboard_models.py
📖 bots/shared/metrics_service.py
📖 bots/shared/dashboard_data_service.py
```

---

## Reading Strategy

### Quick Approach (15 minutes)

1. **Skim handoff** (5 min):
   - PHASE2_PERSISTENCE_HANDOFF.md (focus on code examples)

2. **Review tests** (5 min):
   - tests/seller_bot/test_persistence.py (understand expectations)

3. **Scan current code** (5 min):
   - bots/seller_bot/jorge_seller_bot.py lines 43-121 (dataclass)
   - bots/seller_bot/jorge_seller_bot.py lines 185-240 (init + state management)

### Comprehensive Approach (30 minutes)

Read all files in order listed above, focusing on:
- Dataclass fields and their purpose
- Async/await patterns from cache_service.py
- State management in jorge_seller_bot.py
- Test expectations for method signatures
- Error handling patterns from metrics_service.py

---

## Implementation Order

After reading files, implement in this order:

### Step 1: Update Dataclass (5 min)
1. Open `bots/seller_bot/jorge_seller_bot.py`
2. Navigate to line 43 (SellerQualificationState)
3. Add required fields: contact_id, location_id, stage, conversation_started, extracted_data
4. Save file

### Step 2: Add Imports (1 min)
1. Add to top of file:
   ```python
   from dataclasses import asdict
   from bots.shared.cache_service import get_cache_service
   ```

### Step 3: Update __init__ (2 min)
1. Navigate to line ~195 (JorgeSellerBot.__init__)
2. Add: `self.cache = get_cache_service()`
3. Remove: `self._states = {}`

### Step 4: Add Persistence Methods (10 min)
1. After __init__, add 4 new async methods:
   - get_conversation_state()
   - save_conversation_state()
   - get_all_active_conversations()
   - delete_conversation_state()
2. Copy implementations from PHASE2_PERSISTENCE_HANDOFF.md

### Step 5: Update State Management (10 min)
1. Convert _get_or_create_state() to async
2. Find all self._states reads/writes
3. Replace with await self.get/save_conversation_state()

### Step 6: Test (5 min)
1. Run: `pytest tests/seller_bot/test_persistence.py -v`
2. Fix any failures
3. Run: `pytest tests/ -v` (ensure no regressions)

---

## Testing Commands

```bash
# Activate environment
cd ~/Documents/GitHub/jorge_real_estate_bots
source venv/bin/activate

# Run persistence tests only
pytest tests/seller_bot/test_persistence.py -v

# Run all Phase 2 tests
pytest tests/shared/ tests/seller_bot/ -v

# Run full suite with coverage
pytest tests/ --cov=bots.shared --cov=bots.seller_bot --cov-report=html

# View coverage report
open htmlcov/index.html
```

---

## Key Patterns to Remember

### 1. Datetime Serialization
```python
# Save (dataclass → dict → Redis)
state_dict = asdict(state)
if state.last_interaction:
    state_dict['last_interaction'] = state.last_interaction.isoformat()

# Load (Redis → dict → dataclass)
if 'last_interaction' in state_dict and state_dict['last_interaction']:
    state_dict['last_interaction'] = datetime.fromisoformat(
        state_dict['last_interaction']
    )
state = SellerQualificationState(**state_dict)
```

### 2. Redis Key Pattern
```python
# State key
key = f"seller:state:{contact_id}"

# Active contacts set
set_key = "seller:active_contacts"
```

### 3. Async/Await
```python
# Always await async methods
state = await self.get_conversation_state(contact_id)  # ✅
await self.save_conversation_state(contact_id, state)  # ✅

# Don't forget await
state = self.get_conversation_state(contact_id)  # ❌
```

### 4. Error Handling
```python
try:
    state = await self.get_conversation_state(contact_id)
except Exception as e:
    self.logger.exception(f"Error loading state: {e}")
    return None  # or raise
```

---

## Next Steps After Reading

1. ✅ Understand current SellerQualificationState structure
2. ✅ Know what fields need to be added
3. ✅ Understand async Redis patterns from cache_service.py
4. ✅ Know where to add new persistence methods
5. 🎯 Start implementation: Update dataclass first

**Ready to build!** 🚀
