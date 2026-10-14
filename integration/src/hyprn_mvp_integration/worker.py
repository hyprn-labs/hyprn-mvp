"""Load a frozen native Group only inside the currently attested restricted worker.

The trusted launcher validates canonical contracts/runtime, then passes both the
immutable bundle digest and exact manifest-byte hash. No candidate is imported
while checking retained input bytes. There is no graph or source-body compiler.
"""

import hashlib
import ast
import dis
import base64
import importlib.util
import inspect
import json
import math
import os
import re
from pathlib import Path, PurePosixPath
import sys
import types
from uuid import UUID
from .results import _bounded_json
from .results import evaluate_criteria

PROTOCOL = 'hyprn_mvp.openmdao.program/1'


def frozen_json(raw):
    return _bounded_json(
        raw, size=32 * 1024 * 1024, depth_limit=32, collection_limit=2000, kind='frozen input'
    )


def object_fields(raw):
    """Preserve canonical producer number/string bytes when removing fields.

    No second float-to-JSON canonicalizer: the launcher validates RFC8785 bytes.
    Worker independently hashes the exact field fragments and projected bytes.
    """
    value = frozen_json(raw)
    if not isinstance(value, dict):
        raise ValueError('Frozen object required')
    text = raw.decode('utf-8')
    decoder = json.JSONDecoder()
    position = 1
    fields = {}
    if not text.startswith('{') or not text.endswith('}'):
        raise ValueError('Compact frozen object required')
    while position < len(text) - 1:
        key, end = decoder.raw_decode(text, position)
        if text[end] != ':':
            raise ValueError('Compact object field required')
        _, stop = decoder.raw_decode(text, end + 1)
        fields[key] = text[end + 1 : stop].encode('utf-8')
        if stop == len(text) - 1:
            break
        if text[stop] != ',':
            raise ValueError('Invalid frozen object separator')
        position = stop + 1
    if object_bytes(fields) != raw:
        raise ValueError('Ordered compact frozen object required')
    return fields


def object_bytes(fields):
    return (
        b'{'
        + b','.join(
            json.dumps(k, ensure_ascii=False).encode() + b':' + fields[k]
            for k in sorted(fields, key=lambda s: s.encode('utf-16-be'))
        )
        + b'}'
    )


def array_items(raw):
    value = frozen_json(raw)
    if not isinstance(value, list):
        raise ValueError('Frozen array required')
    text = raw.decode('utf-8')
    decoder = json.JSONDecoder()
    position = 1
    items = []
    if not text.startswith('[') or not text.endswith(']'):
        raise ValueError('Compact frozen array required')
    while position < len(text) - 1:
        _, end = decoder.raw_decode(text, position)
        items.append(text[position:end].encode('utf-8'))
        if end == len(text) - 1:
            break
        if text[end] != ',':
            raise ValueError('Invalid frozen array separator')
        position = end + 1
    if b'[' + b','.join(items) + b']' != raw:
        raise ValueError('Compact frozen array required')
    return items


def verify_object_digest(raw, key='digest'):
    fields = object_fields(raw)
    expected = frozen_json(fields.pop(key))
    if hashlib.sha256(object_bytes(fields)).hexdigest() != expected:
        raise ValueError('Frozen object digest mismatch')
    return expected


def exact_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError('Closed frozen fields required')


def scalar(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite frozen scalar required')


def uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('Canonical frozen UUID required')


def sha(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in '0123456789abcdef' for c in value)
    ):
        raise ValueError('Frozen SHA256 required')


def store_uuid(value):
    if not isinstance(value, str) or value not in (str(UUID(value)), UUID(value).hex):
        raise ValueError('Exact native store UUID required')


def port(value):
    exact_keys(value, 'instance_id port_id')
    uuid(value['instance_id'])
    uuid(value['port_id'])
    return value['instance_id'], value['port_id']


def bounded_text(value, limit=4096, nonblank=False):
    if not isinstance(value, str) or len(value) > limit or nonblank and not value.strip():
        raise ValueError('Bounded inert text required')


def uuid_list(value, limit=1000):
    if not isinstance(value, list) or len(value) > limit or len(set(value)) != len(value):
        raise ValueError('Distinct bounded UUID list required')
    for item in value:
        uuid(item)
    return set(value)


# Pinned unit_declarations/1 identities. This finite vocabulary is a wire
# contract; numerical conversion remains exclusively OpenMDAO's responsibility.
UNIT_CATALOG_DIGEST = 'f9278b0e59aa2d410dcd14a2abc1306d3d18adcf9edbb433002f6466489939f3'
# RFC8785 digest of the same authenticated080 catalog, retained for string targets.
LEGACY_TYPED_CATALOG_DIGEST = '93fc4085d924c6abb015cd351741569876b873693dc2c084b240716f16cfbc07'
UNIT_ENGINE_SOURCE_SHA256 = '9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92'
PHYSICAL_UNITS = frozenset(
    (
        'm',
        'km',
        'cm',
        'mm',
        's',
        'min',
        'h',
        'kg',
        'g',
        'N',
        'Pa',
        'kPa',
        'MPa',
        'K',
        'degC',
        'degF',
        'rad',
        'deg',
        'm/s',
        'km/h',
        'J/kg',
        'kJ/kg',
        'MJ/kg',
        'kg/m**3',
        'g/cm**3',
        'm**2',
        'cm**2',
        'mm**2',
    )
)


def unit_meaning(value):
    """Closed declaration access, preserving historical empty strings."""
    if isinstance(value, str):
        if value and value not in PHYSICAL_UNITS:
            raise ValueError('Unsupported unit')
        return value
    if not isinstance(value, dict):
        raise ValueError('Malformed unit declaration')
    kind = value.get('kind')
    if kind in ('dimensionless', 'unspecified'):
        exact_keys(value, 'kind')
        return '' if kind == 'dimensionless' else None
    if kind == 'physical':
        exact_keys(value, 'kind expression')
        expression = value['expression']
        if not isinstance(expression, str) or expression not in PHYSICAL_UNITS:
            raise ValueError('Unsupported physical unit')
        return expression
    raise ValueError('Unknown unit declaration')


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


def verify_unit_declarations(model, require_resolved=True):
    """Check retained shapes; resolve only exact active definition occurrences."""
    if model['schema_version'] == '4':
        exact_keys(
            model,
            (
                'schema_version model_id model_revision_id parent_model_'
                'revision_id originating_draft_revision digest root_inst'
                'ance_id definitions instances ports connections boundar'
                'y_mappings annotations source_files required_capabiliti'
                'es assumptions'
            ),
        )
    definitions = {}
    flattened = []
    for d in model['definitions']:
        exact_keys(
            d,
            (
                'definition_id definition_version_id kind name ports sou'
                'rce_refs residual_port_ids child_instances boundary_map'
                'pings annotations'
            )
            + (
                ' quantity_definitions'
                if 'quantity_definitions' in d and model['schema_version'] == '4'
                else ''
            ),
        )
        uuid(d['definition_id'])
        uuid(d['definition_version_id'])
        bounded_text(d['name'])
        version = d['definition_version_id']
        if version in definitions:
            raise ValueError('Duplicate definition version')
        definitions[version] = d
        if d['kind'] not in ('explicit_component', 'implicit_component', 'composite'):
            raise ValueError('Unknown definition kind')
        ids = set()
        shapes = set()
        for row in d['ports']:
            exact_keys(
                row, 'port_id definition_version_id direction name code_symbol value_type units'
            )
            uuid(row['port_id'])
            uuid(row['definition_version_id'])
            bounded_text(row['name'])
            if (
                row['port_id'] in ids
                or row['definition_version_id'] != version
                or row['direction'] not in ('input', 'output', 'residual')
                or row['value_type'] != 'real_scalar'
                or not isinstance(row['code_symbol'], str)
                or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', row['code_symbol'])
            ):
                raise ValueError('Malformed retained port')
            ids.add(row['port_id'])
            shapes.add(isinstance(row['units'], str))
            unit_meaning(row['units'])
            flattened.append(row)
        if len(shapes) > 1:
            raise ValueError('Mixed legacy/typed definition')
        if model['schema_version'] == '4' and 'quantity_definitions' in d:
            quantities = d['quantity_definitions']
            if not isinstance(quantities, list) or len(quantities) > 1000:
                raise ValueError('Quantity bound')
            seen_quantities = set()
            for q in quantities:
                exact_keys(q, 'port_id statement')
                uuid(q['port_id'])
                bounded_text(q['statement'], 4096, True)
                if q['port_id'] not in ids or q['port_id'] in seen_quantities:
                    raise ValueError('Quantity port correspondence')
                seen_quantities.add(q['port_id'])
        if not isinstance(d['source_refs'], list) or len(d['source_refs']) > 1000:
            raise ValueError('Invalid source references')
        for ref in d['source_refs']:
            sha(ref)
        uuid_list(d['residual_port_ids'])
        if not set(d['residual_port_ids']) <= ids:
            raise ValueError('Invalid residual ports')
        for key in ('child_instances', 'boundary_mappings', 'annotations'):
            if not isinstance(d[key], list) or len(d[key]) > 1000:
                raise ValueError('Invalid retained definition collection')
        if model['schema_version'] == '4':
            for note in d['annotations']:
                exact_keys(note, 'element_ref text')
                uuid(note['element_ref'])
                bounded_text(note['text'])
    if flattened != model['ports']:
        raise ValueError('Aggregate retained ports mismatch')
    active = {}
    seen = set()
    for instance in model['instances']:
        exact_keys(instance, 'instance_id definition_version_id name')
        iid = instance['instance_id']
        version = instance['definition_version_id']
        uuid(iid)
        uuid(version)
        bounded_text(instance['name'])
        if iid in seen or version not in definitions:
            raise ValueError('Invalid instance definition')
        seen.add(iid)
        for row in definitions[version]['ports']:
            value = unit_meaning(row['units'])
            if require_resolved and value is None:
                raise ValueError(
                    'Unspecified active unit: ' + iid + '/' + version + '/' + row['port_id']
                )
            active[(iid, row['port_id'])] = value
    return active


