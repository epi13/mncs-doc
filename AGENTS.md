# Agent and contributor contract

- Prefer `mncs-language` for implementation.
- Treat Unicode correctly; byte offsets, scalar values and grapheme/user-visible positions must not be conflated.
- Preserve source spans and useful diagnostics through parsing/transformation where practical.
- Distinguish lossless syntax representation from semantic document representation when necessary.
- Avoid format-specific assumptions in reusable document layers.
- Record language/compiler/runtime friction in `docs/LANGUAGE_PRESSURES.md` (text workload) or `docs/PRESSURES.md` (documentation workload).
- Include malformed, adversarial and multilingual fixtures in tests.

## Documentation contract

- Documentation derives from compiler declaration/test inventory plus
  leading source comments plus repository manifest identity.  Never
  hand-maintain a signature, effect list, capability, or identity that
  the compiler already reports; investigate the tooling gap instead.
- Cross references resolve by canonical semantic identity, never by
  display name.  Same-named declarations stay distinct end to end.
- `mncs-language` and `mncs-compiler` are read-only.  Reach them only
  through the `mncs` binary (`$MNCS_BIN` or `PATH`).
- Repositories on active campaign branches are read-only: inspect, do
  not modify.  Keep mncs-doc changes inside mncs-doc.
- Generated documentation artifacts are ephemeral by default: do not
  commit rendered output that `tools/mncs_doc.py` reproduces
  deterministically.  Commit models only as test vectors, never as a
  synchronized database.
- Host code (`tools/`) is the explicit filesystem/render boundary; the
  verdict lattice lives natively (`native/mncs/doc/`).  Do not move
  rendering plumbing into MNCS, and do not leave documentation
  semantics host-owned from habit.
- Doc validates documentation semantics; Doctor owns project
  conformance; Test owns execution verdicts.  A failing example test is
  a `test_failure` check with its case identity preserved, never a
  reinterpreted verdict.

## Family entry contract

- Establish the bounded Language Service family context and current Commons
  architecture/pressure identities before broad repository search.
- Query the current MNCS capability index and existing Commons pressure before
  adding host projection logic; repair a reusable missing facility upstream
  where practical.
- Keep documentation generators deterministic and identity-bound. Host code is
  an explicit file/Markdown projection boundary until the generic structured
  document pressure is repaired; it must not become a second family authority.
