"""Bounded, data-only validation of an exact Modeling approach closure.

No stores, model client, candidate imports or live lookup. Callers authorize and
resolve records before build_closure; historical readers use validate_closure.
Evidence has no independent digest field: its exact bytes are authenticated by
the enclosing closure (and checked against embedded configuration snapshots).
"""
from copy import deepcopy
import base64
import hashlib
import math

from .contracts import DomainError, canonical, digest, validate
from .units import UNIT_CATALOG_DIGEST, resolved_model_units, unit_readiness, require_engine_unit

KEYS = dict(approach_versions='approach_version_id', models='model_revision_id',
            configurations='configuration_revision_id', run_contexts='run_id',
            evidence='evidence_version_id')
MAX_BYTES = 8 * 1024 * 1024
MAX_CONTENT = 1024 * 1024
MAX_ENTITIES = 1000
MAX_DEPTH = 16


class ReferenceIssue(ValueError):
    """Curated authoring detail; never carries arbitrary remote exception text."""
    def __init__(self, path, message):
        super().__init__(message)
        self.issue = dict(path=path, code='invalid_reference', message=message)


def _reference(ok, path, message):
    if not ok:
        raise ReferenceIssue(path, message)


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _closed(name, value):
    try:
        validate(name, value)
    except (DomainError, TypeError, KeyError) as exc:
        raise ValueError('Invalid ' + name) from exc


def _signed(value):
    _require(value['digest'] == digest({k: v for k, v in value.items() if k != 'digest'}),
             'Record digest mismatch')


def _index(rows, key):
    result = {}
    for row in rows:
        identity = tuple(row[k] for k in key) if isinstance(key, tuple) else row[key]
        label = '/'.join(key) if isinstance(key, tuple) else key
        _require(identity not in result, 'Duplicate ' + label)
        result[identity] = row
    return result


def _links(rows):
    pairs = [(r['evidence_version_id'], r['relation']) for r in rows]
    _require(len(pairs) == len(set(pairs)), 'Duplicate evidence relationship')
    return {eid for eid, _ in pairs}


def closure_schema(version, resolution):
    """Select from exact reachable records; an ancestor keeps its own family."""
    return '3' if (version['schema_version'] == '2'
                   or any(v['schema_version'] == '2' for v in resolution['approach_versions'])
                   or any(m['schema_version'] == '4' for m in resolution['models'])) else '1'


def _envelope(root, tables, reached):
    selected = {table: [tables[table][key] for kind, key in reached if kind == table]
                for table in KEYS}
    result = dict(schema_version=closure_schema(root, selected), root_approach_version_id=root['approach_version_id'],
                  root_approach_digest=root['digest'])
    for table in KEYS:
        result[table] = [tables[table][key] for kind, key in sorted(reached) if kind == table]
    result['digest'] = digest(result)
    return result


