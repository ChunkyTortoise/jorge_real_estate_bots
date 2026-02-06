# jorge_real_estate_bots — Technical Specification

**Repo**: `ChunkyTortoise/jorge_real_estate_bots` (private)
**Version**: 1.0.0 | **Last Updated**: 2026-02-05
**Status**: MVP complete, pre-production hardening needed

---

## 1. System Overview

Three-bot AI qualification system for a real estate agent, backed by FastAPI microservices, PostgreSQL, Redis, and a Streamlit command center. Each bot handles a distinct stage of the client lifecycle.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Lead Bot    │  │  Seller Bot  │  │  Buyer Bot   │
│  :8001       │  │  :8002       │  │  :8003       │
│  GHL webhook │  │  Q0-Q4 qual  │  │  Property    │
│  <5min rule  │  │  Confrontat. │  │  matching    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └────────┬────────┴────────┬────────┘
                │                 │
       ┌────────▼─────────┐  ┌───▼──────────────┐
       │  Shared Services │  │  Command Center   │
       │  Claude, GHL,    │  │  Streamlit :8501  │
       │  Events, Cache,  │  │  Dashboard v3     │
       │  Auth, Metrics   │  │  23 components    │
       └────────┬─────────┘  └──────────────────┘
                │
       ┌────────▼─────────┐
       │  PostgreSQL :5432 │
       │  Redis :6379      │
       └──────────────────┘
```

### Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.11+ |
| Web framework | FastAPI | 0.115+ |
| Dashboard | Streamlit | 1.39+ |
| ORM | SQLAlchemy (async) | 2.0+ |
| Database | PostgreSQL | 16 |
| Cache / Pub-Sub | Redis | 7 |
| AI | Anthropic Claude | Haiku/Sonnet/Opus |
| CRM | GoHighLevel API v2 | 2021-07-28 |
| HTTP client | httpx | 0.27+ |
| Retry | tenacity | 9+ |
| Auth | PyJWT + passlib[bcrypt] | - |
| Migrations | Alembic | 1.13+ |
| Container | Docker Compose | 3.8 |
| Tests | pytest + pytest-asyncio | - |

---

## 2. Module Map

### 2.1 Bot Services

#### Lead Bot (`bots/lead_bot/`)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `main.py` | FastAPI app, GHL webhook, WebSocket, performance middleware | `app` |
| `models.py` | Pydantic models: `LeadMessage`, `GHLWebhook`, `LeadAnalysisResponse`, `PerformanceStatus` | request/response models |
| `services/lead_analyzer.py` | Claude-powered lead scoring, cache, pattern matching | `LeadAnalyzer` |
| `websocket_manager.py` | Real-time dashboard push via Redis subscription | `websocket_manager` |

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ghl/webhook/new-lead` | GHL signature | Inbound lead from CRM (<5 min SLA) |
| POST | `/analyze-lead` | JWT | Direct lead analysis |
| GET | `/health` | None | Health check |
| GET | `/performance` | JWT | 5-min rule compliance |
| GET | `/metrics` | JWT | Legacy metrics |
| WS | `/ws/dashboard` | JWT (query) | Real-time event stream |
| GET | `/api/events/recent` | JWT | HTTP polling fallback |
| GET | `/api/websocket/status` | JWT | WebSocket health |
| GET | `/api/events/health` | JWT | Event system health |

