# RFC 0001: Structured document foundation

Status: Draft

## Principles

- Unicode boundaries are explicit and correct.
- Source location survives parsing and transformations where feasible.
- Parsers return structured diagnostics rather than generic failures.
- Syntax fidelity and semantic convenience are separate concerns when they conflict.
- Document nodes are extensible without making every consumer dynamically untyped.
- Streaming/incremental processing remains possible for large inputs.

## Pressure objectives

Unicode/graphemes, strings/slices, enums/sum types, recursive data, pattern matching, parser ergonomics, iterators, source-span types, visitor/query abstractions, heterogeneous extension nodes, error recovery and diagnostics, incremental/streaming parsing and memory-efficient text storage.
