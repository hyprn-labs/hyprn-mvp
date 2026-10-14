"""Empirical Documents prerequisites on the runner's real disposable backend."""
from hyprn_mvp_app.contracts import authored_schema
import pytest


def probe():
    import checks
    from documents_native_fixture import AtomicityProbe
    return AtomicityProbe(checks.PROJECTION_SCOPE, checks.NATIVE_BACKEND)


def test_documents_native_atomicity_identity_and_exact_original():
    p = probe()
    first = p.original(b"Exact original\x00\xff\n")
    second = p.original(b"Exact original\x00\xff\n")
    assert first['node_uuid'] != second['node_uuid']
    assert p.resolve_original(first['command']) == first
    assert p.resolve_original(second['command']) == second
    p.assert_original_refused(first)
    p.record('original-identity', dict(first=first, second=second, identity=p.identity()))


def test_documents_native_atomicity_atomic_commit_and_immutable_witness():
    p = probe()
    case = p.collection()
    before = p.snapshot(case['group_uuid'])
    command = p.command(case, revision=0, title='Committed', member='second')
    result = p.mutate(command)
    after = p.snapshot(case['group_uuid'])
    assert after == result['result']
    assert after['revision'] == 1 and after['title'] == 'Committed'
    assert after['members'] == [case['second']['node_uuid']]
    assert before['members'] == [case['first']['node_uuid']]
    p.assert_immutable(result['witness_uuid'])
    assert p.receipts(command) == [result]
    p.record('atomic-commit', dict(before=before, after=after, receipt=result))


def test_documents_native_atomicity_forced_exception_rolls_back_all_mutations():
    p = probe()
    case = p.collection()
    before = p.snapshot(case['group_uuid'])
    command = p.command(case, revision=0, title='Must roll back', member='second')
    with pytest.raises(RuntimeError, match='forced after witness store'):
        p.mutate(command, force_rollback=True)
    reopened = p.inspect_fresh(command)
    assert reopened['state'] == before
    assert reopened['receipts'] == []
    assert p.snapshot(case['group_uuid']) == before
    p.record('rollback', dict(before=before, fresh_process=reopened))


def test_documents_native_atomicity_sigkill_after_commit_before_reply_and_reopen():
    p = probe()
    case = p.collection()
    before = p.snapshot(case['group_uuid'])
    command = p.command(case, revision=0, title='Survives SIGKILL', member='second')
    killed = p.kill_after_commit(command)
    reopened = p.inspect_fresh(command)
    assert killed['returncode'] == -9 and killed['reply_received'] is False
    assert reopened['identity'] == p.identity()
    assert reopened['state']['revision'] == 1
    assert reopened['state']['title'] == 'Survives SIGKILL'
    assert reopened['state']['members'] == [case['second']['node_uuid']]
    assert len(reopened['receipts']) == 1
    assert p.mutate(command) == reopened['receipts'][0]
    assert p.inspect_fresh(command) == reopened
    p.record('sigkill-reopen', dict(before=before, killed=killed, reopened=reopened))


def test_documents_native_atomicity_replay_after_later_edits_and_conflict_refusal():
    p = probe()
    case = p.collection()
    original = p.command(case, revision=0, title='First edit', member='second')
    receipt = p.mutate(original)
    later = p.command(case, revision=1, title='Later edit', member='first')
    later_receipt = p.mutate(later)
    assert p.mutate(original) == receipt
    with pytest.raises(ValueError, match='command digest conflict'):
        p.mutate({**original, 'title': 'Changed payload'})
    with pytest.raises(ValueError, match='stale revision'):
        p.mutate(p.command(case, revision=0, title='Stale', member='second'))
    assert p.snapshot(case['group_uuid']) == later_receipt['result']
    assert p.receipts(original) == [receipt]
    p.record('later-edit-replay', dict(original=receipt, later=later_receipt,
                                     current=p.snapshot(case['group_uuid'])))