#### Seller Bot (`bots/seller_bot/`)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `main.py` | FastAPI app, REST API | `app` |
| `jorge_seller_bot.py` | Q0-Q4 confrontational qualification, temperature scoring | `JorgeSellerBot`, `SellerQualificationState` |

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/jorge-seller/process` | JWT | Process seller message |
| GET | `/api/jorge-seller/{contact_id}/progress` | JWT | Qualification progress |
| GET | `/api/jorge-seller/conversations/{id}` | JWT | Single conversation |
| GET | `/api/jorge-seller/active` | JWT | All active conversations |
| GET | `/health` | None | Health check |

**Known issue**: `seller_bot/main.py:97` has `reload=True` in production `__main__` block.

#### Buyer Bot (`bots/buyer_bot/`)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `main.py` | FastAPI app, registers `buyer_routes` | `app` |
| `buyer_bot.py` | Property matching, preference extraction, needs analysis | `JorgeBuyerBot` |
| `buyer_prompts.py` | Claude system/user prompts for buyer qualification | prompt templates |
| `buyer_routes.py` | APIRouter with 6 endpoints | `router`, `init_buyer_bot` |

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/jorge-buyer/process` | JWT | Process buyer message |
| GET | `/api/jorge-buyer/{contact_id}/progress` | JWT | Buyer analytics |
| GET | `/api/jorge-buyer/preferences/{contact_id}` | JWT | Saved preferences |
| GET | `/api/jorge-buyer/matches/{contact_id}` | JWT | Property matches |
| GET | `/api/jorge-buyer/active` | JWT | Active conversations |
| GET | `/health` | None | Health check |

### 2.2 Shared Services (`bots/shared/`)

| File | Purpose | Singleton? |
|------|---------|-----------|
| `config.py` | Pydantic `Settings` with 40+ fields, `.env` loader | `settings` global |
| `claude_client.py` | Claude AI with task-complexity routing (Haiku/Sonnet/Opus), prompt caching, streaming | No (factory) |
| `ghl_client.py` | GoHighLevel API v2 async client: contacts, opportunities, messaging, workflows, tags, batch ops | No (factory) |
| `event_broker.py` | Redis pub/sub + Streams, circuit breaker, 60s event retention, fallback to `/tmp` file | `event_broker` singleton |
| `event_models.py` | Pydantic event types: `BaseEvent`, `EventType` enum, factory functions | - |
| `cache_service.py` | Redis caching layer | - |
| `auth_service.py` | JWT auth, user CRUD, password hashing (bcrypt), RBAC | `get_auth_service()` |
| `auth_middleware.py` | FastAPI `Depends()` auth dependency | `get_current_active_user()` |
| `dashboard_data_service.py` | Aggregation layer for dashboard: conversations, hero metrics, performance | `DashboardDataService` |
| `dashboard_models.py` | 15 dataclasses: `HeroMetrics`, `ConversationState`, `PaginatedConversations`, `CommissionMetrics`, etc. | - |
| `metrics_service.py` | Budget/timeline/commission analytics from DB | - |
| `business_rules.py` | Jorge's business validation (price range, service areas, commission calc) | - |
| `lead_intelligence_optimized.py` | Enhanced lead intelligence features | - |
| `performance_tracker.py` | Rolling-window metrics (cache, AI, GHL response times) | - |
| `logger.py` | Structured logging with correlation ID | `get_logger()` |
| `models.py` | Shared Pydantic schemas | - |

### 2.3 Database (`database/`)

| File | Purpose |
|------|---------|
| `base.py` | SQLAlchemy `DeclarativeBase` |
| `models.py` | 9 ORM models (see below) |
| `session.py` | Lazy-init async engine + session factory |
| `repository.py` | Async CRUD: upsert contacts/conversations/leads/preferences, fetch properties |

**ORM Models (9 tables):**

| Model | Table | Key Fields |
|-------|-------|-----------|
| `UserModel` | `users` | email, name, role, password_hash, is_active, must_change_password |
| `SessionModel` | `sessions` | user_id (FK→users), token_hash, expires_at |
| `ContactModel` | `contacts` | contact_id (GHL), location_id, name, email, phone |
| `ConversationModel` | `conversations` | contact_id, bot_type, stage, temperature, conversation_history (JSONB), extracted_data (JSONB), metadata_json (JSONB) |
| `LeadModel` | `leads` | contact_id, score, temperature, budget_min/max, timeline, service_area_match, is_qualified, metadata_json (JSONB) |
| `DealModel` | `deals` | contact_id, opportunity_id, status, commission, closed_at, metadata_json (JSONB) |
| `CommissionModel` | `commissions` | deal_id (FK→deals), amount, status, closed_at |
| `PropertyModel` | `properties` | mls_id, address, city, state, zip, price, beds, baths, sqft, status, metadata_json (JSONB) |
| `BuyerPreferenceModel` | `buyer_preferences` | contact_id, beds_min, baths_min, sqft_min, price_min/max, preapproved, timeline_days, motivation, temperature, preferences_json (JSONB), matches_json (JSONB) |

