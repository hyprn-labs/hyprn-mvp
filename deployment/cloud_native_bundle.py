"""Build the locked Linux native environment and package it at its final release prefix.

The caller supplies an immutable source snapshot and reviewed worker build assets.
No application, AiiDA profile, candidate model or deployment service is started.
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request


MAX_FILES = 200000
MAX_BYTES = 32 * 1024**3


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def absolute(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Absolute nonsymlink build path required')
    return path


def linux():
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('Native release build requires Linux x86_64')


def case_sensitive(parent):
    """Linux binaries must be assembled on a case-sensitive filesystem."""
    with tempfile.TemporaryDirectory(prefix='.hyprn-fs-probe-', dir=parent) as folder:
        first = Path(folder) / 'Probe'
        first.write_bytes(b'')
        try:
            with (Path(folder) / 'probe').open('xb'):
                pass
        except FileExistsError:
            raise ValueError('Case-sensitive native build filesystem required') from None


def fetch(url, record):
    if not url.startswith('https://'):
        raise ValueError('Pinned HTTPS artifact required')
    with urllib.request.urlopen(url, timeout=60) as stream:
        raw = stream.read(record['size'] + 1)
    if len(raw) != record['size'] or hashlib.sha256(raw).hexdigest() != record['sha256']:
        raise ValueError('Pinned artifact bytes differ')
    return raw


def seed_tools(source, tools):
    """Use the same reviewed archives and shipped-interpreter policy as the images."""
    lock = json.loads((source / 'deployment/locks/tools.json').read_bytes())
    key = 'linux-x86_64'
    record = lock['uv_archives'][key]
    raw = fetch(lock['uv_download_base'] + record['archive'], record)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        member = archive.getmember(record['archive'].removesuffix('.tar.gz') + '/uv')
        if not member.isfile():
            raise ValueError('Pinned tool is not a file')
        uv = tools / 'uv' / lock['uv_version'] / key / 'uv'
        uv.parent.mkdir(parents=True)
        uv.write_bytes(archive.extractfile(member).read())
        uv.chmod(0o755)
    record = lock['cpython_archives'][key]
    raw = fetch(lock['cpython_install_mirror'] + '/' + lock['cpython_build'] + '/' + record['archive'], record)
    unpack = tools / 'python' / 'unpack'
    unpack.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        if any(m.name != 'python' and not m.name.startswith('python/') for m in archive.getmembers()):
            raise ValueError('Unexpected interpreter archive root')
        archive.extractall(unpack, filter='data')
    python = tools / 'python' / ('cpython-' + lock['cpython_version'] + '-linux-x86_64-gnu')
    (unpack / 'python').rename(python)
    unpack.rmdir()
    marker = python / 'BUILD'
    if marker.exists() and marker.read_text().strip() != lock['cpython_build']:
        raise ValueError('Pinned interpreter build differs')
    # uv writes this installation marker; the archive bytes were verified above.
    marker.write_text(lock['cpython_build'] + '\n')
    for extension in python.glob('lib/python*/lib-dynload/_dbm*.so'):
        extension.unlink()
    for folder in python.glob('lib/python*/site-packages'):
        for child in folder.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    for folder in python.glob('lib/python*/ensurepip'):
        shutil.rmtree(folder)
    for executable in python.glob('bin/pip*'):
        executable.unlink()
    return python / 'bin/python3.12'


def prepare(source, prefix, cache, source_commit):
    linux()
    source, prefix, cache = map(absolute, (source, prefix, cache))
    if not re.fullmatch('[a-f0-9]{40}', source_commit) or prefix.name != source_commit:
        raise ValueError('Release prefix must name exact source commit')
    if prefix.exists():
        raise ValueError('Refusing existing release prefix')
    # Immutable snapshots have regular files/directories only, including source.
    source_files = list(files(source, allow_links=False))
    if not source_files:
        raise ValueError('Empty source snapshot')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    case_sensitive(prefix.parent)
    case_sensitive(cache)
    prefix.mkdir()
    shutil.copytree(source, prefix / 'source')
    native = prefix / 'native'
    native.mkdir()
    cache.mkdir(parents=True, exist_ok=True)
    interpreter = seed_tools(prefix / 'source', prefix / 'tools')
    script = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
              'import native_environment as n;n.prepare(Path(sys.argv[2]),Path(sys.argv[3]),'
              'tools=Path(sys.argv[4]),cache=Path(sys.argv[5]))')
    subprocess.run([str(interpreter), '-I', '-B', '-c', script,
                    str(prefix / 'source/deployment'), str(native), str(prefix / 'source'),
                    str(prefix / 'tools'), str(cache)], check=True, timeout=1800)
    record = {'schema': 'hyprn-native-build/v1', 'source_commit': source_commit,
              'prefix': str(prefix), 'target': 'linux/amd64',
              'native_lock_sha256': digest(source / 'deployment/locks/native-host.txt'),
              'tools_lock_sha256': digest(source / 'deployment/locks/tools.json')}
    (prefix / 'build.json').write_text(json.dumps(record, sort_keys=True) + '\n')
    return record


def files(root, *, allow_links=True):
    """Flatten only internal links, refusing cycles and every special file."""
    root = absolute(root)
    seen = 0
    total = 0

    def visit(path, ancestors):
        nonlocal seen, total
        if path.is_symlink() and not allow_links:
            raise ValueError('Source symlink refused')
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError('Out-of-bundle symlink')
        info = resolved.stat()
        if stat.S_ISDIR(info.st_mode):
            if resolved in ancestors:
                raise ValueError('Directory symlink cycle')
            for child in sorted(path.iterdir()):
                yield from visit(child, ancestors | {resolved})
        elif stat.S_ISREG(info.st_mode):
            seen += 1
            total += info.st_size
            if seen > MAX_FILES or total > MAX_BYTES:
                raise ValueError('Bundle bound exceeded')
            yield path
        else:
            raise ValueError('Special bundle file refused')
    yield from visit(root, set())


def add_worker(prefix, worker_assets):
    prefix, worker_assets = map(absolute, (prefix, worker_assets))
    native = prefix / 'native'
    # Audit the selection first, before writing into the new native environment.
    selected = []
    for relative in ('runtime.json', 'locks/worker.lock', 'locks/worker-installed.json'):
        path = worker_assets / relative
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise ValueError('Reviewed worker inventory missing')
        selected.append((path, relative))
    for path in files(worker_assets / 'licenses/worker', allow_links=False):
        selected.append((path, str(path.relative_to(worker_assets))))
    runtime = json.loads((worker_assets / 'runtime.json').read_bytes())
    if runtime.get('architecture') != 'amd64':
        raise ValueError('Worker architecture differs')
    for relative, expected in runtime['source_hashes'].items():
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Worker source path refused')
        if digest(prefix / 'source' / relative) != expected:
            raise ValueError('Worker source identity differs')
    if digest(worker_assets / 'locks/worker.lock') != runtime['worker_lock_sha256']:
        raise ValueError('Worker dependency lock differs')
    if any((native / relative).exists() for _, relative in selected):
        raise ValueError('Worker inventory already installed')
    for path, relative in selected:
        target = native / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    record = json.loads((prefix / 'build.json').read_bytes())
    interpreter = native / ('venv-' + record['native_lock_sha256'][:16]) / 'bin/python'
    script = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
              'import native_environment as n;root=Path(sys.argv[2]);'
              'h=n.select_inventory(root);import json;'
              'runtime=json.loads((root/"runtime.json").read_bytes());'
              'runtime["selected_sha256"]=h;n.emit(root/"runtime.json",runtime)')
    subprocess.run([str(interpreter), '-I', '-B', '-c', script,
                    str(prefix / 'source/deployment'), str(native)], check=True, timeout=120)


def pack(prefix, output):
    prefix, output = map(absolute, (prefix, output))
    if output.exists() or output.is_relative_to(prefix):
        raise ValueError('New external archive path required')
    for name in ('build.json', 'native/runtime.json', 'native/selected.json'):
        if not (prefix / name).is_file():
            raise ValueError('Incomplete native build')
    if (prefix / 'bundle-inventory.json').exists():
        raise ValueError('Refusing to repack an extracted bundle')
    inventory = {str(p.relative_to(prefix)): {'sha256': digest(p), 'size': p.stat().st_size}
                 for p in files(prefix)}
    with tarfile.open(output, 'w:gz', dereference=True) as archive:
        for name in sorted(inventory):
            path = prefix / name
            item = archive.gettarinfo(str(path), arcname=name)
            item.uid = item.gid = 0
            item.uname = item.gname = ''
            item.mtime = 315532800
            item.mode = 0o755 if item.mode & 0o111 else 0o644
            with path.open('rb') as stream:
                archive.addfile(item, stream)
        raw = json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()
        item = tarfile.TarInfo('bundle-inventory.json')
        item.size, item.mode, item.mtime = len(raw), 0o644, 315532800
        archive.addfile(item, io.BytesIO(raw))
    return {'sha256': digest(output), 'size_bytes': output.stat().st_size, 'files': len(inventory)}


def verify_extracted(prefix):
    """Run on a fresh extraction at the exact prefix; never accept build-tree imports."""
    linux()
    prefix = absolute(prefix)
    record = json.loads((prefix / 'build.json').read_bytes())
    if str(prefix) != record['prefix']:
        raise ValueError('Native environment cannot be relocated')
    inventory = json.loads((prefix / 'bundle-inventory.json').read_bytes())
    actual = {str(p.relative_to(prefix)): p for p in files(prefix, allow_links=False)}
    if set(actual) != {*inventory, 'bundle-inventory.json'}:
        raise ValueError('Extracted bundle inventory differs')
    for name, expected in inventory.items():
        path = actual[name]
        if path.stat().st_size != expected['size'] or digest(path) != expected['sha256']:
            raise ValueError('Extracted bundle bytes differ')
    interpreter = prefix / 'native' / ('venv-' + record['native_lock_sha256'][:16]) / 'bin/python'
    script = ('import json,platform,sys;from pathlib import Path;'
              'source=Path(sys.argv[1]);'
              'sys.path[:0]=[str(source/p) for p in ("application/src","integration/src")];'
              'import aiida;'
              'import hyprn_mvp_integration.calculation;'
              'assert Path(hyprn_mvp_integration.calculation.__file__).is_relative_to(source);'
              'from importlib.metadata import entry_points;'
              'next(iter(entry_points(group="aiida.calculations",name="hyprn_mvp.scalar"))).load();'
              'print(json.dumps({"interpreter":platform.python_version(),"imports":"passed"}))')
    # Importing AiiDA creates its configuration directory even without a profile.
    # Keep that effect outside the immutable payload and any operator installation.
    with tempfile.TemporaryDirectory(prefix='hyprn-native-import-') as folder:
        environment = {'HOME': folder, 'AIIDA_PATH': str(Path(folder) / 'aiida'),
                       'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}
        subprocess.run([str(interpreter), '-I', '-B', '-c', script, str(prefix / 'source')],
                       check=True, timeout=120, env=environment)
    return {'verified': True, 'source_commit': record['source_commit'], 'files': len(inventory)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('prepare')
    for name in ('source', 'prefix', 'cache', 'source-commit'):
        p.add_argument('--' + name, required=True)
    p = sub.add_parser('add-worker')
    p.add_argument('--prefix', required=True)
    p.add_argument('--worker-assets', required=True)
    p = sub.add_parser('pack')
    p.add_argument('--prefix', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('verify-extracted')
    p.add_argument('--prefix', required=True)
    args = vars(parser.parse_args())
    operation = args.pop('operation')
    call = {'prepare': prepare, 'add-worker': add_worker, 'pack': pack,
            'verify-extracted': verify_extracted}[operation]
    print(json.dumps(call(**args), sort_keys=True))


if __name__ == '__main__':
    main()
