# Jorge Compatibility Shims

This document tracks the remaining compatibility shims that still exist while the canonical conversation model finishes replacing the older multi-bot routing model.

## Active Shims

### `assigned_bot:{contact_id}`

- Owner: webhook/admin/buyer handoff compatibility
- Purpose: preserve behavior for older routing assumptions and live contacts created before canonical mode cache became primary
- Current precedence: secondary only, behind `conversation:mode:{contact_id}`
- Still required for:
  - legacy contacts already carrying assignment state
  - buyer-to-seller early-flow handoff compatibility
  - `/ghl/webhook/new-lead` follow-up stickiness during migration
- Removal criteria:
  - all inbound routing paths use canonical mode cache and persisted canonical mode
  - buyer-to-seller handoff no longer needs assignment fallback
  - live GHL workflows verified not to depend on assignment semantics
- Planned phase: remove after live production signoff

### `bot_type` request compatibility

- Owner: webhook/admin request parsing
- Purpose: allow older payloads and admin callers to continue working while canonical `mode` becomes standard
- Current precedence: normalized into canonical `ConversationMode`
- Removal criteria:
  - all trusted callers send canonical `mode`
  - GHL custom field and admin tools fully standardized on `ai_mode`
- Planned phase: keep temporarily, then deprecate with docs warning

### Canonical metadata fallback in `metadata_json`

- Owner: persistence read compatibility
- Purpose: support rows written before canonical columns existed
- Current precedence: fallback only through `extract_canonical_view(...)`
- Removal criteria:
  - migration has run everywhere
  - no production rows rely on metadata-only canonical fields
  - all operator surfaces and analytics paths read first-class columns
- Planned phase: remove after post-migration verification

## Rule

No new compatibility shim should be added unless it has:

- a named owner
- a concrete migration purpose
- a removal condition
- a planned removal phase