**Indexes**: `ix_conversations_contact_bot` (composite), plus individual indexes on contact_id, email, bot_type, token_hash.

**Migration**: Single initial migration `20260206_000001_initial_schema.py` creates all 9 tables.

### 2.4 Command Center (`command_center/`)

| File | Purpose |
|------|---------|
| `dashboard_v3.py` | Main Streamlit entry point |
| `event_client.py` | WebSocket client for real-time events |
| `production_monitor.py` | Production health monitoring |
| `utils/theme_manager.py` | UI theming |
| `components/` | 23 Streamlit components (see below) |
| `archived/` | Legacy dashboard v1, v2 |

**Components (23):**
`active_conversations`, `active_conversations_table`, `activity_feed`, `auth_component`, `commission_tracking`, `enhanced_hero_metrics`, `export_manager`, `field_access_dashboard`, `ghl_integration_status`, `ghl_status_ui`, `global_filters`, `hero_metrics_card`, `hero_metrics_ui`, `lead_intelligence_dashboard`, `mobile_dashboard_integration`, `mobile_metrics_cards`, `mobile_navigation`, `mobile_responsive_layout`, `offline_indicator`, `performance_analytics`, `performance_chart`, `seller_bot_pipeline`, `touch_optimized_charts`

### 2.5 Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | 6 services: postgres, redis, lead-bot, seller-bot, buyer-bot, dashboard + launcher |
| `Dockerfile` | Python 3.11-slim, exposes 8001/8002/8003/8501 |
| `jorge_launcher.py` | Multi-service launcher (currently only lead bot enabled) |
| `alembic.ini` + `alembic/` | Database migration management |
| `requirements.txt` | ~90 dependencies across 12 categories |

---

## 3. Key Patterns & Conventions

### 3.1 Async Everything
All bot logic, DB access, and external API calls are async. The pattern:
```python
async with AsyncSessionFactory() as session:
    result = await session.execute(select(Model).where(...))
```

### 3.2 Authentication
- JWT tokens with 1-hour expiry
- `Depends(get_current_active_user())` on all non-health endpoints
- WebSocket auth via query param `?token=<jwt>`
- GHL webhook auth via RSA signature or HMAC

### 3.3 Event-Driven Architecture
- Redis pub/sub channels: `jorge:channel:{category}` (leads, ghl, cache, system)
- Redis Streams: `jorge:stream:{category}` (60-second buffer)
- Circuit breaker: 5 failures → open for 30s
- Fallback: `/tmp/jorge_events_fallback.jsonl`

### 3.4 Claude AI Routing
| Complexity | Model | Use Case |
|-----------|-------|----------|
| ROUTINE | Haiku | Lead categorization, basic scoring |
| COMPLEX | Sonnet | Lead qualification, analysis |
| HIGH_STAKES | Opus | Seller negotiations, pricing |

Prompt caching enabled for system prompts >1024 chars.

### 3.5 Configuration
Single `Settings` class (Pydantic) with `.env` file support. Key groups:
- API keys (Anthropic, GHL, Zillow, Twilio, SendGrid)
- Claude model selection
- Database/Redis URLs
- Performance SLAs (5-min response, 500ms analysis, 90s CMA)
- Business rules (price range, service areas, commission rates)
- Security (JWT secret, webhook secrets)
- Feature flags (multi-tenant, mock LLM, test mode)

### 3.6 Naming Conventions
- Files/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `SCREAMING_SNAKE_CASE`
- DB tables: `plural_snake_case`
- Bot endpoints: `/api/jorge-{bot-type}/{action}`

---

## 4. Current Test Status

**Results**: 270 pass / 9 fail / 279 total (as of 2026-02-05)

### 4.1 Test Infrastructure
- `pytest.ini`: `asyncio_mode = auto`
- `tests/conftest.py`: Autouse fixture patches `AsyncSessionFactory` across 5 import locations
- Tests marked `@pytest.mark.integration` bypass mock and hit real DB
- Streamlit tests use `tests/command_center/streamlit_stub.py` to mock `st.*`

