"""Bounded bulk reads preserve exact retained bytes and avoid repeated traversal."""

import io
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_results import retained_record


class Repository:
    def __init__(self, files):
        self.files = files
        self.opens = []

    def open(self, path, mode):
        assert mode == 'rb'
        self.opens.append(path)
        return io.BytesIO(self.files[path])

    def get_object(self, path):
        # Two paths may refer to the same content-addressed object.
        from hashlib import sha256

        key = sha256(self.files[path]).hexdigest()
        return SimpleNamespace(key=key, is_file=lambda: True)


class Backend:
    def __init__(self, repository, mode=None):
        self.objects = {
            repository.get_object(path).key: raw for path, raw in repository.files.items()
        }
        self.mode = mode
        self.calls = []
        self.closed = False

    def iter_object_streams(self, keys):
        keys = list(keys)
        self.calls.append(keys)
        try:
            ordered = list(reversed(keys))
            if self.mode == 'missing':
                ordered.pop()
            if self.mode == 'duplicate':
                ordered.append(ordered[0])
            if self.mode == 'unexpected':
                ordered.insert(0, 'unexpected')
            for key in ordered:
                raw = self.objects.get(key, b'unknown')
                if self.mode == 'corrupt':
                    raw = b'x' * len(raw)
                if self.mode == 'oversize':
                    raw += b'x'
                with io.BytesIO(raw) as stream:
                    yield key, stream
        finally:
            self.closed = True


def test_record_read_checks_bundle_once_and_rechecks_each_request(monkeypatch):
    from hyprn_mvp_app.contracts import canonical
    from hyprn_mvp_integration import calculation

    bundle = retained_record('1')
    request = dict(
        run_id=bundle['manifest']['run_id'],
        bundle_digest=bundle['manifest']['bundle_digest'],
        scope=str(uuid4()),
        command_id=str(uuid4()),
        payload_digest='a' * 64,
    )
    repository = Repository({**bundle['files'], 'manifest.json': canonical(bundle['manifest'])})
    outputs = type('Outputs', (), {'__contains__': lambda self, key: key == 'results'})()
    outputs.results = SimpleNamespace(get_dict=lambda: {'retained': True})
    node = SimpleNamespace(
        uuid=str(uuid4()),
        process_type='aiida.calculations:hyprn_mvp.scalar',
        process_state=SimpleNamespace(value='finished'),
        exit_status=0,
        inputs=SimpleNamespace(
            request=SimpleNamespace(get_dict=lambda: request),
            frozen_bundle=SimpleNamespace(
                base=SimpleNamespace(repository=repository), is_stored=False
            ),
        ),
        outputs=outputs,
    )
    monkeypatch.setattr(calculation.orm, 'CalcJobNode', SimpleNamespace)
    monkeypatch.setattr(calculation.orm, 'load_node', lambda _: node)
    monkeypatch.setattr(calculation, 'read_stored_result', lambda value, *a, **kw: value)
    native = object.__new__(calculation.NativeExecution)
    native.store_uuid = str(uuid4())
    association = dict(store_uuid=native.store_uuid, process_uuid=node.uuid)
    record = native.read_record(request, association)
    assert record['bundle'] == bundle
    assert record['results'] == {'retained': True}
    assert repository.opens.count('manifest.json') == 1
    assert len(repository.opens) == len(bundle['files']) + 1
    repository.files['model.json'] += b'corrupt'
    repeated = native.read_record(request, association)
    assert repeated['bundle'] is None and repeated['results'] is None
    assert {'code': 'corrupt_retained_record', 'partial': True} in repeated['errors']


@pytest.mark.parametrize(
    'mode', [None, 'missing', 'duplicate', 'unexpected', 'corrupt', 'oversize']
)
def test_bulk_retained_reader_verifies_every_stream_and_closes_on_failure(mode):
    from hyprn_mvp_app.contracts import canonical
    from hyprn_mvp_integration.repository import read_bundle

    bundle = retained_record('1')
    request = {key: bundle['manifest'][key] for key in ('run_id', 'bundle_digest')}
    repository = Repository({**bundle['files'], 'manifest.json': canonical(bundle['manifest'])})
    backend = Backend(repository, mode)

    if mode:
        with pytest.raises((ValueError, OSError)):
            read_bundle(repository, backend, request)
    else:
        assert read_bundle(repository, backend, request) == bundle
    assert len(backend.calls) == 1
    assert len(backend.calls[0]) == len(set(backend.calls[0]))
    assert backend.closed
    assert repository.opens == ['manifest.json']


