"""Application-owned scientific answers, independent of numerical execution.

One head per exact approach/case target; every save appends an immutable version.
All references are checked inside the same owner transaction as the answer and
receipt. Nothing infers scientific conclusions or reads a current reference head.
"""

from datetime import datetime, timezone
import json

from jsonschema import Draft202012Validator, FormatChecker

from .approach import saved_version
from .history import History
from .contracts import DomainError, canonical, digest, issue, uid


def _object(properties):
    return dict(
        type='object', properties=properties, required=list(properties), additionalProperties=False
    )


_ID = dict(
    type='string',
    format='uuid',
    pattern='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
)
_NULL_ID = dict(anyOf=[_ID, dict(type='null')])
_TEXT = dict(type='string', minLength=1, maxLength=16384, pattern=r'\S')
_TEXTS = dict(type='array', items=_TEXT, maxItems=64, uniqueItems=True)
_IDS = dict(type='array', items=_ID, maxItems=100, uniqueItems=True)
_FIELDS = dict(
    schema_version=dict(const='1'),
    approach_version_id=_ID,
    case_id=_NULL_ID,
    observations=_TEXT,
    interpretation=_TEXT,
    qualifications=_TEXTS,
    open_deliverables=_TEXTS,
    basis=_object(
        {
            key: _IDS
            for key in (
                'configuration_revision_ids',
                'run_ids',
                'evidence_version_ids',
                'case_answer_version_ids',
            )
        }
    ),
)
DEFINITIONS = {
    'ScientificAnswerSave1': _object(dict(**_FIELDS, command_id=_ID, expected_revision=_NULL_ID)),
    'ScientificAnswer1': _object(
        dict(
            **_FIELDS,
            study_id=_ID,
            answer_id=_ID,
            answer_version_id=_ID,
            previous_version_id=_NULL_ID,
            version_number=dict(type='integer', minimum=1, maximum=9007199254740991),
            created_by=_ID,
            created_at=dict(type='string', format='date-time'),
            digest=dict(type='string', pattern='^[0-9a-f]{64}$'),
        )
    ),
    'ScientificAnswerHeads1': _object(
        dict(
            approach_version_id=_ID,
            items=dict(type='array', maxItems=1001, items={'$ref': '#/$defs/ScientificAnswer1'}),
        )
    ),
}
_VALIDATORS = {
    name: Draft202012Validator({'$defs': DEFINITIONS, **schema}, format_checker=FormatChecker())
    for name, schema in DEFINITIONS.items()
}

DDL = """
CREATE TABLE IF NOT EXISTS scientific_answer_versions(
 answer_version_id TEXT PRIMARY KEY, answer_id TEXT NOT NULL,
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 approach_version_id TEXT NOT NULL REFERENCES approach_versions(approach_version_id),
 case_key TEXT NOT NULL, version_number INTEGER NOT NULL,
 payload TEXT NOT NULL, UNIQUE(answer_id,version_number)
);
CREATE TABLE IF NOT EXISTS scientific_answer_heads(
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 approach_version_id TEXT NOT NULL REFERENCES approach_versions(approach_version_id),
 case_key TEXT NOT NULL, answer_id TEXT NOT NULL UNIQUE,
 answer_version_id TEXT NOT NULL REFERENCES scientific_answer_versions(answer_version_id),
 PRIMARY KEY(study_id,approach_version_id,case_key)
);
CREATE TRIGGER IF NOT EXISTS scientific_answer_versions_no_update
 BEFORE UPDATE ON scientific_answer_versions
 BEGIN SELECT RAISE(ABORT,'saved scientific answers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS scientific_answer_versions_no_delete
 BEFORE DELETE ON scientific_answer_versions
 BEGIN SELECT RAISE(ABORT,'saved scientific answers are never deleted'); END;
"""


def ensure(store):
    """Register owner tables through the application's single writer."""
    with store.connection() as db:
        db.executescript(DDL)


def validate_answer(name, value, *, retained=False):
    errors = list(_VALIDATORS[name].iter_errors(value))
    if errors:
        if retained:
            raise DomainError('corrupt_retained_record', 409)
        raise DomainError(
            'invalid_request',
            400,
            fields=[
                issue(list(error.absolute_path), 'Invalid scientific answer field.')
                for error in errors[:20]
            ],
        )
    return value


def _read(row, sid):
    if row is None:
        raise DomainError('resource_not_found', 404)
    try:
        value = json.loads(row['payload'])
        validate_answer('ScientificAnswer1', value, retained=True)
        if (
            any(
                value[key] != row[key]
                for key in (
                    'answer_id',
                    'answer_version_id',
                    'study_id',
                    'approach_version_id',
                    'version_number',
                )
            )
            or value['study_id'] != sid
            or (value['case_id'] or '') != row['case_key']
            or value['digest'] != digest({k: v for k, v in value.items() if k != 'digest'})
        ):
            raise ValueError('Answer identity mismatch')
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


