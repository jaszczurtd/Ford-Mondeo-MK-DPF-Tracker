#!/usr/bin/env python3
"""Validate the generated cross-platform VS Code project contract."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANAGED_DEBUG_PROFILES = {
    "Project: Debug Firmware",
    "Project: Debug Firmware (RP2350 ARM)",
    "Project: Debug Firmware (STM32G474 / ST-Link)",
}


class VscodeProjectTests(unittest.TestCase):
    def test_generated_files_are_current(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "sync_vscode_project.py"),
                "--check",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tasks_have_unique_labels_and_windows_commands(self) -> None:
        document = json.loads(
            (REPO_ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8")
        )
        tasks = document["tasks"]
        labels = [task["label"] for task in tasks]
        self.assertEqual(len(labels), len(set(labels)))
        for task in tasks:
            self.assertIn("windows", task, task["label"])
            self.assertTrue(task["windows"].get("command"), task["label"])

    def test_tracked_settings_contain_no_machine_local_port(self) -> None:
        settings = json.loads(
            (REPO_ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("jaszczurhal.uploadPort", settings)
        self.assertEqual(
            settings["jaszczurhal.vscodeEntryWindows"],
            "../libraries/JaszczurHAL/vscode/entry/jh-vscode.cmd",
        )
        manifest = json.loads(
            (REPO_ROOT / ".vscode" / "jaszczurhal.project.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["identity"]["usbVid"], "0x2e8a")
        self.assertEqual(manifest["identity"]["usbPid"], "0x000a")

    def test_generated_json_contains_no_unix_host_paths(self) -> None:
        for name in ("settings.json", "tasks.json", "keybindings.reference.json"):
            content = (REPO_ROOT / ".vscode" / name).read_text(encoding="utf-8")
            for forbidden in ("/dev/", "/home/", ".arduino15"):
                self.assertNotIn(forbidden, content, name)

        launch = (REPO_ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8")
        self.assertNotIn("${config:cortex-debug.", launch)
        profiles = {
            profile["name"]: profile
            for profile in json.loads(launch)["configurations"]
        }
        self.assertEqual(set(profiles), MANAGED_DEBUG_PROFILES)
        self.assertEqual(
            profiles["Project: Debug Firmware (STM32G474 / ST-Link)"]["configFiles"],
            ["board/st_nucleo_g4.cfg"],
        )


if __name__ == "__main__":
    unittest.main()
