"""Manage only the owned application container; no execution or legacy access.

The installation decides every identity (deployment/local_paths.py): the store
<data root>/application, the published port (HYPRN_MVP_PORT, else the configuration's
ports.app), the container, public network and ownership label names
(hyprn-mvp-<edition>-<id8>-<role>, labelled with the installation's owner), the container
engine endpoint of every docker command and the owner's sign-in name provisioned with a new
store. The development data root keeps its fixed names, the ambient engine and the sign-in name
"owner". The commands refuse while the store or the port is unresolved. Every file of the build
context gets an explicit mode, whatever the caller's umask.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import subprocess
import tempfile
from uuid import uuid4
import release_binding
import local_paths
import modeling_runtime

ROOT=local_paths.application_root(required=False)
REPO=Path(__file__).resolve().parents[1]
NAMES=local_paths.component_names()
NAME=NAMES["application"]
OWNER=NAMES["application_owner"]
BASE="sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
# Development application port (HYPRN_MVP_PORT); None while unset, refused by main().
PORT=local_paths.port(required=False)
PUBLIC_NETWORK=NAMES["public_network"]
# Sign-in name of the owner provisioned with a new store.
USERNAME=local_paths.owner_username()
# Environment of every docker command: the installation's engine endpoint, or None (ambient).
DOCKER_ENVIRONMENT=local_paths.docker_environment()
UI_DIST=None if ROOT is None else ROOT/"ui"
def run(*args,input=None):
    result=subprocess.run(args,input=input,text=True,capture_output=True,check=True,
                          env=DOCKER_ENVIRONMENT)
    return result.stdout.strip()
def inspect():
    result=subprocess.run(["docker","inspect",NAME],text=True,capture_output=True,
                          env=DOCKER_ENVIRONMENT)
    if result.returncode:
        if "no such" in result.stderr.lower():return None
        raise RuntimeError("Unable to inspect owned application")
    return json.loads(result.stdout)[0]
def guard(info):
    if info["Name"]!="/"+NAME or info["Config"]["Labels"].get(modeling_runtime.LABEL)!=OWNER:
        raise ValueError("Application resource is not owned")
def bound_release():
    binding=release_binding.ACTIVE
    return binding if binding is not None and binding.bound else None
def ui_dist():
    """Served UI build: the bound release's retained build/ui-dist, never the shared
    workspace dist; unbound fixture use keeps UI_DIST."""
    binding=bound_release()
    return binding.manifest_path.parent/'build/ui-dist' if binding is not None else UI_DIST
def release_manifest(binding):
    manifest=json.loads(binding.manifest_path.read_bytes())
    if (manifest.get('build') or {}).get('ui') is None:raise ValueError('Selected release has no retained UI build; it cannot be served')
    return manifest
def hashes():
    paths=[p for group in ("application/src","contracts/schemas") for p in (REPO/group).rglob("*") if p.is_file() and "__pycache__" not in str(p)]
    paths += [REPO/"application/requirements.lock",REPO/"deployment/application.Dockerfile",REPO/"deployment/application_runtime.py"]
    result={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    dist=ui_dist()
    for p in sorted(dist.rglob('*')):
        if p.is_file():result['ui-dist/'+str(p.relative_to(dist))]=hashlib.sha256(p.read_bytes()).hexdigest()
    ui_paths=[p for group in ('ui/src','ui/public') for p in (REPO/group).rglob('*')]
    ui_paths += [REPO/'ui'/name for name in ('index.html','package.json','package-lock.json','vite.config.ts','tsconfig.json')]
    for p in sorted(ui_paths):
        if p.is_file():
            result[str(p.relative_to(REPO))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result
def check(allow_source_change=False):
    info=inspect()
    if not info:raise ValueError("Application not initialized")
    guard(info)
    identity=json.loads((ROOT/"identity.json").read_text())
    if (not allow_source_change and identity["source_hashes"]!=hashes()) or info["Image"]!=identity["image"]:raise ValueError("Application source/image drift")
    binding=bound_release()
    if binding is not None and not allow_source_change:
        if not release_binding.application_inventory_matches(identity["source_hashes"],release_manifest(binding)):
            raise ValueError("Application source or served UI inventory differs from the selected release manifest")
    h=info["HostConfig"]
    if info["Config"]["User"]!="10002:10002" or not h["ReadonlyRootfs"] or h["Privileged"] or h["CapDrop"]!=["ALL"] or h["CapAdd"]:
        raise ValueError("Application isolation mismatch")
    if "no-new-privileges:true" not in h["SecurityOpt"]:raise ValueError("Privilege escalation permitted")
    if set(info["NetworkSettings"]["Networks"])!={modeling_runtime.NETWORK,PUBLIC_NETWORK}:raise ValueError("Application network mismatch")
    mounts={m["Destination"]:(m["Source"],m["RW"]) for m in info["Mounts"] if m["Type"]=="bind"}
    expected={"/store":(str(ROOT/"application"),True),"/run/model.key":(str(modeling_runtime.DEFAULT_ROOT/"credentials/model.key"),False)}
    if mounts!=expected:raise ValueError("Unexpected application mounts")
    if h["PortBindings"]!={"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":str(PORT)}]}:raise ValueError("Unexpected public bind")
    return dict(container=NAME,image=info["Image"],running=info["State"]["Running"],origin=f"http://127.0.0.1:{PORT}",store=str(ROOT/"application"))
def build_evidence_directory(parent=None):
    parent = Path(parent) if parent is not None else ROOT / "evidence/builds"
    for path in (parent, *parent.parents):
        if path.is_symlink():
            raise ValueError("Unsafe build evidence path")
    parent = Path(os.path.abspath(parent))
    if not (parent.is_relative_to(local_paths.scratch_root()) or parent.is_relative_to(ROOT / "evidence")):
        raise ValueError("Build evidence must remain off-cloud")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = parent / str(uuid4())
    result.mkdir(mode=0o700)
    return result

def write_identity(raw):
    """identity.json is replaced atomically (private temporary in ROOT, then os.replace)."""
    temporary=ROOT/(".identity-"+uuid4().hex+".json")
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"wb") as output:output.write(raw)
        os.replace(temporary,ROOT/"identity.json")
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
def setup(rebuild=False, build_evidence_dir=None):
    if bound_release() is not None:release_manifest(bound_release())  # refuse a release without a UI build first
    modeling_runtime.check(modeling_runtime.DEFAULT_ROOT)
    if ROOT.is_symlink():raise ValueError("Unsafe runtime root")
    ROOT.mkdir(exist_ok=True,mode=0o700);ROOT.chmod(0o700)
    for name in ("application","credentials","evidence"):
        path=ROOT/name
        if path.is_symlink():raise ValueError("Unsafe runtime child")
        path.mkdir(exist_ok=True,mode=0o700)
    net=modeling_runtime.inspect(PUBLIC_NETWORK,"network")
    if net is None:
        run("docker","network","create","--label",modeling_runtime.LABEL+"="+OWNER,PUBLIC_NETWORK)
    elif net.get("Labels",{}).get(modeling_runtime.LABEL)!=OWNER:
        raise ValueError("Public network identity mismatch")
    existing=inspect()
    if existing:
        guard(existing)
        if not rebuild:
            check();run("docker","start",NAME);return check()
    elif (ROOT/"identity.json").exists():
        raise ValueError("Owned application container missing; preserve store and investigate")
    if run("docker","image","inspect","python:3.12.11-slim-bookworm","--format","{{.Id}}")!=BASE:
        raise ValueError("Official Python base differs from reviewed pin")
    with tempfile.TemporaryDirectory(prefix="build-",dir=ROOT) as temp:
        temp=Path(temp)
        shutil.copytree(REPO/"application",temp/"application",ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO/"contracts",temp/"contracts",ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT/"wheels",temp/"wheels")
        binding=bound_release()
        if binding is not None:
            # Served assets are exactly the release's retained, manifest-hashed UI build.
            release_binding.copy_ui_build(binding.manifest_path.parent,release_manifest(binding),temp/'ui-dist')
        else:
            if not (UI_DIST/'index.html').is_file():raise ValueError('Build the audited UI before rebuilding the application')
            shutil.copytree(UI_DIST,temp/'ui-dist')
        shutil.copy(REPO/"deployment/application.Dockerfile",temp/"Dockerfile")
        # COPY keeps the context's modes and the application user is not root.
        modeling_runtime.readable_context(temp)
        evidence = build_evidence_directory(build_evidence_dir)
        # Image tags are hyprn-mvp-<role>:<first 16 hex of the build-input digest>.
        inputs=hashlib.sha256(json.dumps(dict(base=BASE,context=sorted(
            (str(p.relative_to(temp)),hashlib.sha256(p.read_bytes()).hexdigest()) for p in temp.rglob("*") if p.is_file())),
            sort_keys=True).encode()).hexdigest()
        tag="hyprn-mvp-application:"+inputs[:16]
        built=subprocess.run(["docker","build","--network=none","--pull=false","-t",tag,str(temp)],
                             text=True,capture_output=True,env=DOCKER_ENVIRONMENT)
        (evidence/"build.log").write_text(built.stdout)
        (evidence/"build.stderr").write_text(built.stderr)
        (evidence/"result.json").write_text(json.dumps({"exit":built.returncode})+"\n")
        built.check_returncode()
    image=run("docker","image","inspect",tag,"--format","{{.Id}}")
    store=ROOT/"application"
    if not existing:
        if list(store.iterdir()):raise ValueError("Refusing unowned nonempty application store")
        password_file=ROOT/"credentials/owner.password"
        fd=os.open(password_file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        password=secrets.token_urlsafe(32)
        with os.fdopen(fd,"w") as f:f.write(password+"\n")
        # The owner's sign-in name is an argument and the password is read from standard input.
        bootstrap=("import sys,os\n"
                   "from hyprn_mvp_app.store import Store\n"
                   "from hyprn_mvp_app.auth import Auth\n"
                   "s=Store('/store/application.sqlite')\n"
                   "Auth(s,'').provision(sys.argv[1],sys.stdin.read().strip())\n"
                   "os.chown('/store/application.sqlite',10002,10002)\n"
                   "os.chown('/store',10002,10002)\n")
        run("docker","run","--rm","-i","--network=none","--user","0:0",
            "--mount",f"type=bind,src={store},dst=/store",image,"python","-c",bootstrap,USERNAME,
            input=password)
    else:
        run("docker","stop",NAME)
        run("docker","rm",NAME)
    def create():
        run("docker","run","-d","--name",NAME,"--label",modeling_runtime.LABEL+"="+OWNER,
            "--user","10002:10002","--read-only","--cap-drop=ALL","--security-opt=no-new-privileges:true",
            "--memory=512m","--cpus=1","--pids-limit=64","--restart=no","--network",PUBLIC_NETWORK,
            "-p",f"127.0.0.1:{PORT}:8000","--tmpfs","/tmp:rw,noexec,nosuid,size=16m",
            "--mount",f"type=bind,src={store},dst=/store",
            "--mount",f"type=bind,src={modeling_runtime.DEFAULT_ROOT}/credentials/model.key,dst=/run/model.key,readonly",
            "-e","HYPRN_MVP_APP_STORE=/store/application.sqlite","-e",f"HYPRN_MVP_ORIGIN=http://127.0.0.1:{PORT}",
            "-e",f"HYPRN_MVP_MODEL_URL=http://{modeling_runtime.CONTAINER}:3000/modeling/1",
            "-e","HYPRN_MVP_MODEL_KEY_FILE=/run/model.key",image)
        run("docker","network","connect",modeling_runtime.NETWORK,NAME)
        identity=dict(owner=OWNER,container=NAME,image=image,base=BASE,source_hashes=hashes(),store=str(store))
        write_identity((json.dumps(identity,indent=2)+"\n").encode())
        return check()
    return create()
def main():
    local_paths.require(ROOT)
    local_paths.require(PORT,local_paths.PORT)
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=["setup","check","stop"])
    parser.add_argument("--rebuild",action="store_true")
    parser.add_argument("--build-evidence-dir",type=Path)
    args=parser.parse_args()
    if args.build_evidence_dir and args.operation!="setup":parser.error("Build evidence requires setup")
    if args.operation=="setup":
        result=setup(args.rebuild,args.build_evidence_dir)
    elif args.operation=="check":result=check()
    else:
        result=check();run("docker","stop",NAME);result["running"]=False
    print(json.dumps(result,indent=2))
if __name__=="__main__":
    # check is read-only and import-free; setup/stop require the selected release.
    release_binding.entrypoint(__file__,read_only=sys.argv[1:]==["check"],project_imports=False)
    main()
