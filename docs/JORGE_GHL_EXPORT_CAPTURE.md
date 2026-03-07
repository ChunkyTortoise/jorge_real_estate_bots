# Jorge GHL Export Capture Guide

Use this guide during the live GHL validation pass to capture the minimum data
needed for repo-backed validation.

If you already have live `GHL_API_KEY` and `GHL_LOCATION_ID`, you can skip the
manual tag/custom-field export and fetch those directly:

```bash
python3 scripts/validate_ghl_contract.py \
  --ghl-api-key "$GHL_API_KEY" \
  --location-id "$GHL_LOCATION_ID" \
  --workflows-json path/to/workflows.json \
  --output docs/ghl_contract_validation_report.md
```

Only the workflow inventory still requires a manual or UI-backed capture.

## Goal

Produce three JSON files that can be validated by:

```bash
python3 scripts/validate_ghl_contract.py \
  --tags-json path/to/tags.json \
  --fields-json path/to/custom_fields.json \
  --workflows-json path/to/workflows.json \
  --output docs/ghl_contract_validation_report.md
```

## Required Capture Files

### Tags Export

Create a JSON file containing either:

- a simple array of tag names, or
- an array of objects with a `name` or `label` field

Example:

```json
["Jorge-Active", "seller-qualified", "seller_hot"]
```

### Custom Fields Export

Create a JSON file containing either:

- a simple array of field labels/names, or
- an array of objects with a `name`, `label`, or `displayName` field

Example:

```json
{
  "fields": [
    {"label": "ai_mode"},
    {"label": "ai_status"}
  ]
}
```

### Workflows Export

Create a JSON file with one object per workflow touching AI-managed contacts.

Required properties per workflow row:

- `name`
- `trigger`
- `sends_messages`
- `writes_tags`
- `writes_fields`
- `moves_pipeline`
- `routing_logic`
- `conflict_risk`
- `disposition`
- `notes`

Example:

```json
{
  "workflows": [
    {
      "name": "Inbound Relay",
      "trigger": "Inbound SMS received",
      "sends_messages": false,
      "writes_tags": false,
      "writes_fields": false,
      "moves_pipeline": false,
      "routing_logic": false,
      "conflict_risk": false,
      "disposition": "keep",
      "notes": "Relays inbound payload to the app only."
    }
  ]
}
```

## Review Rules

- Any workflow with `routing_logic = true` must not be kept.
- Any workflow with `conflict_risk = true` must be `rewrite`, `disable`, or `remove`.
- `Jorge-Active` must be the only manual suppression control.
- Extra tags or fields are allowed only if they do not participate in routing or handoff control.

## Output Artifacts

After running the validator, attach the generated report to:

- [JORGE_GHL_WORKFLOW_INVENTORY.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_GHL_WORKFLOW_INVENTORY.md)
- [JORGE_PRODUCTION_HANDOFF_SIGNOFF.md](/Users/cave/Projects/jorge-real-estate-bots/docs/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md)

## Optional Sync Tool

If you want a repo-generated plan for creating the missing canonical tags and
fields before editing GHL manually, run:

```bash
python3 scripts/sync_ghl_contract.py \
  --ghl-api-key "$GHL_API_KEY" \
  --location-id "$GHL_LOCATION_ID"
```

This is dry-run by default. Use `--apply` only when you are ready to mutate the
live GHL account.
