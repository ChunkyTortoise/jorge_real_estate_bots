# Jorge Compatibility Shims

> **Status (2026-03-07):** Canonical migration complete. All routing uses `resolve_mode()` → `ConversationMode`. Zero `assigned_bot:` references remain in production code.

This document tracks the remaining compatibility shims that still exist while the canonical conversation model finishes replacing the older multi-bot routing model.

## Retired Shims

### `assigned_bot:{contact_id}` — **REMOVED** (2026-03-07)

- All inbound routing paths now use `conversation:mode:{contact_id}` (canonical) with GHL `ai_mode` custom field as level-3 fallback.
- Buyer-to-seller handoff now writes canonical mode directly and syncs GHL `ai_mode=seller`.
- No production code references `assigned_bot:` key pattern.

## Active Shims

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