def verify_unit_catalog(manifest, files, prepared, model, config):
    """Authenticate the unique declared provenance helper by content, never path."""
    identity = prepared['generator_identity']
    path = identity['provenance_path']
    if not any(r['path'] == path and r['role'] == 'provenance' for r in manifest['files']):
        raise ValueError('Missing provenance role')
    raw = files[path]
    provenance = frozen_json(raw)
    descriptors = {r['path']: r for r in prepared['files']}
    manifest_roles = {r['path']: r['role'] for r in manifest['files']}
    rows = provenance['patched_files']
    seen = set()
    catalogs = []
    for row in rows:
        name = row['path']
        if name in seen:
            raise ValueError('Duplicate provenance file')
        seen.add(name)
        data = files[name]
        declared = descriptors[name]
        if (
            len(data) != row['size']
            or hashlib.sha256(data).hexdigest() != row['sha256']
            or declared['size'] != row['size']
            or declared['sha256'] != row['sha256']
            or declared['role'] != 'provenance'
            or manifest_roles.get(name) != 'provenance'
        ):
            raise ValueError('Retained provenance binding mismatch')
        if row['role'] != 'model_helper' or len(data) > 16384:
            continue
        try:
            catalog = frozen_json(data)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(catalog, dict) or 'catalog_digest' not in catalog:
            continue
        exact_keys(
            catalog, 'catalog_digest engine version source_sha256 supported_units linear_pairs'
        )
        payload = json.dumps(
            {k: v for k, v in catalog.items() if k != 'catalog_digest'},
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
        ).encode()
        if (
            catalog['catalog_digest'] != UNIT_CATALOG_DIGEST
            or hashlib.sha256(payload).hexdigest() != UNIT_CATALOG_DIGEST
            or catalog['engine'] != 'OpenMDAO'
            or catalog['version'] != '3.45.1'
            or catalog['source_sha256'] != UNIT_ENGINE_SOURCE_SHA256
        ):
            raise ValueError('Unsupported retained unit catalog')
        catalogs.append(catalog)
    if len(catalogs) != 1:
        raise ValueError('Exactly one authenticated unit catalog required')
    # Reuse retained canonical fragments for generator provenance pins.
    patched = array_items(object_fields(raw)['patched_files'])
    for key, kind in (
        ('generator_digest', 'generator'),
        ('template_digest', 'template'),
        ('adapter_digest', None),
    ):
        selected = [
            r
            for r in patched
            if (
                frozen_json(r)['role'] == kind
                if kind
                else frozen_json(r)['role'] not in ('generator', 'template')
            )
        ]
        if hashlib.sha256(b'[' + b','.join(selected) + b']').hexdigest() != identity[key]:
            raise ValueError('Generator provenance digest mismatch')
    pairs = {(a, b): factor for a, b, factor, offset in catalogs[0]['linear_pairs'] if offset == 0}
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    typed_targets = {
        (i['instance_id'], p['port_id']): isinstance(p['units'], dict)
        for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports']
    }
    units = verify_unit_declarations(model)

    def factor(source, destination):
        if (
            not isinstance(source, str)
            or not isinstance(destination, str)
            or (source, destination) not in pairs
        ):
            raise ValueError('Unsupported or incompatible frozen units')
        return pairs[source, destination]

    for wire in model['connections']:
        factor(units[port(wire['source_ref'])], units[port(wire['target_ref'])])
    for item in config['inputs']:
        destination = units[port(item['target'])]
        expected = factor(item['units'], destination)
        scalar(item['value'] * expected)
        binding = item.get('result_binding')
        if binding is not None:
            proof = binding['conversion']
            if (
                proof['policy'] != 'openmdao-linear-catalog-1'
                or proof['catalog_digest']
                != (
                    UNIT_CATALOG_DIGEST
                    if model['schema_version'] == '3' or typed_targets[port(item['target'])]
                    else LEGACY_TYPED_CATALOG_DIGEST
                )
                or proof['source_units'] != item['units']
                or proof['destination_units'] != destination
                or proof['factor'] != expected
            ):
                raise ValueError('Retained conversion interpretation mismatch')
    for criterion in config['criteria']:
        factor(units[port(criterion['target'])], criterion['units'])


def verify_assumption_closure(config, model):
    """Independent bounded data validation, without application or schema imports."""
    if model['schema_version'] not in ('1', '2', '3', '4'):
        raise ValueError('Unsupported model version')
    for key in (
        'study_id',
        'model_id',
        'model_revision_id',
        'configuration_id',
        'configuration_revision_id',
    ):
        uuid(config[key])
    if config['parent_revision_id'] is not None:
        uuid(config['parent_revision_id'])
    if (
        config['model_id'] != model['model_id']
        or config['model_revision_id'] != model['model_revision_id']
    ):
        raise ValueError('Configuration model identity mismatch')
    instances = uuid_list([i['instance_id'] for i in model['instances']])
    required = uuid_list(config['general_context_evidence_version_ids'])
    for rows, owned in ((model.get('assumptions', []), True), (config['assumptions'], False)):
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError('Assumption count bound')
        uuid_list([a['assumption_id'] for a in rows])
        for row in rows:
            exact_keys(row, 'assumption_id statement evidence_links' + (' owner' if owned else ''))
            bounded_text(row['statement'], nonblank=True)
            if owned:
                owner = row['owner']
                if owner['kind'] == 'model':
                    exact_keys(owner, 'kind')
                elif owner['kind'] == 'instance':
                    exact_keys(owner, 'kind instance_id')
                    uuid(owner['instance_id'])
                    if (
                        owner['instance_id'] not in instances
                        or owner['instance_id'] == model['root_instance_id']
                    ):
                        raise ValueError('Dangling assumption owner')
                else:
                    raise ValueError('Unknown assumption owner')
            links = row['evidence_links']
            seen = set()
            if not isinstance(links, list) or len(links) > 64:
                raise ValueError('Assumption link bound')
            for link in links:
                exact_keys(link, 'evidence_version_id relation')
                uuid(link['evidence_version_id'])
                pair = (link['evidence_version_id'], link['relation'])
                if link['relation'] not in ('supports', 'challenges', 'context') or pair in seen:
                    raise ValueError('Invalid assumption relationship')
                seen.add(pair)
                required.add(pair[0])
    if (
        model['schema_version'] in ('2', '3', '4')
        and 'assumptions' not in model
        or model['schema_version'] == '1'
        and 'assumptions' in model
    ):
        raise ValueError('Model assumption version mismatch')
    for row in config['inputs']:
        required.update(uuid_list(row['provenance']['evidence_version_ids']))
    for row in config['criteria']:
        required.update(uuid_list(row['evidence_version_ids']))
    snapshots = config['evidence_snapshots']
    ids = [s['evidence_version_id'] for s in snapshots]
    uuid_list(ids)
    if len(required) > 1000 or ids != sorted(required):
        raise ValueError('Exact evidence closure required')
    scope_fields = {
        'study': '',
        'model_revision': 'model_id model_revision_id',
        'definition_version': 'model_id model_revision_id definition_id definition_version_id',
        'instance': 'model_id model_revision_id instance_id',
        'port': 'model_id model_revision_id instance_id port_id',
        'connection': 'model_id model_revision_id connection_id',
        'configuration': 'configuration_revision_id',
        'criterion': 'configuration_revision_id criterion_id',
        'run': 'run_id',
    }
    for row in snapshots:
        version = row.get('evidence_schema_version')
        keys = 'evidence_version_id kind content source_refs'
        if version in ('2', '3'):
            keys += ' evidence_schema_version resource_scope'
        if version == '3':
            keys += ' evidence_id study_id title parent_evidence_version_id recorded_context'
        if version not in (None, '2', '3'):
            raise ValueError('Unsupported evidence snapshot')
        exact_keys(row, keys)
        bounded_text(row['content'], nonblank=True)
        if (
            row['kind'] != 'note'
            or not isinstance(row['source_refs'], list)
            or len(row['source_refs']) > 1000
        ):
            raise ValueError('Invalid frozen evidence')
        for ref in row['source_refs']:
            bounded_text(ref)
        if version in ('2', '3'):
            scope = row['resource_scope']
            kind = scope['kind']
            if kind not in scope_fields:
                raise ValueError('Invalid evidence scope kind')
            exact_keys(scope, 'scope_version study_id kind ' + scope_fields[kind])
            if scope['scope_version'] != '1' or scope['study_id'] != config['study_id']:
                raise ValueError('Foreign evidence scope')
            for key, value in scope.items():
                if key.endswith('_id'):
                    uuid(value)
        if version == '3':
            uuid(row['evidence_id'])
            uuid(row['study_id'])
            bounded_text(row['title'], 200, True)
            parent = row['parent_evidence_version_id']
            if parent is not None:
                uuid(parent)
            if row['study_id'] != config['study_id'] or parent == row['evidence_version_id']:
                raise ValueError('Invalid evidence owner or parent')
            context = row['recorded_context']
            exact_keys(context, 'schema_version label resource_labels')
            bounded_text(context['label'])
            if (
                context['schema_version'] != '1'
                or not isinstance(context['resource_labels'], list)
                or len(context['resource_labels']) > 8
            ):
                raise ValueError('Invalid recorded context')
            for label in context['resource_labels']:
                exact_keys(label, 'kind resource_id version_id name')
                uuid(label['resource_id'])
                bounded_text(label['name'])
                if label['version_id'] is not None:
                    uuid(label['version_id'])
                if label['kind'] not in (
                    'study',
                    'model',
                    'definition',
                    'instance',
                    'port',
                    'connection',
                    'configuration',
                    'criterion',
                    'run',
                ):
                    raise ValueError('Invalid recorded label kind')
                if label['kind'] == 'study' and label['resource_id'] != config['study_id']:
                    raise ValueError('Foreign recorded study label')


