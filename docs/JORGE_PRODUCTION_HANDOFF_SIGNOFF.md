# Jorge Production Handoff Signoff

> **STATUS: Current live decision is `not ready`.**
> This document is the active signoff record. Update each row as live blockers are cleared.
> Do not mark handoff `ready` until all blocking checks pass or a responsible owner explicitly accepts the remaining risk.

## Summary

- Date: 2026-03-06
- Tester: Codex / Cayman Roden
- Deploy version / commit: `b9d4d8cda671b4ab8d2f4f21d4e37d6bc19dbcb7` (fix7 whitelist DB creation)
- Current live container: `sha-b9d4d8cda671b4ab8d2f4f21d4e37d6bc19dbcb7` (deployed 2026-03-06, dep-d6lq8ntactks73fm2fd0)
- Environment: `https://jorge-realty-ai-xxdf.onrender.com`
- Handoff decision: `not ready`
- Repo validation baseline: `1655 passed, 21 skipped` (2026-03-06)

## Evidence Sources

- [production_readiness_report.md](/Users/cave/Projects/jorge-real-estate-bots/docs/production_readiness_report.md)
- [ghl_contract_validation_report.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_contract_validation_report.md)
- [ghl_legacy_contract_review.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_legacy_contract_review.md)
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
| Webhook signature mode verified | Note | `GHL_ALLOW_UNSIGNED_WEBHOOKS = true` is set. Unsigned webhooks are accepted. This is the known and accepted production config for the current GHL integration. |
| Deploy failure root cause identified | Pass | Root cause: shared postgres DB had EnterpriseHub tables with FK type conflict. Fix: whitelist-only `create_all` for 9 Jorge-specific tables. Deployed 2026-03-06. |

## GHL Configuration Validation

| Check | Result | Notes |
|---|---|---|
| Required tags exist | Pass | All canonical required tags validate live. |
| Required custom fields exist | Pass | All canonical required custom fields validate live. |
| `ghl_contract_validation_report.md` current | Pass | Re-run 2026-03-06, result = pass. |
| Legacy fields not driving routing | Fail | 331 extra tags, 608 extra fields. High-risk legacy items include `ai off`, `ai-off`, `agent bot`, `buyer bot`, `direct to buyer bot`, `direct to seller bot`, `Bot Type`, `Buyer/Seller`, `AI Last Bot`, `AI Bot Trigger`. Manual audit not yet complete. |
| `Jorge-Active` is sole manual takeover control | Blocked | Tag exists in normalized form. Sole-control status not proven until workflow/legacy audit done. |
| Workflow inventory completed | Fail | GHL workflow API returns 404 for workflow enumeration. Manual inventory via GHL UI still pending. |
| Conflicting workflows removed/disabled | Blocked | Depends on workflow inventory completion. |

## Authenticated Operator Surface Validation

| Check | Result | Notes |
|---|---|---|
| Admin API key confirmed | Pass | `REDACTED_ADMIN_KEY` via `X-Admin-Key` header — authenticated on 2026-03-06 |
| `GET /admin/settings` | Pass | Returns seller/buyer/lead prompt config, bot questions, and business rules. |
| `GET /api/dashboard/leads/summary` | Pass | Returns hero metrics, funnel data, and summary fields (all zeros due to postgres down). |
| `GET /api/dashboard/metrics` | Pass | Returns system and per-bot interaction metrics. |
| `GET /api/dashboard/handoffs` | Pass | Returns `[]` (no handoffs; expected when DB is down). |
| `GET /api/dashboard/sms-metrics` | Pass | Returns delivery/read rate metrics (all zeros). |
| `GET /api/dashboard/leads` | Pass | HTTP 200 `{"leads":[],"total":0}`. Confirmed 2026-03-06. |
| `GET /admin/conversations/{contact_id}` | Blocked | Requires a live contact ID with DB records. |
| `GET /api/dashboard/leads/{contact_id}` | Blocked | Requires a live contact ID. |
| `GET /api/dashboard/conversations/{contact_id}` | Blocked | Requires a live contact ID. |
| `GET /api/dashboard/funnel` | Pass | HTTP 200 with stage breakdown. Confirmed 2026-03-06. |
| `GET /api/dashboard/stall-stats` | Pass | HTTP 200. Confirmed 2026-03-06. |
| Reassign works safely | Blocked | Requires authenticated live operator action with a real contact. |
| Reset works safely | Blocked | Requires authenticated live operator action. |
| Suppression/handoff reasons visible | Blocked | Requires live handoff scenarios with DB records. |

## Live Scenario Validation

| Scenario | Result | Evidence / Notes |
|---|---|---|
| Seller lead | Blocked | Awaiting live GHL webhook test. Postgres healthy as of 2026-03-06. |
| Buyer lead | Blocked | Awaiting live GHL webhook test. |
| Ambiguous lead | Blocked | Awaiting live GHL webhook test. |
| Bilingual handoff | Blocked | Awaiting live GHL webhook test. |
| Manual takeover | Blocked | Tag exists live. Awaiting live GHL webhook test. |
| Resume after takeover | Blocked | Depends on manual takeover validation. |
| Duplicate/race safety | Blocked | Awaiting live GHL webhook test. |
| Qualified outcome side effects | Blocked | Awaiting live GHL webhook test. |
| Scheduling or fallback | Blocked | Awaiting live GHL webhook test. Booking 404 (GHL calendars.write scope) is a known open bug. |

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
- Live scenario validation blocked until live GHL webhook tests are performed with a real contact.
- Booking 404: GHL `POST /calendars/events` returns 404 — likely needs `calendars.write` scope. Scheduling fallback (prose + human handoff) is in place. Booking itself is an open bug.
- `jorge-realty-db` free tier expires 2026-03-24. Must upgrade plan before handoff or risk data loss.

## Post-Handoff Follow-Up Items

1. **URGENT**: Upgrade `jorge-realty-db` from free tier before 2026-03-24 expiry.
2. Complete GHL legacy tag/field manual review — especially: `ai off`, `ai-off`, `agent bot`, `Bot Type`, `Buyer/Seller`, `AI Last Bot`, `AI Bot Trigger`.
3. Complete GHL workflow manual inventory via GHL UI.
4. Execute live scenario validation checklist (9 scenarios) using real GHL webhooks/SMS.
5. Validate admin/dashboard surfaces with live contact IDs after first real lead comes in.
6. Finalize compatibility shim disposition after live scenario validation.
7. Investigate GHL `calendars.write` scope for booking 404 fix.

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