def test_documents_native_atomicity_physical_group_delete_leaves_no_receipt_and_loses_the_group():
    # Hazard control: a physical group delete inside the receipt transaction closes that
    # transaction, removes the group irreversibly and records no receipt. Collections are
    # therefore deleted logically (test_documents_collection_protocol.py); prior receipts and
    # originals are unaffected.
    p = probe()
    case = p.collection()
    edit = p.command(case, revision=0, title='Prior edit', member='second')
    prior = p.mutate(edit)
    deletion = p.command(case, revision=1, action='delete')
    failure = None
    try:
        p.mutate(deletion)
    except Exception as error:
        failure = type(error).__name__
    reopened = p.inspect_fresh(deletion)
    p.record('delete-attempt', dict(before=prior['result'], exception=failure, reopened=reopened,
        prior_receipts=p.receipts(edit),
        original_first=p.resolve_original(case['first']['command']),
        original_second=p.resolve_original(case['second']['command'])))
    assert failure is not None
    assert reopened['state'] is None
    assert reopened['receipts'] == []
    assert p.receipts(edit) == [prior]
    assert p.resolve_original(case['first']['command']) == case['first']
    assert p.resolve_original(case['second']['command']) == case['second']


def test_documents_native_atomicity_physical_group_delete_escapes_forced_rollback():
    # Hazard control: a forced failure after a physical group delete does not restore the group;
    # the transaction is already closed, so the forced exception is never reached.
    p = probe()
    case = p.collection()
    before = p.snapshot(case['group_uuid'])
    deletion = p.command(case, revision=0, action='delete')
    failure = None
    try:
        p.mutate(deletion, force_rollback=True)
    except Exception as error:
        failure = type(error).__name__
    reopened = p.inspect_fresh(deletion)
    p.record('delete-rollback', dict(before=before, exception=failure, reopened=reopened))
    assert before is not None
    assert failure is not None and failure != 'RuntimeError'
    assert reopened['state'] is None
    assert reopened['receipts'] == []


# Production adapter coverage. The transaction probes above characterize the native store;
# the two physical-delete probes are hazard controls that keep proving why deletion is logical.
import base64
import copy
import hashlib
import io
import json
from contextlib import contextmanager
from uuid import uuid4