class ApproachClosure:
    """Independent fixed-reference admission over retained raw JSON fragments.

    No schema/application dependency or scientific interpretation. Digests and
    ancestor subclosures use original producer bytes, including float tokens.
    """

    keys = dict(
        approach_versions='approach_version_id',
        models='model_revision_id',
        configurations='configuration_revision_id',
        run_contexts='run_id',
        evidence='evidence_version_id',
    )

    def __init__(self, raw, sid):
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('Approach closure byte limit')
        self.fields = object_fields(raw)
        self.value = frozen_json(raw)
        self.sid = sid
        exact_keys(
            self.value,
            (
                'schema_version root_approach_version_id root_approach_d'
                'igest approach_versions models configurations run_conte'
                'xts evidence digest'
            ),
        )
        if self.value['schema_version'] not in ('1', '3', '4'):
            raise ValueError('Approach closure version')
        verify_object_digest(raw)
        self.tables = {}
        self.raw = {}
        self.edges = {}
        self.pins = []
        limits = dict(
            approach_versions=64, models=32, configurations=64, run_contexts=64, evidence=1000
        )
        for table, key in self.keys.items():
            items = array_items(self.fields[table])
            rows = {}
            raws = {}
            if len(items) > limits[table]:
                raise ValueError('Approach inventory bound')
            for item in items:
                row = frozen_json(item)
                identity = row[key]
                uuid(identity)
                if identity in rows:
                    raise ValueError('Duplicate approach identity')
                if table != 'evidence':
                    verify_object_digest(item)
                if 'study_id' in row and row['study_id'] != sid:
                    raise ValueError('Foreign approach record')
                rows[identity] = row
                raws[identity] = item
                self.edges[table, identity] = set()
            if list(rows) != sorted(rows):
                raise ValueError('Ordered approach inventory required')
            self.tables[table] = rows
            self.raw[table] = raws
        if (
            sum(map(len, self.tables.values())) > 1000
            or len(self.tables['configurations']) + len(self.tables['run_contexts']) > 64
        ):
            raise ValueError('Approach aggregate bound')
        self.root = self.get('approach_versions', self.value['root_approach_version_id'])
        if self.root['digest'] != self.value['root_approach_digest']:
            raise ValueError('Approach root digest')
        for table, method in [
            ('models', self.model),
            ('approach_versions', self.approach),
            ('configurations', self.configuration),
            ('run_contexts', self.run),
        ]:
            for row in self.tables[table].values():
                method(row)
        for row in self.tables['evidence'].values():
            if row.get('resource_scope', {}).get('study_id', sid) != sid:
                raise ValueError('Foreign approach evidence')
        reached = self.reached(self.root)
        if reached != set(self.edges):
            raise ValueError('Unused approach record')
        if self.envelope_digest(self.root, reached) != self.value['digest']:
            raise ValueError('Approach closure branch mismatch')
        for version, expected in self.pins:
            if self.envelope_digest(version, self.reached(version)) != expected:
                raise ValueError('Ancestor approach closure mismatch')

    def get(self, table, key):
        try:
            return self.tables[table][key]
        except KeyError:
            raise ValueError('Missing exact approach reference') from None

    def edge(self, node, table, key):
        row = self.get(table, key)
        self.edges[node].add((table, key))
        return row

    def links(self, node, links):
        if not isinstance(links, list) or len(links) > 64:
            raise ValueError('Approach evidence link bound')
        seen = set()
        for link in links:
            exact_keys(
                link, 'evidence_version_id relation' + (' locator' if 'locator' in link else '')
            )
            uuid(link['evidence_version_id'])
            if link['relation'] not in ('supports', 'challenges', 'context'):
                raise ValueError('Approach evidence relation')
            if 'locator' in link:
                bounded_text(link['locator'], 1024)
            pair = link['evidence_version_id'], link['relation']
            if pair in seen:
                raise ValueError('Duplicate approach evidence link')
            seen.add(pair)
            self.edge(node, 'evidence', pair[0])

    @staticmethod
    def index(rows, key, limit=1000):
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('Approach local inventory bound')
        uuid_list([r[key] for r in rows], limit)
        return {r[key]: r for r in rows}

    @staticmethod
    def model_port(model, ref):
        instance = next(
            (i for i in model['instances'] if i['instance_id'] == ref['instance_id']), None
        )
        matches = [
            p
            for p in model['ports']
            if instance is not None
            and (p['definition_version_id'], p['port_id'])
            == (instance['definition_version_id'], ref['port_id'])
        ]
        if len(matches) != 1:
            raise ValueError('Approach port correspondence')

    def model(self, m):
        node = 'models', m['model_revision_id']
        definitions = self.index(m['definitions'], 'definition_version_id')
        instances = self.index(m['instances'], 'instance_id')
        ports = {}
        if not isinstance(m['ports'], list) or len(m['ports']) > 1000:
            raise ValueError('Approach port inventory bound')
        for p in m['ports']:
            uuid(p['definition_version_id'])
            uuid(p['port_id'])
            key = p['definition_version_id'], p['port_id']
            if key in ports:
                raise ValueError('Duplicate approach definition port')
            ports[key] = p
        self.index(m['connections'], 'connection_id')
        # Native snapshots keep root_instance_id separate from component instances.
        uuid(m['root_instance_id'])
        if m['schema_version'] not in ('1', '2', '3', '4'):
            raise ValueError('Approach model identity')
        if m['schema_version'] in ('3', '4'):
            verify_unit_declarations(m, require_resolved=False)
        sources = {}
        for s in m['source_files']:
            exact_keys(s, 'encoding media_type bytes sha256')
            sha(s['sha256'])
            raw = base64.b64decode(s['bytes'], validate=True)
            if (
                s['encoding'] != 'base64'
                or s['sha256'] in sources
                or hashlib.sha256(raw).hexdigest() != s['sha256']
            ):
                raise ValueError('Approach model source mismatch')
            sources[s['sha256']] = raw
        for d in definitions.values():
            if not set(d['source_refs']) <= set(sources):
                raise ValueError('Approach definition source missing')
            self.index(d['ports'], 'port_id')
            for p in d['ports']:
                if (
                    ports.get((d['definition_version_id'], p['port_id'])) != p
                    or p['definition_version_id'] != d['definition_version_id']
                ):
                    raise ValueError('Approach definition port')
        for i in instances.values():
            if i['definition_version_id'] not in definitions:
                raise ValueError('Approach instance definition')
        for p in ports.values():
            if (
                p['definition_version_id'] not in definitions
                or p not in definitions[p['definition_version_id']]['ports']
            ):
                raise ValueError('Approach port inventory')
        for c in m['connections']:
            self.model_port(m, c['source_ref'])
            self.model_port(m, c['target_ref'])
        for a in self.index(m.get('assumptions', []), 'assumption_id').values():
            exact_keys(a, 'assumption_id statement evidence_links owner')
            bounded_text(a['statement'], nonblank=True)
            owner = a['owner']
            if owner['kind'] == 'model':
                exact_keys(owner, 'kind')
            elif owner['kind'] == 'instance':
                exact_keys(owner, 'kind instance_id')
                if (
                    owner['instance_id'] not in instances
                    or owner['instance_id'] == m['root_instance_id']
                ):
                    raise ValueError('Approach model assumption owner')
            else:
                raise ValueError('Approach assumption owner')
            self.links(node, a['evidence_links'])

    def approach(self, v):
        exact_keys(
            v,
            (
                'schema_version approach_id approach_version_id study_id'
                ' version_number predecessor_version_id content created_'
                'by created_at digest'
            ),
        )
        for k in ('approach_id', 'approach_version_id', 'study_id', 'created_by'):
            uuid(v[k])
        if v['predecessor_version_id'] is not None:
            uuid(v['predecessor_version_id'])
        bounded_text(v['created_at'], 64, True)
        if (
            v['schema_version'] not in ('1', '2')
            or type(v['version_number']) is not int
            or not 1 <= v['version_number'] <= 2147483647
        ):
            raise ValueError('Approach version')
        node = 'approach_versions', v['approach_version_id']
        c = v['content']
        if len(object_fields(self.raw[node[0]][node[1]])['content']) > 1024 * 1024:
            raise ValueError('Approach content bound')
        exact_keys(
            c,
            (
                'schema_version question scope limitations open_question'
                's model_bindings steps assumptions cases basis_refs'
            )
            + (' original_question elaboration limit_items' if v['schema_version'] == '2' else ''),
        )
        if c['schema_version'] != v['schema_version']:
            raise ValueError('Approach content version')
        if v['schema_version'] == '2':
            for key in ('original_question', 'elaboration'):
                claim = c[key]
                if claim is None:
                    continue
                exact_keys(claim, 'text attribution')
                bounded_text(claim['text'], 4096)
                author = claim['attribution']
                exact_keys(author, 'kind label')
                if author['kind'] not in ('human', 'agent', 'unknown'):
                    raise ValueError('Question attribution')
                if author['label'] is not None:
                    bounded_text(author['label'], 256)
            for limit in self.index(c['limit_items'], 'limit_id', 256).values():
                exact_keys(limit, 'limit_id statement evidence_links')
                bounded_text(limit['statement'], 4096, True)
                self.links(node, limit['evidence_links'])
        for k in ('question', 'scope', 'limitations', 'open_questions'):
            bounded_text(c[k])
        bindings = self.index(c['model_bindings'], 'binding_id', 32)
        steps = self.index(c['steps'], 'step_id', 64)
        assumptions = self.index(c['assumptions'], 'assumption_id', 256)
        cases = self.index(c['cases'], 'case_id', 64)
        bound = {}
        used = set()
        for bid, b in bindings.items():
            exact_keys(b, 'binding_id model_id model_revision_id')
            uuid(b['model_id'])
            uuid(b['model_revision_id'])
            m = self.edge(node, 'models', b['model_revision_id'])
            if b['model_id'] != m['model_id']:
                raise ValueError('Approach model binding')
            bound[bid] = m
        for s in steps.values():
            exact_keys(
                s,
                (
                    'step_id title purpose rationale remaining_work intent i'
                    'mplementation_state implementation_refs assumption_refs'
                    ' evidence_links'
                ),
            )
            bounded_text(s['title'], 256, True)
            for k in ('purpose', 'rationale', 'remaining_work'):
                bounded_text(s[k])
            intent = s['intent']
            exact_keys(intent, 'transformation inputs outputs depends_on_step_ids')
            for k in ('transformation', 'inputs', 'outputs'):
                bounded_text(intent[k])
            deps = uuid_list(intent['depends_on_step_ids'], 64)
            if not deps <= set(steps) or s['step_id'] in deps:
                raise ValueError('Approach step dependency')
            refs = s['implementation_refs']
            state = s['implementation_state']
            if (
                not isinstance(refs, list)
                or len(refs) > 256
                or state not in ('proposed', 'partial', 'linked')
            ):
                raise ValueError('Approach step implementation')
            if (
                state == 'proposed'
                and refs
                or state != 'proposed'
                and not refs
                or state == 'partial'
                and not s['remaining_work']
                or state == 'linked'
                and s['remaining_work']
            ):
                raise ValueError('Approach declared coverage')
            for ref in refs:
                kind = ref['kind']
                fields = {
                    'model': '',
                    'instance': 'instance_id',
                    'port': 'instance_id port_id',
                    'connection': 'connection_id',
                }
                if kind not in fields:
                    raise ValueError('Approach element kind')
                exact_keys(ref, 'kind binding_id ' + fields[kind])
                if ref['binding_id'] not in bound:
                    raise ValueError('Missing approach binding')
                used.add(ref['binding_id'])
                m = bound[ref['binding_id']]
                if kind in ('instance', 'port') and ref['instance_id'] not in {
                    i['instance_id'] for i in m['instances']
                }:
                    raise ValueError('Approach instance reference')
                if kind == 'port':
                    self.model_port(m, ref)
                if kind == 'connection' and ref['connection_id'] not in {
                    c['connection_id'] for c in m['connections']
                }:
                    raise ValueError('Approach connection reference')
            if not isinstance(s['assumption_refs'], list) or len(s['assumption_refs']) > 256:
                raise ValueError('Approach assumption ref bound')
            for ref in s['assumption_refs']:
                kind = ref['kind']
                if kind == 'approach':
                    exact_keys(ref, 'kind assumption_id')
                    if ref['assumption_id'] not in assumptions:
                        raise ValueError('Missing local approach assumption')
                elif kind == 'configuration':
                    exact_keys(ref, 'kind configuration_revision_id assumption_id')
                    cfg = self.edge(node, 'configurations', ref['configuration_revision_id'])
                    if ref['assumption_id'] not in {
                        a['assumption_id'] for a in cfg.get('assumptions', [])
                    }:
                        raise ValueError('Missing configuration assumption')
                elif kind == 'model':
                    exact_keys(ref, 'kind binding_id assumption_id origin')
                    if ref['binding_id'] not in bound or ref['assumption_id'] not in {
                        a['assumption_id'] for a in bound[ref['binding_id']].get('assumptions', [])
                    }:
                        raise ValueError('Missing model assumption')
                    origin = ref['origin']
                    if origin:
                        exact_keys(origin, 'approach_version_id assumption_id digest')
                        old = self.edge(node, 'approach_versions', origin['approach_version_id'])
                        prior = next(
                            (
                                a
                                for a in old['content']['assumptions']
                                if a['assumption_id'] == origin['assumption_id']
                            ),
                            None,
                        )
                        if (
                            old['digest'] != origin['digest']
                            or prior is None
                            or prior['role'] != 'proposed_model_condition'
                            or origin['assumption_id'] in assumptions
                        ):
                            raise ValueError('Approach assumption origin')
                else:
                    raise ValueError('Approach assumption reference kind')
            self.links(node, s['evidence_links'])
        if used != set(bound):
            raise ValueError('Unused approach model binding')
        for a in assumptions.values():
            exact_keys(a, 'assumption_id statement role evidence_links')
            bounded_text(a['statement'], nonblank=True)
            if a['role'] not in ('overall_method', 'proposed_model_condition'):
                raise ValueError('Approach assumption role')
            self.links(node, a['evidence_links'])
        for case in cases.values():
            exact_keys(case, 'case_id title question rationale binding_id evidence_links')
            bounded_text(case['title'], 256, True)
            bounded_text(case['question'])
            bounded_text(case['rationale'])
            if case['binding_id'] is not None and case['binding_id'] not in bound:
                raise ValueError('Approach case binding')
            self.links(node, case['evidence_links'])
        if not isinstance(c['basis_refs'], list) or len(c['basis_refs']) > 64:
            raise ValueError('Approach basis bound')
        for basis in c['basis_refs']:
            if basis['kind'] not in ('configuration', 'run'):
                raise ValueError('Approach basis kind')
            table, key = (
                ('configurations', 'configuration_revision_id')
                if basis['kind'] == 'configuration'
                else ('run_contexts', 'run_id')
            )
            exact_keys(basis, 'kind reason relation ' + key)
            bounded_text(basis['reason'])
            if basis['relation'] not in ('supports', 'challenges', 'context'):
                raise ValueError('Approach basis relation')
            self.edge(node, table, basis[key])

    def pin(self, c):
        p = c.get('approach_binding')
        if p is None:
            return None
        exact_keys(p, 'approach_id approach_version_id approach_digest closure_digest case_id')
        for k in ('approach_id', 'approach_version_id'):
            uuid(p[k])
        for k in ('approach_digest', 'closure_digest'):
            sha(p[k])
        v = self.get('approach_versions', p['approach_version_id'])
        used = {
            ref['binding_id']
            for step in v['content']['steps']
            for ref in step['implementation_refs']
        }
        matches = {
            b['binding_id']
            for b in v['content']['model_bindings']
            if b['binding_id'] in used
            and b['model_id'] == c['model_id']
            and b['model_revision_id'] == c['model_revision_id']
        }
        if (
            p['approach_id'] != v['approach_id']
            or p['approach_digest'] != v['digest']
            or not matches
        ):
            raise ValueError('Approach configuration binding')
        if p['case_id'] is not None:
            uuid(p['case_id'])
            case = next((r for r in v['content']['cases'] if r['case_id'] == p['case_id']), None)
            if case is None or case['binding_id'] not in matches:
                raise ValueError('Approach configured case')
        return v

    def configuration(self, c):
        node = 'configurations', c['configuration_revision_id']
        m = self.edge(node, 'models', c['model_revision_id'])
        if (
            c['schema_version'] not in ('1', '2', '3', '4')
            or c['model_id'] != m['model_id']
            or (m['schema_version'] in ('2', '3', '4')) != (c['schema_version'] in ('3', '4'))
            or m['schema_version'] in ('3', '4')
            and c['schema_version'] != '4'
        ):
            raise ValueError('Approach prior configuration model')
        if c['schema_version'] in ('3', '4'):
            verify_assumption_closure(c, m)
        raw_fields = object_fields(self.raw[node[0]][node[1]])
        for raw in array_items(raw_fields['evidence_snapshots']):
            row = frozen_json(raw)
            self.edge(node, 'evidence', row['evidence_version_id'])
            if raw != self.raw['evidence'][row['evidence_version_id']]:
                raise ValueError('Approach prior evidence bytes')
        for item in c['inputs']:
            binding = item.get('result_binding')
            if binding:
                run = self.edge(node, 'run_contexts', binding['source_run_id'])
                outputs = (
                    []
                    if run['results'] is None
                    else [
                        o
                        for o in run['results']['outputs']
                        if o['target'] == binding['source_output']
                    ]
                )
                result_raw = object_fields(self.raw['run_contexts'][run['run_id']])['results']
                if (
                    run['configuration_digest'] != binding['source_configuration_digest']
                    or hashlib.sha256(result_raw).hexdigest() != binding['results_digest']
                    or len(outputs) != 1
                ):
                    raise ValueError('Approach result source')
                o = outputs[0]
                if (
                    run['results']['execution']['state'] != 'finished'
                    or run['results']['execution']['exit_code'] != 0
                    or o['availability'] != 'available'
                    or not o['assigned']
                    or not o['producer_completed']
                    or o['value'] != binding['original_value']
                    or o['units'] != binding['original_units']
                ):
                    raise ValueError('Approach result eligibility')
        for key in ('context_source', 'derivation'):
            ref = c.get(key)
            if ref and 'source_run_id' in ref:
                run = self.edge(node, 'run_contexts', ref['source_run_id'])
                if run['configuration_digest'] != ref['source_configuration_digest']:
                    raise ValueError('Approach source context')
                if key == 'derivation' and (
                    run['configuration_revision_id'] != ref['source_configuration_revision_id']
                    or run['runtime'] != ref['source_runtime']
                ):
                    raise ValueError('Approach derivation context')
        v = self.pin(c)
        if v:
            self.edge(node, 'approach_versions', v['approach_version_id'])
            self.pins.append((v, c['approach_binding']['closure_digest']))

    def run(self, r):
        exact_keys(
            r,
            (
                'schema_version run_id study_id request association conf'
                'iguration_revision_id configuration_digest model_revisi'
                'on_id model_digest context results assessment runtime e'
                'rrors digest'
            ),
        )
        if r['schema_version'] not in ('1', '2'):
            raise ValueError('Approach run context version')
        node = 'run_contexts', r['run_id']
        c = self.edge(node, 'configurations', r['configuration_revision_id'])
        m = self.edge(node, 'models', r['model_revision_id'])
        exact_keys(r['request'], 'run_id scope command_id payload_digest bundle_digest')
        exact_keys(r['association'], 'store_uuid process_uuid')
        for k in ('run_id', 'scope', 'command_id'):
            uuid(r['request'][k])
        for k in ('payload_digest', 'bundle_digest'):
            sha(r['request'][k])
        store_uuid(r['association']['store_uuid'])
        uuid(r['association']['process_uuid'])
        if (
            r['request']['run_id'] != r['run_id']
            or r['request']['scope'] != self.sid
            or c['digest'] != r['configuration_digest']
            or m['digest'] != r['model_digest']
            or c['model_revision_id'] != m['model_revision_id']
            or r['context'] != c['context_snapshot']
        ):
            raise ValueError('Approach run correspondence')
        if r['results'] is not None:
            if r['results']['schema_version'] != r['schema_version']:
                raise ValueError('Approach context/result format mismatch')
            if (
                r['results']['run_id'] != r['run_id']
                or r['results']['bundle_digest'] != r['request']['bundle_digest']
            ):
                raise ValueError('Approach run results')
            seen = set()
            for o in r['results']['outputs']:
                key = port(o['target'])
                self.model_port(m, o['target'])
                if key in seen:
                    raise ValueError('Approach duplicate output')
                seen.add(key)
                if o['availability'] == 'available':
                    scalar(o['value'])
                    if not o['assigned'] or not o['producer_completed']:
                        raise ValueError('Approach unavailable value')
                elif o['value'] is not None:
                    raise ValueError('Approach failed output is not a value')

    def reached(self, root):
        active = set()
        cache = {}

        def visit(node, depth):
            if depth > 16 or node in active:
                raise ValueError('Approach dependency depth/cycle')
            if node in cache:
                seen, height = cache[node]
                if depth + height > 16:
                    raise ValueError('Approach dependency depth')
                return seen, height
            active.add(node)
            seen = {node}
            height = 0
            for child in self.edges[node]:
                descendants, h = visit(child, depth + 1)
                seen.update(descendants)
                height = max(height, h + 1)
            active.remove(node)
            cache[node] = seen, height
            return seen, height

        return visit(('approach_versions', root['approach_version_id']), 0)[0]

    def envelope_digest(self, root, reached):
        version = (
            '4'
            if any(
                kind == 'run_contexts' and self.tables[kind][key]['schema_version'] == '2'
                for kind, key in reached
            )
            else '3'
            if root['schema_version'] == '2'
            or any(
                (kind == 'models' and self.tables[kind][key]['schema_version'] == '4')
                or (kind == 'approach_versions' and self.tables[kind][key]['schema_version'] == '2')
                for kind, key in reached
            )
            else '1'
        )
        fields = dict(
            schema_version=json.dumps(version).encode(),
            root_approach_version_id=json.dumps(root['approach_version_id']).encode(),
            root_approach_digest=json.dumps(root['digest']).encode(),
        )
        for table in self.keys:
            fields[table] = (
                b'['
                + b','.join(self.raw[table][key] for kind, key in sorted(reached) if kind == table)
                + b']'
            )
        return hashlib.sha256(object_bytes(fields)).hexdigest()


