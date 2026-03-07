#!/usr/bin/env python3
"""
Scan GHL contacts for non-empty 'Bot Type' custom field.
Output: docs/bot_type_scan_report.json
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

LOCATION_ID = os.getenv("GHL_LOCATION_ID", "3xt4qayAh35BlDLaUv7P")
GHL_API_KEY = os.getenv("GHL_API_KEY", "")
BASE_URL = "https://services.leadconnectorhq.com"
HEADERS = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version": "2021-07-28",
    "Accept": "application/json",
}


async def scan():
    contacts_with_bot_type = []
    total = 0
    skip = 0
    limit = 100

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                f"{BASE_URL}/contacts/",
                headers=HEADERS,
                params={"locationId": LOCATION_ID, "limit": limit, "skip": skip},
            )
            resp.raise_for_status()
            data = resp.json()
            contacts = data.get("contacts", [])
            if not contacts:
                break
            total += len(contacts)
            for c in contacts:
                for field in c.get("customFields", []) or []:
                    key = (field.get("key") or field.get("id") or "").lower()
                    val = field.get("value") or field.get("fieldValue") or ""
                    if "bot_type" in key or "bot type" in key:
                        if val:
                            contacts_with_bot_type.append({
                                "contact_id": c.get("id"),
                                "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                                "field_key": key,
                                "value": val,
                            })
            if len(contacts) < limit:
                break
            skip += limit

    report = {
        "total_contacts_scanned": total,
        "contacts_with_bot_type": contacts_with_bot_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out = Path("docs/bot_type_scan_report.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"Scanned {total} contacts. Found {len(contacts_with_bot_type)} with Bot Type. Report: {out}")


if __name__ == "__main__":
    asyncio.run(scan())
