from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NativeDocumentRegionTests(unittest.TestCase):
    def test_region_module_is_callable_against_current_profile(self) -> None:
        language_root = Path(os.environ.get("MNCS_LANGUAGE_ROOT", ROOT.parent / "mncs-language"))
        binary = Path(os.environ.get("MNCS_BINARY", language_root / "target/debug/mncs"))
        if not binary.is_file():
            self.skipTest("mncs-language compiler binary is not available")
        environment = {
            **os.environ,
            "MNCS_LIBRARY_PATH": os.environ.get(
                "MNCS_LIBRARY_PATH", str(language_root / "library")
            ),
        }
        result = subprocess.run(
            [str(binary), "abi", str(ROOT / "native/mncs/doc/region.mncs")],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        document = json.loads(result.stdout)
        self.assertEqual(document["module"], "mncs.doc.region")
        self.assertIn("classify", document["functions"])
        self.assertEqual(
            document["functions"]["classify"]["outputs"][0]["record"]["name"],
            "RegionDecision",
        )


if __name__ == "__main__":
    unittest.main()
