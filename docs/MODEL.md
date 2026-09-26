# Documentation model reference

## `mncs.documentation-model/1`

```json
{
  "schema_version": "mncs.documentation-model/1",
  "generator": {"name": "mncs-doc", "tool": "tools/mncs_doc.py", "tool_version": "1"},
  "subjects": [
    {
      "source_path": "native/mncs/doc/model.mncs",
      "repository": "mncs-doc",
      "revision": 4,
      "module": "mncs.doc.model.v1",
      "source_profile": "0.17",
      "source_artifact_identity": "mncs:source:artifact:...",
      "subject_identity": "mncs:0.2:program:mncs.doc.model.v1",
      "subject_fingerprint": "...",
      "inventory_identity": "sha256:...",
      "test_inventory_identity": "sha256:... | null"
    }
  ],
  "declarations": [
    {
      "identity": "mncs:0.2:function:mncs.doc.model.v1::make_link",
      "kind": "function | test | record_type | finite_type | module",
      "module": "mncs.doc.model.v1",
      "name": "make_link",
      "qualified_name": "mncs.doc.model.v1::make_link",
      "source_span": {"start": 0, "end": 0, "line": 0, "column": 0},
      "exported": true,
      "source_path": "native/mncs/doc/model.mncs",
      "signature": {
        "callable_kind": "function",
        "generic_params": [{"name": "N", "kind": "nat"}],
        "inputs": [{"name": "status", "type": "LinkStatus"}],
        "outputs": [{"name": "link", "type": "DocLink"}],
        "effects": [],
        "capabilities": [],
        "signature_hash": "sha256:..."
      },
      "doc": {
        "summary": "first paragraph",
        "body": "remaining paragraphs",
        "source": "leading-comment",
        "raw_refs": ["make_link"],
        "example_refs": ["link_round_trip_is_clean"]
      },
      "type_relations": {
        "member_of": null,
        "members": [],
        "fields": [{"name": "status", "type": "LinkStatus"}]
      },
      "test_case_identity": "mncs:0.2:test-case:... | null",
      "examples": [
        {"test": "link_round_trip_is_clean", "status": "linked",
         "test_case_identity": "mncs:0.2:test-case:...",
         "semantic_fingerprint": "..."}
      ]
    }
  ],
  "tests": ["<compiler test-inventory entries, plus source_path>"],
  "xrefs": [
    {"from": "mncs:0.2:function:...::a", "to": "make_link",
     "kind": "doc-link", "status": "resolved | missing | ambiguous | stale",
     "resolved_identity": "mncs:0.2:function:... | null",
     "candidates": []}
  ],
  "coverage": {"exported_total": 0, "exported_documented": 0}
}
```

Notes:

- `signature` is present exactly when the compiler reports a callable for
  the declaration identity; otherwise it is `null` (modules, records,
  enums).  `signature_hash` covers generics, inputs, outputs, effects, and
  capabilities, and drives per-identity staleness detection.
- `doc` is present exactly when a leading `//` block attaches; otherwise
  `null`.  Missing optional docs never break generation.
- `type_relations.fields` comes from the compiler record-type identity;
  the compiler emits no separate field declarations and no enum variant
  detail (see `docs/PRESSURES.md`).
- `examples[].status` is `linked` or `missing`.  Execution state is never
  stored here; it belongs to validation reports and mncs-test evidence.

## `mncs.documentation-validation/1`

`{"schema_version", "subjects", "checks": [...], "summary": {"total",
"failed", "passed"}, "verdict": "PASS | FAIL"}`.  Check kinds:

- `xref-resolved`: every doc link resolves (FAIL: missing/ambiguous/stale).
- `example-linked`: every `@example` names a test in scope.
- `example-execution` (opt-in `--verify-examples`): linked example executed
  via the compiler-owned runner.  `test_failure` FAILs the check but
  preserves the test-case identity and notes that linkage is intact; the
  underlying failure belongs to mncs-test/Debug.  `unverifiable` (e.g. no
  suite harness) never fails.
- `required-docs` (`--require-docs exported|all`): policy-demanded docs
  exist.  Default `none` reports counts without failing.
- `inventory-current` / `signature-current` (with sources): re-inventory
  comparison; catches revision drift, added/removed identities, and
  signature changes.

## `mncs.documentation-index/1`

`{"schema_version", "model_identities": [...], "entries": [...]}` with one
entry per declaration: identity, qualified_name, name, kind, module,
summary, anchor, exported, generic_arity, has_effects, has_capabilities,
has_doc, has_example.  Sorted by identity.  Atlas and agents consume this,
never scraped Markdown.

## `mncs.documentation-provenance/1`

`{"schema_version", "generator", "model_digest", "subjects",
"generated_at"}`.  Written only via `extract --provenance-out`; kept out
of the model so generation stays byte-deterministic.

## CLI

```
python3 tools/mncs_doc.py extract --source FILE [--source ...] --output MODEL.json
  [--repository NAME] [--revision REV] [--provenance-out PROV.json] [--check]
python3 tools/mncs_doc.py render --model MODEL.json --format markdown|html|text --output OUT [--check]
python3 tools/mncs_doc.py index --model MODEL.json --output INDEX.json [--check]
python3 tools/mncs_doc.py query --model MODEL.json [--identity ID | --qualified Q | --name N | --module M | --kind K] [--limit N] [--format json|text]
python3 tools/mncs_doc.py validate --model MODEL.json [--source FILE ...] [--no-staleness]
  [--require-docs none|exported|all] [--verify-examples [--library DIR ...] [--example-timeout S]] [--output REPORT.json]
```

`--mncs-bin` (or `$MNCS_BIN`) selects the compiler binary; language and
compiler repositories are only ever read through it, never modified.
Exit codes: 0 PASS/current, 1 FAIL/stale, 2 invocation error.
