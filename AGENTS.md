# jorge-real-estate-bots: Project Context

FastAPI bot for GoHighLevel-integrated real estate workflows. Stack: FastAPI, Redis, Claude, Postgres, async SQLAlchemy. Single bot process at port 8001; all webhooks route through `bots/lead_bot/main.py`.

## Start here
- `README.md` for the quickest “how to run” path.
- `docs/SPEC.md` for the authoritative architecture/module map, API inventory, DB schema, and known issues.

## Common development commands

### Environment setup (local)
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Notes:
- Most modules import `bots.shared.config.settings`, which instantiates `Settings()` at import time and loads `.env`. If required env vars are missing, imports will fail early.

### Run dependencies (Postgres + Redis)
```bash
docker compose up -d postgres redis
# (older docker installs)
# docker-compose up -d postgres redis
```

### Database migrations (Alembic)
`alembic.ini` reads `${DATABASE_URL}`.
```bash
alembic upgrade head

# If running via docker compose service container:
# docker compose exec lead-bot alembic upgrade head
```

### Run the service (local)
All three bots (Lead, Seller, Buyer) run in a **single FastAPI process** using APIRouter. There is one entry point.
```bash
# Single bot process (:8001), handles all webhook routes
uvicorn bots.lead_bot.main:app --host 0.0.0.0 --port 8001 --reload

# Or via Makefile shortcut
make demo

# Streamlit command center (:8501)
streamlit run command_center/dashboard_v3.py --server.port 8501
```
Quick health check:
```bash
curl http://localhost:8001/health
```

### Run everything (Docker)
```bash
docker compose up --build
```

### Tests
Pytest is configured with `asyncio_mode = auto` (`pytest.ini`). Unit tests default to a mocked DB session.
```bash
# Full suite
pytest tests/ -v

# With coverage
pytest tests/ --cov=bots --cov=command_center --cov-report=term-missing

# Run a single file
pytest tests/shared/test_metrics_service.py -v

# Run a single test
pytest tests/shared/test_metrics_service.py::test_get_budget_distribution_success -v

# Keyword filter
pytest tests/ -k "dashboard" -v

# Skip integration-marked tests
pytest tests/ -m "not integration" -v

# Run only integration tests (requires real DB)
pytest tests/ -m integration -v
```

### Lint / format / types
There is no `pyproject.toml`/`ruff.toml`/`mypy.ini` checked in, so these run with defaults.
```bash
ruff check .
ruff format --check .

# (If you want mypy locally)
mypy bots/ command_center/ database/
```

## High-level architecture (big picture)

### Services and boundaries
Single-process architecture: all bots mount as APIRouters into `bots/lead_bot/main.py`:
- `bots/lead_bot/`: **Sole entry point** (`main.py`). Hosts all routers: `routes_webhook.py`, `routes_dashboard.py`, `routes_admin.py`, `routes_realtime.py`, `routes_productization.py`, `routes_test_endpoints.py`.
- `bots/seller_bot/`: Seller qualification logic (Q0-Q4). Imported as a class by `routes_webhook.py`. No separate FastAPI app.
- `bots/buyer_bot/`: Buyer qualification logic. Imported as a class by `routes_webhook.py`. No separate FastAPI app.
- `command_center/`: Streamlit dashboard (“Command Center”). Entry: `command_center/dashboard_v3.py`.
- `database/`: Async SQLAlchemy models/session + small “repository” helper functions.

### Shared services (cross-cutting)
Most non-trivial behavior lives in `bots/shared/`:
- **Configuration**: `bots/shared/config.py` defines `Settings` and instantiates the global `settings` object (loads `.env`).
- **Claude integration**: `bots/shared/claude_client.py` provides async generation with explicit `TaskComplexity` routing (Haiku/Sonnet/Opus) and prompt caching.
- **GoHighLevel integration**: `bots/shared/ghl_client.py` wraps the GHL API with an async `httpx` client and retry logic.
- **Caching**: `bots/shared/cache_service.py` provides Redis-backed cache with an in-memory fallback (used by lead analysis + dashboard aggregation).
- **Events (real-time)**:
  - `bots/shared/event_models.py` defines typed Pydantic event models and categorization.
  - `bots/shared/event_broker.py` publishes to Redis pub/sub and also persists short-lived events to Redis Streams (60s retention) with a circuit breaker + file fallback.
- **Auth**:
  - `bots/shared/auth_service.py` owns JWT/session logic and user CRUD backed by DB + cache.
  - `bots/shared/auth_middleware.py` exposes FastAPI `Depends(...)` helpers like `get_current_active_user()` (used by most non-health endpoints).
- **Dashboard aggregation**:
  - `bots/shared/dashboard_data_service.py` is the “query layer” for Streamlit, combining conversation data + metrics with caching.
  - `bots/shared/metrics_service.py` aggregates performance + business metrics (lead budget/timeline distributions, commission metrics, etc.) and caches them.

### Persistence layer
- `database/session.py`: lazy-initialized async engine + `AsyncSessionFactory()` (important: importing shouldn’t require a live DB).
- `database/models.py`: ORM models (users/sessions/contacts/conversations/leads/deals/commissions/properties/buyer_preferences).
- `database/repository.py`: convenience upsert/query functions used by bots and dashboard services.

### Real-time dashboard flow
- Bots publish structured events via `event_broker`.
- Lead bot hosts a WebSocket endpoint (see `bots/lead_bot/main.py`) and uses `bots/lead_bot/websocket_manager.py` to:
  - subscribe to Redis pub/sub
  - broadcast sanitized events to connected dashboard clients
  - optionally replay recent events from the Redis Streams buffer

## Testing architecture (what’s non-obvious)
- `tests/conftest.py` autouses a fixture that monkeypatches `AsyncSessionFactory` in multiple import locations so unit tests don’t require Postgres.
- Any test marked `@pytest.mark.integration` opts out of that patch and will hit a real database.