class Answers:
    def __init__(self, store):
        self.store = store

    def _approach(self, db, sid, version):
        row = db.execute(
            'SELECT * FROM approach_versions WHERE study_id=? AND approach_version_id=?',
            (sid, version),
        ).fetchone()
        if row is None:
            raise DomainError('resource_not_found', 404)
        return saved_version(row, sid)['version']

    def read(self, actor, sid, version):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return _read(
                db.execute(
                    'SELECT * FROM scientific_answer_versions '
                    'WHERE study_id=? AND answer_version_id=?',
                    (sid, version),
                ).fetchone(),
                sid,
            )

    def heads(self, actor, sid, approach_version):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            self._approach(db, sid, approach_version)
            rows = db.execute(
                'SELECT v.* FROM scientific_answer_heads h JOIN scientific_answer_versions v '
                'ON v.answer_version_id=h.answer_version_id '
                'WHERE h.study_id=? AND h.approach_version_id=? ORDER BY h.case_key',
                (sid, approach_version),
            ).fetchall()
            return dict(
                approach_version_id=approach_version, items=[_read(row, sid) for row in rows]
            )

    def save(self, actor, sid, body):
        # Authorization precedes detailed diagnostics, including on a replay.
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
            if self.store.agent_actor(db, actor) is not None:
                raise DomainError('forbidden', 403)
        validate_answer('ScientificAnswerSave1', body)

        def operation(db):
            version = self._approach(db, sid, body['approach_version_id'])
            case = body['case_id']
            if case is not None and case not in {c['case_id'] for c in version['content']['cases']}:
                raise DomainError(
                    'reference_conflict',
                    fields=[
                        issue(['case_id'], 'Case must exist in the exact saved modeling approach.')
                    ],
                )
            key = (sid, body['approach_version_id'], case or '')
            head = db.execute(
                'SELECT * FROM scientific_answer_heads '
                'WHERE study_id=? AND approach_version_id=? AND case_key=?',
                key,
            ).fetchone()
            previous = head['answer_version_id'] if head else None
            self.store.cas(previous, body['expected_revision'])
            prior = (
                _read(
                    db.execute(
                        'SELECT * FROM scientific_answer_versions WHERE answer_version_id=?',
                        (previous,),
                    ).fetchone(),
                    sid,
                )
                if head
                else None
            )
            basis = body['basis']
            for field, table, column in (
                ('configuration_revision_ids', 'configurations', 'configuration_revision_id'),
                ('evidence_version_ids', 'evidence', 'evidence_version_id'),
            ):
                for identity in basis[field]:
                    # Only fixed owner table/column names above enter SQL.
                    exists = db.execute(
                        f'SELECT 1 FROM {table} WHERE study_id=? AND {column}=?', (sid, identity)
                    ).fetchone()
                    if exists is None:
                        raise DomainError(
                            'reference_conflict',
                            fields=[
                                issue(['basis', field], 'Every reference must exist in this study.')
                            ],
                        )
            for identity in basis['run_ids']:
                try:
                    row, receipt = History(self.store).run_row(
                        db, actor, sid, identity, payload=False
                    )
                except DomainError as error:
                    if error.code == 'resource_not_found':
                        raise DomainError(
                            'reference_conflict',
                            fields=[
                                issue(
                                    ['basis', 'run_ids'],
                                    'Every reference must exist in this study.',
                                )
                            ],
                        ) from None
                    raise
                if receipt is None:
                    raise DomainError('corrupt_retained_record', 409)
            if case is not None and basis['case_answer_version_ids']:
                raise DomainError(
                    'invalid_request',
                    400,
                    fields=[
                        issue(
                            ['basis', 'case_answer_version_ids'],
                            'Only a study synthesis cites case-answer versions.',
                        )
                    ],
                )
            for identity in basis['case_answer_version_ids']:
                row = db.execute(
                    'SELECT * FROM scientific_answer_versions '
                    'WHERE study_id=? AND answer_version_id=?',
                    (sid, identity),
                ).fetchone()
                if row is None:
                    raise DomainError('reference_conflict')
                answer = _read(row, sid)
                if (
                    answer['approach_version_id'] != body['approach_version_id']
                    or answer['case_id'] is None
                ):
                    raise DomainError(
                        'reference_conflict',
                        fields=[
                            issue(
                                ['basis', 'case_answer_version_ids'],
                                'Cite case answers from this exact modeling approach version.',
                            )
                        ],
                    )
            result = {
                key: value
                for key, value in body.items()
                if key not in ('command_id', 'expected_revision')
            }
            result.update(
                study_id=sid,
                answer_id=head['answer_id'] if head else uid(),
                answer_version_id=uid(),
                previous_version_id=previous,
                version_number=prior['version_number'] + 1 if prior else 1,
                created_by=actor,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            result['digest'] = digest(result)
            validate_answer('ScientificAnswer1', result, retained=True)
            db.execute(
                'INSERT INTO scientific_answer_versions VALUES(?,?,?,?,?,?,?)',
                (
                    result['answer_version_id'],
                    result['answer_id'],
                    sid,
                    result['approach_version_id'],
                    case or '',
                    result['version_number'],
                    canonical(result).decode(),
                ),
            )
            db.execute(
                'INSERT INTO scientific_answer_heads VALUES(?,?,?,?,?) '
                'ON CONFLICT(study_id,approach_version_id,case_key) '
                'DO UPDATE SET answer_version_id=excluded.answer_version_id',
                (*key, result['answer_id'], result['answer_version_id']),
            )
            return result

        return self.store.command(actor, sid, 'answer_save', body['command_id'], body, operation)
