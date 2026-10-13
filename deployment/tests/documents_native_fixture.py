"""Guarded Documents native fixture entry; no native imports at module load.

Transaction probes are qualified here. Real execution, snapshot and preparation proofs
need their own capability functions; an unavailable one fails in the runner before
allocation, and registering a route does not qualify that capability.
"""
import scoped_fixture as guard
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
from uuid import UUID, uuid4


def start(*, group):
    scope = guard.documents_scope(guard.APPROVED_PYTHON)
    from checks import DOCUMENTS_ROUTES, documents_targets
    route = DOCUMENTS_ROUTES.get(group)
    if route is None or route['mode'] != 'native':
        raise ValueError('Explicit Documents native group required')
    documents_targets(group)
    # Supported existing isolated profile machinery, never a default profile.
    # It validates again before importing AiiDA and binds its generated store UUID.
    return guard.create_native_fixture(scope)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class AtomicityProbe:
    """Test-only native protocol experiment; no application membership authority.

    The caller owns one serialized writer. This does not qualify simultaneous
    writers, application authorization, or a production Documents adapter.
    All mutations use public ORM methods and StorageBackend.transaction().
    """

    def __init__(self, scope, backend):
        from importlib.metadata import version
        guard.validate_scope(scope)
        if backend is None or version('aiida-core') != '2.9.3':
            raise ValueError('Pinned real AiiDA backend required')
        self.scope, self.backend = scope, backend
        if (str(UUID(backend.profile.uuid)) != scope.profile_uuid
                or backend.profile.name != scope.profile
                or backend.profile.storage_backend != scope.backend
                or backend.profile.storage_config != {'filepath': str(scope.root / 'native')}
                or str(UUID(backend.get_repository().uuid)) != scope.store_uuid):
            raise ValueError('Native probe identity mismatch')

    def identity(self):
        database = guard.no_symlinks(self.scope.root / 'native/database.sqlite')
        return dict(scope=self.scope.record(), aiida_version='2.9.3',
                    database_path=str(database), database_inode=database.stat().st_ino,
                    repository_path=str(self.scope.root / 'native/container'),
                    repository_uuid=str(UUID(self.backend.get_repository().uuid)))

    def record(self, label, value):
        target = guard.scoped_path(self.scope, 'evidence/atomicity-' + label + '.json')
        with target.open('x') as output:
            json.dump(value, output, indent=2)
            output.write('\n')

    def _scope_fields(self):
        return dict(study_id=self.scope.run_uuid, store_uuid=self.scope.store_uuid)

    def receipts(self, command):
        from aiida import orm
        filters = {'attributes.protocol': 'hyprn_mvp.documents.probe1',
                   'attributes.command_id': command['command_id'],
                   **{'attributes.' + key: value for key, value in self._scope_fields().items()}}
        nodes = orm.QueryBuilder(backend=self.backend).append(orm.Dict, filters=filters).all(flat=True)
        return [dict(witness_uuid=node.uuid, **node.get_dict()) for node in nodes]

    def _prior(self, command):
        if any(command.get(k) != v for k, v in self._scope_fields().items()):
            raise ValueError('command scope mismatch')
        prior = self.receipts(command)
        if len(prior) > 1:
            raise ValueError('multiple witnesses: uncertain')
        if prior and prior[0]['payload_digest'] != digest(command):
            raise ValueError('command digest conflict')
        return prior[0] if prior else None

    def _witness(self, command, result):
        from aiida import orm
        node = orm.Dict(dict=dict(protocol='hyprn_mvp.documents.probe1',
            **self._scope_fields(), command_id=command['command_id'],
            payload_digest=digest(command), result=result), backend=self.backend).store()
        return dict(witness_uuid=node.uuid, **node.get_dict())

    def original(self, content):
        from aiida import orm
        command = dict(**self._scope_fields(), command_id=str(uuid4()),
            version_id=str(uuid4()), action='original', size=len(content),
            sha256=hashlib.sha256(content).hexdigest())
        with self.backend.transaction():
            node = orm.SinglefileData.from_bytes(content, filename='original.bin', backend=self.backend)
            node.base.attributes.set('hyprn_mvp_documents', command)
            node.store()
            result = dict(node_uuid=node.uuid, version_id=command['version_id'],
                          sha256=command['sha256'], size=command['size'])
            witness = self._witness(command, result)
        return dict(**result, command=command, witness_uuid=witness['witness_uuid'])

    def resolve_original(self, command):
        from aiida import orm
        witness = self._prior(command)
        if witness is None:
            raise ValueError('original witness absent')
        result = witness['result']
        node = orm.SinglefileData.get_collection(self.backend).get(uuid=result['node_uuid'])
        if node.base.attributes.get('hyprn_mvp_documents') != command:
            raise ValueError('original association mismatch')
        content = node.get_content(mode='rb')
        if (hashlib.sha256(content).hexdigest() != result['sha256']
                or len(content) != result['size'] or result['version_id'] != command['version_id']):
            raise ValueError('original bytes mismatch')
        return dict(**result, command=command, witness_uuid=witness['witness_uuid'])

    def assert_original_refused(self, original):
        for field in ('version_id', 'store_uuid', 'study_id', 'command_id'):
            command = {**original['command'], field: str(uuid4())}
            try:
                self.resolve_original(command)
            except ValueError:
                continue
            raise AssertionError('forged original lookup accepted: ' + field)
        self.assert_immutable(original['witness_uuid'])

    def assert_immutable(self, witness_uuid):
        from aiida import orm
        from aiida.common.exceptions import ModificationNotAllowed
        node = orm.Dict.get_collection(self.backend).get(uuid=witness_uuid)
        before = node.get_dict()
        try:
            node.base.attributes.set('payload_digest', '0' * 64)
        except ModificationNotAllowed:
            pass
        else:
            raise AssertionError('Stored witness attributes were mutable')
        assert orm.Dict.get_collection(self.backend).get(uuid=witness_uuid).get_dict() == before

    def collection(self):
        from aiida import orm
        first, second = self.original(b'Original A\n'), self.original(b'Original B\n')
        with self.backend.transaction():
            group = orm.Group(label='documents-probe-' + str(uuid4()),
                              description='Before description', backend=self.backend).store()
            group.base.extras.set('hyprn_mvp_documents', dict(**self._scope_fields(), revision=0, title='Before'))
            group.add_nodes(orm.SinglefileData.get_collection(self.backend).get(uuid=first['node_uuid']))
        return dict(group_uuid=group.uuid, first=first, second=second)

    def snapshot(self, group_uuid):
        from aiida import orm
        from aiida.common.exceptions import NotExistent
        try:
            group = orm.Group.get_collection(self.backend).get(uuid=group_uuid)
        except NotExistent:
            return None
        data = group.base.extras.get('hyprn_mvp_documents')
        if any(data[k] != v for k, v in self._scope_fields().items()):
            raise ValueError('group scope mismatch')
        return dict(group_uuid=group.uuid, label=group.label, description=group.description,
                    **data, members=sorted(node.uuid for node in group.nodes))

    def command(self, case, *, revision, title='', member='first', action='edit'):
        return dict(**self._scope_fields(), command_id=str(uuid4()), action=action,
                    group_uuid=case['group_uuid'], expected_revision=revision,
                    title=title, description='Description: ' + title,
                    members=[case[member]['node_uuid']])

    def mutate(self, command, *, force_rollback=False):
        from aiida import orm
        with self.backend.transaction():
            prior = self._prior(command)
            if prior is not None:
                return prior
            before = self.snapshot(command['group_uuid'])
            if before is None:
                raise ValueError('group absent')
            if before['revision'] != command['expected_revision']:
                raise ValueError('stale revision')
            group = orm.Group.get_collection(self.backend).get(uuid=command['group_uuid'])
            if command['action'] == 'delete':
                orm.Group.get_collection(self.backend).delete(group.pk)
                result = dict(group_uuid=group.uuid, deleted=True, revision=before['revision'] + 1)
            elif command['action'] == 'edit':
                group.description = command['description']
                group.base.extras.set('hyprn_mvp_documents', dict(**self._scope_fields(),
                    revision=before['revision'] + 1, title=command['title']))
                # Group.clear() commits unconditionally in AiiDA 2.9.3.
                # The supported remove/add API respects the outer transaction.
                group.remove_nodes(list(group.nodes))
                group.add_nodes([orm.SinglefileData.get_collection(self.backend).get(uuid=uid)
                                 for uid in command['members']])
                result = self.snapshot(group.uuid)
            else:
                raise ValueError('unsupported probe command')
            receipt = self._witness(command, result)
            if force_rollback:
                # Fail only after *every* mutation, including stored receipt.
                raise RuntimeError('forced after witness store')
        return receipt

    def _child(self, command, mode):
        request = guard.scoped_path(self.scope, 'artifacts/probe-' + str(uuid4()) + '.json')
        request.write_text(json.dumps(command))
        argv = [guard.APPROVED_PYTHON, '-B', str(Path(__file__).resolve()),
                '--atomicity-child', mode, str(request.relative_to(self.scope.root))]
        return subprocess.Popen(argv, cwd=self.scope.root, env=guard.clean_environment(self.scope),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def inspect_fresh(self, command):
        with self._child(command, 'inspect') as child:
            try:
                stdout, stderr = child.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                stdout, stderr = child.communicate()
                self.record('inspect-timeout-' + str(uuid4()), dict(stdout=stdout, stderr=stderr))
                raise
            self.record('inspect-' + str(uuid4()), dict(pid=child.pid, returncode=child.returncode,
                                                       stdout=stdout, stderr=stderr))
            if child.returncode != 0:
                raise AssertionError('Fresh native inspection failed; see evidence')
            return json.loads(stdout)

    def kill_after_commit(self, command):
        with self._child(command, 'commit-wait') as child:
            marker_line = ''
            try:
                if not select.select([child.stdout], [], [], 30)[0]:
                    raise AssertionError('No commit synchronization within 30 seconds')
                marker_line = child.stdout.readline()
                marker = json.loads(marker_line)
                assert marker == {'committed': command['command_id'], 'reply_sent': False}
                assert child.poll() is None
                child.kill()  # Actual SIGKILL, no finally/rollback path in writer.
                stdout, stderr = child.communicate(timeout=10)
                assert not stdout, 'Business reply unexpectedly emitted'
                return dict(pid=child.pid, returncode=child.returncode, marker=marker,
                            reply_received=False, stdout=stdout, stderr=stderr)
            finally:
                if child.poll() is None:
                    child.kill()
                stdout, stderr = child.communicate(timeout=10)
                self.record('writer-' + str(uuid4()), dict(pid=child.pid,
                    returncode=child.returncode, marker=marker_line, stdout=stdout, stderr=stderr))


def reopen_probe():
    """Reopen only this active runner's store; never allocate or consume a scope.

    This deliberately does not call documents_scope(), whose exclusive claim
    belongs to the parent pytest process. Reopen validates that exact parent
    claim and the pristine allowlisted environment before native import.
    """
    scope = guard.scope_from_environment()
    if sys.executable != guard.APPROVED_PYTHON or scope.interpreter != guard.APPROVED_PYTHON:
        raise ValueError('Reviewed native probe interpreter required')
    claim = json.loads(guard.scoped_path(scope, 'evidence/documents-child.json').read_text())
    if claim != dict(pid=os.getppid(), run_uuid=scope.run_uuid, interpreter=guard.APPROVED_PYTHON):
        raise ValueError('Only active native fixture parent may reopen its store')
    for relative in ('native/database.sqlite', 'native/database.sqlite-wal',
                     'native/database.sqlite-shm', 'native/container', 'aiida/.aiida'):
        guard.no_symlinks(scope.root / relative)
    if not (scope.root / 'native/database.sqlite').is_file():
        raise ValueError('Existing isolated database required')
    from aiida import load_profile
    from aiida.manage import get_manager
    load_profile(scope.profile)
    return AtomicityProbe(scope, get_manager().get_profile_storage())


def atomicity_child():
    if (len(sys.argv) != 4 or sys.argv[1] != '--atomicity-child'
            or sys.argv[2] not in ('inspect', 'commit-wait')):
        raise ValueError('Fixed atomicity child mode required')
    probe = reopen_probe()
    command = json.loads(guard.scoped_path(probe.scope, sys.argv[3]).read_text())
    if sys.argv[2] == 'inspect':
        print(json.dumps(dict(identity=probe.identity(), state=probe.snapshot(command['group_uuid']),
                              receipts=probe.receipts(command))), flush=True)
    else:
        probe.mutate(command)
        # Test synchronization only: no receipt/result/business reply transmitted.
        print(json.dumps({'committed': command['command_id'], 'reply_sent': False}), flush=True)
        signal.pause()
        raise RuntimeError('Writer unexpectedly resumed before SIGKILL')




class CollectionProtocolProbe(AtomicityProbe):
    """Separate finite 24.1R experiment. Historical AtomicityProbe is unchanged."""

    protocol = 'hyprn_mvp.documents.collection-probe2'

    def __init__(self, scope, backend):
        super().__init__(scope, backend)
        self.observations = {}

    def receipts(self, command):
        from aiida import orm
        filters = {'attributes.protocol': self.protocol,
                   'attributes.command_id': command['command_id'],
                   **{'attributes.' + k: v for k, v in self._scope_fields().items()}}
        return [dict(witness_uuid=n.uuid, **n.get_dict()) for n in
                orm.QueryBuilder(backend=self.backend).append(orm.Dict, filters=filters).all(flat=True)]

    def _witness(self, command, result):
        from aiida import orm
        node = orm.Dict(dict=dict(protocol=self.protocol, **self._scope_fields(),
            command_id=command['command_id'], operation=command['action'],
            collection_id=command['collection_id'], group_uuid=command['group_uuid'],
            previous_revision=command['expected_revision'], revision=result['revision'],
            payload_digest=digest(command), result=result), backend=self.backend).store()
        return dict(witness_uuid=node.uuid, **node.get_dict())

    def _prior(self, command):
        if any(command.get(k) != v for k, v in self._scope_fields().items()):
            raise ValueError('resource_not_found')
        prior = self.receipts(command)
        if len(prior) > 1:
            raise ValueError('multiple witnesses: uncertain')
        if not prior:
            return None
        witness = prior[0]
        if witness['payload_digest'] != digest(command):
            raise ValueError('command digest conflict')
        for field in ('collection_id', 'group_uuid'):
            if witness.get(field) != command[field] or witness['result'].get(field) != command[field]:
                raise ValueError('witness identity conflict')
        if (witness.get('operation') != command['action'] or
                witness.get('previous_revision') != command['expected_revision'] or
                witness.get('revision') != command['expected_revision'] + 1 or
                witness['result'].get('revision') != witness['revision']):
            raise ValueError('witness outcome conflict')
        if command['action'] == 'delete':
            self.validate_state(command['group_uuid'])
        return witness

    def collection(self, *, count=2, title='Before'):
        from aiida import orm
        import time
        started = time.monotonic()
        if count not in (0, 2, 10000):
            raise ValueError('Fixed qualification sizes only')
        with self.backend.transaction():
            nodes = []
            for i in range(count):
                raw = ('Original %d\n' % i).encode()
                node = orm.SinglefileData.from_bytes(raw, filename='original.bin', backend=self.backend)
                node.base.attributes.set('hyprn_mvp_documents', dict(**self._scope_fields(),
                    version_id=str(uuid4()), sha256=hashlib.sha256(raw).hexdigest(), size=len(raw)))
                nodes.append(node.store())
            group = orm.Group(label='documents-logical-' + str(uuid4()),
                              description='Preserved description', backend=self.backend).store()
            collection_id = str(uuid4())
            group.base.extras.set('hyprn_mvp_documents', dict(**self._scope_fields(),
                collection_id=collection_id, revision=0, title=title, lifecycle='active'))
            group.add_nodes(nodes)
            other = orm.Group(label='documents-other-' + str(uuid4()), backend=self.backend).store()
            other.add_nodes(nodes)
            case = dict(group_uuid=group.uuid, collection_id=collection_id)
            command = self.command(case, revision=-1, action='create', title=title)
            receipt = self._witness(command, dict(group_uuid=group.uuid,
                collection_id=collection_id, revision=0, deleted=False))
        self.observations[group.uuid] = other.uuid
        self.record('setup-' + group.uuid, dict(count=count,
            duration_seconds=time.monotonic() - started, group_uuid=group.uuid,
            collection_id=collection_id, other_uuid=other.uuid, create_receipt=receipt))
        return dict(**case, create_command=command, create_receipt=receipt)

    def command(self, case, *, revision=0, action='delete', title='Before'):
        return dict(**self._scope_fields(), command_id=str(uuid4()), action=action,
            collection_id=case['collection_id'], group_uuid=case['group_uuid'],
            expected_revision=revision, title=title)

    def snapshot(self, group_uuid):
        from aiida import orm
        from aiida.common.exceptions import NotExistent
        try:
            group = orm.Group.get_collection(self.backend).get(uuid=group_uuid)
        except NotExistent:
            return None
        data = group.base.extras.get('hyprn_mvp_documents')
        if any(data[k] != v for k, v in self._scope_fields().items()):
            raise ValueError('group scope mismatch')
        members = orm.QueryBuilder(backend=self.backend).append(orm.Group,
            filters={'uuid': group_uuid}, tag='collection').append(orm.Node,
            with_group='collection', project='uuid').all(flat=True)
        return dict(group_uuid=group.uuid, label=group.label, description=group.description,
                    **data, members=sorted(members))

    def validate_state(self, group_uuid):
        state = self.snapshot(group_uuid)
        if state is None:
            raise ValueError('associated group absent: uncertain')
        if (state.get('lifecycle') not in ('active', 'deleted') or
                type(state.get('revision')) is not int or state['revision'] < 0):
            raise ValueError('malformed lifecycle/revision')
        try:
            UUID(state['collection_id'])
        except (ValueError, TypeError, KeyError):
            raise ValueError('malformed collection identity') from None
        if state['lifecycle'] == 'deleted':
            marker = state.get('deletion')
            if (state['members'] or not isinstance(marker, dict) or
                    set(marker) != {'command_id', 'payload_digest'}):
                raise ValueError('invalid terminal marker/membership')
            receipts = self.receipts(marker)
            if len(receipts) != 1:
                raise ValueError('terminal witness missing or multiple')
            witness = receipts[0]
            if (witness.get('operation') != 'delete' or
                    witness.get('payload_digest') != marker['payload_digest'] or
                    witness.get('group_uuid') != group_uuid or
                    witness.get('collection_id') != state['collection_id'] or
                    witness.get('revision') != state['revision'] or
                    witness.get('previous_revision') != state['revision'] - 1 or
                    witness.get('result') != dict(group_uuid=group_uuid,
                        collection_id=state['collection_id'], revision=state['revision'], deleted=True)):
                raise ValueError('terminal witness mismatch')
        elif 'deletion' in state:
            raise ValueError('active terminal marker mismatch')
        return state

    def active_ids(self):
        from aiida import orm
        # Native predicate precedes bounded pagination; no app membership cache.
        filters = {'extras.hyprn_mvp_documents.lifecycle': 'active',
            **{'extras.hyprn_mvp_documents.' + k: v for k, v in self._scope_fields().items()}}
        return orm.QueryBuilder(backend=self.backend).append(orm.Group, filters=filters,
            project='uuid').order_by({orm.Group: {'id': 'asc'}}).limit(100).all(flat=True)

    def mutate(self, command, *, fail_at=None, wait_at=None):
        from aiida import orm
        def boundary(name):
            if fail_at == name:
                raise RuntimeError('injected ' + name)
            if wait_at == name:
                print(json.dumps(dict(boundary=name, command_id=command['command_id'],
                                      reply_sent=False)), flush=True)
                signal.pause()
                raise RuntimeError('Writer unexpectedly resumed')
        with self.backend.transaction():
            prior = self._prior(command)
            if prior is not None:
                return prior
            before = self.validate_state(command['group_uuid'])
            if before['collection_id'] != command['collection_id']:
                raise ValueError('reserved identity mismatch')
            if before['lifecycle'] == 'deleted':
                raise ValueError('resource_not_found')
            if before['revision'] != command['expected_revision']:
                raise ValueError('stale_revision')
            group = orm.Group.get_collection(self.backend).get(uuid=command['group_uuid'])
            data = group.base.extras.get('hyprn_mvp_documents')
            if command['action'] == 'delete':
                group.remove_nodes(list(group.nodes))
                boundary('removed')
                data.update(lifecycle='deleted', revision=before['revision'] + 1,
                    deletion=dict(command_id=command['command_id'], payload_digest=digest(command)))
            elif command['action'] == 'edit':
                data.update(title=command['title'], revision=before['revision'] + 1)
            else:
                raise ValueError('unsupported operation')
            group.base.extras.set('hyprn_mvp_documents', data)
            boundary('metadata')
            result = dict(group_uuid=group.uuid, collection_id=data['collection_id'],
                          revision=data['revision'], deleted=data['lifecycle'] == 'deleted')
            receipt = self._witness(command, result)
            boundary('witness')
        boundary('committed')
        return receipt

    def _child(self, command, mode):
        request = guard.scoped_path(self.scope, 'artifacts/logical-' + str(uuid4()) + '.json')
        request.write_text(json.dumps(dict(command=command,
            other_uuid=self.observations.get(command['group_uuid']))))
        return subprocess.Popen([guard.APPROVED_PYTHON, '-B', str(Path(__file__).resolve()),
            '--collection-protocol-child', mode, str(request.relative_to(self.scope.root))],
            cwd=self.scope.root, env=guard.clean_environment(self.scope),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def inspect_fresh(self, command):
        return self._result_fresh(command, 'inspect')

    def replay_fresh(self, command):
        return self._result_fresh(command, 'replay')

    def _result_fresh(self, command, mode):
        with self._child(command, mode) as child:
            try:
                stdout, stderr = child.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                stdout, stderr = child.communicate()
                self.record('logical-timeout-' + str(uuid4()), dict(pid=child.pid,
                    returncode=child.returncode, stdout=stdout, stderr=stderr))
                raise
            self.record('logical-child-' + str(uuid4()), dict(mode=mode, pid=child.pid,
                returncode=child.returncode, stdout=stdout, stderr=stderr))
            if child.returncode:
                raise AssertionError('Logical child failed: ' + stderr[-3000:])
            return json.loads(stdout)

    def kill_at(self, command, boundary):
        with self._child(command, boundary) as child:
            marker_line = ''
            stdout = stderr = ''
            try:
                if not select.select([child.stdout], [], [], 30)[0]:
                    raise AssertionError('No writer synchronization within 30 seconds')
                marker_line = child.stdout.readline()
                assert json.loads(marker_line) == dict(boundary=boundary,
                    command_id=command['command_id'], reply_sent=False)
                assert child.poll() is None
                child.kill()
                stdout, stderr = child.communicate(timeout=10)
                assert child.returncode == -signal.SIGKILL and stdout == ''
                return dict(pid=child.pid, signal='SIGKILL', returncode=child.returncode,
                    marker=json.loads(marker_line), reply_received=False, stderr=stderr)
            finally:
                if child.poll() is None:
                    child.kill()
                    stdout, stderr = child.communicate(timeout=10)
                self.record('logical-writer-' + str(uuid4()), dict(pid=child.pid,
                    returncode=child.returncode, marker=marker_line, stdout=stdout, stderr=stderr))

    def observation(self, command, other_uuid):
        from aiida import orm
        from aiida.repository.common import File
        other = orm.Group.get_collection(self.backend).get(uuid=other_uuid)
        rows = orm.QueryBuilder(backend=self.backend).append(orm.Group,
            filters={'uuid': other_uuid}, tag='other').append(orm.SinglefileData,
            with_group='other', project=['uuid', 'attributes', 'repository_metadata']).all()
        sources = []
        for uid, attributes, metadata in rows:
            # Supported ORM batch projection and native repository API; every
            # original byte is read and hashed on every fresh-process inspection.
            objects = File.from_serialized(metadata).objects
            assert set(objects) == {attributes['filename']}
            raw = self.backend.get_repository().get_object_content(objects[attributes['filename']].key)
            original = attributes['hyprn_mvp_documents']
            assert hashlib.sha256(raw).hexdigest() == original['sha256']
            assert len(raw) == original['size']
            assert all(original[k] == v for k, v in self._scope_fields().items())
            sources.append(dict(uuid=uid, attributes=attributes,
                size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        return dict(identity=self.identity(), state=self.snapshot(command['group_uuid']),
            receipts=self.receipts(command), sources=sorted(sources, key=lambda x: x['uuid']),
            other=dict(uuid=other.uuid, label=other.label, description=other.description,
                       extras=other.base.extras.all, members=sorted(n['uuid'] for n in sources)))

    def corrupt(self, case, command, fault):
        """Explicit native corruption fixtures, never repair or production paths."""
        from aiida import orm
        if fault in ('foreign-study', 'foreign-store', 'reserved-id'):
            field = {'foreign-study': 'study_id', 'foreign-store': 'store_uuid',
                     'reserved-id': 'collection_id'}[fault]
            return {**command, field: str(uuid4())}
        group = orm.Group.get_collection(self.backend).get(uuid=case['group_uuid'])
        if fault == 'missing-group':
            orm.Group.get_collection(self.backend).delete(group.pk)
            return command
        if fault in ('unknown-lifecycle', 'missing-lifecycle', 'bad-revision'):
            data = group.base.extras.get('hyprn_mvp_documents')
            if fault == 'unknown-lifecycle': data['lifecycle'] = 'other'
            elif fault == 'missing-lifecycle': del data['lifecycle']
            else: data['revision'] = True
            group.base.extras.set('hyprn_mvp_documents', data)
            return command
        receipt = self.mutate(command)
        data = group.base.extras.get('hyprn_mvp_documents')
        if fault == 'missing-witness':
            data['deletion']['command_id'] = str(uuid4())
            group.base.extras.set('hyprn_mvp_documents', data)
        elif fault == 'bad-marker':
            data['deletion']['payload_digest'] = '0' * 64
            group.base.extras.set('hyprn_mvp_documents', data)
        elif fault == 'nonempty-tombstone':
            other = orm.Group.get_collection(self.backend).get(uuid=self.observations[group.uuid])
            group.add_nodes(list(other.nodes))
        else:
            # Immutable corrupt witness is deliberately created, never edited in place.
            payload = {k: v for k, v in receipt.items() if k != 'witness_uuid'}
            if fault == 'conflicting-witness': payload['payload_digest'] = 'f' * 64
            if fault == 'wrong-witness-store':
                payload['command_id'] = str(uuid4())
                payload['store_uuid'] = str(uuid4())
                data['deletion']['command_id'] = payload['command_id']
                group.base.extras.set('hyprn_mvp_documents', data)
            orm.Dict(dict=payload, backend=self.backend).store()
        return command

    def hazard_control(self, operation):
        from aiida import orm
        case = self.collection()
        command = self.command(case)
        before = self.inspect_fresh(command)
        error_name = None
        try:
            with self.backend.transaction():
                group = orm.Group.get_collection(self.backend).get(uuid=case['group_uuid'])
                if operation == 'clear': group.clear()
                else: orm.Group.get_collection(self.backend).delete(group.pk)
                raise RuntimeError('deliberate hazard rollback')
        except Exception as error:
            error_name = type(error).__name__
        return dict(operation=operation, exception=error_name, before=before,
                    after=self.inspect_fresh(command))


def collection_protocol_child():
    if (len(sys.argv) != 4 or sys.argv[1] != '--collection-protocol-child' or
            sys.argv[2] not in ('inspect', 'replay', 'removed', 'metadata', 'witness', 'committed')):
        raise ValueError('Fixed collection protocol child mode required')
    historical = reopen_probe()  # Exact existing pre-import parent/scope/store guards.
    probe = CollectionProtocolProbe(historical.scope, historical.backend)
    request = json.loads(guard.scoped_path(probe.scope, sys.argv[3]).read_text())
    command = request['command']
    if sys.argv[2] == 'inspect':
        print(json.dumps(probe.observation(command, request['other_uuid'])), flush=True)
    elif sys.argv[2] == 'replay':
        print(json.dumps(probe.mutate(command)), flush=True)
    else:
        probe.mutate(command, wait_at=sys.argv[2])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--collection-protocol-child':
        collection_protocol_child()
    else:
        atomicity_child()
