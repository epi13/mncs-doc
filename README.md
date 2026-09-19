# mncs-doc

Machine-native structured document and rich-text infrastructure for MNCS.

`mncs-doc` pressures `mncs-language` with text-heavy, semantic and human-facing workloads: Unicode, parsing, source locations, syntax trees, transformations, formatting, layout, search and lossy/lossless interchange.

## Initial scope

- Unicode-aware text primitives and source spans
- Markdown/HTML-style structured document ingestion
- document AST and semantic nodes
- parsing and lossless/source-preserving transforms where possible
- visitors, queries and rewriting
- rendering/formatting adapters
- indexing/search boundaries
- diagnostics for malformed documents

## Repository layout

- `docs/ARCHITECTURE.md`
- `docs/rfcs/0001-foundation.md`
- `docs/LANGUAGE_PRESSURES.md`
- `AGENTS.md`

## Projection contract

Deterministic README, RFC-index, and roadmap projections are implemented as a
family-specific dogfood workload in
[`tools/project.py`](tools/project.py) and described in
[`docs/PROJECTIONS.md`](docs/PROJECTIONS.md). Generated regions are bounded
and checkable; the surrounding explanation remains human-authored. This does
not yet provide the reusable `structured-document` contract from RFC 0001.

The first reusable vertical slice is `native/mncs/doc/region.mncs`: a bounded
source-span decision function for lossless generated-region replacement. The
host projector still finds marker bytes and publishes files; the region
ordering and replacement boundaries are document semantics owned by
`mncs-doc`.
