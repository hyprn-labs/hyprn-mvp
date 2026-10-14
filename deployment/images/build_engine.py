"""Build only the approved source distributions; runtime payloads must remain exact."""

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch(artifact, destination):
    with urllib.request.urlopen(artifact['url']) as response:
        raw = response.read(artifact['size'] + 1)
    if len(raw) != artifact['size'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
        raise ValueError('Reviewed engine artifact identity mismatch')
    destination.write_bytes(raw)


def extract(archive, destination, prefix):
    with tarfile.open(archive) as source:
        seen = set()
        for member in source.getmembers():
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] != prefix or member.name in seen):
                raise ValueError('Unsafe engine source member')
            seen.add(member.name)
            if not (member.isfile() or member.isdir()):
                raise ValueError('Engine source links and special files are refused')
            target = destination / path
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o755)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                target.write_bytes(source.extractfile(member).read())
                target.chmod(0o644)
    return destination / prefix


def payload(root, module):
    return {str(path.relative_to(root)): sha(path)
            for path in sorted((root / module).rglob('*')) if path.is_file()}


def normalize_xdsm_tag(wheel):
    """Retain the reference's Python 3 tag without changing Python requirements."""
    prefix = 'xdsmjs-2.1.0.dist-info/'
    expected = (b'Wheel-Version: 1.0\nGenerator: flit 4.1.0\n'
                b'Root-Is-Purelib: true\nTag: py2-none-any\nTag: py3-none-any\n')
    with zipfile.ZipFile(wheel) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or source.read(prefix + 'WHEEL') != expected:
            raise ValueError('Unexpected XDSMjs intermediate wheel metadata')
        entries = [(info, source.read(info)) for info in source.infolist()
                   if info.filename != prefix + 'RECORD']
    target = wheel.with_name('xdsmjs-2.1.0-py3-none-any.whl')
    records = io.StringIO(newline='')
    writer = csv.writer(records, lineterminator='\n')
    with zipfile.ZipFile(target, 'x') as result:
        for info, raw in entries:
            if info.filename == prefix + 'WHEEL':
                raw = expected.replace(b'Tag: py2-none-any\n', b'')
            result.writestr(info, raw)
            digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=')
            writer.writerow((info.filename, 'sha256=' + digest.decode(), len(raw)))
        writer.writerow((prefix + 'RECORD', '', ''))
        record = zipfile.ZipInfo(prefix + 'RECORD', (1980, 1, 1, 0, 0, 0))
        record.compress_type = zipfile.ZIP_DEFLATED
        record.external_attr = 0o644 << 16
        result.writestr(record, records.getvalue())
    return target


def acquire(root):
    manifest = json.loads((root / 'engine-sources.json').read_bytes())
    backend = json.loads((root / 'build-backend.json').read_bytes())
    wheelhouse = root / 'wheelhouse'
    wheelhouse.mkdir()
    fetch(backend['wheel'], wheelhouse / backend['wheel']['filename'])
    constraint = backend['requirement'] + ' --hash=sha256:' + backend['wheel']['sha256']
    (root / 'build-constraints.txt').write_text(constraint + '\n')
    packages = {row['name'] for row in manifest['packages']}
    lines = (root / 'worker-requirements.lock').read_text().splitlines()
    (root / 'binary.lock').write_text('\n'.join(
        line for line in lines if line.split('==')[0] not in packages
    ) + '\n')
    archives = root / 'archives'
    archives.mkdir()
    for row in manifest['packages']:
        fetch(row['archive'], archives / row['archive']['filename'])


