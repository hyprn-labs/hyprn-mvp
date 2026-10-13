"""The document parser lock names exactly the audited wheel, and only that wheel is admitted.

``integration/document-parser.lock.json`` is the machine-readable adoption record; its
identity must equal the identity table and notices of the audited provenance record
``integration/document-parser-provenance.md``. A changed artifact, version, extra or
dependency needs a new audit, so any difference between the two fails here.

These checks read text only; they never install, import or execute the parser. Checks of the
wheel bytes themselves run against a synthetic wheel built here (proving that the verifier
refuses every altered identity), and against the real wheel only when
``HYPRN_MVP_PARSER_WHEEL`` names a local copy:

    HYPRN_MVP_PARSER_WHEEL=<wheel> <contract interpreter> -m pytest \\
        contracts/tests/test_document_parser_adoption.py -k supplied_parser_wheel

The parser image build verifies the wheel bytes unconditionally before installing them.
"""
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
import pytest

REPO = Path(__file__).resolve().parents[2]
LOCK = REPO / 'integration/document-parser.lock.json'
PROVENANCE = REPO / 'integration/document-parser-provenance.md'
LOCK_FORMAT = 'hyprn-mvp.document-parser-lock/1'
LOCK_KEYS = {'format', 'provenance', 'name', 'version', 'python', 'extras', 'dependencies',
             'dependency_resolution', 'wheel', 'licence', 'source'}
WHEEL_KEYS = {'filename', 'size', 'sha256', 'index_host'}
LICENCE_KEYS = {'expression', 'file', 'size', 'sha256'}
SOURCE_KEYS = {'repository', 'tag', 'commit'}
SHA256 = re.compile(r'[0-9a-f]{64}')
WHEEL_VARIABLE = 'HYPRN_MVP_PARSER_WHEEL'


def lock():
    return json.loads(LOCK.read_text(encoding='utf-8'))


def identity_table(text):
    """The provenance identity table, field -> value; exactly one such table exists."""
    sections = re.findall(r'^## Exact identity and origin\n(.*?)(?=^## )', text, re.S | re.M)
    assert len(sections) == 1, 'One identity section required in the provenance record'
    rows = {}
    for line in sections[0].splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if line.startswith('|') and len(cells) == 2 and not set(cells[1]) <= set('-') and cells[0] != 'Field':
            assert cells[0] not in rows, 'Duplicate identity field ' + cells[0]
            rows[cells[0]] = cells[1]
    return rows


def one(pattern, text, what):
    found = re.findall(pattern, text)
    assert len(found) == 1, 'Exactly one ' + what + ' required in the provenance record'
    return found[0]


def provenance_identity(text):
    """Every identity value the audit recorded, read from the provenance record's own text."""
    table = identity_table(text)
    name, version = one(r'\*\*Adopted exact pin: `([A-Za-z0-9_.-]+)==([0-9][0-9A-Za-z.]*)`', text, 'adopted pin')
    python = one(r'\*\*Adopted exact pin: `[^`]+`, Python ([0-9]+\.[0-9]+), no extras\.\*\*', text, 'pin target')
    registry = one(r'\]\((https://[^)\s]+)\)', table['Registry and project'], 'registry link')
    repository = one(r'source `(https://[^`]+)`', table['Registry and project'], 'source repository')
    filename, size = one(r'^`([^`]+\.whl)`, ([0-9][0-9,]*) bytes', table['Artifact'], 'wheel artifact')
    sha256 = one(r'^`([0-9a-f]{64})`$', table['SHA-256'], 'wheel SHA-256')
    tag = one(r'^\[Tag ([^\]]+)\]', table['Source'], 'release tag')
    commit = one(r'commit `([0-9a-f]{40})`', table['Source'], 'source commit')
    licence = one(r'The top-level ([A-Za-z0-9.-]+) LICENSE \(([0-9][0-9,]*) bytes, SHA-256 `([0-9a-f]{64})`\)',
                  text, 'licence notice')
    one(r'\*\*zero additional runtime dependencies\*\*', text, 'dependency closure')
    one(r'with dependency resolution disabled', text, 'install policy')
    registry = urlsplit(registry)
    return dict(name=name, version=version, python=python, extras=[], dependencies=[],
                dependency_resolution=False, registry_path=registry.path,
                wheel=dict(filename=filename, size=int(size.replace(',', '')), sha256=sha256,
                           index_host=registry.hostname),
                licence=dict(expression=licence[0], size=int(licence[1].replace(',', '')), sha256=licence[2]),
                source=dict(repository=repository, tag=tag, commit=commit))


def exact_int(value):
    return type(value) is int and value > 0


