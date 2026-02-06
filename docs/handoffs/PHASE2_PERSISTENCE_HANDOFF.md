# Phase 2 Persistence Handoff: Seller Bot Redis Persistence

**Date**: January 23, 2026
**Project**: Jorge Real Estate AI MVP - Phase 3B Dashboard
**Status**: Phase 2 Service Layer 93% Complete, Final Component Remaining
**Estimated Time**: 30 minutes for seller bot persistence

---

## Quick Status Summary

### ✅ Phase 2 Completed (93%)

**Service Layer Components**:
1. **metrics_service.py**: Performance aggregation ✅
   - 18/18 tests passing
   - Multi-tier caching (30s/5min/1hr)
   - Budget/timeline/commission metrics
   - Error handling with fallbacks

2. **dashboard_data_service.py**: Data orchestration ✅
   - 21/21 tests passing
   - Complete dashboard data in one call
   - Active conversations with pagination
   - Hero metrics and performance analytics

3. **Test Infrastructure**: All fixed ✅
   - Total: 81/81 tests passing (100%)
   - Phase 1: 42 tests (dashboard_models, performance_tracker)
   - Phase 2: 39 tests (metrics_service, dashboard_data_service)

### ⏳ Remaining (7%)

**Seller Bot Persistence**:
- Tests created: `tests/seller_bot/test_persistence.py` (10 tests) ✅
- Implementation needed: Add Redis persistence to `jorge_seller_bot.py` ⏳

---

## Architecture: Seller Bot Persistence

### Current State (In-Memory)

**Location**: `bots/seller_bot/jorge_seller_bot.py:198`

```python
class JorgeSellerBot:
    def __init__(self):
        self.claude_client = ClaudeClient()
        self.ghl_client = ghl_client or GHLClient()
        self.logger = get_logger(__name__)

        # IN-MEMORY (NOT PERSISTENT) ❌
        self._states: Dict[str, SellerQualificationState] = {}
```

**Problem**: Conversations lost on service restart, no dashboard visibility.

### Target State (Redis-Backed)

```python
class JorgeSellerBot:
    def __init__(self):
        self.claude_client = ClaudeClient()
        self.ghl_client = ghl_client or GHLClient()
        self.cache = get_cache_service()  # Redis backend
        self.logger = get_logger(__name__)

        # NO in-memory dict - all state in Redis ✅

    async def get_conversation_state(
        self,
        contact_id: str
    ) -> Optional[SellerQualificationState]:
        """Load conversation state from Redis."""
        key = f"seller:state:{contact_id}"
        state_dict = await self.cache.get(key)

        if state_dict:
            # Deserialize datetime fields
            if 'last_interaction' in state_dict and state_dict['last_interaction']:
                state_dict['last_interaction'] = datetime.fromisoformat(
                    state_dict['last_interaction']
                )
            if 'conversation_started' in state_dict and state_dict['conversation_started']:
                state_dict['conversation_started'] = datetime.fromisoformat(
                    state_dict['conversation_started']
                )

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

        # Serialize datetime fields to ISO format strings
        if state.last_interaction:
            state_dict['last_interaction'] = state.last_interaction.isoformat()
        if state.conversation_started:
            state_dict['conversation_started'] = state.conversation_started.isoformat()

        # Save to Redis with 7-day TTL
        await self.cache.set(key, state_dict, ttl=604800)  # 7 days

        # Add to active contacts set for efficient listing
        # Note: Requires Redis Set support (sadd method)
        if hasattr(self.cache, 'sadd'):
            await self.cache.sadd("seller:active_contacts", contact_id)

    async def get_all_active_conversations(
        self
    ) -> List[SellerQualificationState]:
        """
        Get all active conversations from Redis.

        Uses seller:active_contacts set for efficient listing.
        """
        states = []

        # Get all active contact IDs from Redis Set
        if hasattr(self.cache, 'smembers'):
            contact_ids = await self.cache.smembers("seller:active_contacts")
        else:
            # Fallback: SCAN keys (less efficient but works)
            contact_ids = []
            # Implementation: Use Redis SCAN to find seller:state:* keys

        # Load each state
        for contact_id in contact_ids:
            state = await self.get_conversation_state(contact_id)
            if state:
                states.append(state)

        return states

    async def delete_conversation_state(self, contact_id: str):
        """Delete conversation state from Redis."""
        key = f"seller:state:{contact_id}"
        await self.cache.delete(key)

        # Remove from active contacts set
        if hasattr(self.cache, 'srem'):
            await self.cache.srem("seller:active_contacts", contact_id)
```

