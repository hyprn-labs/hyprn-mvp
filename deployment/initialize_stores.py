"""Explicit one-time initialization of empty development stores from retained approved images.

This is not a reset command. A nonempty store is refused. Stage artifacts before changing
container names; retain stopped missing-store containers for audit. The stores are the
application and modeling stores below HYPRN_MVP_DATA_ROOT (deployment/local_paths.py); the
published application port is HYPRN_MVP_PORT. Bootstrap refuses while either is unset.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import application_runtime as app
import modeling_runtime as model
import local_paths

# The application and modeling stores this command initializes (None while unset).
STORES = None if app.ROOT is None or model.DEFAULT_ROOT is None else (app.ROOT, model.DEFAULT_ROOT)
APP_IMAGE = 'sha256:8671fbacc59a131f3fc911362531e059958fe35df33562458e85a00ebf3dd7d8'
MODEL_IMAGE = 'sha256:1a4dbe016c1bab9b7d8913691a1567ac854d34083b2413d2fbfdb02b4d8ee7aa'
UI_HASHES = {
    'assets/index-B2a5kozk.css': '5bcaae450ad5a489c9e724abb4bedbe61650a1abcb9c3b172a6fdefec59d0efb',
    'assets/index-Dks7YEbw.js': '7212922f93ae11a2dad2beaa218dfa102cf1cd3f3691bf67c097cf6eee254f50',
    'index.html': '4b98e59fe14a20eb1618c5f181b59995ec9fd66668cb70d1cce2a5beeeed7ee9',
    'THIRD_PARTY_NOTICES.txt': '759f02b5afb6ca84446d9c811992e8a7709c4a9a145aad5544e84959a2aacfa0',
}
EVIDENCE = None if app.ROOT is None else app.ROOT / 'evidence' / 'initialization'


def emit(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def run(*args, input=None):
    return subprocess.run(args, input=input, text=True, capture_output=True, check=True).stdout.strip()


def guarded_empty_root(path):
    if path not in (STORES or ()) or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Exact nonsymlink store required')
    if path.exists() and any(path.iterdir()):
        raise ValueError('Store already has contents; refuse reset, inspect checkpoint')


def verify_image_sources():
    script = """import base64,hashlib,json
from pathlib import Path
out={}
for folder in ('application/src','contracts/schemas'):
 for p in Path('/app',folder).rglob('*'):
  if p.is_file() and '__pycache__' not in str(p):out[str(p.relative_to('/app'))]=hashlib.sha256(p.read_bytes()).hexdigest()
