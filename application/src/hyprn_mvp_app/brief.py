"""The study brief: how a study frames its engineering decision (ADR-0007, ADR-0010).

One draft per study and immutable, numbered versions. Saving a version freezes the
current draft exactly; a study answer pins the brief version it answers. Evidence
references are checked inside the owner transaction; nothing reads a current head in
place of a pinned version.
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
_NAME = dict(type='string', minLength=1, maxLength=256, pattern=r'\S')
_TEXT = dict(type='string', minLength=0, maxLength=4096)
_STATEMENT = dict(type='string', minLength=1, maxLength=4096, pattern=r'\S')
_LINKS = dict(type='array', items={'$ref': '#/$defs/ApproachEvidenceLink1'}, maxItems=64)
_CLAIM = dict(anyOf=[{'$ref': '#/$defs/ApproachQuestionClaim1'}, dict(type='null')])
_UNITS = dict(type='string', maxLength=64)
_TIME = dict(type='string', format='date-time')

DEFINITIONS = {
    'StudyAlternative1': _object(
        dict(alternative_id=_ID, name=_NAME, description=_TEXT, reason=_TEXT)
    ),
    # A constraint sets a threshold that must hold; an objective sets a direction. Each
    # calculation binds the criterion to the output that measures it (ADR-0010).
    'StudyCriterion1': dict(
        oneOf=[
            _object(
                dict(
                    criterion_id=_ID,
                    kind=dict(const='constraint'),
                    name=_NAME,
                    statement=_TEXT,
                    operator=dict(enum=['lt', 'le', 'eq', 'ge', 'gt']),
                    threshold=dict(type='number'),
                    units=_UNITS,
                    absolute_tolerance=dict(type='number', minimum=0),
                    relative_tolerance=dict(type='number', minimum=0),
                    evidence_links=_LINKS,
                ),
                optional=('absolute_tolerance', 'relative_tolerance'),
            ),
            _object(
                dict(
                    criterion_id=_ID,
                    kind=dict(const='objective'),
                    name=_NAME,
                    statement=_TEXT,
                    direction=dict(enum=['minimize', 'maximize']),
                    units=_UNITS,
                    evidence_links=_LINKS,
                )
            ),
        ]
    ),
    'StudyAssumption1': _object(
        dict(assumption_id=_ID, statement=_STATEMENT, evidence_links=_LINKS)
    ),
    'StudyOpenQuestion1': _object(dict(question_id=_ID, text=_STATEMENT)),
    'StudyBriefContent1': _object(
        dict(
            schema_version=dict(const='1'),
            question=_TEXT,
            original_question=_CLAIM,
            elaboration=_CLAIM,
            scope=_TEXT,
            alternatives=dict(
                type='array', items={'$ref': '#/$defs/StudyAlternative1'}, maxItems=32
            ),
            criteria=dict(
                type='array',
                items={'$ref': '#/$defs/StudyCriterion1'},
                maxItems=64,
                description=(
                    'Order is priority. Alternatives that meet every constraint are ranked by '
                    'the objectives in this order, the first objective deciding first; no '
                    'weight or score is implied.'
                ),
            ),
            assumptions=dict(
                type='array', items={'$ref': '#/$defs/StudyAssumption1'}, maxItems=256
            ),
            limits=dict(type='array', items={'$ref': '#/$defs/ApproachLimit1'}, maxItems=256),
            open_questions=dict(
                type='array', items={'$ref': '#/$defs/StudyOpenQuestion1'}, maxItems=64
            ),
        )
    ),
    'StudyBriefDraft1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            revision=_ID,
            based_on_version_id=_NULL_ID,
            content={'$ref': '#/$defs/StudyBriefContent1'},
            updated_by=_ID,
            updated_at=_TIME,
        )
    ),
    'StudyBriefVersion1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            brief_version_id=_ID,
            version_number=dict(type='integer', minimum=1, maximum=9007199254740991),
            predecessor_version_id=_NULL_ID,
            content={'$ref': '#/$defs/StudyBriefContent1'},
            created_by=_ID,
            created_at=_TIME,
            digest=dict(type='string', pattern='^[0-9a-f]{64}$'),
        )
    ),
    'StudyBriefState1': _object(
        dict(
            draft=dict(anyOf=[{'$ref': '#/$defs/StudyBriefDraft1'}, dict(type='null')]),
            latest_version=dict(anyOf=[{'$ref': '#/$defs/StudyBriefVersion1'}, dict(type='null')]),
        )
    ),
    'StudyBriefDraftSave1': _object(
        dict(
            command_id=_ID,
            expected_revision=_NULL_ID,
            content={'$ref': '#/$defs/StudyBriefContent1'},
        )
    ),
    'StudyBriefVersionSave1': _object(dict(command_id=_ID, expected_revision=_ID)),
    'StudyBriefVersionSaved1': _object(
        dict(
            version={'$ref': '#/$defs/StudyBriefVersion1'},
            draft={'$ref': '#/$defs/StudyBriefDraft1'},
        )
    ),
    'StudyBriefVersionPage1': _object(
        dict(
            items=dict(type='array', items={'$ref': '#/$defs/StudyBriefVersion1'}, maxItems=100),
            next_cursor=dict(anyOf=[dict(type='integer', minimum=1), dict(type='null')]),
        )
    ),
}

DEFINITIONS['StudyDeliverable1'] = _object(dict(
    deliverable_id=_ID,
    kind=dict(enum=['assessment', 'interactive_exploration']),
    statement=_STATEMENT,
))
DEFINITIONS['StudyBriefContent2'] = deepcopy(DEFINITIONS['StudyBriefContent1'])
DEFINITIONS['StudyBriefContent2']['properties'].update(
    schema_version=dict(const='2'),
    deliverables=dict(type='array', maxItems=32, items={'$ref': '#/$defs/StudyDeliverable1'}),
)
DEFINITIONS['StudyBriefContent2']['required'].append('deliverables')
for _kind in ('Draft', 'Version', 'State', 'DraftSave', 'VersionSaved', 'VersionPage'):
    _raw = json.dumps(DEFINITIONS[f'StudyBrief{_kind}1'])
    for _ref in ('Content', 'Draft', 'Version'):
        _raw = _raw.replace(f'StudyBrief{_ref}1', f'StudyBrief{_ref}2')
    _schema = json.loads(_raw)
    if 'schema_version' in _schema['properties']:
        _schema['properties']['schema_version'] = dict(const='2')
    DEFINITIONS[f'StudyBrief{_kind}2'] = _schema
for _kind in ('Content', 'Draft', 'Version', 'DraftSave'):
    DEFINITIONS[f'StudyBrief{_kind}Read2'] = dict(anyOf=[
        {'$ref': f'#/$defs/StudyBrief{_kind}1'},
        {'$ref': f'#/$defs/StudyBrief{_kind}2'},
    ])
for _kind in ('State', 'VersionSaved', 'VersionPage'):
    _raw = json.dumps(DEFINITIONS[f'StudyBrief{_kind}2'])
    for _ref in ('Draft', 'Version'):
        _raw = _raw.replace(f'StudyBrief{_ref}2', f'StudyBrief{_ref}Read2')
    DEFINITIONS[f'StudyBrief{_kind}Read2'] = json.loads(_raw)


def current_content(content):
    """Upgrade an editing copy only; historical requirements are never invented."""
    value = deepcopy(content)
    value.update(schema_version='2', deliverables=value.get('deliverables', []))
    return value


_VALIDATORS = {}


def _validator(name):
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(
            {'$defs': definitions() | DEFINITIONS, **DEFINITIONS[name]},
            format_checker=FormatChecker(),
        )
    return _VALIDATORS[name]


def validate_brief(name, value, *, retained=False):
    # Select only a declared supported format, preserving useful field diagnostics
    # inside successor request unions. Unknown formats still fail the closed union.
    if name == 'StudyBriefDraftSaveRead2' and isinstance(value, dict):
        content = value.get('content')
        version = content.get('schema_version') if isinstance(content, dict) else None
        if version in ('1', '2'):
            name = 'StudyBriefDraftSave' + version
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
CREATE TABLE IF NOT EXISTS study_brief_drafts(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 revision TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_brief_versions(
 brief_version_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(study_id,version_number)
);
CREATE TRIGGER IF NOT EXISTS study_brief_versions_no_update
 BEFORE UPDATE ON study_brief_versions
 BEGIN SELECT RAISE(ABORT,'saved study brief versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS study_brief_versions_no_delete
 BEFORE DELETE ON study_brief_versions
 BEGIN SELECT RAISE(ABORT,'saved study brief versions are never deleted'); END;
"""


