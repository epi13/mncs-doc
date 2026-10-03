"""Semantic-state interpretation and deterministic outward render boundary.

Canonical values arrive from declared subjects, never from generated Markdown.
MNCS owns roadmap evidence admission. This file formats/encodes owner decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_runtimes = {}
ROUTES = ('human.repository-overview', 'human.roadmap', 'machine.project-view',
          'human.structure', 'query.capabilities', 'query.dependencies', 'query.blockers')


def identity(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def native_state(function, arguments):
    """Forge executes a Doc-owned pure artifact; Doctor admits its repair."""
    from mncs_forge.provider_artifacts import ProviderArtifact
    family = Path(os.environ.get('MNCS_WORKSPACE_ROOT', ROOT.parent))
    roots = {name: family / name for name in ('mncs-doc', 'mncs-doctor', 'MNCS-Commons')}
    spec = json.loads((ROOT / '.mncs/semantic-artifact.json').read_text())
    compiler = Path(os.environ.get('MNCS_BIN', str(family / 'mncs-language/target/release/mncs')))
    cache = Path(os.environ.get('MNCS_PROVIDER_CACHE', str(Path.home() / '.cache/mncs-doc/semantic')))
    key = identity([spec, str(compiler), str(cache), {k: str(v) for k, v in roots.items()}])
    runtime = _runtimes.get(key)
    if runtime is None:
        runtime = ProviderArtifact(spec, roots=roots, compiler=compiler,
            embed=compiler.parent / 'libmncs_embed.so', cache=cache)
        _runtimes[key] = runtime
    args = [{'integer': {'value': int(value), 'type': {'bits': 64, 'signed': False}}}
            for value in arguments]
    module = 'doctor.projection.v1' if function in ('health', 'repair') else 'mncs.doc.state.v1'
    returned, receipt = runtime.call(module, function, args)
    if returned.get('status') != 'returned':
        raise ValueError('native semantic state unavailable')
    result = returned['returned'][0]['integer']['value']
    return int(result), receipt


def roadmap(values):
    """Consume owning verdicts with exact declared evidence-subject identities."""
    intent = values.get('intent') or {}
    evidence = values.get('evidence') or {}
    states, result, receipts = {}, [], []
    milestones = intent.get('milestones', [])
    if len(milestones) > 64:
        raise ValueError('roadmap exceeds bounded milestone inventory')
    # Declaration order is a topological order; unknown/forward dependencies
    # remain open rather than manufacturing completion.
    for item in milestones:
        proof = evidence.get(item.get('evidence'), {})
        slot = item.get('subject_slot')
        receipt = {key: value for key, value in proof.items() if key != 'receipt_identity'}
        admitted = (proof.get('schema_version') == 'mncs.semantic-evidence/1'
                    and bool(proof.get('producer')) and bool(proof.get('validation'))
                    and proof.get('receipt_identity') == identity(receipt))
        current = bool(admitted and slot in values
                       and proof.get('subject_identity') == identity(values[slot]))
        verdict = {'fail': 0, 'pass': 1, 'unknown': 2}.get(proof.get('verdict'), 2)
        dependencies = all(states.get(name) == 'complete' for name in item.get('dependencies', []))
        code, receipt = native_state('milestone', [verdict, int(current), int(dependencies), int(bool(item.get('blockers')))])
        state = {0: 'open', 1: 'complete', 2: 'blocked', 3: 'unknown'}[code]
        states[item['id']] = state
        result.append(dict(item, state=state, evidence_identity=identity(proof) if proof else None))
        receipts.append(receipt)
    return result, receipts


def interpret(model, route):
    if model.get('schema_version') != 'mncs.semantic-state/1' or route not in ROUTES:
        raise ValueError('unsupported semantic state or interpretation route')
    values = model['values']
    if route == 'query.capabilities':
        return values.get('capabilities', []), []
    if route == 'query.dependencies':
        return values.get('dependencies', []), []
    if route in ('human.roadmap', 'query.blockers'):
        board, receipts = roadmap(values)
        if route == 'query.blockers':
            return [row for row in board if row['state'] != 'complete'], receipts
        lines = ['## Evidence-bound roadmap', '']
        for row in board:
            lines += [f"- **{row['state']}** — {row['title']} (`{row['id']}`)"]
            for blocker in row.get('blockers', []):
                lines += [f'  - {blocker}']
        if not board:
            lines += ['No execution milestones declared.']
        return '\n'.join(lines) + '\n', receipts
    if route == 'machine.project-view':
        return {'schema_version': 'mncs.project-view/1', 'source_identity': model['identity'],
                'repository': values.get('repository'), 'purpose': values.get('purpose'),
                'capabilities': values.get('capabilities', []),
                'dependencies': values.get('dependencies', []),
                'structure': values.get('structure', {}), 'entry': values.get('entry', [])}, []
    if route == 'human.structure':
        lines = ['## Declared structure', '']
        for surface in values.get('structure', {}).get('surfaces', []):
            lines += [f"- `{surface['path']}` — {surface['class']}" +
                      (f"; {surface['note']}" if surface.get('note') else '')]
        return '\n'.join(lines) + '\n', []
    lines = ['## Project entry', '', str(values.get('purpose', 'Purpose unavailable.')), '']
    entry = values.get('entry') or []
    for command in entry:
        lines += ['```bash', command, '```', '']
    capabilities = values.get('capabilities') or []
    lines += ['Declared capabilities (declarations do not establish execution health):', '']
    for item in sorted(capabilities, key=lambda row: row['contract'])[:12]:
        lines += [f"- `{item['contract']}/{item['version']}` — {item['kind']} ({item['stability']})"]
    if len(capabilities) > 12:
        lines += ['- Full inventory: `.mncs/project-view.json`.']
    lines += ['', 'Semantic sources and ownership: `.mncs/projections.json`.']
    return '\n'.join(lines) + '\n', []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--route', choices=ROUTES, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--provenance-out', type=Path)
    parser.add_argument('--result-envelope', action='store_true')
    args = parser.parse_args(argv)
    model = json.loads(args.state.read_text())
    result, receipts = interpret(model, args.route)
    data = (result if isinstance(result, str) else json.dumps(result, sort_keys=True,
                indent=2, ensure_ascii=False) + '\n').encode()
    if args.result_envelope:
        print(json.dumps({'schema_version': 'mncs.projection-render-result/1',
            'content': data.decode(), 'source_identity': model['identity'],
            'renderer': args.route, 'version': '1', 'native': receipts}, sort_keys=True))
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    else:
        print(data.decode(), end='')
    if args.provenance_out:
        args.provenance_out.write_text(json.dumps({'schema_version': 'mncs.interpretation-receipt/1',
            'source_identity': model['identity'], 'renderer': args.route, 'version': '1',
            'output_digest': 'sha256:' + hashlib.sha256(data).hexdigest(), 'native': receipts}, sort_keys=True))
    return 0


if __name__ == '__main__':
    import sys
    family = Path(os.environ.get('MNCS_WORKSPACE_ROOT', ROOT.parent))
    sys.path.insert(0, str(family / 'mncs-forge/src'))
    raise SystemExit(main())
