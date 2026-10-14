"""Independent contract fixtures; candidate source is never imported here."""
import base64
import hashlib
from uuid import uuid4
from hyprn_mvp_app.store import canonical, digest

def uid(): return str(uuid4())
def raw_hash(raw): return hashlib.sha256(raw).hexdigest()


def scoped_evidence_root():
    """Native integration evidence is written and read only inside the test's own scratch scope.

    The scope is the one deployment/checks.py allocated (``HYPRN_MVP_TEST_SCOPE_ROOT``); outside
    a scope the location is refused, never guessed.
    """
    import os
    from pathlib import Path
    value = os.environ.get('HYPRN_MVP_TEST_SCOPE_ROOT')
    if not value:
        raise RuntimeError('Native integration evidence needs a scoped scratch store: '
                           'run this test through deployment/checks.py')
    return Path(value).resolve() / 'evidence'


def require_scoped_runtime(runtime):
    """A native runtime used by a test lives inside that test's scratch scope, never in a
    retained, historical or live installation."""
    from pathlib import Path
    scope = scoped_evidence_root().parent
    root = Path(runtime.root).resolve()
    if root != scope and scope not in root.parents:
        raise RuntimeError('Native runtime outside the test scratch scope; refusing to use it')
    return runtime

_SCOPED_RUNTIME = []


def scoped_native_runtime():
    """The test scope's own native runtime: the fresh backend that deployment/checks.py created for
    this scope and one worker built and attested inside the same scope, prepared once per scope.
    It is never a historical, retained or live profile; outside a native scope it is refused."""
    if not _SCOPED_RUNTIME:
        from checks import PROJECTION_SCOPE as scope, NATIVE_BACKEND as backend
        if scope is None or backend is None:
            raise RuntimeError('Native integration runtime needs a scoped native backend: '
                               'run this test through deployment/checks.py')
        import scoped_fixture as guard
        from hyprn_mvp_integration.calculation import NativeExecution
        guard.prepare_worker_fixture(scope, backend)
        _SCOPED_RUNTIME.append(require_scoped_runtime(NativeExecution(backend=backend, root=scope.root)))
    runtime = _SCOPED_RUNTIME[0]
    runtime.fault = lambda point: None  # No injected fault outlives the test that injected it.
    return runtime

