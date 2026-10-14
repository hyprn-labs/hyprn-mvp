"""Bounded data-only AiiDA 2.9.3 archive policy. No process/plugin loading."""

import base64
import hashlib
import io
import re
import stat
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from uuid import UUID

from aiida import orm
from aiida.common.links import LinkType
from aiida.tools.graph.graph_traversers import get_nodes_export
from aiida.tools.archive import create_archive
from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
from hyprn_mvp_app.contracts import canonical, data_json, digest
from hyprn_mvp_app.execution_bundle import closed
from .results import retained_bundle, read_stored_result, validate_criteria, validate_result
from . import launcher

RAW = 16777216
EXPANDED = 33554432
PATHS = 4096
METADATA = 1048576
INVENTORY = 4194304
# Nested source inspection is bounded separately from native ZIP payload bytes.
# Neither limit changes the public package's physical/logical accounting.
NESTED_EXPANDED = 33554432
NESTED_PATHS = 4096
NODE_TYPES = {
    'process.calculation.calcjob.CalcJobNode.',
    'data.core.dict.Dict.',
    'data.core.folder.FolderData.',
    'data.core.remote.RemoteData.',
    'data.core.code.installed.InstalledCode.',
}
RULES = dict(
    input_calc_forward=False,
    create_backward=True,
    return_backward=False,
    input_work_forward=False,
    call_calc_backward=False,
    call_work_backward=False,
)
FULL_RULES = RULES | dict(
    input_calc_backward=True,
    create_forward=True,
    return_forward=True,
    input_work_backward=True,
    call_calc_forward=True,
    call_work_forward=True,
)
OMISSIONS = ['authinfos', 'comments', 'logs', 'process_checkpoints']
# Immutable source offer of the pinned 597f5abf producer: the upstream archive, its unmodified
# user model and the configuration patch carry credential API identifiers or upstream example
# literals, not deployment credentials. Only these exact provenance paths and bytes are
# admitted; no candidate role inherits the allowance, including a copied file with the same
# content hash. Support sources (provenance/support/...) have no allowance: their current bytes
# pass sensitive() as they are.
AUDITED_PROVENANCE = {
    ('provenance/upstream.tar.gz'): (
        '4937188df6ea12daa8a2b00767005e3649d2974ab6e634409f7756043ef0b360'
    ),
    ('provenance/upstream/app/models/user.rb'): (
        'f9b2f06d3cd1331cfe447a91143e3c03a69cfd6853ba642821d4cd5d11a051d1'
    ),
    ('provenance/patched/app/models/user.rb'): (
        'f9b2f06d3cd1331cfe447a91143e3c03a69cfd6853ba642821d4cd5d11a051d1'
    ),
    ('provenance/patches/030-configuration.patch'): (
        '05b318ea908336e2c7ce371f4250fdc1264c73c1bf0d719e381e80f43465adff'
    ),
}


def audited_provenance(prepared_paths, path, raw):
    return (
        path in prepared_paths and AUDITED_PROVENANCE.get(path) == hashlib.sha256(raw).hexdigest()
    )


# Reviewed dependency documentation examples, not credentials: aio-pika's
# commented connect_robust(password="password") and shortuuid's model field
# api_key = ShortUUIDField(). Only exact runtime license descriptors qualify.
AUDITED_LICENSES = {
    ('licenses/native/aio_pika-9.5.8.dist-info/METADATA'): (
        'f15ca6ca8696f6520f98e1667cf788da9b2e8b722caec89e73328ddaaad6b71f'
    ),
    ('licenses/native/shortuuid-1.0.13.dist-info/METADATA'): (
        '76f39eb41b4bb36f8e36682178ff470d36153c9a49e6d451db0ae9e4a81f5819'
    ),
    ('licenses/native/charset_normalizer-3.5.2.dist-info/METADATA'): (
        '89ce6362bb7be88558f4be99a98f5d1b4da93d19cd0323e5ee0bac05cf883dfb'
    ),
    ('licenses/worker/charset_normalizer-3.5.2.dist-info/METADATA'): (
        '89ce6362bb7be88558f4be99a98f5d1b4da93d19cd0323e5ee0bac05cf883dfb'
    ),
    ('licenses/native/jedi-0.18.2.dist-info/METADATA'): (
        'f21e26976fba61c1ed460d48988b44b61103fcd8058a3ace8e0061417b7effa3'
    ),
    ('licenses/native/psutil-7.2.2.dist-info/METADATA'): (
        '525f8ba78523cf7bc3759d62a105e7c57fd679ea702402b9449fb0746aa0217f'
    ),
    ('licenses/worker/tomli-2.5.0.dist-info/METADATA'): (
        '0d7d3b46cb99dac60216978cebca446f9ec3a21fd3e1f9650086a2e373654e27'
    ),
}


def audited_license(manifest, path, raw):
    sha = hashlib.sha256(raw).hexdigest()
    return (
        AUDITED_LICENSES.get(path) == sha
        and dict(kind='runtime', path=path) in manifest['licenses']
        and any(
            f['path'] == path
            and f['role'] == 'licenses'
            and f['sha256'] == sha
            and f['size'] == len(raw)
            for f in manifest['files']
        )
    )


