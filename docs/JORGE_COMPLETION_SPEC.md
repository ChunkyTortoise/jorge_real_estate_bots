# Jorge Real Estate Bots — Completion Spec

> **Purpose**: Single source of truth for all remaining work before the system is fully complete.
> **Last updated**: 2026-03-07
> **Current build**: `sha-abc931a` — 1655 tests passing, 21 skipped, 0 failures

---

## Current State

| Area | Status |
|---|---|
| Deployment | Live — `jorge-realty-ai-xxdf.onrender.com` |
| Environment | `production` confirmed |
| Postgres | Healthy — 9 Jorge tables, canonical columns migrated |
| Redis | Healthy |
| Test suite | 1655 passing, 0 failures |
| Seller flow (Q0→Q4) | ✅ Pass |
| Buyer flow (Q0→Q4) | ✅ Pass |
| Ambiguous intake | ✅ Pass |
| Bilingual handoff (API) | ✅ Pass |
| Duplicate / race safety | ✅ Pass |
| HOT qualification + offer | ✅ Pass |
| Scheduling offer (fallback) | ✅ Pass |
| Calendar booking (GHL write) | ❌ 404 — missing `calendars.write` scope |
| Manual takeover live test | ❌ Blocked — needs GHL tag test |
| Resume after takeover | ❌ Blocked — depends on above |
| GHL workflow audit | ❌ Blocked — 8 Tier 1 workflows unconfirmed |
| DB tier | ⚠️ At risk — free tier expires 2026-03-24 |

---

## BLOCKING (must complete before signoff)

### B1 — GHL Workflow UI Audit
**Owner**: Jorge Salas (GHL admin access required)
**Deadline**: Before live SMS traffic is enabled

226 workflows exist in the live GHL location; 68 flagged as potential routing conflicts.
These 8 Tier 1 workflows need explicit GHL UI confirmation:

| Priority | Workflow | Key Question | Required Outcome |
|---|---|---|---|
| P1 | `5. Process Message - Which Bot?` | HTTP relay to app or routes independently? | Must relay to `POST /api/ghl/webhook` only |
| P1 | `2. AI OFF/ON Tag Added -> AI Assistant is:` | Does it write `Bot Type` custom field? | Must NOT write `Bot Type` |
| P1 | `Jorge AI Bot - Inbound Message Handler` | Sends GHL-native AI replies or relays to app? | Must relay; if sends direct AI, disable it |
| P1 | `6. Catch Unknown Inbound SMS` | Fires on app-managed contacts? | Must exclude contacts with Jorge-Active tag |
| P1 | `New Inbound Lead` | Sends messages before app processes webhook? | App relay first, or sends only after app called |
| P2 | `Jorge — Bot Activation` | What tags/fields written on activation? | Must not write `Bot Type` or `agent bot`/`buyer bot` tags |
| P2 | `AI Bot - Jorge Qualification` | Independently qualifies leads or relays? | Must relay to app |
| P2 | `Qualified Lead Notify - SMS` | SMSes the contact or only operator? | If SMSes contact, conflicts with app; restrict to operator |

**Acceptance criteria**: Every row in `docs/JORGE_GHL_WORKFLOW_INVENTORY.md` has
`GHL UI Confirmed? = Yes` with trigger + action details filled in and explicit keep/rewrite/disable.

---

### B2 — DB Tier Upgrade
**Owner**: Cayman Roden
**Deadline**: Before 2026-03-24 (free tier deletes all data)

The `jorge-realty-db` Render Postgres instance is on the free tier. The app is now writing
conversation records, leads, and canonical state here.

**Steps**:
1. Render dashboard → `jorge-realty-db` → Upgrade plan (Starter $7/mo or Standard $20/mo)
2. Confirm `DATABASE_URL` is unchanged after upgrade
3. Verify `/health/aggregate` still shows `postgres = ok`

**Acceptance criteria**: `jorge-realty-db` on paid tier, expiry date removed.

---

### B3 — Manual Takeover + Resume Live Test
**Owner**: Cayman Roden
**Prerequisite**: At least one contact processed by the bot (real or test SMS received)

**Steps**:
1. Send test inbound SMS to Jorge number (or POST to `/api/ghl/webhook` with real `contactId`)
2. Confirm DB record: `GET /admin/conversations/{contact_id}` returns 200
3. **Manual takeover**: Add `Jorge-Active` tag in GHL → send inbound message → confirm app does NOT reply → confirm `status = suppressed`
4. **Resume**: Remove `Jorge-Active` tag → send inbound → confirm app resumes → conversation does not restart

**Acceptance criteria**: Both scenarios pass. Update `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`.

---

### B4 — GHL Calendars.Write Scope
**Owner**: Jorge Salas (GHL admin)
**Impact**: Calendar booking returns 404; scheduling falls back to prose-only

