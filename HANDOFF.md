# Jorge Real Estate Bots — Client Handoff

## What's Included

Three AI bots for GoHighLevel, a Streamlit command center, and a full test suite — 661 tests passing.

| Component | Port | Purpose |
|-----------|------|---------|
| **Lead Bot** | 8001 | 5-minute SLA enforcement, Q0–Q4 qualification, temperature scoring |
| **Seller Bot** | 8002 | FRS/PCS scoring, CMA analysis, pricing strategy |
| **Buyer Bot** | 8003 | Financial readiness checks, pre-approval flow, property matching |
| **Command Center** | 8501 | Streamlit dashboard — lead flow, bot performance, commission tracking |

---

## Live Deployment

**URL:** `https://jorge-realty-ai-xxdf.onrender.com`

- Lead Bot: `https://jorge-realty-ai-xxdf.onrender.com/lead/`
- Seller Bot: `https://jorge-realty-ai-xxdf.onrender.com/seller/`
- Buyer Bot: `https://jorge-realty-ai-xxdf.onrender.com/buyer/`
- Swagger docs: append `/docs` to any bot URL

---

## Required Environment Variables

Copy `.env.example` to `.env` and fill in these values before running locally or on a new server.

```bash
# AI (required)
ANTHROPIC_API_KEY=sk-ant-...

# GoHighLevel CRM (required)
GHL_API_KEY=...
GHL_LOCATION_ID=...
GHL_WEBHOOK_SECRET=...

# Database (required)
DATABASE_URL=postgresql://user:pass@host:5432/jorge_bots

# Redis (required)
REDIS_URL=redis://localhost:6379/0

# Jorge's business rules (pre-configured in .env.example)
JORGE_USER_ID=4lAS80xUq4MIRbgfQ5vg
JORGE_MIN_PRICE=200000
JORGE_MAX_PRICE=800000
JORGE_SERVICE_AREAS=Dallas,Plano,Frisco,McKinney,Allen
```

Optional: Twilio (SMS), SendGrid (email), Zillow API (CMA property data), Sentry (error tracking).

---

## Running Locally

**Demo mode** (mock AI, no API keys needed):

```bash
pip install -r requirements.txt
python jorge_launcher.py --demo
```

**Full stack with Docker Compose** (PostgreSQL + Redis + all 3 bots + dashboard):

```bash
cp .env.example .env   # fill in your keys
docker compose up
```

**Run tests:**

```bash
pytest tests/ -v
# 661 passing, ~2 min
```

---

## Deploying to Render

The repo includes a `Dockerfile` and `docker-compose.yml`. On Render:

1. Connect the GitHub repo (`ChunkyTortoise/jorge_real_estate_bots`)
2. Create a **Web Service** pointing to the Dockerfile
3. Set all env vars from the table above in the Render dashboard
4. Add a **Postgres** and **Redis** instance (Render provides both)

Or re-deploy to the existing service: `jorge-realty-ai-xxdf.onrender.com` (srv-d6d5go15pdvs73fcjjq0).

---

## GHL Webhook Setup

Point your GHL workflow webhooks to:

```
POST https://jorge-realty-ai-xxdf.onrender.com/lead/webhook/ghl
POST https://jorge-realty-ai-xxdf.onrender.com/seller/webhook/ghl
POST https://jorge-realty-ai-xxdf.onrender.com/buyer/webhook/ghl
```

See `docs/02-ghl-setup-guide.md` for the full GHL workflow configuration.

---

## Current Status

- 661 tests passing (as of 2026-03-03)
- All three bots working end-to-end with GHL
- Rate limiting active (Redis-backed, `X-RateLimit-*` headers)
- Cross-bot handoff with 0.7 confidence threshold and circular prevention
- CI/CD pipeline active on GitHub Actions

---

## Remaining Client Actions

Two items that only you can complete:

1. **Anthropic credits** — Top up at [console.anthropic.com](https://console.anthropic.com/). The bots use Claude Haiku (fast, cheap) for most messages and Claude Sonnet for complex analysis. Estimated cost: ~$0.10–0.50/day at typical lead volume.

2. **A2P 10DLC registration** — Required for SMS via Twilio. Register your business at [twilio.com/trust-hub](https://www.twilio.com/en-us/trust-hub). Without this, SMS messages may be filtered as spam. This is a carrier-level requirement, not a bot limitation.

---

## File Structure

```
jorge-real-estate-bots/
├── bots/
│   ├── lead_bot/       # Lead qualification + GHL webhook handler
│   ├── seller_bot/     # CMA + pricing strategy
│   └── buyer_bot/      # Pre-approval + property matching
├── agents/             # AI agent logic (intent decoder, handoff, temperature)
├── api/                # Shared FastAPI routes + middleware
├── command_center/     # Streamlit dashboard
├── database/           # SQLAlchemy models + Alembic migrations
├── services/           # GHL API client, Redis client, shared services
├── tests/              # 661 tests (unit + integration + E2E)
├── docs/               # Setup guides, specs, troubleshooting
├── docker-compose.yml  # Full stack (Postgres, Redis, 3 bots, dashboard)
├── Dockerfile          # Production image
├── jorge_launcher.py   # Dev launcher (--demo flag for mock mode)
└── .env.example        # All env var reference with descriptions
```

---

## API Docs

Each bot serves Swagger UI when running:

- Lead Bot: `http://localhost:8001/docs`
- Seller Bot: `http://localhost:8002/docs`
- Buyer Bot: `http://localhost:8003/docs`

---

## GitHub Repo

`https://github.com/ChunkyTortoise/jorge_real_estate_bots`

The repo is public. All code, tests, docs, and Docker configuration are included.
