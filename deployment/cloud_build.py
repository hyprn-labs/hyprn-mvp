"""Build cloud application bytes from an explicit Git commit, without publishing.

Uncommitted files never enter the context. Native assembly remains owned by
cloud_native_bundle.py; neither builder creates qualification evidence.
"""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile

import cloud_release


def path(value):
    value = Path(value)
    if not value.is_absolute() or '..' in value.parts:
        raise ValueError('Absolute build path required')
    if any(p.is_symlink() for p in (value, *value.parents)):
        raise ValueError('Build path cannot contain symlinks')
    return value


def inventory(root):
    result = {}
    for item in sorted(root.rglob('*')):
        if item.is_symlink() or not (item.is_dir() or item.is_file()):
            raise ValueError('Source links and special files are refused')
        if item.is_file():
            result[str(item.relative_to(root))] = {
                'sha256': cloud_release.file_hash(item),
                'size_bytes': item.stat().st_size,
                'executable': bool(item.stat().st_mode & 0o111),
            }
    return result


def snapshot(repository, commit, output):
    repository, output = path(repository), path(output)
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Exact full Git commit required')
    if output.exists() or output.is_relative_to(repository):
        raise ValueError('New build directory outside repository required')
    actual = subprocess.check_output(
        ['git', '-C', str(repository), 'rev-parse', commit + '^{commit}'], text=True).strip()
    if actual != commit:
        raise ValueError('Source commit differs')
    output.mkdir(mode=0o700)
    archive_path = output / 'source.tar'
    with archive_path.open('xb') as stream:
        subprocess.run(['git', '-C', str(repository), 'archive', '--format=tar', commit],
                       stdout=stream, check=True)
    source = output / 'source'
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isdir() or member.isfile()):
                raise ValueError('Git snapshot contains unsupported entries')
            private = ('.git', 'credentials', 'secrets', 'node_modules')
            if any(part in private for part in name.parts):
                raise ValueError('Private or generated directory in Git snapshot')
            if name.name == '.env' or name.name.startswith('.env.'):
                raise ValueError('Environment file in Git snapshot')
        source.mkdir()
        # Git emits only the regular files/directories admitted above. Copy their
        # bytes explicitly; no archive link, owner or extended attribute is used.
        for member in archive.getmembers():
            target = source / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as incoming, target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    record = {'schema': 'hyprn-cloud-build-source/v1', 'source_commit': commit,
              'archive_sha256': cloud_release.file_hash(archive_path),
              'files': inventory(source)}
    (output / 'source.json').write_bytes(cloud_release.canonical(record))
    return {'source_commit': commit, 'source': str(source),
            'source_record_sha256': cloud_release.digest(record)}


def verify_source(root):
    record = cloud_release.read_json(root / 'source.json')
    if (record.get('schema') != 'hyprn-cloud-build-source/v1'
            or not re.fullmatch('[a-f0-9]{40}', record.get('source_commit', ''))
            or inventory(root / 'source') != record.get('files')
            or cloud_release.file_hash(root / 'source.tar') != record.get('archive_sha256')):
        raise ValueError('Committed build source changed')
    return record


