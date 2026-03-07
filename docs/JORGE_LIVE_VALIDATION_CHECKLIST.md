# Jorge Live Validation Checklist

This checklist is the execution plan for final production validation.

## Environment Validation

- [ ] health endpoint responds
- [ ] deployed commit/version recorded
- [ ] production DB reachable
- [ ] canonical migration applied in production
- [ ] Redis reachable
- [ ] Redis fallback status explicitly known
- [ ] Anthropic billing/credits active
- [ ] GHL API key valid
- [ ] admin API key valid
- [ ] default location ID configured
- [ ] calendar ID configured if scheduling is enabled
- [ ] webhook signature mode verified

## GHL Contract Validation

- [ ] export tags, custom fields, and workflows in JSON form
- [ ] run `scripts/validate_ghl_contract.py`
- [ ] review [ghl_legacy_contract_review.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_legacy_contract_review.md) and classify all high-risk legacy tags/fields
- [ ] attach `docs/ghl_contract_validation_report.md` to the evidence set
- [ ] all required tags exist
- [ ] all required custom fields exist
- [ ] field names match the documented contract exactly
- [ ] no legacy field still drives routing
- [ ] `Jorge-Active` is the sole manual takeover control
- [ ] live workflows are fully inventoried
- [ ] no live workflow performs primary routing
- [ ] no live workflow can send a conflicting AI-path message

## Scenario Validation

### 1. Seller Lead

- [ ] inbound seller-intent message received
- [ ] canonical `mode = seller`
- [ ] seller-safe response sent
- [ ] correct seller tags/fields written
- [ ] admin/dashboard show matching canonical state

### 2. Buyer Lead

- [ ] inbound buyer-intent message received
- [ ] canonical `mode = buyer`
- [ ] buyer-safe response sent
- [ ] correct buyer tags/fields written
- [ ] admin/dashboard show matching canonical state

### 3. Ambiguous Lead

- [ ] ambiguous message received
- [ ] canonical `mode = lead_intake`
- [ ] clarification response sent
- [ ] no wrong-path language present

### 4. Bilingual Lead

- [ ] bilingual/Spanish message received
- [ ] canonical `mode = bilingual_handoff`
- [ ] canonical `status = awaiting_human`
- [ ] suppression/handoff visible
- [ ] `needs-bilingual` side effects applied correctly

### 5. Manual Takeover

- [ ] `Jorge-Active` added
- [ ] AI stops replying
- [ ] canonical `status = suppressed`
- [ ] suppression reason visible

### 6. Resume After Manual Takeover

- [ ] `Jorge-Active` removed
- [ ] next inbound resumes correctly
- [ ] conversation does not reclassify incorrectly from scratch

### 7. Duplicate/Race Safety

- [ ] duplicate inbound does not create duplicate send
- [ ] per-contact lock behaves correctly
- [ ] no conflicting double-message is observed

### 8. Qualified Outcome

- [ ] qualified seller/buyer writes the correct tags
- [ ] qualified seller/buyer writes the correct fields
- [ ] downstream GHL workflows behave as reaction-only

### 9. Scheduling Path

- [ ] scheduling offer works if enabled
- [ ] no-calendar fallback works safely
- [ ] booking-failure fallback works safely

## Operator Surface Validation

- [ ] `/admin/conversations/{contact_id}` shows canonical state accurately
- [ ] `/api/dashboard/leads/{contact_id}` shows canonical state accurately
- [ ] `/api/dashboard/conversations/{contact_id}` shows canonical state accurately
- [ ] reassignment works
- [ ] reset clears stale state
- [ ] suppression reasons are visible
- [ ] handoff reasons are visible

### 10. Human Handoff

- [ ] human handoff triggered (via admin reassignment to `mode = human_handoff`, low-confidence trigger, or ambiguous intake escalation)
- [ ] canonical `mode = human_handoff`
- [ ] canonical `status = suppressed` or `awaiting_human` depending on trigger path
- [ ] AI stops sending replies
- [ ] `handoff_reason` populated (e.g. `low_confidence`, `manual_override`, `ambiguous_intake`)
- [ ] admin/dashboard surfaces reflect handoff state

## Signoff Rule

This checklist is complete only when every item is either:

- marked pass, or
- marked blocked/failed with a written explanation in `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`