class _Closure:
    def __init__(self, value, study_id):
        _require(len(canonical(value)) <= MAX_BYTES, 'Closure byte limit')
        _closed('ApproachClosureRead3', value)
        _require(sum(len(value[k]) for k in KEYS) <= MAX_ENTITIES, 'Closure entity limit')
        _require(len(value['configurations']) + len(value['run_contexts']) <= 64,
                 'Prior record limit')
        self.tables = {k: _index(value[k], field) for k, field in KEYS.items()}
        self.root = self.get('approach_versions', value['root_approach_version_id'])
        self.sid = self.root['study_id']
        _require(study_id is None or study_id == self.sid, 'Foreign approach study')
        _require(value['root_approach_digest'] == self.root['digest'], 'Root digest mismatch')
        self.edges = {}
        self.pins = []
        for table, records in self.tables.items():
            for key, record in records.items():
                if table != 'evidence':
                    _signed(record)
                if 'study_id' in record:
                    _require(record['study_id'] == self.sid, 'Foreign study record')
                self.edges[(table, key)] = set()
        for model in self.tables['models'].values():
            self.model(model)
        for row in self.tables['evidence'].values():
            scope = row.get('resource_scope')
            if scope:
                _require(scope['study_id'] == self.sid, 'Foreign evidence scope')
            if row.get('evidence_schema_version') == '3':
                _require(row['parent_evidence_version_id'] != row['evidence_version_id'],
                         'Self evidence parent')
                for label in row['recorded_context']['resource_labels']:
                    if label['kind'] == 'study':
                        _require(label['resource_id'] == self.sid, 'Foreign evidence label')
        for row in self.tables['approach_versions'].values():
            self.approach(row)
        for row in self.tables['configurations'].values():
            self.configuration(row)
        for row in self.tables['run_contexts'].values():
            self.run(row)

    def get(self, table, key):
        try:
            return self.tables[table][key]
        except KeyError as exc:
            raise ValueError('Missing exact ' + table + ' reference') from exc

    def edge(self, node, table, key):
        row = self.get(table, key)
        self.edges[node].add((table, key))
        return row

    def evidence(self, node, ids):
        for eid in ids:
            self.edge(node, 'evidence', eid)

    def model(self, model):
        node = ('models', model['model_revision_id'])
        if model['schema_version']=='3':
            try:
                unit_readiness(model)  # Structural validation only for data-only references.
            except DomainError as exc:
                raise ValueError('Invalid retained model units') from exc
        definitions = _index(model['definitions'], 'definition_version_id')
        instances = _index(model['instances'], 'instance_id')
        ports = _index(model['ports'], ('definition_version_id', 'port_id'))
        _index(model['connections'], 'connection_id')
        # The native public snapshot represents the model root separately;
        # instances enumerates its concrete components. Retained older shapes
        # may also list a root. Exact component/port refs still require membership.
        sources = _index(model['source_files'], 'sha256')
        for source in sources.values():
            try:
                raw = base64.b64decode(source['bytes'], validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError('Invalid source bytes') from exc
            _require(hashlib.sha256(raw).hexdigest() == source['sha256'], 'Source hash mismatch')
        for definition in definitions.values():
            _require(set(definition['source_refs']) <= set(sources), 'Missing definition source')
            definition_ports = _index(definition['ports'], 'port_id')
            descriptions = _index(definition.get('quantity_definitions', []), 'port_id')
            _require(set(descriptions) <= set(definition_ports),
                     'Unknown quantity definition port_id')
            for port in definition['ports']:
                _require(ports.get((definition['definition_version_id'], port['port_id'])) == port and
                         port['definition_version_id'] == definition['definition_version_id'],
                         'Definition port mismatch')
        for instance in instances.values():
            _require(instance['definition_version_id'] in definitions, 'Missing definition')
        for port in ports.values():
            owner = definitions.get(port['definition_version_id'])
            _require(owner is not None and port in owner['ports'], 'Port definition mismatch')
        for conn in model['connections']:
            self.port(model, conn['source_ref'])
            self.port(model, conn['target_ref'])
        assumptions = _index(model.get('assumptions', []), 'assumption_id')
        for assumption in assumptions.values():
            owner = assumption['owner']
            if owner['kind'] == 'instance':
                _require(owner['instance_id'] in instances and
                         owner['instance_id'] != model['root_instance_id'], 'Invalid assumption owner')
            self.evidence(node, _links(assumption['evidence_links']))

    def port(self, model, ref, path=None):
        instances = {r['instance_id']: r for r in model['instances']}
        i = instances.get(ref['instance_id'])
        ports = [p for p in model['ports'] if i is not None and
                 (p['definition_version_id'], p['port_id']) == (i['definition_version_id'], ref['port_id'])]
        if path is not None:
            _reference(len(ports) == 1, path, f"Port {ref['port_id']} does not resolve uniquely for instance {ref['instance_id']} in model revision {model['model_revision_id']}.")
        else:
            _require(len(ports) == 1, 'Invalid instance port')

    def approach(self, version):
        node = ('approach_versions', version['approach_version_id'])
        c = version['content']
        _require(len(canonical(c)) <= MAX_CONTENT, 'Approach content byte limit')
        bindings = _index(c['model_bindings'], 'binding_id')
        steps = _index(c['steps'], 'step_id')
        assumptions = _index(c['assumptions'], 'assumption_id')
        _index(c['cases'], 'case_id')
        limits = _index(c.get('limit_items', []), 'limit_id')
        for limit in limits.values():
            self.evidence(node, _links(limit['evidence_links']))
        bound = {}
        for bid, binding in bindings.items():
            m = self.edge(node, 'models', binding['model_revision_id'])
            _require(m['model_id'] == binding['model_id'], 'Model binding mismatch')
            bound[bid] = m
        used = set()
        for step_index, step in enumerate(steps.values()):
            deps = step['intent']['depends_on_step_ids']
            _require(set(deps) <= set(steps) and step['step_id'] not in deps,
                     'Invalid method dependency')
            self.evidence(node, _links(step['evidence_links']))
            for ref_index, ref in enumerate(step['implementation_refs']):
                path = f'/content/steps/{step_index}/implementation_refs/{ref_index}'
                bid = ref['binding_id']
                _reference(bid in bound, path, f'Model binding {bid} is not present in this approach.')
                used.add(bid)
                m = bound[bid]
                if ref['kind'] in ('instance', 'port'):
                    _reference(ref['instance_id'] in {r['instance_id'] for r in m['instances']}, path,
                               f"Instance {ref['instance_id']} is not present in model revision {m['model_revision_id']}.")
                if ref['kind'] == 'port':
                    self.port(m, ref, path)
                if ref['kind'] == 'connection':
                    _reference(ref['connection_id'] in {r['connection_id'] for r in m['connections']}, path,
                               f"Connection {ref['connection_id']} is not present in model revision {m['model_revision_id']}.")
            for ref_index, ref in enumerate(step['assumption_refs']):
                path = f'/content/steps/{step_index}/assumption_refs/{ref_index}'
                if ref['kind'] == 'approach':
                    _reference(ref['assumption_id'] in assumptions, path, f"Assumption {ref['assumption_id']} is not present in this approach.")
                elif ref['kind'] == 'configuration':
                    cfg = self.edge(node, 'configurations', ref['configuration_revision_id'])
                    _reference(ref['assumption_id'] in {r['assumption_id'] for r in cfg.get('assumptions', [])}, path,
                               f"Assumption {ref['assumption_id']} is not present in configuration revision {ref['configuration_revision_id']}.")
                else:
                    _reference(ref['binding_id'] in bound, path, f"Model binding {ref['binding_id']} is not present in this approach.")
                    m = bound[ref['binding_id']]
                    _reference(ref['assumption_id'] in {r['assumption_id'] for r in m.get('assumptions', [])}, path,
                               f"Assumption {ref['assumption_id']} is not present in model revision {m['model_revision_id']}.")
                    origin = ref['origin']
                    if origin:
                        old = self.edge(node, 'approach_versions', origin['approach_version_id'])
                        _require(old['digest'] == origin['digest'], 'Origin digest mismatch')
                        prior = {a['assumption_id']: a for a in old['content']['assumptions']}.get(origin['assumption_id'])
                        _require(prior is not None and prior['role'] == 'proposed_model_condition',
                                 'Invalid assumption origin')
                        _require(origin['assumption_id'] not in assumptions, 'Duplicate active proposal')
        _require(used == set(bindings), 'Unused model binding')
        for assumption in assumptions.values():
            self.evidence(node, _links(assumption['evidence_links']))
        for case in c['cases']:
            _require(case['binding_id'] is None or case['binding_id'] in bindings, 'Missing case binding')
            self.evidence(node, _links(case['evidence_links']))
        for basis in c['basis_refs']:
            table, key = ('configurations', 'configuration_revision_id') if basis['kind'] == 'configuration' else ('run_contexts', 'run_id')
            self.edge(node, table, basis[key])

    def configuration(self, config):
        node = ('configurations', config['configuration_revision_id'])
        model = self.edge(node, 'models', config['model_revision_id'])
        _require(model['model_id'] == config['model_id'], 'Configuration model mismatch')
        _require(config['schema_version'] in {'1': ('1','2'), '2': ('3','4'), '3': ('4',), '4': ('4',)}[model['schema_version']],
                 'Configuration/model version mismatch')
        units=None
        if model['schema_version']=='3':
            try:
                units=resolved_model_units(model)
            except DomainError as exc:
                raise ValueError('Unresolved configured model units') from exc
        if model['schema_version'] == '4':
            # Read-only retained validation. Resolve each declaration from its
            # exact definition, never infer unit semantics from outer Model4.
            definitions = {d['definition_version_id']: d for d in model['definitions']}
            units = {}
            try:
                for instance in model['instances']:
                    definition = definitions[instance['definition_version_id']]
                    for port in definition['ports']:
                        declaration = port['units']
                        if isinstance(declaration, dict):
                            units[(instance['instance_id'], definition['definition_version_id'], port['port_id'])] = require_engine_unit(declaration)
            except DomainError as exc:
                raise ValueError('Unresolved configured model units') from exc
        snapshots = _index(config['evidence_snapshots'], 'evidence_version_id')
        required = set(config.get('general_context_evidence_version_ids', []))
        for a in list(model.get('assumptions', [])) + list(config.get('assumptions', [])):
            required.update(_links(a['evidence_links']))
        _index(config.get('assumptions', []), 'assumption_id')
        for item in config['inputs']:
            required.update(item['provenance']['evidence_version_ids'])
            binding = item.get('result_binding')
            if binding:
                run = self.edge(node, 'run_contexts', binding['source_run_id'])
                _require(run['configuration_digest'] == binding['source_configuration_digest'],
                         'Result source configuration mismatch')
                _require(run['results'] is not None and digest(run['results']) == binding['results_digest'],
                         'Result source digest mismatch')
                results = run['results']
                outputs = [o for o in results['outputs'] if o['target'] == binding['source_output']]
                _require(results['execution']['state'] == 'finished' and results['execution']['exit_code'] == 0
                         and len(outputs) == 1, 'Ineligible source result')
                output = outputs[0]
                _require(output['availability'] == 'available' and output['producer_completed']
                         and output['assigned'] and output['value'] is not None
                         and output['value'] == binding['original_value']
                         and output['units'] == binding['original_units']
                         and binding['labels']['model_revision_id'] == run['model_revision_id'],
                         'Result output correspondence mismatch')
                conversion = binding['conversion']
                target=item['target']
                instance=next((i for i in model['instances'] if i['instance_id']==target['instance_id']),None)
                unit_key=(target['instance_id'],instance['definition_version_id'],target['port_id']) if instance else None
                if units is not None and (model['schema_version']=='3' or unit_key in units):
                    destination=units.get(unit_key)
                    _require(item['value']==binding['original_value'] and item['units']==binding['original_units']
                             and conversion['source_units']==item['units']
                             and conversion['destination_units']==destination
                             and conversion['catalog_digest']==UNIT_CATALOG_DIGEST
                             and math.isfinite(conversion['factor'])
                             and math.isfinite(binding['original_value'] * conversion['factor'])
                             and binding['original_value'] * conversion['factor']==conversion['destination_value'],
                             'Result conversion mismatch')
                else:
                    _require(conversion['source_units'] == output['units']
                             and conversion['destination_units'] == item['units']
                             and conversion['destination_value'] == item['value']
                             and math.isfinite(binding['original_value'] * conversion['factor'])
                             and binding['original_value'] * conversion['factor'] == item['value'],
                             'Result conversion mismatch')
        for criterion in config['criteria']:
            required.update(criterion['evidence_version_ids'])
        if config['schema_version'] in ('3', '4'):
            _require(list(snapshots) == sorted(required), 'Exact configuration evidence required')
        for eid, row in snapshots.items():
            _require(self.edge(node, 'evidence', eid) == row, 'Configuration evidence bytes mismatch')
        for field in ('derivation', 'context_source'):
            source = config.get(field)
            if source and 'source_run_id' in source:
                run = self.edge(node, 'run_contexts', source['source_run_id'])
                _require(run['configuration_digest'] == source['source_configuration_digest'],
                         'Prior context digest mismatch')
                if field == 'derivation':
                    _require(run['configuration_revision_id'] == source['source_configuration_revision_id']
                             and run['runtime'] == source['source_runtime'], 'Derivation context mismatch')
        pin = config.get('approach_binding')
        if pin:
            version = self.edge(node, 'approach_versions', pin['approach_version_id'])
            _require(version['approach_id'] == pin['approach_id'] and version['digest'] == pin['approach_digest'],
                     'Approach pin identity mismatch')
            bindings = {b['binding_id']: b for b in version['content']['model_bindings']}
            matching = {bid for bid, b in bindings.items() if
                        b['model_id'] == config['model_id'] and b['model_revision_id'] == config['model_revision_id']}
            _require(bool(matching), 'Approach pin model mismatch')
            if pin['case_id'] is not None:
                case = next((c for c in version['content']['cases'] if c['case_id'] == pin['case_id']), None)
                _require(case is not None and case['binding_id'] in matching,
                         'Approach pin case mismatch')
            self.pins.append((version, pin['closure_digest']))

    def run(self, run):
        node = ('run_contexts', run['run_id'])
        config = self.edge(node, 'configurations', run['configuration_revision_id'])
        model = self.edge(node, 'models', run['model_revision_id'])
        _require(run['request']['run_id'] == run['run_id'] and run['request']['scope'] == self.sid,
                 'Run request identity mismatch')
        _require(config['digest'] == run['configuration_digest'] and
                 model['digest'] == run['model_digest'] and
                 config['model_revision_id'] == run['model_revision_id'] and
                 run['context'] == config['context_snapshot'], 'Run context mismatch')
        if run['results'] is not None:
            _require(run['results']['run_id'] == run['run_id'] and
                     run['results']['bundle_digest'] == run['request']['bundle_digest'],
                     'Run results identity mismatch')
            seen = set()
            for output in run['results']['outputs']:
                key = (output['target']['instance_id'], output['target']['port_id'])
                _require(key not in seen, 'Duplicate retained output')
                seen.add(key)
                self.port(model, output['target'])
                if output['availability'] == 'available':
                    _require(type(output['value']) in (int, float) and math.isfinite(output['value'])
                             and output['producer_completed'] and output['assigned'], 'Invalid available output')
                else:
                    _require(output['value'] is None, 'Unavailable output cannot be a valid value')

    def reached(self, root):
        active, cache = set(), {}
        def visit(node):
            _require(node not in active, 'Scientific reference cycle')
            if node in cache:
                return cache[node]
            active.add(node)
            seen, height = {node}, 0
            for child in self.edges[node]:
                descendants, child_height = visit(child)
                seen.update(descendants)
                height = max(height, child_height + 1)
            active.remove(node)
            _require(height <= MAX_DEPTH, 'Closure depth limit')
            cache[node] = (seen, height)
            return cache[node]
        return visit(('approach_versions', root['approach_version_id']))[0]

    def check(self):
        reached = self.reached(self.root)
        _require(reached == set(self.edges), 'Unreferenced closure records')
        for version, expected in self.pins:
            sub = _envelope(version, self.tables, self.reached(version))
            _require(sub['digest'] == expected, 'Ancestor closure digest mismatch')
        return _envelope(self.root, self.tables, reached)


def validate_closure(value, *, study_id=None):
    """Validate strict canonical wire records; return an independent data copy."""
    try:
        _signed(value)
        normalized = _Closure(value, study_id).check()
        _require(canonical(value) == canonical(normalized), 'Noncanonical closure inventory')
        return deepcopy(normalized)
    except (KeyError, TypeError, RecursionError, UnicodeError) as exc:
        raise ValueError('Invalid approach closure') from exc


def build_closure(version, resolution, *, study_id=None):
    """Build from authorized immutable records; coalesce only identical IDs."""
    _closed('ApproachVersionRead2', version)
    _closed('ApproachResolution3', resolution)
    if closure_schema(version, resolution) == '1':
        _closed('ApproachResolution1', resolution)
    tables = {}
    for table, key in KEYS.items():
        rows = list(resolution[table])
        if table == 'approach_versions':
            rows.append(version)
        unique = {}
        for row in rows:
            if row[key] in unique:
                _require(canonical(unique[row[key]]) == canonical(row), 'Conflicting retained identity')
            unique[row[key]] = row
        tables[table] = unique
    value = _envelope(version, tables, {(k, key) for k, rows in tables.items() for key in rows})
    return validate_closure(value, study_id=study_id)


def validate_saved(value, *, study_id=None):
    """Authenticate the noncircular version + closure saved envelope."""
    _closed('ApproachSavedRead3', value)
    closure = validate_closure(value['closure'], study_id=study_id)
    root = next(v for v in closure['approach_versions'] if
                v['approach_version_id'] == closure['root_approach_version_id'])
    _require(value['version'] == root, 'Saved approach root mismatch')
    return dict(version=deepcopy(root), closure=closure)
