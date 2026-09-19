# MNCS language pressure ledger

Record workload, observed behavior, desired semantic, reproducer, owner, workaround and closure verification.

## Initial pressure targets

- UTF-8 validation and Unicode scalar iteration
- grapheme-aware operations and normalization hooks
- cheap text slicing with explicit lifetime/ownership
- recursive document trees and enums
- pattern matching ergonomics
- parser combinator/state-machine expressiveness
- structured parse errors with source spans
- error recovery without exception-like hidden control flow
- visitor/iterator/generator patterns
- extensible node metadata without pervasive dynamic typing
- incremental/streaming parsing
- diagnostics that distinguish byte, scalar and display positions

## Current document-workload evidence

The family README/RFC/roadmap projector is a dogfood workload, not a generic
document implementation. Against the current 0.18 language it still needs a
small reusable document surface for:

Commons records this workload as `MNCS-LANG-BC105FDA1446`; the older
`MNCS-LANG-6643CDECCFEC` registry-projection pressure is deliberately not used
as the document blocker.

- bounded UTF-8 source views with byte/scalar spans;
- lossless replacement of marked generated regions while preserving prose;
- structural Markdown headings, lists, and tables;
- deterministic text emission and malformed-region diagnostics.

The first native slice closes only the bounded region-boundary portion: the
`mncs.doc.region` module validates one pair of marker spans and returns exact
replacement/prefix/suffix offsets. Marker search, Unicode decoding, Markdown
structure, and filesystem publication remain open document-workload pressures.

The filesystem walk, authority lookup, and publication remain external
boundaries. This ledger is intentionally separate from Commons'
`MNCS-LANG-6643CDECCFEC` dynamic registry history.
