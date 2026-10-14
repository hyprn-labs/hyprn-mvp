"""Frozen execution bundle contract (wire ``ExecutionBundleN``): pure, data-only checks.

One module for everything that makes a bundle admissible: assembling the immutable
bundle from exact model-side and application-side bytes, and every check that admits
or re-admits one (preparation, provenance, retained unit catalog, scientific snapshot,
approach pins, file inventory and paths, result dependencies, the retained-bundle
validator) plus the version predicates that select a frozen envelope and the single
retained pairing table (``RETAINED_PAIRINGS``, ``bundle_family``). The application
(submission, history, export) and integration (launcher, calculation, retained-result
reader, export) share it without loading storage, transport or orchestration.

Depends only on ``contracts``, ``units``, ``scientific_configuration`` and
``approach_closure``. It must not own or import Store/SQLite, the modeling HTTP client,
``Submissions``/dispatch, worker code or candidate code; every module it imports is
bound into ``launcher.execution_source_hashes()`` (both enforced by
``application/tests/test_module_boundaries.py``). Candidate bytes remain inert here.

Errors: an inadmissible bundle raises ``ValueError``; ``closed`` maps a nested contract
shape failure to ``ValueError('Invalid <name>')``. ``verify_dependencies`` keeps the
``ContractError`` of its own schema validation.

Moved from ``execution.py`` (and ``finite``/``verify_dependencies`` from
``result_bindings.py``); bodies unchanged except hoisted imports and the
execution schema compiled once.
"""

import base64
import json
import math
from pathlib import PurePosixPath
from typing import NamedTuple
from .approach_closure import validate_closure
from .contracts import (
    ContractError,
    DomainError,
    canonical,
    check_digest,
    data_json,
    digest,
    raw_hash,
    uid,
    validate,
    validate_execution,
)
from .scientific_configuration import project_scientific_configuration
from .units import (
    UNIT_CATALOG_DIGEST,
    UNIT_ENGINE_SOURCE_SHA256,
    port_units,
    require_engine_unit,
    resolved_model_units,
)

MAX_FILES = 2000
MAX_BYTES = 32 * 1024 * 1024

# ---- Retained record families -------------------------------------------------
#
# The single table of supported retained runs, as (history projection, bundle,
# configuration, model) schema versions. It is closed: a pairing that is not listed is
# unsupported and is never upgraded, aliased or guessed. Readers consult it through
# ``bundle_family`` (per stored bundle) or test membership directly
# (``history.retained_read_integrity``). It is historical support only: producers
# (``assemble_bundle``), authoring admission (``Configurations.require_version_pair``)
# and run admission sets (``validate_retained_bundle``, ``Submissions``, launcher,
# calculation) stay explicit and strict, and the worker image (``results.py``,
# ``worker.py``) keeps its own independent tables.
#
# Version interpretation points for retained runs (adding a version touches exactly these):
# 1. ``RETAINED_PAIRINGS`` below (history/bundle/configuration/model pairing).
# 2. ``validate_retained_bundle`` here: its admission set and the per-bundle shape branches
#    (bundle 5 pre-units closure, bundles 6/8 frozen wrapper 5/7 and file roles, bundle 8
#    exact model/descriptive branch).
# 3. ``assemble_bundle`` here (producer): configuration -> bundle version.
# 4. ``history``: the ``RunHistory<N>`` contract names, the history-6 identity check and the
#    bundle-8 ``model_schema_version`` field (see its module docstring).
# 5. ``units.port_units`` for a new model version (Model1/2 literal, Model3/4 resolved).
# 6. Outside the application package, by design: the contracts, the worker image readers
#    and the launcher/calculation admission sets.
RETAINED_PAIRINGS = frozenset(
    {
        ('1', '1', '1', '1'),
        ('1', '2', '1', '1'),
        ('1', '3', '2', '1'),
        ('2', '4', '3', '1'),
        ('2', '4', '3', '2'),
        ('3', '5', '4', '1'),
        ('3', '5', '4', '2'),
        ('4', '6', '4', '2'),
        ('4', '6', '4', '3'),
        ('6', '8', '4', '2'),
        ('6', '8', '4', '3'),
        ('6', '8', '4', '4'),
    }
)


class UnsupportedRetainedVersion(ValueError):
    """A stored bundle version that ``RETAINED_PAIRINGS`` does not list."""


class BundleFamily(NamedTuple):
    """What one retained bundle version carries, read from ``RETAINED_PAIRINGS``.

    ``history`` is the projection version ``History.read`` reports; ``configuration`` the only
    configuration version the bundle carries; ``models`` the model versions retained with it.
    """

    history: str
    configuration: str
    models: frozenset

    @property
    def carries_dependencies(self):
        """Configuration 2-4: modeling-configuration.json and result-dependencies.json."""
        return self.configuration != '1'

    @property
    def carries_approach(self):
        """Configuration 4: approach manifest pins and the frozen approach closure."""
        return self.configuration == '4'


def _families(pairings):
    families = {}
    for history, bundle, configuration, model in sorted(pairings):
        known = families.setdefault(bundle, (history, configuration, set()))
        if known[:2] != (history, configuration):
            raise ValueError(
                'A bundle version must map to one history and one configuration version'
            )
        known[2].add(model)
    return {bundle: BundleFamily(h, c, frozenset(m)) for bundle, (h, c, m) in families.items()}