def docs26_case(raw=b'Exact original\x00\xff\n'):
    import checks
    from hyprn_mvp_integration.documents import NativeDocuments, payload_digest
    scope = checks.PROJECTION_SCOPE
    adapter = NativeDocuments(checks.NATIVE_BACKEND,
                              study_id=scope.run_uuid, native_store_id=scope.store_uuid)
    command = str(uuid4())
    payload = dict(request=dict(command_id=command, filename='original.txt',
        media_type='text/plain', byte_length=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
        reserved_ids=dict(document_id=str(uuid4()), version_id=str(uuid4())), transfer_id=str(uuid4()))
    identity = dict(study_id=scope.run_uuid, actor_id=str(uuid4()), command_id=command,
                    operation_id=str(uuid4()), payload_sha256=payload_digest(payload))
    return adapter, identity, payload, raw


def docs26_counts(adapter):
    from aiida import orm
    return (orm.QueryBuilder(backend=adapter.backend).append(orm.SinglefileData).count(),
            orm.QueryBuilder(backend=adapter.backend).append(orm.Dict).count())


@pytest.mark.parametrize('raw', [b'', b'Exact\x00\xff\r\n', b'x' * 10485760], ids=['empty', 'binary', 'maximum'])
def test_documents_native_originals_exact_bytes_descriptor_bounded_read_and_replay(raw):
    adapter, identity, payload, raw = docs26_case(raw)
    before = docs26_counts(adapter)
    receipt = adapter.store_original(identity, payload, io.BytesIO(raw))
    association = receipt['associations'][0]
    assert receipt['result'] == adapter.descriptor(association)
    assert receipt['result']['original_sha256'] == hashlib.sha256(raw).hexdigest()
    assert receipt['result']['original_size'] == len(raw)
    assert b''.join(adapter.stream(association)) == raw
    reply = adapter.read(association, offset=0, byte_length=min(len(raw), 262144))
    assert base64.b64decode(reply['bytes'], validate=True) == raw[:262144]
    assert reply['descriptor']['payload_sha256'] == hashlib.sha256(raw[:262144]).hexdigest()
    assert adapter.reconcile(identity) == receipt
    assert adapter.store_original(identity, payload, io.BytesIO(raw)) == receipt
    assert docs26_counts(adapter) == (before[0] + 1, before[1] + 1)
    assert set(receipt['result']).isdisjoint({'native_entity_id', 'native_store_id'})


@pytest.mark.parametrize('boundary', ['before_original', 'after_original', 'after_witness', 'after_commit'])
def test_documents_native_originals_transaction_failures_and_lost_reply(boundary, monkeypatch):
    from aiida import orm
    adapter, identity, payload, raw = docs26_case()
    before = docs26_counts(adapter)
    def fail():
        raise RuntimeError('injected ' + boundary)
    with monkeypatch.context() as patch:
        if boundary in ('before_original', 'after_original'):
            original = orm.SinglefileData.store
            def store(node, *args, **kwargs):
                if boundary == 'before_original': fail()
                original(node, *args, **kwargs)
                fail()
            patch.setattr(orm.SinglefileData, 'store', store)
        elif boundary == 'after_witness':
            original = orm.Dict.store
            def store(node, *args, **kwargs):
                original(node, *args, **kwargs)
                fail()
            patch.setattr(orm.Dict, 'store', store)
        else:
            transaction = adapter.backend.transaction
            @contextmanager
            def committed_then_lost():
                with transaction(): yield
                fail()
            patch.setattr(adapter.backend, 'transaction', committed_then_lost)
        with pytest.raises(RuntimeError, match='injected'):
            adapter.store_original(identity, payload, io.BytesIO(raw))
    prior = adapter.reconcile(identity)
    assert (prior is not None) == (boundary == 'after_commit')
    assert docs26_counts(adapter) == (tuple(n + 1 for n in before) if prior else before)
    result = adapter.store_original(identity, payload, io.BytesIO(raw))
    if prior: assert result == prior
    assert docs26_counts(adapter) == tuple(n + 1 for n in before)


@pytest.mark.parametrize('field', ['filename', 'sha256', 'version_id', 'actor_id', 'operation_id', 'transfer_id'])
def test_documents_native_originals_same_command_changed_payload_conflicts(field):
    from hyprn_mvp_integration.documents import payload_digest
    adapter, identity, payload, raw = docs26_case()
    adapter.store_original(identity, payload, io.BytesIO(raw))
    before = docs26_counts(adapter)
    identity, payload = copy.deepcopy(identity), copy.deepcopy(payload)
    if field in ('actor_id', 'operation_id'): identity[field] = str(uuid4())
    elif field == 'version_id': payload['reserved_ids'][field] = str(uuid4())
    elif field == 'transfer_id': payload[field] = str(uuid4())
    else: payload['request'][field] = 'changed.txt' if field == 'filename' else '0' * 64
    identity['payload_sha256'] = payload_digest(payload)
    with pytest.raises(ValueError): adapter.store_original(identity, payload, io.BytesIO(raw))
    assert docs26_counts(adapter) == before


@pytest.mark.parametrize('change', ['extra', 'size_bool', 'oversize', 'bad_hash', 'wrong_command',
                                   'family_pair', 'wrong_family', 'extra_reserved', 'bad_media'])
def test_documents_native_originals_malformed_command_refuses_without_effect(change):
    from hyprn_mvp_integration.documents import payload_digest
    adapter, identity, payload, raw = docs26_case()
    before = docs26_counts(adapter)
    request = payload['request']
    if change == 'extra': payload['untrusted'] = True
    if change == 'size_bool': request['byte_length'] = True
    if change == 'oversize': request['byte_length'] = 10485761
    if change == 'bad_hash': request['sha256'] = 'not-a-digest'
    if change == 'wrong_command': request['command_id'] = str(uuid4())
    if change == 'family_pair': request['family_id'] = str(uuid4())
    if change == 'wrong_family': request.update(family_id=str(uuid4()), expected_revision=1)
    if change == 'extra_reserved': payload['reserved_ids']['collection_id'] = str(uuid4())
    if change == 'bad_media': request['media_type'] = 'text/html'
    identity['payload_sha256'] = payload_digest(payload)
    with pytest.raises(ValueError): adapter.store_original(identity, payload, io.BytesIO(raw))
    assert docs26_counts(adapter) == before


@pytest.mark.parametrize('raw', [b'wrong', b'', b'x' * 10485761], ids=['wrong', 'short', 'excess'])
def test_documents_native_originals_wrong_bytes_refuse_without_native_effect(raw):
    adapter, identity, payload, _ = docs26_case()
    before = docs26_counts(adapter)
    with pytest.raises(ValueError): adapter.store_original(identity, payload, io.BytesIO(raw))
    assert docs26_counts(adapter) == before


@pytest.mark.parametrize('field', ['native_store_id', 'native_entity_id', 'study_id', 'resource_id', 'resource_kind'])
def test_documents_native_originals_association_mismatch(field):
    adapter, identity, payload, raw = docs26_case()
    receipt = adapter.store_original(identity, payload, io.BytesIO(raw))
    association = dict(receipt['associations'][0])
    association[field] = 'collection' if field == 'resource_kind' else str(uuid4())
    with pytest.raises(ValueError): adapter.descriptor(association)
    with pytest.raises(ValueError): adapter.read(association, offset=0, byte_length=1)


def test_documents_native_originals_witness_and_original_immutable_and_duplicate_refused():
    from aiida import orm
    from aiida.common.exceptions import ModificationNotAllowed
    adapter, identity, payload, raw = docs26_case()
    receipt = adapter.store_original(identity, payload, io.BytesIO(raw))
    node = orm.SinglefileData.get_collection(adapter.backend).get(uuid=receipt['associations'][0]['native_entity_id'])
    with pytest.raises(ModificationNotAllowed): node.base.attributes.set('hyprn_mvp_documents', {})
    witness = orm.QueryBuilder(backend=adapter.backend).append(orm.Dict,
        filters={'attributes.identity.command_id': identity['command_id']}).one()[0]
    with pytest.raises(ModificationNotAllowed): witness.base.attributes.set('result', {})
    orm.Dict(dict=receipt, backend=adapter.backend).store()
    before = docs26_counts(adapter)
    with pytest.raises(ValueError): adapter.reconcile(identity)
    with pytest.raises(ValueError): adapter.store_original(identity, payload, io.BytesIO(raw))
    assert docs26_counts(adapter) == before


def test_documents_native_originals_reserved_version_cannot_be_reused_by_new_command():
    from hyprn_mvp_integration.documents import payload_digest
    adapter, identity, payload, raw = docs26_case()
    adapter.store_original(identity, payload, io.BytesIO(raw))
    before = docs26_counts(adapter)
    identity['command_id'] = payload['request']['command_id'] = str(uuid4())
    identity['operation_id'] = str(uuid4())
    identity['payload_sha256'] = payload_digest(payload)
    with pytest.raises(ValueError): adapter.store_original(identity, payload, io.BytesIO(raw))
    assert docs26_counts(adapter) == before


@pytest.mark.parametrize('offset,length', [(-1, 1), (True, 1), (0, True), (0, 262145), (1000, 0), (0, 1000)])
def test_documents_native_originals_read_range_refusal(offset, length):
    adapter, identity, payload, raw = docs26_case()
    receipt = adapter.store_original(identity, payload, io.BytesIO(raw))
    with pytest.raises(ValueError): adapter.read(receipt['associations'][0], offset=offset, byte_length=length)


def test_documents_native_originals_wrong_backend_identity_and_unwitnessed_metadata():
    from aiida import orm
    from hyprn_mvp_integration.documents import NativeDocuments
    adapter, identity, payload, raw = docs26_case()
    with pytest.raises(ValueError): NativeDocuments(adapter.backend, study_id=identity['study_id'], native_store_id=str(uuid4()))
    node = orm.SinglefileData.from_bytes(raw, filename='original.bin', backend=adapter.backend)
    node.base.attributes.set('hyprn_mvp_documents', {'identity': identity})
    node.store()
    association = dict(schema_version='1', study_id=identity['study_id'], resource_id=payload['reserved_ids']['version_id'],
        resource_kind='original', native_store_id=adapter.native_store_id, native_entity_id=node.uuid)
    with pytest.raises(ValueError): adapter.descriptor(association)


@pytest.mark.parametrize('corruption', ['bytes', 'version_hash', 'version_size', 'unknown_metadata',
    'node_association', 'witness_store', 'witness_result', 'witness_reserved', 'witness_category'])
def test_documents_native_originals_sealed_corrupt_original_or_witness_fails_closed(corruption):
    from aiida import orm
    adapter, identity, payload, raw = docs26_case()
    version = adapter._version(identity, payload, '2026-10-11T00:00:00Z')
    node = orm.SinglefileData.from_bytes(b'corrupt' if corruption == 'bytes' else raw,
                                       filename='original.bin', backend=adapter.backend)
    association = dict(schema_version='1', study_id=adapter.study_id,
        resource_id=payload['reserved_ids']['version_id'], resource_kind='original',
        native_store_id=adapter.native_store_id, native_entity_id=node.uuid)
    metadata = dict(identity=identity, payload=payload, version=version, association=association)
    witness = copy.deepcopy(adapter._witness(metadata))
    if corruption == 'version_hash': version['original_sha256'] = '0' * 64
    if corruption == 'version_size': version['original_size'] += 1
    if corruption == 'unknown_metadata': metadata['extra'] = 'untrusted'
    if corruption == 'node_association': metadata['association'] = {**association, 'native_entity_id': str(uuid4())}
    if corruption == 'witness_store': witness['native_store_id'] = str(uuid4())
    if corruption == 'witness_result': witness['result']['filename'] = 'different.txt'
    if corruption == 'witness_reserved': witness['reserved_ids']['version_id'] = str(uuid4())
    if corruption == 'witness_category': witness['category'] = 'collection_create'
    node.base.attributes.set('hyprn_mvp_documents', metadata)
    node.store()
    orm.Dict(dict=witness, backend=adapter.backend).store()
    before = docs26_counts(adapter)
    with pytest.raises(ValueError): adapter.reconcile(identity)
    with pytest.raises(ValueError): adapter.descriptor(association)
    with pytest.raises(ValueError): next(adapter.stream(association))
    with pytest.raises(ValueError): adapter.store_original(identity, payload, io.BytesIO(raw))
    assert docs26_counts(adapter) == before


def test_documents_native_originals_independent_commands_same_bytes_have_distinct_originals():
    adapter, identity, payload, raw = docs26_case()
    first = adapter.store_original(identity, payload, io.BytesIO(raw))
    _, second_identity, second_payload, _ = docs26_case(raw)
    second = adapter.store_original(second_identity, second_payload, io.BytesIO(raw))
    assert first['result']['original_sha256'] == second['result']['original_sha256']
    assert first['associations'][0]['native_entity_id'] != second['associations'][0]['native_entity_id']
    assert first['result']['version_id'] != second['result']['version_id']


def test_documents_native_originals_short_reads_bound_upload_and_public_wire_shapes():
    from pathlib import Path
    import jsonschema
    adapter, identity, payload, raw = docs26_case(b'\x00\xff' * 300000)
    class ShortReader(io.BytesIO):
        def read(self, size):
            assert 0 < size <= 262144
            return super().read(min(size, 711))
    witness = adapter.store_original(identity, payload, ShortReader(raw))
    association = witness['associations'][0]
    schema = authored_schema()
    for name, value in [('DocumentNativeWitness1', witness),
                        ('DocumentVersion1', adapter.descriptor(association)),
                        ('DocumentNativeOriginalReply1', adapter.read(association, offset=123, byte_length=262144))]:
        jsonschema.Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/' + name},
            format_checker=jsonschema.FormatChecker()).validate(value)
    assert base64.b64decode(adapter.read(association, offset=123, byte_length=262144)['bytes']) == raw[123:262267]


