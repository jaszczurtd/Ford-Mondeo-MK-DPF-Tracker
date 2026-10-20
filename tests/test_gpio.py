"""Verify assembly pull/polarity in the production sensor initialization and ISRs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HAL = ROOT.parent / "JaszczurHAL"
sys.path.insert(0, str(HAL / "scripts"))

import component_manager  # noqa: E402


@unittest.skipUnless(sys.platform.startswith("linux"), "GPIO host probe uses GCC/Clang and ELF section GC")
class GpioTests(unittest.TestCase):
    def run_command(self, command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_sensor_levels_and_interrupts(self):
        original = json.loads((ROOT / "device_tree.json").read_text())
        for assembly in original["assemblies"]:
            for alternate in (False, True):
                with self.subTest(assembly=assembly, alternate=alternate), tempfile.TemporaryDirectory() as temp:
                    build = Path(temp) / ".build"
                    build.mkdir()
                    tree = json.loads(json.dumps(original))
                    if alternate:
                        tree["nodes"]["pumpPulse"]["properties"] = {"pull": "down", "activeLow": False}
                        tree["nodes"]["glowPlug"]["properties"] = {"pull": "none", "activeLow": False}
                    (build / "device_tree.json").write_text(json.dumps(tree))
                    (build / "hal_project_config.h").write_text((ROOT / "hal_project_config.h").read_text())
                    generator = [sys.executable, str(HAL / "scripts/generate_hardware_config.py")]
                    common = ["--config-dir", str(build), "--output-root", str(build), "--output-dir", str(build)]
                    self.run_command([*generator, "resolve", *common, "--assembly", assembly])
                    self.run_command([*generator, "finalize", *common,
                                      "--hardware", str(build / "jh_hardware_resolved.json"),
                                      "--hardware-header", str(build / "jh_hardware.h")])
                    binary = build / "gpio"
                    self.run_command([os.environ.get("CXX", "c++"), "-std=c++17", "-O2", "-flto",
                                      "-Wall", "-Wextra", "-Werror", "-ffunction-sections", "-fdata-sections",
                                      "-DHAL_TARGET_MOCK=1", "-I", str(build), "-I", str(ROOT),
                                      "-I", str(ROOT / "Credentials/src"), "-I", str(HAL / "src"),
                                      "-I", str(component_manager.jhbase_root(HAL) / "include"),
                                      "-I", str(HAL / "third_party/cJSON"),
                                      "-include", str(build / "jh_hardware.h"),
                                      str(ROOT / "tests/test_gpio.cpp"), "-Wl,--gc-sections", "-o", str(binary)])
                    self.run_command([str(binary)])


if __name__ == "__main__":
    unittest.main()
