"""Manage only the owned application container; no execution or legacy access.

The application store is HYPRN_MVP_DATA_ROOT/application and the published port is
HYPRN_MVP_PORT (deployment/local_paths.py); the commands refuse while either is unset.
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
import time
import urllib.error
import urllib.request
from uuid import uuid4
import release_binding
import local_paths
import modeling_runtime

ROOT=local_paths.application_root(required=False)
REPO=Path(__file__).resolve().parents[1]
NAME="hyprn-mvp-application"
OWNER="hyprn-mvp-application"
BASE="sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
# Development application port (HYPRN_MVP_PORT); None while unset, refused by main().
PORT=local_paths.port(required=False)
PUBLIC_NETWORK="hyprn-mvp-public"
UI_DIST=None if ROOT is None else ROOT/"ui"
def run(*args,input=None):
    return subprocess.run(args,input=input,text=True,capture_output=True,check=True).stdout.strip()
def inspect():
    result=subprocess.run(["docker","inspect",NAME],text=True,capture_output=True)
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
def docker_top():
    return subprocess.run(["docker","top",NAME,"-eo","pid,args"],text=True,capture_output=True)
def in_container_dispatchers():
    """Dispatcher processes inside the application container. A container that is not
    running has none; any other docker failure is a refusal, never an assumed absence."""
    result=docker_top()
    if result.returncode:
        if "is not running" in result.stderr or "No such container" in result.stderr:return []
        raise RuntimeError("docker top failed; cannot prove no in-container dispatcher: "+result.stderr.strip()[:200])
    return [line.strip() for line in result.stdout.splitlines()[1:] if "hyprn_mvp_app.dispatcher" in line]
def require_executor_quiescent():
    """No host executor (fail-closed executor.json, free executor.lock) and no
    dispatcher left inside the application container (docker exec children can outlive the host)."""
    import dispatch_runtime
    executor=dispatch_runtime.executor_quiescence()
    found=in_container_dispatchers()
    if found:raise ValueError("A dispatcher still runs inside the application container ("+found[0][:120]+"); refusing")
    return dict(executor=executor,in_container_dispatchers=[])
def liveness_probe(timeout=60.0,interval=1.0):
    """The replacement serves the reviewed API: unauthenticated GET /api/1/studies -> 401."""
    url=f"http://127.0.0.1:{PORT}/api/1/studies"
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline=time.monotonic()+timeout;attempts=0;last=None
    while True:
        attempts+=1
        try:
            response=opener.open(urllib.request.Request(url,method="GET"),timeout=5)
            last="HTTP "+str(getattr(response,"status",None));response.close()
        except urllib.error.HTTPError as error:
            if error.code==401:return dict(url=url,status=401,attempts=attempts)
            last="HTTP "+str(error.code)
        except (urllib.error.URLError,OSError) as error:
            last=repr(error)[:200]
        if time.monotonic()>=deadline:
            raise RuntimeError("Application liveness probe failed (expected unauthenticated 401): "+str(last))
        time.sleep(interval)
def upgrade_gate():
    """Reviewed upgrade: replace the EXISTING owned container with the bound release's image
    over the preserved store. Every precondition is read-only and precedes any effect."""
    if bound_release() is None:raise ValueError("Upgrade requires a selected release binding (served UI must be the release build)")
    require_executor_quiescent()
    if (ROOT.is_symlink() or not (ROOT/"identity.json").is_file() or not (ROOT/"application/application.sqlite").is_file()
            or not (ROOT/"credentials/owner.password").is_file()):
        raise ValueError("Preserved application store, credentials or identity missing; refusing upgrade")
    identity=json.loads((ROOT/"identity.json").read_text())
    if (identity.get("owner"),identity.get("container"),identity.get("store"))!=(OWNER,NAME,str(ROOT/"application")):
        raise ValueError("Application identity mismatch; refusing upgrade")
    existing=inspect()
    if existing is None:raise ValueError("Owned application container missing; the upgrade replaces an existing container only")
    guard(existing)
    if existing["Image"]!=identity["image"]:
        raise ValueError("Application container image differs from its recorded identity; refusing upgrade")
    return dict(previous_image=identity["image"],previous_container=existing["Id"])
def setup(rebuild=False, build_evidence_dir=None, upgrade=False):
    if upgrade and rebuild:raise ValueError("--upgrade cannot be combined with --rebuild")
    if bound_release() is not None:release_manifest(bound_release())  # refuse a release without a UI build first
    if upgrade:gate=upgrade_gate()
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
        if not rebuild and not upgrade:
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
        evidence = build_evidence_directory(build_evidence_dir)
        # Image tags are hyprn-mvp-<role>:<first 16 hex of the build-input digest>.
        inputs=hashlib.sha256(json.dumps(dict(base=BASE,context=sorted(
            (str(p.relative_to(temp)),hashlib.sha256(p.read_bytes()).hexdigest()) for p in temp.rglob("*") if p.is_file())),
            sort_keys=True).encode()).hexdigest()
        tag="hyprn-mvp-application:"+inputs[:16]
        built=subprocess.run(["docker","build","--network=none","--pull=false","-t",tag,str(temp)],text=True,capture_output=True)
        (evidence/"build.log").write_text(built.stdout)
        (evidence/"build.stderr").write_text(built.stderr)
        (evidence/"result.json").write_text(json.dumps({"exit":built.returncode})+"\n")
        built.check_returncode()
    image=run("docker","image","inspect",tag,"--format","{{.Id}}")
    store=ROOT/"application"
    replaced=None
    if upgrade:
        # Never reprovision. Keep the previous container (stopped, renamed) until the new one
        # passes check; any failure restores it and the previous identity exactly.
        previous_identity=(ROOT/"identity.json").read_bytes()
        retained=ROOT/"evidence"/("identity-before-upgrade-"+uuid4().hex+".json")
        with retained.open("xb") as output:output.write(previous_identity)
        replaced=NAME+"-replaced-"+uuid4().hex[:12]
        (evidence/"upgrade.json").write_text(json.dumps(dict(gate,image=image,identity_before=str(retained),
                                                               replaced_container=replaced),indent=2)+"\n")
    elif not existing:
        if list(store.iterdir()):raise ValueError("Refusing unowned nonempty application store")
        password_file=ROOT/"credentials/owner.password"
        fd=os.open(password_file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        password=secrets.token_urlsafe(32)
        with os.fdopen(fd,"w") as f:f.write(password+"\n")
        bootstrap="import sys,os; from hyprn_mvp_app.store import Store; from hyprn_mvp_app.auth import Auth; s=Store('/store/application.sqlite'); Auth(s,'').provision('owner',sys.stdin.read().strip()); os.chown('/store/application.sqlite',10002,10002); os.chown('/store',10002,10002)"
        run("docker","run","--rm","-i","--network=none","--user","0:0","--mount",f"type=bind,src={store},dst=/store",image,"python","-c",bootstrap,input=password)
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
    if not upgrade:return create()
    # Re-check right before the first container effect (the build took minutes).
    require_executor_quiescent()
    moved=False
    try:
        run("docker","stop",NAME)
        run("docker","rename",NAME,replaced);moved=True
        result=create()
        # The previous container is discarded only after the replacement is running and
        # serves the reviewed API (unauthenticated GET /api/1/studies -> 401).
        if not result.get("running"):raise ValueError("Replacement application container is not running")
        result["liveness"]=liveness_probe()
    except BaseException:
        restore_upgrade(replaced,previous_identity,moved)
        raise
    try:run("docker","rm",replaced)
    except subprocess.CalledProcessError:result["replaced_container_retained"]=replaced
    return result
def restore_upgrade(replaced,previous_identity,moved):
    """Put the previous identity (first, atomically) and container back exactly; the store
    was never touched."""
    try:
        write_identity(previous_identity)
        if moved:
            if inspect() is not None:
                run("docker","stop",NAME);run("docker","rm",NAME)
            run("docker","rename",replaced,NAME)
        run("docker","start",NAME)
    except BaseException as error:
        raise RuntimeError("Application upgrade failed and its automatic restore failed; the previous container is kept as "
                           +replaced+" with identity evidence/identity-before-upgrade-*.json") from error
def main():
    local_paths.require(ROOT)
    local_paths.require(PORT,local_paths.PORT)
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=["setup","check","stop"])
    parser.add_argument("--rebuild",action="store_true")
    parser.add_argument("--build-evidence-dir",type=Path)
    parser.add_argument("--upgrade",action="store_true",help="Reviewed replacement of the existing owned container with the bound release (executor stopped)")
    args=parser.parse_args()
    if args.build_evidence_dir and args.operation!="setup":parser.error("Build evidence requires setup")
    if args.upgrade and args.operation!="setup":parser.error("--upgrade requires setup")
    if args.operation=="setup":result=setup(args.rebuild,args.build_evidence_dir,upgrade=args.upgrade)
    elif args.operation=="check":result=check()
    else:
        result=check();run("docker","stop",NAME);result["running"]=False
    print(json.dumps(result,indent=2))
if __name__=="__main__":
    # check is read-only and import-free; setup/stop require the selected release.
    release_binding.entrypoint(__file__,read_only=sys.argv[1:]==["check"],project_imports=False)
    main()