def verify_approach(manifest, files, config):
    p = config['approach_binding']
    path = 'approach/closure.json'
    mixed = (
        bundle_layout(manifest) == '6'
        and frozen_json(files['model.json'])['schema_version'] == '2'
    )
    roles = [f for f in manifest['files'] if f.get('role') == 'approach']
    reserved = {name for name in files if name.startswith('approach/')}
    if p is None:
        if (
            mixed
            or bundle_layout(manifest) in ('8', '9')
            and frozen_json(files['model.json'])['schema_version'] != '4'
        ):
            raise ValueError('Selected model requires descriptive approach closure')
        if (
            roles
            or reserved
            or manifest['approach_digest'] is not None
            or manifest['approach_closure_digest'] is not None
        ):
            raise ValueError('Unlinked approach inventory')
        return
    if (
        reserved != {path}
        or len(roles) != 1
        or roles[0]['path'] != path
        or roles[0]['media_type'] != 'application/json'
    ):
        raise ValueError('Approach reserved file role')
    contains_units = any(m['schema_version'] == '3' for m in frozen_json(files[path])['models'])
    if mixed and not contains_units:
        raise ValueError('Legacy selected model requires mixed approach closure')
    if bundle_layout(manifest) not in ('6', '8', '9') and contains_units:
        raise ValueError('Approach model/bundle version mismatch')
    closure = ApproachClosure(files[path], config['study_id'])
    v = closure.pin(config)
    if (bundle_layout(manifest) in ('8', '9')) != (
        closure.value['schema_version'] in ('3', '4')
    ) or (bundle_layout(manifest) == '9') != (closure.value['schema_version'] == '4'):
        raise ValueError('Approach descriptive bundle branch mismatch')
    if (
        v != closure.root
        or p['closure_digest'] != closure.value['digest']
        or manifest['approach_digest'] != v['digest']
        or manifest['approach_closure_digest'] != closure.value['digest']
    ):
        raise ValueError('Approach manifest/root pin mismatch')
    if closure.raw['models'].get(config['model_revision_id']) != files['model.json']:
        raise ValueError('Approach exact model bytes mismatch')