_FAMILIES = _families(RETAINED_PAIRINGS)
_INPUT_FAMILIES = {**_FAMILIES, '9': BundleFamily('7', '4', frozenset({'2', '3', '4'}))}
# Output format is independent of the immutable input bundle family.
CURRENT_RESULT_PAIRINGS = frozenset(
    ('7', '10', configuration, model)
    for _, bundle, configuration, model in RETAINED_PAIRINGS if bundle != '1'
)
RESULT_PAIRINGS = RETAINED_PAIRINGS | CURRENT_RESULT_PAIRINGS


def result_history_version(bundle_version, result_version):
    if result_version == '2' and bundle_version == '10':
        return '7'
    if result_version == '1' and bundle_version not in ('9', '10'):
        return bundle_family(bundle_version).history
    raise UnsupportedRetainedVersion('Unsupported bundle/result version pairing')


def bundle_layout(manifest):
    version = manifest.get('schema_version')
    if version == '10':
        layout = manifest.get('input_schema_version')
        if layout not in ('2', '3', '4', '5', '6', '8', '9'):
            raise UnsupportedRetainedVersion('Unsupported bundle input layout')
        return layout
    return version


def bundle_family(version, input_schema_version=None):
    """The retained family of bundle ``version``; ``UnsupportedRetainedVersion`` if unlisted."""
    if version == '10':
        layout = bundle_layout(
            dict(schema_version=version, input_schema_version=input_schema_version)
        )
        return _INPUT_FAMILIES[layout]
    family = _FAMILIES.get(version) if isinstance(version, str) else None
    if family is None:
        raise UnsupportedRetainedVersion('Unsupported retained bundle version')
    return family


def closed(name, value):
    try:
        validate(name, value, remote=True)
    except DomainError:
        raise ValueError('Invalid ' + name) from None


def executable_digest(prepared):
    return digest(
        dict(
            protocol=prepared['entrypoint']['protocol'],
            model_digest=prepared['model_digest'],
            configuration_digest=prepared['configuration_digest'],
            generator_identity=prepared['generator_identity'],
            files=sorted(
                [
                    {k: f[k] for k in ('path', 'size', 'sha256')}
                    for f in prepared['files']
                    if f['path'].startswith('generated/')
                ],
                key=lambda f: f['path'],
            ),
        )
    )


def safe_path(path):
    if not isinstance(path, str) or not path or '\\' in path or '\x00' in path:
        raise ValueError('Invalid bundle path')
    p = PurePosixPath(path)
    if (
        p.is_absolute()
        or any(v in ('', '.', '..') for v in path.split('/'))
        or len(p.parts) > 16
        or len(path) > 512
    ):
        raise ValueError('Invalid bundle path')
    return path


def validate_assumption_closure(config, model):
    """Check frozen owners and the complete exact-version citation union."""
    if model['schema_version'] == '2' and config['schema_version'] not in ('3', '4'):
        raise ValueError('Invalid configuration/model version pairing')
    if config['schema_version'] not in ('3', '4'):
        return
    required = set(config['general_context_evidence_version_ids'])
    instances = unique(model['instances'], 'instance_id')
    for rows, is_model in ((model.get('assumptions', []), True), (config['assumptions'], False)):
        unique(rows, 'assumption_id')
        for row in rows:
            if is_model:
                owner = row['owner']
                if owner['kind'] == 'instance' and (
                    owner['instance_id'] not in instances
                    or owner['instance_id'] == model['root_instance_id']
                ):
                    raise ValueError('Invalid assumption owner')
            pairs = [(l['evidence_version_id'], l['relation']) for l in row['evidence_links']]
            if len(set(pairs)) != len(pairs):
                raise ValueError('Duplicate assumption relationship')
            required.update(v for v, _ in pairs)
    for item in config['inputs']:
        required.update(item['provenance']['evidence_version_ids'])
    for item in config['criteria']:
        required.update(item['evidence_version_ids'])
    snapshots = unique(config['evidence_snapshots'], 'evidence_version_id')
    if len(required) > 1000 or list(snapshots) != sorted(required):
        raise ValueError('Exact evidence closure required')
    for row in snapshots.values():
        if (
            row.get('evidence_schema_version') in ('2', '3')
            and row['resource_scope']['study_id'] != config['study_id']
        ):
            raise ValueError('Foreign frozen evidence scope')
        if row.get('evidence_schema_version') == '3':
            if (
                row['study_id'] != config['study_id']
                or row['parent_evidence_version_id'] == row['evidence_version_id']
            ):
                raise ValueError('Invalid evidence owner or parent')
            for label in row['recorded_context']['resource_labels']:
                if label['kind'] == 'study' and label['resource_id'] != config['study_id']:
                    raise ValueError('Foreign recorded study label')


def uses_typed_units(model):
    return model['schema_version'] == '3' or (
        model['schema_version'] == '4'
        and any(isinstance(p['units'], dict) for d in model['definitions'] for p in d['ports'])
    )


def model_capabilities(model):
    return (
        ['flat_explicit_scalar']
        + (['unit_declarations/1'] if uses_typed_units(model) else [])
        + (['quantity_definitions/1'] if model['schema_version'] == '4' else [])
    )


def uses_polish_envelope(model, closure):
    return (
        model['schema_version'] == '4' or closure is not None and closure['schema_version'] == '3'
    )


def uses_units_envelope(model, closure):
    return model['schema_version'] == '3' or (
        model['schema_version'] == '2'
        and closure is not None
        and any(m['schema_version'] == '3' for m in closure['models'])
    )


def frozen_version(model, closure):
    return (
        '8'
        if closure is not None and closure['schema_version'] == '4'
        else '7'
        if uses_polish_envelope(model, closure)
        else '5'
        if uses_units_envelope(model, closure)
        else '4'
    )


