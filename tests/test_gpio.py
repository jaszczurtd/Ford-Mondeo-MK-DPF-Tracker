"""Verify assembly pull/polarity in the production sensor initialization and ISRs."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from host_probe import ROOT, compile_probe, generate_hardware, run  # noqa: E402


@unittest.skipUnless(sys.platform.startswith("linux"), "GPIO host probe uses GCC/Clang and ELF section GC")
class GpioTests(unittest.TestCase):
    def run_command(self, result):
        code, output = result
        self.assertEqual(0, code, output)

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
                    self.run_command(generate_hardware(build, assembly))
                    binary = build / "gpio"
                    self.run_command(compile_probe(build, [ROOT / "tests/test_gpio.cpp"], binary))
                    self.run_command(run([str(binary)]))


if __name__ == "__main__":
    unittest.main()
