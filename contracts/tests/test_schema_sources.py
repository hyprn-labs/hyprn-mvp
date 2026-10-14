"""Authored bodies, generated closure and application-only Documents ownership."""

import json
from pathlib import Path
import sys

import pytest

from hyprn_mvp_app import contracts

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'application'))
from generate_execution_schema import generated_bytes, references


def assert_execution_schema():
    assert (ROOT / 'contracts/schemas/execution.schema.json').read_bytes() == generated_bytes()


def test_execution_schema_is_exactly_the_generated_root_closure():
    assert_execution_schema()


def test_generators_preserve_public_contract_bytes_and_check_the_execution_projection(tmp_path):
    import subprocess

    from scoped_fixture import APPROVED_CONTRACT_PYTHON

    output = tmp_path / 'openapi.yaml'
    types = tmp_path / 'contract.ts'
    commands = (
        [sys.executable, '-B', str(ROOT / 'application/generate_execution_schema.py'), '--check'],
        [
            APPROVED_CONTRACT_PYTHON,
            '-B',
            str(ROOT / 'application/generate_contract.py'),
            '--output',
            str(output),
        ],
        [
            sys.executable,
            '-B',
            str(ROOT / 'ui/generate_types.py'),
            '--input',
            str(output),
            '--output',
            str(types),
        ],
    )
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_bytes() == (ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_bytes()
    assert types.read_bytes() == (ROOT / 'ui/src/contract.ts').read_bytes()


def test_definition_bodies_equal_the_pre_split_digests():
    recorded = json.loads((Path(__file__).parent / 'definition_body_digests.json').read_bytes())
    assert {
        name: contracts.digest(contracts.definition(name)) for name in recorded
    } == recorded


def test_authored_names_are_disjoint_and_every_reference_resolves():
    model = json.loads((ROOT / 'contracts/schemas/model.schema.json').read_bytes())['$defs']
    documents = json.loads((ROOT / 'contracts/schemas/documents.schema.json').read_bytes())['$defs']
    assert not model.keys() & documents.keys()
    assert set(model) | set(documents) == set(contracts.definitions())
    assert set(references(model)) <= set(model)
    assert set(references(documents)) <= set(contracts.definitions())


def test_every_documents_registry_definition_resolves_through_the_owner():
    for name in contracts.documents_contract()['definitions']:
        assert contracts.validator(name).schema['$defs'][name] == contracts.definition(name)


def test_public_definition_order_preserves_the_original_namespace():
    recorded = json.loads((Path(__file__).parent / 'definition_body_digests.json').read_bytes())
    assert list(contracts.definitions())[:len(recorded)] == list(recorded)


@pytest.mark.parametrize(
    'fault', ['unknown_anchor', 'duplicate_member', 'missing_member', 'overlap']
)
def test_invalid_authored_order_or_duplicate_namespace_refuses(tmp_path, monkeypatch, fault):
    model = {'$defs': {'Model': {}}}
    documents = {
        '$defs': {'Document': {}},
        'x-hyprn-mvp-definition-order': {'Model': ['Document']},
        'x-hyprn-mvp-documents-contract': {},
    }
    groups = documents['x-hyprn-mvp-definition-order']
    if fault == 'unknown_anchor':
        groups['Unknown'] = groups.pop('Model')
    elif fault == 'duplicate_member':
        groups['Model'].append('Document')
    elif fault == 'missing_member':
        groups['Model'].clear()
    else:
        model['$defs']['Document'] = {}
    for name, data in [('model', model), ('documents', documents)]:
        (tmp_path / (name + '.schema.json')).write_text(json.dumps(data))
    monkeypatch.setattr(contracts, 'SCHEMA_DIRECTORY', tmp_path)
    contracts.authored_schema.cache_clear()
    contracts._documents_schema.cache_clear()
    try:
        with pytest.raises(ValueError, match='Duplicate authored|Invalid authored'):
            contracts.definitions()
    finally:
        contracts.authored_schema.cache_clear()
        contracts._documents_schema.cache_clear()


def test_importing_contracts_opens_no_schema():
    import subprocess

    code = """
import sys
def audit(event, args):
    if event == 'open' and 'contracts/schemas/' in str(args[0]):
        raise AssertionError('Schema opened during contract import')
sys.addaudithook(audit)
import hyprn_mvp_app.contracts
"""
    result = subprocess.run(
        [
            sys.executable,
            '-B',
            '-c',
            'import sys;sys.path.insert(0, ' + repr(str(ROOT / 'application/src')) + ');' + code,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
