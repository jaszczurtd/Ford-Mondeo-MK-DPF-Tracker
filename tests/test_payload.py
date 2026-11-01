"""Verify that the production JSON helper writes null for a missing number."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from host_probe import HAL, ROOT, compile_probe, generate_hardware, run  # noqa: E402


@unittest.skipUnless(sys.platform.startswith("linux"), "payload host probe uses GCC/Clang and ELF section GC")
class PayloadTests(unittest.TestCase):
    def run_command(self, result):
        code, output = result
        self.assertEqual(0, code, output)

    def test_non_finite_numbers_are_null(self):
        tree = json.loads((ROOT / "device_tree.json").read_text())
        assembly = next(iter(tree["assemblies"]))
        with tempfile.TemporaryDirectory() as temp:
            build = Path(temp) / ".build"
            build.mkdir()
            (build / "device_tree.json").write_text(json.dumps(tree))
            self.run_command(generate_hardware(build, assembly))
            cjson = build / "cJSON.o"
            self.run_command(run([os.environ.get("CC", "cc"), "-O2", "-c",
                                  str(HAL / "third_party/cJSON/cJSON.c"), "-o", str(cjson)]))
            binary = build / "payload"
            self.run_command(compile_probe(
                build, [ROOT / "tests/test_payload.cpp", HAL / "src/hal/core/hal_math.cpp"],
                binary, objects=[cjson]))
            self.run_command(run([str(binary)]))


if __name__ == "__main__":
    unittest.main()
