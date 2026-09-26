#!/usr/bin/env python3
"""Canonical MNCS documentation system: semantic model, validation, renderers.

Pipeline
--------

compiler declaration/test inventory (canonical authority)
+ leading source comments (explicit Doc-owned boundary; the compiler lexer
  discards comments, see docs/PRESSURES.md)
+ repository manifest identity (.mncs/project.json)
-> documentation model (mncs.documentation-model/1)
-> Markdown / HTML / plain-text renderers, semantic index, bounded queries,
   structural validation (mncs.documentation-validation/1)

Doc owns the documentation semantic model, cross-reference resolution,
validation, example/test-identity linkage, renderers, and indexes.  It does
not own language semantics, compiler symbol authority, project topology,
execution, or test verdicts; those are consumed read-only from their owners.

All generated output is deterministic for the same inputs: declarations are
identity-sorted, no timestamps are embedded in models or rendered pages, and
anchors derive from semantic identities.  Generation identity/time is
recorded only via --provenance-out, never inside the model itself.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

MODEL_SCHEMA = "mncs.documentation-model/1"
VALIDATION_SCHEMA = "mncs.documentation-validation/1"
INDEX_SCHEMA = "mncs.documentation-index/1"
PROVENANCE_SCHEMA = "mncs.documentation-provenance/1"
TOOL_VERSION = "1"

# Matches one cross reference inside authored doc text:
#   [[module.path::Name]]  qualified reference
#   [[Name]]               short reference (ambiguous when shared)
#   [[mncs:0.2:...]]       direct canonical identity reference
XREF_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
IDENTITY_RE = re.compile(r"^mncs:[0-9a-z.]+\S*$")
COMMENT_RE = re.compile(r"^///? ?")
MODULE_RE = re.compile(r"^module\s+([A-Za-z0-9_.]+)\s*;")
EXAMPLE_RE = re.compile(r"^\s*@example\s+(\S+)\s*$")


def _sha8(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def anchor_of(identity: str) -> str:
    """Stable page anchor derived from the canonical semantic identity."""
    return "doc-" + _sha8(identity)


# ---------------------------------------------------------------------------
# Compiler inventory access (read-only; language/compiler stay untouched)
# ---------------------------------------------------------------------------

def find_mncs_binary(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("MNCS_BIN")
    if env:
        return env
    from shutil import which

    found = which("mncs")
    if found:
        return found
    return "mncs"


def run_inventory(mncs_bin: str, command: str, source: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [mncs_bin, command, str(source)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(f"{command} failed for {source}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{command} emitted non-JSON for {source}: {error}")


def read_manifest(source: Path) -> dict[str, Any]:
    """Walk up from the source for an owning .mncs/project.json manifest."""
    directory = source.resolve().parent
    while True:
        candidate = directory / ".mncs" / "project.json"
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}
        parent = directory.parent
        if parent == directory:
            return {}
        directory = parent


# ---------------------------------------------------------------------------
# Leading documentation comments (explicit Doc-owned extraction boundary)
# ---------------------------------------------------------------------------

def extract_leading_docs(text: str) -> dict[int, str]:
    """Map declaration start line -> attached leading `//` comment block.

    A block is the maximal run of contiguous `//` lines directly above the
    declaration line (no blank line in between).  Module documentation is
    handled separately via the `module` statement line.
    """
    lines = text.split("\n")
    comment_at: dict[int, str] = {}
    index = 0
    while index < len(lines):
        if COMMENT_RE.match(lines[index].lstrip()) and lines[index].strip().startswith("//"):
            start = index
            while index < len(lines) and lines[index].strip().startswith("//"):
                index += 1
            target = index  # 0-based line of first non-comment line
            block = "\n".join(
                COMMENT_RE.sub("", lines[i].lstrip(), count=1) for i in range(start, index)
            ).strip("\n")
            # Only attach when the target line looks like a declaration and
            # the block is non-empty.  Blank-line separation means index
            # already stopped at the blank line, so target is wrong there.
            if block and target < len(lines) and lines[target].strip():
                comment_at[target + 1] = block  # 1-based line numbers
        else:
            index += 1
    return comment_at


def split_summary(text: str) -> tuple[str, str]:
    """First paragraph is the summary; the remainder is the body."""
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if not paragraphs:
        return "", ""
    if len(paragraphs) == 1:
        first = paragraphs[0].split("\n", 1)
        return first[0].strip(), (first[1].strip() if len(first) > 1 else "")
    return paragraphs[0].replace("\n", " ").strip(), "\n\n".join(paragraphs[1:])


def find_example_refs(doc_text: str) -> list[str]:
    refs: list[str] = []
    for line in doc_text.split("\n"):
        match = EXAMPLE_RE.match(line)
        if match:
            refs.append(match.group(1))
    return refs


def doc_text_without_directives(doc_text: str) -> str:
    kept = [line for line in doc_text.split("\n") if not EXAMPLE_RE.match(line)]
    return "\n".join(kept).strip("\n")


# ---------------------------------------------------------------------------
# Signature model (derived from canonical callable metadata, never hand-kept)
# ---------------------------------------------------------------------------

def signature_of(callable: dict[str, Any]) -> dict[str, Any]:
    generics = [
        {"name": g.get("name"), "kind": g.get("kind")}
        for g in callable.get("generic_params") or []
    ]
    inputs = [
        {"name": i.get("name"), "type": i.get("type")}
        for i in callable.get("inputs") or []
    ]
    outputs = [
        {"name": o.get("name"), "type": o.get("type")}
        for o in callable.get("outputs") or []
    ]
    effects = callable.get("effects") or []
    capabilities = callable.get("capabilities") or []
    canonical = json.dumps(
        {
            "generics": generics,
            "inputs": inputs,
            "outputs": outputs,
            "effects": effects,
            "capabilities": capabilities,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "callable_kind": callable.get("callable_kind"),
        "generic_params": generics,
        "inputs": inputs,
        "outputs": outputs,
        "effects": effects,
        "capabilities": capabilities,
        "signature_hash": _sha256(canonical),
    }


def render_signature(name: str, signature: dict[str, Any] | None, kind: str) -> str:
    """Human-readable signature text derived from the signature record."""
    if signature is None:
        return name
    generics = signature.get("generic_params") or []
    generic_text = ""
    if generics:
        parts = [g["name"] if not g.get("kind") else f"{g['name']}: {g['kind']}"
                 for g in generics]
        generic_text = "<" + ", ".join(parts) + ">"
    inputs = ", ".join(f"{i['name']}: {i['type']}" for i in signature.get("inputs") or [])
    outputs = signature.get("outputs") or []
    if outputs:
        outputs_text = "(" + ", ".join(f"{o['name']}: {o['type']}" for o in outputs) + ")"
        head = f"fn {name}{generic_text}({inputs}) -> {outputs_text}"
    else:
        head = f"fn {name}{generic_text}({inputs})"
    if kind == "test":
        head = "test " + head[len("fn "):] if head.startswith("fn ") else head
    lines = [head]
    for capability in signature.get("capabilities") or []:
        lines.append(f"    capability {capability}")
    for effect in signature.get("effects") or []:
        if isinstance(effect, dict):
            # The compiler records the requesting function as the effect
            # target; rendering mirrors source syntax by eliding a target
            # that is just the documented function itself.
            target = effect.get("target")
            target_text = (f" on {target}" if target and target != name else "")
            auth = f" authorized_by {effect['capability']}" if effect.get("capability") else ""
            lines.append(f"    effect {effect.get('kind')}{target_text}{auth}")
        else:
            lines.append(f"    effect {effect}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model extraction
# ---------------------------------------------------------------------------

def _declaration_sort_key(declaration: dict[str, Any]) -> tuple[str, str]:
    return (declaration.get("identity") or "", declaration.get("name") or "")


def build_model(
    sources: list[Path],
    mncs_bin: str,
    repository_override: str | None = None,
    revision_override: Any = None,
) -> dict[str, Any]:
    declarations: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    subjects: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    for source in sources:
        text = source.read_text(encoding="utf-8")
        texts[str(source)] = text
        decl_result = run_inventory(mncs_bin, "declaration-inventory", source)
        if not decl_result.get("valid") or not decl_result.get("inventory"):
            details = json.dumps(decl_result.get("diagnostics", []))[:1000]
            raise RuntimeError(f"invalid MNCS source {source}: {details}")
        inventory = decl_result["inventory"]
        test_result = run_inventory(mncs_bin, "test-inventory", source)
        test_entries = []
        test_inventory_identity = None
        if test_result.get("valid") and test_result.get("inventory"):
            test_entries = test_result["inventory"].get("tests", [])
            test_inventory_identity = test_result["inventory"].get("inventory_identity")
        manifest = read_manifest(source)
        subjects.append(
            {
                "source_path": str(source),
                "repository": repository_override
                or manifest.get("repository"),
                "revision": revision_override
                if revision_override is not None
                else manifest.get("revision"),
                "module": inventory.get("module"),
                "source_profile": inventory.get("source_profile"),
                "source_artifact_identity": inventory.get("source_artifact_identity"),
                "subject_identity": inventory.get("subject_identity"),
                "subject_fingerprint": inventory.get("subject_fingerprint"),
                "inventory_identity": inventory.get("inventory_identity"),
                "test_inventory_identity": test_inventory_identity,
            }
        )
        comment_at = extract_leading_docs(text)
        module_line = None
        for lineno, line in enumerate(text.split("\n"), start=1):
            if MODULE_RE.match(line.strip()):
                module_line = lineno
                break
        callables = {
            c.get("declaration_identity"): c for c in inventory.get("callables", [])
        }
        tests_by_function = {
            t.get("function_identity"): t for t in test_entries if t.get("function_identity")
        }
        for declaration in inventory.get("declarations", []):
            identity = declaration.get("identity")
            kind = declaration.get("kind")
            lineno = (declaration.get("source_span") or {}).get("line")
            raw_doc = None
            if kind == "module" and module_line is not None:
                raw_doc = comment_at.get(module_line)
            elif lineno is not None:
                raw_doc = comment_at.get(lineno)
            callable = callables.get(identity)
            signature = signature_of(callable) if callable is not None else None
            if raw_doc is not None:
                body_text = doc_text_without_directives(raw_doc)
                summary, body = split_summary(body_text)
            else:
                summary, body = "", ""
            entry: dict[str, Any] = {
                "identity": identity,
                "kind": kind,
                "module": declaration.get("module"),
                "name": declaration.get("name"),
                "qualified_name": (
                    declaration.get("module") + "::" + declaration.get("name")
                    if kind != "module"
                    else declaration.get("name")
                ),
                "source_span": declaration.get("source_span"),
                "exported": declaration.get("exported"),
                "source_path": str(source),
                "signature": signature,
                "doc": (
                    {
                        "summary": summary,
                        "body": body,
                        "source": "leading-comment",
                        "raw_refs": sorted(set(XREF_RE.findall(raw_doc or ""))),
                        "example_refs": find_example_refs(raw_doc or ""),
                    }
                    if raw_doc is not None
                    else None
                ),
                "type_relations": {"member_of": None, "members": []},
                "test_case_identity": (
                    callable.get("test_case_identity") if callable else None
                ),
                "examples": [],
            }
            test_link = tests_by_function.get(identity)
            if test_link is not None:
                entry["test_case_identity"] = test_link.get("test_case_identity")
            declarations.append(entry)
        for test_entry in test_entries:
            tests.append({**test_entry, "source_path": str(source)})

    _attach_type_relations(declarations)
    _attach_examples(declarations, tests)
    model = {
        "schema_version": MODEL_SCHEMA,
        "generator": {"name": "mncs-doc", "tool": "tools/mncs_doc.py",
                      "tool_version": TOOL_VERSION},
        "subjects": sorted(subjects, key=lambda s: s.get("module") or ""),
        "declarations": sorted(declarations, key=_declaration_sort_key),
        "tests": sorted(tests, key=lambda t: t.get("test_case_identity") or ""),
        "xrefs": resolve_xrefs(declarations),
    }
    exported = [d for d in declarations if d.get("exported") and d.get("kind") != "module"]
    documented = [d for d in exported if d.get("doc")]
    model["coverage"] = {
        "exported_total": len(exported),
        "exported_documented": len(documented),
    }
    return model


def _attach_type_relations(declarations: list[dict[str, Any]]) -> None:
    """Expose record fields from compiler identities.

    Record-type identities embed the field list
    (e.g. `...::Point::x:i64;y:i64;`, percent-encoded); no source text is
    re-parsed and no per-field declaration is invented.  The compiler emits
    no separate field/member declarations, so `members` stays empty by
    construction.  Enum (finite_type) identities carry no variant detail,
    so variant membership is unavailable until the compiler exposes it
    (see docs/PRESSURES.md).
    """
    from urllib.parse import unquote

    for declaration in declarations:
        identity = declaration.get("identity") or ""
        if declaration.get("kind") != "record_type" or "::" not in identity:
            continue
        segments = identity.split("::")
        if len(segments) < 3:
            continue
        raw_fields = unquote(segments[-1]).rstrip(";")
        fields = []
        for item in raw_fields.split(";"):
            if not item or ":" not in item:
                continue
            field_name, _, field_type = item.partition(":")
            fields.append({"name": field_name, "type": field_type})
        declaration["type_relations"]["fields"] = fields


def _attach_examples(
    declarations: list[dict[str, Any]], tests: list[dict[str, Any]]
) -> None:
    by_qualified = {t.get("qualified_name"): t for t in tests}
    by_name = {}
    for test in tests:
        by_name.setdefault(test.get("name"), []).append(test)
    for declaration in declarations:
        doc = declaration.get("doc")
        if not doc:
            continue
        for ref in doc.get("example_refs", []):
            target = by_qualified.get(ref)
            if target is None and ref in by_name and len(by_name[ref]) == 1:
                target = by_name[ref][0]
            if target is None:
                declaration["examples"].append(
                    {"test": ref, "status": "missing",
                     "test_case_identity": None, "semantic_fingerprint": None}
                )
            else:
                declaration["examples"].append(
                    {"test": ref, "status": "linked",
                     "test_case_identity": target.get("test_case_identity"),
                     "semantic_fingerprint": target.get("semantic_fingerprint")}
                )


def resolve_xrefs(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_qualified: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_identity: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        by_qualified.setdefault(declaration["qualified_name"], []).append(declaration)
        by_name.setdefault(declaration["name"], []).append(declaration)
        by_identity[declaration["identity"]] = declaration
    xrefs: list[dict[str, Any]] = []
    for declaration in declarations:
        doc = declaration.get("doc")
        if not doc:
            continue
        for raw in doc.get("raw_refs", []):
            if IDENTITY_RE.match(raw) and "::" in raw:
                target = by_identity.get(raw)
                if target is not None:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "resolved",
                                  "resolved_identity": target["identity"],
                                  "candidates": []})
                else:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "stale",
                                  "resolved_identity": None, "candidates": []})
            elif "::" in raw:
                matches = by_qualified.get(raw, [])
                if len(matches) == 1:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "resolved",
                                  "resolved_identity": matches[0]["identity"],
                                  "candidates": []})
                elif not matches:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "missing",
                                  "resolved_identity": None, "candidates": []})
                else:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "ambiguous",
                                  "resolved_identity": None,
                                  "candidates": sorted(m["identity"] for m in matches)})
            else:
                matches = by_name.get(raw, [])
                if len(matches) == 1:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "resolved",
                                  "resolved_identity": matches[0]["identity"],
                                  "candidates": []})
                elif not matches:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "missing",
                                  "resolved_identity": None, "candidates": []})
                else:
                    xrefs.append({"from": declaration["identity"], "to": raw,
                                  "kind": "doc-link", "status": "ambiguous",
                                  "resolved_identity": None,
                                  "candidates": sorted(m["identity"] for m in matches)})
    xrefs.sort(key=lambda x: (x["from"], x["to"]))
    return xrefs


# ---------------------------------------------------------------------------
# Renderers: semantic model -> output (never the reverse)
# ---------------------------------------------------------------------------

def _linkify_doc_text(
    text: str, mode: str, resolve: dict[str, str]
) -> str:
    """Replace [[refs]] with links; unresolved refs render as plain code."""

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1)
        target = resolve.get(raw)
        if target is None:
            return f"`{raw}`"
        if mode == "html":
            return f'<a href="#{html.escape(target)}"><code>{html.escape(raw)}</code></a>'
        if mode == "text":
            return raw
        return f"[`{raw}`](#{target})"

    return XREF_RE.sub(replace, text)


def _xref_anchor_map(model: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    by_identity = {d["identity"]: d for d in model.get("declarations", [])}
    for xref in model.get("xrefs", []):
        if xref["status"] == "resolved":
            mapping[xref["to"]] = anchor_of(xref["resolved_identity"])
    for declaration in model.get("declarations", []):
        mapping.setdefault(declaration["qualified_name"], anchor_of(declaration["identity"]))
        if declaration["name"] not in mapping:
            same = [d for d in model.get("declarations", [])
                    if d["name"] == declaration["name"]]
            if len(same) == 1:
                mapping[declaration["name"]] = anchor_of(declaration["identity"])
    return mapping


def render_markdown(model: dict[str, Any]) -> str:
    resolve = _xref_anchor_map(model)
    by_identity = {d["identity"]: d for d in model.get("declarations", [])}
    lines: list[str] = []
    subjects = model.get("subjects", [])
    modules = sorted({s.get("module") or "" for s in subjects})
    lines.append(f"# API reference: {', '.join(modules)}")
    lines.append("")
    lines.append(f"Model schema: `{MODEL_SCHEMA}`")
    lines.append("")
    lines.append("Signatures, effects, capabilities, and identities below are "
                 "derived from compiler declaration inventory, not hand-maintained.")
    lines.append("")
    lines.append("## Subjects")
    lines.append("")
    for subject in subjects:
        lines.append(f"- Module `{subject.get('module')}` (profile `{subject.get('source_profile')}`)")
        lines.append(f"  - Subject identity: `{subject.get('subject_identity')}`")
        lines.append(f"  - Subject fingerprint: `{subject.get('subject_fingerprint')}`")
        lines.append(f"  - Inventory identity: `{subject.get('inventory_identity')}`")
        if subject.get("repository") is not None:
            lines.append(f"  - Repository: `{subject.get('repository')}` "
                         f"(revision `{subject.get('revision')}`)")
    lines.append("")
    lines.append("## Index")
    lines.append("")
    for declaration in model.get("declarations", []):
        kind = declaration.get("kind")
        anchor = anchor_of(declaration["identity"])
        summary = (declaration.get("doc") or {}).get("summary", "")
        suffix = (" — " + _linkify_doc_text(summary, "markdown", resolve)
                  if summary else "")
        lines.append(f"- `{kind}` [`{declaration['qualified_name']}`](#{anchor}){suffix}")
    lines.append("")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for declaration in model.get("declarations", []):
        grouped.setdefault(declaration.get("kind") or "unknown", []).append(declaration)
    section_titles = {
        "module": "Modules", "function": "Functions", "test": "Tests",
        "record_type": "Records", "finite_type": "Enums",
    }
    for kind in ["module", "record_type", "finite_type", "function", "test"]:
        members = grouped.pop(kind, [])
        if not members:
            continue
        lines.append(f"## {section_titles.get(kind, kind)}")
        lines.append("")
        for declaration in members:
            anchor = anchor_of(declaration["identity"])
            lines.append(f'<a id="{anchor}"></a>')
            lines.append("")
            lines.append(f"### `{declaration['qualified_name']}`")
            lines.append("")
            lines.append(f"- Identity: `{declaration['identity']}`")
            if declaration.get("exported") is not None:
                lines.append(f"- Exported: `{str(declaration['exported']).lower()}`")
            span = declaration.get("source_span") or {}
            if span and declaration.get("kind") != "module":
                lines.append(f"- Source: `{declaration.get('source_path')}` "
                             f"(line {span.get('line')})")
            elif span:
                lines.append(f"- Source: `{declaration.get('source_path')}`")
            doc = declaration.get("doc")
            signature = declaration.get("signature")
            if signature is not None:
                lines.append("")
                lines.append("```mncs")
                lines.append(render_signature(declaration["name"], signature,
                                              declaration.get("kind")))
                lines.append("```")
            relations = declaration.get("type_relations") or {}
            if relations.get("fields"):
                lines.append("")
                lines.append("Fields:")
                lines.append("")
                for field in relations["fields"]:
                    lines.append(f"- `{field['name']}: {field['type']}`")
            if doc is not None:
                if doc.get("summary"):
                    lines.append("")
                    lines.append(_linkify_doc_text(doc["summary"], "markdown", resolve))
                if doc.get("body"):
                    lines.append("")
                    lines.append(_linkify_doc_text(doc["body"], "markdown", resolve))
            else:
                lines.append("")
                lines.append("_No authored documentation._")
            if declaration.get("examples"):
                lines.append("")
                lines.append("Examples:")
                lines.append("")
                for example in declaration["examples"]:
                    if example["status"] == "linked":
                        lines.append(f"- Test `{example['test']}` "
                                     f"(case `{example['test_case_identity']}`)")
                    else:
                        lines.append(f"- Test `{example['test']}` — "
                                     f"**{example['status']}**: no such test in scope")
            if declaration.get("test_case_identity") and declaration.get("kind") != "test":
                lines.append("")
                lines.append(f"Verified by test case `{declaration['test_case_identity']}`.")
            lines.append("")
    if grouped:
        lines.append("## Other declarations")
        lines.append("")
        for kind in sorted(grouped):
            for declaration in grouped[kind]:
                lines.append(f"- `{kind}` `{declaration['qualified_name']}` "
                             f"(`{declaration['identity']}`)")
        lines.append("")
    broken = [x for x in model.get("xrefs", []) if x["status"] != "resolved"]
    if broken:
        lines.append("## Unresolved references")
        lines.append("")
        for xref in broken:
            source = by_identity.get(xref["from"], {}).get("qualified_name", xref["from"])
            lines.append(f"- `{source}` → `[[{xref['to']}]]`: **{xref['status']}**")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_html(model: dict[str, Any]) -> str:
    resolve = _xref_anchor_map(model)
    parts = ["<!DOCTYPE html>", "<html lang=\"en\">", "<head>",
             "<meta charset=\"utf-8\">",
             f"<title>{html.escape('API reference')}</title>", "</head>", "<body>"]
    subjects = model.get("subjects", [])
    modules = sorted({s.get("module") or "" for s in subjects})
    parts.append(f"<h1>API reference: {html.escape(', '.join(modules))}</h1>")
    parts.append(f"<p>Model schema: <code>{html.escape(MODEL_SCHEMA)}</code>. "
                 "Derived from compiler declaration inventory.</p>")
    parts.append("<h2>Index</h2><ul>")
    for declaration in model.get("declarations", []):
        anchor = anchor_of(declaration["identity"])
        summary = html.escape(((declaration.get("doc") or {}).get("summary", "")))
        parts.append(f"<li><code>{html.escape(declaration.get('kind',''))}</code> "
                     f"<a href=\"#{anchor}\"><code>"
                     f"{html.escape(declaration['qualified_name'])}</code></a> {summary}</li>")
    parts.append("</ul>")
    for declaration in model.get("declarations", []):
        anchor = anchor_of(declaration["identity"])
        parts.append(f"<section id=\"{anchor}\">")
        parts.append(f"<h2><code>{html.escape(declaration['qualified_name'])}</code></h2>")
        parts.append(f"<p>Identity: <code>{html.escape(declaration['identity'])}</code></p>")
        signature = declaration.get("signature")
        if signature is not None:
            parts.append("<pre>" + html.escape(
                render_signature(declaration["name"], signature,
                                 declaration.get("kind"))) + "</pre>")
        doc = declaration.get("doc")
        if doc is not None:
            if doc.get("summary"):
                parts.append("<p>" + _linkify_doc_text(
                    html.escape(doc["summary"]), "html", resolve) + "</p>")
            if doc.get("body"):
                for paragraph in doc["body"].split("\n\n"):
                    parts.append("<p>" + _linkify_doc_text(
                        html.escape(paragraph).replace("\n", "<br>"),
                        "html", resolve) + "</p>")
        else:
            parts.append("<p><em>No authored documentation.</em></p>")
        parts.append("</section>")
    parts.extend(["</body>", "</html>"])
    return "\n".join(parts) + "\n"


def render_text(model: dict[str, Any]) -> str:
    lines: list[str] = []
    for subject in model.get("subjects", []):
        lines.append(f"module {subject.get('module')} "
                     f"(profile {subject.get('source_profile')})")
        lines.append(f"  identity {subject.get('subject_identity')}")
    lines.append("")
    for declaration in model.get("declarations", []):
        doc = declaration.get("doc") or {}
        signature = declaration.get("signature")
        if signature is not None:
            lines.append(render_signature(declaration["name"], signature,
                                          declaration.get("kind")))
        else:
            lines.append(f"{declaration.get('kind')} {declaration['qualified_name']}")
        lines.append(f"  identity: {declaration['identity']}")
        if doc.get("summary"):
            lines.append(f"  {doc['summary']}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Semantic index and bounded query (agent-facing retrieval)
# ---------------------------------------------------------------------------

def build_index(model: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for declaration in model.get("declarations", []):
        doc = declaration.get("doc") or {}
        signature = declaration.get("signature") or {}
        entries.append(
            {
                "identity": declaration["identity"],
                "qualified_name": declaration["qualified_name"],
                "name": declaration["name"],
                "kind": declaration.get("kind"),
                "module": declaration.get("module"),
                "summary": doc.get("summary", ""),
                "anchor": anchor_of(declaration["identity"]),
                "exported": declaration.get("exported"),
                "generic_arity": len(signature.get("generic_params") or []),
                "has_effects": bool(signature.get("effects")),
                "has_capabilities": bool(signature.get("capabilities")),
                "has_doc": declaration.get("doc") is not None,
                "has_example": bool(declaration.get("examples")),
            }
        )
    entries.sort(key=lambda e: e["identity"])
    return {
        "schema_version": INDEX_SCHEMA,
        "model_identities": [s.get("inventory_identity")
                             for s in model.get("subjects", [])],
        "entries": entries,
    }


def query_model(
    model: dict[str, Any],
    identity: str | None = None,
    qualified: str | None = None,
    name: str | None = None,
    module: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    results = []
    for declaration in model.get("declarations", []):
        if identity is not None and declaration["identity"] != identity:
            continue
        if qualified is not None and declaration["qualified_name"] != qualified:
            continue
        if name is not None and declaration["name"] != name:
            continue
        if module is not None and declaration.get("module") != module:
            continue
        if kind is not None and declaration.get("kind") != kind:
            continue
        doc = declaration.get("doc") or {}
        results.append(
            {
                "identity": declaration["identity"],
                "qualified_name": declaration["qualified_name"],
                "kind": declaration.get("kind"),
                "module": declaration.get("module"),
                "signature_text": render_signature(
                    declaration["name"], declaration.get("signature"),
                    declaration.get("kind")),
                "summary": doc.get("summary", ""),
                "anchor": anchor_of(declaration["identity"]),
                "test_case_identity": declaration.get("test_case_identity"),
                "examples": declaration.get("examples", []),
            }
        )
        if len(results) >= limit:
            break
    return results


# ---------------------------------------------------------------------------
# Validation (Doc semantics) — distinct from Test verdicts and Doctor checks
# ---------------------------------------------------------------------------

def validate_model(
    model: dict[str, Any],
    mncs_bin: str | None = None,
    sources: list[Path] | None = None,
    require_docs: str = "none",
) -> dict[str, Any]:
    """Validate documentation structure, links, examples, and staleness.

    require_docs: "none" (report only), "exported", or "all".
    Staleness is checked only when sources are provided (re-inventory and
    compare identities and per-declaration signature hashes).
    """
    checks: list[dict[str, Any]] = []

    for xref in model.get("xrefs", []):
        if xref["status"] == "resolved":
            checks.append({"check": "xref-resolved", "from": xref["from"],
                           "to": xref["to"], "status": "PASS"})
        else:
            checks.append({"check": "xref-resolved", "from": xref["from"],
                           "to": xref["to"], "status": "FAIL",
                           "reason": xref["status"],
                           "candidates": xref.get("candidates", [])})

    for declaration in model.get("declarations", []):
        for example in declaration.get("examples", []):
            if example["status"] == "linked":
                checks.append({"check": "example-linked",
                               "from": declaration["identity"],
                               "to": example["test"], "status": "PASS",
                               "note": "linked by test identity; execution "
                                       "verdicts belong to mncs-test"})
            else:
                checks.append({"check": "example-linked",
                               "from": declaration["identity"],
                               "to": example["test"], "status": "FAIL",
                               "reason": example["status"]})

    if require_docs in ("exported", "all"):
        for declaration in model.get("declarations", []):
            if declaration.get("kind") == "module":
                continue
            needs = (require_docs == "all" or
                     (require_docs == "exported" and declaration.get("exported")))
            if needs and declaration.get("doc") is None:
                checks.append({"check": "required-docs",
                               "from": declaration["identity"], "status": "FAIL",
                               "reason": "missing authored documentation"})
    else:
        undocumented = sum(1 for d in model.get("declarations", [])
                           if d.get("kind") != "module" and d.get("doc") is None)
        checks.append({"check": "required-docs", "status": "PASS",
                       "note": f"policy=none; {undocumented} undocumented "
                               "non-module declarations reported, not failed"})

    if sources is not None and mncs_bin is not None:
        try:
            fresh = build_model([Path(s) for s in sources], mncs_bin)
        except RuntimeError as error:
            checks.append({"check": "inventory-current", "status": "FAIL",
                           "reason": f"re-inventory failed: {error}"})
            fresh = None
        if fresh is not None:
            old_subjects = {s.get("module"): s for s in model.get("subjects", [])}
            new_subjects = {s.get("module"): s for s in fresh.get("subjects", [])}
            for module_name, old in sorted(old_subjects.items()):
                new = new_subjects.get(module_name)
                if new is None:
                    checks.append({"check": "inventory-current", "status": "FAIL",
                                   "reason": f"module {module_name} no longer present"})
                    continue
                if new.get("inventory_identity") != old.get("inventory_identity"):
                    checks.append({"check": "inventory-current", "status": "FAIL",
                                   "reason": f"module {module_name} inventory changed "
                                             f"({old.get('inventory_identity')} -> "
                                             f"{new.get('inventory_identity')})"})
                else:
                    checks.append({"check": "inventory-current", "status": "PASS",
                                   "note": f"module {module_name} inventory unchanged"})
            old_sigs = {d["identity"]: (d.get("signature") or {}).get("signature_hash")
                        for d in model.get("declarations", [])}
            new_sigs = {d["identity"]: (d.get("signature") or {}).get("signature_hash")
                        for d in fresh.get("declarations", [])}
            for identity in sorted(set(old_sigs) | set(new_sigs)):
                if identity not in new_sigs:
                    checks.append({"check": "signature-current", "from": identity,
                                   "status": "FAIL", "reason": "identity removed"})
                elif identity not in old_sigs:
                    checks.append({"check": "signature-current", "from": identity,
                                   "status": "FAIL",
                                   "reason": "identity added since model was built"})
                elif old_sigs[identity] != new_sigs[identity]:
                    checks.append({"check": "signature-current", "from": identity,
                                   "status": "FAIL",
                                   "reason": "signature changed since model was built"})
            if all(c["status"] == "PASS" for c in checks
                   if c["check"] == "signature-current"):
                checks.append({"check": "signature-current", "status": "PASS",
                               "note": "all shared identities have identical signatures"})

    failed = sum(1 for c in checks if c["status"] == "FAIL")
    return {
        "schema_version": VALIDATION_SCHEMA,
        "subjects": model.get("subjects", []),
        "checks": checks,
        "summary": {"total": len(checks), "failed": failed,
                    "passed": len(checks) - failed},
        "verdict": "FAIL" if failed else "PASS",
    }


def verify_example_execution(
    model: dict[str, Any],
    mncs_bin: str,
    libraries: list[str] | None = None,
    timeout_s: int = 120,
) -> list[dict[str, Any]]:
    """Execute linked documentation examples via the compiler-owned runner.

    This is explicitly opt-in: Doc never executes code during extraction or
    rendering.  Each source with linked examples runs once through
    `mncs test`; per-test entries map back to examples by (module, name).
    A runner that cannot execute a module (e.g. no suite harness) yields
    `unverifiable`, never a documentation failure: execution verdicts belong
    to mncs-test, linkage belongs to Doc.
    """
    checks: list[dict[str, Any]] = []
    by_source: dict[str, list[dict[str, Any]]] = {}
    for declaration in model.get("declarations", []):
        for example in declaration.get("examples", []):
            if example["status"] == "linked":
                by_source.setdefault(declaration["source_path"], []).append(
                    (declaration, example))
    for source_path in sorted(by_source):
        command = [mncs_bin, "test", "--source", source_path]
        for library in libraries or []:
            command += ["--library", library]
        try:
            proc = subprocess.run(command, capture_output=True, text=True,
                                  timeout=timeout_s)
            result = json.loads(proc.stdout)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            for declaration, example in by_source[source_path]:
                checks.append({"check": "example-execution",
                               "from": declaration["identity"],
                               "to": example["test"], "status": "PASS",
                               "execution": "unverifiable",
                               "note": f"runner did not return a result: {error}"})
            continue
        entries = {t.get("entry"): t for t in result.get("tests", [])
                   if isinstance(t, dict)}
        run_evidence = {
            "run_id": result.get("run_id"),
            "classification": result.get("classification"),
            "verdict": result.get("verdict"),
            "summary": result.get("summary"),
        }
        for declaration, example in by_source[source_path]:
            ref = example["test"]
            short = ref.split("::")[-1]
            entry = entries.get(short)
            if entry is None:
                checks.append({"check": "example-execution",
                               "from": declaration["identity"],
                               "to": ref, "status": "PASS",
                               "execution": "unverifiable",
                               "note": "linked by test identity but absent from "
                                       "this runner result; execution belongs "
                                       "to mncs-test",
                               "run": run_evidence})
                continue
            verdict = entry.get("verdict") or entry.get("status")
            if verdict in ("PASS", "passed"):
                checks.append({"check": "example-execution",
                               "from": declaration["identity"],
                               "to": ref, "status": "PASS",
                               "execution": "passed",
                               "test_case_identity": example.get(
                                   "test_case_identity"),
                               "run": run_evidence})
            else:
                checks.append({"check": "example-execution",
                               "from": declaration["identity"],
                               "to": ref, "status": "FAIL",
                               "reason": "test_failure",
                               "execution": verdict,
                               "test_case_identity": example.get(
                                   "test_case_identity"),
                               "note": "documentation linkage is intact; the "
                                       "underlying test failed (see mncs-test "
                                       "/ Debug)",
                               "run": run_evidence})
    return checks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _write_or_check(path: Path, expected: str, check: bool) -> bool:
    if check:
        if not path.exists():
            print(f"stale generated artifact (missing): {path}", file=sys.stderr)
            return False
        actual = path.read_text(encoding="utf-8")
        if actual == expected:
            return True
        print(f"stale generated artifact: {path}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(expected)
    os.replace(temporary, path)
    return True


def _dump_canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _load_model(path: Path) -> dict[str, Any]:
    try:
        model = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"cannot read model {path}: {error}")
    if model.get("schema_version") != MODEL_SCHEMA:
        raise RuntimeError(
            f"unsupported model schema {model.get('schema_version')!r} "
            f"(expected {MODEL_SCHEMA!r})")
    return model


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mncs-bin", default=None,
                        help="mncs compiler binary (default: $MNCS_BIN or PATH)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract",
                                    help="build a documentation model from sources")
    extract.add_argument("--source", type=Path, action="append", required=True,
                         help="MNCS source file (repeatable)")
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--repository", default=None)
    extract.add_argument("--revision", default=None)
    extract.add_argument("--provenance-out", type=Path, default=None,
                         help="sidecar for generation identity/time (kept out "
                              "of the deterministic model)")
    extract.add_argument("--check", action="store_true")

    render = subparsers.add_parser("render", help="render a model")
    render.add_argument("--model", type=Path, required=True)
    render.add_argument("--format", choices=["markdown", "html", "text"],
                        required=True)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--check", action="store_true")

    index = subparsers.add_parser("index", help="build a semantic index")
    index.add_argument("--model", type=Path, required=True)
    index.add_argument("--output", type=Path, required=True)
    index.add_argument("--check", action="store_true")

    query = subparsers.add_parser("query", help="bounded model retrieval")
    query.add_argument("--model", type=Path, required=True)
    query.add_argument("--identity", default=None)
    query.add_argument("--qualified", default=None)
    query.add_argument("--name", default=None)
    query.add_argument("--module", default=None)
    query.add_argument("--kind", default=None)
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--format", choices=["json", "text"], default="json")

    validate = subparsers.add_parser("validate", help="validate a model")
    validate.add_argument("--model", type=Path, required=True)
    validate.add_argument("--source", type=Path, action="append", default=None,
                          help="re-inventory these sources for staleness "
                               "(default: model subject paths)")
    validate.add_argument("--no-staleness", action="store_true",
                          help="skip re-inventory staleness checks")
    validate.add_argument("--require-docs", choices=["none", "exported", "all"],
                          default="none")
    validate.add_argument("--verify-examples", action="store_true",
                          help="execute linked examples via the compiler-owned "
                               "runner (opt-in; Doc never executes otherwise)")
    validate.add_argument("--library", action="append", default=None,
                          help="library directory for example execution "
                               "(repeatable)")
    validate.add_argument("--example-timeout", type=int, default=120)
    validate.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    mncs_bin = find_mncs_binary(args.mncs_bin)
    try:
        if args.command == "extract":
            model = build_model(
                [Path(s) for s in args.source], mncs_bin,
                repository_override=args.repository,
                revision_override=(int(args.revision)
                                   if args.revision is not None and
                                   str(args.revision).isdigit()
                                   else args.revision),
            )
            ok = _write_or_check(args.output, _dump_canonical(model), args.check)
            if args.provenance_out is not None and not args.check:
                import datetime
                provenance = {
                    "schema_version": PROVENANCE_SCHEMA,
                    "generator": model["generator"],
                    "model_digest": _sha256(_dump_canonical(model)),
                    "subjects": model["subjects"],
                    "generated_at": datetime.datetime.now(
                        datetime.timezone.utc).isoformat(),
                }
                args.provenance_out.write_text(_dump_canonical(provenance),
                                               encoding="utf-8")
            return 0 if ok else 1
        if args.command == "render":
            model = _load_model(args.model)
            if args.format == "markdown":
                expected = render_markdown(model)
            elif args.format == "html":
                expected = render_html(model)
            else:
                expected = render_text(model)
            return 0 if _write_or_check(args.output, expected, args.check) else 1
        if args.command == "index":
            model = _load_model(args.model)
            expected = _dump_canonical(build_index(model))
            return 0 if _write_or_check(args.output, expected, args.check) else 1
        if args.command == "query":
            model = _load_model(args.model)
            results = query_model(
                model, identity=args.identity, qualified=args.qualified,
                name=args.name, module=args.module, kind=args.kind,
                limit=args.limit)
            if args.format == "text":
                for result in results:
                    print(f"{result['kind']} {result['qualified_name']}")
                    print(f"  identity: {result['identity']}")
                    print(f"  {result['signature_text'].replace(chr(10), chr(10) + '  ')}")
                    if result["summary"]:
                        print(f"  {result['summary']}")
            else:
                print(_dump_canonical(results), end="")
            return 0
        if args.command == "validate":
            model = _load_model(args.model)
            if args.no_staleness:
                sources = None
            elif args.source is not None:
                sources = [Path(s) for s in args.source]
            else:
                sources = [Path(s.get("source_path"))
                           for s in model.get("subjects", [])]
            report = validate_model(model, mncs_bin, sources,
                                    require_docs=args.require_docs)
            if args.verify_examples:
                report["checks"].extend(
                    verify_example_execution(model, mncs_bin,
                                             libraries=args.library,
                                             timeout_s=args.example_timeout))
                failed = sum(1 for c in report["checks"]
                             if c["status"] == "FAIL")
                report["summary"] = {"total": len(report["checks"]),
                                     "failed": failed,
                                     "passed": len(report["checks"]) - failed}
                report["verdict"] = "FAIL" if failed else "PASS"
            if args.output is not None:
                args.output.write_text(_dump_canonical(report), encoding="utf-8")
            else:
                print(_dump_canonical(report), end="")
            for check in report["checks"]:
                if check["status"] == "FAIL":
                    print(f"FAIL {check['check']}: "
                          f"{check.get('from', '')} "
                          f"{check.get('reason', check.get('to', ''))}".strip(),
                          file=sys.stderr)
            print(f"validation {report['verdict']}: "
                  f"{report['summary']['passed']}/{report['summary']['total']} passed",
                  file=sys.stderr)
            return 0 if report["verdict"] == "PASS" else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"mncs-doc failed: {error}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
