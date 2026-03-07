# Jorge GHL Workflow Inventory

> **STATUS: CRITICAL WORKFLOWS ANALYZED — name-based classification complete, GHL UI trigger/action confirmation still required.**
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

---

## Critical Workflow Analysis — Name-Based Classification (2026-03-07)

The following table covers the highest-risk published workflows identified from the export. Dispositions are based on name analysis and code-confirmed app behavior. Actual trigger/action details still require GHL UI confirmation before these dispositions are final.

### Tier 1 — Must confirm in GHL UI before live messaging

| ID | Workflow Name | Status | Why Critical | Required Disposition | GHL UI Confirmed? |
|---|---|---|---|---|---|
| `11c4943e` | `5. Process Message - Which Bot?` | published | Name explicitly describes bot routing. If it routes to bots independently of the app, it bypasses the app's canonical mode detection. | **Audit required** — If it calls `POST /api/ghl/webhook` or `/ghl/webhook/new-lead`, it may be the relay that triggers the app (keep). If it routes without calling the app, it must be rewritten to call the app exclusively. | No |
| `be1b2b2d` | `Jorge AI Bot - Inbound Message Handler` | published | Sends messages AND has routing logic. Could be sending AI-path messages via GHL native AI instead of the app. | **Audit required** — If it sends an AI-generated GHL message directly (not via the app), it causes double-send. If it's an HTTP action calling the app webhook, keep as relay. | No |
| `d43d02f5` | `2. AI OFF/ON Tag Added -> AI Assistant is:` | published | Writes tags + fields + routing logic. App reads `Bot Type` field (key `bot_type`). If this workflow writes `Bot Type`, it can redirect routing. | **Audit required** — Confirm it writes only `AI Assistant is:` (GHL native AI toggle), NOT `Bot Type`. If it writes `Bot Type`, rewrite to remove that action. | No |
| `7ebafcd6` | `6. Catch Unknown Inbound SMS` | published | Sends messages to unknown inbound SMS. If it fires before the app's webhook, or on any contact the app is handling, it creates unsolicited double-sends. | **Audit required** — Must confirm its trigger excludes Jorge-handled contacts. If it doesn't, disable or add Jorge-Active exclusion. | No |
| `da046656` | `New Inbound Lead` | published | Sends messages AND routing logic. Same risk as #6 — fires on new leads before app processes them. | **Audit required** — Confirm it either is the app webhook relay (HTTP action → `/api/ghl/webhook`), OR excludes contacts where the app is active. | No |
| `64b82875` | `Jorge — Bot Activation` | published | Writes tags + routing logic. Could be writing tags that affect app state (e.g., `ai on`, `buyer bot`, or `Bot Type`). | **Audit required** — If it only sets a `Jorge-Active` remove tag or fires an HTTP webhook to the app, keep. If it writes conflicting tags, rewrite. | No |
| `b886a5e5` | `AI Bot - Jorge Qualification` | published | Routing logic present. Could be qualifying leads independently of the app. | **Audit required** — If it calls the app webhook with `bot_type=lead` or similar, keep as relay. If it independently routes to a bot, disable/rewrite. | No |
| `972d8000` | `Lead Intake Notification` | published | Routing logic present. Could be doing intake independently or routing to a non-app path. | **Audit required** — Confirm it is notification-only to the team, NOT an AI routing step. | No |

### Tier 2 — Jorge-prefixed workflows (likely notification-only, confirm in UI)

| ID | Workflow Name | Status | Analysis | Likely Disposition | GHL UI Confirmed? |
|---|---|---|---|---|---|
| `2c405e58` | `Jorge — Hot Buyer Alert` | published | Routing logic heuristic triggered. Name suggests alert/notification. Likely sends a notification to Jorge (the person) when a buyer is hot. | Probably `keep` if it only sends internal alerts and does NOT send messages to the contact. | No |
| `577d56c4` | `Jorge — Hot Seller Alert` | published | Same as above for sellers. | Probably `keep` if notification only. | No |
| `fbcef074` | `Jorge — Warm Buyer Nurture` | published | Routing logic present. Could send nurture messages to warm buyers independently of the app. | **Higher risk** — Confirm it does NOT send SMS/email to the buyer without app coordination. If it does, it can conflict with app-managed conversations. | No |
| `c8334775` | `Jorge — Warm Seller Nurture` | published | Same as warm buyer. | **Higher risk** — Same as above. | No |
| `9610d6fe` | `Jorge — Manual Scheduling Fallback` | published | No routing/messaging logic detected by name. | `keep` pending GHL UI confirmation. | No |
| `f3fc268b` | `Jorge — Agent Notification` | published | No routing/messaging logic detected by name. | `keep` — notification-only. | No |
| `046979ce` | `Qualified Lead Notify - Email` | published | Writes tags + routing logic. Fires when a lead qualifies. | **Audit required** — Confirm tags it writes don't conflict with app state. If it only notifies Jorge via email, keep. | No |
| `e3266d01` | `Qualified Lead Notify - SMS` | published | Sends messages + writes tags + routing logic. | **High risk** — If it sends an SMS to the qualified lead (not to Jorge internally), it conflicts with the app's own qualification response. Confirm recipient is operator, not contact. | No |

### Summary: Required GHL UI Actions Before Handoff

1. Open each Tier 1 workflow in the GHL UI and confirm the trigger + every action.
2. For any workflow confirmed to send messages to contacts (not operator notifications), verify it coordinates with the Jorge app (calls app webhook) rather than acting independently.
3. For `2. AI OFF/ON Tag Added`, confirm it does NOT write the `Bot Type` custom field.
4. For `5. Process Message - Which Bot?`, confirm it is a relay to the app webhook, not an independent bot selector.
5. Update this table with `Yes` in "GHL UI Confirmed?" and the confirmed action details once each is reviewed.

## Completion Rule

This inventory is complete only when every workflow touching AI-managed contacts has a row and an explicit disposition.
