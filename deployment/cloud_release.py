"""Consume the exact platform contract and verify actual hosted payload bytes.

The renderer is supplied separately by the platform. This module neither vendors
it nor defines another release schema. Missing binary inputs are never replaced
by an inventory of this source checkout.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import types

PIN = Path(__file__).with_name('cloud_release.schema.json')
MAX_DOCUMENT = 2 * 1024 * 1024


class Invalid(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DOCUMENT:
        raise Invalid('invalid_document')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid('duplicate_key')
            result[key] = value
        return result
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid('invalid_json')))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise Invalid('invalid_json') from None


def platform_contract(root):
    root = Path(root)
    pin = read_json(PIN)
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise Invalid('platform_path')
    for relative, expected in pin['files'].items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or file_hash(path) != expected:
            raise Invalid('platform_contract_pin')
    # Compile the bytes just verified, without executing an unpinned import loader.
    source = root / 'host/contract.py'
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin['files']['host/contract.py']:
        raise Invalid('platform_contract_pin')
    module = types.ModuleType('hyprn_pinned_platform_contract')
    module.__file__ = str(source)
    exec(compile(raw, str(source), 'exec'), module.__dict__)
    return module


def documents(platform_root, paths):
    contract = platform_contract(platform_root)
    values = {kind: contract.read_json(paths[kind]) for kind in
              ('workload', 'release', 'runtime', 'desired')}
    if values['release']['platform_contract']['commit'] != read_json(PIN)['commit']:
        raise Invalid('platform_commit_pin')
    contract.check_documents(values)
    preview = contract.render(values['release'], values['runtime'])
    contract.check_desired(values['desired'], values['release'], values['runtime'], contract.digest(preview))
    return contract, values, preview


def payload(path, release, contract):
    """Hash local OCI archives, native bundle, built UI and detached release evidence."""
    path = Path(path)
    inventory = read_json(path)
    if (set(inventory) != {'schema', 'release_sha256', 'files'}
            or inventory['schema'] != 'hyprn-hosted-payload/v1'
            or inventory['release_sha256'] != contract.digest(release)
            or not isinstance(inventory['files'], dict)):
        raise Invalid('payload_inventory')
    expected = {'app', 'modeling', 'worker', 'native_bundle', 'ui', *release['evidence']}
    if set(inventory['files']) != expected:
        raise Invalid('payload_incomplete')
    resolved = {}
    for role, record in inventory['files'].items():
        if (set(record) != {'path', 'size_bytes', 'sha256'}
                or type(record['size_bytes']) is not int or record['size_bytes'] < 1
                or not isinstance(record['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise Invalid('payload_record')
        relative = PurePosixPath(record['path'])
        if (relative.is_absolute() or '..' in relative.parts or '\\' in record['path']
                or not relative.parts):
            raise Invalid('payload_path')
        target = path.parent / relative
        if (any(p.is_symlink() for p in (target, *target.parents)) or not target.is_file()
                or target.stat().st_size != record['size_bytes'] or file_hash(target) != record['sha256']):
            raise Invalid('payload_bytes')
        resolved[role] = target
    for role, expected_hash in release['evidence'].items():
        if inventory['files'][role]['sha256'] != expected_hash:
            raise Invalid('payload_evidence_pin')
    if inventory['files']['ui']['sha256'] != release['ui_manifest_sha256']:
        raise Invalid('payload_ui_pin')
    contract.check_bundle(resolved['native_bundle'], release['native_bundle'])
    for component in ('app', 'modeling', 'worker'):
        verify_oci(resolved[component], release['images'][component].split('@sha256:')[1])
    return {'inventory_sha256': digest(inventory), 'files': resolved}


def verify_oci(path, expected_manifest):
    """Check the complete referenced OCI graph and target architecture without loading it."""
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) > 200000 or sum(m.size for m in members) > 32 * 1024**3:
            raise Invalid('oci_size')
        names = set()
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or member.name in names
                    or not (member.isfile() or member.isdir())):
                raise Invalid('oci_member')
            names.add(member.name)
        def blob(digest_value, *, document=True, expected_size=None):
            if not re.fullmatch('sha256:[0-9a-f]{64}', digest_value):
                raise Invalid('oci_digest')
            member = archive.getmember('blobs/sha256/' + digest_value[7:])
            if not member.isfile():
                raise Invalid('oci_blob')
            if expected_size is not None and member.size != expected_size:
                raise Invalid('oci_blob_size')
            if document and member.size > MAX_DOCUMENT:
                raise Invalid('oci_document_size')
            hasher, parts = hashlib.sha256(), []
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    hasher.update(block)
                    if document:
                        parts.append(block)
            if hasher.hexdigest() != digest_value[7:]:
                raise Invalid('oci_blob')
            return b''.join(parts)
        if archive.getmember('index.json').size > MAX_DOCUMENT:
            raise Invalid('oci_document_size')
        index = json.load(archive.extractfile('index.json'))
        manifests = index.get('manifests', [])
        if len(manifests) != 1 or manifests[0]['digest'] != 'sha256:' + expected_manifest:
            raise Invalid('oci_manifest_pin')
        manifest = json.loads(blob(manifests[0]['digest']))
        config = json.loads(blob(manifest['config']['digest']))
        if config.get('os') != 'linux' or config.get('architecture') != 'amd64':
            raise Invalid('oci_target')
        for layer in manifest['layers']:
            blob(layer['digest'], document=False, expected_size=layer['size'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform-root', required=True)
    for kind in ('workload', 'release', 'runtime', 'desired', 'payload'):
        parser.add_argument('--' + kind, required=True)
    args = vars(parser.parse_args(argv))
    try:
        contract, values, _ = documents(args['platform_root'], args)
        result = payload(args['payload'], values['release'], contract)
        print(json.dumps({'verified': True, 'inventory_sha256': result['inventory_sha256']}))
        return 0
    except Exception:
        print(json.dumps({'verified': False, 'reason_code': 'release_verification_failed'}))
        return 5


if __name__ == '__main__':
    raise SystemExit(main())
