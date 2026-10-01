#!/usr/bin/env python3
"""Project bounded MNCS family context into deterministic Markdown.

The input context is a read-only projection from the owning repositories.  RFC
bodies remain the durable design source; this module only derives a stable
index from their identity/status headers.  The host implementation is an
explicit filesystem/publication boundary while the document-domain pressure
(`MNCS-LANG-BC105FDA1446`) remains the migration driver for reusable
structured-document semantics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


BEGIN = "<!-- MNCS:generated:begin -->"
END = "<!-- MNCS:generated:end -->"
SCHEMA = "mncs.documentation-projection/1"
DESCRIPTOR_SCHEMA = "mncs.projection-descriptor/1"

REPO_ROOT = Path(__file__).resolve().parents[1]
REGION_PROGRAM = REPO_ROOT / "native" / "mncs" / "doc" / "region.mncs"
PROJECTION_PROGRAM = REPO_ROOT / "native" / "mncs" / "doc" / "projection.mncs"

REGION_MISSING = 0
REGION_INVALID = 1
REGION_VALID = 2

ADMISSION_SCHEMA = "mncs.projection-admission/1"
REGION_NAMES = {0: "missing", 1: "invalid", 2: "valid"}

ADMIT_REASONS = {
    0: "admitted",
    1: "no-sources",
    2: "no-template",
    3: "ambiguous-region",
    4: "create-forbidden",
    5: "unknown-status",
}


class NativeError(RuntimeError):
    pass


def find_mncs(explicit: str | None = None) -> str | None:
    from shutil import which

    for candidate in (
        explicit,
        os.environ.get("MNCS_BIN"),
        which("mncs"),
        str(REPO_ROOT.parent / "mncs-language" / "target" / "debug" / "mncs"),
        str(REPO_ROOT.parent / "mncs-language" / "target" / "release" / "mncs"),
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _plain(value: dict[str, Any]) -> Any:
    if not isinstance(value, dict) or len(value) != 1:
        raise NativeError(f"unexpected wire value {value!r}")
    tag, body = next(iter(value.items()))
    if tag == "integer":
        return body["value"]
    if tag == "boolean":
        return body["value"]
    if tag == "finite":
        return {"variant": body.get("variant_identity", body.get("variant")),
                "discriminant": body.get("discriminant")}
    if tag == "record":
        fields = body["fields"]
        if isinstance(fields, dict):
            return {name: _plain(item) for name, item in fields.items()}
        return {name: _plain(item) for name, item in fields}
    if tag == "sequence":
        return [_plain(item) for item in body["values"]]
    raise NativeError(f"unknown wire tag {tag!r}")


def default_libraries() -> list[str]:
    language_root = os.environ.get("MNCS_LANGUAGE_ROOT")
    candidates = []
    if language_root:
        candidates.append(Path(language_root) / "library")
    else:
        candidates.append(REPO_ROOT.parent / "mncs-language" / "library")
    override = os.environ.get("MNCS_TEST_NATIVE")
    candidates.append(Path(override) if override
                      else REPO_ROOT.parent / "mncs-test" / "native")
    candidates.append(REPO_ROOT / "native")
    return [str(path) for path in candidates if path.is_dir()]


def call_native(mncs_bin: str, program: Path, module: str,
                function: str, args: list[int]) -> dict[str, Any]:
    """Invoke a scalar-argument native function; return the decoded record."""
    payload = [{"integer": {"value": int(item)}} for item in args]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as handle:
        json.dump(payload, handle)
        args_path = handle.name
    command = [mncs_bin, "call", str(program), "--module", module,
               "--function", function, "--args", args_path]
    for library in default_libraries():
        command += ["--library", library]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise NativeError(f"cannot start compiler: {error}")
    finally:
        try:
            os.unlink(args_path)
        except OSError:
            pass
    try:
        document = json.loads(completed.stdout)
    except ValueError:
        raise NativeError("compiler returned non-JSON: "
                          f"{completed.stderr.strip()[:400]}")
    if document.get("status") != "returned":
        raise NativeError(f"native call failed: "
                          f"{document.get('error', document)}")
    returned = document["call"]["returned"]
    if not returned:
        raise NativeError("compiler returned no values")
    decoded = _plain(returned[0])
    if not isinstance(decoded, dict):
        raise NativeError(f"native call returned non-record {decoded!r}")
    return decoded


def classify_spans(mncs_bin: str, document: bytes) -> dict[str, Any]:
    """Classify marker spans through native `mncs.doc.region`.

    All offsets are byte offsets into the UTF-8 document; the native
    classifier reasons about bytes, never Unicode scalar indices.
    """
    begin = BEGIN.encode("utf-8")
    end = END.encode("utf-8")
    begins: list[int] = []
    ends: list[int] = []
    cursor = 0
    while True:
        found = document.find(begin, cursor)
        if found == -1:
            break
        begins.append(found)
        cursor = found + len(begin)
    cursor = 0
    while True:
        found = document.find(end, cursor)
        if found == -1:
            break
        ends.append(found)
        cursor = found + len(end)
    first_begin = begins[0] if begins else 0
    first_end = ends[0] if ends else 0
    decision = call_native(
        mncs_bin, REGION_PROGRAM, "mncs.doc.region", "classify_fields",
        [len(document), len(begins), len(ends),
         first_begin, first_begin + (len(begin) if begins else 0),
         first_end, first_end + (len(end) if ends else 0)])
    status = decision.get("status")
    if isinstance(status, dict):
        variant = str(status.get("variant", ""))
        name = variant.split("::")[-1] if "::" in variant else ""
        code = {"Missing": REGION_MISSING, "Invalid": REGION_INVALID,
                "Valid": REGION_VALID}.get(name)
        if code is None:
            code = status.get("discriminant")
        decision["status_code"] = code
    return decision





def _field(value: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return default


def _text(value: Any, default: str = "UNKNOWN") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _context_lines(context: dict[str, Any], heading: str = "Machine-readable status") -> list[str]:
    repository = context.get("repository") or {}
    language = context.get("language") or {}
    architecture = context.get("architecture") or {}
    completeness = context.get("completeness") or {}
    repo_id = _text(_field(repository, "repository"))
    revision = _text(_field(repository, "revision"))
    profile = _text(_field(language, "current_profile", "currentProfile"))
    language_identity = _text(_field(language, "content_identity", "contentIdentity"))
    inventory_identity = _text(
        _field(language, "compiler_inventory_identity", "compilerInventoryIdentity")
    )
    architecture_identity = _text(
        _field(architecture, "content_identity", "contentIdentity")
    )
    state = _text(_field(completeness, "state"))
    complete = _text(_field(completeness, "complete"))
    language_mode = _text(_field(language, "mode"))
    architecture_mode = _text(_field(architecture, "mode"))

    lines = [
        f"## {heading}",
        "",
        f"- Repository: `{repo_id}` (manifest revision `{revision}`)",
        f"- Language profile: `{profile}`; capability identity `{language_identity}`",
        f"- Compiler inventory identity: `{inventory_identity}`",
        f"- Language projection: `{language_mode}`",
        f"- Commons architecture identity: `{architecture_identity}`; projection `{architecture_mode}`",
        f"- Context completeness: `{state}` (complete: `{complete}`)",
    ]

    capabilities = architecture.get("capabilities") or []
    if capabilities:
        lines.extend(["", "### Family capabilities in scope", ""])
        for capability in sorted(
            (item for item in capabilities if isinstance(item, dict)),
            key=lambda item: _text(item.get("id")),
        ):
            canonical = capability.get("canonical") or {}
            identity = _text(capability.get("id"))
            owner = _text(capability.get("owner"))
            path = _text(canonical.get("path"))
            kind = _text(canonical.get("kind"))
            lines.append(f"- `{identity}` — owner `{owner}`, `{kind}` at `{path}`")

    pressures = context.get("pressures") or []
    if pressures:
        lines.extend(["", "### Relevant open pressures", ""])
        for pressure in sorted(
            (item for item in pressures if isinstance(item, dict)),
            key=lambda item: _text(item.get("id")),
        ):
            title = _text(pressure.get("title"), "untitled")
            status = _text(pressure.get("status"), "unresolved")
            lines.append(f"- `{_text(pressure.get('id'))}` — {title} ({status})")
    else:
        lines.extend(["", "- Relevant open pressures: none returned by the bounded projection."])

    lines.extend(
        [
            "",
            "This section is generated from authoritative language, Commons, and repository context. "
            "It contains no completion inference from code presence.",
        ]
    )
    return lines


def _generated_section(lines: Iterable[str]) -> str:
    return "\n".join([BEGIN, *lines, END])


def replace_region(document: str, generated: str) -> str:
    """Replace one bounded generated region, preserving all other prose."""

    begin = document.find(BEGIN)
    end = document.find(END)
    if begin == -1 and end == -1:
        prefix = document.rstrip("\n")
        return f"{prefix}\n\n{generated}\n"
    if begin == -1 or end == -1 or end < begin:
        raise ValueError("generated region markers are incomplete or out of order")
    end += len(END)
    return document[:begin] + generated + document[end:]


def _write_or_check(path: Path, expected: str, check: bool) -> bool:
    actual = path.read_text(encoding="utf-8") if path.exists() else None
    if check:
        if actual == expected:
            return True
        print(f"stale generated projection: {path}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(expected)
    os.replace(temporary, path)
    return True


def project_readme(readme: Path, context_path: Path, check: bool = False) -> bool:
    context = json.loads(context_path.read_text(encoding="utf-8"))
    current = readme.read_text(encoding="utf-8") if readme.exists() else ""
    generated = _generated_section(_context_lines(context))
    expected = replace_region(current, generated)
    return _write_or_check(readme, expected, check)


RFC_HEADING = re.compile(r"^#\s+RFC\s+([0-9]+)\s*:\s*(.+?)\s*$", re.MULTILINE)
RFC_FIELD = re.compile(r"^(Status|Owner|Affected repositories|Affected capabilities):\s*(.+?)\s*$", re.MULTILINE)


def _rfc_records(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        heading = RFC_HEADING.search(text)
        if not heading:
            continue
        fields = {name.lower(): value.strip() for name, value in RFC_FIELD.findall(text)}
        records.append(
            {
                "id": heading.group(1).zfill(4),
                "title": heading.group(2).strip(),
                "status": fields.get("status", "UNKNOWN"),
                "owner": fields.get("owner", "UNKNOWN"),
                "affected": fields.get(
                    "affected repositories", fields.get("affected capabilities", "UNKNOWN")
                ),
                "path": path.relative_to(root).as_posix(),
            }
        )
    return sorted(records, key=lambda item: (int(item["id"]), item["path"]))


def _relative_link(output: Path, target: Path) -> str:
    return Path(os.path.relpath(target, output.parent)).as_posix()


def render_rfc_index(root: Path, output: Path) -> str:
    records = _rfc_records(root)
    lines = [
        BEGIN,
        "# RFC index",
        "",
        f"Projection schema: `{SCHEMA}`",
        "",
        "| ID | Title | Status | Owner | Affected |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        link = _relative_link(output, root / record["path"])
        title = record["title"].replace("|", "\\|")
        lines.append(
            f"| [{record['id']}]({link}) | {title} | {record['status']} | "
            f"{record['owner']} | {record['affected']} |"
        )
    if not records:
        lines.append("| — | No RFC bodies found | UNKNOWN | UNKNOWN | UNKNOWN |")
    lines.append(END)
    return "\n".join(lines) + "\n"


def project_rfc_index(rfc_root: Path, output: Path, check: bool = False) -> bool:
    return _write_or_check(output, render_rfc_index(rfc_root, output), check)


def render_roadmap(context: dict[str, Any]) -> str:
    repository = context.get("repository") or {}
    language = context.get("language") or {}
    architecture = context.get("architecture") or {}
    completeness = context.get("completeness") or {}
    pressures = context.get("pressures") or []
    lines = [
        BEGIN,
        "# Roadmap status",
        "",
        f"Projection schema: `{SCHEMA}`",
        "",
        f"- Repository: `{_text(repository.get('repository'))}`",
        f"- Language profile: `{_text(_field(language, 'current_profile', 'currentProfile'))}`",
        f"- Language identity: `{_text(_field(language, 'content_identity', 'contentIdentity'))}`",
        f"- Commons architecture identity: `{_text(_field(architecture, 'content_identity', 'contentIdentity'))}`",
        f"- Current context state: `{_text(completeness.get('state'))}`",
        "",
        "Roadmap state is derived from authoritative identities, lifecycle records, "
        "and evidence. Completion is never inferred merely from the presence of code.",
    ]
    if pressures:
        lines.extend(["", "## Active pressure work", ""])
        for pressure in sorted(
            (item for item in pressures if isinstance(item, dict)),
            key=lambda item: _text(item.get("id")),
        ):
            lines.append(
                f"- `{_text(pressure.get('id'))}` — {_text(pressure.get('title'), 'untitled')} "
                f"[{_text(pressure.get('status'), 'unresolved')}]"
            )
    lines.append(END)
    return "\n".join(lines) + "\n"


def project_roadmap(context_path: Path, output: Path, check: bool = False) -> bool:
    context = json.loads(context_path.read_text(encoding="utf-8"))
    return _write_or_check(output, render_roadmap(context), check)


def _wrap_generated(generated: bytes) -> bytes:
    body = generated.decode("utf-8").rstrip("\n")
    return "\n".join([BEGIN, body, END]).encode("utf-8")


def _expected_bytes(current: bytes | None, generated: bytes,
                    status_code: int, decision: dict[str, Any]) -> bytes:
    if status_code == REGION_VALID:
        assert current is not None
        start = int(decision["replacement_start"])
        end = int(decision["replacement_end"])
        return current[:start] + generated + current[end:]
    prefix = (current or b"").rstrip(b"\n")
    separator = b"" if not prefix else b"\n\n"
    return prefix + separator + generated + b"\n"


def admit_projection(document_path: Path, source_count: int,
                     template_present: bool, create_allowed: bool,
                     generated_path: Path | None = None,
                     expect_out: Path | None = None,
                     mncs_bin: str | None = None) -> dict[str, Any]:
    """Classify and admit a region write without mutating the document.

    Returns the `mncs.projection-admission/1` envelope. When
    `generated_path` and `expect_out` are both given and the write is
    admitted, the full expected file bytes are written to `expect_out`
    (a caller-provided scratch path, never the document itself) so an
    orchestrator can compare, claim, and copy without reimplementing
    the splice. Read-only against repositories.
    """
    import hashlib

    binary = find_mncs(mncs_bin)
    if binary is None:
        raise NativeError("mncs compiler binary unavailable; cannot "
                          "classify projection region")
    if document_path.exists():
        current: bytes | None = document_path.read_bytes()
    elif create_allowed:
        current = b""
    else:
        return {"schema_version": ADMISSION_SCHEMA, "status": REGION_MISSING,
                "status_name": "missing", "admit": False,
                "reason": 4, "reason_name": "create-forbidden",
                "document_exists": False}
    assert current is not None
    decision = classify_spans(binary, current)
    status_code = decision.get("status_code")
    if status_code is None:
        raise NativeError(f"native classifier returned no status: {decision!r}")
    status_code = int(status_code)
    verdict = native_admit(binary, status_code, create_allowed,
                           source_count, template_present)
    admitted = bool(verdict.get("admit"))
    reason = int(verdict.get("reason", 5))
    envelope: dict[str, Any] = {
        "schema_version": ADMISSION_SCHEMA, "status": status_code,
        "status_name": REGION_NAMES.get(status_code, "unknown"),
        "admit": admitted, "reason": reason,
        "reason_name": ADMIT_REASONS.get(reason, "unknown-status"),
        "document_exists": True,
    }
    if status_code == REGION_VALID:
        envelope["replacement_start"] = int(decision["replacement_start"])
        envelope["replacement_end"] = int(decision["replacement_end"])
        envelope["region_digest"] = "sha256:" + hashlib.sha256(
            current[int(decision["replacement_start"]):int(
                decision["replacement_end"])]).hexdigest()
    if admitted and generated_path is not None and expect_out is not None:
        wrapped = _wrap_generated(generated_path.read_bytes())
        expected = _expected_bytes(current, wrapped, status_code, decision)
        expect_out.parent.mkdir(parents=True, exist_ok=True)
        expect_out.write_bytes(expected)
        envelope["expected_digest"] = "sha256:" + hashlib.sha256(
            expected).hexdigest()
    return envelope


def native_admit(mncs_bin: str, region_status: int,
                 create_allowed: bool, source_count: int,
                 template_present: bool) -> dict[str, Any]:
    """Decide admission through native `mncs.doc.projection`."""
    return call_native(
        mncs_bin, PROJECTION_PROGRAM, "mncs.doc.projection.v1",
        "admit_fields",
        [region_status, 1 if create_allowed else 0,
         source_count, 1 if template_present else 0])


def apply_projection(document_path: Path, generated_path: Path,
                     source_count: int, template_present: bool,
                     create_allowed: bool, check: bool = False,
                     mncs_bin: str | None = None) -> bool:
    """Apply generated bytes to one document's machine-owned region.

    The native region classifier bounds the replacement and the native
    projection policy admits it; the host only splices admitted bytes.
    Ambiguous regions are always refused. Without the compiler the
    operation fails closed: guessing region bounds in the host would
    risk destroying human prose.
    """
    binary = find_mncs(mncs_bin)
    if binary is None:
        raise NativeError("mncs compiler binary unavailable; refusing to "
                          "apply a projection without native region validation")
    if document_path.exists():
        current = document_path.read_bytes()
    elif create_allowed:
        current = b""
    else:
        print(f"projection refused: {document_path} does not exist "
              f"(create-forbidden)", file=sys.stderr)
        return False
    generated = _wrap_generated(generated_path.read_bytes())
    decision = classify_spans(binary, current)
    status_code = decision.get("status_code")
    if status_code is None:
        raise NativeError(f"native classifier returned no status: {decision!r}")
    verdict = native_admit(binary, int(status_code), create_allowed,
                           source_count, template_present)
    if not verdict.get("admit"):
        reason = ADMIT_REASONS.get(int(verdict.get("reason", 5)),
                                   "unknown-status")
        print(f"projection refused: {reason}", file=sys.stderr)
        return False
    expected = _expected_bytes(current, generated, int(status_code),
                               decision)
    actual = current if document_path.exists() else None
    if check:
        if actual == expected:
            return True
        print(f"stale generated projection: {document_path}", file=sys.stderr)
        return False
    document_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=document_path.parent, prefix=f".{document_path.name}.",
        delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(expected)
    os.replace(temporary, document_path)
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    readme = subparsers.add_parser("project-readme")
    readme.add_argument("--readme", type=Path, required=True)
    readme.add_argument("--context", type=Path, required=True)
    readme.add_argument("--check", action="store_true")

    rfc = subparsers.add_parser("project-rfc-index")
    rfc.add_argument("--rfc-root", type=Path, required=True)
    rfc.add_argument("--output", type=Path, required=True)
    rfc.add_argument("--check", action="store_true")

    roadmap = subparsers.add_parser("project-roadmap")
    roadmap.add_argument("--context", type=Path, required=True)
    roadmap.add_argument("--output", type=Path, required=True)
    roadmap.add_argument("--check", action="store_true")

    apply = subparsers.add_parser("project-apply")
    apply.add_argument("--document", type=Path, required=True)
    apply.add_argument("--generated", type=Path, required=True)
    apply.add_argument("--sources", type=int, required=True)
    apply.add_argument("--template-present", type=int, required=True,
                       choices=(0, 1))
    apply.add_argument("--create", action="store_true")
    apply.add_argument("--check", action="store_true")
    apply.add_argument("--mncs-bin", type=str, default=None)

    admit = subparsers.add_parser("project-admit")
    admit.add_argument("--document", type=Path, required=True)
    admit.add_argument("--sources", type=int, required=True)
    admit.add_argument("--template-present", type=int, required=True,
                       choices=(0, 1))
    admit.add_argument("--create", action="store_true")
    admit.add_argument("--generated", type=Path, default=None)
    admit.add_argument("--expect-out", type=Path, default=None)
    admit.add_argument("--mncs-bin", type=str, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "project-readme":
            ok = project_readme(args.readme, args.context, args.check)
        elif args.command == "project-rfc-index":
            ok = project_rfc_index(args.rfc_root, args.output, args.check)
        elif args.command == "project-apply":
            ok = apply_projection(args.document, args.generated,
                                  args.sources, args.template_present == 1,
                                  args.create, args.check, args.mncs_bin)
        elif args.command == "project-admit":
            admission = admit_projection(
                args.document, args.sources,
                args.template_present == 1, args.create,
                generated_path=args.generated,
                expect_out=args.expect_out, mncs_bin=args.mncs_bin)
            print(json.dumps(admission, sort_keys=True))
            ok = True
        else:
            ok = project_roadmap(args.context, args.output, args.check)
    except (OSError, ValueError, KeyError, NativeError) as error:
        print(f"projection failed: {error}", file=sys.stderr)
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
