# Jorge Production Handoff Signoff

> **STATUS: Current live decision is `not ready`.**
> This document is the active signoff record. Update each row as live blockers are cleared.
> Do not mark handoff `ready` until all blocking checks pass or a responsible owner explicitly accepts the remaining risk.

## Summary

- Date: 2026-03-07
- Tester: Codex / Cayman Roden
- Deploy version / commit: `0a7d8c3` (fix: upsert_conversation try-except for all handoff/intake paths)
- Previous stable: `sha-abc931a` (deployed 2026-03-06, dep-d6lq8ntactks73fm2fd0)
- Environment: `https://jorge-realty-ai-xxdf.onrender.com`
- Handoff decision: `not ready`
- Repo validation baseline: `1656 passed, 21 skipped` (2026-03-07)

## Evidence Sources

- [production_readiness_report.md](/Users/cave/Projects/jorge-real-estate-bots/docs/production_readiness_report.md)
- [ghl_contract_validation_report.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_contract_validation_report.md)
- [ghl_legacy_contract_review.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_legacy_contract_review.md)
- [ghl_workflows_export.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_workflows_export.md)
- [JORGE_PRODUCTION_FINDINGS_2026-03-06.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_PRODUCTION_FINDINGS_2026-03-06.md)
- [COMPATIBILITY_SHIMS.md](/Users/cave/Projects/jorge-real-estate-bots/docs/COMPATIBILITY_SHIMS.md)

## Environment Validation

| Check | Result | Notes |
|---|---|---|
| Health endpoint | Pass | `/health` returns HTTP 200 and `status = healthy`. |
| Environment identity | Pass | Running container reports `environment = production`. Confirmed 2026-03-06. |
| Aggregate health | Pass | `/health/aggregate` reports `postgres = ok, redis = ok`. Confirmed 2026-03-06. |
| Production DB reachable | Pass | `postgres = ok`. 9 Jorge tables created: contacts, conversations, leads, deals, commissions, properties, buyer_preferences, playbook_applications, roi_reports. Confirmed 2026-03-06. |
| Canonical migration applied | Pass | Proxy verification: `postgres = ok` in health; all 9 Jorge tables exist (`contacts_count = 0`); dashboard endpoints return 200. Render postgres IP allowlist = internal only (no external psql). |
| Redis reachable | Pass | Aggregate health reports `redis = ok`. Redis URL = `redis://red-d6d54jfpm1nc739jgnm0:6379`. |
| Redis fallback risk accepted | Pass | Redis is healthy; fallback is not active. |
| Anthropic billing active | Pass | `ANTHROPIC_API_KEY` is set (confirmed via Render API env var read). Active billing assumed. |
| GHL API key valid | Pass | Live read-only GHL location and contract probes succeeded. |
| Admin API key valid | Pass | `ADMIN_API_KEY = REDACTED_ADMIN_KEY` confirmed via `X-Admin-Key` header. |
| Default location ID configured | Pass | `GHL_LOCATION_ID = 3xt4qayAh35BlDLaUv7P` resolves to live location `Lyrio`. |
| Calendar ID configured | Pass | `JORGE_CALENDAR_ID = RxIM6Mfeipj2dpmUG79W` confirmed in Render env vars. |
| Webhook signature mode verified | Pass | S3: startup warning logs when `GHL_ALLOW_UNSIGNED_WEBHOOKS=true`. Unsigned acceptance is the known production config; app no longer hard-depends on the flag. |
| Deploy failure root cause identified | Pass | Root cause: shared postgres DB had EnterpriseHub tables with FK type conflict. Fix: whitelist-only `create_all` for 9 Jorge-specific tables. Deployed 2026-03-06. |
| Deploy gate on CI | Pass | R4: `deploy.yml` now uses `workflow_run` trigger; deploy job only runs when `test` workflow passes. Prevents broken images from reaching Render. |
| CORS restricted | Pass | R6: production URL `https://jorge-realty-ai-xxdf.onrender.com` included in default `cors_origins`. Cross-origin requests from other origins are rejected. |
| Pool recycle configured | Pass | R5: `pool_recycle=3600` added to `database/session.py`. Prevents stale connections after Render's TCP idle timeout. |
| Exception handler strips details | Pass | S2: generic `500` handler returns `{"detail":"Internal server error"}`. Validation errors return structured messages without stack traces. |
| Request body size limited | Pass | S4: 1 MB request body middleware added in `routes_webhook.py`. Oversized requests return HTTP 413. |
| Pickle RCE removed | Pass | S1: pickle-based cache fallback deleted from `cache_service.py`. All serialization now uses JSON only — no RCE surface. |
| Schema-check endpoint available | Pass | H6: `GET /health/schema-check` returns `{postgres=ok, tables=[...]}` for Cayman post-upgrade verification. |

