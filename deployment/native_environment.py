"""Copy reviewed installed dependency bytes into a clean execution environment.

Reads only distribution artifacts in the historical environment, never profiles,
stores, jobs or service source. No package resolution, download or installation.
Every copied RECORD hash is checked; a full resolved content lock and license
inventory accompany every numerical bundle.

Every location comes from deployment/local_paths.py; the commands refuse while it is
unset.
"""
import base64
import csv
import hashlib
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4
import local_paths
# packaging is imported only by prepare(): the launch-worker gate stays stdlib-only so the
# executor and activation managers can import it.

REPO=Path(__file__).resolve().parents[1]
ROOT=local_paths.execution_root(required=False)
REVIEWED=local_paths.native_inventory(required=False)
PYTHON=local_paths.native_python(required=False)
PROFILE='hyprn-mvp'
# Installed dependency bytes are read from the two development interpreters' environments; the
# reviewed AiiDA wheel comes from a retired runtime that the neutral layout does not hold, so
# prepare() refuses before any read while PRIOR is None.
PRIOR=local_paths.old_runtime_root(required=False)
CONTRACT_PYTHON=local_paths.contract_python(required=False)
SITES=None if PYTHON is None or CONTRACT_PYTHON is None else [
      Path(PYTHON).parents[1]/'lib/python3.12/site-packages',Path(CONTRACT_PYTHON).parents[1]/'lib/python3.12/site-packages']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def emit(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')

# Selected-release binding of this process (set by the __main__ entrypoint only).
BINDING=None

def launch_worker_text(root,binding,python=PYTHON):
    """Launcher wrapper that re-binds through the exact retained release bootstrap.

    An interpreter's startup path hook may name another checkout, so
    `-m hyprn_mvp_integration.launcher` could import ambient source. The bootstrap
    validates the manifest digest, removes those paths and refuses mixed bindings.
    """
    if binding is None or not binding.bound:raise ValueError('Selected release binding required for launch-worker')
    python=local_paths.require(python)
    return ('#!/bin/sh\nexport AIIDA_PATH='+shlex.quote(str(Path(root)/'aiida'))+'\nexec '+shlex.quote(str(python))+' -B '
            +shlex.quote(str(binding.source/'deployment/release_binding.py'))+' exec-module --expected-sha256 '
            +binding.manifest_sha256+' hyprn_mvp_integration.launcher -- "$@"\n')

def write_launch_worker(root,binding):
    """Write the release wrapper through an exclusive, never-followed temporary in root,
    then atomically replace launch-worker. A planted symlink or leftover name is refused."""
    root=Path(root)
    if any(p.is_symlink() for p in (root,root/'launch-worker')):raise ValueError('Unsafe launch-worker path')
    text=launch_worker_text(root,binding).encode()
    temporary=root/('.launch-worker-'+uuid4().hex)
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700)
    try:
        with os.fdopen(fd,'wb') as output:
            output.write(text);os.fchmod(output.fileno(),0o700)
        os.replace(temporary,root/'launch-worker')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return text

# An execution root holding a native profile/store or executor state is populated; prepare
# and extend would overwrite its launch-worker, selected.json, runtime.json and locks.
POPULATED_MARKERS=('aiida','aiida-store','profile-identity.json','executor.json','executor.lock','evidence/release-binding')

def refuse_populated(root):
    present=[name for name in POPULATED_MARKERS if (Path(root)/name).exists() or (Path(root)/name).is_symlink()]
    if present:raise ValueError('Refusing prepare/extend of a populated execution root ('+', '.join(present)
                                +'); use the reviewed bind-launch-worker step instead')