The circuit breaker (`calendar:write_broken` Redis key, 1h TTL) prevents repeated 404s,
but actual appointment creation is disabled until the scope is added.

**Steps**:
1. GHL → Settings → Integrations → Private Integrations
2. Find the API key used for `GHL_API_KEY` on Render
3. Edit → Scopes → Calendars → enable **Write**
4. Save (no API key regeneration needed — scope change takes effect immediately)
5. Redis circuit breaker auto-clears within 1 hour, or flush immediately:
   `redis-cli DEL calendar:write_broken`

**Acceptance criteria**: `POST /api/admin/calendar-debug` returns a booked appointment, not a 404.

---

## NEAR-TERM (complete within 2 weeks of signoff)

### N1 — First Live Contact Processing
**Owner**: Cayman Roden

Send a real or test SMS to the Jorge GHL number. Creates the first DB record and unblocks:
- `GET /admin/conversations/{contact_id}`
- `GET /api/dashboard/leads/{contact_id}`
- Suppression / handoff reason visibility in dashboard

---

### N2 — GitHub Secret: DATABASE_URL
**Owner**: Cayman Roden

1. GitHub → `ChunkyTortoise/jorge_real_estate_bots` → Settings → Secrets → Actions
2. Add: `DATABASE_URL = postgresql://jorge_realty:REDACTED_POSTGRES_PASSWORD@dpg-d6d54hn5r7bs73aq6rkg-a/jorge_realty`
3. (Optional) Restore env-var reset step in `deploy.yml` once all 15 secrets are set

---

### N3 — Warm Nurture Workflow Safety Check
**Owner**: Jorge Salas

Confirm `Jorge — Warm Buyer Nurture` and `Jorge — Warm Seller Nurture` send notifications
to Jorge only (not to contacts), or only fire for contacts not currently managed by the app.

---

### N4 — Compatibility Shim Cleanup
**Owner**: Cayman Roden
**Prerequisite**: Live scenario validation complete + 2 weeks stable traffic

Review `docs/COMPATIBILITY_SHIMS.md`. Once live traffic confirms no legacy callers,
remove the following shims from `routes_webhook.py` and `repository.py`:
- `assigned_bot:{contact_id}` Redis key dual-writes
- `bot_type` request field compatibility path in webhook handler
- Metadata fallback in `extract_canonical_view()`

Each shim has a removal trigger documented in `COMPATIBILITY_SHIMS.md`.

---

### N5 — Startup Environment Validation
**Owner**: Cayman Roden
**File**: `bots/lead_bot/main.py` (lifespan handler)

The app starts successfully even if required env vars are missing, failing only at
the first API call. Add a startup check:

```python
REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY", "GHL_API_KEY", "GHL_LOCATION_ID",
    "REDIS_URL", "DATABASE_URL", "ADMIN_API_KEY",
]
for var in REQUIRED_ENV_VARS:
    if not getattr(settings, var.lower(), None):
        raise RuntimeError(f"Required env var {var} is not set")
```

**Why**: Ops team sees a clear error at deploy time rather than a cryptic failure 10 minutes later.

---

### N6 — Remove Hardcoded Test Credentials
**Owner**: Cayman Roden
**File**: `bots/lead_bot/main.py` lines ~488–495

Test admin email/password pair (`test_admin@jorge.ai` / `test123`) is hardcoded in
the seed data for development. Confirm it is either:
- Gated behind `if settings.environment != "production"`, OR
- Removed entirely from the production build

---

## TECHNICAL DEBT (schedule for Month 1)

### T1 — Funnel Events: Redis Persistence Not Wired
**File**: `bots/lead_bot/routes_webhook.py` (line ~205), `bots/shared/funnel_attribution.py`
**Impact**: Funnel events recorded in-memory only; lost on restart

The `_funnel_tracker.record_event()` call in the webhook handler does not persist to Redis.
The `FunnelTracker` has `_persist_to_redis()` but it is never called.

**Fix**: Pass the cache instance into `FunnelTracker` at init; call async persist after each event.
The dashboard `GET /api/dashboard/funnel` already reads from DB correctly — this only affects
real-time funnel state between restarts.

---

### T2 — GHL API Rate-Limit Handling
**File**: `bots/shared/ghl_client.py` — `_make_request()`
**Impact**: At scale, 429s from GHL are retried immediately (hammering the limit)

Current retry logic does not check for `429` specifically. Add:
- Detect `status_code == 429`
- Respect `Retry-After` header if present; otherwise exponential backoff
- Alert when daily quota (5,000 req/location) reaches 80%

---

### T3 — Structured Logging
**File**: `bots/shared/logger.py`
**Impact**: Hard to parse logs in Render/Datadog; no correlation IDs

Switch from plain `logging` to JSON-structured output:
```python
{"timestamp": "...", "level": "INFO", "contact_id": "...", "event": "...", "bot": "seller"}
```
Correlation ID (`X-Request-ID`) should propagate through all log lines for a single webhook call.