### 4.2 Failing Tests (9)

| # | Test | Root Cause | Fix Approach |
|---|------|-----------|-------------|
| 1 | `test_global_filters_render_smoke` | Streamlit stub missing `st.title` | Add `title` to `streamlit_stub.py` |
| 2 | `test_mobile_dashboard_integration_render` | DataFrame array length mismatch in mock data | Fix mock data to have consistent column lengths |
| 3 | `test_get_active_conversations_pagination` | Patches `_fetch_real_conversation_data` but service calls `_fetch_active_conversations` | Patch the correct method name |
| 4 | `test_conversation_stage_distribution` | Same as #3 — wrong method patched | Patch `_fetch_active_conversations` |
| 5 | `test_conversation_temperature_distribution` | Same as #3 — wrong method patched | Patch `_fetch_active_conversations` |
| 6 | `test_get_budget_distribution_success` | Expects real lead data in DB; mock session returns empty | Provide mock `LeadModel` data in test fixture |
| 7 | `test_get_timeline_distribution_success` | Same — expects real data | Provide mock data |
| 8 | `test_get_commission_metrics_success` | Same — expects real data | Provide mock data |
| 9 | `test_initial_greeting` | Test ordering pollution — passes alone, fails in suite | Add `autouse` fixture to reset `JorgeSellerBot` state, or use `pytest-randomly` |

### 4.3 Untested Modules (15)

| Module | Priority | Risk |
|--------|---------|------|
| `bots/lead_bot/main.py` | HIGH | Webhook handler, signature verification |
| `bots/lead_bot/models.py` | LOW | Pydantic models (type-checked) |
| `bots/lead_bot/services/lead_analyzer.py` | HIGH | Core lead scoring logic |
| `bots/lead_bot/websocket_manager.py` | MEDIUM | Real-time push |
| `bots/seller_bot/main.py` | HIGH | API routes |
| `bots/shared/auth_middleware.py` | HIGH | Auth gate for all endpoints |
| `bots/shared/auth_service.py` | HIGH | JWT, passwords, user CRUD |
| `bots/shared/business_rules.py` | MEDIUM | Commission calc, validation |
| `bots/shared/cache_service.py` | MEDIUM | Redis caching |
| `bots/shared/claude_client.py` | HIGH | AI integration |
| `bots/shared/config.py` | LOW | Pydantic settings |
| `bots/shared/event_broker.py` | MEDIUM | Event system, circuit breaker |
| `bots/shared/event_models.py` | LOW | Event type definitions |
| `bots/shared/logger.py` | LOW | Logging setup |
| `bots/shared/models.py` | LOW | Shared schemas |

---

## 5. Known Issues & Technical Debt

### 5.1 Critical

| # | Issue | Location | Impact |
|---|-------|---------|--------|
| C1 | No CORS middleware on any bot | All `main.py` files | Browser-based clients blocked |
| C2 | No Pydantic request models on seller/buyer process endpoints | `seller_bot/main.py:42`, `buyer_routes.py:24` | No input validation on `request.json()` |
| C3 | Missing `.dockerignore` | Root | Docker builds include venv, .git, tests, __pycache__ |
| C4 | `reload=True` hardcoded in seller bot `__main__` | `seller_bot/main.py:97` | Dev mode in production |
| C5 | `datetime.utcnow()` deprecated | `buyer_bot.py:73,97`, `database/models.py` | Python 3.12+ warnings, removal in 3.14 |

### 5.2 High

| # | Issue | Location | Impact |
|---|-------|---------|--------|
| H1 | GHL webhook signature verification imports `cryptography` at call time | `lead_bot/main.py:113` | First call latency, import errors not caught at startup |
| H2 | Performance stats stored in module-level dict (lost on restart) | `lead_bot/main.py:40-45` | No persistence, inaccurate metrics |
| H3 | No rate limiting implemented despite `rate_limit_per_minute` config | All endpoints | DDoS/abuse risk |
| H4 | httpx client created per-request in `GHLClient._get_client()` if not using context manager | `ghl_client.py:91-95` | Connection overhead |
| H5 | `event_broker` singleton creates Redis pool at import time on first `EventBroker()` | `event_broker.py:106-132` | Can fail if Redis unavailable at import |
| H6 | Command center components use hardcoded mock data in production | Multiple `components/*.py` | Dashboard shows fake data |

