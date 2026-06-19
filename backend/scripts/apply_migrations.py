#!/usr/bin/env python3
"""Apply PostgreSQL migrations with the psql command-line client."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from dpf_backend.config import load_settings


def migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection URL. Defaults to DPF_DATABASE_URL.",
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "db" / "migrations",
        help="Directory containing *.sql migrations.",
    )
    args = parser.parse_args()

    psql = shutil.which("psql")
    if psql is None:
        print("psql not found. Install postgresql-client.", file=sys.stderr)
        return 2

    database_url = args.database_url or load_settings().database_url
    files = migration_files(args.migrations_dir)
    if not files:
        print(f"No migrations found in {args.migrations_dir}", file=sys.stderr)
        return 2

    for path in files:
        print(f"Applying {path.name}")
        result = subprocess.run(
            [psql, database_url, "-v", "ON_ERROR_STOP=1", "-f", str(path)],
            check=False,
        )
        if result.returncode != 0:
            return result.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
