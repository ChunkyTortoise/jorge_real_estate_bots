#!/usr/bin/env python3
"""Review extra live GHL tags and fields for likely routing/handoff risk."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_ghl_contract import (
    REQUIRED_FIELDS,
    REQUIRED_TAGS,
    extract_array,
    extract_field_identifiers,
    extract_names,
    extra_entries,
    fetch_live_json,
    missing_required,
    missing_required_tags,
)

HIGH_RISK_KEYWORDS = (
    "bot",
    "route",
    "routing",
    "which bot",
    "ai off",
    "ai-on",
    "ai off",
    "ai-off",
    "active",
    "handoff",
    "human",
    "bilingual",
    "manual",
    "suppress",
    "suppression",
    "trigger",
    "workflow",
    "seller",
    "buyer",
    "lead",
    "bot type",
)

MEDIUM_RISK_KEYWORDS = (
    "qualified",
    "qualification",
    "temperature",
    "hot",
    "warm",
    "cold",
    "follow-up",
    "follow up",
    "appointment",
    "calendar",
    "pre approval",
    "timeline",
    "condition",
    "price",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghl-api-key", required=True, help="Live GHL API key")
    parser.add_argument("--location-id", required=True, help="GHL location ID")
    parser.add_argument("--output", help="Optional markdown output path")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    return parser.parse_args()


def normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def classify(values: list[str]) -> dict[str, list[str]]:
    buckets = {
        "high_risk_review": [],
        "medium_risk_review": [],
        "likely_harmless": [],
    }
    for value in values:
        lowered = normalize(value)
        if any(keyword in lowered for keyword in HIGH_RISK_KEYWORDS):
            buckets["high_risk_review"].append(value)
        elif any(keyword in lowered for keyword in MEDIUM_RISK_KEYWORDS):
            buckets["medium_risk_review"].append(value)
        else:
            buckets["likely_harmless"].append(value)
    for key in buckets:
        buckets[key] = sorted(set(buckets[key]))
    return buckets


def summarize(values: list[str], limit: int = 40) -> str:
    if not values:
        return "None"
    if len(values) <= limit:
        return ", ".join(values)
    return f"{', '.join(values[:limit])}, ... ({len(values)} total)"


def render_markdown(payload: dict[str, object]) -> str:
    tags = payload["tags"]
    fields = payload["fields"]
    lines = [
        "# Jorge GHL Legacy Contract Review",
        "",
        f"- Location ID: `{payload['location_id']}`",
        f"- Required tags missing: {summarize(payload['missing_tags'])}",
        f"- Required fields missing: {summarize(payload['missing_fields'])}",
        f"- Extra live tags count: `{len(payload['extra_tags'])}`",
        f"- Extra live fields count: `{len(payload['extra_fields'])}`",
        "",
        "## Tag Review",
        "",
        f"- High-risk review candidates: {summarize(tags['high_risk_review'])}",
        f"- Medium-risk review candidates: {summarize(tags['medium_risk_review'])}",
        f"- Likely harmless or business-only: {summarize(tags['likely_harmless'])}",
        "",
        "## Field Review",
        "",
        f"- High-risk review candidates: {summarize(fields['high_risk_review'])}",
        f"- Medium-risk review candidates: {summarize(fields['medium_risk_review'])}",
        f"- Likely harmless or business-only: {summarize(fields['likely_harmless'])}",
        "",
        "## Review Guidance",
        "",
        "- Treat every high-risk item as a manual audit candidate before handoff.",
        "- Any legacy tag or field that influences routing, suppression, or workflow branching must be retired or explicitly accepted.",
        "- Any legacy item that only serves reporting may remain if it does not create a parallel operator control path.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
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

    missing_tags = missing_required_tags(REQUIRED_TAGS, tags)
    missing_fields = missing_required(REQUIRED_FIELDS, fields)
    extra_tags = extra_entries(REQUIRED_TAGS, tags)
    extra_fields = extra_entries(REQUIRED_FIELDS, fields)

    payload = {
        "location_id": args.location_id,
        "missing_tags": missing_tags,
        "missing_fields": missing_fields,
        "extra_tags": extra_tags,
        "extra_fields": extra_fields,
        "tags": classify(extra_tags),
        "fields": classify(extra_fields),
    }

    output = json.dumps(payload, indent=2) + "\n" if args.json else render_markdown(payload)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if not missing_tags and not missing_fields else 1


if __name__ == "__main__":
    raise SystemExit(main())
