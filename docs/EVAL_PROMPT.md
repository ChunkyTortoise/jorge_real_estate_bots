# Agent Evaluation Prompt: jorge_real_estate_bots

Use this prompt to onboard agents for development tasks on this repo. Copy the relevant sections based on the work being done.

---

## Full Context Prompt (for any agent)

```
You are working on the `jorge_real_estate_bots` repository — a three-bot AI system for real estate lead qualification.

**Read first**: `docs/SPEC.md` — contains complete architecture, module map, database schema, API endpoints, known issues, test status, and development priorities.

**Stack**: FastAPI (async) + PostgreSQL (async SQLAlchemy) + Redis (pub/sub + streams) + Claude AI (Haiku/Sonnet/Opus routing) + GoHighLevel CRM + Streamlit dashboard

**Bots**:
- Lead Bot (:8001) — GHL webhook receiver, <5 min response SLA, Claude-powered scoring
- Seller Bot (:8002) — Q0-Q4 confrontational qualification, temperature scoring
- Buyer Bot (:8003) — Property matching, preference extraction

**Key patterns**:
- All DB access via `async with AsyncSessionFactory() as session:`
- JWT auth on all non-health endpoints via `Depends(get_current_active_user())`
- Redis event broker with circuit breaker (singleton at `bots/shared/event_broker.py`)
- Pydantic Settings loaded from `.env` (`bots/shared/config.py`)
- Tests use autouse conftest fixture that mocks AsyncSessionFactory across 5 import locations

**Current state**: 270/279 tests pass. 9 pre-existing failures (see SPEC.md §4.2). 15 modules have zero test coverage (see SPEC.md §4.3).
```

---

## Task-Specific Prompts

### Fix Failing Tests

```
Fix the 9 failing tests in `jorge_real_estate_bots`. Read `docs/SPEC.md` §4.2 for root causes.

Summary of fixes needed:
1. `test_global_filters_render_smoke` — Add `title` attribute to `tests/command_center/streamlit_stub.py`
2. `test_mobile_dashboard_integration_render` — Fix mock DataFrame column lengths in test
3. `test_get_active_conversations_pagination`, `test_conversation_stage_distribution`, `test_conversation_temperature_distribution` — Change patches from `_fetch_real_conversation_data` to `_fetch_active_conversations` in `tests/shared/test_dashboard_data_service.py`
4. `test_get_budget_distribution_success`, `test_get_timeline_distribution_success`, `test_get_commission_metrics_success` — Provide mock LeadModel data in `tests/shared/test_metrics_service.py` fixtures
5. `test_initial_greeting` — Add autouse fixture in `tests/test_jorge_seller_bot.py` to reset JorgeSellerBot state between tests

Run: `cd /path/to/repo && source venv/bin/activate && python -m pytest tests/ -x --tb=short`
Target: 279/279 pass
```

### Add Test Coverage

```
Add test coverage for untested modules in `jorge_real_estate_bots`. Read `docs/SPEC.md` §4.3 for the list.

Priority order:
1. `bots/shared/auth_service.py` — JWT generation, user CRUD, password hashing
2. `bots/shared/auth_middleware.py` — Token validation dependency
3. `bots/lead_bot/services/lead_analyzer.py` — Lead scoring, Claude integration
4. `bots/shared/claude_client.py` — Task complexity routing, prompt caching
5. `bots/lead_bot/main.py` — Webhook handler, signature verification

Test conventions:
- Use `pytest-asyncio` with `asyncio_mode = auto`
- Mock `AsyncSessionFactory` is auto-applied via conftest (returns empty results)
- Mock Claude client with `AsyncMock(return_value=LLMResponse(content="...", model="test"))`
- Use `@pytest.mark.integration` to skip mock DB for real integration tests
- Place tests in `tests/{module_path}/test_{filename}.py`
```

### Production Hardening

```
Apply production hardening fixes to `jorge_real_estate_bots`. Read `docs/SPEC.md` §5 for the full issue list.

Critical fixes (P0):
1. Add CORS middleware to all three bot `main.py` files
2. Add Pydantic request models to seller/buyer process endpoints (replace raw `request.json()`)
3. Create `.dockerignore` (exclude: .git, venv, __pycache__, tests, docs, .env, *.pyc)

High priority (P1):
4. Add rate limiting with slowapi or custom middleware
5. Move cryptography import to module level in lead_bot/main.py
6. Remove `reload=True` from seller_bot/main.py __main__ block

Medium priority (P2):
7. Replace all `datetime.utcnow()` with `datetime.now(datetime.UTC)`
8. Add Alembic downgrade() to initial migration
9. Persist performance metrics to Redis instead of in-memory dict
```

### API Review

