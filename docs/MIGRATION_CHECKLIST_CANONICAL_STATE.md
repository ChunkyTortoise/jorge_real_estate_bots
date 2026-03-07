# Migration Checklist To Production-Ready Canonical State

This checklist closes the gap between repo-complete migration and production-complete migration.

## Phase 1. Repo State

These items are already expected to be complete:

- canonical conversation model exists
- unified webhook returns canonical fields
- canonical state is first-class in persistence
- admin reassignment accepts canonical `mode`
- dashboard surfaces canonical state
- compatibility shims are secondary and documented
- test suite is green

## Phase 2. Production Database

- identify the production DB used by the deployed service
- verify Alembic `upgrade head` has been applied
- verify canonical conversation columns exist in production
- verify historical rows are readable through canonical state
- verify newly written rows populate canonical columns directly

## Phase 3. GHL Routing Cleanup

- inventory all inbound GHL workflows touching AI contacts
- classify each workflow as `keep`, `rewrite`, `disable`, or `remove`
- remove workflow-first routing behavior
- remove any workflow that can send conflicting AI-path messages
- ensure one unified inbound relay path remains

## Phase 4. GHL Contract Verification

- verify required tags exist
- verify required custom fields exist
- verify field names match the app contract exactly
- verify legacy fields do not still drive routing
- verify `Jorge-Active` is the only manual suppression control

## Phase 5. Live Functional Validation

- verify seller strong-intent routing
- verify buyer strong-intent routing
- verify ambiguous leads remain `lead_intake`
- verify bilingual leads enter `bilingual_handoff`
- verify `Jorge-Active` suppression
- verify resume after removing `Jorge-Active`
- verify duplicate/race handling
- verify qualified contacts write the correct tags and fields
- verify scheduling path or fallback if scheduling is enabled

## Phase 6. Operator Surface Validation

- verify `/admin/conversations/{contact_id}` shows canonical state accurately
- verify dashboard lead/detail/conversation routes show canonical state accurately
- verify reassignment works
- verify reset clears stale route state
- verify suppression and handoff reasons are visible

## Phase 7. Handoff Package

- finalize operator runbook
- finalize workflow inventory
- finalize live validation checklist/results
- finalize compatibility shim disposition
- produce `JORGE_PRODUCTION_HANDOFF_SIGNOFF.md`

## Completion Rule

Migration is complete only when repo state, production runtime, and live GHL configuration all match the same canonical contract.
