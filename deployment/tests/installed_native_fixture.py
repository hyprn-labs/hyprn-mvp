"""Exact-bundle Linux rehearsal; every created resource has one checked scope owner."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

import cloud_release
import local_paths
import scoped_fixture as fixture

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'org.hyprn-mvp.test-scope'
# Exact amd64 child of the reviewed Docker CLI index; see deployment/provenance.md.
CLI_IMAGE = 'docker@sha256:d329fa64f42e03248f9a6cb2e21b6d4aa4d76f5a80aa2ad7946d81fbf1860602'
# Existing reviewed modeling image provides Linux host utilities (not candidate
# execution). Only the extracted native interpreter is started in this fixture.
OWNER_IMAGE = 'sha256:fc4c6fa692effd856f783e1f7082a16653244c20348a2191b2f743fae928e9b9'
OWNER_INDEX = 'sha256:cfb49e197e7694f2e2b3498157174acc753c7fe63a058687b38680da38e84d78'


def docker(*args, timeout=120):
    return subprocess.run(['docker', *args], capture_output=True, text=True,
                          check=True, timeout=timeout).stdout.strip()


def inputs(value):
    if (set(value) != {'schema', 'bundle', 'sha256', 'source_commit'}
            or value['schema'] != 'hyprn-native-rehearsal/v1'
            or not re.fullmatch('[a-f0-9]{64}', value['sha256'])
            or not re.fullmatch('[a-f0-9]{40}', value['source_commit'])):
        raise ValueError('Exact native bundle identity required')
    bundle = fixture.no_symlinks(Path(value['bundle']))
    if (not bundle.is_file() or bundle.is_relative_to(ROOT)
            or any(bundle == p or p in bundle.parents for p in local_paths.live_roots())
            or cloud_release.file_hash(bundle) != value['sha256']):
        raise ValueError('Native bundle bytes or location differ')
    with tarfile.open(bundle) as archive:
        members = archive.getmembers()
        names = set()
        if len(members) > 200000 or sum(m.size for m in members) > 32 * 1024**3:
            raise ValueError('Native archive exceeds bound')
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or '\\' in member.name
                    or member.name in names or not (member.isfile() or member.isdir())):
                raise ValueError('Native archive contains unsafe member')
            names.add(member.name)
        member = archive.getmember('build.json')
        if not member.isfile() or member.size > 16384:
            raise ValueError('Native build identity missing')
        record = json.load(archive.extractfile(member))
    prefix = Path(record['prefix'])
    if (record['source_commit'] != value['source_commit'] or prefix.name != value['source_commit']
            or not prefix.is_absolute() or '..' in prefix.parts or record['target'] != 'linux/amd64'):
        raise ValueError('Native build prefix or target differs')
    return bundle, record


def owned_volume(name, run):
    result = json.loads(docker('volume', 'inspect', name))[0]
    if result.get('Labels', {}).get(LABEL) != run or result['Name'] != name:
        raise ValueError('Foreign volume; refusing use or cleanup')
    mount = Path(result['Mountpoint'])
    if not mount.is_absolute() or '..' in mount.parts:
        raise ValueError('Invalid daemon volume mountpoint')
    return str(mount)


def rehearse(scope, value):
    fixture.guarded(scope, lambda _: None)
    bundle, build = inputs(value)
    pins = cloud_release.read_json(ROOT / 'deployment/pins.json')
    base = 'python@' + pins['image_bases']['python']['platforms']['linux/amd64']
    cli = CLI_IMAGE
    for image in (base, cli):
        info = json.loads(docker('image', 'inspect', image))[0]
        if (info['Os'], info['Architecture']) != ('linux', 'amd64'):
            raise ValueError('Reviewed Linux amd64 fixture image required')
    host = json.loads(docker('image', 'inspect', '--platform=linux/amd64', OWNER_INDEX))[0]
    if host['Id'] != OWNER_IMAGE or (host['Os'], host['Architecture']) != ('linux', 'amd64'):
        raise ValueError('Reviewed Linux host utilities image required')
    socket = local_paths.docker_socket()
    run = scope.run_uuid
    names = {role: 'hyprn-installed-' + role + '-' + run for role in ('release', 'state', 'cli', 'owner')}
    volumes, containers = [], []
    evidence = fixture.scoped_path(scope, 'evidence')
    installation = 'rehearsal-' + run
    worker_owner = 'hyprn-mvp-cloud-' + installation
    prefix = build['prefix']
    try:
        for role in ('release', 'state'):
            name = names[role]
            docker('volume', 'create', '--label', LABEL + '=' + run, name)
            volumes.append(name)
            owned_volume(name, run)
        state = owned_volume(names['state'], run)
        docker('create', '--pull=never', '--name', names['cli'], '--label', LABEL + '=' + run,
               '--platform=linux/amd64', '--network=none', '--entrypoint=/bin/true', cli)
        containers.append(names['cli'])
        executable = fixture.scoped_path(scope, 'artifacts/docker')
        docker('cp', names['cli'] + ':/usr/local/bin/docker', str(executable))
        if executable.is_symlink() or not executable.is_file():
            raise ValueError('Reviewed CLI must be a regular executable')
        executable.chmod(0o755)
        common = ['run', '--rm', '--pull=never', '--platform=linux/amd64', '--network=none',
                  '--read-only', '--security-opt=no-new-privileges',
                  '--pids-limit=128', '--label', LABEL + '=' + run]
        extract = ('import tarfile,sys;from pathlib import Path;p=Path(sys.argv[2]);'
                   'assert not any(p.iterdir());'
                   'a=tarfile.open(sys.argv[1]);'
                   'assert all(m.isfile() or m.isdir() for m in a.getmembers());'
                   'a.extractall(p,filter="data");'
                   'state=Path(sys.argv[3]);'
                   'passwd=Path("/etc/passwd").read_text();group=Path("/etc/group").read_text();'
                   'assert not any(line.split(":")[2]=="10003" for line in passwd.splitlines());'
                   'assert not any(line.split(":")[2]=="10003" for line in group.splitlines());'
                   '(state/"passwd").write_text(passwd+"hyprn-execution:x:10003:10003:Native fixture:"+str(state/"home")+":/bin/sh\\n");'
                   '(state/"group").write_text(group+"hyprn-execution:x:10003:\\n")')
        docker(*common, '--cpus=1', '--memory=2g', '--cap-drop=ALL',
               '--mount', 'type=bind,source=' + str(bundle) + ',target=/bundle,readonly',
               '--mount', 'type=volume,source=' + names['release'] + ',target=' + prefix,
               '--mount', 'type=volume,source=' + names['state'] + ',target=' + state,
               base, 'python', '-I', '-B', '-c', extract, '/bundle', prefix, state, timeout=300)
        controller = Path(__file__).with_name('installed_native_owner.py')
        python = str(Path(prefix) / 'native' / ('venv-' + build['native_lock_sha256'][:16]) / 'bin/python')
        containers.append(names['owner'])
        command = [*common, '--cpus=1', '--memory=1g', '--name', names['owner'], '--cap-drop=ALL', '--cap-add=CHOWN',
                   '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=DAC_OVERRIDE',
                   '--tmpfs=/tmp:rw,noexec,nosuid,size=64m,mode=1777',
                   '--mount', 'type=volume,source=' + names['release'] + ',target=' + prefix + ',readonly',
                   '--mount', 'type=volume,source=' + names['state'] + ',target=' + state,
                   '--mount', 'type=bind,source=' + state + '/passwd,target=/etc/passwd,readonly',
                   '--mount', 'type=bind,source=' + state + '/group,target=/etc/group,readonly',
                   '--mount', 'type=bind,source=' + str(socket) + ',target=/engine.sock,readonly',
                   '--mount', 'type=bind,source=' + str(executable) + ',target=/usr/local/bin/docker,readonly',
                   '--mount', 'type=bind,source=' + str(controller) + ',target=/fixture.py,readonly',
                   '--user=0:0', '--entrypoint=' + python,
                   OWNER_INDEX, '-I', '-B', '/fixture.py', prefix, state, installation]
        result = subprocess.run(['docker', *command], capture_output=True, text=True, timeout=600)
        (evidence / 'installed-native.stdout').write_text(result.stdout)
        (evidence / 'installed-native.stderr').write_text(result.stderr)
        # Retain the actual probe report before the disposable store is released,
        # including refusals. The collector has no daemon socket or network.
        collect = ('import sys;from pathlib import Path;'
                   'p=Path(sys.argv[1])/"execution/evidence"/sys.argv[2];'
                   'assert not p.is_symlink();'
                   'raw=p.open("rb").read(1048577) if p.is_file() else b"";'
                   'assert len(raw)<=1048576;sys.stdout.buffer.write(raw)')
        for report_name in ('containment.json', 'calculation.json'):
            report = docker(*common, '--cpus=1', '--memory=256m', '--cap-drop=ALL', '--user=10003:10003',
                            '--mount', 'type=volume,source=' + names['state'] + ',target=' + state + ',readonly',
                            base, 'python', '-I', '-B', '-c', collect, state, report_name)
            if report:
                (evidence / report_name).write_text(report)
        if result.returncode:
            raise RuntimeError('Installed native owner refused; inspect scoped evidence')
        observed = json.loads(result.stdout)
        if observed['source_commit'] != value['source_commit'] or observed['status'] != 'calculated':
            raise ValueError('Installed native observation differs')
        observation = dict(observed, bundle_sha256=value['sha256'],
                           owner_host_image=OWNER_IMAGE,
                           docker_cli_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
        (evidence / 'installed-native.json').write_text(json.dumps(observation, sort_keys=True))
        return observation
    finally:
        # Workers have the cloud owner's exact random identity, not a broad prefix.
        ids = docker('ps', '-aq', '--filter', 'label=org.hyprn-mvp.owner=' + worker_owner).split()
        for identifier in ids:
            record = json.loads(docker('inspect', identifier))[0]
            if record['Config']['Labels'].get('org.hyprn-mvp.owner') != worker_owner:
                raise ValueError('Foreign worker cleanup refused')
            docker('rm', '-f', identifier)
        for name in reversed(containers):
            probe = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True)
            if probe.returncode:
                continue
            if json.loads(probe.stdout)[0]['Config']['Labels'].get(LABEL) != run:
                raise ValueError('Foreign container cleanup refused')
            docker('rm', '-f', name)
        for name in reversed(volumes):
            owned_volume(name, run)
            docker('volume', 'rm', name)
        (evidence / 'installed-native-cleanup.json').write_text(json.dumps({'released': True, 'scope': run}))
