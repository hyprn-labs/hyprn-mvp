"""Build and attest the restricted worker image; no profile or service is changed.

The execution store is <data root>/execution (HYPRN_MVP_DATA_ROOT, else the installation
configuration named by HYPRN_MVP_CONFIG). The engine builds from reviewed source and lock
bytes; HYPRN_MVP_ENGINE_IMAGE is only the retained comparison reference. The runtime
owner, the container engine endpoint and the digest of the execution configuration recorded in
runtime.json come from the attested launcher, which reads the same installation.
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
ENGINE=local_paths.engine_image(required=False)

def launcher():
    """The attested launcher of this checkout (owner, engine endpoint, configuration digest)."""
    for source in (str(REPO/'application/src'),str(REPO/'integration/src')):
        if source not in sys.path:sys.path.insert(0,source)
    from hyprn_mvp_integration import launcher as module
    return module

def run(*args):return subprocess.run(args,text=True,capture_output=True,check=True,env=launcher().docker_environment()).stdout.strip()
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

def engine_inputs():
    pins = json.loads((REPO / 'deployment/pins.json').read_bytes())
    paths = [
        'deployment/images/engine.Dockerfile', 'deployment/images/install_python.py',
        'deployment/images/build_engine.py', 'deployment/locks/tools.json',
        'deployment/locks/engine-sources.json', 'deployment/locks/build-backend.json',
        'integration/worker-requirements.lock',
    ]
    paths += sorted(str(p.relative_to(REPO)) for p in (
        REPO / 'upstream/engine-packaging'
    ).glob('*.patch'))
    return dict(base=pins['base_image'], files={name: sha(REPO / name) for name in paths})


def build_engine(root, *, no_cache=False):
    """Record an engine built from reviewed sources; a retained image is never a build input."""
    inputs = engine_inputs()
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    tag = 'hyprn-mvp-engine:' + digest[:16]
    evidence = root / 'evidence'
    evidence.mkdir(exist_ok=True)
    label = 'org.hyprn-mvp.engine-inputs'
    if not no_cache:
        inspected = subprocess.run(
            ['docker', 'image', 'inspect', tag], text=True, capture_output=True,
            env=local_paths.docker_environment(),
        )
        if inspected.returncode == 0:
            existing = json.loads(inspected.stdout)[0]
            if (existing['Config'].get('Labels') or {}).get(label) == digest:
                identity = dict(image=existing['Id'], inputs=inputs, inputs_sha256=digest)
                (evidence / 'engine-build.json').write_text(json.dumps(identity, indent=2) + '\n')
                return identity
    with tempfile.TemporaryDirectory(prefix='engine-build-', dir=root) as temporary:
        context = Path(temporary)
        for name in inputs['files']:
            target = context / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
            target.chmod(0o444)
        for path in (context, *context.rglob('*')):
            if path.is_dir():
                path.chmod(0o755)
        if {name: sha(context / name) for name in inputs['files']} != inputs['files']:
            raise ValueError('Engine source changed while staging')
        command = [
            'docker', 'build', '--pull=false', *(['--no-cache'] if no_cache else []),
            '--label', label + '=' + digest,
            '--build-arg', 'PYTHON_IMAGE=' + inputs['base'],
            '-f', str(context / 'deployment/images/engine.Dockerfile'), '-t', tag, str(context),
        ]
        environment = local_paths.docker_environment()
        if environment is None:
            import os
            environment = dict(os.environ)
        result = subprocess.run(command, text=True, capture_output=True,
                                env=dict(environment, DOCKER_BUILDKIT='1'))
        (evidence / 'engine-build.log').write_text(result.stdout + result.stderr)
        result.check_returncode()
    if engine_inputs() != inputs:
        raise ValueError('Engine source changed during build')
    image = subprocess.check_output(
        ['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'],
        text=True, env=local_paths.docker_environment(),
    ).strip()
    subprocess.run(
        ['docker', 'tag', image, 'hyprn-mvp-engine:built-' + image.removeprefix('sha256:')],
        check=True, env=local_paths.docker_environment(),
    )
    identity = dict(image=image, inputs=inputs, inputs_sha256=digest)
    (evidence / 'engine-build.json').write_text(json.dumps(identity, indent=2) + '\n')
    return identity


def build_worker(*, root=None, engine=None, no_cache=False):
    isolated=root is not None
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
    if ((engine is not None and pins['worker_image'] != engine)
            or sha(lock) != pins['worker_lock_sha256']):
        raise ValueError('Reviewed numerical dependency identity changed')
    engine_build = build_engine(root, no_cache=no_cache)
    engine = engine_build['image']
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
        for source,name in [(worker,'worker.py'),(worker.with_name('results.py'),'results.py'),(worker.with_name('__init__.py'),'__init__.py'),(REPO/'deployment/worker.Dockerfile','Dockerfile')]:
            shutil.copyfile(source,temp/name)
            # COPY keeps the context mode: the unprivileged worker user must read the sources
            # whatever the builder's umask (the entry point runs with umask 077).
            (temp/name).chmod(0o444)
        with base_reference(engine) as reference:
            result=subprocess.run(['docker','build','--network=none','--pull=false',
                                   *(['--no-cache'] if no_cache else []), *labels, *build_args,
                                   '--build-arg','ENGINE_IMAGE='+reference,'-t',worker_tag,str(temp)],text=True,capture_output=True,
                                  env=launcher().docker_environment())
        log_path=root/'evidence/worker-build.log'
        if log_path.exists():(root/'evidence'/('worker-build-'+sha(log_path)+'.log')).write_bytes(log_path.read_bytes())
        log_path.write_text(result.stdout+'\n'+result.stderr)
        result.check_returncode()
    image=run('docker','image','inspect',worker_tag,'--format','{{.Id}}')
    run('docker', 'tag', image, 'hyprn-mvp-worker:built-' + image.removeprefix('sha256:'))
    python_version = run(
        'docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', engine, 'python', '-I', '-B', '-c',
        'import platform; print(platform.python_version())',
    )
    expected_python = json.loads((REPO / 'deployment/locks/tools.json').read_bytes())['cpython_version']
    if python_version != expected_python:
        raise ValueError('Built engine interpreter differs from the approved pin')
    if execution_source_hashes()!=source_hashes:
        raise RuntimeError('Execution source changed during worker build; qualification refused')
    # The worker image extends exactly the verified engine image.
    layers=json.loads(run('docker','image','inspect',image))[0]['RootFS']['Layers']
    if layers[:len(base['RootFS']['Layers'])]!=base['RootFS']['Layers']:
        raise RuntimeError('Worker image does not derive from the reviewed engine image')
    runtime=dict(source_hashes=source_hashes,owner=root.name if isolated else launcher().OWNER,root=str(root),
                 execution_configuration_sha256=launcher().execution_configuration_sha256(root=root),
                 worker_image=image,engine_image=engine,architecture=base['Architecture'],
                 python_version=python_version,worker_sha256=sha(worker),results_sha256=sha(worker.with_name('results.py')),worker_lock_sha256=sha(lock),recipe_sha256=sha(REPO/'deployment/worker.Dockerfile'))
    runtime['engine_build'] = engine_build
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