def docs26_child_script():
    # A child reopens ONLY the guard's already-allocated fixture, checking the
    # active pytest parent's identity before importing native code.
    return '''
import sys, json, io, signal
from pathlib import Path
from contextlib import contextmanager
repo = Path(sys.argv[1])
sys.path[:0] = [str(repo / 'deployment/tests'), str(repo / 'deployment'), str(repo / 'integration/src')]
from documents_native_fixture import reopen_probe
p = reopen_probe()
from hyprn_mvp_integration.documents import NativeDocuments
from aiida import orm
adapter = NativeDocuments(p.backend, study_id=p.scope.run_uuid, native_store_id=p.scope.store_uuid)
request = json.loads(Path(sys.argv[2]).read_text())
identity, payload = request['identity'], request['payload']
mode = sys.argv[3]
if mode == 'inspect':
    print(json.dumps(dict(receipt=adapter.reconcile(identity), identity=p.identity())), flush=True)
else:
    def wait():
        print(json.dumps(dict(boundary=mode, command_id=identity['command_id'], reply_sent=False)), flush=True)
        signal.pause()
        raise RuntimeError('Unexpected signal return')
    if mode == 'before_commit':
        store = orm.Dict.store
        def hooked(node, *args, **kwargs):
            store(node, *args, **kwargs)
            wait()
        orm.Dict.store = hooked
    else:
        transaction = p.backend.transaction
        @contextmanager
        def hooked():
            with transaction(): yield
            wait()
        p.backend.transaction = hooked
    adapter.store_original(identity, payload, io.BytesIO(bytes.fromhex(request['raw'])))
'''


