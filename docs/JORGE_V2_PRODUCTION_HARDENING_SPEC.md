# Jorge Production Readiness And Handoff Spec

This document is the canonical finish-line spec for Jorge's live deployment.

It does not propose another architecture rewrite. The current repo architecture is accepted as the implementation baseline. The remaining work is production cutover, live validation, operator readiness, and handoff evidence.

## Current State

### Repo Status

The codebase already has the following in place:

- canonical conversation state
- single orchestration/routing layer
- first-class canonical conversation columns
- canonical admin and dashboard surfaces
- explicit compatibility shim tracking
- clean automated test suite

Current repo validation result:

- `1653 passed, 21 skipped` as of 2026-03-06 — rerun `pytest tests/` for the current count if more hardening work lands

### Migration Status

Migration is complete in code and incomplete in production operations.

Completed:

- canonical conversation model
- routing consolidation
- first-class persistence for canonical state
- canonical admin/dashboard contracts
- compatibility shim demotion to secondary status

Not yet complete:

- production DB migration verification
- live GHL workflow inventory and cleanup
- live GHL tags/custom-fields verification
- live production signoff artifact

## Goal

Declare the Jorge bot system safe to hand off by ensuring:

- no hidden routing authority exists outside the app
- GHL cannot contradict app routing
- canonical state is the only meaningful operator model
- human takeover is reliable and visible
- live infrastructure is validated
- handoff includes operator docs and signoff evidence

## Runtime Ownership

### App Owns

- inbound payload normalization
- signature verification
- rate limiting
- deduplication
- per-contact lock acquisition
- canonical routing
- conversation state progression
- response generation and sanitization
- canonical state persistence
- CRM sync actions emitted to GHL

### GHL Owns

- contacts
- tags
- custom fields
- opportunities/pipelines
- operator notifications
- downstream workflows that react to app-owned state
- manual control via `Jorge-Active`

### GHL Must Not Own

- primary routing
- bot switching
- multi-turn qualification logic
- duplicate suppression
- buyer/seller conflict resolution
- handoff semantics

## Canonical Vocabulary

### Modes

- `seller`
- `buyer`
- `lead_intake`
- `bilingual_handoff`
- `human_handoff`

### Statuses

- `active`
- `qualified`
- `stalled`
- `awaiting_human`
- `booked`
- `closed`
- `suppressed`

### Canonical Operator Fields

These fields must remain the standard operator-facing vocabulary:

- `mode`
- `status`
- `handoff_reason`
- `message_suppression_reason`
- `next_recommended_action`

## Definition Of Done

The system is ready to hand off only when all of the following are true:

- canonical conversation state is the effective source of truth in production
- production DB schema includes canonical conversation columns
- active GHL workflows cannot independently route or switch conversations
- required GHL tags and custom fields exist exactly as documented
- `Jorge-Active` is the only manual takeover control
- seller, buyer, ambiguous, bilingual, and manual-takeover flows are validated live
- dashboard/admin surfaces reflect the same state observed in app behavior
- compatibility shims are verified harmless or explicitly listed as follow-up work
- a production signoff document exists with scenario-by-scenario evidence

## Public API Contract To Preserve

### Supported Endpoints

The following are the core inbound, admin, and dashboard endpoints. For the complete route list see the 6 router files: `routes_webhook.py`, `routes_admin.py`, `routes_dashboard.py`, `routes_realtime.py`, `routes_productization.py`, `routes_test_endpoints.py`.

**Inbound / webhook**

- `POST /ghl/webhook/new-lead`
- `POST /api/ghl/webhook`
- `POST /api/ghl/webhook/message-status`

**Admin**

- `GET /admin/settings`
- `PUT /admin/settings/{bot}`
- `POST /admin/reassign-bot`
- `DELETE /admin/reset-state/{bot}/{contact_id}`
- `GET /admin/conversations/{contact_id}`
- `GET /admin/calendar-debug`

**Dashboard**

- `GET /api/dashboard/leads`
- `GET /api/dashboard/leads/{contact_id}`
- `GET /api/dashboard/leads/summary`
- `GET /api/dashboard/conversations/{contact_id}`
- `GET /api/dashboard/handoffs`
- `GET /api/dashboard/metrics`
- `GET /api/dashboard/sms-metrics`
- `GET /api/dashboard/costs`
- `GET /api/dashboard/funnel`
- `GET /api/dashboard/stall-stats`

**Alerts**

- `GET /api/alerts/active`
- `POST /api/alerts/{alert_id}/acknowledge`

**Realtime / events**

- `WS /ws/dashboard`
- `GET /api/events/recent`
- `GET /api/websocket/status`
- `GET /api/events/health`

**Health / metrics (app-level)**

