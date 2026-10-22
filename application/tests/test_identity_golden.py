"""Golden identity corpus: existing canonical bytes and digests never change.

The corpus was captured once from the pre-change source (see ``captured_from_commit``).
Two reviewed revisions moved product identifiers into the hyprn-mvp namespace and recomputed
exactly the values derived from those bytes; every other captured value is unchanged. The
first renamed the selected worker entrypoint and the ASCII sample string. The second renamed
the program protocol and the namespace strings of the bundle file bytes that the regenerated
producer fixture no longer holds, replaced ten host-specific path literals in three
provenance support files by numbered placeholders, and stores those bytes in the corpus's own
blob table; its mapping-back proof (namespace strings and placeholders reversed reproduce the
previous bytes, digests and corpus exactly) is recorded in the repository-baseline task
checkpoints. Other bundle file bytes are referenced by sha256 in the read-only producer
fixture, and every resolved blob is re-hashed. A mismatch here means an existing record,
bundle, evidence snapshot or receipt identity would change: fix the code, never the corpus.
"""
import base64
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from hyprn_mvp_app.store import Store, DomainError, canonical, digest
from hyprn_mvp_app.execution import assemble_bundle, executable_digest
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration as project
from hyprn_mvp_app.configuration import Configurations

REPO = Path(__file__).resolve().parents[2]
CORPUS_PATH = REPO / 'application/tests/fixtures/identity_golden.json'
# Pinned so the corpus cannot be silently regenerated; changing it needs an explicit review.
CORPUS_SHA256 = 'f3e31a9aaf3f613210f6678c32e6b316c6085b895ff1d09a055b99700bf6e944'
CAPTURED_FROM = '5dfc62765d263f98ac6ca00d42a37d5e6fd1ff20'
RAW = CORPUS_PATH.read_bytes()
CORPUS = json.loads(RAW)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blobs():
    native = json.loads(gzip.decompress((REPO / CORPUS['external_blobs']['source']).read_bytes()))['blobs']
    resolved = {}
    for source in (native, CORPUS['blobs']):
        for key, value in source.items():
            raw = base64.b64decode(value, validate=True)
            assert sha(raw) == key
            resolved[key] = raw
    return resolved


BLOBS = blobs()


def by_name(section):
    return {case['name']: case for case in CORPUS[section]}


def test_corpus_is_the_reviewed_pre_change_capture():
    assert sha(RAW) == CORPUS_SHA256
    assert CORPUS['captured_from_commit'] == CAPTURED_FROM and CORPUS['corpus_version'] == '1'
    assert [b['expected']['schema_version'] for b in CORPUS['bundles']] == ['2', '3', '4', '5', '6', '6', '8', '8']
    assert [e['name'] for e in CORPUS['evidence_snapshots']] == ['evidence_snapshot_v1', 'evidence_snapshot_v2', 'evidence_snapshot_v3']


@pytest.mark.parametrize('name', sorted(by_name('canonical')))
def test_canonical_bytes_and_digest_unchanged(name):
    case = by_name('canonical')[name]
    expected = base64.b64decode(case['canonical_base64'])
    assert canonical(case['value']) == expected
    assert digest(case['value']) == case['digest'] == sha(expected)


def error_value(spec):
    if 'float' in spec:
        return float(spec['float'])
    if 'int' in spec:
        return spec['int']
    return ''.join(map(chr, spec['codepoints']))


@pytest.mark.parametrize('name', sorted(by_name('canonical_errors')))
def test_canonical_refusals_unchanged(name):
    case = by_name('canonical_errors')[name]
    with pytest.raises(Exception) as caught:
        canonical(error_value(case['value']))
    assert type(caught.value).__name__ == case['error_class']
    assert isinstance(caught.value, ValueError) == case['is_value_error']
    assert isinstance(caught.value, UnicodeError) == case['is_unicode_error']


@pytest.mark.parametrize('name', sorted(by_name('evidence_snapshots')))
def test_evidence_snapshot_bytes_unchanged(name):
    case = by_name('evidence_snapshots')[name]
    record = deepcopy(case['record'])
    snapshot = Configurations._snapshot(record)
    assert canonical(snapshot) == base64.b64decode(case['snapshot_base64'])
    assert digest(snapshot) == case['digest']
    assert record == case['record']


