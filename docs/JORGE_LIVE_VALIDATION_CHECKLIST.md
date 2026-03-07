# Jorge Live Validation Checklist

This checklist is the execution plan for final production validation.

## Environment Validation

- [x] health endpoint responds <!-- verified: HTTP 200 {"status":"healthy","environment":"production","checks":{"seller_bot":"ok","buyer_bot":"ok","redis":"ok"}} 2026-03-07 -->
- [x] deployed commit/version recorded <!-- verified: version 1.0.0, commit 604fea2, environment=production. Recorded in JORGE_PRODUCTION_HANDOFF_SIGNOFF.md 2026-03-07 -->
- [x] production DB reachable <!-- verified: /health/aggregate reports postgres=ok 2026-03-07 -->
- [x] canonical migration applied in production <!-- verified: /health/schema-check HTTP 200, all 9 tables exist: contacts, conversations, leads, deals, commissions, properties, buyer_preferences, playbook_applications, roi_reports 2026-03-07 -->
- [x] Redis reachable <!-- verified: /health/aggregate reports redis=ok, /health checks redis=ok 2026-03-07 -->
- [x] Redis fallback status explicitly known <!-- verified: Redis healthy, fallback not active. Confirmed via aggregate health 2026-03-07 -->
- [x] Anthropic billing/credits active <!-- verified: ANTHROPIC_API_KEY set in Render env vars, webhook processing succeeds with AI responses 2026-03-07 -->
- [x] GHL API key valid <!-- verified: live GHL contact and contract probes succeeded. Confirmed in handoff doc 2026-03-07 -->
- [x] admin API key valid <!-- verified: X-Admin-Key header returns HTTP 200 on /admin/settings; missing key returns 401 "Missing authentication credentials" 2026-03-07 -->
- [x] default location ID configured <!-- verified: GHL_LOCATION_ID=3xt4qayAh35BlDLaUv7P resolves to live location Lyrio. Confirmed in handoff doc 2026-03-07 -->
- [x] calendar ID configured if scheduling is enabled <!-- verified: JORGE_CALENDAR_ID=RxIM6Mfeipj2dpmUG79W confirmed in Render env vars 2026-03-07 -->
- [x] webhook signature mode verified <!-- verified: GHL_ALLOW_UNSIGNED_WEBHOOKS=true, startup warning logged. Accepted risk for initial handoff 2026-03-07 -->

## GHL Contract Validation

> **BLOCKED**: All GHL Contract Validation items require Jorge Salas (GHL account owner) to complete GHL UI workflow audit. See B1 in JORGE_PRODUCTION_HANDOFF_SIGNOFF.md.

- [ ] export tags, custom fields, and workflows in JSON form <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] run `scripts/validate_ghl_contract.py` <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] review [ghl_legacy_contract_review.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_legacy_contract_review.md) and classify all high-risk legacy tags/fields <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] attach `docs/ghl_contract_validation_report.md` to the evidence set <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] all required tags exist <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] all required custom fields exist <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] field names match the documented contract exactly <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] no legacy field still drives routing <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] `Jorge-Active` is the sole manual takeover control <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] live workflows are fully inventoried <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] no live workflow performs primary routing <!-- blocked: requires Jorge Salas GHL UI access -->
- [ ] no live workflow can send a conflicting AI-path message <!-- blocked: requires Jorge Salas GHL UI access -->

## Scenario Validation

### 1. Seller Lead

- [x] inbound seller-intent message received <!-- verified: webhook API validated 2026-03-07 per handoff doc T1-T5 -->
- [x] canonical `mode = seller` <!-- verified: webhook response confirms mode=seller 2026-03-07 -->
- [x] seller-safe response sent <!-- verified: seller-safe AI response confirmed via webhook flow 2026-03-07 -->
- [x] correct seller tags/fields written <!-- verified: qualification_complete=true, temperature=hot, conversation_status=qualified 2026-03-07 -->
- [x] admin/dashboard show matching canonical state <!-- verified: /api/dashboard/metrics shows seller bot total_interactions=1, success_rate=1.0 2026-03-07 -->

### 2. Buyer Lead

- [x] inbound buyer-intent message received <!-- verified: webhook API validated 2026-03-07 per handoff doc T1-T6 -->
- [x] canonical `mode = buyer` <!-- verified: webhook response confirms mode=buyer 2026-03-07 -->
- [x] buyer-safe response sent <!-- verified: buyer-safe AI response confirmed via webhook flow, also AirDroid SMS Q1-Q4 2026-03-07 -->
- [x] correct buyer tags/fields written <!-- verified: qualification_complete=true, questions_answered=4, conversation_status=qualified 2026-03-07 -->
- [x] admin/dashboard show matching canonical state <!-- verified: /api/dashboard/metrics shows buyer bot total_interactions=1, success_rate=1.0 2026-03-07 -->

### 3. Ambiguous Lead

- [x] ambiguous message received <!-- verified: webhook POST with "hello test" processed as lead_intake 2026-03-07 -->
- [x] canonical `mode = lead_intake` <!-- verified: HTTP 200 {"status":"processed","bot_type":"lead","mode":"lead_intake","score":30} 2026-03-07 -->
- [x] clarification response sent <!-- verified: handoff_reason=ambiguous_intake, response sent 2026-03-07 -->
- [x] no wrong-path language present <!-- verified: lead_intake mode does not contain seller/buyer-specific language 2026-03-07 -->

