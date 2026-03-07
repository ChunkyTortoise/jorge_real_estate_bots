# Jorge Canonical Doc Map

This file records which documents are authoritative after the canonical conversation migration.

## Canonical docs

- [JORGE_V2_PRODUCTION_HARDENING_SPEC.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_V2_PRODUCTION_HARDENING_SPEC.md)
  Source of truth for architecture, routing ownership, endpoint list, and finish-line requirements.
- [JORGE_OPERATOR_RUNBOOK.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_OPERATOR_RUNBOOK.md)
  Source of truth for Jorge/operator behavior and manual takeover.
- [GHL_CONFIGURATION_CONTRACT.md](/Users/cave/Projects/jorge-real-estate-bots/docs/GHL_CONFIGURATION_CONTRACT.md)
  Source of truth for GHL-owned tags, fields, and workflow boundaries.
- [MIGRATION_CHECKLIST_CANONICAL_STATE.md](/Users/cave/Projects/jorge-real-estate-bots/docs/MIGRATION_CHECKLIST_CANONICAL_STATE.md)
  Source of truth for the canonical-state rollout checklist.
- [JORGE_GHL_WORKFLOW_INVENTORY.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_GHL_WORKFLOW_INVENTORY.md)
  Source of truth for live GHL workflow audit and disposition. Currently a template — requires live GHL access to populate.
- [JORGE_GHL_EXPORT_CAPTURE.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_GHL_EXPORT_CAPTURE.md)
  Source of truth for how to capture live GHL tags, fields, and workflow data into repo-validated evidence.
- [JORGE_LIVE_VALIDATION_CHECKLIST.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_LIVE_VALIDATION_CHECKLIST.md)
  Source of truth for the final production validation run.
- [JORGE_PRODUCTION_HANDOFF_SIGNOFF.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md)
  Source of truth for the final handoff decision and evidence record.
- [JORGE_PRODUCTION_FINDINGS_2026-03-06.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_PRODUCTION_FINDINGS_2026-03-06.md)
  Current live findings snapshot from the first production-finalization pass. Not the final signoff, but authoritative for known blockers observed on 2026-03-06.
- [ghl_contract_validation_report.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_contract_validation_report.md)
  Current live GHL contract validation evidence for required tags and custom fields. Regenerate after each GHL cleanup pass.
- [ghl_legacy_contract_review.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_legacy_contract_review.md)
  Current live GHL legacy review evidence identifying extra tags and fields that may still influence routing, suppression, or workflow branching.
- [ghl_contract_sync_plan.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_contract_sync_plan.md)
  Current dry-run creation plan for missing canonical GHL tags and custom fields. Review before any live GHL mutation.
- [COMPATIBILITY_SHIMS.md](/Users/cave/Projects/jorge-real-estate-bots/docs/COMPATIBILITY_SHIMS.md)
  Canonical register of transitional compatibility shims. Referenced by the hardening spec and signoff doc.
- [TROUBLESHOOTING.md](/Users/cave/Projects/jorge-real-estate-bots/docs/TROUBLESHOOTING.md)
  Canonical operator troubleshooting reference. Maintained alongside the runbook.
- [WEBHOOK_ROUTING_SPEC.md](/Users/cave/Projects/jorge-real-estate-bots/docs/WEBHOOK_ROUTING_SPEC.md)
  Canonical spec for inbound webhook routing logic and signature verification.

## Superseded / historical docs

- [OPERATIONS.md](/Users/cave/Projects/jorge-real-estate-bots/docs/OPERATIONS.md)
  Historical deployment/reference notes. Not authoritative for operator flow.
- [jorge-system-map.md](/Users/cave/Projects/jorge-real-estate-bots/docs/jorge-system-map.md)
  Historical workflow-first system map. Not authoritative for routing or ownership.
- [bot-spec.md](/Users/cave/Projects/jorge-real-estate-bots/docs/bot-spec.md)
  Historical pre-canonical multi-bot behavior spec.
- [03-current-system-deployed.md](/Users/cave/Projects/jorge-real-estate-bots/docs/03-current-system-deployed.md)
  Historical deployment snapshot. Not authoritative for current routing ownership.
- [E2E_SMOKE_TEST.md](/Users/cave/Projects/jorge-real-estate-bots/docs/E2E_SMOKE_TEST.md)
  Historical validation snapshot. Useful evidence, but not a substitute for current handoff signoff.
- [02-ghl-setup-guide.md](/Users/cave/Projects/jorge-real-estate-bots/docs/02-ghl-setup-guide.md)
  Historical GHL setup walkthrough. Superseded by `GHL_CONFIGURATION_CONTRACT.md`.
- [04-enterprise-dev-beyond-spec.md](/Users/cave/Projects/jorge-real-estate-bots/docs/04-enterprise-dev-beyond-spec.md)
  Historical feature-planning notes. Not authoritative for current state.
- [05-alignment-corrections-today.md](/Users/cave/Projects/jorge-real-estate-bots/docs/05-alignment-corrections-today.md)
  Historical alignment session notes. Not authoritative for current state.
- [06-remaining-work-to-finish.md](/Users/cave/Projects/jorge-real-estate-bots/docs/06-remaining-work-to-finish.md)
  Historical work-in-progress list. Superseded by `MIGRATION_CHECKLIST_CANONICAL_STATE.md`.
- [jorge-status-2026-03-02.md](/Users/cave/Projects/jorge-real-estate-bots/docs/jorge-status-2026-03-02.md)
  Historical status snapshot from 2026-03-02. Not authoritative for current state.
- [jorge-update-email.md](/Users/cave/Projects/jorge-real-estate-bots/docs/jorge-update-email.md)
  Historical client update email draft. Not authoritative.
- [SPEC.md](/Users/cave/Projects/jorge-real-estate-bots/docs/SPEC.md)
  Historical pre-canonical system spec. Superseded by `JORGE_V2_PRODUCTION_HARDENING_SPEC.md`.
- [EVAL_PROMPT.md](/Users/cave/Projects/jorge-real-estate-bots/docs/EVAL_PROMPT.md)
  Historical LLM evaluation prompt. Not authoritative for production behavior.
- [billing_public_contract.md](/Users/cave/Projects/jorge-real-estate-bots/docs/billing_public_contract.md)
  Historical billing contract draft. Review before handoff to confirm whether it applies.
- [PRODUCTIZATION_CONTINUATION_CHECKLIST.md](/Users/cave/Projects/jorge-real-estate-bots/docs/PRODUCTIZATION_CONTINUATION_CHECKLIST.md)
  Historical productization work checklist. Not authoritative for core handoff.

## Directories

- `adr/` — Architecture Decision Records. Historical decisions; read-only reference.
- `handoffs/` — Previous handoff drafts and session notes. Historical; superseded by current handoff package.
- `phases/` — Phase-by-phase build notes. Historical; not authoritative for current state.
- `reference/` — Supporting reference material. Check individual files for relevance.
- `screenshots/` — UI and flow screenshots. Evidence artifacts; not authoritative for behavior.

## Rule

If a document conflicts with the canonical docs above, follow the canonical docs and mark the older document for update or removal.