```
Review the REST API design across all three bots in `jorge_real_estate_bots`. Read `docs/SPEC.md` §2.1 for endpoint inventory.

Evaluate:
1. **Consistency**: Are URL patterns, response formats, and error handling uniform?
2. **Validation**: Which endpoints accept raw JSON without Pydantic models?
3. **Error responses**: Are errors structured as `{"error": ..., "message": ..., "code": ...}`?
4. **Auth**: Is JWT consistently applied? Any gaps?
5. **OpenAPI**: Are response_model declarations complete for auto-docs?
6. **Versioning**: No API versioning exists — recommend approach.

Key files:
- `bots/lead_bot/main.py` (most complete — has Pydantic models, response_model)
- `bots/seller_bot/main.py` (raw request.json(), no response_model)
- `bots/buyer_bot/buyer_routes.py` (raw request.json(), no response_model)
```

### Security Audit

```
Perform a security audit on `jorge_real_estate_bots`. Read `docs/SPEC.md` §5 for known issues.

Focus areas:
1. **Authentication**: JWT implementation in `bots/shared/auth_service.py`, token handling, secret management
2. **Webhook verification**: GHL signature validation in `bots/lead_bot/main.py:105-145`
3. **Input validation**: Raw JSON endpoints without Pydantic validation
4. **Secrets management**: `.env` handling, no secrets in Docker images
5. **SQL injection**: Verify all DB queries use parameterized SQLAlchemy
6. **WebSocket auth**: JWT in query params (visible in logs)
7. **Rate limiting**: No implementation despite config fields
8. **Error leakage**: `detail=str(e)` in HTTPException responses exposes internals
9. **CORS**: No CORS middleware = open to all origins when added

Key files: `auth_service.py`, `auth_middleware.py`, `lead_bot/main.py`, `ghl_client.py`, `config.py`
```

### Database & Schema Review

```
Review the database schema and access patterns in `jorge_real_estate_bots`. Read `docs/SPEC.md` §2.3 for schema details.

Evaluate:
1. **Schema design**: Are models normalized appropriately? Missing indexes?
2. **JSONB usage**: 6 tables use JSONB columns — is this appropriate vs. normalized columns?
3. **Foreign keys**: Only 2 FK constraints (sessions→users, commissions→deals). Missing: conversations→contacts, leads→contacts, deals→contacts
4. **Migration safety**: Initial migration has no downgrade(). Autogenerate readiness.
5. **Session management**: Lazy init pattern in `database/session.py` — thread safety?
6. **Repository pattern**: `database/repository.py` — are upsert operations atomic?
7. **Connection pooling**: Hardcoded pool_size=10, max_overflow=0 — appropriate for 3 services sharing one DB?

Key files: `database/models.py`, `database/session.py`, `database/repository.py`, `alembic/versions/20260206_000001_initial_schema.py`
```

### Dashboard Review

```
Review the Streamlit command center in `jorge_real_estate_bots`. Read `docs/SPEC.md` §2.4.

Evaluate:
1. **Data sources**: Which components use real DB data vs. hardcoded mock data?
2. **Component architecture**: 23 components — are there redundancies? (e.g., hero_metrics_card vs hero_metrics_ui)
3. **Real-time updates**: WebSocket client in `event_client.py` — is it production-ready?
4. **Mobile support**: 5 mobile-specific components — responsive design approach?
5. **Auth**: `auth_component.py` — how does Streamlit auth integrate with JWT?
6. **Performance**: Any expensive queries or N+1 patterns in dashboard data service?

Key files: `command_center/dashboard_v3.py`, `command_center/components/`, `bots/shared/dashboard_data_service.py`
```

---

## Quick Reference for Agents

### Running Tests
```bash
cd /path/to/jorge_real_estate_bots
source venv/bin/activate
python -m pytest tests/ -x --tb=short        # Quick run
python -m pytest tests/ -v --tb=long          # Verbose
python -m pytest tests/shared/ -k "dashboard" # Filter
python -m pytest tests/ -m "not integration"  # Skip DB tests
```

### Key File Locations
```
Config:           bots/shared/config.py
DB Models:        database/models.py
DB Session:       database/session.py
Auth:             bots/shared/auth_service.py + auth_middleware.py
Claude AI:        bots/shared/claude_client.py
GHL CRM:          bots/shared/ghl_client.py
Events:           bots/shared/event_broker.py + event_models.py
Dashboard Data:   bots/shared/dashboard_data_service.py
Dashboard Models: bots/shared/dashboard_models.py
Test Config:      pytest.ini + tests/conftest.py
```

### Import Patterns
```python
from bots.shared.config import settings
from bots.shared.claude_client import ClaudeClient, LLMResponse, TaskComplexity
from bots.shared.ghl_client import GHLClient, get_ghl_client
from bots.shared.event_broker import event_broker
from bots.shared.auth_middleware import get_current_active_user
from bots.shared.auth_service import get_auth_service
from database.session import AsyncSessionFactory
from database.models import ConversationModel, LeadModel, ContactModel
from database.repository import upsert_contact, upsert_conversation
```
