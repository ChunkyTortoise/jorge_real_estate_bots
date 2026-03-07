# Jorge Real Estate Bots — Completion Spec

> **Purpose**: Single source of truth for all remaining work before the system is fully complete.
> **Last updated**: 2026-03-07
> **Current build**: `b0ef6d9` — 1717 tests passing, 21 skipped, 0 failures
> **T1–T8 tests added**: 2026-03-07 — all 60 new tests passing
> **N1, N2 completed**: 2026-03-07 — first live contact processed, DATABASE_URL secret set
> **B3 suppression bug fixed**: 2026-03-07 — GHL tag extraction unwrapping deployed

---

## Current State

| Area | Status |
|---|---|
| Deployment | Live — `jorge-realty-ai-xxdf.onrender.com` |
| Environment | `production` confirmed |
| Postgres | Healthy — 9 Jorge tables, canonical columns migrated |
| Redis | Healthy |
| Test suite | 1716 passing, 21 skipped, 0 failures (T1-T8 added 2026-03-07) |
| Seller flow (Q0→Q4) | ✅ Pass |
| Buyer flow (Q0→Q4) | ✅ Pass |
| Ambiguous intake | ✅ Pass |
| Bilingual handoff (API) | ✅ Pass |
| Duplicate / race safety | ✅ Pass |
| HOT qualification + offer | ✅ Pass |
| Scheduling offer (fallback) | ✅ Pass |
| Calendar booking (GHL write) | ❌ 404 — missing `calendars.write` scope |
| Manual takeover live test | ✅ Fixed — suppression bug resolved (tag unwrap); pending live redeploy verify |
| Resume after takeover | ✅ Confirmed live (2026-03-07) |
| First live contact processed | ✅ N1 done — contactId `prX3fC1c7UaCjUzwdeyu` processed |
| DATABASE_URL GitHub secret | ✅ N2 done — secret set via gh CLI |
| GHL workflow audit | ⚠️ Partial — 9 Jorge workflows confirmed via API; GHL UI blocked (Firebase error) |
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

### N1 — First Live Contact Processing ✅ DONE (2026-03-07)
**Owner**: Cayman Roden

POST to `/api/ghl/webhook` with contactId `prX3fC1c7UaCjUzwdeyu` returned:
`{"status":"processed","bot_type":"lead","mode":"lead_intake","score":30}`

---

### N2 — GitHub Secret: DATABASE_URL ✅ DONE (2026-03-07)
**Owner**: Cayman Roden

Set via: `gh secret set DATABASE_URL --repo ChunkyTortoise/jorge_real_estate_bots`
Verified: `gh secret list | grep DATABASE_URL` confirmed present.

---

### N3 — Warm Nurture Workflow Safety Check ⚠️ PARTIAL (2026-03-07)
**Owner**: Jorge Salas

Both workflows confirmed **PUBLISHED** via GHL API (IDs `fbcef074`, `c8334775`).
Action/trigger details not inspectable via API or GHL UI (Firebase permission error blocked UI).

**Still required**: Jorge Salas must open each workflow in GHL UI and confirm:
- Recipients: notifications to Jorge only (NOT to contacts)
- Exclusion: contacts with `Jorge-Active` tag are excluded from SMS sends

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

### T1 — Funnel Events: Redis Persistence Not Wired ✅ DONE
**File**: `bots/shared/funnel_attribution.py`
**Implemented**: `record_event_async` + `get_journey_async` with Redis sorted-set persistence (30d TTL).
**Tests**: `tests/shared/test_funnel_attribution.py::TestFunnelTrackerRedis` (10 tests)

---

### T2 — GHL API Rate-Limit Handling ✅ DONE (quota alert deferred)
**File**: `bots/shared/ghl_client.py` — `_make_request()`
**Implemented**: 429 detection, `Retry-After` header respected (capped at 60s), exponential backoff via tenacity.
**Deferred**: 80% daily-quota alert — no reliable quota counter available from GHL API.
**Tests**: `tests/shared/test_ghl_client.py::TestRetryAfterHeader` (4 tests)

---

### T3 — Structured Logging ✅ DONE
**File**: `bots/shared/logger.py`
**Implemented**: `JSONFormatter` (timestamp/level/correlation_id/logger/message), `CorrelationFilter`,
`set_correlation_id()` / `get_correlation_id()`, PII redaction (email + phone).
**Tests**: `tests/shared/test_logger.py` (14 tests)

---

### T4 — Alert Push Notifications ✅ DONE
**File**: `bots/shared/alerting_service.py`
**Implemented**: `push_alert_outbound(alert, webhook_url)` — Slack-compatible POST with severity emoji.
Triggered from `check_stalled_conversations()` in `main.py` when `ALERT_WEBHOOK_URL` is set.
**Tests**: `tests/shared/test_alerting_service.py::TestPushAlertOutbound` (5 tests)

---

### T5 — Stall Re-engagement Analytics ✅ DONE (DB persistence deferred)
**File**: `bots/shared/stall_reengagement.py`
**Implemented**: `is_opt_out_message()`, `record_opt_out()`, `is_opted_out()` with Redis key
`stall_optout:{id}` (365d TTL). Opt-out check wired into `trigger_reengagement()`.
**Deferred**: DB persistence (`stall_reengagement_events` table) — not required for correctness.
**Tests**: `tests/shared/test_stall_reengagement.py::TestOptOut` (8 tests)

---

### T6 — Dashboard Pagination (H4 — already coded, verify) ✅ DONE
**File**: `bots/lead_bot/routes_dashboard.py`
**Status**: LIMIT/OFFSET pagination confirmed in place at SQLAlchemy level.
Startup env validation added: `RuntimeError` in production on missing required vars.
**Tests**: `tests/lead_bot/test_startup_validation.py` (3 tests)

---

### T7 — Bilingual Escalation SLA ✅ DONE
**File**: `bots/lead_bot/main.py` — `check_stalled_conversations()`
**Implemented**: Hourly scan for `bilingual_handoff` contacts with `last_activity > 1h ago`.
Fires `push_alert_outbound` to `ALERT_WEBHOOK_URL` when breach detected. Records metric
`bilingual.overdue_count` via `AlertingService`.
**Tests**: `tests/lead_bot/test_bilingual_sla.py` (3 tests)

---

### T8 — Localhost URLs in Config ✅ DONE
**File**: `bots/shared/config.py`
**Implemented**: `cors_origins` and `base_url` are env-var-driven with production defaults.
Default `base_url = "https://jorge-realty-ai-xxdf.onrender.com"`.
**Tests**: Covered by existing config tests.

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
- [x] 1716 tests passing (T1-T8 coverage, 2026-03-07)
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