def validate_frozen_configuration(frozen):
    version = frozen.get('schema_version')
    if version not in (None, '4', '5', '7', '8'):
        raise ValueError('Unsupported frozen configuration version')
    closed('FrozenConfiguration' + (version or 'Legacy'), frozen)
    validate_scientific_snapshot(frozen)
    if frozen['configuration']['schema_version'] == '4' and version != frozen_version(
        frozen['model_snapshot'], frozen['approach_closure']
    ):
        raise ValueError('Frozen descriptive branch mismatch')


def validate_scientific_snapshot(snapshot):
    """Validate retained model/configuration/closure without inventing storage context.

    Raw portable and launcher readers have no study_revision or Frozen wrapper.
    Submission and stored-history callers must use validate_frozen_configuration.
    """
    frozen = snapshot
    config = frozen['configuration']
    model = frozen['model_snapshot']
    closed('ModelRevisionRead4', model)
    closed('ConfigurationRevision', config)
    if model['schema_version'] in ('3', '4'):
        if config['schema_version'] != '4':
            raise ValueError('Model3/4 requires Configuration4')
        resolved_model_units(model)
    check_digest(model)
    check_digest(config)
    if (
        config['model_id'] != model['model_id']
        or config['model_revision_id'] != model['model_revision_id']
    ):
        raise ValueError('Configuration/model mismatch')
    for source in model['source_files']:
        if raw_hash(base64.b64decode(source['bytes'], validate=True)) != source['sha256']:
            raise ValueError('Frozen source mismatch')
    validate_assumption_closure(config, model)
    if config['schema_version'] == '4':
        if 'approach_closure' not in frozen:
            raise ValueError('Missing frozen approach field')
        validate_approach_binding(config, model, frozen['approach_closure'])


def validate_approach_binding(config, model, closure):
    """Pure exact pin validation, shared by submission and retained admission."""
    if model['schema_version'] not in ('2', '3', '4'):
        raise ValueError('Configuration4 requires ModelRevision2/3/4')
    pin = config['approach_binding']
    if pin is None:
        if closure is not None:
            raise ValueError('Unlinked configuration has approach closure')
        return
    if closure is None:
        raise ValueError('Missing approach closure')
    validate_closure(closure, study_id=config['study_id'])
    if (
        closure['root_approach_version_id'] != pin['approach_version_id']
        or closure['root_approach_digest'] != pin['approach_digest']
        or closure['digest'] != pin['closure_digest']
    ):
        raise ValueError('Approach closure pin mismatch')
    version = next(
        v
        for v in closure['approach_versions']
        if v['approach_version_id'] == pin['approach_version_id']
    )
    if version['approach_id'] != pin['approach_id']:
        raise ValueError('Approach family mismatch')
    content = version['content']
    used = {ref['binding_id'] for step in content['steps'] for ref in step['implementation_refs']}
    matching = {
        b['binding_id']
        for b in content['model_bindings']
        if b['binding_id'] in used
        and b['model_id'] == model['model_id']
        and b['model_revision_id'] == model['model_revision_id']
    }
    retained = next(
        (m for m in closure['models'] if m['model_revision_id'] == model['model_revision_id']), None
    )
    if not matching or canonical(retained) != canonical(model):
        raise ValueError('Approach model correspondence mismatch')
    if pin['case_id'] is not None:
        case = next((c for c in content['cases'] if c['case_id'] == pin['case_id']), None)
        if case is None or case['binding_id'] not in matching:
            raise ValueError('Approach case correspondence mismatch')


def verify_files(descriptors, files):
    if not descriptors or len(descriptors) > MAX_FILES or len(files) != len(descriptors):
        raise ValueError('Bundle file inventory mismatch')
    seen = set()
    ids = set()
    total = 0
    for item in descriptors:
        path = safe_path(item['path'])
        if path in seen:
            raise ValueError('Duplicate bundle path')
        if 'file_id' in item:
            if item['file_id'] in ids:
                raise ValueError('Duplicate file identity')
            ids.add(item['file_id'])
        seen.add(path)
        raw = files.get(path)
        if (
            type(item['size']) is not int
            or item['size'] < 0
            or not isinstance(raw, bytes)
            or len(raw) != item['size']
            or raw_hash(raw) != item['sha256']
        ):
            raise ValueError('Raw bundle bytes mismatch')
        total += len(raw)
        if total > MAX_BYTES:
            raise ValueError('Bundle exceeds expanded size bound')
    if seen != set(files):
        raise ValueError('Undeclared bundle file')
    for path in seen:
        if any(str(parent) in seen for parent in PurePosixPath(path).parents):
            raise ValueError('Bundle file/directory collision')