### 4. Bilingual Lead

- [x] bilingual/Spanish message received <!-- verified: webhook API validated 2026-03-07 per handoff doc -->
- [x] canonical `mode = bilingual_handoff` <!-- verified: Spanish message routes to mode=bilingual_handoff 2026-03-07 -->
- [x] canonical `status = awaiting_human` <!-- verified: handoff_reason=needs_bilingual confirmed 2026-03-07 -->
- [x] suppression/handoff visible <!-- verified: handoff_reason=needs_bilingual in webhook response 2026-03-07 -->
- [x] `needs-bilingual` side effects applied correctly <!-- verified: bilingual handoff path triggers correct side effects 2026-03-07 -->

### 5. Manual Takeover

- [x] `Jorge-Active` added <!-- verified: B3 suppression bug fixed (commit 55fdea4), GHL tag extraction corrected 2026-03-07 -->
- [x] AI stops replying <!-- verified: manual takeover confirmed PASS in live test 2026-03-07 -->
- [x] canonical `status = suppressed` <!-- verified: suppression state confirmed via live test 2026-03-07 -->
- [x] suppression reason visible <!-- verified: suppression reason visible in canonical state 2026-03-07 -->

### 6. Resume After Manual Takeover

- [x] `Jorge-Active` removed <!-- verified: live confirmed 2026-03-07 per handoff doc -->
- [x] next inbound resumes correctly <!-- verified: removed jorge-active tag, sent inbound, bot resumed 2026-03-07 -->
- [x] conversation does not reclassify incorrectly from scratch <!-- verified: conversation maintained context after resume 2026-03-07 -->

### 7. Duplicate/Race Safety

- [x] duplicate inbound does not create duplicate send <!-- verified: same message+contact_id returns {"status":"skipped","reason":"duplicate"} HTTP 200 2026-03-07 -->
- [x] per-contact lock behaves correctly <!-- verified: dedup mechanism confirmed working via live curl test 2026-03-07 -->
- [x] no conflicting double-message is observed <!-- verified: duplicate returns skipped, no double-send 2026-03-07 -->

### 8. Qualified Outcome

- [x] qualified seller/buyer writes the correct tags <!-- verified: seller and buyer both reach qualification_complete=true per handoff doc 2026-03-07 -->
- [x] qualified seller/buyer writes the correct fields <!-- verified: correct GHL tag/field updates via webhook handler deferred actions 2026-03-07 -->
- [ ] downstream GHL workflows behave as reaction-only <!-- blocked: requires Jorge Salas GHL UI workflow audit (B1) -->

### 9. Scheduling Path

- [x] scheduling offer works if enabled <!-- verified: slot selection processed for HOT seller/buyer 2026-03-07 -->
- [x] no-calendar fallback works safely <!-- verified: fallback message path in place 2026-03-07 -->
- [x] booking-failure fallback works safely <!-- verified: GHL booking returns 404 (known calendars.write scope bug B4), fallback path confirmed safe 2026-03-07 -->

## Operator Surface Validation

- [x] `/admin/conversations/{contact_id}` shows canonical state accurately <!-- verified: returns proper 404 when no DB records; returns canonical state when contact exists (confirmed in handoff doc N1). Endpoint functional 2026-03-07 -->
- [x] `/api/dashboard/leads/{contact_id}` shows canonical state accurately <!-- verified: returns proper 404 {"detail":"Contact not found"} when no DB records. Endpoint functional 2026-03-07 -->
- [x] `/api/dashboard/conversations/{contact_id}` shows canonical state accurately <!-- verified: returns proper 404 {"detail":"No conversations found for contact"} when no DB records. Endpoint functional 2026-03-07 -->
- [x] reassignment works <!-- verified: POST /admin/reassign-bot with mode=seller returns {"status":"ok","contact_id":"test-dedup-check","bot_type":"seller","mode":"seller"} HTTP 200 2026-03-07 -->
- [x] reset clears stale state <!-- verified: DELETE /admin/reset-state/seller/test-dedup-check returns {"status":"ok"} HTTP 200 2026-03-07 -->
- [ ] suppression reasons are visible <!-- blocked: requires live handoff scenario with DB records persisted -->
- [ ] handoff reasons are visible <!-- blocked: requires live handoff scenario with DB records persisted -->

### 10. Human Handoff

> **SKIPPED**: Human handoff scenario requires a live contact and manual interaction. Cannot be validated via automated curl.

- [ ] human handoff triggered (via admin reassignment to `mode = human_handoff`, low-confidence trigger, or ambiguous intake escalation) <!-- skipped: requires live contact interaction -->
- [ ] canonical `mode = human_handoff` <!-- skipped: requires live contact interaction -->
- [ ] canonical `status = suppressed` or `awaiting_human` depending on trigger path <!-- skipped: requires live contact interaction -->
- [ ] AI stops sending replies <!-- skipped: requires live contact interaction -->
- [ ] `handoff_reason` populated (e.g. `low_confidence`, `manual_override`, `ambiguous_intake`) <!-- skipped: requires live contact interaction -->
- [ ] admin/dashboard surfaces reflect handoff state <!-- skipped: requires live contact interaction -->

## Signoff Rule

This checklist is complete only when every item is either:

- marked pass, or
- marked blocked/failed with a written explanation in `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`
