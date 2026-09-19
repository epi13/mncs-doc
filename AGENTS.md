# Agent and contributor contract

- Prefer `mncs-language` for implementation.
- Treat Unicode correctly; byte offsets, scalar values and grapheme/user-visible positions must not be conflated.
- Preserve source spans and useful diagnostics through parsing/transformation where practical.
- Distinguish lossless syntax representation from semantic document representation when necessary.
- Avoid format-specific assumptions in reusable document layers.
- Record language/compiler/runtime friction in `docs/LANGUAGE_PRESSURES.md`.
- Include malformed, adversarial and multilingual fixtures in tests.

## Family entry contract

- Establish the bounded Language Service family context and current Commons
  architecture/pressure identities before broad repository search.
- Query the current MNCS capability index and existing Commons pressure before
  adding host projection logic; repair a reusable missing facility upstream
  where practical.
- Keep documentation generators deterministic and identity-bound. Host code is
  an explicit file/Markdown projection boundary until the generic structured
  document pressure is repaired; it must not become a second family authority.