NODE_FIELDS = {
    'id',
    'uuid',
    'node_type',
    'process_type',
    'label',
    'description',
    'ctime',
    'mtime',
    'attributes',
    'extras',
    'repository_metadata',
    'dbcomputer_id',
    'user_id',
}
PROCESS_DEFAULTS = dict(
    process_state='finished',
    sealed=True,
    process_label='ScalarCalculation',
    metadata_inputs={'metadata': {'disable_cache': True, 'options': {'max_wallclock_seconds': 60}}},
    version={'core': '2.9.3'},
    resources={'num_machines': 1, 'num_mpiprocs_per_machine': 1},
    max_wallclock_seconds=60,
    parser_name='hyprn_mvp.scalar',
    scheduler_stdout='_scheduler-stdout.txt',
    scheduler_stderr='_scheduler-stderr.txt',
    submit_script_filename='_aiidasubmit.sh',
    environment_variables={},
    import_sys_environment=True,
    prepend_text='',
    append_text='',
    custom_scheduler_commands='',
    mpirun_extra_params=[],
    environment_variables_double_quotes=False,
    detailed_job_info=None,
    retrieve_temporary_list=[],
    scheduler_state='done',
)
PROCESS_ATTRIBUTES = set(PROCESS_DEFAULTS) | {
    'exit_status',
    'exit_message',
    'last_job_info',
    'job_id',
    'remote_workdir',
    'retrieve_list',
    'scheduler_lastchecktime',
}
SECRET = re.compile(
    (
        '(?i)(?:-----BEGIN (?:[A-Z ]*PRIVATE KEY)|(?:(?:api|acce'
        'ss|auth|session)[_-]?(?:key|token)|password|secret|auth'
        'orization)\\s*[=:]\\s*[\\x22\\x27]?[A-Za-z0-9+/_.-]{8,}|AKI'
        'A[A-Z0-9]{16})'
    )
)


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Closed archive object required')


def uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('Canonical archive UUID required')
    return value


def safe_path(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 4096
        or '\\' in value
        or value.startswith('/')
        or len(value.split('/')) > 32
        or any(p in ('', '.', '..') for p in value.split('/'))
    ):
        raise ValueError('Unsafe path in archive')
    return unicodedata.normalize('NFC', value).casefold()


def sensitive(raw, *, allowed_paths=()):
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('Unknown repository content') from None
    if '\x00' in text or SECRET.search(text):
        raise ValueError('Sensitive archive content')
    for path in allowed_paths:
        text = text.replace(str(path) + '/', '[approved-root]/')
    if re.search(r'(?i)/(?:Users|home|private/tmp)/', text):
        raise ValueError('Private host path in archive content')


def archive_bounds(path):
    """Validate the actual native ZIP before its reader can decompress SQLite."""
    if path.stat().st_size > RAW:
        raise ValueError('Native archive byte bound')
    seen = set()
    total = 0
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > PATHS:
                raise ValueError('Native archive entry bound')
            for item in entries:
                name = item.filename.rstrip('/') if item.is_dir() else item.filename
                key = safe_path(name)
                mode = item.external_attr >> 16
                if (
                    key in seen
                    or item.flag_bits & 1
                    or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                ):
                    raise ValueError('Unsafe native archive entry')
                seen.add(key)
                if item.file_size > RAW:
                    raise ValueError('Native file byte bound')
                total += item.file_size
                if total > EXPANDED:
                    raise ValueError('Native expansion bound')
                if not (
                    name in ('metadata.json', 'db.sqlite3', 'repo')
                    or re.fullmatch(r'repo/[a-f0-9]{64}', name)
                ):
                    raise ValueError('Unlisted native archive entry')
                if not item.is_dir():
                    with archive.open(item) as stream:
                        size = 0
                        sha = hashlib.sha256()
                        while chunk := stream.read(65536):
                            size += len(chunk)
                            if size > item.file_size:
                                raise ValueError('Native expansion mismatch')
                            sha.update(chunk)
                    if size != item.file_size:
                        raise ValueError('Truncated native archive')
                    if name.startswith('repo/') and sha.hexdigest() != name[5:]:
                        raise ValueError('Native repository hash mismatch')
            if not {'metadata.json', 'db.sqlite3'} <= seen:
                raise ValueError('Incomplete native archive')
    except (zipfile.BadZipFile, RuntimeError, EOFError) as error:
        raise ValueError('Malformed native archive') from error
    return total, len(entries)