---

## Implementation Checklist

### Step 1: Update SellerQualificationState Dataclass (5 min)

**File**: `bots/seller_bot/jorge_seller_bot.py:43-121`

**Current State**:
```python
@dataclass
class SellerQualificationState:
    current_question: int = 0
    questions_answered: int = 0
    is_qualified: bool = False

    condition: Optional[str] = None
    price_expectation: Optional[int] = None
    motivation: Optional[str] = None
    urgency: Optional[str] = None
    offer_accepted: Optional[bool] = None
    timeline_acceptable: Optional[bool] = None

    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    last_interaction: Optional[datetime] = None
```

**Required Updates**:
- [ ] Add `contact_id: str` field
- [ ] Add `location_id: str` field
- [ ] Add `stage: str` field (for dashboard ConversationStage mapping)
- [ ] Add `conversation_started: datetime` field
- [ ] Add `extracted_data: Dict[str, Any] = field(default_factory=dict)` for dashboard

**Target State**:
```python
@dataclass
class SellerQualificationState:
    # Required identifiers
    contact_id: str
    location_id: str

    # Qualification state
    current_question: int = 0
    questions_answered: int = 0
    is_qualified: bool = False
    stage: str = "Q0"  # Q0, Q1, Q2, Q3, Q4, QUALIFIED, STALLED

    # Q1-Q4 data
    condition: Optional[str] = None
    price_expectation: Optional[int] = None
    motivation: Optional[str] = None
    urgency: Optional[str] = None
    offer_accepted: Optional[bool] = None
    timeline_acceptable: Optional[bool] = None

    # Metadata
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    last_interaction: Optional[datetime] = None
    conversation_started: datetime = field(default_factory=datetime.now)
```

---

### Step 2: Add Redis Persistence Methods to JorgeSellerBot (15 min)

**File**: `bots/seller_bot/jorge_seller_bot.py:135+`

**Add Import**:
```python
from dataclasses import asdict
from bots.shared.cache_service import get_cache_service
```

**Update `__init__`**:
```python
def __init__(self, ghl_client: Optional[GHLClient] = None):
    self.claude_client = ClaudeClient()
    self.ghl_client = ghl_client or GHLClient()
    self.cache = get_cache_service()  # Add Redis cache
    self.logger = get_logger(__name__)

    # Remove: self._states = {}
```

