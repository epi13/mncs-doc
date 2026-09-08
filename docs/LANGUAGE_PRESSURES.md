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
