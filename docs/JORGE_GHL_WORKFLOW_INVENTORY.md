# Jorge GHL Workflow Inventory

> **STATUS: PARTIALLY SEEDED — live workflow list captured, manual action review still required.**
> The live workflow list has now been captured via the working GHL endpoint and exported to:
> [ghl_workflows_export.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_workflows_export.md)
> and
> [ghl_workflows_export.json](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_workflows_export.json).
> Trigger details and actual workflow actions still require GHL admin review in the UI before this inventory is complete.

After capturing live tags, custom fields, and workflows, generate a validation
report with:

```bash
python3 scripts/validate_ghl_contract.py \
  --tags-json path/to/tags.json \
  --fields-json path/to/custom_fields.json \
  --workflows-json path/to/workflows.json \
  --output docs/ghl_contract_validation_report.md
```

See [JORGE_GHL_EXPORT_CAPTURE.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_GHL_EXPORT_CAPTURE.md) for the expected export shapes.

Use this document to inventory every live GHL workflow that touches AI-managed contacts.

## Current Live Export Snapshot

- live workflow count captured via API: `226`
- heuristic routing/conflict candidates: `68`
- published workflows in export: `164`

Primary evidence artifacts:

- [ghl_workflows_export.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_workflows_export.md)
- [ghl_workflows_export.json](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_workflows_export.json)
- [ghl_contract_validation_report.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_contract_validation_report.md)

High-priority workflows to inspect first in the GHL UI:

- `5. Process Message - Which Bot?`
- `6. Catch Unknown Inbound SMS`
- `New Inbound Lead`
- `Jorge AI Bot - Inbound Message Handler`
- `Jorge — Bot Activation`
- `2. AI OFF/ON Tag Added -> AI Assistant is: (Custom Field Change)`
- `AI Bot - Jorge Qualification`
- `Lead Intake Notification`
- `Qualified Lead Notify - SMS`
- `Qualified Lead Notify - Email`

These names came from the live export and should be treated as first-pass audit
targets, not final dispositions.

## Historical Candidate Names To Verify In GHL

These names come from older repo docs and must not be treated as authoritative
live inventory. They are here only to make the manual GHL audit faster.

- `New Inbound Lead`
- `5. Process Message - Which Bot?`
- `Seller Bot Relay`
- `Buyer Bot Relay`
- `Lead Bot Relay`
- calendar booking workflow referenced in historical smoke docs:
  - `577d56c4-28af-4668-8d84-80f5db234f48`

Also review any workflow in GHL that references any of the following legacy
controls from [ghl_legacy_contract_review.md](/Users/cave/Projects/jorge-real-estate-bots/docs/ghl_legacy_contract_review.md):

- `ai off`
- `ai-off`
- `agent bot`
- `buyer bot`
- `direct to buyer bot`
- `direct to seller bot`
- `Bot Type`
- `Buyer/Seller`

## Instructions

For each workflow:

- include the exact live workflow name
- describe the trigger precisely
- list every action that affects messaging, tags, fields, or routing
- mark whether it can conflict with the app
- choose a disposition:
  - `keep`
  - `rewrite`
  - `disable`
  - `remove`

## Workflow Table

| Workflow Name | Trigger | Sends Messages | Writes Tags | Writes Fields | Moves Pipeline | Routing/Bot Logic Present | Conflict Risk | Disposition | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| Example: New Inbound Lead Relay | Inbound SMS received | No | No | No | No | No | No | keep | Relays inbound payload to app only |

## Required Review Questions

For every workflow marked `keep`, confirm:

- it does not decide seller vs buyer vs lead routing
- it does not switch `mode` (or legacy `bot_type`) or any equivalent routing field independently
- it does not send a message that can conflict with an AI-path message
- it only reacts to app-owned tags/fields or creates operator tasks/notifications

## Completion Rule

This inventory is complete only when every workflow touching AI-managed contacts has a row and an explicit disposition.
