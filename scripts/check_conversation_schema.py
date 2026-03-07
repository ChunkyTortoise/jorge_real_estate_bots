#!/usr/bin/env python3
"""Verify canonical conversation columns in a live database.

Usage:
  DATABASE_URL=... python scripts/check_conversation_schema.py
  python scripts/check_conversation_schema.py --database-url postgresql+psycopg://...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable

from sqlalchemy.engine import make_url
from sqlalchemy import create_engine, inspect, text


REQUIRED_COLUMNS = [
    "mode",
    "mode_version",
    "status",
    "handoff_reason",
    "human_takeover",
    "bilingual_required",
    "message_suppression_reason",
    "qualification_summary",
    "next_recommended_action",
    "crm_sync_status",
    "last_inbound_at",
    "last_outbound_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--table", default="conversations")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return parser.parse_args()


def to_sync_database_url(database_url: str) -> str:
    """Normalize async SQLAlchemy URLs to sync drivers for inspection."""
    url = make_url(database_url)
    drivername = url.drivername
    if "+" not in drivername:
        return database_url

    backend, _driver = drivername.split("+", 1)
    if backend == "sqlite":
        sync_driver = "sqlite"
    elif backend == "postgresql":
        sync_driver = "postgresql+psycopg"
    else:
        sync_driver = backend
    return str(url.set(drivername=sync_driver))


def diff_columns(actual: Iterable[str]) -> tuple[list[str], list[str]]:
    actual_set = set(actual)
    missing = [name for name in REQUIRED_COLUMNS if name not in actual_set]
    present = [name for name in REQUIRED_COLUMNS if name in actual_set]
    return present, missing


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("DATABASE_URL is required via --database-url or env", file=sys.stderr)
        return 2

    sync_url = to_sync_database_url(args.database_url)
    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        if args.table not in table_names:
            result = {
                "ok": False,
                "table": args.table,
                "error": f"table '{args.table}' not found",
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"FAIL: {result['error']}")
            return 1

        columns = [col["name"] for col in inspector.get_columns(args.table)]
        present, missing = diff_columns(columns)

        alembic_version = None
        if "alembic_version" in table_names:
            with engine.connect() as conn:
                row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
                alembic_version = row[0] if row else None

        result = {
            "ok": not missing,
            "table": args.table,
            "database_url_driver": make_url(args.database_url).drivername,
            "inspection_driver": make_url(sync_url).drivername,
            "alembic_version": alembic_version,
            "required_columns_present": present,
            "required_columns_missing": missing,
            "all_columns": columns,
        }

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Table: {args.table}")
            print(f"Alembic version: {alembic_version or 'unknown'}")
            print(f"Present: {', '.join(present) if present else '(none)'}")
            if missing:
                print(f"Missing: {', '.join(missing)}")
            else:
                print("Missing: none")
        return 0 if result["ok"] else 1
    except Exception as exc:
        result = {
            "ok": False,
            "table": args.table,
            "database_url_driver": make_url(args.database_url).drivername,
            "inspection_driver": make_url(sync_url).drivername,
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"FAIL: {exc}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