**Add Methods** (after `__init__`):
```python
async def get_conversation_state(
    self,
    contact_id: str
) -> Optional[SellerQualificationState]:
    """
    Load conversation state from Redis.

    Args:
        contact_id: GHL contact ID

    Returns:
        SellerQualificationState if exists, None otherwise
    """
    key = f"seller:state:{contact_id}"
    state_dict = await self.cache.get(key)

    if not state_dict:
        return None

    # Deserialize datetime fields
    if 'last_interaction' in state_dict and state_dict['last_interaction']:
        state_dict['last_interaction'] = datetime.fromisoformat(
            state_dict['last_interaction']
        )
    if 'conversation_started' in state_dict and state_dict['conversation_started']:
        state_dict['conversation_started'] = datetime.fromisoformat(
            state_dict['conversation_started']
        )

    return SellerQualificationState(**state_dict)

async def save_conversation_state(
    self,
    contact_id: str,
    state: SellerQualificationState
):
    """
    Save conversation state to Redis with 7-day TTL.

    Args:
        contact_id: GHL contact ID
        state: Current conversation state
    """
    key = f"seller:state:{contact_id}"
    state_dict = asdict(state)

    # Serialize datetime fields to ISO format
    if state.last_interaction:
        state_dict['last_interaction'] = state.last_interaction.isoformat()
    if state.conversation_started:
        state_dict['conversation_started'] = state.conversation_started.isoformat()

    # Save to Redis with 7-day TTL
    await self.cache.set(key, state_dict, ttl=604800)

    # Add to active contacts set (if Redis Set support available)
    if hasattr(self.cache, 'sadd'):
        await self.cache.sadd("seller:active_contacts", contact_id)

    self.logger.debug(f"Saved state for contact {contact_id}: Q{state.current_question}")

async def get_all_active_conversations(self) -> List[SellerQualificationState]:
    """
    Get all active seller conversations from Redis.

    Returns:
        List of active conversation states
    """
    states = []

    # Get active contact IDs from Redis Set
    if hasattr(self.cache, 'smembers'):
        contact_ids = await self.cache.smembers("seller:active_contacts")
    else:
        # Fallback: return empty list (production should implement SCAN)
        self.logger.warning("Redis Set operations not available, returning empty list")
        return []

    # Load each state
    for contact_id in contact_ids:
        state = await self.get_conversation_state(contact_id)
        if state:
            states.append(state)

    return states

async def delete_conversation_state(self, contact_id: str):
    """
    Delete conversation state from Redis.

    Args:
        contact_id: GHL contact ID
    """
    key = f"seller:state:{contact_id}"
    await self.cache.delete(key)

    # Remove from active contacts set
    if hasattr(self.cache, 'srem'):
        await self.cache.srem("seller:active_contacts", contact_id)

    self.logger.info(f"Deleted state for contact {contact_id}")
```

---

### Step 3: Update State Management Methods (10 min)

**Find and Update `_get_or_create_state()` method**:

**Current** (approximate line 220):
```python
def _get_or_create_state(self, contact_id: str) -> SellerQualificationState:
    """Get existing state or create new one."""
    if contact_id not in self._states:
        self._states[contact_id] = SellerQualificationState()
    return self._states[contact_id]
```

**New**:
```python
async def _get_or_create_state(
    self,
    contact_id: str,
    location_id: str
) -> SellerQualificationState:
    """Get existing state from Redis or create new one."""
    state = await self.get_conversation_state(contact_id)

    if not state:
        state = SellerQualificationState(
            contact_id=contact_id,
            location_id=location_id,
            current_question=0,
            stage="Q0",
            conversation_started=datetime.now()
        )
        await self.save_conversation_state(contact_id, state)

    return state
```

**Update all state reads** (find lines with `self._states[contact_id]`):
- Replace with: `await self.get_conversation_state(contact_id)`

**Update all state writes** (find lines with `self._states[contact_id] = state`):
- Replace with: `await self.save_conversation_state(contact_id, state)`

**Update `process_seller_message()` method** (line ~200):
- Change `state = self._get_or_create_state(contact_id)`
- To: `state = await self._get_or_create_state(contact_id, location_id)`
- Add `await self.save_conversation_state(contact_id, state)` after state updates

---

## Testing Strategy

### Run Tests Incrementally

**Step 1: Run persistence tests**:
```bash
pytest tests/seller_bot/test_persistence.py -v
```

Expected: 10/10 tests passing

**Step 2: Run all Phase 2 tests**:
```bash
pytest tests/shared/ tests/seller_bot/ -v
```

Expected: 91/91 tests passing (81 + 10)

**Step 3: Check for regressions**:
```bash
pytest tests/ -v --tb=short
```

Expected: All existing tests still pass

---

## Common Issues & Solutions

### Issue 1: Import Errors
**Error**: `ImportError: cannot import name 'get_cache_service'`
**Solution**: Add import at top of file:
```python
from bots.shared.cache_service import get_cache_service
```