def bind_launch_worker(root,binding):
    """Replace only the launch-worker wrapper, retaining its previous bytes as evidence.

    Accepts the reviewed legacy wrapper or an earlier release wrapper for this root;
    anything else is refused unchanged. No profile, store, process or job is touched.
    """
    root=Path(root)
    wrapper=root/'launch-worker'
    if any(p.is_symlink() for p in (root,wrapper,root/'evidence')):raise ValueError('Unsafe launch-worker path')
    previous=wrapper.read_bytes()
    local_paths.require(PYTHON)
    legacy=('#!/bin/sh\nexport AIIDA_PATH='+shlex.quote(str(root/'aiida'))+'\nexec '+shlex.quote(str(PYTHON))+' -B -m hyprn_mvp_integration.launcher "$@"\n').encode()
    released=re.fullmatch(rb'#!/bin/sh\nexport AIIDA_PATH='+re.escape(shlex.quote(str(root/'aiida')).encode())+rb'\nexec '
        +re.escape(shlex.quote(str(PYTHON)).encode())+rb" -B (?:'[^'\n]+/source/deployment/release_binding\.py'|[^\s'\"]+/source/deployment/release_binding\.py) exec-module --expected-sha256 [0-9a-f]{64} hyprn_mvp_integration\.launcher -- \"\$@\"\n",previous)
    if previous!=legacy and not released:raise ValueError('Unexpected existing launch-worker; refusing replacement')
    retained=root/'evidence'/('launch-worker-'+sha(previous)+'.sh')
    if retained.exists():
        if retained.read_bytes()!=previous:raise ValueError('Retained launch-worker evidence differs; refusing replacement')
    else:
        with retained.open('xb') as output:output.write(previous)
    text=write_launch_worker(root,binding)
    if wrapper.read_bytes()!=text:raise ValueError('launch-worker replacement not observed')
    record=dict(previous_sha256=sha(previous),current_sha256=sha(text),release_id=binding.release_id,
                manifest_sha256=binding.manifest_sha256,source_root=str(binding.source),
                retained_previous=str(retained),bound_at=datetime.now(timezone.utc).isoformat())
    # Create-only, uniquely named evidence (never overwrites an earlier binding record).
    evidence=root/'evidence'/('launch-worker-binding-'+uuid4().hex+'.json')
    with evidence.open('x') as output:output.write(json.dumps(record,sort_keys=True,indent=2)+'\n')
    return dict(record,evidence=str(evidence))

def require_launch_worker(root,binding):
    """Refuse unless launch-worker is exactly this release's wrapper.

    The reviewed legacy wrapper runs `-m hyprn_mvp_integration.launcher`, which may resolve to
    another checkout through an interpreter's startup path hook; an earlier release's
    wrapper names another manifest. Either would execute source other than this release.
    """
    if binding is None or not binding.bound:raise ValueError('Selected release binding required for launch-worker')
    root=Path(root);wrapper=root/'launch-worker'
    if any(p.is_symlink() for p in (root,wrapper)):raise ValueError('Unsafe launch-worker path')
    try:actual=wrapper.read_bytes()
    except FileNotFoundError:raise ValueError('launch-worker missing; run the reviewed bind-launch-worker step') from None
    if actual!=launch_worker_text(root,binding).encode():
        raise ValueError('launch-worker is not bound to release '+str(binding.release_id)+' (sha256 '+sha(actual)[:16]
                         +'); stop, back up, then run the reviewed bind-launch-worker step of this release')
    return dict(path=str(wrapper),sha256=sha(actual),release_id=binding.release_id,manifest_sha256=binding.manifest_sha256)

def bind_step(root,binding):
    """Reviewed rebinding step: executor stopped, wrapper rebound, result re-verified.

    The stop is proven by the shared fail-closed quiescence gate (parsable executor.json,
    no live executor, executor.lock not held), not by executor.json alone."""
    import dispatch_runtime
    dispatch_runtime.executor_quiescence(root)
    record=bind_launch_worker(root,binding)
    require_launch_worker(root,binding)
    return record

def launcher_evidence(root,binding):
    """Post-activation check: the first launch through launch-worker proved this release."""
    directory=Path(root)/'evidence/release-binding'
    if directory.is_symlink():raise ValueError('Unsafe launcher evidence directory')
    ours,others=[],0
    for path in sorted(directory.glob('launcher-binding-*.json')) if directory.is_dir() else []:
        record=json.loads(path.read_text())
        if (record.get('release_id'),record.get('manifest_sha256'),record.get('source_root'))!=(
                binding.release_id,binding.manifest_sha256,str(binding.source)):
            others+=1;continue
        module=record['modules']['hyprn_mvp_integration.launcher']
        launcher=Path(module['file'])
        if not launcher.is_relative_to(binding.source):raise ValueError('Launcher evidence names source outside the release')
        # The launched module bytes must be this release's manifest entry, not only its path.
        expected=binding.inventory.get('integration/src/hyprn_mvp_integration/launcher.py')
        if expected is None or module.get('sha256')!=expected:
            raise ValueError('Launcher evidence sha256 differs from the release manifest: '+path.name)
        ours.append(str(path))
    if not ours:raise ValueError('No launcher-binding evidence for release '+str(binding.release_id)+' yet; run one launch, then recheck')
    return dict(release_id=binding.release_id,records=ours,other_releases=others)