### 5.3 Medium

| # | Issue | Location | Impact |
|---|-------|---------|--------|
| M1 | No Alembic `downgrade()` in initial migration | `alembic/versions/20260206_*.py` | Cannot rollback schema |
| M2 | No database connection pooling configuration exposed via env vars | `database/session.py:38-46` | Hardcoded pool_size=10, max_overflow=0 |
| M3 | `jorge_launcher.py` has seller/buyer bots disabled | `jorge_launcher.py` | Only lead bot launches |
| M4 | No health check aggregation endpoint | - | Must hit each bot separately |
| M5 | WebSocket authentication sends JWT as query param | `lead_bot/main.py:416` | Token visible in logs/URLs |
| M6 | No graceful shutdown handling for in-flight requests | All bots | Requests dropped on restart |
| M7 | `send_immediate_followup` sends raw contact_id in SMS | `ghl_client.py:573-578` | Exposes internal IDs to clients |

### 5.4 Low

| # | Issue | Location | Impact |
|---|-------|---------|--------|
| L1 | `FutureWarning: 'M' deprecated, use 'ME'` | `mobile_dashboard_integration.py:275` | Will break on pandas upgrade |
| L2 | `DeprecationWarning: datetime.utcnow()` | Multiple files | Python 3.14 removal |
| L3 | Archived dashboards v1/v2 still in codebase | `command_center/archived/` | Dead code |
| L4 | Example/script files not maintained | `examples/`, `scripts/` | Misleading reference |
| L5 | `check_health_sync()` in GHL client uses separate `httpx.Client` | `ghl_client.py:614-640` | Inconsistent with async pattern |

---

## 6. Configuration Reference

### 6.1 Environment Variables (Required)

```bash
# API Keys
ANTHROPIC_API_KEY=
GHL_API_KEY=
GHL_LOCATION_ID=
ZILLOW_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
SENDGRID_API_KEY=

# Infrastructure
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jorge_bots
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET=  # Must change from default
ADMIN_DEFAULT_PASSWORD=  # Optional, auto-generated if unset
GHL_WEBHOOK_SECRET=  # Optional HMAC verification
GHL_WEBHOOK_PUBLIC_KEY=  # Optional RSA verification
```

### 6.2 Environment Variables (Optional)

```bash
# AI Model Override
CLAUDE_MODEL=claude-3-5-sonnet-20241022
CLAUDE_SONNET_MODEL=claude-3-5-sonnet-20241022
CLAUDE_HAIKU_MODEL=claude-3-5-haiku-20241022
CLAUDE_OPUS_MODEL=claude-3-opus-20240229

# Business Rules
JORGE_MIN_PRICE=200000
JORGE_MAX_PRICE=800000
JORGE_SERVICE_AREAS=Dallas,Plano,Frisco,McKinney,Allen
JORGE_STANDARD_COMMISSION=0.06
JORGE_MINIMUM_COMMISSION=0.04

# Performance SLAs
LEAD_RESPONSE_TIMEOUT_SECONDS=300
LEAD_ANALYSIS_TIMEOUT_MS=500
CMA_GENERATION_TIMEOUT_SECONDS=90

# Feature Flags
MULTI_TENANT_ENABLED=false
USE_MOCK_LLM=false
TEST_MODE=false
ENVIRONMENT=development
DEBUG=false

# Monitoring
SENTRY_DSN=
DATADOG_API_KEY=
```

---

## 7. Deployment

### 7.1 Docker Compose

```bash
docker compose up -d        # Start all services
docker compose logs -f      # Tail all logs
docker compose ps           # Service status
```

**Services**: postgres (5432), redis (6379), lead-bot (8001), seller-bot (8002), buyer-bot (8003), dashboard (8501), launcher

**Health checks**: All services have health checks with 10-15s intervals and 5 retries.

### 7.2 Alembic Migrations