@pytest.mark.parametrize('boundary', ['before_commit', 'after_commit'])
def test_documents_native_originals_actual_sigkill_and_fresh_process_reconciliation(boundary):
    import checks
    import scoped_fixture as guard
    from pathlib import Path
    import select
    import subprocess
    adapter, identity, payload, raw = docs26_case()
    scope = checks.PROJECTION_SCOPE
    before = docs26_counts(adapter)
    request = guard.scoped_path(scope, 'artifacts/original-' + str(uuid4()) + '.json')
    request.write_text(json.dumps(dict(identity=identity, payload=payload, raw=raw.hex())))
    def child(mode):
        return subprocess.Popen([guard.APPROVED_PYTHON, '-B', '-c', docs26_child_script(),
            str(Path(__file__).resolve().parents[2]), str(request), mode], cwd=scope.root,
            env=guard.clean_environment(scope), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    marker = ''
    with child(boundary) as process:
        try:
            assert select.select([process.stdout], [], [], 30)[0], 'Missing synchronization'
            marker = process.stdout.readline()
            assert json.loads(marker) == dict(boundary=boundary, command_id=identity['command_id'], reply_sent=False)
            assert process.poll() is None
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == -9 and not stdout
        finally:
            if process.poll() is None: process.kill()
            stdout, stderr = process.communicate(timeout=10)
            guard.scoped_path(scope, 'evidence/original-kill-' + boundary + '.json').write_text(json.dumps(
                dict(pid=process.pid, returncode=process.returncode, marker=marker, stdout=stdout, stderr=stderr)))
    with child('inspect') as process:
        try:
            stdout, stderr = process.communicate(timeout=30)
        finally:
            if process.poll() is None: process.kill()
        guard.scoped_path(scope, 'evidence/original-reopen-' + boundary + '.json').write_text(json.dumps(
            dict(pid=process.pid, returncode=process.returncode, stdout=stdout, stderr=stderr)))
        assert process.returncode == 0
        reopened = json.loads(stdout)
    assert reopened['identity']['repository_uuid'] == scope.store_uuid
    assert (reopened['receipt'] is not None) == (boundary == 'after_commit')
    assert docs26_counts(adapter) == (tuple(n + 1 for n in before) if reopened['receipt'] else before)
    result = adapter.store_original(identity, payload, io.BytesIO(raw))
    if reopened['receipt']: assert result == reopened['receipt']
    assert docs26_counts(adapter) == tuple(n + 1 for n in before)