def assemble_bundle(run_id, prepared, prepared_files, frozen, selected, dependencies=None):
    """Combine exact model-side and app-side bytes; no candidate imports or fetches."""
    from uuid import UUID

    if str(UUID(run_id)) != run_id:
        raise ValueError('Invalid run identity')
    validate_preparation(prepared, prepared_files, frozen)
    check_digest(prepared, 'prepared_digest')
    verify_files(prepared['files'], prepared_files)
    config = frozen['configuration']
    model = frozen['model_snapshot']
    scientific = project_scientific_configuration(config)
    check_digest(config)
    check_digest(model)
    for key, value in dict(
        model_id=model['model_id'],
        model_revision_id=model['model_revision_id'],
        model_digest=model['digest'],
        configuration_revision_id=config['configuration_revision_id'],
        configuration_digest=scientific['digest'],
    ).items():
        if prepared.get(key) != value:
            raise ValueError('Prepared model/configuration binding mismatch')
    if (
        config['model_id'] != model['model_id']
        or config['model_revision_id'] != model['model_revision_id']
    ):
        raise ValueError('Configuration/model mismatch')
    if prepared_files['model.json'] != canonical(model):
        raise ValueError('Prepared model differs from frozen configuration')
    for source in model['source_files']:
        raw = base64.b64decode(source['bytes'], validate=True)
        if (
            raw_hash(raw) != source['sha256']
            or prepared_files.get('sources/' + source['sha256'] + '.py') != raw
        ):
            raise ValueError('Frozen source mismatch')
    requirements = {(r['name'].lower(), r['version']) for r in prepared['dependency_requirements']}
    installed_dependencies = {(r['name'].lower(), r['version']) for r in selected['dependencies']}
    if not requirements <= installed_dependencies:
        raise ValueError('Unresolved model dependency')
    runtime = selected['runtime']
    if set(runtime) != {
        'image_digest',
        'architecture',
        'python_version',
        'worker_entrypoint',
        'policy_digest',
    }:
        raise ValueError('Incomplete selected runtime')
    if (
        not runtime['image_digest'].startswith('sha256:')
        or len(runtime['image_digest']) != 71
        or len(runtime['policy_digest']) != 64
    ):
        raise ValueError('Unpinned selected runtime')
    files = dict(prepared_files)
    additions = {
        'preparation.json': canonical(prepared),
        'configuration.json': canonical(config),
        'context.json': canonical(config['context_snapshot']),
        'evidence/index.json': canonical(config['evidence_snapshots']),
        **selected['files'],
    }
    if config['schema_version'] == '4' and frozen['approach_closure'] is not None:
        additions['approach/closure.json'] = canonical(frozen['approach_closure'])
    if any(p.startswith('approach/') for p in (*prepared_files, *selected['files'])):
        raise ValueError('Reserved approach path collision')
    if config['schema_version'] in ('2', '3', '4'):
        if dependencies is None:
            raise ValueError('Missing resolved result dependencies')
        verify_dependencies(config, dependencies)
        additions.update(
            {
                'modeling-configuration.json': canonical(scientific),
                'result-dependencies.json': canonical(dependencies),
            }
        )
    elif dependencies is not None:
        raise ValueError('Legacy configuration cannot carry result dependencies')
    if set(files) & set(additions):
        raise ValueError('Reserved application bundle path collision')
    for path, raw in additions.items():
        safe_path(path)
        if not isinstance(raw, bytes):
            raise ValueError('Exact byte payload required')
    files.update(additions)
    for dep in selected['dependencies']:
        if dep['lock_path'] not in files or not dep['lock_path'].startswith('locks/'):
            raise ValueError('Missing resolved lock')
    for license_path in selected['licenses']:
        if license_path not in files or not license_path.startswith('licenses/'):
            raise ValueError('Missing license bytes')
    descriptors = [
        dict(
            path=path,
            size=len(raw),
            sha256=raw_hash(raw),
            media_type='text/x-python'
            if path.endswith('.py')
            else 'application/json'
            if path.endswith('.json')
            else 'text/plain',
            role='source'
            if path.startswith('sources/')
            else {
                'modeling-configuration.json': 'modeling_configuration',
                'result-dependencies.json': 'result_dependencies',
            }.get(path, path.split('/')[0].split('.')[0]),
        )
        for path, raw in sorted(files.items())
    ]
    verify_files(descriptors, files)
    manifest = dict(
        schema_version='2',
        bundle_id=uid(),
        run_id=run_id,
        prepared_digest=prepared['prepared_digest'],
        model_revision_id=model['model_revision_id'],
        configuration_revision_id=config['configuration_revision_id'],
        model_digest=model['digest'],
        configuration_digest=config['digest'],
        files=descriptors,
        generator=prepared['generator_identity'],
        dependencies=selected['dependencies'],
        runtime=runtime,
        entrypoint=prepared['entrypoint'],
        executable_content_digest=prepared['executable_content_digest'],
        required_capabilities=prepared['required_capabilities'],
        licenses=[
            *prepared['license_notices'],
            *[dict(kind='runtime', path=p) for p in selected['licenses']],
        ],
        result_protocol_version=prepared['result_protocol_version'],
    )
    if config['schema_version'] in ('2', '3', '4'):
        raw = files['result-dependencies.json']
        manifest.update(
            schema_version='6'
            if frozen.get('schema_version') == '5'
            else {'2': '3', '3': '4', '4': '5'}[config['schema_version']],
            modeling_configuration_digest=scientific['digest'],
            result_dependencies=dict(
                path='result-dependencies.json', sha256=raw_hash(raw), size=len(raw)
            ),
        )
    if config['schema_version'] == '4':
        pin = config['approach_binding']
        manifest.update(
            approach_digest=pin['approach_digest'] if pin else None,
            approach_closure_digest=pin['closure_digest'] if pin else None,
        )
    if uses_polish_envelope(model, frozen.get('approach_closure')):
        manifest.update(schema_version='8', model_schema_version=model['schema_version'])
    if frozen.get('schema_version') == '8':
        manifest.update(schema_version='9', model_schema_version=model['schema_version'])
    if prepared['schema_version'] == '3':
        manifest.update(input_schema_version=manifest['schema_version'], schema_version='10')
    manifest['bundle_digest'] = digest(manifest)
    validate_bundle_shape(manifest)
    return dict(manifest=manifest, files=files)


def validate_preparation(prepared, files, frozen, *, raw_snapshot=False):
    """Validate the closed real manifest, ancestry, raw bytes and frozen bindings."""
    if prepared.get('schema_version') not in ('2', '3'):
        raise ValueError('Unsupported preparation version; create a new schema2 run command')
    try:
        _validate_preparation(prepared, files, frozen, raw_snapshot=raw_snapshot)
    except (KeyError, TypeError, IndexError, RecursionError, UnicodeError) as error:
        raise ValueError('Invalid prepared program binding') from error


