"""Build host probes that include the production tracker.cpp."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HAL = ROOT.parent / "JaszczurHAL"
sys.path.insert(0, str(HAL / "scripts"))

import component_manager  # noqa: E402


def run(command):
    """Run a command; return its exit code and its combined output."""
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout + result.stderr


def generate_hardware(build, assembly):
    """Write jh_hardware.h of @p assembly from build/device_tree.json and the
    project config into @p build."""
    (build / "hal_project_config.h").write_text((ROOT / "hal_project_config.h").read_text())
    generator = [sys.executable, str(HAL / "scripts/generate_hardware_config.py")]
    common = ["--config-dir", str(build), "--output-root", str(build), "--output-dir", str(build)]
    for command in ([*generator, "resolve", *common, "--assembly", assembly],
                    [*generator, "finalize", *common,
                     "--hardware", str(build / "jh_hardware_resolved.json"),
                     "--hardware-header", str(build / "jh_hardware.h")]):
        code, output = run(command)
        if code != 0:
            return code, output
    return 0, ""


def compile_probe(build, sources, binary, objects=()):
    """Compile C++ @p sources with the mock HAL headers of @p build."""
    return run([os.environ.get("CXX", "c++"), "-std=c++17", "-O2", "-flto",
                "-Wall", "-Wextra", "-Werror", "-ffunction-sections", "-fdata-sections",
                "-DHAL_TARGET_MOCK=1", "-I", str(build), "-I", str(ROOT),
                "-I", str(ROOT / "Credentials/src"), "-I", str(HAL / "src"),
                "-I", str(component_manager.jhbase_root(HAL) / "include"),
                "-I", str(HAL / "third_party/cJSON"),
                "-include", str(build / "jh_hardware.h"),
                *[str(source) for source in sources], *[str(o) for o in objects],
                "-Wl,--gc-sections", "-o", str(binary)])
