#!/usr/bin/env python3
"""Synchronize Ford Tracker VS Code files with JaszczurHAL generators."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JH_ROOT = REPO_ROOT.parent / "libraries" / "JaszczurHAL"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_text(value: Any, *, indent: int = 4) -> str:
    return json.dumps(value, indent=indent, ensure_ascii=False) + "\n"


def manifest_selection(manifest: dict[str, Any]) -> tuple[str, str, str | None]:
    """Target, board and assembly: with device_tree.json the assembly the
    manifest selects, else the manifest's target and board."""
    import device_tree_project

    if device_tree_project.device_tree_path(REPO_ROOT) is None:
        return str(manifest["target"]), str(manifest["board"]), None
    entry, _ = device_tree_project.choose(REPO_ROOT, None, manifest.get("assembly"))
    return entry["target"], entry["board"], entry["name"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated files differ.")
    parser.add_argument(
        "--jaszczurhal-root",
        type=Path,
        default=Path(os.environ.get("JASZCZURHAL_ROOT", DEFAULT_JH_ROOT)),
        help="JaszczurHAL checkout used as the generator source.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    jh_root = args.jaszczurhal_root.resolve()
    scripts_dir = jh_root / "scripts"
    if not scripts_dir.is_dir():
        print(f"error: JaszczurHAL scripts not found: {scripts_dir}", file=sys.stderr)
        return 1
    sys.path.insert(0, str(scripts_dir))

    from board_registry import tooling_target_registry
    from vscode_task_config import (
        apply_project_view_settings,
        assembly_debug_builds,
        assembly_launch_document,
        keybindings_reference,
        project_tasks_document,
        sync_cortex_debug_launch_document,
        vscode_entry_settings,
        write_text_lf,
    )

    vscode_dir = REPO_ROOT / ".vscode"
    manifest = load_json(vscode_dir / "jaszczurhal.project.json")
    settings = load_json(vscode_dir / "settings.json")
    identity = manifest.get("identity") if isinstance(manifest.get("identity"), dict) else {}
    target, board, assembly = manifest_selection(manifest)
    tasks = project_tasks_document(
        tooling_target_registry(jh_root),
        target,
        board,
        module=str(manifest["module"]),
        usb_product=str(identity.get("usbProduct") or ""),
        project_dir=REPO_ROOT,
        selected_assembly=assembly,
    )

    settings.pop("jaszczurhal.uploadPort", None)
    unix_entry = str(
        settings.get("jaszczurhal.vscodeEntry")
        or "../libraries/JaszczurHAL/vscode/entry/jh-vscode"
    )
    settings.update(vscode_entry_settings(unix_entry))
    # IntelliSense follows the database of Project: Refresh IntelliSense.
    apply_project_view_settings(
        settings,
        str(settings.get("C_Cpp.default.compileCommands")
            or "${workspaceFolder}/.build/compile_commands_patched.json"),
    )

    expected = {
        vscode_dir / "settings.json": json_text(settings),
        vscode_dir / "tasks.json": json_text(tasks, indent=2),
        vscode_dir / "keybindings.reference.json": json_text(keybindings_reference()),
    }
    if assembly is not None:
        # One debug profile per assembly, as sync-board-picker writes it.
        launch_path = vscode_dir / "launch.json"
        launch = load_json(launch_path) if launch_path.is_file() else {}
        sync_cortex_debug_launch_document(
            launch,
            assembly_launch_document(
                manifest,
                assembly_debug_builds(REPO_ROOT),
                workspace_dir=REPO_ROOT,
                jh_root=jh_root,
                default_assembly=assembly,
            ),
        )
        expected[launch_path] = json_text(launch)
    mismatches = [
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    if args.check:
        if mismatches:
            print("error: Ford Tracker VS Code files are out of date:", file=sys.stderr)
            for path in mismatches:
                print(f"  {path.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1
        print(f"Ford Tracker VS Code files are synchronized ({len(expected)} files).")
        return 0

    for path, content in expected.items():
        write_text_lf(path, content)
        print(f"generated {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
