# GHL Configuration Contract

This document defines the live GHL contract required for a safe Jorge handoff.

## GHL Owns

- contacts
- tags
- custom fields
- opportunities/pipelines
- operator notifications
- downstream workflow reactions
- manual takeover via `Jorge-Active`

## GHL Must Not Own

- primary routing
- buyer/seller conflict resolution
- qualification state machine logic
- duplicate prevention
- response safety filtering
- handoff semantics

## Required Tags

### Operator Tags

- `Jorge-Active`
- `needs-bilingual`
- `needs-human-review`

### Qualification Tags

- `seller-qualified`
- `buyer-qualified`

### Temperature Tags

- `seller_hot`
- `seller_warm`
- `seller_cold`
- `buyer_hot`
- `buyer_warm`
- `buyer_cold`
- `lead_hot`
- `lead_warm`
- `lead_cold`

## Required Custom Fields

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

> **Note on Field IDs:** GHL uses internal field IDs (e.g. `contact.custom_field_id_abc123`) when writing fields via API. The names above are human-readable labels. During live validation, the operator must capture the actual field IDs from the GHL admin console (Settings → Custom Fields) and confirm they match what the app is writing. Field IDs are account-specific and cannot be determined from this document alone.

## Workflow Policy

### GHL Workflows May

- relay inbound messages to the unified webhook
- notify Jorge on qualification or escalation
- create tasks for `needs-human-review` and `needs-bilingual`
- react to app-owned fields/tags
- move pipeline stages if driven by app-owned fields/tags
- run downstream nurture/reporting workflows

### GHL Workflows Must Not

- decide seller vs buyer vs lead routing
- switch bot ownership on their own
- run the primary qualification state machine
- prevent duplicates
- define handoff rules
- send conflicting AI-path messages

## Manual Takeover Contract

`Jorge-Active` is the sole supported manual suppression control.

Expected behavior:

- AI does not send replies
- canonical state reflects suppression
- removing the tag allows AI to resume on the next inbound message

No second tag, workflow, or custom field should act as a parallel manual takeover mechanism.

## Live Verification Checklist

Before handoff, verify:

1. every required tag exists
2. every required custom field exists
3. field names match the app contract exactly
4. no legacy field still drives routing
5. no workflow performs primary routing or bot switching
6. `Jorge-Active` is the only manual suppression control

## Workflow Inventory Requirement

Every live workflow touching AI-managed contacts must be recorded with:

- workflow name
- trigger
- actions
- sends messages: yes/no
- writes routing fields: yes/no
- writes tags: yes/no
- moves pipeline: yes/no
- conflict risk: yes/no
- disposition: `keep`, `rewrite`, `disable`, `remove`

Use [JORGE_GHL_WORKFLOW_INVENTORY.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_GHL_WORKFLOW_INVENTORY.md) as the canonical inventory table.
