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


def require_binary(test):
    return unittest.skipIf(project.find_mncs() is None,
                           "mncs compiler binary unavailable")(test)


class DogfoodIndexTests(unittest.TestCase):
    def test_own_rfc_index_is_current(self):
        repo = Path(__file__).resolve().parents[1]
        self.assertTrue(project.project_rfc_index(
            repo / "docs" / "rfcs", repo / "docs" / "rfc-index.generated.md",
            check=True))


class ApplyProjectionTests(unittest.TestCase):
    def _write(self, root: Path, name: str, text: str) -> Path:
        path = root / name
        path.write_text(text, encoding="utf-8")
        return path

    @require_binary
    def test_apply_replaces_valid_region_and_preserves_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._write(
                root, "README.md",
                "# Title\n\nHuman intro.\n\n"
                "<!-- MNCS:generated:begin -->\nold\n<!-- MNCS:generated:end -->\n\n"
                "Human outro.\n")
            generated = self._write(root, "gen.md", "new-bytes\n")
            self.assertTrue(project.apply_projection(
                document, generated, source_count=2,
                template_present=True, create_allowed=False))
            rendered = document.read_text(encoding="utf-8")
            self.assertIn("Human intro.", rendered)
            self.assertIn("Human outro.", rendered)
            self.assertIn("new-bytes", rendered)
            self.assertNotIn("old\n", rendered)
            # Idempotent: a second apply changes nothing and checks clean.
            before = document.read_bytes()
            self.assertTrue(project.apply_projection(
                document, generated, source_count=2,
                template_present=True, create_allowed=False, check=True))
            self.assertTrue(project.apply_projection(
                document, generated, source_count=2,
                template_present=True, create_allowed=False))
            self.assertEqual(before, document.read_bytes())

    @require_binary
    def test_apply_detects_hand_edited_region(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._write(
                root, "README.md",
                "<!-- MNCS:generated:begin -->\nnew-bytes\n<!-- MNCS:generated:end -->\n")
            generated = self._write(root, "gen.md", "new-bytes\n")
            self.assertTrue(project.apply_projection(
                document, generated, source_count=1,
                template_present=True, create_allowed=False, check=True))
            document.write_text(
                document.read_text(encoding="utf-8").replace(
                    "new-bytes", "hand-edit"), encoding="utf-8")
            self.assertFalse(project.apply_projection(
                document, generated, source_count=1,
                template_present=True, create_allowed=False, check=True))

    @require_binary
    def test_apply_refuses_ambiguous_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._write(
                root, "README.md",
                "<!-- MNCS:generated:begin -->\na\n<!-- MNCS:generated:end -->\n"
                "<!-- MNCS:generated:begin -->\nb\n<!-- MNCS:generated:end -->\n")
            generated = self._write(root, "gen.md", "new\n")
            before = document.read_bytes()
            self.assertFalse(project.apply_projection(
                document, generated, source_count=1,
                template_present=True, create_allowed=True))
            self.assertEqual(before, document.read_bytes())

    @require_binary
    def test_apply_creates_missing_region_only_when_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._write(root, "README.md", "# Title\n\nProse.\n")
            generated = self._write(root, "gen.md", "derived\n")
            self.assertFalse(project.apply_projection(
                document, generated, source_count=1,
                template_present=True, create_allowed=False))
            self.assertIn("Prose.", document.read_text(encoding="utf-8"))
            self.assertNotIn(project.BEGIN, document.read_text(encoding="utf-8"))
            self.assertTrue(project.apply_projection(
                document, generated, source_count=1,
                template_present=True, create_allowed=True))
            rendered = document.read_text(encoding="utf-8")
            self.assertIn("Prose.", rendered)
            self.assertIn("derived", rendered)

    @require_binary
    def test_apply_refuses_sourceless_or_templateless_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._write(
                root, "README.md",
                "<!-- MNCS:generated:begin -->\nold\n<!-- MNCS:generated:end -->\n")
            generated = self._write(root, "gen.md", "new\n")
            before = document.read_bytes()
            self.assertFalse(project.apply_projection(
                document, generated, source_count=0,
                template_present=True, create_allowed=False))
            self.assertFalse(project.apply_projection(
                document, generated, source_count=1,
                template_present=False, create_allowed=False))
            self.assertEqual(before, document.read_bytes())

    def test_apply_fails_closed_without_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._write(root, "README.md", "prose\n")
            generated = self._write(root, "gen.md", "derived\n")
            real_find = project.find_mncs
            project.find_mncs = lambda explicit=None: None  # type: ignore
            try:
                with self.assertRaises(project.NativeError):
                    project.apply_projection(
                        document, generated, source_count=1,
                        template_present=True, create_allowed=True)
            finally:
                project.find_mncs = real_find
            self.assertEqual(b"prose\n", document.read_bytes())


if __name__ == "__main__":
    unittest.main()
