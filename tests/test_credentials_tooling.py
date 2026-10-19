#!/usr/bin/env python3
"""Tests for public Credentials setup and cross-platform orchestration."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
JASZCZURHAL = REPO_ROOT.parent / "JaszczurHAL"


def load_builder(credentials: Path = REPO_ROOT / "Credentials"):
    spec = importlib.util.spec_from_file_location(
        "credentials_builder", credentials / "scripts" / "build.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


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
    def test_windows_compiler_paths_survive_cmake_serialization(self) -> None:
        # CMake writes these values into quoted set() calls in its compiler
        # metadata. Exercise its parser even when this test runs on Linux.
        class WindowsToolchainPath(PureWindowsPath):
            def is_file(self) -> bool:
                return self.name.endswith(".exe")

        builder = load_builder()
        cmake = shutil.which("cmake")
        self.assertIsNotNone(cmake, "CMake is required for the path regression test")
        tools = {
            "CMAKE_C_COMPILER": "gcc",
            "CMAKE_CXX_COMPILER": "g++",
            "CMAKE_AR": "ar",
            "CMAKE_RANLIB": "ranlib",
        }
        cases = (
            (r"C:\jh\tools\gnu-arm\bin", "C:/jh/tools/gnu-arm/bin"),
            (r"C:\Program Files\GNU Arm\bin", "C:/Program Files/GNU Arm/bin"),
            (r"\\build-server\toolchains\GNU Arm\bin", "//build-server/toolchains/GNU Arm/bin"),
        )
        for native, expected in cases:
            with self.subTest(path=native), tempfile.TemporaryDirectory() as temporary:
                with patch.object(
                    builder, "resolve_arm_bin", return_value=WindowsToolchainPath(native)
                ), patch.object(sys, "path", sys.path.copy()):
                    definitions, _ = builder.target_toolchain(
                        SimpleNamespace(target="stm32g474"), {}, JASZCZURHAL
                    )
                values = dict(argument[2:].split("=", 1) for argument in definitions)
                root = Path(temporary)
                script = root / "compiler-paths.cmake"
                script.write_text(
                    "cmake_minimum_required(VERSION 3.20)\n"
                    'file(WRITE "${CMAKE_CURRENT_LIST_DIR}/paths.txt" "")\n'
                    + "".join(
                        f'set({name} "{values[name]}")\n'
                        f'file(APPEND "${{CMAKE_CURRENT_LIST_DIR}}/paths.txt" "${{{name}}}\\n")\n'
                        for name in tools
                    ),
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [cmake, "-P", str(script)], check=False, capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(
                    (root / "paths.txt").read_text(encoding="utf-8").splitlines(),
                    [f"{expected}/arm-none-eabi-{tool}.exe" for tool in tools.values()],
                )

    def test_managed_toolchain_precedes_inherited_path_for_every_rp_and_stm32_target(self) -> None:
        builder = load_builder()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Exercise equivalent paths on every host. Windows TEMP may also
            # use an 8.3 name that resolve() expands to its long form.
            alias_parent = root / "path alias"
            alias_parent.mkdir()
            _, state_file = template_with_managed_tools(alias_parent / "..")
            state = json.loads(state_file.read_text(encoding="utf-8"))
            inherited_path = str(root / "other tools")
            with patch.dict(os.environ, {"PATH": inherited_path, "CREDENTIALS_TEST_ENV": "kept"}):
                before = dict(os.environ)
                for target in ("rp2040", "rp2350-arm", "rp2350-riscv", "stm32g474"):
                    with self.subTest(target=target), patch.object(sys, "path", sys.path.copy()):
                        key = "riscv" if target == "rp2350-riscv" else "gnu-arm"
                        toolchain = Path(state["tools"][key]).parent
                        _, environment = builder.target_toolchain(
                            SimpleNamespace(target=target, toolchain_bin=toolchain),
                            state,
                            JASZCZURHAL,
                        )
                        self.assertIsNotNone(environment)
                        self.assertEqual(
                            environment["PATH"],
                            os.pathsep.join((str(toolchain.resolve()), inherited_path)),
                        )
                        self.assertEqual(environment["CREDENTIALS_TEST_ENV"], "kept")
                        self.assertEqual(dict(os.environ), before)

    def test_stm32_build_finds_managed_compiler_in_nested_cmake_checks(self) -> None:
        builder = load_builder()
        state = builder.load_host_environment(REPO_ROOT / "Credentials", None)
        tools = state.get("tools", {})
        cmake = builder.resolve_program("CMake", None, tools.get("cmake"), ("cmake",))
        ninja = builder.resolve_program("Ninja", None, tools.get("ninja"), ("ninja",))
        arm = builder.resolve_arm_bin(
            SimpleNamespace(target="stm32g474", toolchain_bin=None), state
        )
        compiler = arm / ("arm-none-eabi-gcc.exe" if os.name == "nt" else "arm-none-eabi-gcc")
        with tempfile.TemporaryDirectory(prefix="credentials managed build ") as temporary:
            root = Path(temporary)
            credentials = root / "Credentials"
            shutil.copytree(REPO_ROOT / "Credentials", credentials)
            configured = run_python(credentials / "scripts" / "configure.py", "--test")
            self.assertEqual(configured.returncode, 0, configured.stderr)
            state_file = root / "host-environment.json"
            state_file.write_text(
                json.dumps({"tools": {
                    "cmake": str(cmake), "ninja": str(ninja), "gnu-arm": str(compiler),
                }}),
                encoding="utf-8",
            )
            builder = load_builder(credentials)
            real_run = subprocess.run
            results = []

            def run_isolated(command, **kwargs):
                if "-S" in command:
                    # CMake also searches /usr/bin without PATH. Disable that
                    # fallback in the main configure AND its try_compile child.
                    command = [
                        *command,
                        "-DCMAKE_FIND_USE_CMAKE_SYSTEM_PATH=OFF",
                        "-DCMAKE_TRY_COMPILE_PLATFORM_VARIABLES=CMAKE_FIND_USE_CMAKE_SYSTEM_PATH",
                    ]
                result = real_run(command, capture_output=True, text=True, **kwargs)
                results.append(result)
                return result

            empty_path = root / "empty path"
            empty_path.mkdir()
            argv = [
                str(credentials / "scripts" / "build.py"), "stm32g474",
                "--host-environment", str(state_file), "--jaszczurhal-root", str(JASZCZURHAL),
            ]
            with patch.dict(os.environ, {
                "PATH": str(empty_path), "CMAKE_PROGRAM_PATH": "", "CMAKE_PREFIX_PATH": "",
            }), \
                    patch.object(sys, "argv", argv), patch.object(sys, "path", sys.path.copy()), \
                    patch.object(builder.subprocess, "run", side_effect=run_isolated):
                # Exercise an empty build directory and a subsequent cached build.
                for attempt in ("fresh", "incremental"):
                    results.clear()
                    result = builder.main()
                    output = "\n".join(r.stdout + r.stderr for r in results)
                    self.assertEqual(result, 0, f"{attempt} build:\n{output}")
                    self.assertEqual(len(results), 2)
            archive = credentials / "build" / "stm32g474" / "libCredentials.a"
            self.assertGreater(archive.stat().st_size, 0)

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
            self.assertIn(f"-DCMAKE_MAKE_PROGRAM={(root / 'ninja.exe').resolve().as_posix()}", joined)
            self.assertIn("-DPICO_PLATFORM=rp2040", joined)
            self.assertIn(f"-DPICO_TOOLCHAIN_PATH={(root / 'GNU Arm bin').resolve().as_posix()}", joined)
            self.assertIn(f"-DCREDENTIALS_JASZCZURHAL_ROOT={JASZCZURHAL.resolve().as_posix()}", joined)
            self.assertEqual(
                str(credentials.resolve() / "build" / "rp2040" / "libCredentials.a"),
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
                "rp2350-arm": ["-DPICO_PLATFORM=rp2350-arm-s", f"-DPICO_TOOLCHAIN_PATH={arm.as_posix()}"],
                "rp2350-riscv": ["-DPICO_PLATFORM=rp2350-riscv", f"-DPICO_TOOLCHAIN_PATH={riscv.as_posix()}"],
                "stm32g474": [
                    "-DCMAKE_TOOLCHAIN_FILE="
                    f"{(hal / 'link_libraries' / 'stm32_lib' / 'toolchain_stm32g474.cmake').as_posix()}",
                    f"-DCMAKE_C_COMPILER={(arm / 'arm-none-eabi-gcc.exe').as_posix()}",
                    f"-DCMAKE_CXX_COMPILER={(arm / 'arm-none-eabi-g++.exe').as_posix()}",
                    f"-DCMAKE_AR={(arm / 'arm-none-eabi-ar.exe').as_posix()}",
                    f"-DCMAKE_RANLIB={(arm / 'arm-none-eabi-ranlib.exe').as_posix()}",
                ],
                "esp32": [
                    f"-DCMAKE_TOOLCHAIN_FILE={(idf / 'toolchain-esp32.cmake').as_posix()}",
                    "-DCREDENTIALS_IDF_TARGET=esp32",
                ],
                "esp32s3": [
                    f"-DCMAKE_TOOLCHAIN_FILE={(idf / 'toolchain-esp32s3.cmake').as_posix()}",
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