class Export:
    def __init__(self, native, payload):
        self.native = native
        self.backend = native.backend
        self.root = launcher.runtime_root(native.root)
        if self.backend is None:
            raise ValueError('Explicit native backend required')
        if UUID(self.backend.get_repository().uuid) != UUID(native.store_uuid):
            raise ValueError('Native backend identity mismatch')
        exact(
            payload,
            {
                'schema_version',
                'study_id',
                'origin_store_uuid',
                'roots',
                'computations',
                'policy_version',
            },
        )
        if payload['schema_version'] != '1' or payload['policy_version'] != 'record-policy-1':
            raise ValueError('Unsupported archive policy')
        uuid(payload['study_id'])
        uuid(payload['origin_store_uuid'])
        if UUID(payload['origin_store_uuid']) != UUID(native.store_uuid):
            raise ValueError('Origin store mismatch')
        self.payload = payload
        self.approved = {}
        self.roots = []
        roots = payload['roots']
        items = payload['computations']
        if not isinstance(roots, list) or not 1 <= len(roots) <= 16 or roots != sorted(set(roots)):
            raise ValueError('Selected run bound/order')
        if not isinstance(items, list) or not 1 <= len(items) <= 64:
            raise ValueError('Computational run bound')
        for item in items:
            exact(item, {'run_id', 'request', 'association', 'results_digest', 'role'})
            uuid(item['run_id'])
            exact(
                item['request'],
                {'run_id', 'scope', 'command_id', 'payload_digest', 'bundle_digest'},
            )
            exact(item['association'], {'store_uuid', 'process_uuid'})
            for key in ('run_id', 'scope', 'command_id'):
                uuid(item['request'][key])
            for key in ('payload_digest', 'bundle_digest'):
                if not re.fullmatch('[a-f0-9]{64}', item['request'][key]):
                    raise ValueError('Invalid request digest')
            if (
                item['request']['run_id'] != item['run_id']
                or item['request']['scope'] != payload['study_id']
            ):
                raise ValueError('Foreign archive request')
            if UUID(item['association']['store_uuid']) != UUID(native.store_uuid):
                raise ValueError('Foreign archive store')
            process = uuid(item['association']['process_uuid'])
            store = item['association']['store_uuid']
            if store not in (str(UUID(store)), UUID(store).hex):
                raise ValueError('Noncanonical native store identity')
            if process in self.approved:
                raise ValueError('Duplicate process association')
            if item['role'] != (
                'selected' if item['run_id'] in roots else 'computational_ancestor'
            ):
                raise ValueError('Archive role mismatch')
            self.approved[process] = item
        runs = [i['run_id'] for i in items]
        if runs != sorted(set(runs)) or not set(roots) <= set(runs):
            raise ValueError('Archive run inventory mismatch')

    def node(self, identity):
        types = (
            orm.QueryBuilder(backend=self.backend)
            .append(orm.Node, filters={'uuid': identity}, project=['node_type', 'process_type'])
            .all()
        )
        if types != [
            ['process.calculation.calcjob.CalcJobNode.', 'aiida.calculations:hyprn_mvp.scalar']
        ]:
            raise ValueError('Approved native process unavailable or unsupported')
        rows = (
            orm.QueryBuilder(backend=self.backend)
            .append(orm.Node, filters={'uuid': identity}, project='*')
            .all()
        )
        if len(rows) != 1:
            raise ValueError('Approved native process unavailable')
        return rows[0][0]

    def repositories(self, node):
        result = {}
        seen = set()
        for parent, _, names in node.base.repository.walk():
            for name in names:
                path = str(parent / name)
                key = safe_path(path)
                if key in seen or len(result) >= PATHS:
                    raise ValueError('Repository path bound/collision')
                seen.add(key)
                with node.base.repository.open(path, mode='rb') as stream:
                    raw = stream.read(RAW + 1)
                if len(raw) > RAW:
                    raise ValueError('Repository file byte bound')
                sha = hashlib.sha256(raw).hexdigest()
                if node.base.repository.get_object(path).key != sha:
                    raise ValueError('Repository content hash mismatch')
                previous = self.objects.get(sha)
                if previous is not None and previous != len(raw):
                    raise ValueError('Repository content size mismatch')
                if previous is None:
                    self.objects[sha] = len(raw)
                    self.bytes += len(raw)
                # Every node/path occurrence remains authorized and inventoried,
                # even when the content-addressed native archive stores it once.
                self.paths += 1
                if self.bytes > EXPANDED or self.paths > PATHS:
                    raise ValueError('Repository aggregate bound')
                result[path] = raw
        return result

    def guard_closure(self):
        """Bound graph discovery before calling the pinned unrestricted traverser."""

        def creators(data):
            rows = (
                orm.QueryBuilder(backend=self.backend)
                .append(orm.Node, filters={'id': data.pk}, tag='data')
                .append(
                    orm.Node,
                    with_outgoing='data',
                    edge_filters={'type': 'create'},
                    project=['uuid', 'node_type', 'process_type'],
                    edge_project='label',
                )
                .limit(2)
                .all()
            )
            if len(rows) > 1 or any(
                kind != 'process.calculation.calcjob.CalcJobNode.'
                or process_type != 'aiida.calculations:hyprn_mvp.scalar'
                for _, kind, process_type, _ in rows
            ):
                raise ValueError('Unsupported native creator type before materialization')
            return [(identity, label) for identity, _, _, label in rows]

        for identity in self.approved:
            node = self.node(identity)
            if not isinstance(node, orm.CalcJobNode):
                raise ValueError('Approved CalcJob required')
            for direction, maximum in (('with_outgoing', 67), ('with_incoming', 4)):
                count = (
                    orm.QueryBuilder(backend=self.backend)
                    .append(orm.Node, filters={'id': node.pk}, tag='p')
                    .append(orm.Node, **{direction: 'p'})
                    .count()
                )
                if count > maximum:
                    raise ValueError('Native link bound')
                kinds = (
                    orm.QueryBuilder(backend=self.backend)
                    .append(orm.Node, filters={'id': node.pk}, tag='p')
                    .append(orm.Node, **{direction: 'p'}, project=['node_type', 'process_type'])
                    .all()
                )
                if any(
                    kind not in NODE_TYPES or process_type is not None
                    for kind, process_type in kinds
                ):
                    raise ValueError('Unsupported native node type before materialization')
            for edge in node.base.links.get_incoming().all():
                if edge.link_type != LinkType.INPUT_CALC:
                    raise ValueError('Unsupported process link')
                data = edge.node
                parents = creators(data)
                if edge.link_label.startswith('upstream_results__'):
                    if (
                        len(parents) != 1
                        or parents[0][0] not in self.approved
                        or parents[0][1] != 'results'
                    ):
                        raise ValueError('Missing approved computational creator')
                elif parents:
                    raise ValueError('Unexpected input creator')
            for edge in node.base.links.get_outgoing().all():
                if edge.link_type != LinkType.CREATE:
                    raise ValueError('Unsupported process link')
                if creators(edge.node) != [(node.uuid, edge.link_label)]:
                    raise ValueError('Unexpected output creator')

    def inspect(self, backend=None):
        self.backend = backend or self.native.backend
        self.bytes = self.paths = 0
        self.objects = {}
        self.nested_archives = {}
        self.nested_bytes = self.nested_paths = 0
        self.guard_closure()
        roots = [
            self.node(self.approved[p]['association']['process_uuid'])
            for p in self.approved
            if self.approved[p]['role'] == 'selected'
        ]
        graph = get_nodes_export(
            [n.pk for n in roots], get_links=True, backend=self.backend, **RULES
        )
        if (
            graph['rules'] != FULL_RULES
            or len(graph['nodes']) > PATHS
            or len(graph['links']) > PATHS
        ):
            raise ValueError('Native closure/rules bound')
        kinds = (
            orm.QueryBuilder(backend=self.backend)
            .append(
                orm.Node,
                filters={'id': {'in': list(graph['nodes'])}},
                project=['node_type', 'process_type'],
            )
            .all()
        )
        if any(
            kind not in NODE_TYPES
            or process_type
            != (('aiida.calculations:hyprn_mvp.scalar') if kind.startswith('process.') else None)
            for kind, process_type in kinds
        ):
            raise ValueError('Unsupported native closure type')
        nodes = {
            n.pk: n
            for [n] in orm.QueryBuilder(backend=self.backend)
            .append(orm.Node, filters={'id': {'in': list(graph['nodes'])}}, project='*')
            .all()
        }
        if {n.uuid for n in nodes.values() if isinstance(n, orm.ProcessNode)} != set(self.approved):
            raise ValueError('Computational closure differs from approval')
        roles = {}
        expected_links = set()
        expected_files = {}
        provenance = {}
        manifests = {}

        def link(source, target, label, kind):
            expected_links.add((source.uuid, target.uuid, label, kind.value))

        for node in nodes.values():
            if not isinstance(node, orm.ProcessNode):
                continue
            if (
                not isinstance(node, orm.CalcJobNode)
                or node.process_type != 'aiida.calculations:hyprn_mvp.scalar'
                or not node.is_sealed
                or node.process_state.value != 'finished'
            ):
                raise ValueError('Complete sealed CalcJob required')
            item = self.approved[node.uuid]
            roles[node.uuid] = 'process'
            incoming = {
                l.link_label: l.node
                for l in node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all()
            }
            outgoing = {
                l.link_label: l.node
                for l in node.base.links.get_outgoing(link_type=LinkType.CREATE).all()
            }
            if (
                not {'request', 'frozen_bundle'} <= set(incoming)
                or not {'results', 'retrieved'} <= set(outgoing)
                or not set(outgoing) <= {'results', 'retrieved', 'assessment', 'remote_folder'}
            ):
                raise ValueError('Incomplete scientific record')
            if (
                not isinstance(incoming['request'], orm.Dict)
                or incoming['request'].get_dict() != item['request']
            ):
                raise ValueError('Exact archive request mismatch')
            if not isinstance(incoming['frozen_bundle'], orm.FolderData):
                raise ValueError('Frozen input required')
            bundle = retained_bundle(incoming['frozen_bundle'].base.repository, item['request'])
            # The archive envelope stays at version1. Its retained reader checks
            # the complete nested version pairing, projection and citation closure
            # before either native inventory or offline archive inspection.
            if bundle['manifest']['schema_version'] not in ('3', '4', '5', '6', '8'):
                raise ValueError('Current retained bundle required')
            expected_files[incoming['frozen_bundle'].uuid] = {
                **bundle['files'],
                'manifest.json': canonical(bundle['manifest']),
            }
            manifests[incoming['frozen_bundle'].uuid] = bundle['manifest']
            prepared = data_json(bundle['files']['preparation.json'])
            provenance[incoming['frozen_bundle'].uuid] = {
                f['path'] for f in prepared['files'] if f['role'] == 'provenance'
            }
            deps = data_json(bundle['files']['result-dependencies.json'])
            pins = {s['label']: s for s in deps['sources']}
            expected_inputs = (
                {'request', 'frozen_bundle'}
                | ({'code'} if 'code' in incoming else set())
                | {'upstream_results__' + p for p in pins}
            )
            if set(incoming) != expected_inputs:
                raise ValueError('Unexplained process input')
            for label, data in incoming.items():
                role = 'upstream' if label.startswith('upstream_results__') else label
                if role == 'upstream':
                    pin = pins[label.removeprefix('upstream_results__')]
                    if (
                        pin['result_uuid'] != data.uuid
                        or pin['association']['process_uuid'] not in self.approved
                    ):
                        raise ValueError('Missing approved result creator')
                    source = self.approved[pin['association']['process_uuid']]
                    if (
                        any(
                            pin[k] != source[k]
                            for k in ('request', 'association', 'results_digest')
                        )
                        or pin['source_run_id'] != source['run_id']
                    ):
                        raise ValueError('Upstream approval mismatch')
                else:
                    roles[data.uuid] = role
                link(data, node, label, LinkType.INPUT_CALC)
            for label, data in outgoing.items():
                roles[data.uuid] = label
                link(node, data, label, LinkType.CREATE)
            result = outgoing['results']
            if (
                not isinstance(result, orm.Dict)
                or digest(result.get_dict()) != item['results_digest']
            ):
                raise ValueError('Exact results digest mismatch')
            creators = result.base.links.get_incoming(link_type=LinkType.CREATE).all()
            if (
                len(creators) != 1
                or creators[0].node.uuid != node.uuid
                or creators[0].link_label != 'results'
            ):
                raise ValueError('Results creator mismatch')
            assessment = outgoing['assessment'].get_dict() if 'assessment' in outgoing else None
            value = read_stored_result(
                result.get_dict(),
                item['request'],
                data_json(bundle['files']['model.json']),
                assessment,
            )
            validate_criteria(value, data_json(bundle['files']['configuration.json']))
            if (node.exit_status == 0) != (value['execution']['state'] == 'finished'):
                raise ValueError('Execution outcome mismatch')
            retrieved = self.repositories(outgoing['retrieved'])
            if not {'result.json', 'launcher.stderr'} <= set(retrieved) or set(retrieved) - {
                'result.json',
                'launcher.stderr',
                '_scheduler-stdout.txt',
                '_scheduler-stderr.txt',
            }:
                raise ValueError('Required retained diagnostics mismatch')
            # ScalarParser reads the retained launcher envelope, then stores its
            # validated scientific result through AiiDA's pinned serialization.
            # Compare that exact representation without rewriting either record.
            envelope = data_json(retrieved['result.json'])
            exact(envelope, {'id', 'reason', 'exit_code', 'seconds', 'state', 'output'})
            exact(
                envelope['state'],
                {
                    'Status',
                    'Running',
                    'Paused',
                    'Restarting',
                    'OOMKilled',
                    'Dead',
                    'Pid',
                    'ExitCode',
                    'Error',
                    'StartedAt',
                    'FinishedAt',
                },
            )
            parsed = validate_result(
                retrieved['result.json'], item['request'], data_json(bundle['files']['model.json'])
            )
            validate_criteria(parsed, data_json(bundle['files']['configuration.json']))
            from aiida.orm.implementation.utils import clean_value

            if clean_value(parsed) != result.get_dict():
                raise ValueError('Required retained diagnostics mismatch')
            if node.exit_status and not (
                value['execution']['message'].strip() or retrieved['launcher.stderr'].strip()
            ):
                raise ValueError('Missing scientific failure explanation')
            expected_files[outgoing['retrieved'].uuid] = retrieved
        actual = {
            (nodes[l.source_id].uuid, nodes[l.target_id].uuid, l.link_label, l.link_type)
            for l in graph['links']
        }
        if actual != expected_links or set(roles) != set(n.uuid for n in nodes.values()):
            raise ValueError('Unexplained native node/link')
        inventory = dict(
            nodes=[],
            links=[
                dict(source_uuid=a, target_uuid=b, label=c, type=d) for a, b, c, d in sorted(actual)
            ],
            computers=[],
            users=[],
            repositories=[],
            omissions=OMISSIONS,
        )
        self.bytes = self.paths = self.metadata_bytes = 0
        rows = []
        users = set()
        computers = set()
        self.objects = {}
        self.nested_archives = {}
        self.nested_bytes = self.nested_paths = 0
        for node in sorted(nodes.values(), key=lambda n: n.uuid):
            row = (
                orm.QueryBuilder(backend=self.backend)
                .append(orm.Node, filters={'id': node.pk}, project='**')
                .dict()[0]
            )
            row = next(iter(row.values()))
            exact(row, NODE_FIELDS)
            if (
                type(row['id']) is not int
                or type(row['user_id']) is not int
                or row['dbcomputer_id'] is not None
                and type(row['dbcomputer_id']) is not int
                or not isinstance(row['node_type'], str)
                or not isinstance(row['repository_metadata'], dict)
                or row['process_type'] not in (None, 'aiida.calculations:hyprn_mvp.scalar')
            ):
                raise ValueError('Unexpected native row field types')
            attributes = dict(row['attributes'])
            if backend is not None and orm.ProcessNode.CHECKPOINT_KEY in attributes:
                raise ValueError('Archive checkpoint was not omitted')
            attributes.pop(orm.ProcessNode.CHECKPOINT_KEY, None)
            role = roles[node.uuid]
            self.metadata(node, role, attributes)
            files = self.repositories(node)
            if role in ('frozen_bundle', 'retrieved'):
                if files != expected_files[node.uuid]:
                    raise ValueError('Unlisted repository bytes')
            elif role == 'process' and files:
                self.process_files(node, files)
            elif files:
                raise ValueError('Unknown process/infrastructure repository content')
            for path, raw in files.items():
                audited = audited_provenance(provenance.get(node.uuid, set()), path, raw)
                if role == 'frozen_bundle' and audited_license(manifests[node.uuid], path, raw):
                    audited = True
                if path.endswith('.tar.gz'):
                    if not audited:
                        raise ValueError('Unknown compressed provenance')
                    self.tar(raw)
                elif not audited:
                    sensitive(raw, allowed_paths=(self.root,) if role == 'process' else ())
                inventory['repositories'].append(
                    dict(
                        node_uuid=node.uuid,
                        path=path,
                        size=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest(),
                    )
                )
            inventory['nodes'].append(
                dict(
                    uuid=node.uuid,
                    node_type=node.node_type,
                    attributes_digest=digest(attributes),
                    extras_digest=digest(row['extras']),
                    label=node.label,
                    description=node.description,
                )
            )
            row['attributes'] = attributes
            normalized = {
                k: (v.isoformat() if k in ('ctime', 'mtime') else v)
                for k, v in row.items()
                if k not in ('id', 'user_id', 'dbcomputer_id')
            }
            self.metadata_bytes += len(canonical(normalized))
            if self.metadata_bytes > METADATA:
                raise ValueError('Aggregate metadata bound')
            rows.append(normalized)
            users.add(node.user.pk)
            if node.computer:
                computers.add(node.computer.pk)
        self.entities(users, computers, inventory)
        inventory['repositories'].sort(key=lambda f: (f['node_uuid'], f['path']))
        if len(canonical(inventory)) > INVENTORY:
            raise ValueError('Inventory byte bound')
        return inventory, rows, roots

    def tar(self, raw):
        import tarfile

        sha = hashlib.sha256(raw).hexdigest()
        if sha in self.nested_archives:
            if self.nested_archives[sha] != len(raw):
                raise ValueError('Nested source archive identity mismatch')
            return
        seen = set()
        try:
            with tarfile.open(fileobj=io.BytesIO(raw), mode='r|gz') as archive:
                for member in archive:
                    key = safe_path(member.name.rstrip('/'))
                    if key in seen or not (member.isfile() or member.isdir()):
                        raise ValueError('Unsafe retained source archive')
                    seen.add(key)
                    self.nested_paths += 1
                    self.nested_bytes += member.size
                    if (
                        self.nested_paths > NESTED_PATHS
                        or self.nested_bytes > NESTED_EXPANDED
                        or member.size > RAW
                    ):
                        raise ValueError('Nested source archive bound')
                    if member.isfile():
                        # Only the exact independently pinned upstream tar reaches
                        # this parser; inspect all members without extracting.
                        if len(archive.extractfile(member).read(RAW + 1)) != member.size:
                            raise ValueError('Truncated source member')
        except (tarfile.TarError, EOFError) as error:
            raise ValueError('Malformed retained source archive') from error
        # Callers check exact occurrence role/path/hash authority before this
        # cache lookup. Failed or partial inspections are never cached.
        self.nested_archives[sha] = len(raw)

    def metadata(self, node, role, attributes):
        if len(canonical(attributes)) + len(canonical(node.base.extras.all)) > METADATA:
            raise ValueError('Native metadata bound')
        if node.description or node.label != ('hyprn-mvp-scalar' if role == 'code' else ''):
            raise ValueError('Unapproved native labels/descriptions')
        extras = node.base.extras.all
        if role == 'code' and extras.get('hidden') is False:
            extras = {k: v for k, v in extras.items() if k != 'hidden'}
        if set(extras) - {'_aiida_hash'} or any(
            not isinstance(v, str) or not re.fullmatch('[a-f0-9]{64}', v) for v in extras.values()
        ):
            raise ValueError('Unapproved native extras')
        if role == 'process':
            if set(attributes) - PROCESS_ATTRIBUTES:
                raise ValueError('Unapproved process metadata')
            for key, expected in PROCESS_DEFAULTS.items():
                if key in attributes and canonical(attributes[key]) != canonical(expected):
                    raise ValueError('Unsupported process settings')
            if type(attributes['exit_status']) is not int or attributes['exit_status'] not in (
                0,
                300,
                301,
            ):
                raise ValueError('Unsupported terminal process status')
            if 'retrieve_list' in attributes and attributes['retrieve_list'] not in (
                ['result.json', 'launcher.stderr'],
                [
                    'result.json',
                    'launcher.stderr',
                    '_scheduler-stdout.txt',
                    '_scheduler-stderr.txt',
                ],
            ):
                raise ValueError('Unexpected retrieval inventory')
            if 'job_id' in attributes and not re.fullmatch('[0-9]+', attributes['job_id']):
                raise ValueError('Invalid scheduler job identity')
            if 'scheduler_lastchecktime' in attributes:
                from datetime import datetime

                if not isinstance(attributes['scheduler_lastchecktime'], str):
                    raise ValueError('Invalid scheduler timestamp')
                datetime.fromisoformat(attributes['scheduler_lastchecktime'])
            if 'exit_message' in attributes and (
                not isinstance(attributes['exit_message'], str)
                or len(attributes['exit_message']) > 4096
            ):
                raise ValueError('Invalid process diagnostic')
            sensitive(canonical(attributes), allowed_paths=(self.root,))
            for key in (
                'environment_variables',
                'prepend_text',
                'append_text',
                'custom_scheduler_commands',
            ):
                if attributes.get(key):
                    raise ValueError('Unsafe process environment/script')
            if 'remote_workdir' in attributes:
                self.remote_path(attributes['remote_workdir'], node.uuid)
            if 'last_job_info' in attributes:
                info = attributes['last_job_info']
                exact(info, {'job_id', 'job_state', 'job_owner', 'wallclock_time_seconds'})
                import getpass

                if (
                    info['job_owner'] != getpass.getuser()
                    or info['job_state'] not in ('running', 'done')
                    or not re.fullmatch('[0-9]+', info['job_id'])
                    or type(info['wallclock_time_seconds']) is not int
                ):
                    raise ValueError('Unknown scheduler identity')
            if attributes.get('detailed_job_info') is not None:
                raise ValueError('Unknown detailed scheduler information')
        elif role in ('frozen_bundle', 'retrieved'):
            if attributes:
                raise ValueError('Unapproved folder metadata')
        elif role == 'assessment':
            exact(attributes, {'version', 'evaluator_sha256'})
            if attributes['version'] != 'fixed-threshold-1' or not re.fullmatch(
                '[a-f0-9]{64}', attributes['evaluator_sha256']
            ):
                raise ValueError('Invalid assessment')
        elif role == 'code':
            if not isinstance(node, orm.InstalledCode) or attributes != dict(
                input_plugin='hyprn_mvp.scalar',
                append_text='',
                prepend_text='',
                use_double_quotes=False,
                with_mpi=None,
                wrap_cmdline_params=False,
                filepath_executable=str(self.root / 'launch-worker'),
            ):
                raise ValueError('Unapproved installed code')
        elif role == 'remote_folder':
            if not isinstance(node, orm.RemoteData):
                raise ValueError('Unknown remote node')
            exact(attributes, {'remote_path'})
            creators = node.base.links.get_incoming(link_type=LinkType.CREATE).all()
            if len(creators) != 1:
                raise ValueError('Unknown remote creator')
            self.remote_path(attributes['remote_path'], creators[0].node.uuid)

    def remote_path(self, path, process_uuid):
        import getpass

        work = (
            self.root
            / ('aiida-work' if self.root == launcher.ROOT else 'tmp/work')
            / getpass.getuser()
        )
        expected = str(work / process_uuid[:2] / process_uuid[2:4] / process_uuid[4:])
        if path != expected:
            raise ValueError('Unapproved remote work path')

    def process_files(self, node, files):
        if set(files) != {'_aiidasubmit.sh', '.aiida/calcinfo.json', '.aiida/job_tmpl.json'}:
            raise ValueError('Unknown process repository files')
        request = self.approved[node.uuid]['request']
        bundle_digest = request['bundle_digest']
        script = (
            '#!/bin/bash\nexec > _scheduler-stdout.txt\nexec 2> _sched'
            "uler-stderr.txt\n\n\n'"
            f'{self.root}'
            "/launch-worker' 'input' '"
            f'{bundle_digest}'
            "'  > 'result.json' 2> 'launcher.stderr'\n"
        ).encode()
        if files['_aiidasubmit.sh'] != script:
            raise ValueError('Unapproved job script')
        calc = dict(
            codes_info=[
                dict(
                    code_uuid=node.inputs.code.uuid,
                    cmdline_params=['input', bundle_digest],
                    stdout_name='result.json',
                    stderr_name='launcher.stderr',
                )
            ],
            local_copy_list=[[node.inputs.frozen_bundle.uuid, '.', 'input']],
            retrieve_list=[
                'result.json',
                'launcher.stderr',
                '_scheduler-stdout.txt',
                '_scheduler-stderr.txt',
            ],
            uuid=node.uuid,
            file_copy_operation_order=[2, 0, 1],
        )
        if data_json(files['.aiida/calcinfo.json']) != calc:
            raise ValueError('Unknown CalcInfo fields')
        job = data_json(files['.aiida/job_tmpl.json'])
        name = job.get('job_name')
        if not isinstance(name, str) or not re.fullmatch('aiida-[0-9]+', name):
            raise ValueError('Unknown job identity')
        expected = dict(
            submit_as_hold=False,
            rerunnable=False,
            job_name=name,
            sched_output_path='_scheduler-stdout.txt',
            shebang='#!/bin/bash',
            sched_error_path='_scheduler-stderr.txt',
            sched_join_files=False,
            prepend_text='',
            append_text='',
            job_resource=dict(
                num_machines=1,
                num_mpiprocs_per_machine=1,
                num_cores_per_machine=None,
                num_cores_per_mpiproc=None,
                tot_num_mpiprocs=1,
            ),
            codes_info=[
                dict(
                    prepend_cmdline_params=[],
                    cmdline_params=[str(self.root / 'launch-worker'), 'input', bundle_digest],
                    use_double_quotes=[False, False],
                    wrap_cmdline_params=False,
                    stdin_name=None,
                    stdout_name='result.json',
                    stderr_name='launcher.stderr',
                    join_files=False,
                )
            ],
            codes_run_mode=0,
            import_sys_environment=True,
            job_environment={},
            environment_variables_double_quotes=False,
            max_memory_kb=None,
            max_wallclock_seconds=60,
        )
        if job != expected:
            raise ValueError('Unknown scheduler template')

    def entities(self, users, computers, inventory):
        for identifier in computers:
            row = next(
                iter(
                    orm.QueryBuilder(backend=self.backend)
                    .append(orm.Computer, filters={'id': identifier}, project='**')
                    .dict()[0]
                    .values()
                )
            )
            exact(
                row,
                {
                    'id',
                    'uuid',
                    'label',
                    'hostname',
                    'description',
                    'scheduler_type',
                    'transport_type',
                    'metadata',
                },
            )
            expected_label = (
                'hyprn-mvp-local' if self.root == launcher.ROOT else 'hyprn-mvp-scoped-worker'
            )
            if any(
                row[k] != v
                for k, v in dict(
                    label=expected_label,
                    hostname='localhost',
                    description='',
                    scheduler_type='core.direct',
                    transport_type='core.local',
                ).items()
            ):
                raise ValueError('Unapproved native computer')
            metadata = dict(
                workdir=str(
                    self.root
                    / ('aiida-work' if self.root == launcher.ROOT else 'tmp/work')
                    / '{username}'
                )
            )
            if self.root != launcher.ROOT:
                metadata['minimum_scheduler_poll_interval'] = 0.2
            if row['metadata'] != metadata:
                raise ValueError('Unapproved computer execution metadata')
            data = {k: v for k, v in row.items() if k != 'id'}
            inventory['computers'].append(dict(uuid=row['uuid'], metadata_digest=digest(data)))
        inventory['computers'].sort(key=lambda row: row['uuid'])
        expected = (
            'owner@hyprn-mvp.invalid'
            if self.root == launcher.ROOT
            else 'hyprn-mvp-test@localhost.invalid'
        )
        for identifier in users:
            row = next(
                iter(
                    orm.QueryBuilder(backend=self.backend)
                    .append(orm.User, filters={'id': identifier}, project='**')
                    .dict()[0]
                    .values()
                )
            )
            exact(row, {'id', 'email', 'first_name', 'last_name', 'institution'})
            data = {k: v for k, v in row.items() if k != 'id'}
            if data != dict(email=expected, first_name='', last_name='', institution=''):
                raise ValueError('Unapproved native user identity')
            inventory['users'].append(
                dict(uuid='user:' + digest(data), metadata_digest=digest(data))
            )
        inventory['users'].sort(key=lambda row: row['uuid'])

    def run(self):
        before, rows, roots = self.inspect()
        self.native.fault('archive_preflight')
        with tempfile.TemporaryDirectory(
            prefix='hyprn-mvp-record-', dir=self.root / 'tmp'
        ) as directory:
            path = Path(directory) / 'computations.aiida'
            create_archive(
                roots,
                path,
                backend=self.backend,
                include_authinfos=False,
                include_comments=False,
                include_logs=False,
                strip_checkpoints=True,
                **RULES,
            )
            archive_bounds(path)
            with zipfile.ZipFile(path) as archive:
                expected = {'metadata.json', 'db.sqlite3'} | {
                    'repo/' + r['sha256'] for r in before['repositories']
                }
                if set(archive.namelist()) != expected:
                    raise ValueError('Unlisted repository objects in native archive')
                if archive.getinfo('metadata.json').file_size > METADATA:
                    raise ValueError('Archive metadata bound')
                metadata = data_json(archive.read('metadata.json'))
                exact(
                    metadata,
                    {
                        'export_version',
                        'aiida_version',
                        'key_format',
                        'compression',
                        'ctime',
                        'creation_parameters',
                    },
                )
                from datetime import datetime

                datetime.fromisoformat(metadata['ctime'])
                if any(
                    metadata[k] != v
                    for k, v in dict(
                        export_version='main_0001',
                        aiida_version='2.9.3',
                        key_format='sha256',
                        compression=6,
                    ).items()
                ):
                    raise ValueError('Unsupported native archive format')
                params = metadata['creation_parameters']
                expected_params = dict(
                    entities_starting_set={'node': sorted(n.uuid for n in roots)},
                    include_authinfos=False,
                    include_comments=False,
                    include_logs=False,
                    graph_traversal_rules=FULL_RULES,
                )
                if (
                    isinstance(params, dict)
                    and isinstance(params.get('entities_starting_set'), dict)
                    and isinstance(params['entities_starting_set'].get('node'), list)
                ):
                    params['entities_starting_set']['node'].sort()
                if params != expected_params:
                    raise ValueError('Native archive creation policy mismatch')
            with ArchiveFormatSqlZip().open(path, 'r') as reader:
                backend = reader.get_backend()
                for entity in (orm.AuthInfo, orm.Comment, orm.Log, orm.Group):
                    if orm.QueryBuilder(backend=backend).append(entity).count():
                        raise ValueError('Unexpected administrative archive entity')
                after, archived_rows, _ = self.inspect(backend)
                if before != after or rows != archived_rows:
                    raise ValueError('Actual archive differs from approved inventory')
                count = orm.QueryBuilder(backend=backend).append(orm.Node).count()
                if count != len(before['nodes']):
                    raise ValueError('Unexpected archive nodes')
                for entity, key in ((orm.User, 'users'), (orm.Computer, 'computers')):
                    if orm.QueryBuilder(backend=backend).append(entity).count() != len(before[key]):
                        raise ValueError('Unexpected archive infrastructure')
            final, final_rows, _ = self.inspect()
            if final != before or final_rows != rows:
                raise ValueError('Native metadata changed during archive creation')
            raw = path.read_bytes()
        return dict(
            schema_version='1',
            origin_store_uuid=self.payload['origin_store_uuid'],
            inventory=before,
            inventory_digest=digest(before),
            archive_sha256=hashlib.sha256(raw).hexdigest(),
            archive_size=len(raw),
            archive_base64=base64.b64encode(raw).decode('ascii'),
        )


def archive_record(native, payload):
    try:
        return Export(native, payload).run()
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError('Invalid or incomplete native archive record') from error