def build(root, runtime):
    manifest = json.loads((root / 'engine-sources.json').read_bytes())
    backend = json.loads((root / 'build-backend.json').read_bytes())
    if sha(root / 'wheelhouse' / backend['wheel']['filename']) != backend['wheel']['sha256']:
        raise ValueError('Build backend drift')
    environment = dict(os.environ, SOURCE_DATE_EPOCH='315532800', UV_NO_CONFIG='1')
    base = [
        str(runtime / 'uv'), 'build', '--python', str(runtime / 'venv/bin/python'),
        '--offline', '--no-index', '--find-links', str(root / 'wheelhouse'),
        '--build-constraints', str(root / 'build-constraints.txt'), '--require-hashes',
    ]
    installed = []
    evidence = []
    for row in manifest['packages']:
        name = row['name'] + '-' + row['version']
        archive = root / 'archives' / row['archive']['filename']
        if sha(archive) != row['archive']['sha256']:
            raise ValueError('Engine archive drift')
        patch = root / 'packaging' / (row['name'] + '.patch')
        if sha(patch) != row['patch_sha256']:
            raise ValueError('Approved engine packaging patch drift')
        wheels = []
        for iteration in (1, 2):
            work = root / 'generated' / name / str(iteration)
            work.mkdir(parents=True)
            source = extract(archive, work, name)
            original = source / 'pyproject.toml'
            actual = sha(original) if original.exists() else None
            if actual != row['original_pyproject_sha256']:
                raise ValueError('Original upstream recipe drift')
            expected = {item['path']: item['original_sha256']
                        for item in row['runtime_comparison']}
            if payload(source, row['module']) != expected:
                raise ValueError('Original engine package payload drift')
            original.write_text(row['pyproject'])
            if sha(original) != row['proposed_pyproject_sha256']:
                raise ValueError('Approved Flit recipe drift')
            if payload(source, row['module']) != expected:
                raise ValueError('Engine packaging changed runtime source')
            subprocess.run(base + ['--sdist', '--out-dir', str(work), str(source)],
                           env=environment, check=True)
            sdist = work / (name + '.tar.gz')
            generated = extract(sdist, work / 'verified', name)
            expected_wheel = {item['path']: item['original_sha256']
                              for item in row['expected_wheel_payload']}
            if payload(generated, row['module']) != expected_wheel:
                raise ValueError('Generated sdist runtime payload differs')
            subprocess.run(base + ['--wheel', '--out-dir', str(work), str(sdist)],
                           env=environment, check=True)
            wheel = work / (row['name'] + '-' + row['version'] + '-py3-none-any.whl')
            if row['name'] == 'xdsmjs':
                wheel = normalize_xdsm_tag(work / 'xdsmjs-2.1.0-py2.py3-none-any.whl')
            with zipfile.ZipFile(wheel) as built:
                files = {path: hashlib.sha256(built.read(path)).hexdigest()
                         for path in built.namelist() if path.startswith(row['module'] + '/')}
                metadata = {path: hashlib.sha256(built.read(path)).hexdigest()
                            for path in built.namelist()
                            if not path.startswith(row['module'] + '/')
                            and not path.endswith('.dist-info/RECORD')}
                if metadata != row['expected_wheel_metadata']:
                    raise ValueError('Built wheel metadata differs from reviewed equivalence')
            if files != expected_wheel:
                raise ValueError('Built wheel runtime payload differs')
            wheels.append(wheel)
        if sha(wheels[0]) != sha(wheels[1]):
            raise ValueError('Engine wheel is not reproducible')
        target = root / 'wheelhouse' / wheels[0].name
        shutil.copyfile(wheels[0], target)
        installed.append(row['name'] + '==' + row['version'] + ' --hash=sha256:' + sha(target))
        evidence.append(dict(name=row['name'], version=row['version'], wheel_sha256=sha(target),
                             archive_sha256=sha(archive), patch_sha256=sha(patch),
                             runtime_files=expected_wheel, reproducible=True))
    lock = root / 'built.lock'
    lock.write_text('\n'.join(installed) + '\n')
    subprocess.run([
        str(runtime / 'uv'), 'pip', 'install', '--python', str(runtime / 'venv/bin/python'),
        '--offline', '--no-index', '--find-links', str(root / 'wheelhouse'),
        '--require-hashes', '--no-deps', '-r', str(lock),
    ], env=environment, check=True)
    (runtime / 'engine-build.json').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    if sys.argv[1] == 'acquire':
        acquire(Path(sys.argv[2]))
    else:
        build(Path(sys.argv[2]), Path(sys.argv[3]))
