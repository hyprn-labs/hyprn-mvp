"""Capture the result-protocol-3 native program fixture through the reviewed private producer.

Explicit utility, never collected as a test module.

    HYPRN_MVP_MODEL_TEST_ROOT=<scoped service root> \\
    HYPRN_MVP_MODEL_TEST_CONTAINER=<test container> \\
        python3 integration/tests/capture_native_programs_protocol3.py

The cases are those of ``capture_native_programs`` authored as model-format-4 revisions with
typed unit declarations. Each enters the producer as a portable model package through the
authenticated import. Its configuration is an application configuration version 6 (no
criteria, no approach binding); the producer receives the exact private projection (version
5) and prepares artifact 4, which pins result protocol 3. Every declared file is fetched by its
authenticated file id and checked against its size and SHA-256. No candidate is executed.
"""

import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'application/src'), str(Path(__file__).parent)]
from capture_native_programs import CAPTURED, CASES, SOURCE_SERVICE, PACKAGE_NOTICES, SPECS  # noqa: E402
from capture_native_programs import model_revision, package_files  # noqa: E402
from contracts.tests.test_modeling_contract import numerical, uid  # noqa: E402
from deployment.tests import model_client  # noqa: E402
from deployment.tests.model_client import ModelClient  # noqa: E402
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration  # noqa: E402
from hyprn_mvp_app.store import digest  # noqa: E402

IMAGE = json.loads((ROOT / 'deployment/pins.json').read_text())['modeling_producer']['image']
FIXTURE = ROOT / 'integration/tests/fixtures/native-programs-protocol3.json.gz'
CAPABILITIES = ['flat_explicit_scalar', 'unit_declarations/1', 'quantity_definitions/1']


def declaration(units):
    return {'kind': 'dimensionless'} if units == '' else {'kind': 'physical', 'expression': units}


def model4_revision(kind):
    """The format-1 revision of one case, re-authored as format 4 with typed units."""
    model = model_revision(kind)
    model.update(schema_version='4', assumptions=[], required_capabilities=list(CAPABILITIES))
    for definition in model['definitions']:
        definition['quantity_definitions'] = []
        for port in definition['ports']:
            port['units'] = declaration(port['units'])
    model['ports'] = [p for d in model['definitions'] for p in d['ports']]
    model.pop('digest')
    model['digest'] = digest(model)
    return model


def package(revision):
    value = dict(
        schema_version='4',
        source_service=SOURCE_SERVICE,
        model_id=revision['model_id'],
        model_revision_id=revision['model_revision_id'],
        revisions=[revision],
        files=package_files([revision]),
        required_capabilities=list(CAPABILITIES),
        license_notices=PACKAGE_NOTICES,
    )
    value['digest'] = digest(value)
    return value


def configuration(kind, model, study):
    """An application configuration version 6 that supplies every free input once."""
    incoming = [c['target_ref'] for c in model['connections']]
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    targets = [
        dict(instance_id=i['instance_id'], port_id=p['port_id'])
        for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports']
        if p['direction'] == 'input'
        and dict(instance_id=i['instance_id'], port_id=p['port_id']) not in incoming
    ]
    values = SPECS[kind]['values']
    if len(targets) != len(values):
        raise ValueError('Unexpected free inputs for ' + kind)
    captured = kind in CAPTURED
    config = dict(
        schema_version='6',
        study_id=study,
        model_id=model['model_id'],
        model_revision_id=model['model_revision_id'],
        name='Test configuration' if captured else 'Frozen test configuration',
        inputs=[
            dict(
                target=target,
                value=number,
                units=units,
                result_binding=None,
                provenance=dict(
                    kind='manual', statement='Explicit scientific fixture', evidence_version_ids=[]
                ),
            )
            for target, (number, units) in zip(targets, values)
        ],
        numerical=numerical(),
        context_snapshot=dict(description='Retained context', boundary='', notes=[]),
        evidence_snapshots=[],
        required_capabilities=list(CAPABILITIES) + ['configuration_assumptions/1'],
        context_source=dict(kind='current_study', expected_study_revision=uid()),
        derivation=None,
        assumptions=[],
        general_context_evidence_version_ids=[],
        configuration_id=uid(),
        configuration_revision_id=uid(),
        parent_revision_id=None,
    )
    config['digest'] = digest(config)
    return config