def verify_wheel(raw, record):
    """Refuse any wheel whose bytes, file inventory, metadata, closure or licence differ from the lock."""
    wheel = record['wheel']
    if len(raw) != wheel['size']:
        raise ValueError('wheel size differs from the lock')
    if hashlib.sha256(raw).hexdigest() != wheel['sha256']:
        raise ValueError('wheel SHA-256 differs from the lock')
    archive = zipfile.ZipFile(io.BytesIO(raw))
    names = archive.namelist()
    dist_info = record['name'] + '-' + record['version'] + '.dist-info/'
    if len(set(names)) != len(names) or not all(n.startswith((record['name'] + '/', dist_info)) for n in names):
        raise ValueError('wheel holds files outside the package and its metadata')
    rows = list(csv.reader(io.StringIO(archive.read(dist_info + 'RECORD').decode('utf-8'))))
    if sorted(row[0] for row in rows) != sorted(names) or len(rows) != len(names):
        raise ValueError('wheel RECORD does not list exactly the packaged files')
    for name, digest, size in rows:
        if name == dist_info + 'RECORD':
            if digest or size:
                raise ValueError('wheel RECORD lists a digest for itself')
            continue
        content = archive.read(name)
        expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip('=')
        if digest != expected or not size.isdigit() or int(size) != len(content):
            raise ValueError('wheel RECORD digest or size differs for ' + name)
    metadata = BytesParser().parsebytes(archive.read(dist_info + 'METADATA'))
    if (metadata['Name'], metadata['Version']) != (record['name'], record['version']):
        raise ValueError('wheel metadata names another distribution')
    if metadata['License-Expression'] != record['licence']['expression']:
        raise ValueError('wheel licence differs from the lock')
    if record['python'] not in SpecifierSet(metadata['Requires-Python'] or ''):
        raise ValueError('wheel does not support the locked Python')
    environment = {**default_environment(), 'python_version': record['python'],
                   'python_full_version': record['python'] + '.0', 'extra': ''}
    closure = [str(r) for r in map(Requirement, metadata.get_all('Requires-Dist') or [])
               if not r.marker or r.marker.evaluate(environment)]
    if closure != record['dependencies']:
        raise ValueError('wheel has a runtime dependency the lock does not admit')
    licence = archive.read(record['licence']['file'])
    if len(licence) != record['licence']['size'] or hashlib.sha256(licence).hexdigest() != record['licence']['sha256']:
        raise ValueError('wheel licence file differs from the lock')
    return True


def test_documents_parser_adoption_lock_matches_provenance():
    record = lock()
    audited = provenance_identity(PROVENANCE.read_text(encoding='utf-8'))
    assert audited['registry_path'] == '/project/' + record['name'] + '/' + record['version'] + '/'
    for field in ('name', 'version', 'python', 'extras', 'dependencies', 'dependency_resolution', 'source'):
        assert record[field] == audited[field], field
    assert record['wheel'] == audited['wheel']
    assert {k: v for k, v in record['licence'].items() if k != 'file'} == audited['licence']


def test_documents_parser_adoption_lock_is_closed_and_self_consistent():
    record = lock()
    assert set(record) == LOCK_KEYS and record['format'] == LOCK_FORMAT
    assert set(record['wheel']) == WHEEL_KEYS
    assert set(record['licence']) == LICENCE_KEYS
    assert set(record['source']) == SOURCE_KEYS
    assert record['provenance'] == PROVENANCE.relative_to(REPO).as_posix()
    assert record['extras'] == [] and record['dependencies'] == [] and record['dependency_resolution'] is False
    assert exact_int(record['wheel']['size']) and exact_int(record['licence']['size'])
    assert SHA256.fullmatch(record['wheel']['sha256']) and SHA256.fullmatch(record['licence']['sha256'])
    assert record['wheel']['filename'] == record['name'] + '-' + record['version'] + '-py3-none-any.whl'
    assert record['licence']['file'] == record['name'] + '-' + record['version'] + '.dist-info/licenses/LICENSE'
    assert record['source']['tag'] == record['version']
    assert re.fullmatch(r'[0-9a-f]{40}', record['source']['commit'])
    assert re.fullmatch(r'[a-z0-9.-]+', record['wheel']['index_host'])


def test_documents_parser_adoption_provenance_points_to_the_lock():
    text = PROVENANCE.read_text(encoding='utf-8')
    assert text.count('`integration/document-parser.lock.json`') >= 1
    # The provenance record is prose and one identity table; it holds no second machine record.
    assert '```json' not in text