def test_bulk_read_shared_object_preserves_each_logical_size_bound():
    from hyprn_mvp_integration.repository import read_files

    repository = Repository({'one': b'abc', 'two': b'abc'})
    backend = Backend(repository)
    assert read_files(repository, backend, {'one': 3, 'two': 3}) == repository.files
    assert len(backend.calls[0]) == 1
    with pytest.raises(ValueError, match='size'):
        read_files(repository, Backend(repository), {'one': 3, 'two': 2})


@pytest.mark.parametrize('fault', ['request', 'version', 'path', 'size', 'total', 'duplicate'])
def test_manifest_refusal_precedes_bulk_object_reads(fault):
    from hyprn_mvp_app.contracts import canonical, digest
    from hyprn_mvp_integration.repository import read_bundle
    from hyprn_mvp_integration.results import UnsupportedRecordVersion

    bundle = retained_record('1')
    manifest = bundle['manifest']
    if fault == 'version':
        manifest['schema_version'] = 'unknown'
    if fault == 'path':
        manifest['files'][-1]['path'] = '../escape'
    if fault == 'size':
        manifest['files'][-1]['size'] = True
    if fault == 'total':
        manifest['files'][-1]['size'] = 32 * 1024 * 1024
    if fault == 'duplicate':
        manifest['files'].append(manifest['files'][0])
    manifest['bundle_digest'] = digest(
        {key: value for key, value in manifest.items() if key != 'bundle_digest'}
    )
    request = {key: manifest[key] for key in ('run_id', 'bundle_digest')}
    if fault == 'request':
        request['bundle_digest'] = 'f' * 64
    repository = Repository({**bundle['files'], 'manifest.json': canonical(manifest)})
    backend = Backend(repository)
    with pytest.raises(ValueError) as error:
        read_bundle(repository, backend, request)
    if fault == 'version':
        assert isinstance(error.value, UnsupportedRecordVersion)
    assert not backend.calls


@pytest.mark.parametrize('packed', [False, True])
def test_real_repository_bulk_read_reduces_queries_for_identical_bytes(tmp_path, capsys, packed):
    import json
    from time import perf_counter

    from aiida.repository import Repository as NativeRepository
    from aiida.repository.backend import DiskObjectStoreRepositoryBackend
    from disk_objectstore import Container
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    from hyprn_mvp_integration.repository import read_files

    container = Container(tmp_path / 'repository')
    backend = DiskObjectStoreRepositoryBackend(container)
    backend.initialise()
    repository = NativeRepository(backend)
    expected = {
        f'files/{index}.txt': (str(index) + ' retained bytes').encode() for index in range(480)
    }
    for path, raw in expected.items():
        repository.put_object_from_filelike(io.BytesIO(raw), path)
    if packed:
        container.pack_all_loose()
        container.clean_storage()
    bounds = {path: len(raw) for path, raw in expected.items()}
    statements = []

    def count(*args):
        statements.append(1)

    event.listen(Engine, 'before_cursor_execute', count)
    try:
        start = perf_counter()
        previous = {}
        for path, size in bounds.items():
            with repository.open(path) as stream:
                previous[path] = stream.read(size + 1)
        before_seconds = perf_counter() - start
        before_queries = len(statements)
        statements.clear()
        start = perf_counter()
        current = read_files(repository, backend, bounds)
        after_seconds = perf_counter() - start
        after_queries = len(statements)
    finally:
        event.remove(Engine, 'before_cursor_execute', count)
        container.close()
    assert previous == current == expected
    assert before_queries >= 2 * len(bounds)
    assert 0 < after_queries <= 2
    with capsys.disabled():
        print(json.dumps(dict(
            repository_benchmark='packed' if packed else 'loose', files=len(bounds),
            before_queries=before_queries, after_queries=after_queries,
            before_seconds=before_seconds, after_seconds=after_seconds,
        )))
