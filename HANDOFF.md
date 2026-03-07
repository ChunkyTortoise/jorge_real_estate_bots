# Jorge Real Estate Bots -- Client Handoff

## What's Included

Three AI bots for GoHighLevel, a Streamlit command center, and a full test suite -- 1792 tests passing.

| Component | Port | Purpose |
|-----------|------|---------|
| **Lead Bot** | 8001 | 5-minute SLA enforcement, Q0-Q4 qualification, temperature scoring |
| **Seller Bot** | 8002 | FRS/PCS scoring, CMA analysis, pricing strategy |
| **Buyer Bot** | 8003 | Financial readiness checks, pre-approval flow, property matching |
| **Command Center** | 8501 | Streamlit dashboard -- lead flow, bot performance, commission tracking |

---

## Live Deployment

**URL:** `https://jorge-realty-ai-xxdf.onrender.com`

- Lead Bot: `https://jorge-realty-ai-xxdf.onrender.com/lead/`
- Seller Bot: `https://jorge-realty-ai-xxdf.onrender.com/seller/`
- Buyer Bot: `https://jorge-realty-ai-xxdf.onrender.com/buyer/`
- Swagger docs: append `/docs` to any bot URL

---

## Render Dashboard URLs

| Resource | URL |
|----------|-----|
| Web Service | https://dashboard.render.com/web/srv-d6d5go15pdvs73fcjjq0 |
| Redis | `red-d6d54jfpm1nc739jgnm0:6379` (internal, not publicly accessible) |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI responses |
| `GHL_API_KEY` | Yes | GoHighLevel API key for CRM operations |
| `GHL_LOCATION_ID` | Yes | GHL location (sub-account) ID |
| `GHL_CALENDAR_ID` | Yes | GHL calendar ID for booking appointments |
| `JORGE_USER_ID` | Yes | Jorge's GHL user ID for assignment |
| `JORGE_CALENDAR_ID` | Yes | Jorge's calendar ID for availability lookups |
| `REDIS_URL` | Yes | Redis connection URL (conversation state, rate limiting, funnel data) |
| `ADMIN_API_KEY` | Yes | API key for admin endpoints (`X-Admin-Key` header) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | Secret for dashboard JWT auth tokens |
| `GHL_WEBHOOK_SECRET` | **Must be EMPTY** | Leave unset in Render. If set, all webhooks return 401. |

Copy `.env.example` to `.env` for local development. On Render, set these in the `jorge-env` environment group.

---

## Common Operations

### Reset a conversation

```bash
curl -X DELETE https://jorge-realty-ai-xxdf.onrender.com/admin/reset-state/{bot}/{contact_id} \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

Replace `{bot}` with `lead`, `buyer`, or `seller` and `{contact_id}` with the GHL contact ID.

### Reassign a contact to a different bot

Update the contact's `customData.botType` field in GoHighLevel to `buyer` or `seller`. The next incoming message will route to the new bot.

Alternatively, use the admin API:

```bash
curl -X POST https://jorge-realty-ai-xxdf.onrender.com/admin/reassign-bot \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{"contact_id": "CONTACT_ID", "mode": "buyer"}'
```

### Manual takeover (bot goes silent)

Add the **"Jorge-Active"** tag to the contact in GoHighLevel. When this tag is present, the bot will not respond to messages from that contact, allowing a human agent to take over.

Remove the tag to re-enable bot responses.

---

## Troubleshooting Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| Booking returns 404 | GHL API key missing `calendars.write` scope | Re-generate GHL API key with Calendar permissions |
| Webhooks return 401 | `GHL_WEBHOOK_SECRET` is set | Remove `GHL_WEBHOOK_SECRET` from Render env vars (must be empty) |
| Bot not responding | Service down or misconfigured | Check `/health/aggregate`, verify Redis is up, verify `GHL_API_KEY` is valid |
| Admin endpoints return 503 | `ADMIN_API_KEY` not set | Set `ADMIN_API_KEY` in Render environment variables |
| Bot responds in English | Missing Spanish config | Verify bot system prompts include Spanish language instruction |
| Rate limit errors (429) | Too many messages per contact | Default: 10 messages/min per contact. Wait or adjust in admin settings |

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for the full troubleshooting guide.

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
# 1792 passing, ~70s
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

- **1792 tests passing** (as of 2026-03-07)
- All three bots working end-to-end with GHL
- **Redis connected** (`redis: ok` in `/health/aggregate`) — Render Redis fully reachable, no MemoryCache fallback
- **All 9 DB tables migrated** — confirmed via `/health/schema-check`. Alembic runs on every boot (fail-loud: container won't start if Postgres is down)
- **Lyrio Dashboard on live data** — wired to live GHL + Jorge API via `JorgeApiDataProvider`
- Rate limiting active (Redis-backed, `X-RateLimit-*` headers)
- Cross-bot handoff with 0.7 confidence threshold and circular prevention
- CI/CD pipeline active on GitHub Actions
- Buyer Q4 loop limit (3 attempts before STALLED)
- Funnel attribution with Redis persistence (30-day TTL)
- Dashboard endpoints for funnel and stall stats

---

## Remaining Client Actions

Two items that only you can complete:

1. **Anthropic credits** -- Top up at [console.anthropic.com](https://console.anthropic.com/). The bots use Claude Haiku (fast, cheap) for most messages and Claude Sonnet for complex analysis. Estimated cost: ~$0.10-0.50/day at typical lead volume.

2. **A2P 10DLC registration** -- Required for SMS via Twilio. Register your business at [twilio.com/trust-hub](https://www.twilio.com/en-us/trust-hub). Without this, SMS messages may be filtered as spam. This is a carrier-level requirement, not a bot limitation.

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
├── tests/              # 1330+ tests (unit + integration + E2E)
├── docs/               # Setup guides, specs, troubleshooting, operations runbook
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
