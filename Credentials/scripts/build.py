#!/usr/bin/env python3
"""Build the Credentials archive with a native cross-platform CMake workflow."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("rp2040", "stm32g474"))
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--cmake", type=Path)
    parser.add_argument("--ninja", type=Path)
    parser.add_argument("--toolchain-bin", type=Path)
    parser.add_argument("--host-environment", type=Path)
    parser.add_argument("--jaszczurhal-root", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved commands as JSON without executing them.",
    )
    return parser.parse_args()


def load_host_environment(root_dir: Path, explicit: Path | None) -> dict[str, Any]:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    if os.environ.get("JH_HOST_ENVIRONMENT"):
        candidates.append(Path(os.environ["JH_HOST_ENVIRONMENT"]))
    candidates.extend(
        (
            root_dir.parent / "JaszczurHAL" / ".build" / "windows" / "host-environment.json",
            root_dir.parent.parent
            / "libraries"
            / "JaszczurHAL"
            / ".build"
            / "windows"
            / "host-environment.json",
        )
    )

    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if path.is_file():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    return {}


def resolve_program(
    label: str,
    explicit: Path | None,
    state_value: str | None,
    path_names: tuple[str, ...],
) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    if state_value:
        candidates.append(Path(state_value))
    for name in path_names:
        discovered = shutil.which(name)
        if discovered:
            candidates.append(Path(discovered))

    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if path.is_file():
            return path
    raise RuntimeError(f"{label} executable was not found")


def resolve_toolchain_bin(args: argparse.Namespace, state: dict[str, Any]) -> Path:
    environment_name = (
        "RP2040_TOOLCHAIN_BIN" if args.target == "rp2040" else "STM32_TOOLCHAIN_BIN"
    )
    candidates: list[Path] = []
    if args.toolchain_bin is not None:
        candidates.append(args.toolchain_bin)
    if os.environ.get(environment_name):
        candidates.append(Path(os.environ[environment_name]))
    if os.environ.get("CREDENTIALS_TOOLCHAIN_BIN"):
        candidates.append(Path(os.environ["CREDENTIALS_TOOLCHAIN_BIN"]))
    managed_compiler = state.get("tools", {}).get("gnu-arm")
    if managed_compiler:
        candidates.append(Path(managed_compiler).parent)
    for name in ("arm-none-eabi-gcc", "arm-none-eabi-gcc.exe"):
        compiler = shutil.which(name)
        if compiler:
            candidates.append(Path(compiler).parent)

    compiler_names = ("arm-none-eabi-gcc.exe", "arm-none-eabi-gcc")
    for candidate in candidates:
        directory = candidate.expanduser().resolve()
        if any((directory / name).is_file() for name in compiler_names):
            return directory
    raise RuntimeError(f"ARM toolchain was not found for {args.target}")


def resolve_jaszczurhal_root(root_dir: Path, explicit: Path | None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    candidates.extend(
        (
            root_dir.parent / "JaszczurHAL",
            root_dir.parent.parent / "libraries" / "JaszczurHAL",
        )
    )

    for candidate in candidates:
        directory = candidate.expanduser().resolve()
        if (directory / "src" / "hal" / "core" / "hal_array.h").is_file():
            return directory
    raise RuntimeError(
        "JaszczurHAL source tree was not found; install Credentials next to "
        "JaszczurHAL or pass --jaszczurhal-root"
    )


def main() -> int:
    args = parse_args()
    root_dir = Path(__file__).resolve().parent.parent
    state = load_host_environment(root_dir, args.host_environment)
    tools = state.get("tools", {})

    try:
        cmake = resolve_program(
            "CMake",
            args.cmake,
            tools.get("cmake"),
            ("cmake", "cmake.exe"),
        )
        ninja = resolve_program(
            "Ninja",
            args.ninja,
            tools.get("ninja"),
            ("ninja", "ninja.exe"),
        )
        toolchain_bin = resolve_toolchain_bin(args, state)
        jaszczurhal_root = resolve_jaszczurhal_root(
            root_dir, args.jaszczurhal_root
        )
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    build_dir = (
        args.build_dir.expanduser().resolve()
        if args.build_dir is not None
        else root_dir / "build" / args.target
    )
    configure_command = [
        str(cmake),
        "-S",
        str(root_dir),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_TOOLCHAIN_FILE={root_dir / 'cmake' / 'arm-none-eabi-toolchain.cmake'}",
        f"-DCREDENTIALS_TOOLCHAIN_BIN={toolchain_bin}",
        f"-DCREDENTIALS_TARGET={args.target}",
        f"-DCREDENTIALS_JASZCZURHAL_ROOT={jaszczurhal_root}",
    ]
    build_command = [
        str(cmake),
        "--build",
        str(build_dir),
        "--target",
        "Credentials",
    ]

    if args.dry_run:
        print(
            json.dumps(
                {
                    "configure": configure_command,
                    "build": build_command,
                    "target": args.target,
                },
                indent=2,
            )
        )
        return 0

    for command in (configure_command, build_command):
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode

    archive = (
        root_dir / "src" / "cortex-m0plus" / "libCredentials.a"
        if args.target == "rp2040"
        else root_dir / "build" / "stm32g474" / "libCredentials.a"
    )
    if not archive.is_file():
        print(f"error: expected archive was not generated: {archive}", file=sys.stderr)
        return 2
    print(f"Built {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
