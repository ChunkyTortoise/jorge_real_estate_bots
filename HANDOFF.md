# Jorge Real Estate Bots -- Client Handoff

## What's Included

Three AI bots (Lead, Buyer, Seller) running as a single FastAPI app, a Streamlit command center, and a full test suite.

| Component | Purpose |
|-----------|---------|
| **Lead Bot** | 5-minute SLA enforcement, Q0-Q4 qualification, temperature scoring |
| **Seller Bot** | Q1-Q4 seller qualification (condition, price, motivation, cash offer), HOT/WARM/COLD scoring |
| **Buyer Bot** | Financial readiness checks, pre-approval flow, property matching |
| **Command Center** | Streamlit dashboard -- lead flow, bot performance, commission tracking |

All three bots run in the same process (`bots/lead_bot/main.py`) and route via `ConversationMode` (SELLER / BUYER / LEAD_INTAKE) set on the GHL contact.

---

## Live Deployment

**URL:** `https://jorge-realty-ai-xxdf.onrender.com`

- API docs: `https://jorge-realty-ai-xxdf.onrender.com/docs`
- Health: `https://jorge-realty-ai-xxdf.onrender.com/health/aggregate`

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
| `JORGE_USER_ID` | Yes | Jorge's GHL user ID for assignment |
| `JORGE_CALENDAR_ID` | Yes | Jorge's calendar ID for availability lookups |
| `REDIS_URL` | Yes | Redis connection URL (conversation state, rate limiting, funnel data) |
| `ADMIN_API_KEY` | Yes | API key for admin endpoints (`X-Admin-Key` header) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | Secret for dashboard JWT auth tokens |
| `GHL_WEBHOOK_SECRET` | **Must be EMPTY** | Leave unset in Render. If set, all webhooks return 401. |

Copy `.env.example` to `.env` for local development. On Render, set these in the `jorge-env` environment group.

---

## GHL Webhook Setup

Point your GHL workflow webhooks to:

```
# Unified dispatcher -- all inbound messages
POST https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook

# New-lead entry point (trigger on Contact Created workflows)
POST https://jorge-realty-ai-xxdf.onrender.com/ghl/webhook/new-lead

# SMS delivery status callbacks (optional)
POST https://jorge-realty-ai-xxdf.onrender.com/api/ghl/webhook/message-status
```

**Routing logic**: The unified webhook reads the contact's `conversationMode` custom field (set automatically or via admin API) and routes to SELLER, BUYER, or LEAD_INTAKE.

---

## Common Operations

### Reset a conversation

```bash
curl -X DELETE https://jorge-realty-ai-xxdf.onrender.com/admin/reset-state/{bot}/{contact_id} \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

Replace `{bot}` with `lead`, `buyer`, or `seller`.

### Reassign a contact to a different bot

```bash
curl -X POST https://jorge-realty-ai-xxdf.onrender.com/admin/reassign-bot \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{"contact_id": "CONTACT_ID", "mode": "buyer"}'
```

Or update the contact's `conversationMode` custom field in GoHighLevel directly (`seller`, `buyer`, or `lead_intake`).

### Manual takeover (bot goes silent)

Add the **"Jorge-Active"** tag to the contact in GoHighLevel. The bot will stop responding to that contact immediately.

Remove the tag to re-enable bot responses.

### Check live health

```bash
curl https://jorge-realty-ai-xxdf.onrender.com/health/aggregate
# Returns: {"status":"healthy","services":{"lead_bot":"ok","seller_bot":"ok","buyer_bot":"ok","redis":"ok","postgres":"ok"}}
```

---

## Admin Endpoints

All admin endpoints require `X-Admin-Key: YOUR_ADMIN_KEY` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/reset-state/{bot}/{contact_id}` | DELETE | Clear conversation state |
| `/admin/reassign-bot` | POST | Change a contact's bot mode |
| `/admin/bot-settings` | GET/PUT | View or update bot tone/behavior settings |
| `/api/dashboard/funnel` | GET | Funnel conversion stats |
| `/api/dashboard/stall-stats` | GET | Stalled conversation breakdown |
| `/api/events/recent` | GET | Recent webhook events (last 50) |