def reviewed_selection(source):
    source=Path(source)
    selected=json.loads((source/'selected.json').read_bytes())
    for item in selected['files']:
        relative=Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in ('locks','licenses'):
            raise ValueError('Reviewed selection path refused')
        path=source/relative
        if any(p.is_symlink() for p in (path,*path.parents)):
            raise ValueError('Reviewed selection symlink refused')
        raw=path.read_bytes()
        if len(raw)!=item['size'] or sha(raw)!=item['sha256']:
            raise ValueError('Reviewed selection bytes changed')
    return selected

def reuse_reviewed():
    """Reuse only fixed audited interpreter/lock/license bytes; no old data."""
    if (ROOT/'selected.json').exists() or (ROOT/'aiida').exists():
        raise ValueError('Refusing existing selected runtime or native profile')
    selection=reviewed_selection(REVIEWED)
    previous=json.loads((REVIEWED/'runtime.json').read_bytes())
    runtime=json.loads((ROOT/'runtime.json').read_bytes())
    if (previous['selected_sha256']!=sha((REVIEWED/'selected.json').read_bytes())
            or runtime['engine_image']!=previous['engine_image']
            or runtime['worker_lock_sha256']!=previous['worker_lock_sha256']):
        raise ValueError('Reviewed runtime dependency identity changed')
    site=Path(local_paths.require(PYTHON,local_paths.NATIVE_PYTHON)).parents[1]/'lib/python3.12/site-packages'
    for dist in json.loads((REVIEWED/'locks/native-installed.json').read_bytes()):
        for item in dist['files']:
            raw=(site/item['path']).read_bytes()
            if sha(raw)!=item['sha256'] or len(raw)!=item['size']:
                raise ValueError('Reviewed native dependency bytes changed')
    for item in selection['files']:
        target=ROOT/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
        raw=(REVIEWED/item['path']).read_bytes()
        if target.exists() and target.read_bytes()!=raw:raise ValueError('New dependency selection mismatch')
        target.write_bytes(raw)
    (ROOT/'selected.json').write_bytes((REVIEWED/'selected.json').read_bytes())
    runtime['selected_sha256']=sha((ROOT/'selected.json').read_bytes());emit(ROOT/'runtime.json',runtime)
    write_launch_worker(ROOT,BINDING)
    emit(ROOT/'evidence/dependency-reuse.json',dict(interpreter=str(PYTHON),source=str(REVIEWED),selected_sha256=runtime['selected_sha256'],copied_scientific_records=False))

