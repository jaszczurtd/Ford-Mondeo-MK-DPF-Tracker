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
JASZCZURHAL = REPO_ROOT.parent / "libraries" / "JaszczurHAL"


def run_python(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def template_with_managed_tools(root: Path) -> tuple[Path, Path]:
    """A template copy and a Windows host record naming managed GNU Arm and
    RISC-V compilers, CMake and Ninja that exist only as empty files."""
    credentials = root / "Credentials"
    shutil.copytree(REPO_ROOT / "Credentials", credentials)
    compilers = {}
    for directory, prefix in (
        (root / "GNU Arm bin", "arm-none-eabi"),
        (root / "RISC-V" / "bin", "riscv32-unknown-elf"),
    ):
        directory.mkdir(parents=True)
        for tool in ("gcc", "g++", "ar", "ranlib"):
            (directory / f"{prefix}-{tool}.exe").touch()
        compilers[prefix] = str(directory / f"{prefix}-gcc.exe")
    for name in ("cmake.exe", "ninja.exe"):
        (root / name).touch()
    state = root / "host-environment.json"
    state.write_text(
        json.dumps(
            {
                "tools": {
                    "cmake": str(root / "cmake.exe"),
                    "ninja": str(root / "ninja.exe"),
                    "gnu-arm": compilers["arm-none-eabi"],
                    "riscv": compilers["riscv32-unknown-elf"],
                }
            }
        ),
        encoding="utf-8",
    )
    return credentials, state


def dry_run(credentials: Path, state: Path, target: str) -> subprocess.CompletedProcess[str]:
    return run_python(
        credentials / "scripts" / "build.py",
        target,
        "--host-environment",
        str(state),
        "--jaszczurhal-root",
        str(JASZCZURHAL),
        "--dry-run",
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
            credentials, state = template_with_managed_tools(root)

            result = dry_run(credentials, state, "rp2040")

            self.assertEqual(result.returncode, 0, result.stderr)
            command = json.loads(result.stdout)
            joined = " ".join(command["configure"])
            self.assertIn(str((root / "cmake.exe").resolve()), command["configure"][0])
            self.assertIn(f"-DCMAKE_MAKE_PROGRAM={(root / 'ninja.exe').resolve()}", joined)
            self.assertIn("-DPICO_PLATFORM=rp2040", joined)
            self.assertIn(f"-DPICO_TOOLCHAIN_PATH={(root / 'GNU Arm bin').resolve()}", joined)
            self.assertIn(f"-DCREDENTIALS_JASZCZURHAL_ROOT={JASZCZURHAL.resolve()}", joined)
            self.assertEqual(
                str(credentials.resolve() / "src" / "cortex-m0plus" / "libCredentials.a"),
                command["archive"],
            )

    def test_each_target_builds_with_its_firmware_toolchain(self) -> None:
        # The toolchain of the JaszczurHAL firmware build of each target, so
        # the archive has the firmware's ABI.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            credentials, state = template_with_managed_tools(root)
            arm = (root / "GNU Arm bin").resolve()
            riscv = (root / "RISC-V" / "bin").resolve()
            hal = JASZCZURHAL.resolve()
            idf = hal / "third_party" / "esp-idf" / "tools" / "cmake"
            expected = {
                "rp2350-arm": ["-DPICO_PLATFORM=rp2350-arm-s", f"-DPICO_TOOLCHAIN_PATH={arm}"],
                "rp2350-riscv": ["-DPICO_PLATFORM=rp2350-riscv", f"-DPICO_TOOLCHAIN_PATH={riscv}"],
                "stm32g474": [
                    "-DCMAKE_TOOLCHAIN_FILE="
                    f"{hal / 'link_libraries' / 'stm32_lib' / 'toolchain_stm32g474.cmake'}",
                    f"-DCMAKE_C_COMPILER={arm / 'arm-none-eabi-gcc.exe'}",
                    f"-DCMAKE_CXX_COMPILER={arm / 'arm-none-eabi-g++.exe'}",
                    f"-DCMAKE_AR={arm / 'arm-none-eabi-ar.exe'}",
                    f"-DCMAKE_RANLIB={arm / 'arm-none-eabi-ranlib.exe'}",
                ],
                "esp32": [
                    f"-DCMAKE_TOOLCHAIN_FILE={idf / 'toolchain-esp32.cmake'}",
                    "-DCREDENTIALS_IDF_TARGET=esp32",
                ],
                "esp32s3": [
                    f"-DCMAKE_TOOLCHAIN_FILE={idf / 'toolchain-esp32s3.cmake'}",
                    "-DCREDENTIALS_IDF_TARGET=esp32s3",
                ],
            }
            for target, definitions in expected.items():
                with self.subTest(target=target):
                    result = dry_run(credentials, state, target)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    command = json.loads(result.stdout)
                    for definition in definitions:
                        self.assertIn(definition, command["configure"])
                    self.assertEqual(
                        str(credentials.resolve() / "build" / target / "libCredentials.a"),
                        command["archive"],
                    )

    def test_unknown_target_lists_the_known_ones(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credentials, state = template_with_managed_tools(Path(temporary))

            result = dry_run(credentials, state, "mock")

            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown target 'mock'", result.stderr)
            self.assertIn("rp2350-arm", result.stderr)

if __name__ == "__main__":
    unittest.main()