def _validate_preparation(prepared, files, frozen, *, raw_snapshot=False):
    closed('PreparedModelArtifactRead3', prepared)
    check_digest(prepared, 'prepared_digest')
    verify_files(prepared['files'], files)
    model = frozen['model_snapshot']
    config = frozen['configuration']
    if raw_snapshot:
        expected = {'model_snapshot', 'configuration'} | (
            {'approach_closure'} if config.get('schema_version') == '4' else set()
        )
        if set(frozen) != expected:
            raise ValueError('Invalid raw scientific snapshot')
        validate_scientific_snapshot(frozen)
    else:
        validate_frozen_configuration(frozen)
    scientific = project_scientific_configuration(config)
    package = prepared['model_package_manifest']
    check_digest(package)
    capabilities = model_capabilities(model)
    if prepared['required_capabilities'] != capabilities:
        raise ValueError('Unsupported model capability')
    if package['schema_version'] != model['schema_version']:
        raise ValueError('Model package version mismatch')
    if (
        package['model_id'] != model['model_id']
        or package['model_revision_id'] != model['model_revision_id']
        or not package['revisions']
        or package['revisions'][-1] != model
        or package['required_capabilities'] != prepared['required_capabilities']
        or model['required_capabilities'] != prepared['required_capabilities']
        or scientific['required_capabilities'] != prepared['required_capabilities']
    ):
        raise ValueError('Model package binding mismatch')
    package_files = {}
    parent = None
    seen = set()
    for pin in package['revisions']:
        check_digest(pin)
        if (
            pin['model_id'] != model['model_id']
            or pin['parent_model_revision_id'] != parent
            or pin['model_revision_id'] in seen
        ):
            raise ValueError('Model ancestry mismatch')
        parent = pin['model_revision_id']
        seen.add(parent)
        package_files['revisions/' + parent + '.json'] = canonical(pin)
        for source in pin['source_files']:
            raw = base64.b64decode(source['bytes'], validate=True)
            if raw_hash(raw) != source['sha256']:
                raise ValueError('Package source hash mismatch')
            package_files['sources/' + source['sha256'] + '.py'] = raw
    verify_files(package['files'], package_files)
    expected = {'model.json': canonical(model)}
    expected.update(
        {
            'sources/' + s['sha256'] + '.py': base64.b64decode(s['bytes'], validate=True)
            for s in model['source_files']
        }
    )
    if any(files.get(p) != raw for p, raw in expected.items()):
        raise ValueError('Prepared frozen content mismatch')
    if {p for p in files if p.startswith('sources/')} != {
        p for p in expected if p.startswith('sources/')
    }:
        raise ValueError('Undeclared frozen source')
    for key, value in dict(
        model_id=model['model_id'],
        model_revision_id=model['model_revision_id'],
        model_digest=model['digest'],
        configuration_revision_id=config['configuration_revision_id'],
        configuration_digest=scientific['digest'],
    ).items():
        if prepared[key] != value:
            raise ValueError('Prepared configuration binding mismatch')
    if (
        config['model_id'] != model['model_id']
        or config['model_revision_id'] != model['model_revision_id']
    ):
        raise ValueError('Configuration/model mismatch')
    if prepared['executable_content_digest'] != executable_digest(prepared):
        raise ValueError('Executable content digest mismatch')
    inventory = {f['path']: f for f in prepared['files']}
    if list(inventory) != sorted(inventory):
        raise ValueError('Prepared inventory is not sorted')
    for path, descriptor in inventory.items():
        expected_role = (
            'generated'
            if path.startswith('generated/')
            else 'source'
            if path.startswith('sources/')
            else 'model'
            if path == 'model.json'
            else None
        )
        if expected_role and descriptor['role'] != expected_role:
            raise ValueError('Prepared file role mismatch')
    entry = prepared['entrypoint']
    paths = [entry[k] for k in ('module_path', 'bindings_path', 'source_map_path')]
    if len(set(paths)) != 3 or any(
        p not in files or inventory[p]['role'] != 'generated' for p in paths
    ):
        raise ValueError('Missing generated entrypoint, bindings or source line mapping')
    bindings = data_json(files[entry['bindings_path']])
    closed('ProgramBindings', bindings)
    definitions = unique(model['definitions'], 'definition_version_id')
    instances = unique(model['instances'], 'instance_id')
    components = unique(bindings['components'], 'component_id')
    unique(bindings['components'], 'path')
    observed = unique(bindings['components'], 'instance_id')
    if set(observed) != set(instances):
        raise ValueError('Component observation coverage mismatch')
    ports = {}
    for iid, instance in instances.items():
        definition = definitions[instance['definition_version_id']]
        for pid, port in unique(definition['ports'], 'port_id').items():
            if port['definition_version_id'] != definition['definition_version_id']:
                raise ValueError('Port owner mismatch')
            ports[(iid, pid)] = port
    bound_units = port_units(model)

    def engine_unit(target):
        return bound_units[(target[0], instances[target[0]]['definition_version_id'], target[1])]

    incoming = set()
    for wire in model['connections']:
        src, tgt = port_key(wire['source_ref']), port_key(wire['target_ref'])
        if (
            ports[src]['direction'] != 'output'
            or ports[tgt]['direction'] != 'input'
            or tgt in incoming
        ):
            raise ValueError('Invalid frozen connection reference')
        incoming.add(tgt)
    free = {key for key, p in ports.items() if p['direction'] == 'input'} - incoming
    outputs = {key for key, p in ports.items() if p['direction'] == 'output'}
    all_paths = set()
    all_targets = set()
    for name, expected_targets in [('inputs', free), ('outputs', outputs)]:
        targets = set()
        for binding in bindings[name]:
            target = port_key(binding['target'])
            component = components[binding['component_id']]
            if target in all_targets or binding['path'] in all_paths:
                raise ValueError('Duplicate observation binding')
            if (
                target not in expected_targets
                or binding['units'] != engine_unit(target)
                or component['instance_id'] != target[0]
                or binding['path'].rsplit('.', 1)[0] != component['path']
            ):
                raise ValueError('Invalid frozen observation binding')
            targets.add(target)
            all_targets.add(target)
            all_paths.add(binding['path'])
        if targets != expected_targets:
            raise ValueError('Incomplete observation binding')
    config_targets = [port_key(v['target']) for v in config['inputs']]
    if len(set(config_targets)) != len(config_targets) or set(config_targets) != free:
        raise ValueError('Configuration free input coverage mismatch')
    # Unit conversion remains the native runtime's responsibility; the app only
    # validates typed binding units against frozen port declarations.
    for criterion in config['criteria']:
        if port_key(criterion['target']) not in outputs:
            raise ValueError('Unknown criterion output')
    mapping = data_json(files[entry['source_map_path']])
    closed('ProgramSourceMap', mapping)
    owners = set()
    for row in mapping['entries']:
        iid = row['instance_id']
        definition = definitions[instances[iid]['definition_version_id']]
        source = row['source_sha256']
        owner = (iid, source)
        if owner in owners:
            raise ValueError('Duplicate source mapping')
        owners.add(owner)
        if (
            row['definition_version_id'] != definition['definition_version_id']
            or source not in definition['source_refs']
            or row['source_path'] != 'sources/' + source + '.py'
            or raw_hash(files[row['source_path']]) != source
            or inventory[row['generated_path']]['role'] != 'generated'
            or not row['generated_path'].endswith('.py')
            or not 1
            <= row['generated_line_start']
            <= row['generated_line_end']
            <= len(files[row['generated_path']].splitlines())
        ):
            raise ValueError('Invalid frozen source ownership/range')
    if owners != {
        (iid, s)
        for iid, i in instances.items()
        for s in definitions[i['definition_version_id']]['source_refs']
    }:
        raise ValueError('Incomplete source mapping')
    validate_provenance(prepared, files, inventory)
    if uses_typed_units(model):
        validate_unit_catalog(prepared, files, config, model, engine_unit)
    notices = prepared['license_notices']
    if len({n['path'] for n in notices}) != len(notices):
        raise ValueError('Duplicate notice')
    for notice in notices:
        if notice['path'] not in files or inventory[notice['path']]['role'] != 'license':
            raise ValueError('Missing notice bytes')
    author = b'\n'.join(files[n['path']] for n in notices if n['kind'] == 'model_author')
    if any(n.encode() not in author for n in package['license_notices']):
        raise ValueError('Missing model author notice')