def prepare(extend=False):
    refuse_populated(ROOT)  # before any import, read or write
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    if (ROOT/'venv').exists() and not extend:raise ValueError('New environment already exists; refuse replacement')
    if PRIOR is None:raise ValueError('No retired runtime holds the reviewed AiiDA wheel; prepare is unavailable')
    wheel=PRIOR/'downloads/aiida_core-2.9.3-py3-none-any.whl'
    pins=json.loads((REPO/'deployment/pins.json').read_bytes())
    if sha(wheel.read_bytes())!=pins['verified_artifacts']['aiida-core'][0]['sha256']:
        raise ValueError('Reviewed AiiDA artifact changed')
    distributions={}
    for site in SITES:
        for dist in metadata.distributions(path=[str(site)]):
            distributions.setdefault(canonicalize_name(dist.metadata['Name']),dist)
    selected={};visited=set()
    def visit(name,extras=()):
        name=canonicalize_name(name)
        key=(name,tuple(sorted(extras)))
        if key in visited:return
        visited.add(key)
        dist=distributions[name];selected[name]=dist
        for requirement in dist.requires or []:
            req=Requirement(requirement)
            if req.marker and not any(req.marker.evaluate({'extra':extra}) for extra in ('',*extras)):continue
            if distributions[canonicalize_name(req.name)].version not in req.specifier:raise ValueError('Dependency constraint mismatch')
            visit(req.name,req.extras)
    for name in ('aiida-core','pytest','rfc8785','jsonschema','httpx'):visit(name)
    inventory=[];copy_files=[];license_files={}
    for name,dist in sorted(selected.items()):
        records=[]
        for entry in dist.files or []:
            rel=str(entry)
            # Console wrappers are not used; bytecode and installed RECORD itself
            # are generated artifacts, not imported package source.
            if rel.startswith('../') or rel.endswith('.pyc') or rel.endswith('/RECORD'):continue
            if entry.hash is None:raise ValueError('Unhashed dependency artifact: '+rel)
            raw=Path(dist.locate_file(entry)).read_bytes()
            actual=base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
            if entry.hash.mode!='sha256' or actual!=entry.hash.value:raise ValueError('Installed artifact mismatch: '+rel)
            records.append(dict(path=rel,sha256=sha(raw),size=len(raw)))
            copy_files.append((rel,raw))
            if '.dist-info/' in rel and (Path(rel).name=='METADATA' or any(x in rel.lower() for x in ('license','copying','notice'))):
                license_files['licenses/native/'+rel]=raw
        inventory.append(dict(name=name,version=dist.version,origin=dist.metadata.get_all('Project-URL') or [],
            license=dist.metadata.get('License-Expression') or dist.metadata.get('License') or dist.metadata.get_all('Classifier'),files=records))
    # Provenance validation is complete before copying package files.
    # The native development interpreter creates the environment from its own base interpreter.
    if not extend:subprocess.run([str(local_paths.require(PYTHON,local_paths.NATIVE_PYTHON)),'-m','venv','--without-pip',str(ROOT/'venv')],check=True)
    destination=ROOT/'venv/lib/python3.12/site-packages'
    for rel,raw in copy_files:
        target=destination/rel
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Refusing changed deployed dependency bytes')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    # Authored entry points only. No historical editable package or startup .pth.
    plugin=destination/'hyprn_mvp_integration-0.1.0.dist-info';plugin.mkdir(exist_ok=extend)
    (plugin/'METADATA').write_text('Metadata-Version: 2.1\nName: hyprn-mvp-integration\nVersion: 0.1.0\n')
    (plugin/'entry_points.txt').write_text('[aiida.calculations]\nhyprn_mvp.scalar = hyprn_mvp_integration.calculation:ScalarCalculation\n\n[aiida.parsers]\nhyprn_mvp.scalar = hyprn_mvp_integration.calculation:ScalarParser\n')
    emit(ROOT/'locks/native-installed.json',inventory)
    for rel,raw in license_files.items():
        target=ROOT/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    # Read actual worker distribution metadata/license bytes in the verified
    # numerical image with network disabled. This imports no candidate code.
    runtime=json.loads((ROOT/'runtime.json').read_bytes())
    script="""import base64,importlib.metadata as m,json
out=[]
for d in m.distributions():
 files={}
 for f in d.files or []:
  s=str(f)
  if '.dist-info/' in s and (s.endswith('/METADATA') or any(x in s.lower() for x in ('license','copying','notice'))):files[s]=base64.b64encode(d.locate_file(f).read_bytes()).decode()
 out.append({'name':d.metadata['Name'],'version':d.version,'files':files})
print(json.dumps(out))
"""
    output=subprocess.run(['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',runtime['worker_image'],'python','-B','-c',script],capture_output=True,text=True,check=True).stdout
    workers=json.loads(output)
    for dist in workers:
        for rel,encoded in dist.pop('files').items():
            path=ROOT/'licenses/worker'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(encoded))
    emit(ROOT/'locks/worker-installed.json',workers)
    dependencies=[dict(name=d['name'],version=d['version'],lock_path='locks/native-installed.json') for d in inventory]
    dependencies += [dict(name=d['name'],version=d['version'],lock_path='locks/worker-installed.json') for d in workers]
    descriptors=[]
    for top in ('locks','licenses'):
        for path in sorted((ROOT/top).rglob('*')):
            if path.is_file():descriptors.append(dict(path=str(path.relative_to(ROOT)),size=path.stat().st_size,sha256=sha(path.read_bytes())))
    emit(ROOT/'selected.json',dict(dependencies=dependencies,files=descriptors,licenses=[d['path'] for d in descriptors if d['path'].startswith('licenses/')]))
    runtime['selected_sha256']=sha((ROOT/'selected.json').read_bytes())
    emit(ROOT/'runtime.json',runtime)
    # The same wrapper (reviewed interpreter) that require_launch_worker accepts.
    write_launch_worker(ROOT,BINDING)
    print(json.dumps(dict(native_distributions=len(inventory),worker_distributions=len(workers),selected_sha256=runtime['selected_sha256'])))

