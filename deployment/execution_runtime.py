"""Build and attest the restricted worker image; no profile or service is changed.

The execution store is HYPRN_MVP_DATA_ROOT/execution and the numerical engine base image is
HYPRN_MVP_ENGINE_IMAGE (deployment/local_paths.py); the operations refuse while either is
unset, and the build refuses an engine image that differs from the reviewed pin.
"""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import local_paths

REPO=Path(__file__).resolve().parents[1]
ROOT=local_paths.execution_root(required=False)
OWNER='hyprn-mvp-execution'
ENGINE=local_paths.engine_image(required=False)

def run(*args):return subprocess.run(args,text=True,capture_output=True,check=True).stdout.strip()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

@contextlib.contextmanager
def base_reference(image):
    """A transient tag naming the verified base image id for one build (BuildKit cannot build
    FROM a bare image id). It is removed afterwards and the base keeps its other references; a
    tag that became the base's only reference stays, so the base image is never deleted."""
    reference='hyprn-mvp-build-base:'+uuid.uuid4().hex[:16]
    run('docker','tag',image,reference)
    try:yield reference
    finally:
        tags=json.loads(run('docker','image','inspect',image))[0].get('RepoTags') or []
        if reference in tags and len(tags)>1:run('docker','image','rm','--no-prune',reference)

def build_worker(*, root=None, engine=None):
    isolated=root is not None
    engine=engine or local_paths.engine_image()
    sys.path[:0]=[str(REPO/'integration/src'),str(REPO/'application/src')]
    from hyprn_mvp_integration.launcher import fixture_runtime_root, execution_source_hashes
    if isolated:root=fixture_runtime_root(root)
    else:root=local_paths.require(ROOT)
    source_hashes=execution_source_hashes()
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):raise ValueError('Unsafe new runtime root')
    root.mkdir(mode=0o700,exist_ok=True);root.chmod(0o700)
    for name in ('evidence','locks','licenses'):(root/name).mkdir(mode=0o700,exist_ok=True)
    pins=json.loads((REPO/'deployment/pins.json').read_bytes())
    lock=REPO/'integration/worker-requirements.lock'
    if pins['worker_image']!=engine or sha(lock)!=pins['worker_lock_sha256']:
        raise ValueError('Reviewed numerical dependency identity changed')
    base=json.loads(run('docker','image','inspect',engine))[0]
    if base['Id']!=engine:raise ValueError('Dependency image identity mismatch')
    worker=REPO/'integration/src/hyprn_mvp_integration/worker.py'
    # A scoped build carries its test scope label, so each scope's image is its own and is found by it.
    labels=['--label','org.hyprn-mvp.test-scope='+root.name.removeprefix(local_paths.SCOPE_PREFIX)] if isolated else []
    build_args=['--build-arg','WORKER_SHA256='+sha(worker),'--build-arg','RESULTS_SHA256='+sha(worker.with_name('results.py'))]
    inputs=dict(engine=engine,recipe=sha(REPO/'deployment/worker.Dockerfile'),worker=sha(worker),
                results=sha(worker.with_name('results.py')),package=sha(worker.with_name('__init__.py')),labels=labels)
    # Image tags are hyprn-mvp-<role>:<first 16 hex of the build-input digest>.
    worker_tag='hyprn-mvp-worker:'+hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()[:16]
    with tempfile.TemporaryDirectory(prefix='worker-build-',dir=root) as temp:
        temp=Path(temp)
        for source,name in [(worker,'worker.py'),(worker.with_name('results.py'),'results.py'),(worker.with_name('__init__.py'),'__init__.py'),(REPO/'deployment/worker.Dockerfile','Dockerfile')]:shutil.copyfile(source,temp/name)
        with base_reference(engine) as reference:
            result=subprocess.run(['docker','build','--network=none','--pull=false',*labels,*build_args,
                                   '--build-arg','ENGINE_IMAGE='+reference,'-t',worker_tag,str(temp)],text=True,capture_output=True)
        log_path=root/'evidence/worker-build.log'
        if log_path.exists():(root/'evidence'/('worker-build-'+sha(log_path)+'.log')).write_bytes(log_path.read_bytes())
        log_path.write_text(result.stdout+'\n'+result.stderr)
        result.check_returncode()
    image=run('docker','image','inspect',worker_tag,'--format','{{.Id}}')
    python_version=next(v.split('=',1)[1] for v in base['Config']['Env'] if v.startswith('PYTHON_VERSION='))
    if execution_source_hashes()!=source_hashes:
        raise RuntimeError('Execution source changed during worker build; qualification refused')
    # The worker image extends exactly the verified engine image.
    layers=json.loads(run('docker','image','inspect',image))[0]['RootFS']['Layers']
    if layers[:len(base['RootFS']['Layers'])]!=base['RootFS']['Layers']:
        raise RuntimeError('Worker image does not derive from the reviewed engine image')
    runtime=dict(source_hashes=source_hashes,owner=root.name if isolated else OWNER,root=str(root),worker_image=image,engine_image=engine,architecture=base['Architecture'],
                 python_version=python_version,worker_sha256=sha(worker),results_sha256=sha(worker.with_name('results.py')),worker_lock_sha256=sha(lock),recipe_sha256=sha(REPO/'deployment/worker.Dockerfile'))
    path=root/'runtime.json'
    if path.exists():
        previous=json.loads(path.read_bytes())
        if 'selected_sha256' in previous:runtime['selected_sha256']=previous['selected_sha256']
    if path.exists():(root/'evidence'/('runtime-'+sha(path)+'.json')).write_bytes(path.read_bytes())
    shutil.copyfile(lock,root/'locks/worker.lock')
    path.write_text(json.dumps(runtime,indent=2)+'\n')
    return runtime

def main():
    local_paths.require(ROOT)
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['build-worker','attest','check']);args=parser.parse_args()
    sys.path[:0]=[str(REPO/'integration/src'),str(REPO/'application/src')]
    if args.operation=='build-worker':result=build_worker()
    else:
        from hyprn_mvp_integration.launcher import attest,require_attestation
        result=attest() if args.operation=='attest' else require_attestation()
        result={k:v for k,v in result.items() if k!='cases'}
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    # Every operation imports execution source; check is the only read-only one.
    import release_binding
    release_binding.entrypoint(__file__,read_only=sys.argv[1:]==['check'],project_imports=True)
    main()
