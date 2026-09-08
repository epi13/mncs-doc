# Agent and contributor contract

- Prefer `mncs-language` for implementation.
- Treat Unicode correctly; byte offsets, scalar values and grapheme/user-visible positions must not be conflated.
- Preserve source spans and useful diagnostics through parsing/transformation where practical.
- Distinguish lossless syntax representation from semantic document representation when necessary.
- Avoid format-specific assumptions in reusable document layers.
- Record language/compiler/runtime friction in `docs/LANGUAGE_PRESSURES.md`.
- Include malformed, adversarial and multilingual fixtures in tests.
