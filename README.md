# mncs-doc

The canonical MNCS documentation system: documentation as a derived,
identity-aware, verifiable view of the actual system.

```
compiler inventories + authored comments + repo identity
-> documentation model -> Markdown / HTML / text + index + validation
```

## What Doc owns

The documentation semantic model, extraction from canonical metadata,
identity-based cross references, structural validation, example-to-test
linkage, renderers, semantic indexes, and stale-doc detection.  See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Doc does not own language semantics, compiler symbol authority, project
topology, test verdicts, or persistence; those stay with their owners
and are consumed read-only.

## Quick start

```text
export MNCS_BIN=/path/to/mncs   # or place mncs on PATH
python3 tools/mncs_doc.py extract --source path/to/module.mncs --output model.json
python3 tools/mncs_doc.py render --model model.json --format markdown --output api.md
python3 tools/mncs_doc.py validate --model model.json
python3 tools/mncs_doc.py query --model model.json --qualified my.module::my_fn --format text
```

Full command and schema reference: [`docs/MODEL.md`](docs/MODEL.md).
Authoring conventions (comments, `[[xrefs]]`, `@example`):
[`docs/AUTHORING.md`](docs/AUTHORING.md).
Known metadata gaps: [`docs/PRESSURES.md`](docs/PRESSURES.md).

## Repository layout

- `native/mncs/doc/model.mncs` — native verdict lattice (link status,
  severity, example state, tally folding) with self-contained tests.
  Doc documents this module with itself.
- `tools/mncs_doc.py` — host adapter: extract, render, index, query,
  validate (including opt-in `--verify-examples`).
- `tools/project.py` — deterministic README/RFC-index/roadmap
  projections over family context (retained; see
  [`docs/PROJECTIONS.md`](docs/PROJECTIONS.md)).
- `tests/fixtures/*.mncs` — MNCS fixtures for the semantic test suite.
- `tests/test_doc.py` — extraction, signatures, identity, xrefs,
  examples, staleness, determinism, rendering, query.
- `tests/test_projection.py` — projection adapter tests (retained).
- `docs/ARCHITECTURE.md`, `docs/MODEL.md`, `docs/AUTHORING.md`,
  `docs/PRESSURES.md`, `docs/LANGUAGE_PRESSURES.md`,
  `docs/rfcs/0001-foundation.md`.

## Verification

```text
python3 -m unittest discover -s tests
```

`MNCS_BIN` (or `mncs` on `PATH`) must point at the compiler binary;
inventory-backed tests skip cleanly without it.
