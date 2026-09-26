# Authoring documentation

Humans add meaning where the system cannot: summaries, explanations,
relationships in prose, and example selection.  Everything else derives
from compiler metadata.  Never duplicate a signature, effect list, or
identity in prose; reference it.

## Documentation comments

Attach a contiguous `//` block directly above a declaration (no blank
line between the block and the declaration):

```mncs
// Totals two entries. See [[log_entry]].
// @example total_adds_amounts
fn total(first: Entry, second: Entry) -> (result: i64) {
    return first.amount + second.amount;
}
```

Rules:

- The block is the maximal run of `//` lines immediately preceding the
  declaration line.  A blank line ends the block.
- Module documentation is the comment block directly above the `module`
  statement (the `mncs <version>;` header may sit above that).
- Summary = first paragraph; body = the rest.  Keep the summary to one
  paragraph; indexes display it verbatim.
- Lines matching `@example <test>` are directives, not prose: they are
  excluded from rendered text and linked against test inventory.

This leading-comment boundary is explicit and owned by Doc: the compiler
lexer discards comments, so no compiler artifact carries doc text
(see `docs/PRESSURES.md`).  If the language ever retains documentation
with declaration identities, this extractor becomes a thin reader over
that metadata with no model change.

## Cross references

Write `[[...]]` in doc text:

- `[[Entry]]` — short name; resolves only when unique in scope, otherwise
  reported `ambiguous` with candidates (never silently linked).
- `[[mncs.doc.api.v1::total]]` — qualified name; exact match required.
- `[[mncs:0.2:function:mncs.doc.api.v1::total]]` — canonical identity;
  resolves exactly, or reports `stale` when the inventory no longer
  carries it (e.g. after a rename).

Unresolved references render as plain code and fail validation.  Doc
never emits a broken link.

## Examples

`@example <test-name>` names a first-class `test` declaration in scope
(short or qualified name).  Extraction links it to the compiler
`test_case_identity` and `semantic_fingerprint`:

- `linked`: the test exists; rendered with its case identity.
- `missing`: no such test; validation fails until fixed or removed.

Execution is opt-in (`validate --verify-examples`): linked examples run
through the compiler-owned `mncs test` runner.  A passing run records
`passed`; a failing test records `test_failure` with the case identity
for Debug while noting linkage is intact; a module the runner cannot
execute (e.g. no suite harness) records `unverifiable`, never a failure.
Doc does not re-run, reinterpret, or store test verdicts.

## Visibility

Doc respects the compiler `exported` flag and never publishes
internal-by-construction details by default; `--require-docs exported`
requires authored docs for exported declarations.  The language has no
separate public/internal annotation, so Doc does not invent one
(see `docs/PRESSURES.md`).

## Effects and capabilities

Effect and capability lines render from callable metadata automatically.
Do not restate them in prose beyond explaining what they mean for
callers.  The compiler records the requesting function as the effect
target; rendering elides a target that is just the documented function,
mirroring source syntax.
