# Architecture

`mncs-doc` is the canonical MNCS documentation system.  Documentation is a
derived, identity-aware, verifiable view of the actual system:

canonical source + semantic metadata + persistent evidence
-> documentation model
-> rendered documentation

There is one canonical implementation.  There is no `doc-v2`, no parallel
generator, and no separate manually synchronized documentation database.

## Pipeline

```
compiler declaration inventory (mncs.declaration-inventory/1)
compiler test inventory        (mncs.test-inventory/1)
+ leading source comments      (explicit Doc-owned boundary)
+ repository manifest identity (.mncs/project.json)
        |
        v
documentation model            (mncs.documentation-model/1)
        |
        +-> Markdown renderer (stable identity-derived anchors)
        +-> HTML renderer     (static, escaped)
        +-> plain-text renderer
        +-> semantic index    (mncs.documentation-index/1)
        +-> bounded queries   (identity / qualified / name / module / kind)
        +-> structural validation (mncs.documentation-validation/1)
```

The host adapter is [`tools/mncs_doc.py`](../tools/mncs_doc.py).  The native
semantic core is [`native/mncs/doc/model.mncs`](../native/mncs/doc/model.mncs).

## Ownership boundary

Doc owns:

- the documentation semantic model;
- extraction/assembly of canonical documentation information;
- cross-reference resolution by semantic identity;
- documentation validation (links, examples, staleness, required docs);
- example-to-test linkage by test-case identity;
- documentation rendering (Markdown, HTML, plain text);
- semantic indexes and navigation structures;
- deterministic generation and stale-artifact detection.

Doc does not own:

- language semantics or compiler symbol authority (`mncs-language`,
  `mncs-compiler` are read-only; identities, fingerprints, signatures,
  effects, and capabilities are consumed, never re-declared);
- project topology or architectural ownership (Commons/Atlas);
- persistence or provenance graphs (Store/Lineage);
- test execution or verdicts (`mncs-test`; Doc links examples and may
  invoke the compiler-owned runner opt-in, but never judges tests);
- project conformance (Doctor consumes Doc validation output; Doc does
  not check project policy beyond its own `--require-docs` option).

## Source-of-truth hierarchy

1. Compiler declaration/test inventory: identities, declarations,
   signatures, generics, effects, capabilities, source spans, fingerprints.
2. Leading `//` source comments attached to declarations (Doc extraction;
   see `docs/PRESSURES.md` for why the compiler does not supply these).
3. Repository manifest (`.mncs/project.json`): repository identity/revision.
4. Commons architecture and pressure identities: referenced, never copied.

If Doc has to be told manually that a function exists, that is tooling
pressure, not a documentation task.  Signatures are never hand-maintained:
when compiler signatures change, generated docs update or fail validation.

## Historical responsibilities, classified

Recovered from repository history, schemas, renderers, and consumers:

1. Legitimate modern Doc responsibility: the semantic documentation model,
   xref resolution, validation, example linkage, renderers, indexes, and
   deterministic project projections (`tools/project.py`, retained).
2. Language/compiler metadata responsibility: declaration/callable/test
   inventories, semantic identities, effect/capability truth.
3. Commons/Atlas responsibility: family architecture, capability ownership,
   pressure records, publishing/surfacing generated docs.
4. Store/Lineage responsibility: persisting artifacts and provenance.
5. Rendering concern: Markdown/HTML/text serializers, escaping, anchors.
6. Obsolete scaffolding: any hand-maintained API registry, duplicated
   signature text, regex-based declaration parsing, or static symbol map.
   None existed in this repository; none was built.

## Native vs host boundary

Native MNCS (`native/mncs/doc/model.mncs`) owns the verdict lattice:
`LinkStatus`, `DocSeverity`, `ExampleState`, `DocLink`, `ValidationTally`,
and the total folding functions over them, with self-contained tests.
The module follows the `mncs-test` precedent (native semantic core plus a
narrow host adapter).

Host Python owns filesystem access, compiler-inventory invocation,
comment attachment, model assembly, rendering/escaping, index/query
plumbing, and opt-in example execution.  Rendering stays host-side
deliberately: MNCS text handling is byte-oriented and bounded, and moving
string templating into MNCS would fight the language instead of
documenting it.

## Determinism and staleness

Models and rendered pages contain no timestamps and no filesystem-order
dependence: declarations sort by identity, xrefs by (from, to).  Generation
identity/time goes only to a `--provenance-out` sidecar.  Staleness is
detected by re-inventory: inventory-identity comparison per module and
signature-hash comparison per identity, plus missing/added identity diffs.