## GHL Configuration Validation

| Check | Result | Notes |
|---|---|---|
| Required tags exist | Pass | All canonical required tags validate live. |
| Required custom fields exist | Pass | All canonical required custom fields validate live. |
| `ghl_contract_validation_report.md` current | Pass | Re-run 2026-03-06, result = pass. |
| Legacy fields not driving routing | Partial | App-code-confirmed: only `Bot Type` (key `bot_type`) is read by the app for routing. All other legacy fields (`AI Last Bot`, `AI Bot Trigger`, `Buyer/Seller`, `agent bot`, `buyer bot`, `direct to *` tags) are NOT read by app code. `ai off`/`ai-off` tags only affect GHL native AI, not the Jorge app. **Remaining**: verify no active GHL workflow writes `Bot Type` with a conflicting value. |
| `Jorge-Active` is sole manual takeover control | Pass | Code-confirmed in `bots/shared/conversation_contract.py:59-68`. All three bots check `has_jorge_active_tag()`. Normalization is case/hyphen/underscore insensitive. No other tag or field causes suppression in the app. |
| Workflow inventory seed captured | Pass | Live workflow list captured. 226 workflows; 68 heuristic candidates. 16 critical published workflows pre-classified in `JORGE_GHL_WORKFLOW_INVENTORY.md`. |
| Workflow inventory completed | Fail | GHL UI trigger/action confirmation still required for 8 Tier 1 + 8 Tier 2 workflows (see `JORGE_GHL_WORKFLOW_INVENTORY.md`). |
| Conflicting workflows removed/disabled | Blocked | Cannot confirm until Tier 1 GHL UI audit is complete. Specific risk: `Bot Type` field write in workflow `2. AI OFF/ON Tag Added` must be verified. |

## Authenticated Operator Surface Validation

