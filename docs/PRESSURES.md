# Pressure ledger (documentation workload)

Genuine gaps found while building the canonical documentation system.
Language and compiler repositories are read-only; nothing here was
worked around with fragile parsing.  Owner in brackets.

## Active pressures

### DOC-01: compiler artifacts do not retain documentation comments

Workload: attach authored docs to declaration identities.
Observed: the `mncs-syntax` lexer counts and discards comments; neither
`declaration-inventory` nor `test-inventory` carries doc text, so Doc
extracts leading `//` blocks from source text keyed by compiler
`source_span` lines.
Desired: doc text (or stable doc hashes) retained per declaration
identity in compiler artifacts, making `extract_leading_docs` a reader
rather than a parser.  Until then the source-text boundary is explicit
in `docs/ARCHITECTURE.md` and covered by byte-level tests.
Owner: mncs-language.  Blocking: no (explicit bounded extraction).

### DOC-02: enum variant detail absent from declaration inventory

Workload: type-relationship navigation (variants of an enum).
Observed: `finite_type` identities carry only the type name
(`mncs:0.2:finite-type:m::Shape`); record identities embed fields but
enum identities embed no variants.
Desired: variant/member declarations or variant lists per finite type
identity.  Doc currently reports no members rather than guessing.
Owner: mncs-compiler.  Blocking: no.

### DOC-03: bare-test modules are not executable; suite modules are not extractable

Workload: verified documentation examples.
Observed: `mncs test --source` on a self-contained module with bare
`test` decls fails (`execution target module does not match program`;
a suite initializer is required), while suite-harness modules need
`use` imports that `declaration-inventory` cannot resolve
(`MNE173 ... unavailable to the resolver`; no `--library` flag).
So no single module shape today is both Doc-extractable and
runner-executable: example execution reports `unverifiable`.
Desired: either execute bare-test modules directly, or resolve library
imports during inventory (batch/library-aware inventory).
Owner: mncs-language + mncs-test.  Blocking: no (linkage, the Doc
contract, works fully; execution stays Test-owned).

### DOC-04: no batch inventory; per-file compiler startup dominates

Workload: multi-module reference generation.
Observed: 5 modules cost ~6.2s (10 inventory subprocesses, ~0.6s
startup each); extraction itself is milliseconds.
Desired: multi-source or workspace inventory in one invocation.
Doc batches nothing itself; one re-inventory per source per validation.
Owner: mncs-language.  Blocking: no.

### DOC-05: no public/internal visibility metadata

Workload: public vs internal API surfacing.
Observed: callables carry `exported: bool` only; no language-level
visibility annotation distinct from export.
Desired: nothing today; Doc respects `exported` and invents no naming
convention.  Recorded so a future visibility feature has a consumer.
Owner: mncs-language.  Blocking: no.

### DOC-06: effect `target` duplicates the requesting function

Workload: faithful signature rendering.
Observed: effect entries carry `target` equal to the requesting
function name (`process_run` on `run`), which source syntax never
spells.  Doc elides self-targets in rendering and keeps the full
record in the model.
Desired: documentation of the `target` field semantics in the
inventory schema.  Owner: mncs-compiler.  Blocking: no.

## Text-workload pressures

The structured-document text pressures in `docs/LANGUAGE_PRESSURES.md`
(Unicode boundaries, source spans, lossless trees, diagnostics) remain
valid for the document-infrastructure layer and the deterministic
projection adapter; they are unchanged by this campaign.
