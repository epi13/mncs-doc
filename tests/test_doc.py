"""Semantic documentation tests for the canonical mncs-doc pipeline.

Every expectation derives from compiler-owned inventory plus the fixture
sources in tests/fixtures.  Nothing here re-states hand-maintained
signatures: the assertions compare Doc output against the inventory the
compiler itself reports.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import mncs_doc  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures"


def find_binary() -> str | None:
    import os
    from shutil import which

    for candidate in (
        os.environ.get("MNCS_BIN"),
        which("mncs"),
        str(Path("/home/epi13/Documents/Projects")
            / "mncs-language" / "target" / "debug" / "mncs"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return None


MNCS_BIN = find_binary()


def require_binary(test):
    return unittest.skipIf(MNCS_BIN is None, "mncs compiler binary unavailable")(test)


def declarations_by_qualified(model):
    return {d["qualified_name"]: d for d in model["declarations"]}


class ExtractionTests(unittest.TestCase):
    @require_binary
    def test_known_declarations_produce_correct_records(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        self.assertEqual(model["schema_version"], "mncs.documentation-model/1")
        self.assertEqual(model["subjects"][0]["module"], "mncs.doc.fixture_api.v1")
        kinds = {d["qualified_name"]: d["kind"] for d in model["declarations"]}
        self.assertEqual(kinds["mncs.doc.fixture_api.v1::log_entry"], "function")
        self.assertEqual(kinds["mncs.doc.fixture_api.v1::Entry"], "record_type")
        self.assertEqual(kinds["mncs.doc.fixture_api.v1::EntryKind"], "finite_type")
        self.assertEqual(kinds["mncs.doc.fixture_api.v1::total_adds_amounts"], "test")
        self.assertEqual(kinds["mncs.doc.fixture_api.v1"], "module")
        for declaration in model["declarations"]:
            self.assertTrue(declaration["identity"].startswith("mncs:"),
                            declaration)

    @require_binary
    def test_signatures_match_canonical_inventory(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        raw = mncs_doc.run_inventory(MNCS_BIN, "declaration-inventory",
                                     FIXTURES / "api.mncs")["inventory"]
        callables = {c["declaration_identity"]: c for c in raw["callables"]}
        by_qualified = declarations_by_qualified(model)
        for declaration in model["declarations"]:
            callable = callables.get(declaration["identity"])
            if callable is None:
                self.assertIsNone(declaration["signature"])
                continue
            signature = declaration["signature"]
            self.assertEqual(
                [(i["name"], i["type"]) for i in signature["inputs"]],
                [(i["name"], i["type"]) for i in callable["inputs"]])
            self.assertEqual(
                [(o["name"], o["type"]) for o in signature["outputs"]],
                [(o["name"], o["type"]) for o in callable["outputs"]])
            self.assertEqual(signature["effects"], callable["effects"])
            self.assertEqual(signature["capabilities"], callable["capabilities"])
            self.assertEqual(
                [(g["name"], g.get("kind")) for g in signature["generic_params"]],
                [(g["name"], g.get("kind")) for g in callable["generic_params"]])

    @require_binary
    def test_generic_signature_renders_constraints(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        text = mncs_doc.render_signature(
            "sum_run", by_qualified["mncs.doc.fixture_api.v1::sum_run"]["signature"],
            "function")
        self.assertIn("<N: nat>", text)
        self.assertIn("xs: [i64; N]", text)

    @require_binary
    def test_effects_and_capabilities_stay_visible(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        text = mncs_doc.render_signature(
            "post", by_qualified["mncs.doc.fixture_api.v1::post"]["signature"],
            "function")
        self.assertIn("capability ledger_capability", text)
        self.assertIn("effect ledger_post authorized_by ledger_capability", text)

    @require_binary
    def test_record_fields_come_from_compiler_identity(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        fields = by_qualified["mncs.doc.fixture_api.v1::Entry"]["type_relations"]["fields"]
        self.assertEqual([(f["name"], f["type"]) for f in fields],
                         [("amount", "i64"), ("flags", "i64")])

    @require_binary
    def test_module_and_summary_docs_attach(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        module = by_qualified["mncs.doc.fixture_api.v1"]
        self.assertIsNotNone(module["doc"])
        self.assertIn("ledger", module["doc"]["summary"])
        record_fn = by_qualified["mncs.doc.fixture_api.v1::log_entry"]
        self.assertEqual(record_fn["doc"]["summary"],
                         "Logs one entry amount. See [[Entry]].")

    @require_binary
    def test_same_named_declarations_stay_distinct(self):
        model = mncs_doc.build_model(
            [FIXTURES / "amb_a.mncs", FIXTURES / "amb_b.mncs"], MNCS_BIN)
        creates = [d for d in model["declarations"] if d["name"] == "create"]
        self.assertEqual(len(creates), 2)
        identities = {d["identity"] for d in creates}
        self.assertEqual(len(identities), 2)
        anchors = {mncs_doc.anchor_of(d["identity"]) for d in creates}
        self.assertEqual(len(anchors), 2)


class CrossReferenceTests(unittest.TestCase):
    @require_binary
    def test_valid_links_resolve_by_identity(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        statuses = {(x["from"], x["to"]): x for x in model["xrefs"]}
        record_id = by_qualified["mncs.doc.fixture_api.v1::log_entry"]["identity"]
        self.assertEqual(statuses[(record_id, "Entry")]["status"], "resolved")
        self.assertEqual(
            statuses[(record_id, "Entry")]["resolved_identity"],
            by_qualified["mncs.doc.fixture_api.v1::Entry"]["identity"])
        total_id = by_qualified["mncs.doc.fixture_api.v1::total"]["identity"]
        self.assertEqual(statuses[(total_id, "log_entry")]["status"], "resolved")
        self.assertEqual(
            statuses[(total_id, "log_entry")]["resolved_identity"],
            by_qualified["mncs.doc.fixture_api.v1::log_entry"]["identity"])

    @require_binary
    def test_missing_ambiguous_and_stale_links_are_detected(self):
        model = mncs_doc.build_model(
            [FIXTURES / "amb_a.mncs", FIXTURES / "amb_b.mncs"], MNCS_BIN)
        by_status = {}
        for xref in model["xrefs"]:
            by_status.setdefault(xref["status"], []).append(xref["to"])
        self.assertIn("create", by_status.get("ambiguous", []))
        self.assertIn("NoSuchThing", by_status.get("missing", []))
        self.assertIn("mncs:0.2:function:mncs.doc.fixture_gone.v9::removed",
                      by_status.get("stale", []))
        ambiguous = [x for x in model["xrefs"] if x["status"] == "ambiguous"]
        self.assertEqual(len(ambiguous[0]["candidates"]), 2)

    @require_binary
    def test_validation_fails_on_broken_links_only(self):
        clean = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        report = mncs_doc.validate_model(clean, MNCS_BIN, sources=None,
                                         require_docs="none")
        self.assertEqual(report["verdict"], "PASS")
        broken = mncs_doc.build_model(
            [FIXTURES / "amb_a.mncs", FIXTURES / "amb_b.mncs"], MNCS_BIN)
        report = mncs_doc.validate_model(broken, MNCS_BIN, sources=None,
                                         require_docs="none")
        self.assertEqual(report["verdict"], "FAIL")
        reasons = {c.get("reason") for c in report["checks"]
                   if c["status"] == "FAIL"}
        self.assertTrue({"missing", "ambiguous", "stale"} & reasons)


class ExampleTests(unittest.TestCase):
    @require_binary
    def test_example_links_to_test_case_identity(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        total = by_qualified["mncs.doc.fixture_api.v1::total"]
        self.assertEqual(len(total["examples"]), 1)
        example = total["examples"][0]
        self.assertEqual(example["status"], "linked")
        self.assertTrue(example["test_case_identity"].startswith("mncs:"))
        test_entry = by_qualified["mncs.doc.fixture_api.v1::total_adds_amounts"]
        self.assertEqual(test_entry["test_case_identity"],
                         example["test_case_identity"])

    @require_binary
    def test_example_linkage_validates(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        report = mncs_doc.validate_model(model, MNCS_BIN, sources=None,
                                         require_docs="none")
        example_checks = [c for c in report["checks"]
                          if c["check"] == "example-linked"]
        self.assertTrue(example_checks)
        self.assertTrue(all(c["status"] == "PASS" for c in example_checks))


class ExampleExecutionTests(unittest.TestCase):
    def _model_with_example(self):
        return {
            "schema_version": "mncs.documentation-model/1",
            "subjects": [],
            "declarations": [
                {"identity": "mncs:0.2:function:m::show",
                 "kind": "function", "module": "m", "name": "show",
                 "qualified_name": "m::show", "source_path": "/tmp/m.mncs",
                 "signature": None, "doc": {"summary": "Shows."},
                 "type_relations": {}, "test_case_identity": None,
                 "examples": [{"test": "show_is_shown", "status": "linked",
                               "test_case_identity": "mncs:0.2:test-case:m::show_is_shown::x",
                               "semantic_fingerprint": "x"}]},
            ],
            "tests": [],
            "xrefs": [],
        }

    def test_passing_execution_maps_to_pass(self):
        from unittest import mock

        result = {"run_id": "r", "classification": "passed", "verdict": "PASS",
                  "summary": {"passed": 1},
                  "tests": [{"entry": "show_is_shown", "verdict": "PASS"}]}
        with mock.patch.object(mncs_doc.subprocess, "run") as run:
            run.return_value = mock.Mock(stdout=json.dumps(result))
            checks = mncs_doc.verify_example_execution(
                self._model_with_example(), "mncs")
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["status"], "PASS")
        self.assertEqual(checks[0]["execution"], "passed")

    def test_failing_test_is_doc_fail_with_test_layer_preserved(self):
        from unittest import mock

        result = {"run_id": "r", "classification": "test_failure",
                  "verdict": "FAIL", "summary": {"failed": 1},
                  "tests": [{"entry": "show_is_shown", "verdict": "FAIL"}]}
        with mock.patch.object(mncs_doc.subprocess, "run") as run:
            run.return_value = mock.Mock(stdout=json.dumps(result))
            checks = mncs_doc.verify_example_execution(
                self._model_with_example(), "mncs")
        self.assertEqual(checks[0]["status"], "FAIL")
        self.assertEqual(checks[0]["reason"], "test_failure")
        self.assertIn("mncs-test", checks[0]["note"])
        self.assertEqual(checks[0]["test_case_identity"],
                         "mncs:0.2:test-case:m::show_is_shown::x")

    def test_unrunnable_module_is_unverifiable_not_failure(self):
        from unittest import mock

        with mock.patch.object(mncs_doc.subprocess, "run") as run:
            run.side_effect = OSError("no runner")
            checks = mncs_doc.verify_example_execution(
                self._model_with_example(), "mncs")
        self.assertEqual(checks[0]["status"], "PASS")
        self.assertEqual(checks[0]["execution"], "unverifiable")


class StalenessTests(unittest.TestCase):
    @require_binary
    def test_added_identity_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "copy.mncs"
            shutil.copy(FIXTURES / "api.mncs", source)
            model = mncs_doc.build_model([source], MNCS_BIN)
            with source.open("a", encoding="utf-8") as handle:
                handle.write("\n// Added later.\nfn added() -> (result: i64) {\n"
                             "    return 0;\n}\n")
            report = mncs_doc.validate_model(model, MNCS_BIN, sources=[source],
                                             require_docs="none")
            self.assertEqual(report["verdict"], "FAIL")
            added = [c for c in report["checks"]
                     if c["check"] == "signature-current"
                     and c.get("reason", "").startswith("identity added")]
            self.assertTrue(added)

    @require_binary
    def test_changed_signature_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "copy.mncs"
            shutil.copy(FIXTURES / "api.mncs", source)
            model = mncs_doc.build_model([source], MNCS_BIN)
            text = source.read_text(encoding="utf-8")
            text = text.replace("fn log_entry(amount: i64, flags: i64)",
                                "fn log_entry(amount: i64, flags: i64, extra: i64)")
            text = text.replace("return Entry { amount: amount, flags: flags };",
                                "return Entry { amount: amount, flags: flags + extra };")
            source.write_text(text, encoding="utf-8")
            report = mncs_doc.validate_model(model, MNCS_BIN, sources=[source],
                                             require_docs="none")
            self.assertEqual(report["verdict"], "FAIL")
            changed = [c for c in report["checks"]
                       if c.get("reason") == "signature changed since model was built"]
            self.assertTrue(changed)

    @require_binary
    def test_unchanged_source_validates_current(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        report = mncs_doc.validate_model(model, MNCS_BIN,
                                         sources=[FIXTURES / "api.mncs"],
                                         require_docs="none")
        self.assertEqual(report["verdict"], "PASS")


class DeterminismTests(unittest.TestCase):
    @require_binary
    def test_repeated_extraction_is_byte_identical(self):
        first = mncs_doc._dump_canonical(
            mncs_doc.build_model([FIXTURES / "api.mncs",
                                  FIXTURES / "amb_a.mncs"], MNCS_BIN))
        second = mncs_doc._dump_canonical(
            mncs_doc.build_model([FIXTURES / "amb_a.mncs",
                                  FIXTURES / "api.mncs"], MNCS_BIN))
        self.assertEqual(first, second)
        model = json.loads(first)
        self.assertNotIn("2026", first)
        identities = [d["identity"] for d in model["declarations"]]
        self.assertEqual(identities, sorted(identities))

    @require_binary
    def test_renderers_preserve_semantics(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        markdown = mncs_doc.render_markdown(model)
        rendered_again = mncs_doc.render_markdown(
            json.loads(mncs_doc._dump_canonical(model)))
        self.assertEqual(markdown, rendered_again)
        for declaration in model["declarations"]:
            if declaration["kind"] == "module":
                continue
            self.assertIn(declaration["identity"], markdown)
        self.assertIn("effect ledger_post authorized_by ledger_capability",
                      markdown)


class RenderingTests(unittest.TestCase):
    @require_binary
    def test_html_escapes_doc_text(self):
        model = mncs_doc.build_model([FIXTURES / "escape.mncs"], MNCS_BIN)
        output = mncs_doc.render_html(model)
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn("&amp;", output)

    @require_binary
    def test_broken_links_never_render_as_links(self):
        model = mncs_doc.build_model(
            [FIXTURES / "amb_a.mncs", FIXTURES / "amb_b.mncs"], MNCS_BIN)
        markdown = mncs_doc.render_markdown(model)
        # The missing ref renders as code in the unresolved section, never
        # as a link target.
        self.assertIn("`[[NoSuchThing]]`: **missing**", markdown)
        self.assertNotIn("[`NoSuchThing`](#", markdown)

    @require_binary
    def test_partial_docs_do_not_break_generation(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_qualified = declarations_by_qualified(model)
        self.assertIsNone(by_qualified["mncs.doc.fixture_api.v1::sum_run"]["doc"])
        markdown = mncs_doc.render_markdown(model)
        self.assertIn("_No authored documentation._", markdown)
        report = mncs_doc.validate_model(model, MNCS_BIN, sources=None,
                                         require_docs="exported")
        self.assertEqual(report["verdict"], "FAIL")
        missing = [c for c in report["checks"]
                   if c["check"] == "required-docs" and c["status"] == "FAIL"]
        self.assertEqual(len(missing), 1)


class QueryTests(unittest.TestCase):
    @require_binary
    def test_bounded_retrieval(self):
        model = mncs_doc.build_model([FIXTURES / "api.mncs"], MNCS_BIN)
        by_id = mncs_doc.query_model(
            model, identity="mncs:0.2:function:mncs.doc.fixture_api.v1::total")
        self.assertEqual(len(by_id), 1)
        self.assertIn("fn total", by_id[0]["signature_text"])
        functions = mncs_doc.query_model(model, kind="function", limit=2)
        self.assertEqual(len(functions), 2)
        scoped = mncs_doc.query_model(model, module="mncs.doc.fixture_api.v1",
                                      kind="test")
        self.assertEqual(len(scoped), 1)
        index = mncs_doc.build_index(model)
        self.assertEqual(index["schema_version"], "mncs.documentation-index/1")
        entries = index["entries"]
        self.assertEqual([e["identity"] for e in entries],
                         sorted(e["identity"] for e in entries))
        post = next(e for e in entries
                    if e["qualified_name"] == "mncs.doc.fixture_api.v1::post")
        self.assertTrue(post["has_effects"] and post["has_capabilities"])


if __name__ == "__main__":
    unittest.main()
