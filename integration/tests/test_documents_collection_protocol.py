"""24.1R logical deletion qualification, independent of historical physical tests."""
from uuid import uuid4
import pytest


def probe():
    import checks
    from documents_native_fixture import CollectionProtocolProbe
    return CollectionProtocolProbe(checks.PROJECTION_SCOPE, checks.NATIVE_BACKEND)


def test_documents_collection_protocol_terminal_commit_preserves_sources_and_other_group():
    p = probe()
    case = p.collection()
    before = p.inspect_fresh(p.command(case))
    command = p.command(case)
    receipt = p.mutate(command)
    after = p.inspect_fresh(command)
    assert after['state']['group_uuid'] == case['group_uuid']
    assert after['state']['collection_id'] == case['collection_id']
    assert after['state']['lifecycle'] == 'deleted'
    assert after['state']['members'] == [] and after['state']['revision'] == 1
    assert after['receipts'] == [receipt]
    assert after['sources'] == before['sources']
    assert after['other'] == before['other']
    assert case['group_uuid'] not in p.active_ids()
    p.assert_immutable(receipt['witness_uuid'])
    p.record('logical-commit', dict(before=before, after=after))


@pytest.mark.parametrize('boundary', ['removed', 'metadata', 'witness'])
def test_documents_collection_protocol_exception_rolls_back_every_boundary(boundary):
    p = probe()
    case = p.collection()
    command = p.command(case)
    before = p.inspect_fresh(command)
    with pytest.raises(RuntimeError, match='injected ' + boundary):
        p.mutate(command, fail_at=boundary)
    assert p.inspect_fresh(command) == before
    p.record('exception-' + boundary, dict(before=before, after=p.inspect_fresh(command)))


@pytest.mark.parametrize('boundary', ['removed', 'metadata', 'witness', 'committed'])
def test_documents_collection_protocol_actual_sigkill_and_separate_process_replay(boundary):
    p = probe()
    case = p.collection()
    command = p.command(case)
    before = p.inspect_fresh(command)
    killed = p.kill_at(command, boundary)
    assert killed['returncode'] == -9 and killed['reply_received'] is False
    after = p.inspect_fresh(command)
    assert after['identity'] == before['identity']
    if boundary == 'committed':
        assert after['state']['members'] == []
        assert after['state']['lifecycle'] == 'deleted' and after['state']['revision'] == 1
        assert len(after['receipts']) == 1
        assert p.replay_fresh(command) == after['receipts'][0]
        assert p.inspect_fresh(command) == after
    else:
        assert after == before and after['receipts'] == []
        assert p.replay_fresh(command)['result']['deleted'] is True
    p.record('logical-kill-' + boundary, dict(before=before, killed=killed, after=after))


def test_documents_collection_protocol_cas_conflicts_historical_receipts_no_resurrection():
    p = probe()
    case = p.collection()
    edit = p.command(case, action='edit', title='Later')
    earlier = p.mutate(edit)
    stale = p.command(case)
    before = p.inspect_fresh(stale)
    with pytest.raises(ValueError, match='stale_revision'): p.mutate(stale)
    assert p.inspect_fresh(stale) == before
    command = p.command(case, revision=1)
    terminal = p.mutate(command)
    before = p.inspect_fresh(command)
    for changed in ({'expected_revision': 0}, {'collection_id': str(uuid4())}, {'action': 'edit'}):
        with pytest.raises(ValueError, match='conflict'): p.mutate({**command, **changed})
    with pytest.raises(ValueError, match='resource_not_found'): p.mutate(p.command(case, revision=2))
    assert p.replay_fresh(edit) == earlier
    assert p.replay_fresh(case['create_command']) == case['create_receipt']
    assert p.replay_fresh(command) == terminal
    assert p.inspect_fresh(command) == before
    same_title = p.collection(title='Later')
    assert same_title['collection_id'] != case['collection_id']
    assert same_title['group_uuid'] != case['group_uuid']
    assert case['group_uuid'] not in p.active_ids()
    p.record('historical-replay', dict(before=before, earlier=earlier, create=case['create_receipt']))


@pytest.mark.parametrize('fault', ['foreign-study', 'foreign-store', 'reserved-id', 'missing-group',
    'unknown-lifecycle', 'missing-lifecycle', 'bad-revision', 'missing-witness',
    'bad-marker', 'nonempty-tombstone', 'duplicate-witness', 'conflicting-witness', 'wrong-witness-store'])
def test_documents_collection_protocol_integrity_and_scope_fail_closed_without_effects(fault):
    p = probe()
    case = p.collection()
    command = p.command(case)
    rejected = p.corrupt(case, command, fault)
    before = p.inspect_fresh(command)
    with pytest.raises(ValueError): p.mutate(rejected)
    assert p.inspect_fresh(command) == before
    p.record('integrity-' + fault, dict(command=rejected, before=before))


@pytest.mark.parametrize('count', [0, 10000])
def test_documents_collection_protocol_empty_and_actual_maximum_atomic_removal(count):
    p = probe()
    case = p.collection(count=count)
    command = p.command(case)
    before = p.inspect_fresh(command)
    assert len(before['state']['members']) == count
    assert len(set(before['state']['members'])) == count
    for boundary in ('removed', 'metadata', 'witness'):
        with pytest.raises(RuntimeError, match='injected ' + boundary): p.mutate(command, fail_at=boundary)
        assert p.inspect_fresh(command) == before
    receipt = p.mutate(command)
    after = p.inspect_fresh(command)
    assert after['state']['members'] == [] and after['state']['revision'] == 1
    assert after['state']['lifecycle'] == 'deleted' and after['receipts'] == [receipt]
    assert after['sources'] == before['sources'] and len(after['sources']) == count
    assert after['other'] == before['other']
    assert p.replay_fresh(command) == receipt
    assert p.inspect_fresh(command) == after
    p.record('capacity-' + str(count), dict(before=before, after=after))


@pytest.mark.parametrize('operation', ['clear', 'physical-delete'])
def test_documents_collection_protocol_unsupported_apis_are_negative_hazard_controls(operation):
    p = probe()
    result = p.hazard_control(operation)
    assert result['exception'] == 'RuntimeError'
    assert result['after']['receipts'] == []
    if operation == 'clear':
        assert result['before']['state']['members']
        assert result['after']['state']['members'] == []
    else:
        assert result['before']['state'] is not None and result['after']['state'] is None
    p.record('hazard-' + operation, result)