def verify_configuration_domains(manifest, files, prepared):
    """Verify full/private configuration and closed scalar dependency equality."""
    raw = files['configuration.json']
    config = frozen_json(raw)
    if verify_object_digest(raw) != manifest['configuration_digest']:
        raise ValueError('Full configuration digest mismatch')
    version = bundle_layout(manifest)
    if (
        config['schema_version']
        != {'2': '1', '3': '2', '4': '3', '5': '4', '6': '4', '8': '4'}[version]
    ):
        raise ValueError('Configuration/bundle version mismatch')
    keys = (
        'schema_version study_id model_id model_revision_id name'
        ' inputs criteria numerical context_snapshot evidence_sn'
        'apshots required_capabilities configuration_id configur'
        'ation_revision_id parent_revision_id digest'
    )
    exact_keys(
        config,
        keys
        + (' context_source derivation' if version in ('3', '4', '5', '6', '8', '9') else '')
        + (
            ' assumptions general_context_evidence_version_ids'
            if version in ('4', '5', '6', '8', '9')
            else ''
        )
        + (' approach_binding' if version in ('5', '6', '8', '9') else ''),
    )
    if version in ('5', '6', '8', '9'):
        verify_approach(manifest, files, config)
    if version in ('4', '5', '6', '8', '9'):
        verify_assumption_closure(config, frozen_json(files['model.json']))
    targets = [port(i['target']) for i in config['inputs']]
    if len(targets) > 1000 or len(targets) != len(set(targets)):
        raise ValueError('Explicit input inventory mismatch')
    for item in config['inputs']:
        exact_keys(
            item,
            'target value units provenance'
            + (' result_binding' if version in ('3', '4', '5', '6', '8', '9') else ''),
        )
        scalar(item['value'])
        if not isinstance(item['units'], str):
            raise ValueError('Original source units required')
    if version == '2':
        if prepared['configuration_digest'] != config['digest']:
            raise ValueError('Prepared literal configuration mismatch')
        return config
    fields = object_fields(raw)
    for key in ('context_source', 'derivation', 'digest'):
        fields.pop(key)
    if version in ('4', '5', '6', '8', '9'):
        fields.pop('assumptions')
        fields.pop('general_context_evidence_version_ids')
    if version in ('5', '6', '8', '9'):
        fields.pop('approach_binding')
        fields['schema_version'] = b'"3"'
    inputs = []
    for item in array_items(fields['inputs']):
        row = object_fields(item)
        row.pop('result_binding')
        inputs.append(object_bytes(row))
    fields['inputs'] = b'[' + b','.join(inputs) + b']'
    fields['required_capabilities'] = (
        b'['
        + b','.join(
            r
            for r in array_items(fields['required_capabilities'])
            if frozen_json(r)
            not in (
                {'result_linked_inputs/1', 'configuration_assumptions/1'}
                if version in ('4', '5', '6', '8', '9')
                else {'result_linked_inputs/1'}
            )
        )
        + b']'
    )
    private_digest = hashlib.sha256(object_bytes(fields)).hexdigest()
    fields['digest'] = json.dumps(private_digest).encode()
    if (
        files['modeling-configuration.json'] != object_bytes(fields)
        or manifest['modeling_configuration_digest'] != private_digest
        or prepared['configuration_digest'] != private_digest
    ):
        raise ValueError('Private scientific projection mismatch')
    raw_dependencies = files['result-dependencies.json']
    descriptor = manifest['result_dependencies']
    if descriptor != dict(
        path='result-dependencies.json',
        size=len(raw_dependencies),
        sha256=hashlib.sha256(raw_dependencies).hexdigest(),
    ):
        raise ValueError('Dependency descriptor mismatch')
    deps = frozen_json(raw_dependencies)
    exact_keys(deps, 'schema_version sources mappings')
    if (
        deps['schema_version'] != '1'
        or not isinstance(deps['sources'], list)
        or not isinstance(deps['mappings'], list)
    ):
        raise ValueError('Typed dependency version required')
    if len(deps['sources']) > 64 or len(deps['mappings']) > 1000:
        raise ValueError('Dependency bound')
    sources = {}
    runs = set()
    identities = set()
    for source in deps['sources']:
        exact_keys(source, 'label source_run_id request association result_uuid results_digest')
        uuid(source['source_run_id'])
        uuid(source['result_uuid'])
        sha(source['results_digest'])
        exact_keys(source['request'], 'run_id scope command_id payload_digest bundle_digest')
        for key in ('run_id', 'scope', 'command_id'):
            uuid(source['request'][key])
        for key in ('payload_digest', 'bundle_digest'):
            sha(source['request'][key])
        exact_keys(source['association'], 'store_uuid process_uuid')
        store_uuid(source['association']['store_uuid'])
        uuid(source['association']['process_uuid'])
        identity = (source['association']['store_uuid'], source['result_uuid'])
        label = source['label']
        if (
            label != 'r' + UUID(source['result_uuid']).hex
            or label in sources
            or identity in identities
            or source['source_run_id'] in runs
            or source['request']['run_id'] != source['source_run_id']
            or source['request']['scope'] != config['study_id']
        ):
            raise ValueError('Ambiguous source identity')
        sources[label] = source
        runs.add(source['source_run_id'])
        identities.add(identity)
    if list(sources) != sorted(sources):
        raise ValueError('Ordered sources required')
    expected = []
    used = set()
    for item in config['inputs']:
        binding = item['result_binding']
        if binding is None:
            continue
        exact_keys(
            binding,
            (
                'source_run_id source_output results_digest source_confi'
                'guration_digest original_value original_units conversio'
                'n labels'
            ),
        )
        uuid(binding['source_run_id'])
        port(binding['source_output'])
        sha(binding['results_digest'])
        sha(binding['source_configuration_digest'])
        scalar(binding['original_value'])
        labels = binding['labels']
        exact_keys(labels, 'run_name model_name model_revision_id instance_name output_name')
        uuid(labels['model_revision_id'])
        if (
            any(
                not isinstance(labels[k], str) for k in ('run_name', 'instance_name', 'output_name')
            )
            or labels['model_name'] is not None
            and not isinstance(labels['model_name'], str)
        ):
            raise ValueError('Typed source labels required')
        conversion = binding['conversion']
        exact_keys(
            conversion,
            'policy catalog_digest source_units destination_units factor destination_value',
        )
        sha(conversion['catalog_digest'])
        scalar(conversion['factor'])
        scalar(conversion['destination_value'])
        if (
            conversion['policy'] != 'openmdao-linear-catalog-1'
            or conversion['source_units'] != item['units']
            or not isinstance(conversion['destination_units'], str)
            or item['value'] != binding['original_value']
            or item['units'] != binding['original_units']
            or item['value'] * conversion['factor'] != conversion['destination_value']
        ):
            raise ValueError('Frozen original scalar mismatch')
        matched = [s for s in sources.values() if s['source_run_id'] == binding['source_run_id']]
        if len(matched) != 1 or matched[0]['results_digest'] != binding['results_digest']:
            raise ValueError('Exact scalar source required')
        label = matched[0]['label']
        used.add(label)
        expected.append(
            dict(
                target=item['target'],
                source_label=label,
                **{
                    k: binding[k]
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
    for row in deps['mappings']:
        exact_keys(
            row,
            (
                'target source_label source_output results_digest origin'
                'al_value original_units conversion'
            ),
        )
        port(row['target'])
        port(row['source_output'])
        scalar(row['original_value'])
        conversion = row['conversion']
        exact_keys(
            conversion,
            'policy catalog_digest source_units destination_units factor destination_value',
        )
        scalar(conversion['factor'])
        scalar(conversion['destination_value'])
    if used != set(sources) or deps['mappings'] != sorted(
        expected, key=lambda m: port(m['target'])
    ):
        raise ValueError('Complete scalar mapping mismatch')
    return config


def verify_program_pins(manifest, files, prepared, model, config):
    """Bind unchanged generated descriptors and exact source/package bytes."""
    roles = {row['path']: row['role'] for row in manifest['files']}
    if (
        roles.get('modeling-configuration.json') != 'modeling_configuration'
        or roles.get('result-dependencies.json') != 'result_dependencies'
    ):
        raise ValueError('Frozen application file role mismatch')
    for key in (
        'model_revision_id',
        'configuration_revision_id',
        'model_digest',
        'required_capabilities',
        'result_protocol_version',
    ):
        if manifest[key] != prepared[key]:
            raise ValueError('Prepared manifest identity mismatch')
    if (
        prepared['model_id'] != model['model_id']
        or prepared['model_revision_id'] != model['model_revision_id']
        or prepared['configuration_revision_id'] != config['configuration_revision_id']
        or manifest['generator'] != prepared['generator_identity']
        or model['required_capabilities'] != model_capabilities(model)
        or prepared['required_capabilities'] != model['required_capabilities']
    ):
        raise ValueError('Frozen program identity or capability mismatch')
    projected = frozen_json(files['modeling-configuration.json'])
    if projected['required_capabilities'] != model['required_capabilities']:
        raise ValueError('Unknown configuration capability')
    fields = object_fields(files['configuration.json'])
    if (
        files['context.json'] != fields['context_snapshot']
        or files['evidence/index.json'] != fields['evidence_snapshots']
    ):
        raise ValueError('Frozen context/evidence bytes mismatch')
    prepared_fields = object_fields(files['preparation.json'])
    package_raw = prepared_fields['model_package_manifest']
    package = frozen_json(package_raw)
    verify_object_digest(package_raw)
    if (
        package['schema_version'] != model['schema_version']
        or package['model_id'] != model['model_id']
        or package['model_revision_id'] != model['model_revision_id']
        or package['required_capabilities'] != model['required_capabilities']
    ):
        raise ValueError('Package identity mismatch')
    revisions = array_items(object_fields(package_raw)['revisions'])
    parent = None
    seen = set()
    package_files = {}
    for raw in revisions:
        pin = frozen_json(raw)
        verify_object_digest(raw)
        uuid(pin['model_revision_id'])
        if (
            pin['model_id'] != model['model_id']
            or pin['parent_model_revision_id'] != parent
            or pin['model_revision_id'] in seen
        ):
            raise ValueError('Package ancestry mismatch')
        parent = pin['model_revision_id']
        seen.add(parent)
        package_files['revisions/' + parent + '.json'] = raw
        for source in pin['source_files']:
            data = base64.b64decode(source['bytes'], validate=True)
            if hashlib.sha256(data).hexdigest() != source['sha256']:
                raise ValueError('Package source mismatch')
            package_files['sources/' + source['sha256'] + '.py'] = data
    if not revisions or revisions[-1] != files['model.json']:
        raise ValueError('Selected model package mismatch')

    def inventory(rows, content, exact=False):
        paths = set()
        for row in rows:
            path = row['path']
            if (
                path in paths
                or path not in content
                or row['size'] != len(content[path])
                or row['sha256'] != hashlib.sha256(content[path]).hexdigest()
            ):
                raise ValueError('Prepared/package inventory mismatch')
            paths.add(path)
        if exact and paths != set(content):
            raise ValueError('Package inventory closure mismatch')

    inventory(package['files'], package_files, True)
    inventory(prepared['files'], files)
    sources = {}
    for source in model['source_files']:
        raw = base64.b64decode(source['bytes'], validate=True)
        path = 'sources/' + source['sha256'] + '.py'
        if (
            path in sources
            or hashlib.sha256(raw).hexdigest() != source['sha256']
            or files.get(path) != raw
        ):
            raise ValueError('Selected source mismatch')
        sources[path] = raw
    if set(sources) != {p for p in files if p.startswith('sources/')}:
        raise ValueError('Source inventory mismatch')
    # Rebuild only the tiny descriptor digest object, never the scientific graph.
    generated = []
    for raw in array_items(prepared_fields['files']):
        row = object_fields(raw)
        if frozen_json(row['path']).startswith('generated/'):
            generated.append(
                (
                    frozen_json(row['path']),
                    object_bytes({k: row[k] for k in ('path', 'size', 'sha256')}),
                )
            )
    content = {
        k: prepared_fields[k]
        for k in ('model_digest', 'configuration_digest', 'generator_identity')
    }
    content['protocol'] = object_fields(prepared_fields['entrypoint'])['protocol']
    content['files'] = b'[' + b','.join(raw for _, raw in sorted(generated)) + b']'
    if hashlib.sha256(object_bytes(content)).hexdigest() != prepared['executable_content_digest']:
        raise ValueError('Executable descriptor digest mismatch')
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    instances = {i['instance_id']: i for i in model['instances']}
    if len(definitions) != len(model['definitions']) or len(instances) != len(model['instances']):
        raise ValueError('Duplicate model identity')
    ports = {}
    for iid, instance in instances.items():
        uuid(iid)
        uuid(instance['definition_version_id'])
        definition = definitions[instance['definition_version_id']]
        for row in definition['ports']:
            uuid(row['port_id'])
            key = (iid, row['port_id'])
            if key in ports or row['definition_version_id'] != definition['definition_version_id']:
                raise ValueError('Invalid port owner')
            ports[key] = row
        if any('sources/' + s + '.py' not in sources for s in definition['source_refs']):
            raise ValueError('Missing definition source')
    incoming = set()
    for wire in model['connections']:
        src, tgt = port(wire['source_ref']), port(wire['target_ref'])
        if (
            ports[src]['direction'] != 'output'
            or ports[tgt]['direction'] != 'input'
            or tgt in incoming
        ):
            raise ValueError('Invalid connection')
        incoming.add(tgt)
    free = {k for k, v in ports.items() if v['direction'] == 'input'} - incoming
    outputs = {k for k, v in ports.items() if v['direction'] == 'output'}
    if {port(i['target']) for i in config['inputs']} != free:
        raise ValueError('Incomplete frozen inputs')
    if any(port(c['target']) not in outputs for c in config['criteria']):
        raise ValueError('Invalid criterion target')
    bindings = frozen_json(files[prepared['entrypoint']['bindings_path']])
    if bindings['schema_version'] != '1':
        raise ValueError('Unsupported bindings version')
    components = {c['component_id']: c for c in bindings['components']}
    if (
        len(components) != len(bindings['components'])
        or len({c['path'] for c in components.values()}) != len(components)
        or len({c['instance_id'] for c in components.values()}) != len(components)
        or {c['instance_id'] for c in components.values()} != set(instances)
    ):
        raise ValueError('Incomplete component observations')
    paths = set()
    targets = set()
    for name, expected in (('inputs', free), ('outputs', outputs)):
        observed = set()
        for row in bindings[name]:
            target = port(row['target'])
            component = components[row['component_id']]
            if (
                target not in expected
                or target in targets
                or row['path'] in paths
                or row['units']
                != (
                    unit_meaning(ports[target]['units'])
                    if model['schema_version'] in ('3', '4')
                    else ports[target]['units']
                )
                or component['instance_id'] != target[0]
                or row['path'].rsplit('.', 1)[0] != component['path']
            ):
                raise ValueError('Invalid observation binding')
            observed.add(target)
            targets.add(target)
            paths.add(row['path'])
        if observed != expected:
            raise ValueError('Incomplete binding coverage')
    mapping = frozen_json(files[prepared['entrypoint']['source_map_path']])
    owners = set()
    if mapping['schema_version'] != '1':
        raise ValueError('Unsupported source mapping')
    for row in mapping['entries']:
        iid = row['instance_id']
        definition = definitions[instances[iid]['definition_version_id']]
        source = row['source_sha256']
        if (
            (iid, source) in owners
            or row['definition_version_id'] != definition['definition_version_id']
            or source not in definition['source_refs']
            or row['source_path'] != 'sources/' + source + '.py'
            or row['source_path'] not in sources
            or not row['generated_path'].startswith('generated/')
            or not row['generated_path'].endswith('.py')
            or not 1
            <= row['generated_line_start']
            <= row['generated_line_end']
            <= len(files[row['generated_path']].splitlines())
        ):
            raise ValueError('Invalid source ownership/range')
        owners.add((iid, source))
    if owners != {
        (iid, s)
        for iid, i in instances.items()
        for s in definitions[i['definition_version_id']]['source_refs']
    }:
        raise ValueError('Incomplete source mapping')


def bundle_layout(manifest):
    version = manifest.get('schema_version')
    if version == '10':
        layout = manifest.get('input_schema_version')
        if (
            layout not in ('2', '3', '4', '5', '6', '8', '9')
            or manifest['result_protocol_version'] != '2'
        ):
            raise ValueError('Unsupported bundle input layout or result protocol')
        return layout
    if version not in ('2', '3', '4', '5', '6', '8'):
        raise ValueError('Unsupported bundle version')
    if manifest.get('result_protocol_version') != '1':
        raise ValueError('Historical bundle result protocol mismatch')
    return version


def read_inputs(root, expected_digest=None, expected_manifest_sha256=None):
    root = Path(root)
    manifest_path = root / 'manifest.json'
    if (
        root.is_symlink()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.stat().st_nlink != 1
        or manifest_path.stat().st_size > 1048576
    ):
        raise ValueError('Invalid frozen manifest')
    raw_manifest = manifest_path.read_bytes()
    if len(raw_manifest) > 1048576:
        raise ValueError('Manifest size exceeded')
    manifest = frozen_json(raw_manifest)
    if bundle_layout(manifest) not in ('2', '3', '4', '5', '6', '8', '9'):
        raise ValueError('Unsupported bundle version; create a new run command')
    if bundle_layout(manifest) in ('5', '6', '8', '9'):
        exact_keys(
            manifest,
            (
                'schema_version bundle_id run_id prepared_digest model_r'
                'evision_id configuration_revision_id model_digest confi'
                'guration_digest files generator dependencies runtime re'
                'quired_capabilities licenses result_protocol_version bu'
                'ndle_digest entrypoint executable_content_digest modeli'
                'ng_configuration_digest result_dependencies approach_di'
                'gest approach_closure_digest'
            )
            + (' model_schema_version' if bundle_layout(manifest) in ('8', '9') else '')
            + (' input_schema_version' if manifest['schema_version'] == '10' else ''),
        )
    verify_object_digest(raw_manifest, 'bundle_digest')
    if expected_digest is not None and manifest['bundle_digest'] != expected_digest:
        raise ValueError('Immutable expected bundle digest mismatch')
    if (
        expected_manifest_sha256 is not None
        and hashlib.sha256(raw_manifest).hexdigest() != expected_manifest_sha256
    ):
        raise ValueError('Trusted manifest bytes mismatch')
    entry = manifest['entrypoint']
    if (
        set(entry) != {'protocol', 'module_path', 'factory', 'bindings_path', 'source_map_path'}
        or entry['protocol'] != PROTOCOL
        or entry['factory'] != 'build_model'
        or manifest['result_protocol_version'] not in ('1', '2')
    ):
        raise ValueError('Unsupported entrypoint protocol or factory')
    files = {}
    total = 0
    if not 0 < len(manifest['files']) <= 2000:
        raise ValueError('Frozen file count exceeded')
    for item in manifest['files']:
        name = item['path']
        parts = PurePosixPath(name).parts
        if (
            not parts
            or name.startswith('/')
            or '\\' in name
            or '\x00' in name
            or any(p in ('', '.', '..') for p in name.split('/'))
            or len(parts) > 16
            or len(name) > 512
            or name in files
        ):
            raise ValueError('Invalid frozen path')
        path = root / name
        if (
            any(p.is_symlink() for p in [path, *path.parents])
            or not path.is_file()
            or path.stat().st_nlink != 1
        ):
            raise ValueError('Nonregular frozen file')
        if type(item['size']) is not int or not 0 <= item['size'] <= 32 * 1024 * 1024:
            raise ValueError('Invalid frozen file size')
        total += item['size']
        if total > 32 * 1024 * 1024 or path.stat().st_size != item['size']:
            raise ValueError('Frozen size exceeded')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Frozen bytes mismatch')
        files[name] = raw
    if {str(p.relative_to(root)) for p in root.rglob('*') if not p.is_dir()} != {
        'manifest.json',
        *files,
    }:
        raise ValueError('Unexpected frozen file')
    for key in ('module_path', 'bindings_path', 'source_map_path'):
        if entry[key] not in files or not entry[key].startswith('generated/'):
            raise ValueError('Missing declared entrypoint file')
    prepared = frozen_json(files['preparation.json'])
    verify_object_digest(files['preparation.json'], 'prepared_digest')
    if (prepared.get('schema_version'), manifest['result_protocol_version']) not in (
        ('2', '1'),
        ('3', '2'),
    ):
        raise ValueError('Unsupported preparation version')
    for key in ('entrypoint', 'prepared_digest', 'executable_content_digest'):
        if manifest[key] != prepared[key]:
            raise ValueError('Prepared execution binding mismatch')
    model = frozen_json(files['model.json'])
    if bundle_layout(manifest) == '6' and model['schema_version'] not in ('2', '3', '4'):
        raise ValueError('Invalid configuration/model version pairing')
    if (
        bundle_layout(manifest) in ('8', '9')
        and manifest['model_schema_version'] != model['schema_version']
    ):
        raise ValueError('Exact Bundle8 model version mismatch')
    if model['schema_version'] in ('3', '4'):
        if (
            model['schema_version'] == '4' and bundle_layout(manifest) not in ('8', '9')
        ) or bundle_layout(manifest) not in ('6', '8', '9'):
            raise ValueError('Invalid configuration/model version pairing')
        verify_unit_declarations(model)
    if verify_object_digest(files['model.json']) != manifest['model_digest']:
        raise ValueError('Frozen model digest mismatch')
    configuration = verify_configuration_domains(manifest, files, prepared)
    if model['schema_version'] == '2' and configuration['schema_version'] not in ('3', '4'):
        raise ValueError('Invalid configuration/model version pairing')
    if configuration['schema_version'] == '4' and model['schema_version'] not in ('2', '3', '4'):
        raise ValueError('Invalid configuration/model version pairing')
    if bundle_layout(manifest) in ('4', '5', '6', '8', '9'):
        verify_program_pins(manifest, files, prepared, model, configuration)
    if uses_typed_units(model):
        verify_unit_catalog(manifest, files, prepared, model, configuration)
    return manifest, model, configuration


class Assignments:
    """Observe successful vector writes; prohibit mutation through returned views."""

    def __init__(self, vector, assigned):
        self.vector, self.assigned = vector, assigned

    def __getitem__(self, key):
        value = self.vector[key].copy()
        value.flags.writeable = False
        return value

    def __setitem__(self, key, value):
        self.vector[key] = value
        self.assigned.add(key)

    def __contains__(self, key):
        return key in self.vector

    def keys(self):
        return self.vector.keys()


def observe_compute(compute, component, state):
    """Wrap one native call, using the program/1 availability_observer protocol."""

    def observed(inputs, outputs, *args, **kwargs):
        state.update(completed=False, assigned=set())
        component._hyprn_mvp_assigned = set()
        component._hyprn_mvp_completed = False
        writes = set()
        try:
            if any(not math.isfinite(float(inputs[key][0])) for key in inputs.keys()):
                raise ValueError('Nonfinite or unavailable component input')
            compute(inputs, Assignments(outputs, writes), *args, **kwargs)
            state['completed'] = component._hyprn_mvp_completed is True
        finally:
            # Generated reset writes do not belong to the authored assignment set.
            assigned = component._hyprn_mvp_assigned
            if not isinstance(assigned, set):
                raise ValueError('Invalid availability observer')
            state['assigned'] = writes & assigned

    return observed


def generated_origin(obj, root, manifest):
    """Identify actual loaded classes and their frozen implementation/base files."""
    declared = {f['path']: f['sha256'] for f in manifest['files']}
    origins = []
    for cls in type(obj).__mro__:
        try:
            filename = inspect.getsourcefile(cls)
        except TypeError:
            continue
        if not filename:
            continue
        path = Path(filename).resolve()
        try:
            relative = path.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if not relative.startswith('generated/') or relative not in declared:
            raise ValueError('Undeclared generated class origin')
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != declared[relative]:
            raise ValueError('Generated class origin hash mismatch')
        origins.append(dict(module=cls.__module__, name=cls.__name__, path=relative, sha256=sha))
    if not origins or origins[0]['module'] != type(obj).__module__:
        raise ValueError('Factory must return a frozen generated class')
    return origins


def load_program(root, manifest):
    """The only candidate import seam; execute() calls it after byte verification."""
    entry = manifest['entrypoint']
    sys.path.insert(0, str(root / 'generated'))
    spec = importlib.util.spec_from_file_location(
        '_hyprn_mvp_frozen_entry', root / entry['module_path']
    )
    if spec is None or spec.loader is None:
        raise ValueError('Missing native program entrypoint')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, 'build_model', None)
    if not callable(factory):
        raise ValueError('Missing fixed build_model factory')
    return factory()


def diagnostic_catalog(root, manifest, source_map):
    """Freeze data-only source coordinates before candidate code runs.

    Mapping is usable only if both retained hashes and the exact recorded
    indentation/line normalization prove a one-to-one authored line mapping.
    A missing proof omits diagnostics; it never changes scientific admission.
    """
    declared = {f['path']: f['sha256'] for f in manifest['files']}
    catalog = {}
    for row in source_map.get('entries', []):
        try:
            source, generated = row['source_path'], row['generated_path']
            sha(row['source_sha256'])
            if (
                source != 'sources/' + row['source_sha256'] + '.py'
                or not generated.startswith('generated/')
                or any(p in ('', '.', '..') for p in generated.split('/'))
            ):
                continue
            uuid(row['instance_id'])
            uuid(row['definition_version_id'])
            raw = (root / source).read_bytes()
            body = (root / generated).read_bytes()
            if (
                hashlib.sha256(raw).hexdigest() != row['source_sha256']
                or declared.get(source) != row['source_sha256']
                or hashlib.sha256(body).hexdigest() != declared.get(generated)
            ):
                continue
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            lines = text.splitlines()
            start, end = row['generated_line_start'], row['generated_line_end']
            if (
                type(start) is not int
                or type(end) is not int
                or start < 1
                or end - start + 1 != len(lines)
                or body.decode('utf-8').splitlines()[start - 1 : end]
                != ['        ' + line for line in lines]
            ):
                continue
            tree = ast.parse(text)
            literals = []
            for node in ast.walk(tree):
                message = name = None
                if isinstance(node, ast.Assert):
                    name, message = 'AssertionError', node.msg
                elif (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and isinstance(node.exc.func, ast.Name)
                    and len(node.exc.args) == 1
                    and not node.exc.keywords
                ):
                    name, message = node.exc.func.id, node.exc.args[0]
                if name and isinstance(message, ast.Constant) and type(message.value) is str:
                    literals.append((node.lineno, node.end_lineno, name, message.value))
            if generated in catalog:
                catalog[generated] = None  # Ambiguous mapping never picks a winner.
            else:
                catalog[generated] = (dict(row), literals)
        except (
            KeyError,
            ValueError,
            TypeError,
            UnicodeError,
            SyntaxError,
            OSError,
            RecursionError,
        ):
            continue
    return catalog


def _literal_diagnostic(text):
    """Bounded source literal, never an exception value or a general secret filter."""
    text = text[:2048]
    # Withhold path/credential-like literals entirely, without echoing values.
    if re.search(
        (
            '[/\\\\]|(?i:password|passwd|secret|token|credential|autho'
            'rization|api[_ -]?key|bearer|private[_ -]?key)'
        ),
        text,
    ) or re.search(r'\b(?:AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{12,})', text):
        return '[message withheld]'
    return ' '.join(''.join(c if c.isprintable() else ' ' for c in text).split())[:512]


def runtime_diagnostic(exc, catalog, authored_codes):
    """Use registered frozen code identities; never stringify exception objects."""
    names = {
        t: t.__name__
        for t in (
            AssertionError,
            ValueError,
            RuntimeError,
            TypeError,
            KeyError,
            IndexError,
            AttributeError,
            ZeroDivisionError,
            OverflowError,
            FloatingPointError,
            ArithmeticError,
            NameError,
            UnboundLocalError,
            OSError,
        )
    }
    name = names.get(type(exc), 'Exception')
    result = name
    tb = BaseException.__traceback__.__get__(exc)
    for _ in range(64):
        if tb is None:
            break
        code = tb.tb_frame.f_code
        registered = authored_codes.get(id(code))
        if registered and registered[0] is code:
            entry = catalog.get(registered[1])
            if entry:
                row, literals = entry
                line = tb.tb_lineno - row['generated_line_start'] + 1
                if 1 <= line <= row['generated_line_end'] - row['generated_line_start'] + 1:
                    # An error while evaluating an assert condition/raise argument
                    # is not evidence that its literal message was actually raised.
                    raised = (
                        0 <= tb.tb_lasti < len(code.co_code)
                        and code.co_code[tb.tb_lasti] == dis.opmap['RAISE_VARARGS']
                    )
                    matches = [
                        m
                        for first, last, kind, m in literals
                        if raised and first <= line <= last and kind == name
                    ]
                    message = _literal_diagnostic(matches[0]) if len(matches) == 1 else ''
                    result = name + (': ' + message if message else '')
                    result += (
                        f' [source {row["source_path"]}:{line}; instance {row["instance_id"]}; '
                        f'definition {row["definition_version_id"]}]'
                    )
        tb = tb.tb_next
    return result


def execute(root, expected_digest, expected_manifest_sha256):
    root = Path(root)
    manifest, model, configuration = read_inputs(root, expected_digest, expected_manifest_sha256)
    import openmdao.api as om
    from openmdao.utils.units import unit_conversion

    if model['required_capabilities'] != model_capabilities(model):
        raise ValueError('Unsupported model capability')
    if configuration['numerical'] != dict(
        mode='deterministic',
        initialization=[],
        solvers=[],
        derivatives=dict(method='none', form=None, check=None),
        design_variables=[],
        objectives=[],
        constraints=[],
        optimizer=None,
        uncertainty=None,
    ):
        raise ValueError('Unsupported numerical mode')
    entry = manifest['entrypoint']
    bindings = json.loads((root / entry['bindings_path']).read_bytes())
    if bindings.get('schema_version') != '1':
        raise ValueError('Unsupported bindings version')
    source_map = json.loads((root / entry['source_map_path']).read_bytes())
    source_paths = {item['instance_id']: item['generated_path'] for item in source_map['entries']}
    diagnostics = diagnostic_catalog(root, manifest, source_map)
    authored_codes = {}
    group = load_program(root, manifest)
    if not isinstance(group, om.Group):
        raise ValueError('Native factory must return an OpenMDAO Group')
    origins = dict(group=generated_origin(group, root, manifest), components=[])
    problem = om.Problem(model=group, reports=False)
    states = {
        c['component_id']: dict(completed=False, assigned=set()) for c in bindings['components']
    }
    outputs = []
    error = None
    try:
        problem.setup()
        components = {
            c.pathname: c
            for c in group.system_iter(recurse=True, typ=om.ExplicitComponent)
            if not (c.pathname == '_auto_ivc' and isinstance(c, om.IndepVarComp))
        }
        if set(components) != {c['path'] for c in bindings['components']}:
            raise ValueError('Generated component inventory mismatch')
        for binding in bindings['components']:
            component = components[binding['path']]
            classes = generated_origin(component, root, manifest)
            if classes[0]['path'] != source_paths[binding['instance_id']]:
                raise ValueError('Generated component source-map mismatch')
            origins['components'].append(
                dict(component_id=binding['component_id'], classes=classes)
            )
            authored = inspect.getattr_static(type(component), '_authored_compute', None)
            if type(authored) is types.FunctionType:
                path = source_paths[binding['instance_id']]
                pending = [authored.__code__]
                while pending:
                    code = pending.pop()
                    if Path(code.co_filename).resolve() == (root / path).resolve():
                        authored_codes[id(code)] = (code, path)
                        pending.extend(c for c in code.co_consts if type(c) is types.CodeType)
            component.compute = observe_compute(
                component.compute, component, states[binding['component_id']]
            )
        for direction in ('inputs', 'outputs'):
            metadata = group.get_io_metadata(
                iotypes=direction[:-1], metadata_keys=['units', 'shape'], return_rel_names=False
            )
            for binding in bindings[direction]:
                meta = metadata.get(binding['path'])
                if meta is None or meta['shape'] != (1,):
                    raise ValueError('Generated scalar binding mismatch')
                actual, declared = meta['units'] or '', binding['units']
                # OpenMDAO canonicalizes aliases (e.g. K to degK). Require
                # identical native units, not merely compatible/scaled units.
                if actual != declared and (
                    not actual or not declared or unit_conversion(actual, declared) != (1.0, 0.0)
                ):
                    raise ValueError('Generated scalar binding units mismatch')
        assignments = {
            (v['target']['instance_id'], v['target']['port_id']): v for v in configuration['inputs']
        }
        if len(assignments) != len(configuration['inputs']) or len(assignments) != len(
            bindings['inputs']
        ):
            raise ValueError('Explicit input inventory mismatch')
        for binding in bindings['inputs']:
            value = assignments[(binding['target']['instance_id'], binding['target']['port_id'])]
            if type(value['value']) not in (int, float) or not math.isfinite(value['value']):
                raise ValueError('Explicit finite input required')
            old, new = value['units'] or None, binding['units'] or None
            if bool(old) != bool(new):
                raise ValueError('Incompatible input units')
            if old:
                _, offset = unit_conversion(old, new)
                if offset:
                    raise ValueError('Affine unit conversion unsupported')
            problem.set_val(binding['path'], value['value'], units=old)
        # This bounded diagnostic is retained in raw launcher output, not a public
        # result field or an attestation claim. Active origin proof belongs to12-3.
        print(
            'HYPRN_MVP_NATIVE_ORIGINS_V1 ' + json.dumps(origins, separators=(',', ':')), flush=True
        )
        problem.run_model()
    except Exception as exc:
        error = runtime_diagnostic(exc, diagnostics, authored_codes)
    for binding in bindings['outputs']:
        state = states[binding['component_id']]
        assigned = binding['path'].rsplit('.', 1)[-1] in state['assigned']
        value = None
        reason = (
            'producer_failed' if not state['completed'] else 'unassigned' if not assigned else None
        )
        if reason is None:
            try:
                value = float(problem.get_val(binding['path'])[0])
                if not math.isfinite(value):
                    value = None
                    reason = 'nonfinite'
            except Exception:
                value = None
                reason = 'unavailable'
        outputs.append(
            dict(
                target=binding['target'],
                value=value,
                units=binding['units'],
                availability='available' if reason is None else 'unavailable',
                reason=reason,
                producer_completed=state['completed'],
                assigned=assigned,
            )
        )
    available = sum(o['availability'] == 'available' for o in outputs)
    complete = available == len(outputs) and error is None
    result = dict(
        schema_version=manifest['result_protocol_version'],
        run_id=manifest['run_id'],
        bundle_digest=manifest['bundle_digest'],
        execution=dict(
            state='finished' if complete else 'failed',
            exit_code=0 if complete else 1,
            message=error or ('completed' if complete else 'incomplete_outputs'),
        ),
        outputs=outputs,
        criteria=[],
        artifacts=[],
    )
    if manifest['result_protocol_version'] == '1':
        result.update(
            convergence=dict(state='not_applicable', diagnostics_ref=None),
            optimization=dict(termination='not_applicable', feasibility='not_applicable'),
            completeness=dict(
                expected=len(outputs),
                available=available,
                failed=sum(not o['producer_completed'] for o in outputs),
                unavailable=len(outputs) - available,
            ),
            applicability=dict(state='unassessed', evidence_refs=[]),
        )
    result['criteria'] = evaluate_criteria(result, configuration['criteria'], unit_conversion)
    return result


def main():
    if len(sys.argv) != 4 or os.getuid() == 0:
        raise RuntimeError('Restricted fixed entrypoint and trusted input pins required')
    result = execute(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
    print(
        '\nHYPRN_MVP_RESULT_V'
        + result['schema_version']
        + ' '
        + json.dumps(result, allow_nan=False, separators=(',', ':')),
        flush=True,
    )


if __name__ == '__main__':
    main()