---

## Troubleshooting Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| Booking returns 404 | GHL API key missing `calendars.write` scope | Re-generate GHL API key with Calendar permissions |
| Webhooks return 401 | `GHL_WEBHOOK_SECRET` is set | Remove `GHL_WEBHOOK_SECRET` from Render env vars (must be empty) |
| Bot not responding | Service down or misconfigured | Check `/health/aggregate`, verify Redis is up, verify `GHL_API_KEY` is valid |
| Admin endpoints return 503 | `ADMIN_API_KEY` not set | Set `ADMIN_API_KEY` in Render environment variables |
| Bot responds in English | Missing Spanish config | Verify bot system prompts include Spanish language instruction |
| Rate limit errors (429) | Too many messages per contact | Default: 10 messages/min per contact. Wait or adjust via `/admin/bot-settings` |

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for the full troubleshooting guide.

---

## Running Locally

**Full stack with Docker Compose** (PostgreSQL + Redis + bot):

```bash
cp .env.example .env   # fill in your keys
docker compose up
```

**Single bot (no Docker)**:

```bash
pip install -r requirements.txt
uvicorn bots.lead_bot.main:app --host 0.0.0.0 --port 8001 --reload
```

API docs available at `http://localhost:8001/docs`.

**Run tests:**

```bash
pytest tests/ -v
```

---

## Deploying to Render

The repo includes a `Dockerfile`, `docker-compose.yml`, and `render.yaml` blueprint.

1. Connect the GitHub repo (`ChunkyTortoise/jorge_real_estate_bots`)
2. Create a **Web Service** pointing to the Dockerfile
3. Set all env vars from the table above in the Render dashboard
4. Add a **Postgres** and **Redis** instance (Render provides both)

Or re-deploy to the existing service: `jorge-realty-ai-xxdf.onrender.com` (srv-d6d5go15pdvs73fcjjq0).

---

## Current Status

- **1732 tests passing** (as of 2026-03-08)
- All three bots working end-to-end with GHL
- **Redis connected** -- Render Redis fully reachable
- **PostgreSQL** -- all DB tables migrated (Alembic runs on boot)
- Rate limiting active (Redis-backed, `X-RateLimit-*` headers)
- Buyer Q4 loop limit (3 attempts before STALLED)
- Funnel attribution with Redis persistence (30-day TTL)
- Manual takeover via Jorge-Active tag

### Known Blockers (require Jorge Salas)

1. **Booking returns 404** -- GHL API key needs `calendars.write` scope. Go to GHL Settings > Integrations > Private Integrations, find the API key, add Calendar permissions.
2. **GHL Automation workflows** -- Need a quick audit to confirm webhook URLs are correct and no duplicate triggers are active.

---

## File Structure

```
jorge-real-estate-bots/
├── bots/
│   ├── lead_bot/           # FastAPI app entry point + all routes
│   │   ├── main.py         # App factory, health endpoints
│   │   ├── routes_webhook.py   # /api/ghl/webhook (unified dispatcher)
│   │   ├── routes_admin.py     # /admin/* endpoints
│   │   ├── routes_dashboard.py # /api/dashboard/* endpoints
│   │   ├── routes_realtime.py  # WebSocket / SSE
│   │   └── routes_productization.py  # Multi-tenant productization
│   ├── seller_bot/         # Seller qualification logic
│   └── buyer_bot/          # Buyer qualification logic
├── bots/shared/            # Config, GHL client, Claude client, Redis, business rules
├── command_center/         # Streamlit dashboard
├── database/               # SQLAlchemy models + Alembic migrations
├── billing/                # Billing module (for future productization)
├── adapters/               # Adapter layer (for future productization)
├── api/                    # Additional API modules (for future productization)
├── tests/                  # 1717+ tests (unit + integration)
├── docs/                   # Setup guides, specs, troubleshooting, operations runbook
├── docker-compose.yml      # Full stack (Postgres, Redis, bot)
├── Dockerfile              # Production image
└── .env.example            # All env var reference with descriptions
```

---

## GitHub Repo

`https://github.com/ChunkyTortoise/jorge_real_estate_bots`
