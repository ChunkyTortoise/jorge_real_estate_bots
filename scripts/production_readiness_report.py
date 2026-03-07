#!/usr/bin/env python3
"""Check deployed Jorge endpoints and emit a markdown readiness report.

This does not verify live GHL workflows or tags directly. It verifies the public
app/operator surface so the remaining live checklist items can be recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


CANONICAL_FIELDS = [
    "mode",
    "status",
    "handoff_reason",
    "message_suppression_reason",
    "next_recommended_action",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


def fetch_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def try_fetch_json(url: str, headers: dict[str, str] | None = None) -> tuple[CheckResult, Any | None]:
    try:
        status, body = fetch_json(url, headers=headers)
        return CheckResult(url, 200 <= status < 300, f"HTTP {status}: {json.dumps(body)[:300]}"), body
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        return CheckResult(url, False, f"HTTP {exc.code}: {body[:300]}"), None
    except Exception as exc:
        return CheckResult(url, False, str(exc)), None


def canonical_field_check(name: str, payload: Any) -> CheckResult:
    missing = [field for field in CANONICAL_FIELDS if field not in payload]
    return CheckResult(name, not missing, "missing: " + ", ".join(missing) if missing else "all canonical fields present")


def status_field_check(name: str, payload: Any, expected: str = "healthy") -> CheckResult:
    actual = payload.get("status") if isinstance(payload, dict) else None
    return CheckResult(name, actual == expected, f"status={actual!r}, expected={expected!r}")


def field_equals_check(name: str, payload: Any, field: str, expected: str) -> CheckResult:
    actual = payload.get(field) if isinstance(payload, dict) else None
    return CheckResult(name, actual == expected, f"{field}={actual!r}, expected={expected!r}")


def build_headers(admin_key: str | None) -> dict[str, str]:
    if not admin_key:
        return {}
    return {"X-Admin-Key": admin_key}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("JORGE_LIVE_URL", "https://jorge-realty-ai-xxdf.onrender.com"))
    parser.add_argument("--admin-key", default=os.getenv("ADMIN_API_KEY"))
    parser.add_argument("--contact-id", default=os.getenv("JORGE_CONTACT_ID"))
    parser.add_argument("--output", help="Optional markdown report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/")
    headers = build_headers(args.admin_key)

    checks: list[CheckResult] = []

    health_result, health_payload = try_fetch_json(f"{base}/health")
    checks.append(CheckResult("GET /health", health_result.ok, health_result.details))
    if health_result.ok and isinstance(health_payload, dict):
        checks.append(status_field_check("GET /health status", health_payload, expected="healthy"))
        checks.append(field_equals_check("GET /health environment", health_payload, field="environment", expected="production"))

    agg_result, agg_payload = try_fetch_json(f"{base}/health/aggregate")
    checks.append(CheckResult("GET /health/aggregate", agg_result.ok, agg_result.details))
    if agg_result.ok and isinstance(agg_payload, dict):
        checks.append(status_field_check("GET /health/aggregate status", agg_payload, expected="healthy"))

    if args.admin_key:
        admin_settings_result, _admin_settings_payload = try_fetch_json(f"{base}/admin/settings", headers=headers)
        checks.append(CheckResult("GET /admin/settings", admin_settings_result.ok, admin_settings_result.details))

        leads_summary_result, _leads_summary_payload = try_fetch_json(f"{base}/api/dashboard/leads/summary", headers=headers)
        checks.append(CheckResult("GET /api/dashboard/leads/summary", leads_summary_result.ok, leads_summary_result.details))

        leads_result, _leads_payload = try_fetch_json(f"{base}/api/dashboard/leads", headers=headers)
        checks.append(CheckResult("GET /api/dashboard/leads", leads_result.ok, leads_result.details))

        if args.contact_id:
            for path, label in [
                (f"/admin/conversations/{urllib.parse.quote(args.contact_id)}", "GET /admin/conversations/{contact_id}"),
                (f"/api/dashboard/leads/{urllib.parse.quote(args.contact_id)}", "GET /api/dashboard/leads/{contact_id}"),
                (f"/api/dashboard/conversations/{urllib.parse.quote(args.contact_id)}", "GET /api/dashboard/conversations/{contact_id}"),
            ]:
                result, payload = try_fetch_json(f"{base}{path}", headers=headers)
                checks.append(CheckResult(label, result.ok, result.details))
                if result.ok:
                    if isinstance(payload, dict):
                        checks.append(canonical_field_check(f"{label} canonical fields", payload))
                    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
                        checks.append(canonical_field_check(f"{label} canonical fields", payload[0]))
    else:
        checks.append(CheckResult("Admin/dashboard checks", False, "ADMIN_API_KEY not provided; skipped authenticated checks"))

    ok = all(check.ok for check in checks)

    lines = [
        "# Jorge Production Readiness Report",
        "",
        f"- Base URL: `{base}`",
        f"- Contact ID: `{args.contact_id or '(none provided)'}`",
        f"- Overall result: `{'pass' if ok else 'review required'}`",
        "",
        "| Check | Result | Details |",
        "|---|---|---|",
    ]
    for check in checks:
        lines.append(f"| {check.name} | {'PASS' if check.ok else 'FAIL'} | {check.details.replace('|', '\\|')} |")
    report = "\n".join(lines) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(report)
    else:
        sys.stdout.write(report)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