def test_receipt_payload_digests_and_rows_unchanged(tmp_path):
    store = Store(tmp_path / 'golden.sqlite')
    cases = by_name('receipts')
    accepted = cases['receipt_golden_accept']['inputs']
    rejected = cases['receipt_golden_reject']['inputs']
    assert store.command(accepted['actor'], None, accepted['category'], accepted['command_id'], accepted['payload'],
                         lambda db: accepted['result']) == accepted['result']
    with pytest.raises(DomainError):
        store.command(rejected['actor'], None, rejected['category'], rejected['command_id'], rejected['payload'],
                      lambda db: (_ for _ in ()).throw(DomainError(**rejected['error'])))
    with store.connection() as db:
        for case in cases.values():
            inputs = case['inputs']
            row = dict(db.execute('SELECT scope,payload_digest,state,result,error FROM receipts WHERE scope=? AND category=? AND command_id=?',
                                  ('actor:' + inputs['actor'], inputs['category'], inputs['command_id'])).fetchone())
            assert row == case['expected']


# Bundles whose frozen approach versions carry the retired ``cases`` field (ADR-0006). No
# reader for retired formats is kept (ADR-0007; development records may be discarded, owner
# authorization of 2026-10-18), so assembly refuses them; the corpus bytes stay pinned.
RETIRED_BUNDLES = frozenset({
    'bundle6_configuration4_model3_frozen5_approach',
    'bundle8_configuration4_model2_frozen7_approach2',
    'bundle8_configuration4_model4_frozen7_approach2_mixed',
})


def carries_retired_cases(bundle):
    closure = bundle['inputs']['frozen'].get('approach_closure') or {}
    return any('cases' in v['content'] for v in closure.get('approach_versions', []))


def test_only_bundles_with_retired_cases_are_retired_and_assembly_refuses_them(monkeypatch):
    assert {b['name'] for b in CORPUS['bundles'] if carries_retired_cases(b)} == RETIRED_BUNDLES
    for name in sorted(RETIRED_BUNDLES):
        inputs = by_name('bundles')[name]['inputs']
        files = {path: BLOBS[key] for path, key in inputs['prepared_files'].items()}
        selected = dict(inputs['selected'], files={path: BLOBS[key] for path, key in inputs['selected']['files'].items()})
        monkeypatch.setitem(assemble_bundle.__globals__, 'uid', lambda: inputs['bundle_id'])
        with pytest.raises(ValueError):
            assemble_bundle(inputs['run_id'], deepcopy(inputs['prepared']), files, deepcopy(inputs['frozen']), selected,
                            deepcopy(inputs['dependencies']))


@pytest.mark.parametrize('name', [b['name'] for b in CORPUS['bundles'] if b['name'] not in RETIRED_BUNDLES])
def test_bundle_manifest_files_and_record_digests_unchanged(name, monkeypatch):
    inputs = by_name('bundles')[name]['inputs']
    expected = by_name('bundles')[name]['expected']
    files = {path: BLOBS[key] for path, key in inputs['prepared_files'].items()}
    selected = dict(inputs['selected'], files={path: BLOBS[key] for path, key in inputs['selected']['files'].items()})
    # The bundle id is a fresh identifier at assembly; pin it to the captured value.
    monkeypatch.setitem(assemble_bundle.__globals__, 'uid', lambda: inputs['bundle_id'])
    before = deepcopy(inputs)
    bundle = assemble_bundle(inputs['run_id'], deepcopy(inputs['prepared']), files, deepcopy(inputs['frozen']), selected,
                             deepcopy(inputs['dependencies']))
    manifest = bundle['manifest']
    config = inputs['frozen']['configuration']
    model = inputs['frozen']['model_snapshot']
    scientific = project(config)
    actual = dict(schema_version=manifest['schema_version'], bundle_digest=manifest['bundle_digest'],
                  manifest_sha256=sha(canonical(manifest)),
                  files={path: sha(raw) for path, raw in sorted(bundle['files'].items())},
                  executable_digest=executable_digest(inputs['prepared']),
                  prepared_digest=digest({k: v for k, v in inputs['prepared'].items() if k != 'prepared_digest'}),
                  configuration_schema_version=config['schema_version'],
                  configuration_digest=digest({k: v for k, v in config.items() if k != 'digest'}),
                  configuration_sha256=sha(canonical(config)),
                  model_schema_version=model['schema_version'],
                  model_digest=digest({k: v for k, v in model.items() if k != 'digest'}),
                  model_sha256=sha(canonical(model)),
                  scientific_configuration_digest=scientific['digest'],
                  scientific_configuration_sha256=sha(canonical(scientific)))
    assert actual == expected
    # Retained identities are self-consistent with the stored records.
    assert expected['configuration_digest'] == config['digest'] and expected['model_digest'] == model['digest']
    assert expected['prepared_digest'] == inputs['prepared']['prepared_digest']
    assert expected['executable_digest'] == inputs['prepared']['executable_content_digest']
    assert manifest['bundle_digest'] == digest({k: v for k, v in manifest.items() if k != 'bundle_digest'})
    assert inputs == before
