"""AiiDA owns processes and artifacts; candidate bytes never execute here."""
import io
import json
import math
import os
from pathlib import Path
from uuid import UUID

from aiida import orm
from aiida.common.datastructures import CalcInfo, CodeInfo
from aiida.engine import CalcJob
from aiida.parsers.parser import Parser
from hyprn_mvp_app.contracts import canonical, check_digest, data_json, digest
from hyprn_mvp_app.execution_bundle import verify_files, closed, MAX_BYTES, safe_path, validate_retained_bundle
from . import launcher

PROFILE = 'hyprn-mvp'
REQUEST_KEYS = {'run_id', 'scope', 'command_id', 'payload_digest', 'bundle_digest'}


from .results import (validate_result, validate_criteria, retained_bundle, read_stored_result,
                      UnsupportedRecordVersion, ASSESSMENT_VERSION)


class ScalarCalculation(CalcJob):
    @staticmethod
    def validate_upstream(value, _port):
        if len(value) > 64:
            return 'At most 64 upstream results are supported'
        for label, node in value.items():
            if (not isinstance(node, orm.Dict) or not node.is_stored
                    or label != 'r' + UUID(node.uuid).hex):
                return 'Flat original stored results Dict namespace required'

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input('frozen_bundle', valid_type=orm.FolderData)
        spec.input('request', valid_type=orm.Dict)
        spec.input_namespace('upstream_results', dynamic=True, valid_type=orm.Dict,
                             required=False, validator=cls.validate_upstream)
        parent_validator = spec.inputs.validator
        def validate_inputs(inputs, port):
            error = parent_validator(inputs, port)
            if error:return error
            try:
                repository = inputs['frozen_bundle'].base.repository
                with repository.open('manifest.json', mode='rb') as stream:
                    raw = stream.read(1048577)
                if len(raw)>1048576:raise ValueError('Manifest size bound')
                manifest = data_json(raw)
                request=inputs['request'].get_dict()
                if set(request)!=REQUEST_KEYS:raise ValueError('Closed immutable request required')
                for key in ('run_id','scope','command_id'):
                    if str(UUID(request[key]))!=request[key]:raise ValueError('Canonical request UUID required')
                for key in ('payload_digest','bundle_digest'):
                    if not isinstance(request[key],str) or len(request[key])!=64 or any(c not in '0123456789abcdef' for c in request[key]):
                        raise ValueError('Immutable request digest required')
                actual = {label:node.uuid for label,node in inputs.get('upstream_results',{}).items()}
                if manifest['schema_version']=='2':
                    expected = {}
                elif manifest['schema_version'] in ('3','4','5','6','8'):
                    descriptor=manifest['result_dependencies']
                    with repository.open('result-dependencies.json',mode='rb') as stream:
                        raw=stream.read(min(descriptor['size'],MAX_BYTES)+1)
                    if len(raw)!=descriptor['size'] or __import__('hashlib').sha256(raw).hexdigest()!=descriptor['sha256']:
                        raise ValueError('Dependency bytes mismatch')
                    dependencies=data_json(raw);closed('ResultDependencies1',dependencies)
                    expected={s['label']:s['result_uuid'] for s in dependencies['sources']}
                    if len(expected)!=len(dependencies['sources']):raise ValueError('Duplicate source label')
                else:raise ValueError('Unsupported bundle version')
                if actual!=expected:raise ValueError('Upstream inputs differ from frozen dependency mapping')
                if inputs['metadata'].get('disable_cache') is not True:raise ValueError('Fresh execution requires disabled cache')
                if manifest['schema_version'] in ('2','3','4','5','6','8'):
                    files={};total=0
                    if not 0<len(manifest['files'])<=2000:raise ValueError('Bundle file bound')
                    for item in manifest['files']:
                        path=safe_path(item['path'])
                        if path in files:raise ValueError('Duplicate bundle path')
                        with repository.open(path,mode='rb') as stream:files[path]=stream.read(MAX_BYTES-total+1)
                        total+=len(files[path])
                        if total>MAX_BYTES:raise ValueError('Bundle byte bound')
                    bundle=dict(manifest=manifest,files=files)
                    launcher.verify_execution_bundle(bundle,inputs['request'].get_dict(),dict(runtime=manifest['runtime']))
                    # Validate every stored native creator and scalar even when a
                    # caller bypasses NativeExecution.launch and uses the engine.
                    backend=inputs['frozen_bundle'].backend
                    native=NativeExecution()
                    native.backend=backend
                    native.store_uuid=backend.get_repository().uuid
                    resolved=native._upstream_results(bundle)
                    if {k:n.uuid for k,n in resolved.items()}!=actual:raise ValueError('Exact original native inputs required')
            except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:
                return str(error)
        spec.inputs.validator = validate_inputs
        spec.output('results', valid_type=orm.Dict, required=False)
        spec.output('assessment', valid_type=orm.Dict, required=False)
        spec.inputs['metadata']['options']['parser_name'].default = 'hyprn_mvp.scalar'
        spec.inputs['metadata']['options']['resources'].default = {'num_machines': 1, 'num_mpiprocs_per_machine': 1}
        spec.exit_code(300, 'ERROR_WORKER', message='Missing or invalid bounded worker output')
        spec.exit_code(301, 'ERROR_SCIENTIFIC', message='Partial or failed scientific execution')

    def prepare_for_submission(self, folder):
        code = CodeInfo()
        code.code_uuid = self.inputs.code.uuid
        code.cmdline_params = ['input', self.inputs.request.get_dict()['bundle_digest']]
        code.stdout_name = 'result.json'
        code.stderr_name = 'launcher.stderr'
        info = CalcInfo()
        info.codes_info = [code]
        info.local_copy_list = [(self.inputs.frozen_bundle.uuid, '.', 'input')]
        info.retrieve_list = ['result.json', 'launcher.stderr']
        return info


