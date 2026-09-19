#!/usr/bin/env python3
"""Project bounded MNCS family context into deterministic Markdown.

The input context is a read-only projection from the owning repositories.  RFC
bodies remain the durable design source; this module only derives a stable
index from their identity/status headers.  The host implementation is an
explicit projection boundary while the generic structured-document pressure
in Commons remains unresolved.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


BEGIN = "<!-- MNCS:generated:begin -->"
END = "<!-- MNCS:generated:end -->"
SCHEMA = "mncs.documentation-projection/1"


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
    import json

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
    import json

    context = json.loads(context_path.read_text(encoding="utf-8"))
    return _write_or_check(output, render_roadmap(context), check)


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "project-readme":
            ok = project_readme(args.readme, args.context, args.check)
        elif args.command == "project-rfc-index":
            ok = project_rfc_index(args.rfc_root, args.output, args.check)
        else:
            ok = project_roadmap(args.context, args.output, args.check)
    except (OSError, ValueError, KeyError) as error:
        print(f"projection failed: {error}", file=sys.stderr)
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