def synthetic_wheel(record, *, files=None, metadata=None, licence=b'synthetic licence\n'):
    """A wheel built here from fragments; it is never the audited parser."""
    name, version = record['name'], record['version']
    dist_info = name + '-' + version + '.dist-info/'
    metadata = metadata if metadata is not None else (
        'Metadata-Version: 2.4\nName: ' + name + '\nVersion: ' + version + '\nLicense-Expression: '
        + record['licence']['expression'] + '\nRequires-Python: >=3.9\n'
        'Requires-Dist: typing_extensions>=4.0; python_version < "3.11"\n'
        'Requires-Dist: cryptography; extra == "crypto"\n\n')
    content = {name + '/__init__.py': b'', dist_info + 'METADATA': metadata.encode(),
               dist_info + 'licenses/LICENSE': licence, **(files or {})}
    rows = [[path, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('='),
             str(len(raw))] for path, raw in content.items()] + [[dist_info + 'RECORD', '', '']]
    text = io.StringIO()
    csv.writer(text, lineterminator='\n').writerows(rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for path, raw in {**content, dist_info + 'RECORD': text.getvalue().encode()}.items():
            archive.writestr(path, raw)
    return buffer.getvalue(), licence


def locked_to(record, raw, licence):
    return {**record, 'wheel': {**record['wheel'], 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
            'licence': {**record['licence'], 'size': len(licence), 'sha256': hashlib.sha256(licence).hexdigest()}}


def test_documents_parser_adoption_wheel_verifier_refuses_every_altered_identity():
    record = lock()
    raw, licence = synthetic_wheel(record)
    synthetic = locked_to(record, raw, licence)
    assert verify_wheel(raw, synthetic)
    with pytest.raises(ValueError, match='size'):
        verify_wheel(raw + b'\0', synthetic)
    with pytest.raises(ValueError, match='SHA-256'):
        verify_wheel(raw[:-1] + bytes([raw[-1] ^ 1]), synthetic)
    with pytest.raises(ValueError, match='differs from the lock'):
        verify_wheel(raw, record)  # The audited identity never admits other bytes.
    dist_info = record['name'] + '-' + record['version'] + '.dist-info/'
    altered = {
        'outside': dict(files={'other/__init__.py': b''}),
        'dependency': dict(metadata='Metadata-Version: 2.4\nName: ' + record['name'] + '\nVersion: '
                           + record['version'] + '\nLicense-Expression: ' + record['licence']['expression']
                           + '\nRequires-Python: >=3.9\nRequires-Dist: requests>=2\n\n'),
        'distribution': dict(metadata='Metadata-Version: 2.4\nName: other\nVersion: ' + record['version']
                             + '\nLicense-Expression: ' + record['licence']['expression'] + '\nRequires-Python: >=3.9\n\n'),
        'licence': dict(metadata='Metadata-Version: 2.4\nName: ' + record['name'] + '\nVersion: '
                        + record['version'] + '\nLicense-Expression: MIT\nRequires-Python: >=3.9\n\n'),
        'python': dict(metadata='Metadata-Version: 2.4\nName: ' + record['name'] + '\nVersion: '
                       + record['version'] + '\nLicense-Expression: ' + record['licence']['expression']
                       + '\nRequires-Python: <3.12\n\n'),
    }
    for case, arguments in altered.items():
        changed, changed_licence = synthetic_wheel(record, **arguments)
        with pytest.raises(ValueError):
            verify_wheel(changed, locked_to(record, changed, changed_licence))
            pytest.fail('altered ' + case + ' admitted')
    # A licence file with other bytes than the locked notice is refused even when the wheel is consistent.
    changed, _ = synthetic_wheel(record, licence=b'other licence\n')
    with pytest.raises(ValueError, match='licence file'):
        verify_wheel(changed, locked_to(record, changed, licence))
    # A RECORD that no longer matches a packaged file is refused.
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(buffer, 'w') as target:
        for item in source.namelist():
            data = source.read(item)
            target.writestr(item, data + b'#' if item == record['name'] + '/__init__.py' else data)
    with pytest.raises(ValueError, match='RECORD'):
        verify_wheel(buffer.getvalue(), locked_to(record, buffer.getvalue(), licence))
    assert dist_info + 'RECORD' in zipfile.ZipFile(io.BytesIO(raw)).namelist()


@pytest.mark.skipif(not os.environ.get(WHEEL_VARIABLE), reason=WHEEL_VARIABLE + ' names no local wheel copy')
def test_supplied_parser_wheel_matches_lock():
    path = Path(os.environ[WHEEL_VARIABLE])
    assert path.is_absolute() and path.is_file() and not path.is_symlink(), WHEEL_VARIABLE + ' must name a regular file'
    assert path.name == lock()['wheel']['filename']
    assert verify_wheel(path.read_bytes(), lock())