def legacy_fixture(kind='chain', multiplier=2, downstream=None):
    """Historical schema1 data only; never accepted for new execution."""
    sid, mid, revision = uid(), uid(), uid()
    definitions, instances, sources, inputs, connections = [], [], [], [], []
    targets = {}
    def component(name, ins, outs, source):
        version, instance = uid(), uid()
        ports = [dict(port_id=uid(), definition_version_id=version, direction=direction,
                      name=symbol, code_symbol=symbol, value_type='real_scalar', units=units)
                 for direction, values in [('input', ins), ('output', outs)] for symbol, units in values]
        raw = source.encode()
        sha = raw_hash(raw)
        sources.append(dict(encoding='base64', media_type='text/x-python', bytes=base64.b64encode(raw).decode(), sha256=sha))
        definitions.append(dict(definition_id=uid(), definition_version_id=version, kind='explicit_component',
            name=name, ports=ports, source_refs=[sha], residual_port_ids=[], child_instances=[], boundary_mappings=[], annotations=[]))
        instances.append(dict(instance_id=instance, definition_version_id=version, name=name))
        refs = {p['code_symbol']:dict(instance_id=instance, port_id=p['port_id']) for p in ports}
        targets[name] = refs
        return refs
    def assign(ref, value, units=''):
        inputs.append(dict(target=ref, value=value, units=units,
            provenance=dict(kind='manual', statement='Explicit scientific fixture', evidence_version_ids=[])))
    if kind == 'chain':
        a=component('linear',[('x',''),('z','')],[('u','')],f"outputs['u'] = {multiplier} * inputs['x'] + inputs['z']\r\n# café\r\n")
        b=component('square',[('u','')],[('y','')],downstream or "outputs['y'] = inputs['u'] ** 2\n")
        assign(a['x'],2);assign(a['z'],3)
        connections.append(dict(connection_id=uid(),source_ref=a['u'],target_ref=b['u']))
        # Deliberately reversed storage order must not change topology semantics.
        instances.reverse()
    elif kind == 'unrelated':
        a=component('response',[('drive',''),('gain','')],[('response','')],"outputs['response'] = inputs['gain'] / (1 + inputs['drive'] ** 2)\n")
        assign(a['drive'],2);assign(a['gain'],15)
    elif kind in ('units','affine'):
        target_unit='km' if kind=='units' else 'K'
        a=component('distance',[('entered',target_unit)],[('travel',target_unit)],"outputs['travel'] = inputs['entered']\n")
        assign(a['entered'],2000,'m' if kind=='units' else 'degC')
    else: raise ValueError(kind)
    model=dict(schema_version='1',model_id=mid,model_revision_id=revision,parent_model_revision_id=None,
        originating_draft_revision='fixture:1',root_instance_id=uid(),definitions=definitions,instances=instances,
        ports=[],connections=connections,boundary_mappings=[],annotations=[],source_files=sources,required_capabilities=['flat_explicit_scalar'])
    model['digest']=digest(model)
    configuration=dict(schema_version='1',configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None,
        study_id=sid,model_id=mid,model_revision_id=revision,name='Frozen test configuration',inputs=inputs,criteria=[],
        numerical=dict(mode='deterministic',initialization=[],solvers=[],derivatives=dict(method='none',form=None,check=None),
                       design_variables=[],objectives=[],constraints=[],optimizer=None,uncertainty=None),
        context_snapshot=dict(description='Retained context',boundary='',notes=[]),evidence_snapshots=[],required_capabilities=['flat_explicit_scalar'])
    configuration['digest']=digest(configuration)
    files={'model.json':canonical(model),'generated/components.json':canonical({k:model[k] for k in ('definitions','instances','connections')})}
    files.update({'sources/'+s['sha256']+'.py':base64.b64decode(s['bytes']) for s in sources})
    descriptors=[dict(file_id=uid(),path=p,size=len(raw),sha256=raw_hash(raw),media_type='text/x-python' if p.endswith('.py') else 'application/json',role='source' if p.endswith('.py') else 'model' if p=='model.json' else 'generated') for p,raw in sorted(files.items())]
    prepared=dict(schema_version='1',preparation_id=uid(),model_id=mid,model_revision_id=revision,model_digest=model['digest'],
        configuration_revision_id=configuration['configuration_revision_id'],configuration_digest=configuration['digest'],
        required_capabilities=['flat_explicit_scalar'],generator_identity=dict(name='independent-fixture',version='1',source_commit='0'*40,template_digest=raw_hash(b'fixture')),
        dependency_requirements=[dict(name='openmdao',version='3.45.1')],files=descriptors,license_notices=[])
    package_files=[dict(d,path='revisions/'+revision+'.json') if d['path']=='model.json' else d for d in descriptors if d['role']!='generated']
    package=dict(schema_version='1',source_service='independent-fixture',model_id=mid,model_revision_id=revision,
        revisions=[model],files=package_files,required_capabilities=['flat_explicit_scalar'],license_notices=[])
    package['digest']=digest(package);prepared['model_package_manifest']=package
    prepared['prepared_digest']=digest(prepared)
    return dict(prepared=prepared,files=files,frozen=dict(configuration=configuration,model_snapshot=model,study_revision=uid()),targets=targets)

def fixture(kind='chain', multiplier=2, downstream=None, *, current=False):
    """Read exact captured producer bytes; historical admission is explicit by default."""
    import copy
    import gzip
    import json
    from pathlib import Path
    name = 'native-programs.json.gz' if current else 'native-programs-protocol1.json.gz'
    data=json.loads(gzip.decompress((Path(__file__).parent/'fixtures'/name).read_bytes()))
    key='chain3' if kind=='chain' and multiplier==3 else kind
    if downstream is not None:
        matches=[name for name,case in data['cases'].items()
                 if any(base64.b64decode(s['bytes']).decode()==downstream for s in case['frozen']['model_snapshot']['source_files'])]
        if not matches:raise ValueError('Capture this source through the pinned producer before using it as an execution fixture')
        key=matches[0]
    case=copy.deepcopy(data['cases'][key])
    case['files']={f['path']:base64.b64decode(data['blobs'][f['sha256']],validate=True) for f in case['prepared']['files']}
    return case

def runtime_fixture():
    return dict(runtime=dict(image_digest='sha256:'+'a'*64,architecture='arm64',python_version='3.12.11',
                worker_entrypoint='hyprn_mvp_integration.worker',policy_digest='b'*64),
                dependencies=[dict(name='openmdao',version='3.45.1',lock_path='locks/worker.lock'),dict(name='numpy',version='2.5.3',lock_path='locks/worker.lock')],
                files={'locks/worker.lock':b'openmdao==3.45.1 --hash=sha256:'+b'c'*64+b'\nnumpy==2.5.3 --hash=sha256:'+b'd'*64+b'\n',
                       'licenses/runtime.txt':b'Independent test fixture; never authorize a runtime with this fixture.'},
                licenses=['licenses/runtime.txt'])


def current_fixture(kind='chain', multiplier=2, downstream=None):
    """Current native execution uses the actual current producer capture, never relabeled bytes."""
    case = fixture(kind, multiplier, downstream, current=True)
    if (case['prepared']['schema_version'], case['prepared']['result_protocol_version']) != (
        '3',
        '2',
    ):
        raise ValueError('Recapture native programs with the current pinned producer')
    return case
