#!/usr/bin/env python3
"""Create missing canonical Jorge GHL tags and custom fields.

Default mode is dry-run. Use --apply to perform live mutations.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from validate_ghl_contract import REQUIRED_FIELDS, REQUIRED_TAGS, extract_array


@dataclass(frozen=True)
class FieldSpec:
    name: str
    data_type: str
    placeholder: str = ""


CANONICAL_FIELD_SPECS = [
    FieldSpec("ai_mode", "TEXT"),
    FieldSpec("ai_status", "TEXT"),
    FieldSpec("ai_temperature", "TEXT"),
    FieldSpec("ai_last_summary", "LARGE_TEXT"),
    FieldSpec("ai_last_handoff_reason", "TEXT"),
    FieldSpec("ai_last_response_at", "TEXT"),
    FieldSpec("property_condition", "TEXT"),
    FieldSpec("price_expectation", "TEXT"),
    FieldSpec("selling_motivation", "TEXT"),
    FieldSpec("buyer_preferences", "LARGE_TEXT"),
    FieldSpec("pre_approval_status", "TEXT"),
    FieldSpec("buyer_timeline", "TEXT"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghl-api-key", required=True, help="Live GHL API key")
    parser.add_argument("--location-id", required=True, help="Live GHL location ID")
    parser.add_argument("--apply", action="store_true", help="Apply live mutations instead of dry-run")
    parser.add_argument("--output", help="Optional markdown plan/report output path")
    return parser.parse_args()


def make_request(url: str, api_key: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Version": "2021-07-28",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.7.1",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def existing_tags(payload: Any) -> set[str]:
    tags: set[str] = set()
    for item in extract_array(payload):
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                tags.add(name.strip())
        elif isinstance(item, str) and item.strip():
            tags.add(item.strip())
    return tags


def existing_fields(payload: Any) -> set[str]:
    fields: set[str] = set()
    for item in extract_array(payload):
        if not isinstance(item, dict):
            continue
        for key in ("name", "label", "displayName"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                fields.add(value.strip())
        field_key = item.get("fieldKey")
        if isinstance(field_key, str) and field_key.strip():
            normalized = field_key.strip()
            if normalized.startswith("contact."):
                normalized = normalized.split(".", 1)[1]
            fields.add(normalized)
    return fields


def create_tag(api_key: str, location_id: str, tag: str) -> Any:
    return make_request(
        f"https://services.leadconnectorhq.com/locations/{location_id}/tags",
        api_key,
        method="POST",
        payload={"name": tag},
    )


def create_field(api_key: str, location_id: str, field: FieldSpec, position: int) -> Any:
    payload = {
        "name": field.name,
        "fieldKey": field.name,
        "dataType": field.data_type,
        "placeholder": field.placeholder,
        "position": position,
        "model": "contact",
    }
    return make_request(
        f"https://services.leadconnectorhq.com/locations/{location_id}/customFields",
        api_key,
        method="POST",
        payload=payload,
    )


def render_markdown(
    location_id: str,
    apply: bool,
    missing_tags: list[str],
    missing_fields: list[FieldSpec],
    created_tags: list[str],
    created_fields: list[str],
    errors: list[str],
) -> str:
    lines = [
        "# Jorge GHL Contract Sync Report",
        "",
        f"- Location ID: `{location_id}`",
        f"- Mode: `{'apply' if apply else 'dry-run'}`",
        "",
        "## Planned Missing Tags",
        "",
    ]
    if missing_tags:
        lines.extend([f"- `{tag}`" for tag in missing_tags])
    else:
        lines.append("- None")
    lines.extend(["", "## Planned Missing Custom Fields", ""])
    if missing_fields:
        lines.extend([f"- `{field.name}` ({field.data_type})" for field in missing_fields])
    else:
        lines.append("- None")
    lines.extend(["", "## Created During This Run", ""])
    lines.append(f"- Tags: {', '.join(created_tags) if created_tags else 'None'}")
    lines.append(f"- Fields: {', '.join(created_fields) if created_fields else 'None'}")
    lines.extend(["", "## Errors", ""])
    if errors:
        lines.extend([f"- {error}" for error in errors])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    tags_payload = make_request(
        f"https://services.leadconnectorhq.com/locations/{args.location_id}/tags",
        args.ghl_api_key,
    )
    fields_payload = make_request(
        f"https://services.leadconnectorhq.com/locations/{args.location_id}/customFields?model=contact",
        args.ghl_api_key,
    )

    current_tags = existing_tags(tags_payload)
    current_fields = existing_fields(fields_payload)
    missing_tags = [tag for tag in REQUIRED_TAGS if tag not in current_tags]
    missing_fields = [field for field in CANONICAL_FIELD_SPECS if field.name not in current_fields]

    created_tags: list[str] = []
    created_fields: list[str] = []
    errors: list[str] = []

    if args.apply:
        for tag in missing_tags:
            try:
                create_tag(args.ghl_api_key, args.location_id, tag)
                created_tags.append(tag)
            except Exception as exc:
                errors.append(f"tag {tag}: {exc}")
        for index, field in enumerate(missing_fields, start=1000):
            try:
                create_field(args.ghl_api_key, args.location_id, field, position=index)
                created_fields.append(field.name)
            except Exception as exc:
                errors.append(f"field {field.name}: {exc}")

    report = render_markdown(
        location_id=args.location_id,
        apply=args.apply,
        missing_tags=missing_tags,
        missing_fields=missing_fields,
        created_tags=created_tags,
        created_fields=created_fields,
        errors=errors,
    )

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    if args.apply:
        return 0 if not errors else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