```bash
alembic upgrade head        # Apply migrations
alembic downgrade -1        # Rollback one (NOT IMPLEMENTED in initial migration)
alembic revision --autogenerate -m "description"  # Generate new migration
```

### 7.3 Running Locally

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with real credentials

# Database
docker compose up -d postgres redis
alembic upgrade head

# Run individual bots
uvicorn bots.lead_bot.main:app --port 8001
uvicorn bots.seller_bot.main:app --port 8002
uvicorn bots.buyer_bot.main:app --port 8003
streamlit run command_center/dashboard_v3.py --server.port 8501

# Or use launcher (only lead bot enabled currently)
python jorge_launcher.py
```

---

## 8. Development Priorities

### Phase 3: Production Hardening (Recommended Next)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P0 | Add CORS middleware to all bots | S | Unblocks browser clients |
| P0 | Add Pydantic request models to seller/buyer endpoints | M | Input validation |
| P0 | Create `.dockerignore` | S | Smaller images, no secrets in container |
| P1 | Fix 9 failing tests | M | CI reliability |
| P1 | Add rate limiting (slowapi or custom) | M | Security |
| P1 | Add tests for auth_service, auth_middleware | M | Auth coverage |
| P1 | Add tests for lead_analyzer, claude_client | L | Core logic coverage |
| P2 | Replace `datetime.utcnow()` with `datetime.now(UTC)` | S | Future-proof |
| P2 | Add Alembic downgrade support | S | Safe rollbacks |
| P2 | Move performance stats to Redis | M | Persistent metrics |
| P2 | Add API gateway / unified health endpoint | M | Observability |
| P3 | Enable seller/buyer bots in launcher | S | Full deployment |
| P3 | Remove archived dashboards and dead scripts | S | Cleanup |
| P3 | Replace hardcoded mock data in command center components | L | Real dashboard data |

### Phase 4: Feature Completeness

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P1 | Multi-tenant support (config flag exists) | L | Scale to multiple agents |
| P1 | Webhook retry/dead-letter queue | M | Reliability |
| P2 | CMA report generation pipeline | L | Core feature |
| P2 | Twilio/SendGrid integration activation | M | Communication channels |
| P2 | Property data ingestion (Zillow API) | M | Buyer bot matching |
| P3 | Sentry/Datadog integration | M | Production monitoring |
| P3 | Load testing baseline (locustfile exists) | M | Performance validation |

---

## 9. Architecture Decision Records

### ADR-1: Microservice Per Bot
**Decision**: Each bot runs as an independent FastAPI service on separate ports.
**Rationale**: Independent scaling, isolated failures, independent deployment.
**Trade-off**: Operational complexity, no shared in-process state.

### ADR-2: Lazy Database Initialization
**Decision**: Engine and session factory created on first use, not at import.
**Rationale**: Tests can import modules without requiring PostgreSQL.
**Trade-off**: First request slightly slower; runtime errors instead of startup errors.

### ADR-3: Redis Event Broker with Circuit Breaker
**Decision**: All inter-service events go through Redis pub/sub with circuit breaker and file fallback.
**Rationale**: Resilient event delivery; degraded mode when Redis unavailable.
**Trade-off**: 60-second retention only; events can be lost if both Redis and filesystem fail.

### ADR-4: JWT Authentication on All Endpoints
**Decision**: Every non-health endpoint requires JWT.
**Rationale**: Security baseline; admin dashboard protected.
**Trade-off**: GHL webhook uses signature verification instead of JWT.

### ADR-5: Claude Task Complexity Routing
**Decision**: Route to Haiku/Sonnet/Opus based on declared task complexity.
**Rationale**: Cost optimization — routine tasks use cheaper models.
**Trade-off**: Caller must declare complexity; no automatic detection.

---

## 10. Qualification Frameworks

### Seller Bot: Q0-Q4 Stages
| Stage | Question | Data Extracted |
|-------|----------|---------------|
| Q0 | Initial greeting | Name, property address |
| Q1 | Property condition | Condition rating, repairs needed |
| Q2 | Price expectation | Target price, willingness to negotiate |
| Q3 | Motivation to sell | Motivation level, urgency |
| Q4 | Offer acceptance | Deal readiness |
| QUALIFIED | All Q's answered | Full qualification data |
| STALLED | No response >48h | - |

**Temperature**: HOT (motivated, ready) / WARM (interested, not urgent) / COLD (exploring)

### Lead Bot: Scoring Framework
| Factor | Weight | Source |
|--------|--------|--------|
| Budget match | High | Extracted from message |
| Service area match | High | GHL contact data |
| Timeline urgency | Medium | Conversation analysis |
| Financing status | Medium | Extracted from message |
| Engagement level | Low | Response patterns |

**Score**: 0-100, mapped to temperature (HOT ≥80, WARM ≥50, COLD <50)

### Buyer Bot: Preference Matching
| Preference | DB Field | Match Logic |
|-----------|----------|-------------|
| Budget range | price_min, price_max | Property price within range |
| Bedrooms | beds_min | Property beds ≥ minimum |
| Bathrooms | baths_min | Property baths ≥ minimum |
| Square footage | sqft_min | Property sqft ≥ minimum |
| Pre-approval | preapproved | Boolean flag |
| Timeline | timeline_days | Days until needed |

---

## 11. File Tree (Complete)

```
jorge_real_estate_bots/
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 20260206_000001_initial_schema.py
├── bots/
│   ├── buyer_bot/
│   │   ├── __init__.py
│   │   ├── buyer_bot.py
│   │   ├── buyer_prompts.py
│   │   ├── buyer_routes.py
│   │   └── main.py
│   ├── lead_bot/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── lead_analyzer.py
│   │   └── websocket_manager.py
│   ├── seller_bot/
│   │   ├── __init__.py
│   │   ├── jorge_seller_bot.py
│   │   └── main.py
│   └── shared/
│       ├── __init__.py
│       ├── auth_middleware.py
│       ├── auth_service.py
│       ├── business_rules.py
│       ├── cache_service.py
│       ├── claude_client.py
│       ├── config.py
│       ├── dashboard_data_service.py
│       ├── dashboard_models.py
│       ├── event_broker.py
│       ├── event_models.py
│       ├── ghl_client.py
│       ├── lead_intelligence_optimized.py
│       ├── logger.py
│       ├── metrics_service.py
│       ├── models.py
│       └── performance_tracker.py
├── command_center/
│   ├── archived/
│   │   ├── dashboard.py
│   │   └── dashboard_v2.py
│   ├── components/
│   │   ├── __init__.py
│   │   └── [23 component files]
│   ├── dashboard_v3.py
│   ├── event_client.py
│   ├── production_monitor.py
│   └── utils/
│       └── theme_manager.py
├── database/
│   ├── __init__.py
│   ├── base.py
│   ├── models.py
│   ├── repository.py
│   └── session.py
├── docs/
│   ├── handoffs/
│   ├── phases/
│   ├── reference/
│   └── screenshots/
├── examples/
│   └── lead_intelligence_integration_example.py
├── scripts/
│   ├── phase3c_integration_test.py
│   ├── test_auth_system.py
│   ├── test_phase1_integration.py
│   ├── test_real_data_integration.py
│   ├── validate_seller_bot.py
│   └── verify_ghl_integration.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── buyer_bot/
│   │   └── test_buyer_bot.py
│   ├── command_center/
│   │   ├── __init__.py
│   │   ├── streamlit_stub.py
│   │   ├── test_active_conversations_table.py
│   │   ├── test_component_smoke.py
│   │   ├── test_enhanced_hero_metrics.py
│   │   ├── test_ghl_integration_status.py
│   │   ├── test_hero_metrics_card.py
│   │   ├── test_mobile_components.py
│   │   └── test_performance_chart.py
│   ├── load/
│   │   └── locustfile.py
│   ├── seller_bot/
│   │   ├── __init__.py
│   │   └── test_persistence.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── test_dashboard_data_service.py
│   │   ├── test_dashboard_models.py
│   │   ├── test_ghl_client.py
│   │   ├── test_lead_intelligence_optimized.py
│   │   ├── test_metrics_service.py
│   │   └── test_performance_tracker.py
│   └── test_jorge_seller_bot.py
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── jorge_launcher.py
├── pytest.ini
└── requirements.txt
```
