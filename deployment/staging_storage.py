"""Retain source; expire only identified staging exports and owned build volumes.

The explicit parent policy discovers new build/payload manifests automatically.
There is no home scan, image deletion, or global Docker prune.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime

import check_build_cache
import check_storage
import experiment_storage
import local_paths

ARCHIVES = {'app.oci.tar', 'modeling.oci.tar', 'worker.oci.tar', 'engine.oci.tar', 'native.tar.gz'}
SCHEMAS = {'source.json': 'hyprn-cloud-build-source/v1', 'payload.json': 'hyprn-hosted-payload/v1'}


def policy_path(explicit=None):
    return (local_paths.absolute(explicit, '--config') if explicit else
            local_paths.located('HYPRN_MVP_STAGING_STORAGE_CONFIG', 'staging-storage.json', required=False))


def parent_path(value):
    path = local_paths.absolute(value, 'staging parent')
    if path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_dir():
        raise ValueError('Staging parent must be an existing canonical directory')
    return path


def enroll(path, parents, budget=None, reserve=None):
    check_storage.safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with check_storage.safe(path.with_suffix('.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.exists() else dict(version=1, parents=[], budget_bytes=40*1024**3, reserve_bytes=5*1024**3)
        for value in parents:
            parent = parent_path(value)
            if str(parent) not in data['parents']:
                data['parents'].append(str(parent))
        for key, value in [('budget_bytes', budget), ('reserve_bytes', reserve)]:
            if value is not None:
                if value <= 0:
                    raise ValueError('Budget and reserve must be positive')
                data[key] = value
        check_storage.write(path, data)
    return data


def roots(config):
    found = {}
    for value in config['parents']:
        for root in parent_path(value).iterdir():
            if root.is_symlink() or not root.is_dir():
                continue
            for name, schema in SCHEMAS.items():
                marker = root / name
                if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 32*1024**2:
                    continue
                try:
                    record = json.loads(marker.read_text())
                except (ValueError, OSError):
                    continue
                if isinstance(record, dict) and record.get('schema') == schema:
                    experiment_storage.validate_root(str(root))
                    found[root] = record
                    break
    return found


def exports(root, snapshot):
    result = []
    for entry in snapshot['entries']:
        path = Path(entry[0])
        relative = path.relative_to(root)
        # Only root payloads and the builder's explicit artifact destinations.
        if path.name not in ARCHIVES or relative.parts[:-1] not in ((), ('artifacts',), ('unused-rebuilt-numerical-images',)):
            continue
        s = path.lstat()
        if (path.is_file() and not path.is_symlink() and s.st_nlink == 1
                and not any((p / '.git').exists() for p in (path.parent, *path.parent.parents))):
            result.append(path)
    return result


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True, check=True, timeout=180).stdout


def containers():
    ids = docker('ps', '-aq').split()
    return json.loads(docker('inspect', *ids)) if ids else []


def volume_build(volume):
    commit = (volume.get('Labels') or {}).get('org.hyprn.build', '')
    return commit if re.fullmatch('[a-f0-9]{40}', commit) and re.fullmatch(
        'hyprn-staging-build-' + commit[:12] + '-(cache|native|verify)', volume['Name']) else None


def old_volume(volume, eligible_commits, used, cutoff):
    commit = volume_build(volume)
    created = datetime.fromisoformat(volume['CreatedAt'].replace('Z', '+00:00')).timestamp()
    return commit in eligible_commits and volume['Name'] not in used and created < cutoff


VOLUME_PROBE = """import os,json
latest=0;total=0
for folder,dirs,files in os.walk('/data',followlinks=False):
 for name in ['.',*dirs,*files]:
  s=os.lstat(os.path.join(folder,name))
  latest=max(latest,s.st_mtime,s.st_ctime)
  total+=s.st_blocks*512
