# Jorge Production Findings — 2026-03-06

This document captures the live findings observed during the production-finalization pass on 2026-03-06.

## Summary

Current decision: `not ready` — core runtime blockers are resolved, but workflow audit, contact-specific operator validation, and live scenario execution are still incomplete.

The deployed service is reachable, reports `environment = production`, aggregate health is green, and authenticated operator-surface auth is confirmed. The remaining blockers are now centered on live contact-backed verification and the GHL workflow/legacy audit.

---

## Evidence Collected

### Repo Validation

- `.venv/bin/pytest -q tests` → `1655 passed, 21 skipped` (2026-03-06, latest run)
- 2 additional tests versus the prior baseline of 1653

### Deployed Health

- `GET /health` → HTTP 200, `status = healthy`, `environment = production`, `version = 1.0.0`
- `GET /health/aggregate` → HTTP 200, `status = healthy`
  - `lead_bot = ok`, `seller_bot = ok`, `buyer_bot = ok`, `redis = ok`, `postgres = ok`

### Environment Identity

- The currently probed deployment now reports `environment = production`.
- Earlier `staging` findings are historical only and superseded by the current `production_readiness_report.md`.

### DATABASE_URL And Postgres

- Earlier `DATABASE_URL` misconfiguration was corrected.
- Current aggregate health confirms `postgres = ok`.
- External schema verification remains blocked until the live `DATABASE_URL` is provided for `check_conversation_schema.py`.

### Auth Surface Probe

- `X-Admin-Key: REDACTED_ADMIN_KEY` is the correct admin authentication header.
- All authenticated operator surfaces confirmed reachable:
  - `GET /admin/settings` → HTTP 200, returns seller/buyer/lead prompt and config
  - `GET /api/dashboard/leads/summary` → HTTP 200, returns hero, funnel, and summary fields
  - `GET /api/dashboard/metrics` → HTTP 200, returns system and bot-level metrics
  - `GET /api/dashboard/handoffs` → HTTP 200, returns `[]`
  - `GET /api/dashboard/sms-metrics` → HTTP 200
  - `GET /api/dashboard/funnel` → HTTP 200
  - `GET /api/dashboard/stall-stats` → HTTP 200
  - `GET /api/dashboard/leads` → HTTP 200, returns `{"leads":[],"total":0,...}`
- Contact-specific operator endpoints are still blocked because there are no known live contact IDs with DB-backed Jorge records.
- Direct read-only GHL contact enumeration using the current `GHL_API_KEY` returned HTTP 403, so sample contact discovery is still blocked without either broader GHL scope or a known contact ID from ops.

### GHL Location And Contract Probe

- `GHL_API_KEY` and `GHL_LOCATION_ID = 3xt4qayAh35BlDLaUv7P` (Lyrio) valid.
- Required tags: pass
- Required custom fields: pass
- Extra live tags: 331
- Extra live fields: 608
- Legacy review report updated: `ghl_legacy_contract_review.md`
- Workflow export captured via live API: `ghl_workflows_export.md` / `ghl_workflows_export.json`
- Working workflow list endpoint confirmed:
  - `GET /workflows/?locationId=...`
- Captured live workflow list totals:
  - workflow count = `226`
  - published workflows = `164`
  - heuristic routing/conflict candidates = `68`
- High-risk legacy items identified include: `ai off`, `ai-off`, `agent bot`, `buyer bot`, `direct to buyer bot`, `direct to seller bot`, `Bot Type`, `Buyer/Seller`, `AI Last Bot`, `AI Bot Trigger`, `Lead Identity`, etc.

### Render Env Var Audit