- `GET /health`
- `GET /health/aggregate`
- `POST /analyze-lead`
- `GET /performance`
- `GET /metrics`

**Productization** (see `routes_productization.py` for full list)

- `GET /playbooks`, `POST /playbooks/apply`
- `POST /onboarding/validate-credentials`, `POST /onboarding/bootstrap`
- `GET /integrations/health`
- `GET /roi/summary`, `GET /roi/trends`
- `POST /reports/generate`, `GET /reports/{report_id}`

**Test endpoints** (non-production only)

- `POST /test/seller`
- `POST /test/buyer`

### Canonical Types To Preserve

- `ConversationMode`
- `ConversationStatus`
- `HandoffReason`
- `CanonicalConversation`
- `RoutingDecision`

## Compatibility Policy

The following are transitional only and must never be treated as primary truth:

- `assigned_bot:{contact_id}`
- request/body `bot_type`
- metadata fallback for canonical reads

Rules:

- canonical persisted state wins
- canonical mode cache wins over compatibility assignment cache
- compatibility shims must remain secondary and documented
- no new shim may be added without owner, purpose, removal criteria, and removal phase

See [COMPATIBILITY_SHIMS.md](/Users/cave/Projects/jorge-real-estate-bots/docs/COMPATIBILITY_SHIMS.md).

## Production Readiness Workstreams

### 1. Production Database Migration Verification

Required actions:

1. Identify the production DB used by the deployed service.
2. Verify Alembic `upgrade head` has been applied.
3. Verify canonical columns exist on `conversations`.
4. Verify old rows are backfilled or readable without ambiguity.
5. Verify newly written rows populate first-class canonical fields directly.

Required canonical columns:

- `mode`
- `mode_version`
- `status`
- `handoff_reason`
- `human_takeover`
- `bilingual_required`
- `message_suppression_reason`
- `qualification_summary`
- `next_recommended_action`
- `crm_sync_status`
- `last_inbound_at`
- `last_outbound_at`

Acceptance criteria:

- production schema matches [models.py](/Users/cave/Projects/jorge-real-estate-bots/database/models.py)
- production rows expose canonical state without relying on `metadata_json`
- no runtime errors occur from missing canonical columns

### 2. Live GHL Workflow Inventory And Cleanup

Required actions:

Create an inventory of every live GHL workflow, relay, and automation touching AI-managed contacts.

For each workflow record:

- workflow name
- trigger
- actions
- whether it sends messages
- whether it applies/removes tags
- whether it writes bot/routing fields
- whether it moves pipeline stage
- whether it can conflict with app behavior
- classification: `keep`, `rewrite`, `disable`, `remove`

Acceptance criteria:

- no active workflow can independently route seller vs buyer vs lead
- no active workflow can send a conflicting AI-path message
- an audited workflow inventory exists in the handoff package

### 3. Live GHL Tag And Custom Field Verification

Required tags:

- `Jorge-Active`
- `needs-bilingual`
- `needs-human-review`
- `seller-qualified`
- `buyer-qualified`
- `seller_hot`
- `seller_warm`
- `seller_cold`
- `buyer_hot`
- `buyer_warm`
- `buyer_cold`
- `lead_hot`
- `lead_warm`
- `lead_cold`

Required custom fields:

- `ai_mode`
- `ai_status`
- `ai_temperature`
- `ai_last_summary`
- `ai_last_handoff_reason`
- `ai_last_response_at`
- `property_condition`
- `price_expectation`
- `selling_motivation`
- `buyer_preferences`
- `pre_approval_status`
- `buyer_timeline`

Acceptance criteria:

- live GHL configuration matches [GHL_CONFIGURATION_CONTRACT.md](/Users/cave/Projects/jorge-real-estate-bots/docs/GHL_CONFIGURATION_CONTRACT.md)
- no undocumented field or tag is required for safe operation

### 4. Live Environment Validation

Validate the deployed environment for:

- database URL present and correct
- Redis URL present and correct
- Anthropic API key present and funded
- GHL API key present
- admin API key present
- default location ID present
- calendar ID present if scheduling is enabled
- webhook secret configuration matches intended signature mode

Operational checks:

- health endpoint responds
- Redis is connected or fallback is explicitly accepted as a risk
- DB is reachable
- bot instances initialize
- signature mode behaves as expected

Acceptance criteria:

- no hidden fallback dependency remains undocumented
- Redis and DB status are explicitly known at handoff time

### 5. Live Functional Validation

Run and record the following scenarios:

1. New seller lead
2. New buyer lead
3. Ambiguous lead
4. Bilingual lead
5. Manual takeover
6. Resume after manual takeover
7. Duplicate/race safety
8. Qualified seller/buyer outcome
9. Scheduling path if enabled

Each scenario must include:

- observed inbound behavior
- outbound response correctness
- canonical mode/status
- GHL side effects
- dashboard/admin state
- pass/fail result

Acceptance criteria:

- each scenario has explicit evidence
- app behavior, GHL state, and operator surfaces agree

### 6. Operator Surface Validation

Validate admin conversation detail exposes:

- `mode`
- `mode_version`
- `status`
- `handoff_reason`
- `human_takeover`
- `bilingual_required`
- `message_suppression_reason`
- `qualification_summary`
- `next_recommended_action`
- `crm_sync_status`
- `last_inbound_at`
- `last_outbound_at`
- `temperature`
- cache debug fields

Validate dashboard surfaces expose:

- canonical mode
- canonical status
- handoff reason
- suppression reason
- qualification summary
- timing fields
- temperature
- next recommended action

Acceptance criteria:

- Jorge can understand why a contact is silent or escalated without reading code
- reset/reassign actions do not leave stale route state behind

### 7. Compatibility Shim Disposition

Review each shim:

- `assigned_bot:{contact_id}`
- `bot_type` request compatibility
- metadata fallback through canonical extractor

Required disposition:

- verify whether the shim is still exercised in production
- confirm it is secondary only
- confirm removal criteria
- mark whether it is safe to keep or must be removed before handoff

Acceptance criteria:

- the handoff package includes a shim table with owner, purpose, precedence, removal trigger, and removal phase

### 8. Runbook Finalization

The operator runbook must include:

- manual takeover
- AI resume behavior
- suppression diagnosis
- bilingual/human escalation diagnosis
- safe reassignment and reset
- generic fallback diagnosis
- Redis disconnect diagnosis
- GHL side-effect diagnosis
- escalation contacts / owners

Acceptance criteria:

- a non-engineer can follow common support paths
- a support engineer can diagnose routing and suppression without reading source

### 9. Production Signoff Artifact

Create a final signoff document containing:

- deploy version / commit
- environment validation result
- DB migration status
- Redis status
- workflow inventory result
- tag/field verification result
- scenario-by-scenario live validation result
- known limitations
- accepted compatibility shims
- post-handoff follow-up items
- rollback/remediation notes if something failed

Required filename:

- `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`

## Validation Requirements

### Repo Validation

Run:

- full suite
- targeted webhook/admin/dashboard tests
- migration-related tests
- chaos tests for cache/GHL failures
- event broker and websocket tests

Required outcome:

- green suite
- no unexpected warnings

### Production Validation

Run live checks for:

- seller path
- buyer path
- ambiguous lead path
- bilingual handoff
- manual takeover
- resume path
- duplicate handling
- scheduling fallback path if enabled
- tag/custom-field writes
- dashboard/admin state verification

### Failure-Mode Validation

At minimum verify:

- Redis unavailable behavior is understood and documented
- Anthropic credits exhaustion behavior is understood and documented
- GHL failure does not create dangerous duplicate/conflicting actions
- signature mode matches deployment intent

## Assumptions And Defaults

- the current repo architecture is the accepted baseline
- the app remains the routing and decision engine
- GHL remains the CRM and operator system of record
- canonical conversation state is the source of truth
- compatibility shims may remain only if documented and secondary
- production readiness requires live validation, not just green tests
- if Redis is still in fallback mode at handoff, that is an explicit known limitation
- if Anthropic billing is not active, that is an explicit known limitation

## Known Issues / Limitations

The following are confirmed issues or production constraints at the time of this spec. They must be acknowledged in the handoff signoff.

### GHL Calendar Booking — 404 on POST /calendars/events

Confirmed live (2026-03-04 E2E test): booking a slot returns `404` from GHL's `POST /calendars/events` endpoint. Free-slot retrieval works. Likely cause: missing `calendars.write` scope on the GHL API key. The scheduling offer path works; only the final booking write fails. Must be resolved or explicitly accepted before declaring scheduling live.

### GHL Webhook Secret Must Be Empty

If `GHL_WEBHOOK_SECRET` is set in the Render environment, all inbound webhooks return `401`. The value must be left **empty/unset** for signature verification to pass in the current deployment. This is a known configuration constraint — do not set this variable without verifying the signature mode in `routes_webhook.py`.

### message.body Dict Format

GHL delivers `message.body` as a dict `{id, body, type}`, not a plain string. Extracting `.body` directly raises `AttributeError: 'dict' has no attribute 'strip'`. This was a production bug fixed in commit `88afbfd` (`routes_webhook.py`). Verified fixed. Included here as a reminder that GHL payload shapes should be treated as structured objects, not primitives.

## Deliverables

The handoff is complete when the following exist and are accurate:

- canonical readiness spec
- operator runbook
- GHL configuration contract
- compatibility shim register
- workflow inventory table
- live validation checklist/results
- production signoff document
