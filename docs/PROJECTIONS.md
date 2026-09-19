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

The current implementation is deliberately classified as a host-boundary
projection adapter in the repository manifest. Commons pressure
`MNCS-LANG-6643CDECCFEC` records the reusable missing generic surface for
dynamic structured registry projection; this adapter is not permission to
hide that pressure behind new application semantics. When the owning
language/stdlib/runtime capability is repaired, the projection can move into
MNCS while preserving the same input contract and byte-level tests.

Typical checks are:

```text
python3 tools/project.py project-readme --readme README.md --context context.json --check
python3 tools/project.py project-rfc-index --rfc-root docs/rfcs --output docs/rfc-index.generated.md --check
python3 tools/project.py project-roadmap --context context.json --output ROADMAP.generated.md --check
```

Doctor validates local manifest binding and can report stale generated files;
it does not own the source facts or rewrite human prose.
