"""Linux fixture controller. All product operations use only the extracted release."""

import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import tempfile
import threading
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def forward(client, upstream):
    """Forward the actual daemon byte stream without interpreting or replacing replies."""
    with client, socket.socket(socket.AF_UNIX) as server:
        server.connect(upstream)
        with selectors.DefaultSelector() as selector:
            selector.register(client, selectors.EVENT_READ, server)
            selector.register(server, selectors.EVENT_READ, client)
            while selector.get_map():
                for key, _event in selector.select(30):
                    try:
                        raw = key.fileobj.recv(65536)
                        if raw:
                            key.data.sendall(raw)
                        else:
                            selector.unregister(key.fileobj)
                            key.data.shutdown(socket.SHUT_WR)
                    except (BrokenPipeError, ConnectionResetError):
                        # Docker closes attach streams when a bounded probe is killed.
                        return


def main():
    prefix, state = map(Path, sys.argv[1:3])
    installation = sys.argv[3]
    source = prefix / 'source'
    build = json.loads((prefix / 'build.json').read_bytes())
    python = prefix / 'native' / ('venv-' + build['native_lock_sha256'][:16]) / 'bin/python'
    # Verification runs against read-only extracted bytes, with all import side
    # effects confined to /tmp; the build cache and checkout are not mounted.
    verified = subprocess.run([str(python), '-I', '-B', str(source / 'deployment/cloud_native_bundle.py'),
                               'verify-extracted', '--prefix', str(prefix)],
                              env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/tmp'},
                              capture_output=True, text=True, timeout=180)
    if verified.returncode:
        raise RuntimeError(verified.stderr)
    os.chmod(state, 0o755)
    control, root, home = (state / name for name in ('control', 'execution', 'home'))
    control.mkdir(mode=0o755)
    for folder in (root, home):
        folder.mkdir(mode=0o700)
        os.chown(folder, 10003, 10003)
    private = control / 'native-private'
    private.mkdir(mode=0o700)
    os.chown(private, 10003, 10003)
    # UNIX socket names are bounded independently of the volume's absolute path.
    # Keep a root-owned short socket directory; never alter the shared daemon socket.
    proxy = Path(tempfile.mkdtemp(prefix='hyprn-engine-'))
    proxy.chmod(0o755)
    endpoint = proxy / 'engine.sock'
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(endpoint))
    os.chown(endpoint, 0, 10003)
    os.chmod(endpoint, 0o660)
    listener.listen(8)
    def accept():
        while True:
            try:
                client, _ = listener.accept()
            except OSError:
                return
            threading.Thread(target=forward, args=(client, '/engine.sock'), daemon=True).start()
    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    projection = dict(schema='hyprn-cloud-execution/v1', edition='cloud', installation_id=installation,
                      store_id='execution-' + installation, execution_root=str(root), host_home=str(home),
                      docker={'endpoint':'unix://' + str(endpoint)}, profile='hyprn-mvp-cloud-' + installation,
                      source=str(source), native_root=str(prefix / 'native'), python=str(python))
    projection.update(release_sha256=hashlib.sha256((prefix / 'build.json').read_bytes()).hexdigest(),
                      config_sha256=hashlib.sha256(canonical(projection)).hexdigest())
    config = private / 'execution.json'
    config.write_bytes(canonical(projection))
    config.chmod(0o600)
    os.chown(config, 10003, 10003)
    environment = {'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(home),
                   'USER':'hyprn-execution','LOGNAME':'hyprn-execution',
                   'HYPRN_MVP_CLOUD_EXECUTION_CONFIG':str(config)}
    # Exercise the actual released privileged wrapper as well as the native
    # owner. Its receipt validation and user/socket handoff are part of startup.
    sys.path.insert(0, str(source / 'deployment'))
    from cloud_lifecycle import Lifecycle, Refused
    host = Lifecycle.__new__(Lifecycle)
    host.root = control
    host.preview = {'execution': {'user': 10003}}

    def owner(operation, *, accepted=True):
        host.deadline = time.monotonic() + 180
        try:
            result = host.native(operation, configuration=projection)
        except Refused:
            if accepted:
                raise
            return None
        if not accepted:
            raise AssertionError('Native owner unexpectedly accepted ' + operation)
        return result
    try:
        first = owner('initialize')
        if owner('inspect') != first or owner('inspect') != first:
            raise ValueError('Native identities changed across fresh owner processes')
        owner('check', accepted=False)
        before = (root / 'profile-identity.json').read_bytes()
        owner('initialize', accepted=False)
        if (root / 'profile-identity.json').read_bytes() != before or owner('inspect') != first:
            raise ValueError('Refused initialization changed native identity')
        if owner('attest') != first or owner('check') != first:
            raise ValueError('Attestation changed native identity')
        script = '''import json,sys
from pathlib import Path
source=Path(sys.argv[1]);config=Path(sys.argv[2]);mode=sys.argv[3]
sys.path[:0]=[str(source/p) for p in ('deployment','application/src','integration/src','integration/tests')]
import cloud_native
configuration=cloud_native.bootstrap(config)
from hyprn_mvp_integration.calculation import NativeExecution
native=NativeExecution.from_environment()
saved=Path(configuration['execution_root'])/'saved-calculation.json'
if mode=='calculate':
    from execution_fixtures import current_fixture,uid
    from hyprn_mvp_app.execution import assemble_bundle
    from hyprn_mvp_app.store import digest
    case=current_fixture('chain')
    bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],native.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],
        command_id=uid(),payload_digest=digest({'proof':'installed-native-chain'}),
        bundle_digest=bundle['manifest']['bundle_digest'])
    record=native.launch(bundle,request)
    # Preserve actual retained outputs before asserting numerical success. This
    # fixed native read checks the immutable request/process association itself.
    retained=native.read_record(request,{k:record[k] for k in ('store_uuid','process_uuid')})
    diagnostics={'record':record,'errors':retained['errors'],
        'artifacts':{k:v.decode('utf-8',errors='replace') for k,v in retained['artifacts'].items()}}
    (Path(configuration['execution_root'])/'evidence/calculation.json').write_text(json.dumps(diagnostics))
    assert record['exit_status']==0,record
    output=next(o for o in record['results']['outputs'] if o['target']==case['targets']['square']['y'])
    assert output['value']==49 and output['availability']=='available',record
    assert native.retained_bundle(record['process_uuid'])==bundle
    saved.write_text(json.dumps({'request':request,'record':record}))
else:
    old=json.loads(saved.read_text());request=old['request'];record=native.inspect(old['record']['process_uuid'])
    assert record==old['record']
    assert len(native.matches(request))==1
    retained=native.retained_bundle(record['process_uuid'])
    try: native.launch(retained,request)
    except RuntimeError as error: assert 'cannot be launched again' in str(error)
    else: raise AssertionError('Retained request launched twice')
print(json.dumps(record))
'''
        records=[]
        for mode in ('calculate','restart-read'):
            result=subprocess.run([str(python),'-I','-B','-c',script,str(source),str(config),mode],
                env=environment,user=10003,group=10003,extra_groups=[],capture_output=True,text=True,timeout=240)
            if result.returncode:
                raise RuntimeError(mode+': '+result.stderr)
            records.append(json.loads(result.stdout))
        if records[0]!=records[1] or owner('check')!=first:
            raise ValueError('Retained result or native identity changed after restart')
        schema = subprocess.run([str(python), '-I', '-B',
            str(source / 'deployment/cloud_owner_schemas.py')], input=json.dumps(first),
            env=environment, user=10003, group=10003, extra_groups=[],
            capture_output=True, text=True, timeout=30)
        if schema.returncode:
            raise RuntimeError('Installed owner schema probe: ' + schema.stderr)
        observation = json.loads(schema.stdout)
        if observation['repository_uuid'] != first['repository_uuid']:
            raise ValueError('Installed schema probe changed repository identity')
        containment = (root / 'evidence/containment.json').read_bytes()
        runtime = json.loads((root / 'runtime.json').read_bytes())
        print(json.dumps({'status':'calculated','source_commit':build['source_commit'],
                          'worker_image':runtime['worker_image'],
                          'attestation_sha256':hashlib.sha256(containment).hexdigest(),
                          'owner':first,'attested':True,'calculation':records[0],
                          'restart_read_identical':True,'duplicate_native_request_refused':True,
                          'verified_extraction':True,'reinitialization_refused':True,
                          'unattested_check_refused':True,
                          'released_lifecycle_wrapper':True,
                          'schema_observation':observation,
                          'binding':'isolated-native-bundle'}), flush=True)
    finally:
        listener.close()


if __name__ == '__main__':
    main()
