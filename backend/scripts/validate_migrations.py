#!/usr/bin/env python3
"""Validate the migration files without requiring a database server."""

from __future__ import annotations

from pathlib import Path
import re
import sys


REQUIRED_TABLES = {
    "schema_migrations",
    "raw_mqtt",
    "boot_sessions",
    "telemetry_data",
    "actuator_events",
    "status_events",
}

EXPECTED_MIGRATIONS = ("001_initial_schema.sql", "002_telemetry_windows.sql")


def main() -> int:
    migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("No migration files found", file=sys.stderr)
        return 1

    names = [path.name for path in files]
    if names != sorted(names):
        print("Migration files are not sorted", file=sys.stderr)
        return 1
    for expected in EXPECTED_MIGRATIONS:
        if expected not in names:
            print(f"Missing migration file: {expected}", file=sys.stderr)
            return 1

    first = files[0].read_text(encoding="utf-8")
    missing = [
        table
        for table in REQUIRED_TABLES
        if not re.search(rf"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\b", first, re.I)
    ]
    if missing:
        print(f"Missing required tables: {', '.join(missing)}", file=sys.stderr)
        return 1

    if "INSERT INTO schema_migrations" not in first:
        print("Migration does not record itself in schema_migrations", file=sys.stderr)
        return 1

    second = (migrations_dir / "002_telemetry_windows.sql").read_text(encoding="utf-8")
    if "CREATE TABLE IF NOT EXISTS telemetry_windows" not in second:
        print("Migration 002 does not create telemetry_windows", file=sys.stderr)
        return 1
    if "002_telemetry_windows" not in second:
        print("Migration 002 does not record itself", file=sys.stderr)
        return 1

    print(f"Validated {len(files)} migration file(s): {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
