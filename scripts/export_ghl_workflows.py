#!/usr/bin/env python3
"""Export live GHL workflows into validator-friendly JSON and markdown."""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghl-api-key", required=True, help="Live GHL API key")
    parser.add_argument("--location-id", required=True, help="GHL location ID")
    parser.add_argument("--json-output", help="Path for workflow JSON export")
    parser.add_argument("--md-output", help="Path for markdown summary")
    return parser.parse_args()


def fetch_json(url: str, api_key: str) -> Any:
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


def normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


ROUTING_TERMS = (
    "which bot",
    "bot change",
    "bot trigger",
    "bot",
    "seller",
    "buyer",
    "lead",
    "ai off",
    "ai on",
    "unknown inbound",
    "catch unknown",
    "process message",
)

MESSAGE_TERMS = (
    "sms",
    "text",
    "outbound",
    "inbound",
    "reply",
    "follow up",
    "follow-up",
    "drip",
    "reminder",
    "sequence",
    "campaign",
)

TAG_TERMS = ("tag", "tags", "activation", "qualified", "mia", "status")
FIELD_TERMS = ("field", "fields", "bot type", "buyer/seller", "assistant is", "temperature")
PIPELINE_TERMS = ("pipeline", "opportunity", "escrow", "dispo", "assign", "appointment booked")


def guess_flags(name: str) -> dict[str, Any]:
    lowered = normalize(name)
    sends_messages = any(term in lowered for term in MESSAGE_TERMS)
    writes_tags = any(term in lowered for term in TAG_TERMS)
    writes_fields = any(term in lowered for term in FIELD_TERMS)
    moves_pipeline = any(term in lowered for term in PIPELINE_TERMS)
    routing_logic = any(term in lowered for term in ROUTING_TERMS)
    conflict_risk = routing_logic or ("ai off" in lowered) or ("which bot" in lowered) or ("unknown inbound" in lowered)
    disposition = "rewrite" if routing_logic or conflict_risk else "keep"
    notes_bits: list[str] = ["Auto-generated from workflow name only."]
    if routing_logic:
        notes_bits.append("Name suggests routing or bot-selection behavior.")
    if sends_messages:
        notes_bits.append("Name suggests message sending or campaign behavior.")
    if writes_fields:
        notes_bits.append("Name suggests custom-field mutation.")
    if writes_tags:
        notes_bits.append("Name suggests tag mutation.")
    if moves_pipeline:
        notes_bits.append("Name suggests pipeline/opportunity mutation.")
    return {
        "sends_messages": sends_messages,
        "writes_tags": writes_tags,
        "writes_fields": writes_fields,
        "moves_pipeline": moves_pipeline,
        "routing_logic": routing_logic,
        "conflict_risk": conflict_risk,
        "disposition": disposition,
        "notes": " ".join(notes_bits),
    }


def make_workflow_rows(payload: Any) -> list[dict[str, Any]]:
    items = []
    if isinstance(payload, dict):
        items = payload.get("workflows", [])
    if not isinstance(items, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "UNKNOWN")
        flags = guess_flags(name)
        rows.append(
            {
                "id": item.get("id", ""),
                "name": name,
                "status": item.get("status", ""),
                "trigger": "UNKNOWN - inspect in GHL UI",
                **flags,
            }
        )
    return rows


def render_markdown(rows: list[dict[str, Any]], location_id: str) -> str:
    lines = [
        "# Jorge GHL Workflow Export",
        "",
        f"- Location ID: `{location_id}`",
        f"- Workflow count: `{len(rows)}`",
        "",
        "> This file is auto-generated from the live workflow list endpoint only.",
        "> Trigger/actions still require manual confirmation in the GHL UI.",
        "",
        "| ID | Workflow Name | Status | Sends Messages | Writes Tags | Writes Fields | Moves Pipeline | Routing Logic | Conflict Risk | Suggested Disposition | Notes |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {name} | {status} | {sends} | {tags} | {fields} | {pipeline} | {routing} | {risk} | {disp} | {notes} |".format(
                id=str(row["id"]).replace("|", "\\|"),
                name=str(row["name"]).replace("|", "\\|"),
                status=str(row["status"]).replace("|", "\\|"),
                sends="yes" if row["sends_messages"] else "no",
                tags="yes" if row["writes_tags"] else "no",
                fields="yes" if row["writes_fields"] else "no",
                pipeline="yes" if row["moves_pipeline"] else "no",
                routing="yes" if row["routing_logic"] else "no",
                risk="yes" if row["conflict_risk"] else "no",
                disp=str(row["disposition"]).replace("|", "\\|"),
                notes=str(row["notes"]).replace("|", "\\|"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = fetch_json(
        f"https://services.leadconnectorhq.com/workflows/?locationId={args.location_id}",
        args.ghl_api_key,
    )
    rows = make_workflow_rows(payload)
    validator_payload = {"workflows": rows}

    if args.json_output:
        Path(args.json_output).write_text(json.dumps(validator_payload, indent=2) + "\n", encoding="utf-8")
    if args.md_output:
        Path(args.md_output).write_text(render_markdown(rows, args.location_id), encoding="utf-8")
    if not args.json_output and not args.md_output:
        print(json.dumps(validator_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