---

### T4 — Alert Push Notifications
**File**: `bots/shared/alerting_service.py`
**Impact**: Alerts exist in-app but operators must manually check dashboard

Add outbound channel for alerts (at minimum one of):
- Webhook POST to a Slack incoming webhook URL (`ALERT_WEBHOOK_URL` env var)
- Email via SendGrid/Mailgun (`ALERT_EMAIL` env var)

Default rules already defined (high error rate, slow p95, low cache hit rate) — just need delivery.

---

### T5 — Stall Re-engagement Analytics
**File**: `bots/shared/stall_reengagement.py`
**Impact**: No visibility into which stall messages convert vs. are ignored

- Persist attempt outcomes to DB (`stall_reengagement_events` table or `extracted_data`)
- Expose conversion rate in `GET /api/dashboard/stall-stats`
- Allow opt-out: if contact replies "stop" / "unsubscribe", mark `stall_opted_out = True`
  and skip future re-engagement attempts

---

### T6 — Dashboard Pagination (H4 — already coded, verify)
**File**: `bots/lead_bot/routes_dashboard.py` (lines ~80, 241, 309)
**Impact**: Dashboard loads all rows into memory at scale

The H4 fix added LIMIT/OFFSET at the SQLAlchemy level. Verify the frontend (if any) passes
`page` and `page_size` query params correctly and the response includes `total_count`.

---

### T7 — Bilingual Escalation SLA
**File**: `bots/lead_bot/routes_webhook.py` (lines 479–527)
**Impact**: Spanish-speaking contacts get a canned response and are never followed up

Current bilingual flow: detects Spanish → sends hardcoded message → tags `needs-bilingual` → stops.
There is no SLA for a bilingual agent to respond, no alert if SLA is missed, and no escalation path.

**Minimum viable fix**:
- Add `bilingual_queued_at` timestamp to conversation record
- Alert if > 1 hour elapses with no human response for bilingual contacts
- OR: implement Claude Spanish prompting (preferable long-term)

---

### T8 — Localhost URLs in Config
**File**: `bots/shared/config.py` (lines ~74, 86–87)
**Impact**: CORS and URL references use hardcoded localhost values

```python
cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]
base_url: str = "http://localhost:8000"
```

Replace with env-var-driven defaults:
```python
cors_origins: list[str] = Field(default_factory=lambda: [settings.base_url])
base_url: str = Field(default="https://jorge-realty-ai-xxdf.onrender.com")
```

---

## OWNER ASSIGNMENTS

| Item | Owner | When |
|---|---|---|
| B1 GHL workflow audit | Jorge Salas | Before live traffic |
| B2 DB tier upgrade | Cayman Roden | Before 2026-03-24 |
| B3 Manual takeover test | Cayman Roden | This week |
| B4 Calendars.write scope | Jorge Salas | This week |
| N1–N3 | Cayman + Jorge | Week of 2026-03-10 |
| N4 Shim cleanup | Cayman Roden | After 2 weeks stable traffic |
| N5–N6 | Cayman Roden | Week of 2026-03-10 |
| T1–T8 | Cayman Roden | Month 1 |

---

## ACCEPTANCE GATE — Handoff Ready

Mark `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md` as `ready` when ALL blocking items are ✅:

- [x] Environment = production
- [x] Postgres healthy, 9 tables, canonical state migrated
- [x] Redis healthy
- [x] All dashboard endpoints returning 200
- [x] Seller, buyer, ambiguous, bilingual scenarios pass (API-level)
- [x] Duplicate / race safety passes
- [x] 1655 tests passing
- [ ] **B1**: GHL Tier 1 workflow audit — all 8 workflows confirmed in GHL UI
- [ ] **B2**: `jorge-realty-db` upgraded to paid tier
- [ ] **B3**: Manual takeover + resume live test passes
- [ ] **B4**: Calendar booking works end-to-end (GHL returns 201, not 404)

---

## LIVE VALIDATION CHECKLIST

After B1–B4 complete, run `docs/JORGE_LIVE_VALIDATION_CHECKLIST.md`.
Scenarios 5 (manual takeover), 6 (resume), and 10 (human handoff) are the only
unchecked ones. All others have been API-validated.

---

## ROLLBACK REFERENCE

| Item | Value |
|---|---|
| Last stable SHA | `abc931a` |
| Rollback via | Render dashboard → jorge-realty-ai → Deploys → redeploy previous |
| Internal postgres URL | `postgresql://jorge_realty:REDACTED_POSTGRES_PASSWORD@dpg-d6d54hn5r7bs73aq6rkg-a/jorge_realty` |
| Admin key | `REDACTED_ADMIN_KEY` (header `X-Admin-Key`) |
| Redis | `red-d6d54jfpm1nc739jgnm0:6379` |
| Calendar circuit breaker key | `calendar:write_broken` (Redis, 1h TTL) |
