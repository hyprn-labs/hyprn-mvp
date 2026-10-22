"""An in-process private modeling double for the model and configuration write tools.

It answers the private routes the application calls with typed records built from the recorded
schema-4 model of ``fixtures/recorded_api.json``, and validates every request body against its
private schema exactly as the real modeling client does, so a tool's translation is checked by
the application's own contract. It never applies an edit: it records each edit batch and
returns the draft under a new revision. It never runs or imports candidate code.
"""

import copy
import json
from pathlib import Path

from hyprn_mvp_app.contracts import definitions
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.store import digest, uid

RECORDED = json.loads(
    (Path(__file__).resolve().parent / 'fixtures/recorded_api.json').read_text(encoding='utf-8')
)
D = definitions()
SUPPORTED = (
    ('resolved_configuration', '3'),
    ('unit_declarations', '1'),
    ('quantity_definitions', '1'),
    ('model_assumptions', '1'),
    ('flat_explicit_scalar', '1'),
    ('criteria_free_configuration', '1'),
)


def sample(schema):
    """The smallest instance of a private schema (first choices, required fields only)."""
    if '$ref' in schema:
        return sample(D[schema['$ref'].split('/')[-1]])
    if 'const' in schema:
        return schema['const']
    if 'enum' in schema:
        return schema['enum'][0]
    if 'oneOf' in schema or 'anyOf' in schema:
        options = schema.get('oneOf', schema.get('anyOf'))
        return sample(next((o for o in options if o.get('type') == 'null'), options[0]))
    kind = schema.get('type')
    if kind == 'object':
        return {k: sample(schema['properties'][k]) for k in schema['required']}
    if kind == 'array':
        return [sample(schema['items']) for _ in range(schema.get('minItems', 0))]
    if kind == 'null':
        return None
    if kind == 'boolean':
        return True
    if kind in ('integer', 'number'):
        return schema.get('minimum', 1)
    if schema.get('format') == 'uuid':
        return uid()
    if schema.get('pattern') == '^[0-9a-f]{64}$':
        return '0' * 64
    if schema.get('pattern') == '^[0-9a-f]{40}$':
        return 'a' * 40
    return 'x' * max(1, schema.get('minLength', 1))


def capabilities():
    caps = sample(D['Capabilities2'])
    caps['generator_identity']['provenance_path'] = 'provenance/fixture.json'
    item = sample(D['Capabilities2']['properties']['capabilities']['items'])
    caps.update(
        contract_versions=['1.2', '1.3'],
        schema_versions=['2', '3', '4'],
        capabilities=[dict(item, id=i, version=v, supported=True) for i, v in SUPPORTED],
    )
    validate('CapabilitiesRead2', caps)
    return caps


def revision_of(draft, parent=None):
    """The immutable revision a commit of ``draft`` produces."""
    value = {
        k: copy.deepcopy(v)
        for k, v in draft.items()
        if k not in ('study_id', 'name', 'draft_revision')
    }
    value.update(
        model_revision_id=uid(),
        parent_model_revision_id=parent,
        originating_draft_revision=draft['draft_revision'],
    )
    value['digest'] = digest(value)
    return value