print(json.dumps(dict(latest=latest,bytes=total)))
"""


def volume_data(name, image):
    if not re.fullmatch('sha256:[a-f0-9]{64}', image or ''):
        raise ValueError('Set a reviewed immutable probe_image in the staging policy before deleting volumes')
    return json.loads(docker('run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
                             '--security-opt=no-new-privileges', '--pids-limit=32', '--memory=128m',
                             '--cpus=1', '--mount', 'type=volume,src='+name+',dst=/data,readonly,volume-nocopy',
                             '--entrypoint=python3', image, '-I', '-B', '-c', VOLUME_PROBE))


def collect(path, *, apply=False, now=None, inspect_activity=experiment_storage.activity, include_docker=True):
    now = time.time() if now is None else now
    cutoff = now - 86400
    check_storage.safe(path)
    with check_storage.safe(path.with_suffix('.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = json.loads(path.read_text())
        if config.get('version') != 1 or any(type(config.get(k)) is not int or config[k] <= 0 for k in ('budget_bytes', 'reserve_bytes')):
            raise ValueError('Invalid staging storage policy')
        report = dict(removed_file_bytes=0, roots=[], removed_volumes=[], cache_prune=None)
        states = {}
        observed = {}
        state = inspect_activity()
        for root, record in sorted(roots(config).items()):
            before = experiment_storage.snapshot(root)
            active = experiment_storage.busy(root, state)
            reason = 'recent' if before['latest'] >= cutoff else 'active' if active else 'expired'
            commit = record.get('source_commit')
            if commit:
                states.setdefault(commit, []).append((root, reason))
            targets = exports(root, before)
            eligible = sum(p.stat().st_blocks*512 for p in targets)
            if apply and reason == 'expired' and targets:
                if experiment_storage.busy(root, inspect_activity()) or experiment_storage.snapshot(root) != before:
                    reason = 'changed or active'
                    if commit:
                        states[commit][-1] = (root, reason)
                else:
                    identities = {e[0]: e for e in before['entries']}
                    for target in targets:
                        check_storage.safe(target)
                        s = target.lstat()
                        current = (str(target), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
                        if current != identities[str(target)]:
                            raise ValueError('Export changed during collection: ' + str(target))
                        target.unlink()
                        report['removed_file_bytes'] += s.st_blocks*512
                    reason = 'collected'
            observed[root] = experiment_storage.snapshot(root)
            report['roots'].append(dict(path=str(root), state=reason, bytes=check_storage.allocated(root), eligible_bytes=eligible))
        if include_docker:
            eligible_commits = {commit for commit, records in states.items() if all(reason == 'expired' for _, reason in records)}
            used = {m['Name'] for c in containers() for m in c.get('Mounts', []) if m['Type'] == 'volume'}
            names = docker('volume', 'ls', '-q', '--filter', 'label=org.hyprn.build').split()
            volumes = json.loads(docker('volume', 'inspect', *names)) if names else []
            report['eligible_volumes'] = []
            report['owned_volume_bytes'] = 0
            for volume in volumes:
                if not volume_build(volume):
                    continue
                probe = volume_data(volume['Name'], os.environ.get('HYPRN_MVP_STORAGE_PROBE_IMAGE', config.get('probe_image')))
                report['owned_volume_bytes'] += probe['bytes']
                if not old_volume(volume, eligible_commits, used, cutoff) or probe['latest'] >= cutoff:
                    continue
                report['eligible_volumes'].append(volume['Name'])
                if apply:
                    # Container references (including stopped containers) and live build roots
                    # are checked again; Docker refuses removal if a new reference appears.
                    fresh = inspect_activity()
                    commit = volume_build(volume)
                    if any(experiment_storage.busy(root, fresh) or experiment_storage.snapshot(root) != observed[root]
                           for root, _ in states[commit]):
                        continue
                    used_now = {m['Name'] for c in containers() for m in c.get('Mounts', []) if m['Type'] == 'volume'}
                    if volume['Name'] in used_now:
                        continue
                    if volume_data(volume['Name'], os.environ.get('HYPRN_MVP_STORAGE_PROBE_IMAGE', config.get('probe_image')))['latest'] >= cutoff:
                        continue
                    docker('volume', 'rm', volume['Name'])
                    report['owned_volume_bytes'] -= probe['bytes']
                    report['removed_volume_bytes'] = report.get('removed_volume_bytes', 0) + probe['bytes']
                    report['removed_volumes'].append(volume['Name'])
            records = check_build_cache.inventory()
            report['project_cache_bytes'] = sum(check_build_cache.size(r['Size']) for r in records)
            ids = [r['ID'] for r in records if r.get('Reclaimable') and not r.get('Shared')]
            if apply and ids:
                selector = 'id~=^(' + '|'.join(re.escape(i) for i in ids) + ')$'
                report['cache_prune'] = docker('buildx', 'prune', '--force', '--all', '--reserved-space', '0',
                                              '--filter', selector, '--filter', 'until=24h')
                report['project_cache_bytes'] = sum(check_build_cache.size(r['Size']) for r in check_build_cache.inventory())
        report['used_bytes'] = sum(r['bytes'] for r in report['roots'])
        import shutil
        report['admitted'] = (report['used_bytes'] <= config['budget_bytes'] and
                              report.get('project_cache_bytes', 0) <= config.get('cache_budget_bytes', 20*1024**3) and
                              report.get('owned_volume_bytes', 0) <= config.get('volume_budget_bytes', 20*1024**3) and
                              all(shutil.disk_usage(p).free >= config['reserve_bytes'] for p in config['parents']))
        return report


def automatic(*, current=None):
    # Scoped children may exercise the CLI; never discover a host policy there.
    if os.environ.get(local_paths.CHECK_SESSION) and not os.environ.get('HYPRN_MVP_STAGING_STORAGE_CONFIG'):
        return
    path = policy_path()
    if path is None or not path.exists():
        return
    if current is not None:
        enroll(path, [str(Path(current).parent)])
    report = collect(path, apply=True)
    print(json.dumps({'staging_storage': report}), file=sys.stderr, flush=True)
    if not report['admitted']:
        raise ValueError('Staging storage budget exceeded; recent, running and source data retained')