def ensure(store):
    """Register owner tables through the application's single writer."""
    if store.verify_schema():
        return
    with store.connection() as db:
        db.executescript(DDL)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _identity_problems(content):
    """Item identities are unique within each list; names of alternatives and criteria too."""
    problems = []
    deliverables = [item['deliverable_id'] for item in content.get('deliverables', [])]
    if len(deliverables) != len(set(deliverables)):
        problems.append(issue(['deliverables'], 'Each deliverable needs its own identity.'))
    for field, key in (
        ('alternatives', 'alternative_id'),
        ('criteria', 'criterion_id'),
        ('assumptions', 'assumption_id'),
        ('limits', 'limit_id'),
        ('open_questions', 'question_id'),
    ):
        ids = [item[key] for item in content[field]]
        if len(ids) != len(set(ids)):
            problems.append(issue([field], 'Each item needs its own identity.'))
    for field in ('alternatives', 'criteria'):
        names = [item['name'].strip().casefold() for item in content[field]]
        if len(names) != len(set(names)):
            problems.append(issue([field], 'Each name must be distinct.'))
    return problems


def _evidence_ids(content):
    for field in ('criteria', 'assumptions', 'limits'):
        for item in content[field]:
            for link in item['evidence_links']:
                yield field, link['evidence_version_id']


