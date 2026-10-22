"""Model explanations: what one model version represents and why (ADR-0007, decision D2).

The application owns the explanation; the modeling service never stores it. Each model has one
editable draft and each saved model version has at most one explanation version, which pins
that exact model version (its id and digest) and never changes. Pinning a model version
therefore pins its explanation, and reading it needs only the application store: a restarted or
replaced modeling service cannot change it. Saving a version reads the model version once to
check the component references; cited evidence must belong to the study.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import diagnostics
from .contracts import DomainError, canonical, definitions, digest, issue, uid


def _object(properties, optional=()):
    return dict(
        type='object',
        properties=properties,
        required=[name for name in properties if name not in optional],
        additionalProperties=False,
    )


_ID = dict(
    type='string',
    format='uuid',
    pattern='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
)
_NULL_ID = dict(anyOf=[_ID, dict(type='null')])
_TEXT = dict(type='string', minLength=0, maxLength=16384)
_STATEMENT = dict(type='string', minLength=1, maxLength=4096, pattern=r'\S')
_TIME = dict(type='string', format='date-time')
_COUNT = dict(type='integer', minimum=1, maximum=9007199254740991)

DEFINITIONS = {
    # A component is explained either as one instance of the model version or as a definition
    # version, which covers every instance of it.
    'ModelExplanationComponent1': dict(
        oneOf=[
            _object(dict(kind=dict(const='instance'), instance_id=_ID, explanation=_STATEMENT)),
            _object(
                dict(
                    kind=dict(const='definition_version'),
                    definition_version_id=_ID,
                    explanation=_STATEMENT,
                )
            ),
        ]
    ),
    'ModelExplanationContent1': _object(
        dict(
            schema_version=dict(const='1'),
            represents=_TEXT,
            basis=_TEXT,
            calculation_logic=_TEXT,
            components=dict(
                type='array', items={'$ref': '#/$defs/ModelExplanationComponent1'}, maxItems=1000
            ),
            evidence_links=dict(
                type='array', items={'$ref': '#/$defs/ApproachEvidenceLink1'}, maxItems=64
            ),
        )
    ),
    'ModelExplanationDraft1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            model_id=_ID,
            revision=_ID,
            based_on_model_revision_id=_NULL_ID,
            content={'$ref': '#/$defs/ModelExplanationContent1'},
            updated_by=_ID,
            updated_at=_TIME,
        )
    ),
    'ModelExplanationVersion1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            model_id=_ID,
            explanation_version_id=_ID,
            version_number=_COUNT,
            model_revision_id=_ID,
            model_digest=dict(type='string', pattern='^[0-9a-f]{64}$'),
            content={'$ref': '#/$defs/ModelExplanationContent1'},
            created_by=_ID,
            created_at=_TIME,
            digest=dict(type='string', pattern='^[0-9a-f]{64}$'),
        )
    ),
    'ModelExplanationState1': _object(
        dict(
            draft=dict(anyOf=[{'$ref': '#/$defs/ModelExplanationDraft1'}, dict(type='null')]),
            latest_version=dict(
                anyOf=[{'$ref': '#/$defs/ModelExplanationVersion1'}, dict(type='null')]
            ),
        )
    ),
    # The explanation of one model version; null when none was saved for it.
    'ModelVersionExplanation1': _object(
        dict(
            model_id=_ID,
            model_revision_id=_ID,
            explanation=dict(
                anyOf=[{'$ref': '#/$defs/ModelExplanationVersion1'}, dict(type='null')]
            ),
        )
    ),
    'ModelExplanationDraftSave1': _object(
        dict(
            command_id=_ID,
            expected_revision=_NULL_ID,
            content={'$ref': '#/$defs/ModelExplanationContent1'},
        )
    ),
    'ModelExplanationVersionSave1': _object(
        dict(command_id=_ID, expected_revision=_ID, model_revision_id=_ID)
    ),
    'ModelExplanationVersionSaved1': _object(
        dict(
            version={'$ref': '#/$defs/ModelExplanationVersion1'},
            draft={'$ref': '#/$defs/ModelExplanationDraft1'},
        )
    ),
    'ModelExplanationVersionPage1': _object(
        dict(
            items=dict(
                type='array', items={'$ref': '#/$defs/ModelExplanationVersion1'}, maxItems=100
            ),
            next_cursor=dict(anyOf=[dict(type='integer', minimum=1), dict(type='null')]),
        )
    ),
}

# Successor content adds explicit local documentation without changing saved format 1.
# The model explanation remains the application-owned, exact-model-version container.
DEFINITIONS['ComponentDocumentation1'] = _object(dict(
    instance_id=_ID,
    description=dict(type='string', maxLength=4096),
    limits=dict(type='string', maxLength=4096),
))
DEFINITIONS['ModelExplanationContent2'] = deepcopy(DEFINITIONS['ModelExplanationContent1'])
DEFINITIONS['ModelExplanationContent2']['properties'].update(
    schema_version=dict(const='2'),
    limits=_TEXT,
    component_details=dict(type='array', maxItems=1000,
                           items={'$ref': '#/$defs/ComponentDocumentation1'}),
)
DEFINITIONS['ModelExplanationContent2']['required'] += ['limits', 'component_details']
for _name in ('ModelExplanationDraft', 'ModelExplanationVersion', 'ModelExplanationDraftSave'):
    _schema = deepcopy(DEFINITIONS[_name + '1'])
    _schema['properties']['content'] = {'$ref': '#/$defs/ModelExplanationContent2'}
    if 'schema_version' in _schema['properties']:
        _schema['properties']['schema_version'] = dict(const='2')
    DEFINITIONS[_name + '2'] = _schema
    DEFINITIONS[_name + 'Read2'] = dict(oneOf=[
        {'$ref': '#/$defs/' + _name + '1'}, {'$ref': '#/$defs/' + _name + '2'},
    ])

def _current_refs(value):
    if isinstance(value, list):
        return [_current_refs(item) for item in value]
    if isinstance(value, dict):
        return {key: (_current_refs(item) if key != '$ref' else {
            '#/$defs/ModelExplanationDraft1': '#/$defs/ModelExplanationDraftRead2',
            '#/$defs/ModelExplanationVersion1': '#/$defs/ModelExplanationVersionRead2',
        }.get(item, item)) for key, item in value.items()}
    return value

for _name in ('ModelExplanationState', 'ModelVersionExplanation',
              'ModelExplanationVersionPage', 'ModelExplanationVersionSaved'):
    DEFINITIONS[_name + 'Read2'] = _current_refs(DEFINITIONS[_name + '1'])

_VALIDATORS = {}


def _validator(name):
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(
            {'$defs': definitions() | DEFINITIONS, **DEFINITIONS[name]},
            format_checker=FormatChecker(),
        )
    return _VALIDATORS[name]


def validate_explanation(name, value, *, retained=False):
    errors = list(_validator(name).iter_errors(value))
    if errors:
        if retained:
            raise DomainError('corrupt_retained_record', 409)
        raise DomainError(
            'invalid_request',
            400,
            fields=diagnostics(errors),
        )
    return value


DDL = """
CREATE TABLE IF NOT EXISTS model_explanation_drafts(
 study_id TEXT NOT NULL REFERENCES studies(study_id), model_id TEXT NOT NULL,
 revision TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(study_id,model_id)
);
CREATE TABLE IF NOT EXISTS model_explanation_versions(
 explanation_version_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id), model_id TEXT NOT NULL,
 model_revision_id TEXT NOT NULL UNIQUE,
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(study_id,model_id,version_number)
);
CREATE TRIGGER IF NOT EXISTS model_explanation_versions_no_update
 BEFORE UPDATE ON model_explanation_versions
 BEGIN SELECT RAISE(ABORT,'saved model explanations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS model_explanation_versions_no_delete
 BEFORE DELETE ON model_explanation_versions
 BEGIN SELECT RAISE(ABORT,'saved model explanations are never deleted'); END;
"""


def ensure(store):
    """Register owner tables through the application's single writer."""
    if store.verify_schema():
        return
    with store.connection() as db:
        db.executescript(DDL)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _target(component):
    return (
        component['kind'],
        component['instance_id' if component['kind'] == 'instance' else 'definition_version_id'],
    )


def read_stored(row, sid, mid, name, key):
    """A stored explanation draft or version, checked against its row identity and digest."""
    if row is None:
        raise DomainError('resource_not_found', 404)
    try:
        value = json.loads(row['payload'])
        validate_explanation(name.removesuffix('1') + 'Read2', value, retained=True)
        if value['study_id'] != sid or value['model_id'] != mid or value[key] != row[key]:
            raise ValueError('Model explanation identity mismatch')
        if name == 'ModelExplanationVersion1' and (
            value['version_number'] != row['version_number']
            or value['model_revision_id'] != row['model_revision_id']
            or value['digest'] != digest({k: v for k, v in value.items() if k != 'digest'})
        ):
            raise ValueError('Model explanation digest mismatch')
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


class Explanations:
    """Reads need only the application store; saving a version also reads the model version
    through ``coordinator`` (the modeling coordinator), outside the owner transaction."""

    def __init__(self, store, coordinator):
        self.store = store
        self.coordinator = coordinator

    def _authorize(self, db, actor, sid, mid, *, write=False):
        self.store.model_association(db, actor, sid, mid, write=write)

    def _draft(self, db, sid, mid):
        row = db.execute(
            'SELECT * FROM model_explanation_drafts WHERE study_id=? AND model_id=?', (sid, mid)
        ).fetchone()
        return read_stored(row, sid, mid, 'ModelExplanationDraft1', 'revision') if row else None

    def _version_row(self, db, sid, mid, where, args):
        return db.execute(
            'SELECT * FROM model_explanation_versions WHERE study_id=? AND model_id=? AND ' + where,
            (sid, mid, *args),
        ).fetchone()

    def _latest(self, db, sid, mid):
        row = db.execute(
            'SELECT * FROM model_explanation_versions WHERE study_id=? AND model_id=? '
            'ORDER BY version_number DESC LIMIT 1',
            (sid, mid),
        ).fetchone()
        return (
            read_stored(row, sid, mid, 'ModelExplanationVersion1', 'explanation_version_id')
            if row
            else None
        )

    def state(self, actor, sid, mid):
        with self.store.connection() as db:
            self._authorize(db, actor, sid, mid)
            return dict(draft=self._draft(db, sid, mid), latest_version=self._latest(db, sid, mid))

    def of_model_version(self, actor, sid, mid, model_revision_id):
        """The explanation saved for one model version, or null; the model version itself is
        not read, so this answers while the modeling service is unavailable."""
        with self.store.connection() as db:
            self._authorize(db, actor, sid, mid)
            row = self._version_row(db, sid, mid, 'model_revision_id=?', (model_revision_id,))
            return dict(
                model_id=mid,
                model_revision_id=model_revision_id,
                explanation=read_stored(
                    row, sid, mid, 'ModelExplanationVersion1', 'explanation_version_id'
                )
                if row
                else None,
            )

    def versions(self, actor, sid, mid, *, limit=20, before=None):
        if not 1 <= limit <= 100:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self._authorize(db, actor, sid, mid)
            where, args = '1', []
            if before is not None:
                where, args = 'version_number<?', [before]
            rows = db.execute(
                'SELECT * FROM model_explanation_versions WHERE study_id=? AND model_id=? AND '
                + where
                + ' ORDER BY version_number DESC LIMIT ?',
                (sid, mid, *args, limit + 1),
            ).fetchall()
            items = [
                read_stored(row, sid, mid, 'ModelExplanationVersion1', 'explanation_version_id')
                for row in rows[:limit]
            ]
            return dict(
                items=items,
                next_cursor=items[-1]['version_number'] if len(rows) > limit else None,
            )

    def _check(self, db, sid, content, model=None):
        """Distinct component targets and evidence of this study; with ``model``, every
        component names an instance or definition version of that exact model version."""
        problems = []
        targets = [_target(c) for c in content['components']]
        if len(targets) != len(set(targets)):
            problems.append(issue(['components'], 'Each component is explained once.'))
        if model is not None:
            known = {('instance', i['instance_id']) for i in model['instances']}
            known |= {
                ('definition_version', i['definition_version_id']) for i in model['instances']
            }
            for index, target in enumerate(targets):
                if target not in known:
                    problems.append(
                        issue(
                            ['components', index],
                            'Each explained component must belong to the model version.',
                        )
                    )
                    break
        details = content.get('component_details', [])
        ids = [item['instance_id'] for item in details]
        if len(ids) != len(set(ids)):
            problems.append(issue(['component_details'], 'Each component has one documentation entry.'))
        if model is not None:
            instances = {item['instance_id'] for item in model['instances']}
            for index, item in enumerate(details):
                if item['instance_id'] not in instances:
                    problems.append(issue(['component_details', index, 'instance_id'],
                                          'The component must belong to this model version.'))
        for index, link in enumerate(content['evidence_links']):
            if (
                db.execute(
                    'SELECT 1 FROM evidence WHERE study_id=? AND evidence_version_id=?',
                    (sid, link['evidence_version_id']),
                ).fetchone()
                is None
            ):
                problems.append(
                    issue(
                        ['evidence_links', index],
                        'Every evidence reference must exist in this study.',
                    )
                )
                break
        if problems:
            raise DomainError('invalid_request', 422, fields=problems[:20])

    def save_draft(self, actor, sid, mid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self._authorize(db, actor, sid, mid, write=True)
        validate_explanation('ModelExplanationDraftSaveRead2', body)

        def operation(db):
            self._authorize(db, actor, sid, mid, write=True)
            previous = self._draft(db, sid, mid)
            self.store.cas(previous['revision'] if previous else None, body['expected_revision'])
            if previous and previous['schema_version'] == '2' and body['content']['schema_version'] != '2':
                raise DomainError('invalid_request', 422, fields=[issue(
                    ['content', 'schema_version'],
                    'Use format 2 to preserve the model and component documentation.',
                )])
            self._check(db, sid, body['content'])
            draft = dict(
                schema_version=body['content']['schema_version'],
                study_id=sid,
                model_id=mid,
                revision=uid(),
                based_on_model_revision_id=(
                    previous['based_on_model_revision_id'] if previous else None
                ),
                content=body['content'],
                updated_by=actor,
                updated_at=_now(),
            )
            validate_explanation('ModelExplanationDraftRead2', draft, retained=True)
            db.execute(
                'INSERT INTO model_explanation_drafts VALUES(?,?,?,?) '
                'ON CONFLICT(study_id,model_id) '
                'DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
                (sid, mid, draft['revision'], canonical(draft).decode()),
            )
            return draft

        return self.store.command(
            actor,
            sid,
            'model_explanation_draft',
            body['command_id'],
            dict(body, model_id=mid),
            operation,
            attribute=lambda draft: [('model_explanation_draft', mid, draft['revision'])],
        )

    def save_version(self, actor, sid, mid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self._authorize(db, actor, sid, mid, write=True)
        validate_explanation('ModelExplanationVersionSave1', body)
        revision = body['model_revision_id']
        # The exact model version, integrity-checked by the coordinator, read before the owner
        # transaction so no remote call holds the writer.
        model = self.coordinator.read(
            actor, sid, mid, '/revisions/' + revision, response_schema='ModelRevisionResponse4'
        )['data']

        def operation(db):
            self._authorize(db, actor, sid, mid, write=True)
            draft = self._draft(db, sid, mid)
            self.store.cas(draft['revision'] if draft else None, body['expected_revision'])
            if self._version_row(db, sid, mid, 'model_revision_id=?', (revision,)) is not None:
                raise DomainError(
                    'reference_conflict',
                    409,
                    fields=[
                        issue(
                            ['model_revision_id'],
                            'This model version already has its saved explanation, which '
                            'never changes; save a new model version to explain it anew.',
                        )
                    ],
                )
            self._check(db, sid, draft['content'], model)
            latest = self._latest(db, sid, mid)
            version = dict(
                schema_version=draft['schema_version'],
                study_id=sid,
                model_id=mid,
                explanation_version_id=uid(),
                version_number=latest['version_number'] + 1 if latest else 1,
                model_revision_id=revision,
                model_digest=model['digest'],
                content=deepcopy(draft['content']),
                created_by=actor,
                created_at=_now(),
            )
            version['digest'] = digest(version)
            validate_explanation('ModelExplanationVersionRead2', version, retained=True)
            db.execute(
                'INSERT INTO model_explanation_versions VALUES(?,?,?,?,?,?)',
                (
                    version['explanation_version_id'],
                    sid,
                    mid,
                    revision,
                    version['version_number'],
                    canonical(version).decode(),
                ),
            )
            # The draft continues from the explained model version with a new revision.
            nextdraft = dict(
                draft,
                revision=uid(),
                based_on_model_revision_id=revision,
                updated_by=actor,
                updated_at=version['created_at'],
            )
            db.execute(
                'UPDATE model_explanation_drafts SET revision=?,payload=? '
                'WHERE study_id=? AND model_id=?',
                (nextdraft['revision'], canonical(nextdraft).decode(), sid, mid),
            )
            return dict(version=version, draft=nextdraft)

        return self.store.command(
            actor,
            sid,
            'model_explanation_version',
            body['command_id'],
            dict(body, model_id=mid),
            operation,
            attribute=lambda saved: [
                (
                    'model_explanation_version',
                    mid,
                    saved['version']['explanation_version_id'],
                )
            ],
        )
