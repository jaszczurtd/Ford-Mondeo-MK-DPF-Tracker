#!/usr/bin/env python3
"""Install the public Credentials template without overwriting private data."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=project_dir.parent / "libraries" / "Credentials",
        help="Credentials destination (default: ../libraries/Credentials).",
    )
    parser.add_argument(
        "--test-config",
        action="store_true",
        help="Install reserved, non-secret test configuration for CI.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(__file__).resolve().parent.parent
    source_dir = project_dir / "Credentials"
    destination = args.destination.expanduser().resolve()

    if destination.exists():
        print(
            f"error: refusing to overwrite existing Credentials: {destination}",
            file=sys.stderr,
        )
        print("The current private library remains untouched.", file=sys.stderr)
        return 2

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, destination)

    command = [sys.executable, str(destination / "scripts" / "configure.py")]
    if args.test_config:
        command.append("--test")
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        print(
            f"error: Credentials configuration failed with exit code "
            f"{completed.returncode}; the new template remains at {destination}",
            file=sys.stderr,
        )
        return completed.returncode

    print(f"Installed Credentials template at {destination}")
    print(f"See {destination / 'README.md'} before building it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