def read_stored(row, sid, name, key):
    """A stored brief draft or version, checked against its row identity and digest."""
    if row is None:
        raise DomainError('resource_not_found', 404)
    try:
        value = json.loads(row['payload'])
        validate_brief(name[:-1] + value['schema_version'], value, retained=True)
        if value['study_id'] != sid or value[key] != row[key]:
            raise ValueError('Study brief identity mismatch')
        if name == 'StudyBriefVersion1' and (
            value['version_number'] != row['version_number']
            or value['digest'] != digest({k: v for k, v in value.items() if k != 'digest'})
        ):
            raise ValueError('Study brief version digest mismatch')
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


class Briefs:
    def __init__(self, store):
        self.store = store

    def _draft(self, db, sid):
        row = db.execute('SELECT * FROM study_brief_drafts WHERE study_id=?', (sid,)).fetchone()
        return read_stored(row, sid, 'StudyBriefDraft1', 'revision') if row else None

    def _latest(self, db, sid):
        row = db.execute(
            'SELECT * FROM study_brief_versions WHERE study_id=? '
            'ORDER BY version_number DESC LIMIT 1',
            (sid,),
        ).fetchone()
        return read_stored(row, sid, 'StudyBriefVersion1', 'brief_version_id') if row else None

    def state(self, actor, sid):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return dict(draft=self._draft(db, sid), latest_version=self._latest(db, sid))

    def read(self, actor, sid, version):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return read_stored(
                db.execute(
                    'SELECT * FROM study_brief_versions WHERE study_id=? AND brief_version_id=?',
                    (sid, version),
                ).fetchone(),
                sid,
                'StudyBriefVersion1',
                'brief_version_id',
            )

    def versions(self, actor, sid, *, limit=20, before=None):
        if not 1 <= limit <= 100:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            params = [sid]
            sql = 'SELECT * FROM study_brief_versions WHERE study_id=?'
            if before is not None:
                sql += ' AND version_number<?'
                params.append(before)
            rows = db.execute(
                sql + ' ORDER BY version_number DESC LIMIT ?', (*params, limit + 1)
            ).fetchall()
            items = [
                read_stored(row, sid, 'StudyBriefVersion1', 'brief_version_id')
                for row in rows[:limit]
            ]
            return dict(
                items=items,
                next_cursor=items[-1]['version_number'] if len(rows) > limit else None,
            )

    def _check_references(self, db, sid, content):
        problems = _identity_problems(content)
        for field, identity in _evidence_ids(content):
            if (
                db.execute(
                    'SELECT 1 FROM evidence WHERE study_id=? AND evidence_version_id=?',
                    (sid, identity),
                ).fetchone()
                is None
            ):
                problems.append(
                    issue([field], 'Every evidence reference must exist in this study.')
                )
                break
        if problems:
            raise DomainError('invalid_request', 422, fields=problems[:20])

    def save_draft(self, actor, sid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
        validate_brief('StudyBriefDraftSaveRead2', body)

        def operation(db):
            previous = self._draft(db, sid)
            self.store.cas(previous['revision'] if previous else None, body['expected_revision'])
            self._check_references(db, sid, body['content'])
            draft = dict(
                schema_version=body['content']['schema_version'],
                study_id=sid,
                revision=uid(),
                based_on_version_id=previous['based_on_version_id'] if previous else None,
                content=body['content'],
                updated_by=actor,
                updated_at=_now(),
            )
            validate_brief('StudyBriefDraftRead2', draft, retained=True)
            db.execute(
                'INSERT INTO study_brief_drafts VALUES(?,?,?) ON CONFLICT(study_id) '
                'DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
                (sid, draft['revision'], canonical(draft).decode()),
            )
            return draft

        return self.store.command(
            actor,
            sid,
            'brief_draft',
            body['command_id'],
            body,
            operation,
            attribute=lambda draft: [('brief_draft', sid, draft['revision'])],
        )

    def save_version(self, actor, sid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
        validate_brief('StudyBriefVersionSave1', body)

        def operation(db):
            draft = self._draft(db, sid)
            self.store.cas(draft['revision'] if draft else None, body['expected_revision'])
            self._check_references(db, sid, draft['content'])
            latest = self._latest(db, sid)
            version = dict(
                schema_version=draft['schema_version'],
                study_id=sid,
                brief_version_id=uid(),
                version_number=latest['version_number'] + 1 if latest else 1,
                predecessor_version_id=latest['brief_version_id'] if latest else None,
                content=deepcopy(draft['content']),
                created_by=actor,
                created_at=_now(),
            )
            version['digest'] = digest(version)
            validate_brief('StudyBriefVersionRead2', version, retained=True)
            db.execute(
                'INSERT INTO study_brief_versions VALUES(?,?,?,?)',
                (
                    version['brief_version_id'],
                    sid,
                    version['version_number'],
                    canonical(version).decode(),
                ),
            )
            # The draft continues from the saved version with a new revision.
            nextdraft = dict(
                draft,
                revision=uid(),
                based_on_version_id=version['brief_version_id'],
                updated_by=actor,
                updated_at=version['created_at'],
            )
            db.execute(
                'UPDATE study_brief_drafts SET revision=?,payload=? WHERE study_id=?',
                (nextdraft['revision'], canonical(nextdraft).decode(), sid),
            )
            return dict(version=version, draft=nextdraft)

        return self.store.command(
            actor,
            sid,
            'brief_version',
            body['command_id'],
            body,
            operation,
            attribute=lambda saved: [('brief_version', sid, saved['version']['brief_version_id'])],
        )
