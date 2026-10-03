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