def unique(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate ' + key)
    return result


def port_key(ref):
    return ref['instance_id'], ref['port_id']


def validate_provenance(prepared, files, inventory):
    identity = prepared['generator_identity']
    path = identity['provenance_path']
    if inventory[path]['role'] != 'provenance':
        raise ValueError('Invalid provenance role')
    provenance = data_json(files[path])
    closed('ProgramProvenance', provenance)
    for key, role in [
        ('source_archive', 'source_archive'),
        ('adapter_source', 'adapter'),
        ('runtime_lock', 'runtime_lock'),
    ]:
        if provenance[key]['role'] != role:
            raise ValueError('Invalid provenance inventory role')
    rows = [provenance[k] for k in ('source_archive', 'adapter_source', 'runtime_lock')]
    for key in ('upstream_files', 'patched_files', 'applied_patches'):
        unique(provenance[key], 'path')
        rows.extend(provenance[key])
    upstream = {r['path'] for r in provenance['upstream_files']}
    patched = {r['path'] for r in provenance['patched_files']}
    if not upstream or not patched or upstream & patched:
        raise ValueError('Original/patched provenance overlap')
    for row in rows:
        descriptor = inventory[row['path']]
        if any(descriptor[k] != row[k] for k in ('sha256', 'size')):
            raise ValueError('Provenance raw file mismatch')
    if provenance['adapter_source'] not in provenance['patched_files']:
        raise ValueError('Adapter source missing from patched inventory')
    if (
        identity['source_commit'] != provenance['source_commit']
        or identity['source_archive_sha256'] != provenance['source_archive']['sha256']
        or identity['adapter_version'] != provenance['adapter_version']
    ):
        raise ValueError('Provenance identity mismatch')
    patched = provenance['patched_files']
    for key, rows in [
        ('generator_digest', [r for r in patched if r['role'] == 'generator']),
        ('template_digest', [r for r in patched if r['role'] == 'template']),
        ('adapter_digest', [r for r in patched if r['role'] not in ('generator', 'template')]),
    ]:
        if not rows or digest(rows) != identity[key]:
            raise ValueError('Provenance source identity mismatch')


def validate_unit_catalog(prepared, files, config, model, engine_unit):
    """Validate the retained build-time table, never parse physical expressions.

    The published catalog uses its generator's JSON encoding, distinct from
    application RFC8785 digests. Its pinned hash authenticates every pair/factor.
    """
    provenance = data_json(files[prepared['generator_identity']['provenance_path']])
    catalogs = []
    fields = {
        'catalog_digest',
        'engine',
        'version',
        'source_sha256',
        'supported_units',
        'linear_pairs',
    }
    # Prepared2 + unit_declarations/1 retains exactly one trusted catalog among
    # declared provenance helpers. Native filenames are never an app contract.
    for row in provenance['patched_files']:
        if row['role'] != 'model_helper':
            continue
        raw = files[row['path']]
        if len(raw) > 16384:
            continue
        if len(raw) != row['size'] or raw_hash(raw) != row['sha256']:
            raise ValueError('Retained catalog provenance mismatch')
        try:
            catalog = data_json(raw)
        except ValueError:
            continue  # Other helpers may be inert source text.
        if not isinstance(catalog, dict) or 'catalog_digest' not in catalog:
            continue
        if (
            set(catalog) != fields
            or catalog['catalog_digest'] != UNIT_CATALOG_DIGEST
            or catalog['engine'] != 'OpenMDAO'
            or catalog['version'] != '3.45.1'
            or catalog['source_sha256'] != UNIT_ENGINE_SOURCE_SHA256
        ):
            raise ValueError('Unsupported retained unit catalog')
        payload = json.dumps(
            {k: v for k, v in catalog.items() if k != 'catalog_digest'},
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
        ).encode()
        if raw_hash(payload) != UNIT_CATALOG_DIGEST:
            raise ValueError('Retained unit catalog digest mismatch')
        catalogs.append(catalog)
    if len(catalogs) != 1:
        raise ValueError('Exactly one authenticated retained unit catalog required')
    catalog = catalogs[0]
    pairs = {(a, b): factor for a, b, factor, offset in catalog['linear_pairs'] if offset == 0}
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    typed_targets = {
        (i['instance_id'], p['port_id']): isinstance(p['units'], dict)
        for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports']
    }

    def factor(source, destination):
        require_engine_unit(source)
        require_engine_unit(destination)
        if (source, destination) not in pairs:
            raise ValueError('Incompatible frozen units')
        return pairs[(source, destination)]

    for wire in model['connections']:
        factor(engine_unit(port_key(wire['source_ref'])), engine_unit(port_key(wire['target_ref'])))
    for item in config['inputs']:
        destination = engine_unit(port_key(item['target']))
        expected = factor(item['units'], destination)
        binding = item.get('result_binding')
        if binding is not None:
            conversion = binding['conversion']
            if (
                conversion['policy'] != 'openmdao-linear-catalog-1'
                or conversion['catalog_digest']
                != (
                    UNIT_CATALOG_DIGEST
                    if model['schema_version'] == '3' or typed_targets[port_key(item['target'])]
                    else digest(catalog)
                )
                or conversion['source_units'] != item['units']
                or conversion['destination_units'] != destination
                or conversion['factor'] != expected
            ):
                raise ValueError('Retained conversion interpretation mismatch')
    for criterion in config['criteria']:
        factor(engine_unit(port_key(criterion['target'])), criterion['units'])


def validate_bundle_shape(manifest):
    # The execution contract is read and compiled once per process (contracts).
    try:
        validate_execution('ExecutionBundleRead10', manifest)
    except ContractError:
        raise ValueError('Invalid execution bundle manifest') from None


def validate_retained_bundle(bundle, request, frozen, *, raw_snapshot=False):
    manifest = bundle['manifest']
    files = bundle['files']
    # Admission (explicit, strict): bundle 1 predates retained re-admission.
    if manifest.get('schema_version') not in ('2', '3', '4', '5', '6', '8', '10'):
        raise ValueError('Unsupported bundle version; create a new run command')
    validate_bundle_shape(manifest)
    check_digest(manifest, 'bundle_digest')
    verify_files(manifest['files'], files)
    version = bundle_layout(manifest)
    family = bundle_family(manifest['schema_version'], manifest.get('input_schema_version'))
    if raw_snapshot:
        expected = {'model_snapshot', 'configuration'} | (
            {'approach_closure'} if family.carries_approach else set()
        )
        if set(frozen) != expected:
            raise ValueError('Invalid raw scientific snapshot')
    model = frozen['model_snapshot']
    config = frozen['configuration']
    closed('ModelRevisionRead4', model)
    closed('ConfigurationRevision', config)
    if config.get('schema_version') != family.configuration:
        raise ValueError('Configuration version does not match bundle')
    if family.carries_approach:
        closure = frozen.get('approach_closure')
        if version not in ('8', '9') and uses_polish_envelope(model, closure):
            raise ValueError('Descriptive bundle downgrade')
        if version == '5':
            closed('ModelRevision2', model)
            if closure is not None:
                closed('ApproachClosurePreUnits', closure)
        elif version in ('8', '9'):
            if (
                (version == '8' and not uses_polish_envelope(model, closure))
                or manifest['model_schema_version'] != model['schema_version']
            ):
                raise ValueError('Bundle8 exact model/descriptive branch mismatch')
            if closure is not None:
                closed('ApproachClosure4' if version == '9' else 'ApproachClosure3', closure)
        elif not uses_units_envelope(model, closure):
            raise ValueError('Invalid bundle6 version pairing')
        elif model.get('schema_version') == '2':
            closed('ApproachClosureWithModel3', closure)
    if version in ('6', '8', '9'):
        if model['schema_version'] not in family.models or (
            not raw_snapshot
            and frozen.get('schema_version') != {'6': '5', '8': '7', '9': '8'}[version]
        ):
            raise ValueError('Invalid bundle6 version pairing')
        for row in manifest['files']:
            path = row['path']
            role = (
                'source'
                if path.startswith('sources/')
                else {
                    'modeling-configuration.json': 'modeling_configuration',
                    'result-dependencies.json': 'result_dependencies',
                }.get(path, path.split('/')[0].split('.')[0])
            )
            if row['role'] != role:
                raise ValueError('Bundle6 file role mismatch')
    elif model['schema_version'] in ('3', '4') or frozen.get('schema_version') in ('5', '7'):
        raise ValueError('Invalid historical bundle version pairing')
    if (
        manifest['bundle_digest'] != request['bundle_digest']
        or manifest['run_id'] != request['run_id']
    ):
        raise ValueError('Stored bundle changed against immutable request')
    prepared = data_json(files['preparation.json'])
    validate_preparation(
        prepared,
        {f['path']: files[f['path']] for f in prepared['files']},
        frozen,
        raw_snapshot=raw_snapshot,
    )
    for key in (
        'prepared_digest',
        'model_revision_id',
        'configuration_revision_id',
        'model_digest',
        'entrypoint',
        'executable_content_digest',
        'required_capabilities',
        'result_protocol_version',
    ):
        if manifest[key] != prepared[key]:
            raise ValueError('Stored preparation binding changed')
    if manifest['generator'] != prepared['generator_identity']:
        raise ValueError('Stored generator changed')
    config = frozen['configuration']
    if request.get('scope', config['study_id']) != config['study_id']:
        raise ValueError('Stored request scope mismatch')
    scientific = project_scientific_configuration(config)
    if (
        manifest['configuration_digest'] != config['digest']
        or prepared['configuration_digest'] != scientific['digest']
    ):
        raise ValueError('Stored configuration digest changed')
    if family.carries_dependencies:
        roles = {row['path']: row['role'] for row in manifest['files']}
        if (
            roles.get('modeling-configuration.json') != 'modeling_configuration'
            or roles.get('result-dependencies.json') != 'result_dependencies'
        ):
            raise ValueError('Frozen application file role mismatch')
        if (
            config['schema_version'] != family.configuration
            or manifest['modeling_configuration_digest'] != scientific['digest']
            or files['modeling-configuration.json'] != canonical(scientific)
        ):
            raise ValueError('Stored private projection changed')
        raw = files['result-dependencies.json']
        descriptor = manifest['result_dependencies']
        if descriptor != dict(path='result-dependencies.json', sha256=raw_hash(raw), size=len(raw)):
            raise ValueError('Stored dependencies changed')
        verify_dependencies(config, data_json(raw))
    elif config['schema_version'] != '1':
        raise ValueError('Configuration version does not match bundle')
    approach_paths = {p for p in files if p.startswith('approach/')}
    pin = config.get('approach_binding')
    if family.carries_approach:
        if manifest['approach_digest'] != (pin['approach_digest'] if pin else None) or manifest[
            'approach_closure_digest'
        ] != (pin['closure_digest'] if pin else None):
            raise ValueError('Stored approach manifest pin mismatch')
    if pin:
        descriptor = next(
            (d for d in manifest['files'] if d['path'] == 'approach/closure.json'), None
        )
        approach_roles = {d['path'] for d in manifest['files'] if d['role'] == 'approach'}
        if (
            approach_paths != {'approach/closure.json'}
            or approach_roles != approach_paths
            or descriptor['media_type'] != 'application/json'
            or files['approach/closure.json'] != canonical(frozen['approach_closure'])
        ):
            raise ValueError('Stored approach file mismatch')
    elif approach_paths or any(d['role'] == 'approach' for d in manifest['files']):
        raise ValueError('Unlinked bundle carries approach file')
    for path, value in [
        ('configuration.json', config),
        ('context.json', config['context_snapshot']),
        ('evidence/index.json', config['evidence_snapshots']),
    ]:
        if files[path] != canonical(value):
            raise ValueError('Stored application evidence changed')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_dependencies(configuration, dependencies):
    """Pure equality check shared by bundle assembly and retained validation."""
    validate('ResultDependencies1', dependencies)
    sources = {s['label']: s for s in dependencies['sources']}
    if (
        len(sources) != len(dependencies['sources'])
        or dependencies['sources'] != sorted(dependencies['sources'], key=lambda s: s['label'])
        or dependencies['mappings']
        != sorted(dependencies['mappings'], key=lambda m: port_key(m['target']))
    ):
        raise ValueError('Ambiguous native source mapping')
    expected = []
    used = set()
    for item in configuration['inputs']:
        b = item.get('result_binding')
        if b is None:
            continue
        matches = [s for s in sources.values() if s['source_run_id'] == b['source_run_id']]
        if len(matches) != 1:
            raise ValueError('Missing exact native source')
        s = matches[0]
        used.add(s['label'])
        c = b['conversion']
        if (
            s['label'] != 'r' + s['result_uuid'].replace('-', '')
            or s['request']['run_id'] != s['source_run_id']
            or s['request']['scope'] != configuration['study_id']
            or s['results_digest'] != b['results_digest']
            or item['value'] != b['original_value']
            or item['units'] != b['original_units']
            or c['source_units'] != item['units']
            or not finite(item['value'])
            or not finite(c['factor'])
            or not finite(c['destination_value'])
            or item['value'] * c['factor'] != c['destination_value']
        ):
            raise ValueError('Native scalar binding mismatch')
        expected.append(
            dict(
                target=item['target'],
                source_label=s['label'],
                **{
                    k: b[k]
                    for k in (
                        'source_output',
                        'results_digest',
                        'original_value',
                        'original_units',
                        'conversion',
                    )
                },
            )
        )
    if used != set(sources) or dependencies['mappings'] != sorted(
        expected, key=lambda m: port_key(m['target'])
    ):
        raise ValueError('Native scalar mapping mismatch')
