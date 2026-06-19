#!/usr/bin/env python3
"""Run simple function-based backend tests without external test dependencies."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import traceback


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    tests_dir = repo_root / "backend" / "tests"
    sys.path.insert(0, str(repo_root / "backend" / "src"))

    total = 0
    failed = 0
    for path in sorted(tests_dir.glob("test_*.py")):
        module = load_module(path)
        for name in sorted(dir(module)):
            if not name.startswith("test_"):
                continue
            test_func = getattr(module, name)
            if not callable(test_func):
                continue
            total += 1
            try:
                test_func()
            except Exception:  # noqa: BLE001 - this is a tiny test runner
                failed += 1
                print(f"FAIL {path.name}::{name}")
                traceback.print_exc()

    passed = total - failed
    print(f"Backend tests: {passed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