### Issue 2: Missing Fields in SellerQualificationState
**Error**: `TypeError: __init__() missing 2 required positional arguments: 'contact_id' and 'location_id'`
**Solution**: Update all SellerQualificationState instantiations to include required fields

### Issue 3: Datetime Serialization
**Error**: `TypeError: Object of type datetime is not JSON serializable`
**Solution**: Convert datetime to ISO string before saving:
```python
state_dict['last_interaction'] = state.last_interaction.isoformat()
```

### Issue 4: Async/Await Errors
**Error**: `RuntimeWarning: coroutine 'get_conversation_state' was never awaited`
**Solution**: Add `await` before async method calls:
```python
state = await self.get_conversation_state(contact_id)  # ✅
state = self.get_conversation_state(contact_id)  # ❌
```

---

## Git Workflow

### Commit After Completion

```bash
# Stage changes
git add bots/seller_bot/jorge_seller_bot.py tests/seller_bot/test_persistence.py

# Commit with descriptive message
git commit -m "feat(seller-bot): Add Redis-backed conversation persistence

- Add contact_id, location_id, stage, conversation_started fields to SellerQualificationState
- Implement get/save_conversation_state() with 7-day TTL
- Add get_all_active_conversations() for dashboard integration
- Add seller:active_contacts Redis Set for efficient listing
- Replace in-memory dict with CacheService
- Update all state reads/writes to use async Redis methods
- Comprehensive tests (10 tests, 100% coverage)

Phase 2 Service Layer now 100% complete (91/91 tests passing)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Success Criteria

### Functionality
- [ ] All seller conversations persist across service restarts
- [ ] States expire after 7 days (TTL enforcement)
- [ ] Dashboard can list all active seller conversations
- [ ] Datetime fields serialize/deserialize correctly
- [ ] State updates save to Redis immediately

### Testing
- [ ] All 10 persistence tests pass
- [ ] All 81 existing tests still pass (no regressions)
- [ ] Total: 91/91 tests passing (100%)
- [ ] Coverage ≥80% for jorge_seller_bot.py

### Performance
- [ ] State save completes in <50ms
- [ ] State load completes in <20ms
- [ ] get_all_active_conversations() scales to 100+ contacts

---

## Next Steps After Completion

Once seller bot persistence is complete:

1. **Run full test suite**:
   ```bash
   pytest tests/ --cov=bots --cov-report=html
   ```

2. **Verify coverage**:
   ```bash
   open htmlcov/index.html
   ```

3. **Manual testing** (optional):
   - Start seller bot conversation
   - Restart service
   - Verify conversation resumes from saved state

4. **Move to Phase 3**: UI Components
   - Streamlit dashboard components
   - Real-time data integration
   - Interactive charts and tables

---

## Reference Files

### Key Implementation Patterns

**CacheService Usage** (`bots/shared/cache_service.py:139-222`):
```python
# Get from Redis
cached = await self.cache.get("key")

# Set with TTL
await self.cache.set("key", value_dict, ttl=604800)

# Delete
await self.cache.delete("key")
```

**Dashboard Models** (`bots/shared/dashboard_models.py:128-166`):
```python
@dataclass
class ConversationState:
    contact_id: str
    seller_name: str
    stage: ConversationStage
    temperature: Temperature
    current_question: int
    questions_answered: int
    last_activity: datetime
    conversation_started: datetime
    is_qualified: bool
```

---

## Time Estimates

- **Step 1**: Update SellerQualificationState dataclass: 5 min
- **Step 2**: Add Redis persistence methods: 15 min
- **Step 3**: Update state management: 10 min
- **Testing & Debug**: 5-10 min

**Total**: ~30 minutes

---

## Ready to Continue?

**Next Action**: Update `SellerQualificationState` dataclass with required fields (`contact_id`, `location_id`, `stage`, `conversation_started`)

**First Task**: Read `bots/seller_bot/jorge_seller_bot.py` lines 43-121, then add the missing fields to the dataclass.

Good luck! 🚀