ui={str(p.relative_to('/app/ui')):base64.b64encode(p.read_bytes()).decode() for p in Path('/app/ui').rglob('*') if p.is_file()}
print(json.dumps({'source':out,'ui':ui}))
"""
    output = json.loads(run('docker','run','--rm','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges',APP_IMAGE,'python','-B','-c',script))
    expected = {str(p.relative_to(app.REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('application/src','contracts/schemas') for p in (app.REPO/folder).rglob('*')
        if p.is_file() and '__pycache__' not in str(p)}
    if output['source'] != expected:
        raise ValueError('Retained application image source mismatch')
    ui = {p:base64.b64decode(raw) for p,raw in output['ui'].items()}
    if {p:hashlib.sha256(raw).hexdigest() for p,raw in ui.items()} != UI_HASHES:
        raise ValueError('Approved Foundry assets mismatch')
    # Native source remains in its existing compliance scope. Verify all retained patches.
    script = "require 'json'; require 'digest'; puts Dir['/usr/share/hyprn-mvp-modeling-source/patches/*.patch'].to_h {|p| [File.basename(p),Digest::SHA256.file(p).hexdigest]}.to_json"
    patches = json.loads(run('docker','run','--rm','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges','--entrypoint','ruby',MODEL_IMAGE,'-e',script))
    if patches != {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (app.REPO/'upstream/whatsopt-patches').glob('*.patch')}:
        raise ValueError('Native patch provenance mismatch')
    return output['source'], ui, patches


def archive_missing_container(name, image, owner):
    info = model.inspect(name)
    if not info:
        return
    if info['Image'] != image or info['State']['Running'] or info['Config']['Labels'].get(model.LABEL) != owner:
        raise ValueError('Unexpected existing container; refuse replacement')
    if any(Path(m['Source']).exists() for m in info['Mounts'] if m['Type']=='bind'):
        raise ValueError('Existing container has retained files; refuse fresh replacement')
    # Do not record environment values. New name is unique; no removal.
    archived = name + '-missing-' + secrets.token_hex(4)
    emit(EVIDENCE/(name+'-before.json'),dict(id=info['Id'],image=info['Image'],mounts=info['Mounts'],state=info['State'],archived_name=archived))
    run('docker','rename',name,archived)


def bootstrap():
    port = local_paths.port()  # Refused before any effect while HYPRN_MVP_PORT is unset.
    for root in STORES:
        guarded_empty_root(root)
    sources, ui, patches = verify_image_sources()
    stores = [(app.ROOT, ('application', 'credentials', 'evidence')),
              (model.DEFAULT_ROOT, ('modeling', 'credentials', 'evidence'))]
    for root, children in stores:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        for child in children:(root/child).mkdir(mode=0o700)
    EVIDENCE.mkdir(mode=0o700)
    emit(EVIDENCE/'approval.json',dict(authorization='Owner: initialize empty development stores',app_image=APP_IMAGE,model_image=MODEL_IMAGE,source_hashes=sources,ui_hashes=UI_HASHES,native_patches=patches))
    app.UI_DIST.mkdir(parents=True,mode=0o700)
    for name,raw in ui.items():
        path=app.UI_DIST/name;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    for name in ('model.key','rails.key'):
        path=model.DEFAULT_ROOT/'credentials'/name
        with path.open('x') as stream:stream.write(secrets.token_hex(64))
        path.chmod(0o444)
    password=secrets.token_urlsafe(32)
    path=app.ROOT/'credentials/owner.password'
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(password+'\n')
    # Network identity must be reviewed before reusing a name.
    for name,owner,internal in [(model.NETWORK,model.OWNER,True),(app.PUBLIC_NETWORK,app.OWNER,False)]:
        net=model.inspect(name,'network')
        if net is not None:
            if net.get('Labels',{}).get(model.LABEL)!=owner or net['Internal']!=internal:
                raise ValueError('Existing network boundary differs')
        else:
            run('docker','network','create','--label',model.LABEL+'='+owner,*(['--internal'] if internal else []),name)
    archive_missing_container(model.CONTAINER,MODEL_IMAGE,model.OWNER)
    archive_missing_container(app.NAME,APP_IMAGE,app.OWNER)
    (model.DEFAULT_ROOT/'modeling').chmod(0o777)
    emit(model.DEFAULT_ROOT/'identity.json',dict(owner=model.OWNER,container=model.CONTAINER,network=model.NETWORK,image=MODEL_IMAGE,source_image=model.source_image(),source_hashes=model.source_hashes(),runtime=str(model.DEFAULT_ROOT),recovery='verified retained image; host runtime path relocation only'))
    run('docker','run','-d','--name',model.CONTAINER,'--label',model.LABEL+'='+model.OWNER,
        '--user','10001:10001','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
        '--memory=768m','--cpus=1','--pids-limit=128','--restart=no','--network',model.NETWORK,
        '--tmpfs','/tmp:rw,noexec,nosuid,size=192m,mode=1777','--tmpfs','/native/tmp:rw,noexec,nosuid,size=32m,uid=10001,gid=10001',
        '--mount',f'type=bind,src={model.DEFAULT_ROOT}/modeling,dst=/store',
        '--mount',f'type=bind,src={model.DEFAULT_ROOT}/credentials/model.key,dst=/run/model.key,readonly',
        '--mount',f'type=bind,src={model.DEFAULT_ROOT}/credentials/rails.key,dst=/run/rails.key,readonly',MODEL_IMAGE)
    bootstrap="import sys,os; from hyprn_mvp_app.store import Store; from hyprn_mvp_app.auth import Auth; s=Store('/store/application.sqlite'); Auth(s,'').provision('owner',sys.stdin.read().strip()); os.chown('/store/application.sqlite',10002,10002); os.chown('/store',10002,10002)"
    run('docker','run','--rm','-i','--network=none','--user','0:0','--mount',f'type=bind,src={app.ROOT}/application,dst=/store',APP_IMAGE,'python','-B','-c',bootstrap,input=password)
    run('docker','run','-d','--name',app.NAME,'--label',model.LABEL+'='+app.OWNER,
        '--user','10002:10002','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
        '--memory=512m','--cpus=1','--pids-limit=64','--restart=no','--network',app.PUBLIC_NETWORK,
        '-p',f'127.0.0.1:{port}:8000','--tmpfs','/tmp:rw,noexec,nosuid,size=16m',
        '--mount',f'type=bind,src={app.ROOT}/application,dst=/store',
        '--mount',f'type=bind,src={model.DEFAULT_ROOT}/credentials/model.key,dst=/run/model.key,readonly',
        '-e','HYPRN_MVP_APP_STORE=/store/application.sqlite','-e',f'HYPRN_MVP_ORIGIN=http://127.0.0.1:{port}',
        '-e',f'HYPRN_MVP_MODEL_URL=http://{model.CONTAINER}:3000/modeling/1','-e','HYPRN_MVP_MODEL_KEY_FILE=/run/model.key',APP_IMAGE)
    run('docker','network','connect',model.NETWORK,app.NAME)
    emit(app.ROOT / 'identity.json', dict(
        owner=app.OWNER, container=app.NAME, image=APP_IMAGE, source_hashes=app.hashes(),
        store=str(app.ROOT / 'application'),
        recovery='verified retained image; host runtime path relocation only',
    ))
    emit(EVIDENCE/'bootstrap.json',dict(application=app.check(),modeling=model.check(model.DEFAULT_ROOT)))
    print('Fresh application/modeling stores provisioned; native environment and attestation pending.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['bootstrap'])
    parser.parse_args()
    local_paths.require(STORES)
    bootstrap()
