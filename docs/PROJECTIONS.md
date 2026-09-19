# Deterministic documentation projections

`mncs-doc/tools/project.py` provides the current projection adapter for human
facing Markdown. It does not become a second architecture, language, pressure,
or RFC authority.

## Inputs and ownership

- `project-readme` consumes one bounded `mncs.family-agent-context/1` packet
  from Language Service. Language capability facts remain owned by
  `mncs-language`; family architecture and pressure facts remain owned by
  `MNCS-Commons`; repository identity remains owned by `.mncs/project.json`.
- `project-rfc-index` scans RFC bodies. The Markdown proposal remains the
  durable human-readable design artifact; the generated index is only a
  deterministic navigation projection.
- `project-roadmap` consumes the same bounded context packet. It reports
  identities, lifecycle states, and evidence-backed pressure work without
  inventing percentages or treating source presence as completion.

Each generated document uses the bounded markers
`<!-- MNCS:generated:begin -->` and `<!-- MNCS:generated:end -->`. `--check`
recomputes the expected bytes and exits non-zero for missing or hand-edited
generated content. Output ordering is identity-sorted and contains no clock,
randomness, or run-specific metadata.

The current implementation remains a temporary host semantic implementation
of a family-specific policy, with filesystem publication at its external
boundary. It is classified as a migration shadow/workload in the repository
manifest, not as a generic `structured-document` implementation. The family
projector is deliberately not the owner of language status, Commons pressure
lifecycle, architecture, or roadmap policy.

The workload currently exposes the document-domain pressure
`MNCS-LANG-BC105FDA1446`: source-preserving regions and spans are only partly
native. Structured Markdown nodes and deterministic rendering remain later
slices of that document workload. It is intentionally separate from Commons'
dynamic registry projection pressure `MNCS-LANG-6643CDECCFEC`; that pressure
is not a generic document contract. Once a reusable document capability is
callable and tested in MNCS, this workload will consume it without changing
its family-specific policy.

The current callable slice is `mncs.doc.region/1`. It receives marker spans
from the host parser and validates the lossless replacement envelope. This is
deliberately narrower than the eventual Markdown AST/rendering surface.

Typical checks are:

```text
python3 tools/project.py project-readme --readme README.md --context context.json --check
python3 tools/project.py project-rfc-index --rfc-root docs/rfcs --output docs/rfc-index.generated.md --check
python3 tools/project.py project-roadmap --context context.json --output ROADMAP.generated.md --check
```

Doctor validates local manifest binding and can report stale generated files;
it does not own the source facts or rewrite human prose.