def build_app(root):
    root = path(root)
    record = verify_source(root)
    source = root / 'source'
    pins = cloud_release.read_json(source / 'deployment/pins.json')
    images = {}
    for name in ('python', 'node'):
        digest = pins['image_bases'][name]['platforms']['linux/amd64']
        if not re.fullmatch('sha256:[a-f0-9]{64}', digest):
            raise ValueError('Pinned AMD64 base image required')
        images[name] = 'docker.io/library/' + name + '@' + digest
    artifacts = root / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    output = artifacts / 'app.oci.tar'
    identity = root / 'app-image.id'
    if output.exists() or identity.exists():
        raise ValueError('Application build already attempted; inspect before retry')
    args = ['docker', 'buildx', 'build', '--platform=linux/amd64', '--target=cloud',
            '--provenance=false', '--load', '--build-arg', 'PYTHON_IMAGE=' + images['python'],
            '--build-arg', 'NODE_IMAGE=' + images['node'], '--iidfile', str(identity),
            '--file', str(source / 'deployment/application.Dockerfile'), str(source)]
    with (root / 'app-build.log').open('x') as log:
        subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    image = identity.read_text().strip()
    if not re.fullmatch('sha256:[a-f0-9]{64}', image):
        raise ValueError('Built image identity invalid')
    subprocess.run(['docker', 'image', 'save', '--platform=linux/amd64', '--output',
                    str(output), image], check=True, timeout=300)
    with tarfile.open(output) as archive:
        manifests = json.load(archive.extractfile('index.json'))['manifests']
        if len(manifests) != 1:
            raise ValueError('Exactly one application manifest required')
        manifest = manifests[0]['digest']
    cloud_release.verify_oci(output, manifest.removeprefix('sha256:'))
    verify_source(root)
    proof = {'source_commit': record['source_commit'], 'image': image, 'manifest': manifest,
             'sha256': cloud_release.file_hash(output), 'size_bytes': output.stat().st_size,
             'base_images': images, 'source_record_sha256': cloud_release.digest(record),
             'oci_verified': True, 'execution_qualified': False}
    (artifacts / 'app.oci.verification.json').write_bytes(cloud_release.canonical(proof))
    return proof


def freeze_payload(platform_root, documents, inputs, output):
    """Bind caller-reviewed documents to verified bytes; never invent evidence.

Evidence documents are supplied, not generated here. Their scope and outstanding
runtime acceptance remain intact. This operation does not authorize publication.
"""
    documents, inputs, output = map(path, (documents, inputs, output))
    if output.exists() or output.is_relative_to(documents):
        raise ValueError('Fresh separate payload directory required')
    document_paths = {name: documents / (name + '.json')
                      for name in ('workload', 'release', 'runtime', 'desired')}
    contract, values, _ = cloud_release.documents(platform_root, document_paths)
    release = values['release']
    sources = cloud_release.read_json(inputs)
    expected = {'app', 'modeling', 'worker', 'native_bundle', 'ui', *release['evidence']}
    if set(sources) != expected:
        raise ValueError('Every payload role must have an explicit source')
    selected = {}
    for role, source in sources.items():
        source = path(source)
        if not source.is_file():
            raise ValueError('Payload source must be a regular file')
        suffix = '.oci.tar' if role in ('app', 'modeling', 'worker') else '.json'
        name = 'native.tar.gz' if role == 'native_bundle' else role + suffix
        selected[role] = (source, {
            'path': name, 'sha256': cloud_release.file_hash(source),
            'size_bytes': source.stat().st_size,
        })
    output.mkdir(mode=0o700)
    for name, source in document_paths.items():
        # Serialize the validated values, avoiding a second unvalidated read.
        (output / (name + '.json')).write_bytes(cloud_release.canonical(values[name]))
    for source, record in selected.values():
        shutil.copyfile(source, output / record['path'])
    payload = {'schema': 'hyprn-hosted-payload/v1',
               'release_sha256': contract.digest(release),
               'files': {role: record for role, (_, record) in selected.items()}}
    payload_path = output / 'payload.json'
    payload_path.write_bytes(cloud_release.canonical(payload))
    verified = cloud_release.payload(payload_path, release, contract)
    return {'release_sha256': contract.digest(release),
            'payload_sha256': verified['inventory_sha256'], 'payload_verified': True,
            'publication_performed': False, 'runtime_acceptance_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest='operation', required=True)
    command = operations.add_parser('snapshot')
    for name in ('repository', 'commit', 'output'):
        command.add_argument('--' + name, required=True)
    command = operations.add_parser('app')
    command.add_argument('--root', required=True)
    command = operations.add_parser('payload')
    for name in ('platform-root', 'documents', 'inputs', 'output'):
        command.add_argument('--' + name, required=True)
    args = vars(parser.parse_args())
    operation = args.pop('operation')
    function = {'snapshot': snapshot, 'app': build_app, 'payload': freeze_payload}[operation]
    result = function(**args)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