def initialize():
    expected=str(ROOT/'aiida')
    if os.environ.get('AIIDA_PATH')!=expected:raise ValueError('Explicit new profile path required')
    import aiida
    from aiida import orm
    from aiida.manage.configuration import get_config,create_profile
    config=get_config(create=True)
    if config.profile_names:raise ValueError('Refusing to initialize existing profile')
    create_profile(config,name=PROFILE,email='owner@hyprn-mvp.invalid',
        storage_backend='core.sqlite_dos',storage_config={'filepath':str(ROOT/'aiida-store')},
        broker_backend=None,broker_config={})
    config.store()
    if config.default_profile_name is not None:raise ValueError('Default profile is forbidden')
    aiida.load_profile(PROFILE)
    computer=orm.Computer(label='hyprn-mvp-local',hostname='localhost',transport_type='core.local',
        scheduler_type='core.direct',workdir=str(ROOT/'aiida-work/{username}')).store()
    computer.configure(safe_interval=0.1)
    code=orm.InstalledCode(label='hyprn-mvp-scalar',computer=computer,filepath_executable=str(ROOT/'launch-worker'),default_calc_job_plugin='hyprn_mvp.scalar').store()
    from aiida.manage import get_manager
    emit(ROOT/'profile-identity.json',dict(profile_uuid=config.get_profile(PROFILE).uuid,
        repository_uuid=get_manager().get_profile_storage().get_repository().uuid,
        computer_uuid=computer.uuid,code_uuid=code.uuid,profile=PROFILE))
    print('Fresh isolated profile initialized without broker or daemon')

def evidence():
    from aiida import orm
    from hyprn_mvp_integration.calculation import NativeExecution
    native=NativeExecution.from_environment()
    records=[]
    for (node,) in orm.QueryBuilder().append(orm.CalcJobNode,filters={'process_type':'aiida.calculations:hyprn_mvp.scalar'},project='*').all():
        bundle=native.retained_bundle(node.uuid)
        request=node.inputs.request.get_dict()
        records.append(dict(request=request,record=native.inspect(node.uuid),
            model_revision_id=bundle['manifest']['model_revision_id'],configuration_revision_id=bundle['manifest']['configuration_revision_id'],
            file_count=len(bundle['files']),retained_manifest_digest=bundle['manifest']['bundle_digest'],
            retained_exact_match=native.matches(request)==[node.uuid]))
    emit(ROOT/'evidence/native-records.json',dict(profile=PROFILE,store_uuid=native.store_uuid,records=records))
    print(json.dumps(dict(records=len(records),unique_matches=all(r['retained_exact_match'] for r in records))))

if __name__=='__main__':
    import release_binding
    # check-* are read-only; every other operation has effects. None may run from an
    # unselected checkout (the expected wrapper names the selected release).
    read_only=sys.argv[1:] in (['check-launch-worker'],['check-launcher-evidence'])
    BINDING=release_binding.entrypoint(__file__,read_only=read_only,project_imports=True)
    local_paths.require(ROOT)
    if sys.argv[1:] == ['bind-launch-worker']:print(json.dumps(bind_step(ROOT,BINDING)))
    elif sys.argv[1:] == ['check-launch-worker']:print(json.dumps(require_launch_worker(ROOT,BINDING)))
    elif sys.argv[1:] == ['check-launcher-evidence']:print(json.dumps(launcher_evidence(ROOT,BINDING)))
    elif sys.argv[1:] == ['reuse-reviewed']:reuse_reviewed()
    elif sys.argv[1:] == ['prepare']:prepare()
    elif sys.argv[1:] == ['extend']:prepare(extend=True)
    elif sys.argv[1:] == ['initialize']:initialize()
    elif sys.argv[1:] == ['evidence']:evidence()
    else:raise ValueError('Choose prepare or initialize')
