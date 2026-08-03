#!/usr/bin/env python3
"""Tests for public Credentials setup and cross-platform orchestration."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class CredentialsToolingTests(unittest.TestCase):
    def test_configure_test_creates_only_public_fixture_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credentials = Path(temporary) / "Credentials"
            shutil.copytree(REPO_ROOT / "Credentials", credentials)

            result = run_python(credentials / "scripts" / "configure.py", "--test")

            self.assertEqual(result.returncode, 0, result.stderr)
            data = (credentials / "config" / "CredentialsData.local.h").read_text(
                encoding="utf-8"
            )
            mapping = (credentials / "config" / "MacHostMapping.local.cpp").read_text(
                encoding="utf-8"
            )
            self.assertIn("CREDENTIALS_LOCAL_CONFIGURED 1", data)
            self.assertIn("example.invalid", data)
            self.assertIn("02:00:00:00:00:01", mapping)
            self.assertNotIn("YOUR_", data + mapping)

    def test_configure_never_replaces_existing_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credentials = Path(temporary) / "Credentials"
            shutil.copytree(REPO_ROOT / "Credentials", credentials)
            local = credentials / "config" / "CredentialsData.local.h"
            local.write_text("private sentinel\n", encoding="utf-8")

            normal = run_python(credentials / "scripts" / "configure.py")
            test = run_python(credentials / "scripts" / "configure.py", "--test")

            self.assertEqual(normal.returncode, 0, normal.stderr)
            self.assertEqual(test.returncode, 2)
            self.assertEqual(local.read_text(encoding="utf-8"), "private sentinel\n")

    def test_setup_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "Credentials"
            destination.mkdir()
            sentinel = destination / "private.txt"
            sentinel.write_text("do not replace\n", encoding="utf-8")

            result = run_python(
                REPO_ROOT / "scripts" / "setup_credentials.py",
                "--destination",
                str(destination),
                "--test-config",
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not replace\n")
            self.assertIn("refusing to overwrite", result.stderr)

    def test_setup_installs_non_secret_ci_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "Credentials"

            result = run_python(
                REPO_ROOT / "scripts" / "setup_credentials.py",
                "--destination",
                str(destination),
                "--test-config",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = (destination / "config" / "CredentialsData.local.h").read_text(
                encoding="utf-8"
            )
            self.assertIn("CREDENTIALS_LOCAL_CONFIGURED 1", data)

    def test_build_dry_run_uses_managed_windows_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "GNU Arm bin"
            bin_dir.mkdir()
            for name in (
                "arm-none-eabi-gcc.exe",
                "arm-none-eabi-g++.exe",
                "arm-none-eabi-ar.exe",
                "arm-none-eabi-ranlib.exe",
            ):
                (bin_dir / name).touch()
            cmake = root / "cmake.exe"
            ninja = root / "ninja.exe"
            cmake.touch()
            ninja.touch()
            state = root / "host-environment.json"
            state.write_text(
                json.dumps(
                    {
                        "tools": {
                            "cmake": str(cmake),
                            "ninja": str(ninja),
                            "gnu-arm": str(bin_dir / "arm-none-eabi-gcc.exe"),
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = run_python(
                REPO_ROOT / "Credentials" / "scripts" / "build.py",
                "rp2040",
                "--host-environment",
                str(state),
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            command = json.loads(result.stdout)
            joined = " ".join(command["configure"])
            self.assertIn(str(cmake.resolve()), command["configure"][0])
            self.assertIn(f"-DCMAKE_MAKE_PROGRAM={ninja.resolve()}", joined)
            self.assertIn(f"-DCREDENTIALS_TOOLCHAIN_BIN={bin_dir.resolve()}", joined)

    def test_toolchain_discovers_windows_executable_names(self) -> None:
        toolchain = (
            REPO_ROOT / "Credentials" / "cmake" / "arm-none-eabi-toolchain.cmake"
        ).read_text(encoding="utf-8")
        self.assertIn("find_program", toolchain)
        for name in (
            "arm-none-eabi-gcc.exe",
            "arm-none-eabi-g++.exe",
            "arm-none-eabi-ar.exe",
            "arm-none-eabi-ranlib.exe",
        ):
            self.assertIn(name, toolchain)


if __name__ == "__main__":
    unittest.main()