class ScalarParser(Parser):
    def parse(self, **kwargs):
        try:
            with self.retrieved.base.repository.open('result.json', mode='rb') as stream:
                raw = stream.read(131073)
            request = self.node.inputs.request.get_dict()
            bundle = retained_bundle(self.node.inputs.frozen_bundle.base.repository, request)
            model = json.loads(bundle['files']['model.json'])
            result = validate_result(raw, request, model)
            config = json.loads(bundle['files']['configuration.json'])
            validate_criteria(result, config)
            self.out('results', orm.Dict(dict=result))
            self.out('assessment', orm.Dict(dict=dict(version=ASSESSMENT_VERSION,
                evaluator_sha256=__import__('hashlib').sha256(Path(__file__).with_name('results.py').read_bytes()).hexdigest())))
            if result['execution']['state'] != 'finished':
                return self.exit_codes.ERROR_SCIENTIFIC
        except (KeyError, ValueError, OSError, TypeError, RecursionError, AttributeError):
            return self.exit_codes.ERROR_WORKER


class NativeExecution:
    """Explicit fresh profile only. An uncertain stored node is never relaunched."""
    def __init__(self, *, backend=None, root=None):
        if (backend is None) != (root is None):
            raise ValueError('Explicit backend and root must be injected together')
        self.backend = backend
        self.root = launcher.ROOT if root is None else Path(root)
        self.profile_name = PROFILE if backend is None else backend.profile.name
        if backend is not None:
            if Path(backend.profile.storage_config['filepath']) != self.root / 'native':
                raise ValueError('Injected backend must belong to explicit fixture root')
            self.store_uuid = str(UUID(backend.get_repository().uuid))
        self.fault = lambda point: None

    @classmethod
    def from_environment(cls):
        expected = str(launcher.ROOT / 'aiida')
        if os.environ.get('AIIDA_PATH') != expected:
            raise RuntimeError('Explicit new AIIDA_PATH required before importing AiiDA')
        import aiida
        from aiida.manage.configuration import get_config
        config = get_config()
        if (str(config.dirpath) != expected+'/.aiida' or config.profile_names != [PROFILE]
                or config.default_profile_name is not None):
            raise RuntimeError('Unexpected native profile configuration')
        profile = config.get_profile(PROFILE)
        if profile.storage_config['filepath'] != str(launcher.ROOT / 'aiida-store'):
            raise RuntimeError('Unexpected native store')
        pinned = json.loads((launcher.ROOT / 'profile-identity.json').read_text())
        if profile.uuid != pinned['profile_uuid']:
            raise RuntimeError('Native profile identity changed')
        aiida.load_profile(PROFILE)
        from aiida.manage import get_manager
        instance = cls()
        instance.backend = get_manager().get_profile_storage()
        instance.store_uuid = get_manager().get_profile_storage().get_repository().uuid
        if not instance.store_uuid or instance.store_uuid != pinned['repository_uuid']:
            raise RuntimeError('Native storage identity is unavailable')
        code=orm.load_code(pinned['code_uuid'])
        if (code.computer.uuid!=pinned['computer_uuid']
                or Path(code.filepath_executable)!=launcher.ROOT/'launch-worker'
                or code.computer.get_workdir()!=str(launcher.ROOT/'aiida-work/{username}')
                or code.computer.hostname!='localhost'):
            raise RuntimeError('Native code/computer identity changed')
        return instance

    def _resolve_source(self, source):
        """Read exact existing process and its CREATE/results Dict, never copy it."""
        from aiida.common.links import LinkType
        from aiida.common.exceptions import NotExistent
        if not isinstance(source, dict) or set(source) != {'source_run_id','request','association','results_digest','outputs'}:
            raise ValueError('Closed approved source required')
        association = source['association']; request = source['request']
        if (not isinstance(association, dict) or set(association) != {'store_uuid','process_uuid'}
                or not isinstance(request, dict)
                or set(request) != REQUEST_KEYS or request['run_id'] != source['source_run_id']):
            raise ValueError('Source request/store mismatch')
        if UUID(association['store_uuid']) != UUID(self.store_uuid):raise ValueError('Source store mismatch')
        if str(UUID(association['process_uuid'])) != association['process_uuid']:
            raise ValueError('Exact source process UUID required')
        try:
            node = orm.QueryBuilder(backend=self.backend).append(orm.Node,
                filters={'uuid': association['process_uuid']}, project='*').one()[0]
            if (not isinstance(node, orm.CalcJobNode) or node.process_type != 'aiida.calculations:hyprn_mvp.scalar'
                    or not node.is_finished_ok or canonical(node.inputs.request.get_dict()) != canonical(request)):
                raise ValueError('Source process/request mismatch')
            result_node = node.base.links.get_outgoing(link_type=LinkType.CREATE, link_label_filter='results').one().node
            if not isinstance(result_node, orm.Dict) or not result_node.is_stored:
                raise ValueError('Original results Dict required')
            creator = result_node.base.links.get_incoming(link_type=LinkType.CREATE).one()
            if creator.node.uuid != node.uuid or creator.link_label != 'results':
                raise ValueError('Source result creator mismatch')
            source_pin = {k:source[k] for k in ('source_run_id','request','association','results_digest')}
            closed('NativeSource', source_pin | dict(result_uuid=result_node.uuid,label='r'+UUID(result_node.uuid).hex))
            repository = node.inputs.frozen_bundle.base.repository
            with repository.open('manifest.json', mode='rb') as stream:
                raw = stream.read(1048577)
            if len(raw) > 1048576:raise ValueError('Source manifest bound')
            manifest = data_json(raw)
            if manifest.get('schema_version') == '1':
                bundle = retained_bundle(repository, request)  # Historical data only.
            else:
                if manifest.get('schema_version') not in ('2','3','4','5','6','8'):raise ValueError('Unsupported source bundle')
                files = {}; total = 0
                if not 0 < len(manifest['files']) <= 2000:raise ValueError('Source file bound')
                for item in manifest['files']:
                    path = safe_path(item['path'])
                    with repository.open(path, mode='rb') as stream:
                        files[path] = stream.read(MAX_BYTES - total + 1)
                    total += len(files[path])
                    if total > MAX_BYTES:raise ValueError('Source byte bound')
                bundle = dict(manifest=manifest,files=files)
                launcher.verify_execution_bundle(bundle,request,dict(runtime=manifest['runtime']))
            raw_result = result_node.get_dict()
            if digest(raw_result) != source['results_digest']:raise ValueError('Source results digest mismatch')
            result = read_stored_result(raw_result,request,data_json(bundle['files']['model.json']))
            if result['execution']['state'] != 'finished' or result['execution']['exit_code'] != 0:
                raise ValueError('Successful source execution required')
            wanted = source['outputs']
            if not isinstance(wanted,list) or not 0 < len(wanted) <= 1000:raise ValueError('Source output bound')
            keys = []; available = {tuple(o['target'][k] for k in ('instance_id','port_id')):o for o in result['outputs']}
            for output in wanted:
                if not isinstance(output,dict) or set(output) != {'target','value','units'}:raise ValueError('Closed source scalar required')
                closed('PortRef',output['target'])
                key = tuple(output['target'][k] for k in ('instance_id','port_id')); keys.append(key)
                actual = available.get(key)
                if (actual is None or actual['availability'] != 'available'
                        or type(output['value']) not in (int,float) or not math.isfinite(output['value'])
                        or canonical(output) != canonical({k:actual[k] for k in ('target','value','units')})):
                    raise ValueError('Source scalar mismatch')
            if keys != sorted(set(keys)):raise ValueError('Distinct ordered source outputs required')
            return result_node
        except (NotExistent, AttributeError, KeyError, TypeError) as error:
            raise ValueError('Exact retained source unavailable') from error

    def resolve_results(self, sources):
        if not isinstance(sources,list) or len(sources) > 64:raise ValueError('Source count bound')
        runs = [s.get('source_run_id') if isinstance(s,dict) else None for s in sources]
        if any(not isinstance(r,str) for r in runs) or runs != sorted(set(runs)):
            raise ValueError('Distinct ordered source runs required')
        if sum(len(s.get('outputs',[])) for s in sources) > 1000:raise ValueError('Source scalar count bound')
        resolved = [s | dict(result_uuid=self._resolve_source(s).uuid) for s in sources]
        return data_json(canonical(resolved))

    def archive_record(self, preflight):
        from .computational_export import archive_record
        return archive_record(self, preflight)

    def _upstream_results(self, bundle):
        if bundle['manifest']['schema_version'] == '2':return {}
        dependencies = data_json(bundle['files']['result-dependencies.json'])
        nodes = {}
        for pin in dependencies['sources']:
            outputs = {}
            for row in dependencies['mappings']:
                if row['source_label'] == pin['label']:
                    key = tuple(row['source_output'][k] for k in ('instance_id','port_id'))
                    output = dict(target=row['source_output'],value=row['original_value'],units=row['original_units'])
                    if key in outputs and canonical(outputs[key]) != canonical(output):raise ValueError('Contradictory source output')
                    outputs[key] = output
            source = {k:pin[k] for k in ('source_run_id','request','association','results_digest')}
            node = self._resolve_source(source | dict(outputs=[outputs[k] for k in sorted(outputs)]))
            if node.uuid != pin['result_uuid']:raise ValueError('Original result UUID mismatch')
            source_node=node.creator
            with source_node.inputs.frozen_bundle.base.repository.open('manifest.json',mode='rb') as stream:
                raw=stream.read(1048577)
            if len(raw)>1048576:raise ValueError('Source manifest bound')
            source_manifest=data_json(raw)
            config=data_json(bundle['files']['configuration.json'])
            for item in config['inputs']:
                binding=item.get('result_binding')
                if binding and binding['source_run_id']==pin['source_run_id'] and binding['source_configuration_digest']!=source_manifest['configuration_digest']:
                    raise ValueError('Original source configuration digest mismatch')
            nodes[pin['label']] = node
        return nodes

    def require_attestation(self):
        return launcher.require_attestation(root=self.root)

    def bundle_runtime(self):
        # Bind the existing selection payload to the current native attestation.
        # The app-side bridge receives no fingerprint/host paths or new fields.
        evidence=launcher.require_attestation(root=self.root)
        selected=launcher.bundle_runtime(root=self.root)
        try:
            if evidence['passed'] is not True:raise ValueError('Attestation not confirmed')
            fingerprint=evidence['fingerprint'];runtime=fingerprint['runtime']
            expected=dict(image_digest=fingerprint['image'],architecture=runtime['architecture'],
                python_version=runtime['python_version'],worker_entrypoint='hyprn_mvp_integration.worker',
                policy_digest=digest(fingerprint['policy']))
            if fingerprint['image']!=runtime['worker_image'] or selected['runtime']!=expected:
                raise ValueError('Selected runtime differs from attestation')
        except (KeyError,TypeError,ValueError) as error:
            raise RuntimeError('Selected runtime attestation identity mismatch') from error
        return selected

    def launch(self, bundle, request):
        if bundle['manifest'].get('schema_version') not in ('2','3','4','5','6','8'):
            raise ValueError('Unsupported bundle version; create a new run command')
        if set(request) != REQUEST_KEYS or request['bundle_digest'] != bundle['manifest']['bundle_digest'] or request['run_id'] != bundle['manifest']['run_id']:
            raise ValueError('Immutable request mismatch')
        self.require_attestation()
        launcher.verify_execution_bundle(bundle, request, self.bundle_runtime())
        if self.matches(request):
            raise RuntimeError('Existing native request cannot be launched again')
        from aiida.manage import get_manager
        from aiida.engine.utils import instantiate_process
        if self.backend is not get_manager().get_profile_storage():
            raise ValueError('Runner backend differs from explicit native backend')
        code=orm.load_code('hyprn-mvp-scalar')
        if self.root!=launcher.ROOT:
            launcher.fixture_runtime_root(self.root)
            if (Path(code.filepath_executable)!=self.root/'launch-worker'
                    or code.computer.hostname!='localhost'
                    or not code.computer.get_workdir().startswith(str(self.root/'tmp')+'/')):
                raise ValueError('Installed code differs from isolated runtime')
        retained = orm.FolderData(backend=self.backend)
        for path, raw in {**bundle['files'], 'manifest.json': canonical(bundle['manifest'])}.items():
            retained.base.repository.put_object_from_filelike(io.BytesIO(raw), path)
        self.fault('before_node')
        runner = get_manager().create_runner(communicator=None)
        process = None
        try:
            launcher.verify_execution_bundle(bundle, request, self.bundle_runtime())
            upstream = self._upstream_results(bundle)
            process = instantiate_process(runner, ScalarCalculation,
                code=code, frozen_bundle=retained,
                request=orm.Dict(dict=request, backend=self.backend), upstream_results=upstream,
                metadata={'disable_cache': True, 'options': {'max_wallclock_seconds': 60}})
            self.fault('after_node')
            self.fault('before_continuation')
            runner.run_get_node(process)
            self.fault('after_continuation')
            result = self.inspect(process.node.uuid)
            self.fault('before_response')
            return result
        finally:
            if process is not None:
                process.close()
            runner.close()

    def matches(self, request):
        if set(request) != REQUEST_KEYS:
            raise ValueError('Incomplete native match')
        query = orm.QueryBuilder(backend=self.backend).append(orm.Dict, tag='request', filters={
            'attributes.' + key: value for key, value in request.items()}).append(
                orm.CalcJobNode, with_incoming='request', edge_filters={'label': 'request'},
                filters={'process_type': 'aiida.calculations:hyprn_mvp.scalar'}, project='uuid')
        return [row[0] for row in query.all()]

    def inspect(self, process_uuid):
        node = orm.load_node(process_uuid)
        if not isinstance(node, orm.CalcJobNode) or node.process_type != 'aiida.calculations:hyprn_mvp.scalar':
            raise ValueError('Unexpected native process')
        result = dict(store_uuid=self.store_uuid, process_uuid=node.uuid,
                      process_state=node.process_state.value if node.process_state else 'unknown', exit_status=node.exit_status)
        if 'results' in node.outputs:
            try:
                request = node.inputs.request.get_dict()
                bundle = retained_bundle(node.inputs.frozen_bundle.base.repository, request)
                assessment = node.outputs.assessment.get_dict() if 'assessment' in node.outputs else None
                result['results'] = read_stored_result(node.outputs.results.get_dict(), request,
                    json.loads(bundle['files']['model.json']), assessment)
            except UnsupportedRecordVersion:
                result['result_error'] = dict(code='unsupported_record_version', partial=True)
            except (ValueError, KeyError, TypeError, OSError, AttributeError, RecursionError):
                result['result_error'] = dict(code='corrupt_retained_record', partial=True)
        return result

    def retained_bundle(self, process_uuid):
        self.inspect(process_uuid)
        node = orm.load_node(process_uuid)
        return retained_bundle(node.inputs.frozen_bundle.base.repository, node.inputs.request.get_dict())

    def read_record(self, request, association):
        """Fixed data-only read of an exact app-owned request and native association.

        No lookup by label, current model, launch, continuation or reassessment.
        Even raw failed artifacts require the complete immutable request match.
        """
        if (set(request) != REQUEST_KEYS or set(association) != {'store_uuid','process_uuid'}
                or association['store_uuid'] != self.store_uuid):
            raise ValueError('Retained store/request mismatch')
        from uuid import UUID
        from aiida.common.exceptions import NotExistent
        if str(UUID(association['process_uuid'])) != association['process_uuid']:
            raise ValueError('Exact retained process UUID required')
        try:node = orm.load_node(association['process_uuid'])
        except NotExistent:raise ValueError('Retained process unavailable') from None
        if (not isinstance(node, orm.CalcJobNode) or node.process_type != 'aiida.calculations:hyprn_mvp.scalar'
                or node.uuid != association['process_uuid'] or node.inputs.request.get_dict() != request):
            raise ValueError('Retained process/request mismatch')
        record = dict(**association,request=request,
            process_state=node.process_state.value if node.process_state else 'unknown',exit_status=node.exit_status,
            bundle=None,results=None,assessment=None,artifacts={},errors=[])
        def partial(code):
            record['errors'].append(dict(code=code,partial=True))
        try:
            record['bundle'] = self.retained_bundle(node.uuid)
            if 'assessment' in node.outputs:
                record['assessment'] = node.outputs.assessment.get_dict()
            if 'results' in node.outputs:
                record['results'] = read_stored_result(node.outputs.results.get_dict(),request,
                    json.loads(record['bundle']['files']['model.json']),record['assessment'])
            else:partial('missing_results')
        except UnsupportedRecordVersion:
            partial('unsupported_record_version')
        except (ValueError,KeyError,TypeError,OSError,AttributeError,RecursionError):
            partial('corrupt_retained_record')
        # Only the two fixed calculation outputs, never arbitrary repository paths.
        if 'retrieved' in node.outputs:
            for path in ('result.json','launcher.stderr'):
                try:
                    with node.outputs.retrieved.base.repository.open(path,mode='rb') as stream:
                        raw = stream.read(131073)
                    if len(raw)>131072:raise ValueError('Retained artifact bound')
                    record['artifacts'][path] = raw
                except (OSError,KeyError,ValueError):partial('missing_or_invalid_artifact')
        else:partial('missing_artifacts')
        return record