class ModelingDouble:
    """One recorded model per study; ``batches`` holds every edit batch sent, ``created`` every
    model creation, ``diagnostics`` what validation reports."""

    def __init__(self, sid=None):
        self.sid = sid
        self.caps = capabilities()
        draft = copy.deepcopy(next(iter(RECORDED['model_drafts'].values())))
        draft['study_id'] = sid
        self.model_id = draft['model_id']
        self.drafts = {self.model_id: draft}
        self.revisions = {
            self.model_id: [
                copy.deepcopy(RECORDED['model_revision'][r['model_revision_id']])
                for r in RECORDED['model_revisions'][self.model_id]
            ]
        }
        # The recorded model cites evidence of the recorded study; a fresh study holds none.
        for value in [draft, *self.revisions[self.model_id]]:
            for assumption in value.get('assumptions', ()):
                assumption['evidence_links'] = []
            if 'digest' in value:
                value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
        self.batches, self.created, self.calls = [], [], []
        self.diagnostics = []

    def bind(self, store, sid):
        """Place the recorded model in study ``sid``, associated as its owner records it."""
        self.sid = sid
        for draft in self.drafts.values():
            draft['study_id'] = sid
        with store.connection(write=True) as db:
            db.execute('INSERT INTO model_associations VALUES(?,?,?)', (sid, self.model_id, uid()))

    def declare(self, revision_id, port_name, units):
        """Give a port of a saved version its unit declaration (the version is re-signed)."""
        value = self.revision(self.model_id, revision_id)
        for definition in value['definitions']:
            for port in definition['ports']:
                if port['name'] == port_name:
                    port['units'] = units
        value['ports'] = [copy.deepcopy(p) for d in value['definitions'] for p in d['ports']]
        value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})

    def revision(self, model_id, revision_id):
        return next(r for r in self.revisions[model_id] if r['model_revision_id'] == revision_id)

    def call(self, actor, study, method, path, body=None, *, request_schema=None, **_):
        if request_schema:
            validate(request_schema, body)
        self.calls.append((method, path.split('?')[0]))
        parts = path.split('?')[0].strip('/').split('/')
        if path == '/capabilities':
            return 200, {'data': copy.deepcopy(self.caps)}
        if parts[0] == 'commands':
            return 200, {'data': {'command_id': parts[1], 'state': 'absent'}}
        if parts == ['models'] and method == 'POST':
            draft = copy.deepcopy(self.drafts[self.model_id])
            draft.update(model_id=uid(), name=body['name'], draft_revision=uid(), study_id=self.sid)
            self.drafts[draft['model_id']] = draft
            self.revisions[draft['model_id']] = []
            self.created.append(body)
            return 201, {'data': copy.deepcopy(draft)}
        model_id = parts[1]
        draft = self.drafts[model_id]
        if len(parts) == 2:
            return 200, {'data': copy.deepcopy(draft)}
        if parts[2] == 'revisions' and len(parts) == 4:
            return 200, {'data': copy.deepcopy(self.revision(model_id, parts[3]))}
        if parts[2] == 'revisions':
            items = [
                {k: r[k] for k in ('model_revision_id', 'parent_model_revision_id')}
                for r in self.revisions[model_id]
            ]
            return 200, {'data': {'items': items, 'next_cursor': None}}
        action = parts[2]
        if action in ('preview', 'edits'):
            self.batches.append((action, copy.deepcopy(body)))
            result = dict(copy.deepcopy(draft), draft_revision=uid())
            if action == 'edits':
                self.drafts[model_id] = result
            return 200, {'data': copy.deepcopy(result), 'created_ids': {}, 'diagnostics': []}
        if action == 'validate':
            checked = body.get('draft_revision') or body.get('model_revision_id')
            return 200, {
                'data': {
                    'checked_revision': checked,
                    'validation_scope': 'static',
                    'diagnostics': copy.deepcopy(self.diagnostics),
                }
            }
        if action == 'commits':
            history = self.revisions[model_id]
            parent = history[-1]['model_revision_id'] if history else None
            value = revision_of(draft, parent)
            history.append(value)
            return 200, {'data': copy.deepcopy(value)}
        if action == 'configuration-compatibility':
            candidate = body['configuration_candidate']
            model = self.revision(model_id, body['model_revision_id'])
            return 200, {
                'data': dict(
                    schema_version='2',
                    model_revision_id=model['model_revision_id'],
                    model_digest=model['digest'],
                    candidate_digest=digest(candidate),
                    compatible=True,
                    diagnostics=[],
                    required_capabilities=candidate['required_capabilities'],
                    validator_identity='agent-tools-private-double',
                    input_interpretations=[],
                )
            }
        raise AssertionError((method, path))
