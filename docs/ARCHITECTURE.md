# Architecture

## Layers

1. **Text/source** — Unicode text, byte/scalar/grapheme boundaries, source IDs and spans.
2. **Syntax** — tokenization/parsing and lossless format-specific trees where needed.
3. **Document model** — headings, paragraphs, inline content, links, lists, tables, metadata and extension nodes.
4. **Transforms** — traversal, querying, rewriting, normalization and validation.
5. **Output** — serializers, formatters and render adapters.
6. **Index/tooling** — search/index hooks, diagnostics, source maps and deterministic fixtures.

## First milestones

1. Text/span foundation and document node model.
2. Markdown ingestion/emission subset.
3. Traversal/query/rewrite API.
4. Source-preserving diagnostics and malformed-input corpus.
5. HTML/other adapters and indexing pressure workloads.
