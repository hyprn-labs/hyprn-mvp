"""Finite native original storage; metadata validates identity, never access.

The trusted bridge supplies one fixed backend/study/store and an already
authorized command, under its serialized single native writer. This module
neither selects profiles nor grants authorization. An absent witness alone is
not permission to retry an uncertain writer. Original bytes are inert data.
"""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import re
from uuid import UUID

MAX_ORIGINAL = 10 * 1024 * 1024
CHUNK = 256 * 1024
NAMESPACE = 'hyprn_mvp_documents'
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
HASH_PATTERN = re.compile(r'^[0-9a-f]{64}$')
MEDIA = {'application/pdf', 'text/plain', 'text/markdown', 'text/csv'}


def payload_digest(payload):
    """Digest the complete normalized DocumentNativeStoreOriginal1 payload."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('Invalid document metadata fields')


def _uuid(value):
    if not isinstance(value, str) or not UUID_PATTERN.fullmatch(value):
        raise ValueError('Invalid document identity')


def _hash(value):
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise ValueError('Invalid document digest')


def _integer(value, maximum, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid document bound')


def _read_exact(source, size, sha256):
    """Never issue an unbounded read; authenticate all bytes before delivery."""
    data = bytearray()
    while len(data) <= size:
        chunk = source.read(min(CHUNK, size + 1 - len(data)))
        if type(chunk) is not bytes:
            raise ValueError('Binary original stream required')
        if not chunk:
            break
        if len(chunk) > min(CHUNK, size + 1 - len(data)):
            raise ValueError('Original stream exceeded read bound')
        data.extend(chunk)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError('Original bytes mismatch')
    return bytes(data)


class NativeDocuments:
    def __init__(self, backend, *, study_id, native_store_id):
        _uuid(study_id)
        _uuid(native_store_id)
        self.backend = backend
        self.study_id = study_id
        self.native_store_id = native_store_id
        self._store()

    def _store(self):
        if str(UUID(self.backend.get_repository().uuid)) != self.native_store_id:
            raise ValueError('Native document store mismatch')

    def _identity(self, identity):
        self._store()
        _exact(identity, ('study_id', 'actor_id', 'command_id', 'operation_id', 'payload_sha256'))
        for key in ('study_id', 'actor_id', 'command_id', 'operation_id'):
            _uuid(identity[key])
        _hash(identity['payload_sha256'])
        if identity['study_id'] != self.study_id:
            raise ValueError('Document scope mismatch')

    def _command(self, identity, payload):
        self._identity(identity)
        _exact(payload, ('request', 'reserved_ids', 'transfer_id'))
        _uuid(payload['transfer_id'])
        reserved = payload['reserved_ids']
        _exact(reserved, ('document_id', 'version_id'))
        for value in reserved.values(): _uuid(value)
        request = payload['request']
        keys = {'command_id', 'filename', 'media_type', 'byte_length', 'sha256'}
        if type(request) is dict and ('family_id' in request or 'expected_revision' in request):
            keys |= {'family_id', 'expected_revision'}
        _exact(request, keys)
        if 'family_id' in request:
            _uuid(request['family_id'])
            _integer(request['expected_revision'], 2**63 - 1, 1)
            if request['family_id'] != reserved['document_id']:
                raise ValueError('Original family mismatch')
        _uuid(request['command_id'])
        _integer(request['byte_length'], MAX_ORIGINAL)
        _hash(request['sha256'])
        if (not isinstance(request['filename'], str) or not 1 <= len(request['filename']) <= 200
                or not isinstance(request['media_type'], str) or request['media_type'] not in MEDIA):
            raise ValueError('Invalid original metadata')
        if (request['command_id'] != identity['command_id']
                or payload_digest(payload) != identity['payload_sha256']):
            raise ValueError('Original command digest mismatch')

    def _association(self, association):
        self._store()
        _exact(association, ('schema_version', 'study_id', 'resource_id', 'resource_kind',
                             'native_store_id', 'native_entity_id'))
        for key in ('study_id', 'resource_id', 'native_store_id', 'native_entity_id'):
            _uuid(association[key])
        if (association['schema_version'] != '1' or association['resource_kind'] != 'original'
                or association['study_id'] != self.study_id
                or association['native_store_id'] != self.native_store_id):
            raise ValueError('Original association mismatch')

    def _nodes(self, cls, filters):
        from aiida import orm
        return orm.QueryBuilder(backend=self.backend).append(cls, filters=filters).limit(2).all(flat=True)

    def _original(self, association):
        from aiida import orm
        self._association(association)
        nodes = self._nodes(orm.SinglefileData, {'uuid': association['native_entity_id']})
        if len(nodes) != 1:
            raise ValueError('Original unavailable')
        node = nodes[0]
        metadata = node.base.attributes.get(NAMESPACE, None)
        _exact(metadata, ('identity', 'payload', 'version', 'association'))
        self._command(metadata['identity'], metadata['payload'])
        version = metadata['version']
        _exact(version, ('schema_version', 'version_id', 'document_id', 'study_id', 'revision',
            'original_sha256', 'original_size', 'media_type', 'filename', 'created_by', 'created_at', 'availability'))
        timestamp = version['created_at']
        try:
            if not isinstance(timestamp, str) or not timestamp.endswith('Z'):
                raise ValueError()
            datetime.fromisoformat(timestamp)
        except (ValueError, TypeError):
            raise ValueError('Invalid original timestamp') from None
        expected = self._version(metadata['identity'], metadata['payload'], timestamp)
        if (version != expected or type(version['revision']) is not int
                or type(version['original_size']) is not int
                or metadata['association'] != association
                or association['resource_id'] != version['version_id']
                or node.filename != 'original.bin'
                or node.base.repository.list_object_names() != ['original.bin']):
            raise ValueError('Original metadata mismatch')
        with node.open(mode='rb') as handle:
            raw = _read_exact(handle, version['original_size'], version['original_sha256'])
        return metadata, raw

    def _version(self, identity, payload, created_at):
        request, reserved = payload['request'], payload['reserved_ids']
        return dict(schema_version='1', **reserved, study_id=self.study_id, revision=1,
            original_sha256=request['sha256'], original_size=request['byte_length'],
            media_type=request['media_type'], filename=request['filename'],
            created_by=identity['actor_id'], created_at=created_at, availability='available')

    def _witness(self, metadata):
        return dict(schema_version='documents-witness/1', identity=metadata['identity'],
            native_store_id=self.native_store_id, reserved_ids=metadata['payload']['reserved_ids'],
            associations=[metadata['association']], category='upload', result=metadata['version'],
            previous_revision=None, resulting_revision=1)

    def reconcile(self, identity):
        """Exact immutable outcome or absence; absence is not a fencing proof."""
        from aiida import orm
        self._identity(identity)
        # Do not filter digest/category/store: corrupted or conflicting witnesses
        # in this scoped command namespace must fail, not become an absent result.
        nodes = self._nodes(orm.Dict, {'attributes.identity.study_id': self.study_id,
            'attributes.identity.command_id': identity['command_id']})
        if not nodes:
            return None
        if len(nodes) != 1:
            raise ValueError('Multiple original witnesses: uncertain')
        witness = nodes[0].get_dict()
        _exact(witness, ('schema_version', 'identity', 'native_store_id', 'reserved_ids',
            'associations', 'category', 'result', 'previous_revision', 'resulting_revision'))
        if (witness['identity'] != identity or type(witness['associations']) is not list
                or len(witness['associations']) != 1):
            raise ValueError('Original command conflict')
        metadata, _ = self._original(witness['associations'][0])
        if witness != self._witness(metadata) or type(witness['resulting_revision']) is not int:
            raise ValueError('Original witness mismatch')
        return witness

    def store_original(self, identity, payload, source):
        """Caller must hold the single-writer boundary before this call.

        source is an already resolved scoped binary transfer, never a path.
        Transfer resolution and current authorization belong to the bridge.
        """
        from aiida import orm
        # Snapshot caller-owned dictionaries before I/O/native mutation.
        identity, payload = json.loads(json.dumps([identity, payload], allow_nan=False))
        self._command(identity, payload)
        with self.backend.transaction():
            prior = self.reconcile(identity)
            if prior is not None:
                return prior
            reserved = payload['reserved_ids']
            if self._nodes(orm.SinglefileData,
                    {'attributes.' + NAMESPACE + '.version.version_id': reserved['version_id']}):
                raise ValueError('Original version already reserved')
            raw = _read_exact(source, payload['request']['byte_length'], payload['request']['sha256'])
            node = orm.SinglefileData(file=io.BytesIO(raw), filename='original.bin', backend=self.backend)
            association = dict(schema_version='1', study_id=self.study_id,
                resource_id=reserved['version_id'], resource_kind='original',
                native_store_id=self.native_store_id, native_entity_id=node.uuid)
            metadata = dict(identity=identity, payload=payload, association=association,
                version=self._version(identity, payload, datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')))
            node.base.attributes.set(NAMESPACE, metadata)
            node.store()
            self._original(association)  # Exact native readback precedes witness/commit.
            witness = self._witness(metadata)
            orm.Dict(dict=witness, backend=self.backend).store()
        return witness

    def _verified(self, association):
        metadata, raw = self._original(association)
        witness = self.reconcile(metadata['identity'])
        if witness is None or witness['associations'] != [association]:
            raise ValueError('Original witness absent or mismatched')
        return metadata['version'], raw

    def descriptor(self, association):
        return self._verified(association)[0]

    def stream(self, association):
        """Authenticate full bounded original before yielding any bytes."""
        _, raw = self._verified(association)
        for offset in range(0, len(raw), CHUNK):
            yield raw[offset:offset + CHUNK]

    def read(self, association, *, offset, byte_length):
        _integer(offset, MAX_ORIGINAL)
        _integer(byte_length, CHUNK)
        version, raw = self._verified(association)
        if offset + byte_length > len(raw):
            raise ValueError('Original range outside source')
        part = raw[offset:offset + byte_length]
        descriptor = {key: version[key] for key in ('version_id', 'original_sha256',
                      'original_size', 'media_type', 'filename')}
        descriptor.update(offset=offset, byte_length=len(part), payload_sha256=hashlib.sha256(part).hexdigest(),
            disposition='attachment', cache_control='no-store', content_type_options='nosniff')
        return dict(descriptor=descriptor, encoding='base64', bytes=base64.b64encode(part).decode('ascii'))
