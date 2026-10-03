"""Evidence-derived roadmap and shared ephemeral/file interpretation routes."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT.parent / 'mncs-forge/src')]
import semantic


def proof(declarations):
    result = {'schema_version':'mncs.semantic-evidence/1', 'producer':'owning-verifier',
        'validation':{'contract':'projection-conformance','identity':'exact-validator'},
        'verdict':'pass','subject_identity':semantic.identity(declarations)}
    return dict(result, receipt_identity=semantic.identity(result))


def model():
    declarations = [{'id':'real-contract','version':'1'}]
    return {'schema_version':'mncs.semantic-state/1','identity':'exact-source',
        'values': {'declarations':declarations,'intent':{'milestones':[
            {'id':'delivery','title':'Deliver capability','subject_slot':'declarations','evidence':'check'}]},
            'evidence': {'check': proof(declarations)}}}


def test_actual_native_milestone_completion_and_stale_evidence():
    data = model()
    board, receipts = semantic.roadmap(data['values'])
    assert board[0]['state'] == 'complete'
    assert receipts[0]['schema_version'] == 'mncs.provider-execution-provenance/1'
    data['values']['declarations'][0]['version'] = 'changed'
    assert semantic.roadmap(data['values'])[0][0]['state'] == 'unknown'
    data['values']['evidence']['check']['verdict'] = 'fail'
    row = data['values']['evidence']['check']
    row['receipt_identity'] = semantic.identity({k:v for k,v in row.items() if k != 'receipt_identity'})
    assert semantic.roadmap(data['values'])[0][0]['state'] == 'blocked'


def test_generated_prose_and_missing_proof_never_complete():
    data = model()
    data['values']['evidence'] = {}
    data['values']['intent']['milestones'][0]['state'] = 'complete'
    assert semantic.roadmap(data['values'])[0][0]['state'] == 'unknown'


def test_repeated_native_interpretation_launches_no_subprocesses():
    data = model()
    first = semantic.roadmap(data['values'])[0]
    with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
        assert semantic.roadmap(data['values'])[0] == first


def test_machine_and_ephemeral_views_share_canonical_values():
    data = model()
    data['values'].update({'capabilities':[{'contract':'x'}],'dependencies':[{'contract':'y'}]})
    view, _ = semantic.interpret(data, 'machine.project-view')
    caps, _ = semantic.interpret(data, 'query.capabilities')
    deps, _ = semantic.interpret(data, 'query.dependencies')
    assert view['capabilities'] == caps
    assert view['dependencies'] == deps
    assert view['source_identity'] == data['identity']


def test_failed_or_unknown_evidence_retains_identity():
    data = model()
    data['values']['evidence']['check']['verdict'] = 'unknown'
    row = data['values']['evidence']['check']
    row['receipt_identity'] = semantic.identity({k:v for k,v in row.items() if k != 'receipt_identity'})
    board, _ = semantic.roadmap(data['values'])
    assert board[0]['state'] == 'unknown'
    assert board[0]['evidence_identity'] == semantic.identity(data['values']['evidence']['check'])


def test_unattributed_or_tampered_verdict_never_completes():
    data = model()
    del data['values']['evidence']['check']['producer']
    assert semantic.roadmap(data['values'])[0][0]['state'] == 'unknown'


def test_verbatim_copy_round_trips_utf8():
    data = {'schema_version': 'mncs.semantic-state/1', 'identity': 'x',
            'values': {'page': '# Title\n\nbody\n'}}
    content, receipts = semantic.interpret(data, 'machine.verbatim-copy')
    assert content == '# Title\n\nbody\n'
    assert receipts == []


def test_verbatim_copy_requires_single_utf8_subject():
    with pytest.raises(ValueError, match='exactly one'):
        semantic.interpret({'schema_version': 'mncs.semantic-state/1',
                            'values': {'a': 'x', 'b': 'y'}}, 'machine.verbatim-copy')
    with pytest.raises(ValueError, match='utf-8'):
        semantic.interpret({'schema_version': 'mncs.semantic-state/1',
                            'values': {'a': {'not': 'a string'}}}, 'machine.verbatim-copy')


def test_delegated_renderer_receives_model(tmp_path):
    (tmp_path / 'renderer.py').write_text(
        'def render(model):\n    return "# " + model["values"]["title"] + "\\n"')
    data = {'schema_version': 'mncs.semantic-state/1', 'identity': 'x',
            'values': {'title': 'Hello'},
            'renderer_entry': {'module': 'renderer.py', 'callable': 'render'}}
    content, receipts = semantic.interpret(data, 'custom.route', tmp_path)
    assert content == '# Hello\n'
    assert receipts == []


def test_delegated_renderer_may_return_structured_content(tmp_path):
    (tmp_path / 'renderer.py').write_text(
        'def render(model):\n    return {"echo": model["values"]["n"]}\n')
    data = {'schema_version': 'mncs.semantic-state/1', 'identity': 'x',
            'values': {'n': 3},
            'renderer_entry': {'module': 'renderer.py', 'callable': 'render'}}
    content, _ = semantic.interpret(data, 'custom.route', tmp_path)
    assert content == {'echo': 3}


def test_delegation_rejects_escape_and_bad_callables(tmp_path):
    (tmp_path / 'renderer.py').write_text('def render(model):\n    return "x"\n')
    base = {'schema_version': 'mncs.semantic-state/1', 'values': {}}
    for entry in ({'module': '../renderer.py', 'callable': 'render'},
                  {'module': '/abs/renderer.py', 'callable': 'render'},
                  {'module': 'renderer.txt', 'callable': 'render'},
                  {'module': 'renderer.py', 'callable': '_private'},
                  {'module': 'renderer.py', 'callable': 'missing'},
                  {'module': 'absent.py', 'callable': 'render'}):
        with pytest.raises(ValueError):
            semantic.interpret(dict(base, renderer_entry=entry), 'custom.route', tmp_path)
    with pytest.raises(ValueError, match='renderer root'):
        semantic.interpret(dict(base, renderer_entry={'module': 'renderer.py',
                                                      'callable': 'render'}),
                           'custom.route', None)


def test_delegation_rejects_symlink_escape(tmp_path):
    (tmp_path / 'outside.py').write_text('def render(model):\n    return "evil"\n')
    (tmp_path / 'link.py').symlink_to(tmp_path / 'outside.py')
    data = {'schema_version': 'mncs.semantic-state/1', 'values': {},
            'renderer_entry': {'module': 'link.py', 'callable': 'render'}}
    with pytest.raises(ValueError, match='escapes'):
        semantic.interpret(data, 'custom.route', tmp_path)


def test_unknown_route_without_entry_stays_unsupported():
    with pytest.raises(ValueError, match='unsupported'):
        semantic.interpret({'schema_version': 'mncs.semantic-state/1', 'values': {}},
                           'nope.route', None)