def capture(kind, blobs):
    client = ModelClient()
    model = model4_revision(kind)
    draft = client.call(
        'POST',
        '/imports',
        dict(
            command_id=uid(),
            expected_revision=None,
            study_id=client.study,
            package=package(model),
            preserve_public_ids=True,
        ),
        status=201,
    )['data']
    path = '/models/' + model['model_id']
    assert client.call('GET', path + '/revisions/' + model['model_revision_id'])['data'] == model
    config = configuration(kind, model, client.study)
    private = project_scientific_configuration(copy.deepcopy(config))
    assert private['schema_version'] == '5' and 'criteria' not in private
    body = dict(
        command_id=uid(),
        model_revision_id=model['model_revision_id'],
        configuration_snapshot=private,
        configuration_digest=private['digest'],
    )
    prepared = client.call('POST', path + '/prepare-execution', body)['data']
    assert prepared['schema_version'] == '4'
    assert prepared['result_protocol_version'] == '3'
    # Preparing a committed revision after a current draft edit must be invariant.
    client.call(
        'POST',
        path + '/edits',
        dict(
            schema_version='4',
            command_id=uid(),
            expected_revision=draft['draft_revision'],
            edits=[
                dict(
                    kind='rename_instance',
                    instance_id=model['instances'][0]['instance_id'],
                    name='Edited current draft after commit',
                )
            ],
        ),
    )
    second = client.call('POST', path + '/prepare-execution', {**body, 'command_id': uid()})['data']
    assert second['executable_content_digest'] == prepared['executable_content_digest']
    for descriptor in prepared['files']:
        sha = descriptor['sha256']
        if sha not in blobs:
            blobs[sha] = client.call(
                'GET',
                '/preparations/' + prepared['preparation_id'] + '/files/' + descriptor['file_id'],
            )['data']['bytes']
        raw = base64.b64decode(blobs[sha], validate=True)
        assert len(raw) == descriptor['size'] and hashlib.sha256(raw).hexdigest() == sha
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    key = (lambda i: i['instance_id']) if kind in CAPTURED else (lambda i: i['name'])
    targets = {
        key(i): {
            p['code_symbol']: dict(instance_id=i['instance_id'], port_id=p['port_id'])
            for p in definitions[i['definition_version_id']]['ports']
        }
        for i in model['instances']
    }
    case = dict(
        prepared=prepared,
        frozen=dict(
            schema_version='9', configuration=config, model_snapshot=model, study_revision=uid()
        ),
        targets=targets,
    )
    if kind in CAPTURED:
        case['capture'] = dict(
            draft_edit_invariance=True,
            repeated_preparation_id=second['preparation_id'],
            producer_image=IMAGE,
        )
    return case


def main():
    observed = json.loads(
        subprocess.check_output(['docker', 'inspect', model_client._container()])
    )[0]
    if observed['Image'] != IMAGE:
        raise SystemExit('The service under test does not run the reviewed producer image')
    blobs, cases = {}, {}
    for kind in CASES:
        cases[kind] = capture(kind, blobs)
        print('captured', kind, flush=True)
    used = {f['sha256'] for case in cases.values() for f in case['prepared']['files']}
    data = dict(producer_image=IMAGE, cases=cases, blobs={sha: blobs[sha] for sha in sorted(used)})
    FIXTURE.write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode(), mtime=0))
    print('written', len(cases), 'cases', len(data['blobs']), 'blobs', flush=True)


if __name__ == '__main__':
    main()
