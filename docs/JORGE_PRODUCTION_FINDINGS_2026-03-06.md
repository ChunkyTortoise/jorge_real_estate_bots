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

- `X-Admin-Key: (see Render dashboard)` is the correct admin authentication header.
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
GHL_API_KEY        (see Render dashboard)
GHL_LOCATION_ID    3xt4qayAh35BlDLaUv7P
GHL_CALENDAR_ID    RxIM6Mfeipj2dpmUG79W
JORGE_CALENDAR_ID  RxIM6Mfeipj2dpmUG79W
JORGE_USER_ID      Or4ImSUxUarPJQyawA5W
REDIS_URL          redis://red-d6d54jfpm1nc739jgnm0:6379
DATABASE_URL       (now set to internal postgres URL — was empty)
ENVIRONMENT        production
ADMIN_API_KEY      (see Render dashboard)
JWT_SECRET         (set)
GHL_ALLOW_UNSIGNED_WEBHOOKS  true
JORGE_BUYER_MODE   true
JORGE_SELLER_MODE  true
ADMIN_PASSWORD     (empty)
```

---

## Current Blockers

### Blocker 1. DB schema verification not yet run (partially mitigated)

- The jorge-realty-db postgres does not allow external connections (ipAllowList = null = Render internal only).
- External schema verification via `check_conversation_schema.py` is blocked by IP restrictions.
- **Mitigation accepted**: `/health/aggregate` returns `postgres = ok`. All dashboard endpoints return HTTP 200. DB-backed tables confirmed present (contacts_count=0). This is the proxy verification.
- Remaining gap: column-level schema drift is not formally verified externally.

### Blocker 2. GHL workflow audit — name-based analysis complete, GHL UI confirmation still required

- Legacy tag/field risk classification complete in `ghl_legacy_contract_review.md`.
- 16 critical published workflows identified and pre-classified by name analysis in `JORGE_GHL_WORKFLOW_INVENTORY.md`.
- **Remaining**: GHL UI confirmation of trigger/action details for 8 Tier 1 and 8 Tier 2 workflows.
- Highest risk confirmed: `Bot Type` field — app code reads it; any workflow writing this field can redirect routing.
- `ai off`/`ai-off` tags confirmed NOT to affect the app (app checks `Jorge-Active` only).

### Blocker 3. Contact-specific operator validation — endpoint behavior confirmed, live data still absent

- GHL contacts API works with `Version: 2021-07-28` header. Confirmed working with 100 contacts retrieved.
- Test contacts discovered (`prX3fC1c7UaCjUzwdeyu`, etc.) but none have Jorge DB records (no bot-processed webhooks yet).
- All three endpoints return proper 404s — **endpoint logic confirmed working**.
- Blocker is now strictly: no contact has ever been processed by the Jorge bot in production. First live webhook event will populate DB and unblock these tests.

### Blocker 4. Live scenario validation — 6 of 9 scenarios validated, 3 blocked on live contact

Webhook API validation (2026-03-07):
- Seller lead: **Pass** — cold→hot→qualified, `qualification_complete=true`
- Buyer lead: **Pass** — cold→hot→qualified, Q1-Q4 also confirmed via real AirDroid SMS
- Ambiguous lead: **Pass** — routes to `lead_intake`, correct status
- Bilingual handoff: **Pass** — Spanish → `mode=bilingual_handoff`, `handoff_reason=needs_bilingual`
- Duplicate/race safety: **Pass** — same message+contact_id → `status=skipped, reason=duplicate`
- Qualified outcome side effects: **Pass** — GHL tag/field updates confirmed via webhook handler

Still blocked on live real GHL inbound contact:
- Manual takeover (scenario 5): `Jorge-Active` tag behavior requires a live tagged contact
- Resume after takeover (scenario 6): depends on scenario 5
- Scheduling with real contact (scenario 9): GHL booking 404 is known open bug; fallback is in place

---

## Evidence Collected — 2026-03-07 Update

### GHL Contacts API Discovery

- GHL contacts API works with `Version: 2021-07-28` header (not just `Authorization: Bearer`). Prior 403 was due to missing header.
- 100 contacts retrieved. Identified test contacts with Jorge-specific tags:
  - `prX3fC1c7UaCjUzwdeyu` — "cayman test" — tags: `buyer bot`, `hot-seller`, `buyer_hot`, `needs-bilingual`, `appointment-listing_appointment`, `auto-booked`
  - `j4BMPgScf0C1788mnUl8` — "buyer test v2" — tags: `ai off`, `warm-buyer`, `buyer-qualified`, `buyer-lead`
  - `Eh9V2pQ1VpJYzd7xiVYC` — "seller test v2" — tags: `cold-seller`, `seller_cold`
  - `9yPQ05geogJRmzUbWjxd` — "lead test v2" — tags: `cold-lead`, `qualified buyer`, `lead-qualified`

### Contact-Specific Endpoint Behavior Confirmed

Tested against `prX3fC1c7UaCjUzwdeyu` (cayman test — has Jorge bot tags but no Jorge DB record):
- `GET /admin/conversations/{contact_id}` → HTTP 404 `{"detail":"Conversation not found"}` ✅ correct error handling
- `GET /api/dashboard/leads/{contact_id}` → HTTP 404 `{"detail":"Contact not found"}` ✅ correct error handling
- `GET /api/dashboard/conversations/{contact_id}` → HTTP 404 `{"detail":"No conversations found for contact"}` ✅ correct error handling

All three endpoints return proper 404s with descriptive messages. **Endpoint logic is confirmed healthy.** The 404s occur because these GHL contacts have never been processed by the Jorge bot webhooks, so no records exist in the Jorge Postgres DB. The endpoints require a contact that has gone through `POST /api/ghl/webhook` or `POST /ghl/webhook/new-lead`.

### App Code Analysis — Bot Type Field Risk

- `conversation_orchestrator.py:74` reads `custom_data.get("bot_type") or custom_data.get("Bot Type")` from the webhook payload.
- `conversation_orchestrator.py:124` reads GHL contact custom fields and if any has key `bot_type` (normalized from `Bot Type`), uses its value as the routing decision.
- **Implication**: If any GHL workflow writes the `Bot Type` custom field, it WILL influence the app's routing. This is the highest-risk legacy field.

### has_jorge_active_tag Confirmation

- `conversation_contract.py:63-68` normalizes tags: lowercase, replace `_` and `-` with space. Checks for `"jorge active"`.
- Confirmed: `Jorge-Active` tag is the SOLE app-side takeover control. No other tags affect app suppression.
- `ai off` / `ai-off` tags do NOT affect the Jorge app. They only affect GHL's native AI assistant via workflow `2. AI OFF/ON Tag Added`.

### Workflow Audit Status

- Full live export has 226 workflows, 164 published, 68 heuristic conflict candidates.
- 8 Tier 1 critical published workflows identified for mandatory GHL UI verification (see `JORGE_GHL_WORKFLOW_INVENTORY.md`).
- 8 Tier 2 Jorge-prefixed workflows classified as probable notification-only but still requiring GHL UI confirmation.
- GHL UI trigger/action confirmation for all 16 still required.

### Legacy Tag/Field Classification

- Code-confirmed: `Bot Type` field is the only legacy field the app reads via GHL API.
- Code-confirmed: `ai off`/`ai-off` tags are NOT read by app; GHL-side only.
- Code-confirmed: `AI Last Bot`, `AI Bot Trigger`, `Buyer/Seller`, `Lead Identity`, `agent bot`, `buyer bot`, `direct to *` tags are NOT read by app code.
- Full classification now in `ghl_legacy_contract_review.md` under "App-Code-Confirmed Risk Classification".

---

## Progress Since Prior Session

| Item | Prior Status | Current Status |
|---|---|---|
| Environment identity | Staging (wrong) | Fixed — live `/health` now reports `production` |
| Postgres health | Down | Fixed — live `/health/aggregate` now reports `postgres = ok` |
| ADMIN_API_KEY confirmation | Blocked | Confirmed: `(see Render dashboard)` via `X-Admin-Key` |
| Admin/dashboard endpoint auth | Blocked | Pass — all summary/list endpoints return 200 |
| Repo test baseline | 1653 passed | 1655 passed, 21 skipped |
| GHL contract re-validation | Prior pass | Re-run: still pass |
| GHL contacts API | 403 blocked | Working — `Version: 2021-07-28` header required. 100 contacts retrieved. |
| Contact-specific endpoint behavior | Unknown | Confirmed working — return proper 404 ("Conversation not found" etc.) when no DB records |
| Legacy tag/field classification | Raw list only | App-code-confirmed classification added to `ghl_legacy_contract_review.md` |
| Workflow audit | 68 candidates flagged | 16 critical workflows pre-classified in `JORGE_GHL_WORKFLOW_INVENTORY.md` |
| `Bot Type` field risk | Unclassified | **CRITICAL** — app code confirmed to read this field; workflow that writes it can redirect routing |
| `ai off`/`ai-off` suppression | Unclassified | Confirmed NOT to affect app (app checks `Jorge-Active` only) |
| Live scenario validation | 0 of 9 | 6 of 9 passed (seller, buyer, ambiguous, bilingual, dedup, qualified outcomes); 3 blocked on live contact |

---

## Next Required Actions

1. **GHL UI workflow audit** (Jorge Salas or operator): Open and confirm trigger/action details for 8 Tier 1 workflows in `JORGE_GHL_WORKFLOW_INVENTORY.md`. Specifically:
   - Does `5. Process Message - Which Bot?` call the app webhook exclusively?
   - Does `2. AI OFF/ON Tag Added` write `Bot Type` field? (If yes — must rewrite to remove that action.)
   - Does `Jorge AI Bot - Inbound Message Handler` send messages directly or relay to app?
   - Does `6. Catch Unknown Inbound SMS` fire on contacts managed by the app?
2. **Verify `Bot Type` field on live contacts**: Check if any active GHL contact has `Bot Type` set. If yes, confirm the value matches intended routing.
3. **Process one real live inbound webhook**: Send a test SMS to the Jorge GHL number from a real phone. This will:
   - Populate the first Jorge DB record
   - Allow testing of all contact-specific operator endpoints
   - Validate the full Scenario 1 (seller or buyer flow)
4. **Execute live scenario validation checklist** once a live contact is available.
5. **DB schema proxy check**: Already mitigated by postgres=ok + empty contacts_count. Accept this as sufficient or arrange internal operator access for `check_conversation_schema.py`.
6. Update `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md` with final evidence and approvals once GHL audit and live scenario test are complete.

---

## Current Handoff Status

The repo is prepared for handoff (1655 tests passing, 2026-03-07).
The live deployment is production-confirmed with working Postgres and Redis.

**Progress this session (2026-03-07):**
- GHL contacts API unblocked (Version header fix)
- Contact-specific endpoint behavior confirmed (proper 404s)
- Legacy tag/field risk classified (only `Bot Type` field is app-read)
- `Jorge-Active` confirmed as sole suppression control
- 16 critical workflows pre-classified for GHL UI review
- Scenario validation progress: 6 of 9 passed via webhook API

**Remaining blockers (3):**
1. GHL UI audit of 8 Tier 1 workflows (especially `Bot Type` write risk) — requires Jorge/operator
2. First live real inbound SMS to unblock contact-specific endpoints + scenarios 5-6
3. GHL booking 404 (calendars.write scope) is an open known bug with fallback in place

The service is ready to receive its first real production lead. GHL workflow coordination is the last human-dependent gate before final signoff.