All env vars retrieved via Render API. Full list confirmed:
```
ANTHROPIC_API_KEY  (set)
GHL_API_KEY        REDACTED_GHL_KEY
GHL_LOCATION_ID    3xt4qayAh35BlDLaUv7P
GHL_CALENDAR_ID    RxIM6Mfeipj2dpmUG79W
JORGE_CALENDAR_ID  RxIM6Mfeipj2dpmUG79W
JORGE_USER_ID      Or4ImSUxUarPJQyawA5W
REDIS_URL          redis://red-d6d54jfpm1nc739jgnm0:6379
DATABASE_URL       (now set to internal postgres URL — was empty)
ENVIRONMENT        production
ADMIN_API_KEY      REDACTED_ADMIN_KEY
JWT_SECRET         (set)
GHL_ALLOW_UNSIGNED_WEBHOOKS  true
JORGE_BUYER_MODE   true
JORGE_SELLER_MODE  true
ADMIN_PASSWORD     (empty)
```

---

## Current Blockers

### Blocker 1. DB schema verification not yet run

- The jorge-realty-db postgres does not allow external connections (ipAllowList = null = Render internal only).
- External schema verification via `check_conversation_schema.py` is blocked by IP restrictions.
- Alternative: verify via `/health/aggregate` showing `postgres = ok` after redeploy, plus spot-check of admin/dashboard endpoints returning DB-backed data.

### Blocker 2. GHL workflow and legacy-contract audit still incomplete

- 331 extra live tags, 608 extra fields — not yet fully classified.
- High-risk items identified in `ghl_legacy_contract_review.md` but not yet individually reviewed.
- Live workflow list is now captured, but trigger/action review and final disposition still require GHL UI confirmation.
- High-priority workflow audit candidates from the export include:
  - `5. Process Message - Which Bot?`
  - `6. Catch Unknown Inbound SMS`
  - `New Inbound Lead`
  - `Jorge AI Bot - Inbound Message Handler`
  - `Jorge — Bot Activation`
  - `AI Bot - Jorge Qualification`
  - `Lead Intake Notification`
  - `Qualified Lead Notify - SMS`
  - `Qualified Lead Notify - Email`

### Blocker 3. Contact-specific operator validation still not executable

- `GET /admin/conversations/{contact_id}`, `GET /api/dashboard/leads/{contact_id}`, and `GET /api/dashboard/conversations/{contact_id}` still require a real contact ID with Jorge DB records.
- Direct GHL contact enumeration is currently blocked by HTTP 403 using the available GHL token, so contact discovery needs either:
  - a provided sample contact ID from ops, or
  - broader GHL token scope, or
  - a real inbound lead processed through production.

### Blocker 4. Live scenario validation not yet executed

- All 9 scenario validations pending live service being healthy.

---

## Progress Since Prior Session

| Item | Prior Status | Current Status |
|---|---|---|
| Environment identity | Staging (wrong) | Fixed — live `/health` now reports `production` |
| Postgres health | Down | Fixed — live `/health/aggregate` now reports `postgres = ok` |
| ADMIN_API_KEY confirmation | Blocked | Confirmed: `REDACTED_ADMIN_KEY` via `X-Admin-Key` |
| Admin/dashboard endpoint auth | Blocked | Pass — settings, leads, summary, metrics, handoffs, funnel, stall stats, SMS metrics all return 200 |
| Repo test baseline | 1653 passed | 1655 passed, 21 skipped |
| GHL contract re-validation | Prior pass | Re-run: still pass |
| Contact discovery for detail views | Unknown | Blocked — GHL contact enumeration returns HTTP 403 with current token |

---

## Next Required Actions

1. Run `check_conversation_schema.py` with the real live `DATABASE_URL`, or obtain an operator-approved internal verification equivalent.
2. Obtain at least one real contact ID with Jorge DB records, or expand GHL token scope enough to enumerate contacts safely.
3. Validate contact-specific operator endpoints with that contact ID.
4. Execute live scenario validation checklist.
5. Complete GHL legacy tag/field manual review.
6. Complete GHL workflow trigger/action audit and final inventory disposition using `ghl_workflows_export.md` as the seed list.
7. Update `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md` with final evidence and approvals.

---

## Current Handoff Status

The repo is prepared for handoff (1655 tests passing).
The live deployment is healthier and now reports production with working Postgres, but it is still not approved for handoff.

The remaining blockers are DB schema verification, contact-backed operator checks, workflow/legacy audit completion, and live scenario validation.
