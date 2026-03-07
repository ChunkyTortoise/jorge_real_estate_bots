# Jorge Operator Runbook

> **NOTE:** This runbook describes designed behavior. Live validation is pending — see `MIGRATION_CHECKLIST_CANONICAL_STATE.md` for current status. Escalation contact names (section below) must be filled in before handoff is declared complete.

This runbook is for Jorge or any support/operator managing live conversations.

## Core Rule

The app is the routing brain.
GHL is the CRM and operator UI.

If a contact behaves unexpectedly, always check canonical state first:

- `mode`
- `status`
- `handoff_reason`
- `message_suppression_reason`
- `next_recommended_action`

Use:

- `GET /admin/conversations/{contact_id}`
- `GET /api/dashboard/leads/{contact_id}`
- `GET /api/dashboard/conversations/{contact_id}`

## Manual Takeover

### To take over a contact manually

1. Add the `Jorge-Active` tag in GHL.
2. The app will stop sending AI replies for that contact.
3. The contact will show canonical suppression state:
   - `suppressed = True`
   - `handoff_reason = jorge_active`
   - `message_suppression_reason` populated
   - The resulting `mode` depends on the bot context at the time of takeover (e.g. a buyer contact stays in `buyer` mode, not automatically set to `human_handoff`). Check canonical state via `/admin/conversations/{contact_id}` for the actual mode.

### To resume AI after manual takeover

1. Remove the `Jorge-Active` tag in GHL.
2. Wait for the next inbound message from the contact.
3. The app should resume from canonical state rather than starting over.

If AI does not resume as expected:

- check `mode`
- check `status`
- check `handoff_reason`
- check whether the conversation was explicitly reassigned or reset

## What To Check If A Contact Is Silent

Check the following in order:

1. `Jorge-Active` tag is present
2. canonical `status = suppressed`
3. canonical `handoff_reason = jorge_active`
4. canonical `message_suppression_reason` is populated
5. contact is in `bilingual_handoff` or `human_handoff`
6. app health is normal and webhook requests are succeeding

If silent behavior is intentional, do not reset the conversation just to force a reply.

## What To Check If A Contact Was Escalated

Expected escalation states:

- `status = awaiting_human`
- `status = stalled`
- `mode = bilingual_handoff`
- `mode = human_handoff`

Expected handoff reasons:

- `jorge_active`
- `needs_bilingual`
- `needs_human_review`
- `low_confidence`
- `manual_override`
- `ambiguous_intake`

If escalated:

- confirm whether a human should respond manually
- confirm downstream task/notification workflow ran in GHL
- do not remove handoff state unless reassignment or resume is intended

## Reassigning A Contact Safely

Use `POST /admin/reassign-bot` with:

- `mode = seller`
- `mode = buyer`
- `mode = lead_intake`
- `mode = bilingual_handoff`
- `mode = human_handoff`

Legacy `bot_type` is accepted for compatibility, but canonical `mode` should be preferred.

After reassignment, verify:

- canonical `mode` changed
- the next inbound message follows the new mode
- any stale `assigned_bot` compatibility state is cleared if reassigned to a handoff mode

## Resetting A Contact Safely

Use `DELETE /admin/reset-state/{bot}/{contact_id}` only when the conversation should truly restart.

Reset clears:

- bot-specific conversation state
- canonical mode cache
- compatibility assignment cache

After reset:

- the next inbound message may be reclassified from scratch
- only use reset when continuity is no longer valuable

## If Responses Become Generic Fallback Only

This usually means Anthropic is unavailable or credits are exhausted.

Check:

- Anthropic billing/credits
- app logs for Claude/API failures
- whether responses are still being sanitized and delivered

Expected degraded behavior:

- conversation continues
- replies become safe scripted/fallback responses
- no conversation should die silently

This is an accepted degraded mode only if documented in the handoff signoff.

## If Redis Is Disconnected

Check:

- health endpoint
- deploy logs for Redis connection failures
- whether the app is using MemoryCache fallback

Risk:

- conversations may still work
- memory-backed state can be lost on restart

If Redis fallback is active in production:

- record it as a known limitation
- do not claim full production readiness without explicit acceptance of that risk

## If GHL Side Effects Are Missing

If messages send but tags/fields do not update:

1. check app logs for GHL API failures
2. verify GHL API key is valid
3. verify required tags and custom fields exist
4. verify no GHL workflow is overwriting app-managed fields
5. verify deferred tag/workflow actions are firing after send path

## If A Contact Gets The Wrong Type Of Message

Immediately check:

- canonical `mode`
- canonical `status`
- `handoff_reason`
- compatibility `assigned_bot` state
- whether a GHL workflow independently routed or messaged the contact

Wrong-type messaging means the handoff is not safe until the routing source is identified and corrected.

## What The Operator UI Must Show

For any active issue, verify the UI exposes:

- `mode`
- `status`
- `handoff_reason`
- `message_suppression_reason`
- `qualification_summary`
- `next_recommended_action`
- `last_inbound_at`
- `last_outbound_at`
- `temperature`

## Escalation Contacts / Owners

Use the following owner model in the handoff:

- App/runtime owner: [ ] TODO — name of engineering owner of the Render deployment
- GHL workflow owner: [ ] TODO — name of operator/admin responsible for workflow changes in GHL
- Billing/API owner: [ ] TODO — name of account owner for Anthropic and GHL credentials

These names must be filled in before handoff is declared complete. Record them in `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`.