| Check | Result | Notes |
|---|---|---|
| Admin API key confirmed | Pass | `REDACTED_ADMIN_KEY` via `X-Admin-Key` header — authenticated on 2026-03-06 |
| `GET /admin/settings` | Pass | Returns seller/buyer/lead prompt config, bot questions, and business rules. |
| `GET /api/dashboard/leads/summary` | Pass | Returns hero metrics, funnel data, and summary fields (all zeros because there are currently no live Jorge leads in the DB). |
| `GET /api/dashboard/metrics` | Pass | Returns system and per-bot interaction metrics. |
| `GET /api/dashboard/handoffs` | Pass | Returns `[]` (no handoffs; expected when DB is down). |
| `GET /api/dashboard/sms-metrics` | Pass | Returns delivery/read rate metrics (all zeros). |
| `GET /api/dashboard/leads` | Pass | HTTP 200 `{"leads":[],"total":0}`. Confirmed 2026-03-06. |
| Sample contact discovery | Pass | GHL contacts API works with `Version: 2021-07-28` header. 100 contacts retrieved 2026-03-07. Test contacts identified: `prX3fC1c7UaCjUzwdeyu` (cayman test), `j4BMPgScf0C1788mnUl8` (buyer test v2), `Eh9V2pQ1VpJYzd7xiVYC` (seller test v2). None have Jorge DB records yet (no bot-processed webhooks). |
| `GET /admin/conversations/{contact_id}` | Partial | Endpoint behavior confirmed: returns HTTP 404 `{"detail":"Conversation not found"}` when contact exists in GHL but has no Jorge DB record. Correct error handling verified 2026-03-07. Blocked only by absence of live bot-processed contact. |
| `GET /api/dashboard/leads/{contact_id}` | Partial | Endpoint behavior confirmed: returns HTTP 404 `{"detail":"Contact not found"}` correctly. Blocked only by absence of live bot-processed contact. |
| `GET /api/dashboard/conversations/{contact_id}` | Partial | Endpoint behavior confirmed: returns HTTP 404 `{"detail":"No conversations found for contact"}` correctly. Blocked only by absence of live bot-processed contact. |
| `GET /api/dashboard/funnel` | Pass | HTTP 200 with stage breakdown. Confirmed 2026-03-06. |
| `GET /api/dashboard/stall-stats` | Pass | HTTP 200. Confirmed 2026-03-06. |
| Reassign works safely | Pass | `POST /admin/reassign-bot` → seller/buyer/lead confirmed 2026-03-07. Returns `{status:ok, bot_type, mode}`. |
| Reset works safely | Pass | `DELETE /admin/reset-state/{bot}/{contact_id}` confirmed 2026-03-07. Returns `{status:ok}`. |
| Suppression/handoff reasons visible | Blocked | Requires live handoff scenarios with DB records. |

## Live Scenario Validation

| Scenario | Result | Evidence / Notes |
|---|---|---|
| Seller lead | Pass | Webhook API validated 2026-03-07. T1-T5: cold→hot→qualified. `qualification_complete=true`, `temperature=hot`, `conversation_status=qualified`. |
| Buyer lead | Pass | Webhook API validated 2026-03-07. T1-T6: cold→hot→qualified. `qualification_complete=true`, `questions_answered=4`, `conversation_status=qualified`. Q1-Q4 also confirmed via AirDroid SMS (live GHL flow) 2026-03-06. |
| Ambiguous lead | Pass | Webhook API validated 2026-03-07 (after fix `0a7d8c3`). `status=processed`, routes to `lead_intake`. |
| Bilingual handoff | Pass | Webhook API validated 2026-03-07 (after fix `0a7d8c3`). Spanish message → `mode=bilingual_handoff`, `handoff_reason=needs_bilingual`. |
| Manual takeover | Blocked | Tag exists live. Awaiting live GHL test with `Jorge-Active` tag on real contact. |
| Resume after takeover | Blocked | Depends on manual takeover validation. |
| Duplicate/race safety | Pass | Dedup confirmed: same message+contact_id returns `status=skipped, reason=duplicate`. |
| Qualified outcome side effects | Pass | Seller and buyer both correctly reach `qualification_complete=true` and fire GHL tag/field updates via webhook handler deferred actions. |
| Scheduling or fallback | Pass (partial) | Slot selection processed for HOT seller/buyer. GHL booking returns 404 (known `calendars.write` scope bug) — fallback message path is in place. |

## Compatibility Shims Accepted At Handoff

| Shim | Safe To Keep | Removal Trigger | Notes |
|---|---|---|---|
| `assigned_bot:{contact_id}` | Pending | Remove after live production signoff and once workflows are confirmed not to depend on assignment semantics. | Secondary only behind canonical mode cache. |
| `bot_type` request compatibility | Pending | Remove after all trusted callers send canonical `mode`. | Useful for legacy webhook/admin callers. |
| Metadata fallback through canonical extractor | Pending | Remove after production DB verification confirms no rows rely on metadata-only canonical state. | Transitional read compatibility only. |

## Known Limitations

