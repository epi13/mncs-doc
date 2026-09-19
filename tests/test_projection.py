import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import project  # noqa: E402


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "repository": {"repository": "fixture", "revision": 3},
            "language": {
                "current_profile": "0.18",
                "content_identity": "sha256:language",
                "compiler_inventory_identity": "sha256:inventory",
                "mode": "full",
            },
            "architecture": {
                "content_identity": "sha256:architecture",
                "mode": "full",
                "capabilities": [
                    {
                        "id": "zeta.capability",
                        "owner": "fixture",
                        "canonical": {"path": "src/zeta", "kind": "implementation"},
                    },
                    {
                        "id": "alpha.capability",
                        "owner": "fixture",
                        "canonical": {"path": "src/alpha", "kind": "implementation"},
                    },
                ],
            },
            "pressures": [
                {"id": "MNCS-LANG-2", "title": "Second", "status": "open"},
                {"id": "MNCS-LANG-1", "title": "First", "status": "discovered"},
            ],
            "completeness": {"state": "complete", "complete": True},
        }

    def test_readme_projection_preserves_human_prose_and_checks_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "context.json"
            readme = root / "README.md"
            context.write_text(json.dumps(self.context), encoding="utf-8")
            readme.write_text("# Human explanation\n\nKeep this paragraph.\n", encoding="utf-8")

            self.assertTrue(project.project_readme(readme, context))
            rendered = readme.read_text(encoding="utf-8")
            self.assertIn("Keep this paragraph.", rendered)
            self.assertIn("`alpha.capability`", rendered)
            self.assertTrue(project.project_readme(readme, context, check=True))

            readme.write_text(rendered.replace("sha256:language", "sha256:stale"), encoding="utf-8")
            self.assertFalse(project.project_readme(readme, context, check=True))

    def test_rfc_index_is_sorted_and_identity_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rfc_root = root / "rfcs"
            rfc_root.mkdir()
            (rfc_root / "0002-second.md").write_text(
                "# RFC 0002: Second\n\nStatus: Accepted\n", encoding="utf-8"
            )
            (rfc_root / "0001-first.md").write_text(
                "# RFC 0001: First\n\nStatus: Draft\nOwner: team\n", encoding="utf-8"
            )
            output = root / "docs" / "rfc-index.md"
            self.assertTrue(project.project_rfc_index(rfc_root, output))
            rendered = output.read_text(encoding="utf-8")
            self.assertLess(rendered.index("[0001]"), rendered.index("[0002]"))
            self.assertTrue(project.project_rfc_index(rfc_root, output, check=True))
            self.assertNotIn("2026", rendered)

    def test_roadmap_projection_has_no_subjective_percentages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "context.json"
            output = root / "ROADMAP.generated.md"
            context.write_text(json.dumps(self.context), encoding="utf-8")
            self.assertTrue(project.project_roadmap(context, output))
            rendered = output.read_text(encoding="utf-8")
            self.assertIn("sha256:architecture", rendered)
            self.assertNotRegex(rendered, r"\b\d+%")
            self.assertTrue(project.project_roadmap(context, output, check=True))


if __name__ == "__main__":
    unittest.main()
