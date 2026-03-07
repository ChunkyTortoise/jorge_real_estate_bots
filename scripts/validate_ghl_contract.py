#!/usr/bin/env python3
"""Validate manually exported GHL tags, custom fields, and workflows."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REQUIRED_TAGS = [
    "Jorge-Active",
    "needs-bilingual",
    "needs-human-review",
    "seller-qualified",
    "buyer-qualified",
    "seller_hot",
    "seller_warm",
    "seller_cold",
    "buyer_hot",
    "buyer_warm",
    "buyer_cold",
    "lead_hot",
    "lead_warm",
    "lead_cold",
]

REQUIRED_FIELDS = [
    "ai_mode",
    "ai_status",
    "ai_temperature",
    "ai_last_summary",
    "ai_last_handoff_reason",
    "ai_last_response_at",
    "property_condition",
    "price_expectation",
    "selling_motivation",
    "buyer_preferences",
    "pre_approval_status",
    "buyer_timeline",
]

ARRAY_KEYS = ("items", "data", "results", "workflows", "tags", "fields", "customFields")
NAME_KEYS = ("name", "label", "displayName", "title", "value")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tags-json", help="Path to exported tags JSON")
    parser.add_argument("--fields-json", help="Path to exported custom fields JSON")
    parser.add_argument("--workflows-json", help="Path to exported workflows JSON")
    parser.add_argument("--ghl-api-key", help="Optional live GHL API key for read-only tag/field fetch")
    parser.add_argument("--location-id", help="Location ID for live GHL fetch")
    parser.add_argument("--output", help="Optional markdown report output path")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    return parser.parse_args()


def load_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fetch_live_json(url: str, api_key: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Version": "2021-07-28",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.7.1",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_array(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ARRAY_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def extract_names(items: list[Any]) -> list[str]:
    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            names.append(item)
            continue
        if isinstance(item, dict):
            for key in NAME_KEYS:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    names.append(value.strip())
                    break
    return names


def extract_field_identifiers(items: list[Any]) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                values.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        for key in ("name", "label", "displayName", "title", "value"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        field_key = item.get("fieldKey")
        if isinstance(field_key, str) and field_key.strip():
            normalized = field_key.strip()
            values.append(normalized)
            if normalized.startswith("contact."):
                values.append(normalized.split(".", 1)[1])
    return values


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "true", "1"}:
            return True
        if lowered in {"no", "false", "0"}:
            return False
    if isinstance(value, int):
        return bool(value)
    return None


def pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def normalize_workflow(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"name": item, "trigger": "", "sends_messages": None, "writes_tags": None, "writes_fields": None, "moves_pipeline": None, "routing_logic": None, "conflict_risk": None, "disposition": "", "notes": ""}
    if not isinstance(item, dict):
        return {"name": repr(item), "trigger": "", "sends_messages": None, "writes_tags": None, "writes_fields": None, "moves_pipeline": None, "routing_logic": None, "conflict_risk": None, "disposition": "", "notes": ""}
    return {
        "name": pick(item, "name", "title", "workflowName") or "UNKNOWN",
        "trigger": pick(item, "trigger", "enrollmentTrigger", "when") or "",
        "sends_messages": as_bool(pick(item, "sends_messages", "sendsMessages")),
        "writes_tags": as_bool(pick(item, "writes_tags", "writesTags")),
        "writes_fields": as_bool(pick(item, "writes_fields", "writesFields")),
        "moves_pipeline": as_bool(pick(item, "moves_pipeline", "movesPipeline")),
        "routing_logic": as_bool(pick(item, "routing_logic", "routingLogic", "contains_routing_logic", "containsRoutingLogic")),
        "conflict_risk": as_bool(pick(item, "conflict_risk", "conflictRisk")),
        "disposition": item.get("disposition") or "",
        "notes": item.get("notes") or "",
    }


def missing_required(required: list[str], actual: list[str]) -> list[str]:
    actual_set = {value.strip() for value in actual}
    return [item for item in required if item not in actual_set]


def normalize_tag(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def missing_required_tags(required: list[str], actual: list[str]) -> list[str]:
    actual_set = {normalize_tag(value) for value in actual}
    return [item for item in required if normalize_tag(item) not in actual_set]


def extra_entries(required: list[str], actual: list[str]) -> list[str]:
    required_set = set(required)
    return sorted({value.strip() for value in actual if value.strip() and value.strip() not in required_set})


def validate_workflows(workflows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    for workflow in workflows:
        name = workflow["name"]
        disposition = workflow["disposition"] or "UNSPECIFIED"
        sends_messages = workflow["sends_messages"]
        routing_logic = workflow["routing_logic"]
        conflict_risk = workflow["conflict_risk"]

        if disposition == "UNSPECIFIED":
            warnings.append(f"{name}: missing disposition")
        if sends_messages is None:
            warnings.append(f"{name}: sends_messages not specified")
        if routing_logic is None:
            warnings.append(f"{name}: routing_logic not specified")
        if conflict_risk is None:
            warnings.append(f"{name}: conflict_risk not specified")

        if routing_logic is True and disposition not in {"rewrite", "disable", "remove"}:
            blockers.append(f"{name}: routing logic present but disposition is {disposition}")
        if conflict_risk is True and disposition not in {"rewrite", "disable", "remove"}:
            blockers.append(f"{name}: marked conflict risk but disposition is {disposition}")
    return blockers, warnings


def fmt_bool(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "?"


def summarize(values: list[str], limit: int = 20) -> str:
    if not values:
        return "None"
    if len(values) <= limit:
        return ", ".join(values)
    head = ", ".join(values[:limit])
    return f"{head}, ... ({len(values)} total)"


def render_markdown(
    tags_missing: list[str],
    tags_extra: list[str],
    fields_missing: list[str],
    fields_extra: list[str],
    workflow_blockers: list[str],
    workflow_warnings: list[str],
    workflows: list[dict[str, Any]],
) -> str:
    ok = not tags_missing and not fields_missing and not workflow_blockers
    lines = [
        "# Jorge GHL Contract Validation Report",
        "",
        f"- Overall result: `{'pass' if ok else 'review required'}`",
        "",
        "## Tags",
        "",
        f"- Missing required tags: {summarize(tags_missing)}",
        f"- Extra live tags in export: {summarize(tags_extra)}",
        "",
        "## Custom Fields",
        "",
        f"- Missing required fields: {summarize(fields_missing)}",
        f"- Extra live fields in export: {summarize(fields_extra)}",
        "",
        "## Workflow Review",
        "",
        f"- Blockers: {', '.join(workflow_blockers) if workflow_blockers else 'None'}",
        f"- Warnings: {', '.join(workflow_warnings) if workflow_warnings else 'None'}",
        "",
        "| Workflow | Trigger | Sends Messages | Writes Tags | Writes Fields | Moves Pipeline | Routing Logic | Conflict Risk | Disposition | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for workflow in workflows:
        lines.append(
            "| {name} | {trigger} | {sends} | {tags} | {fields} | {pipeline} | {routing} | {risk} | {disposition} | {notes} |".format(
                name=str(workflow["name"]).replace("|", "\\|"),
                trigger=str(workflow["trigger"]).replace("|", "\\|"),
                sends=fmt_bool(workflow["sends_messages"]),
                tags=fmt_bool(workflow["writes_tags"]),
                fields=fmt_bool(workflow["writes_fields"]),
                pipeline=fmt_bool(workflow["moves_pipeline"]),
                routing=fmt_bool(workflow["routing_logic"]),
                risk=fmt_bool(workflow["conflict_risk"]),
                disposition=str(workflow["disposition"] or "").replace("|", "\\|"),
                notes=str(workflow["notes"] or "").replace("|", "\\|"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    tags_payload = load_json(args.tags_json)
    fields_payload = load_json(args.fields_json)
    if args.ghl_api_key and args.location_id:
        tags_payload = fetch_live_json(
            f"https://services.leadconnectorhq.com/locations/{args.location_id}/tags",
            args.ghl_api_key,
        )
        fields_payload = fetch_live_json(
            f"https://services.leadconnectorhq.com/locations/{args.location_id}/customFields?model=contact",
            args.ghl_api_key,
        )

    tags = extract_names(extract_array(tags_payload))
    fields = extract_field_identifiers(extract_array(fields_payload))
    workflows = [normalize_workflow(item) for item in extract_array(load_json(args.workflows_json))]

    tags_missing = missing_required_tags(REQUIRED_TAGS, tags)
    tags_extra = extra_entries(REQUIRED_TAGS, tags)
    fields_missing = missing_required(REQUIRED_FIELDS, fields)
    fields_extra = extra_entries(REQUIRED_FIELDS, fields)
    workflow_blockers, workflow_warnings = validate_workflows(workflows)

    payload = {
        "ok": not tags_missing and not fields_missing and not workflow_blockers,
        "missing_tags": tags_missing,
        "extra_tags": tags_extra,
        "missing_fields": fields_missing,
        "extra_fields": fields_extra,
        "workflow_blockers": workflow_blockers,
        "workflow_warnings": workflow_warnings,
        "workflows": workflows,
    }

    output = json.dumps(payload, indent=2) + "\n" if args.json else render_markdown(
        tags_missing,
        tags_extra,
        fields_missing,
        fields_extra,
        workflow_blockers,
        workflow_warnings,
        workflows,
    )

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