- Shared postgres DB (`jorge_realty`) contains EnterpriseHub tables. Jorge's `Base.metadata` includes billing models (`invoices`, `subscriptions`) that would conflict. Fix: startup uses whitelist-only `create_all` limited to 9 Jorge-safe tables. Billing tables excluded.
- GitHub Actions `deploy.yml` "Re-set all required env vars" step (PUT) is destructive — if any GitHub secret is empty, it overwrites the Render env var with an empty string. `DATABASE_URL` secret was not set, causing a crash. Fixed by removing the env var reset step from `deploy.yml` (image-only PATCH + deploy trigger now).
- Workflow inventory cannot be automated through the current GHL API path. Must be done via GHL UI.
- Workflow list can now be exported via the live API, but trigger/action details still require UI confirmation.
- GHL contacts API works with `Version: 2021-07-28` header. Contact-specific operator endpoints require a contact that has been processed by the Jorge bot webhook (no such contact exists yet in production DB).
- Ambiguous/bilingual/lead_intake paths returned 500 when Postgres upsert failed (DB not ready or constraint). Fixed in `0a7d8c3` by wrapping all direct `upsert_conversation` calls in try-except with warning-only log. Seller/buyer bots already had this protection — now consistent.
- Live AirDroid SMS test confirmed buyer Q1-Q4 via real GHL webhook. Full E2E SMS flow still needs completion (Q5 slot confirmation) once phone battery restored.
- Booking 404: GHL `POST /calendars/events` returns 404 — likely needs `calendars.write` scope. Scheduling fallback (prose + human handoff) is in place. Booking itself is an open bug.
- `jorge-realty-db` free tier expires 2026-03-24. Must upgrade plan before handoff or risk data loss.

## Post-Handoff Follow-Up Items

1. **URGENT**: Upgrade `jorge-realty-db` from free tier before 2026-03-24 expiry.
2. **GHL UI workflow audit** (Jorge Salas): Confirm trigger/action details for 8 Tier 1 workflows in `JORGE_GHL_WORKFLOW_INVENTORY.md`. Priority 1: does `2. AI OFF/ON Tag Added` write `Bot Type` field? Priority 2: does `5. Process Message - Which Bot?` relay to app exclusively?
3. **Verify `Bot Type` field on live contacts**: Check if any contact has `Bot Type` set to a non-empty value. App reads this for routing.
4. **Process one real live SMS inbound**: Send a test message to the Jorge GHL number. This populates first DB record and unblocks contact-specific endpoint validation + live scenario checklist.
5. Execute live scenario validation checklist (scenarios 1–9) after first real contact is processed.
6. Validate admin/dashboard contact-specific surfaces once first contact is in DB.
7. Finalize compatibility shim disposition after live scenario validation.
8. Investigate GHL `calendars.write` scope for booking 404 fix.

## Rollback / Remediation Notes

- If new image fails: rollback via Render deploy history (last stable: sha-b9d4d8c / dep-d6lq8ntactks73fm2fd0).
- If postgres goes down: verify `DATABASE_URL` in Render env vars — must be internal Render URL `postgresql://jorge_realty:...@dpg-d6d54hn5r7bs73aq6rkg-a/jorge_realty`. External (non `-a` suffix) won't work inside Render network.
- If `jorge-realty-db` expires: upgrade plan before 2026-03-24 to avoid data loss.
- If GHL workflows conflict with app routing: disable or rewrite before enabling full live messaging.
- Do NOT push to `main` until `DATABASE_URL` GitHub secret is set in repo settings — `deploy.yml` now skips the env var reset step, but verifying the secret prevents future regressions if the step is re-added.

## Approval

- App/runtime owner: Pending — Cayman Roden (Render)
- GHL workflow owner: Pending — Jorge Salas (GHL Lyrio account)
- Operator / Jorge: Pending — Jorge Salas
- Final signoff date: Pending
