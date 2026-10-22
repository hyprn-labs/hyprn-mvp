"""The study answer: the study's single decision record (ADR-0008, ADR-0010).

One draft per study and immutable, numbered versions; the latest version is the study's only
answer head. Each saved version pins one saved brief version and holds the mapping of every
brief alternative to the calculation versions that back it, the alternatives x criteria table,
justifications, the interpretation, the outcome, the decisive uncertainties, the next analysis
and the answer exploration's basis.

Everything cited belongs to the same study. A table cell cites one run of one calculation
version and stores that run's criterion evaluation exactly as the calculations owner reports
it when the draft or version is saved; nothing in the table is aggregated or inferred. The
outcome is always stated explicitly; it is never derived from execution or criteria.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json

from jsonschema import Draft202012Validator, FormatChecker

from .brief import Briefs
from .calculation_estimates import Estimates
from .calculation_preparation import preparation
from .calculations import DEFINITIONS as CALCULATION_DEFINITIONS, Analyses
from .contracts import diagnostics
from .contracts import DomainError, canonical, definitions, digest, issue, uid
from .criterion_evaluation import unresolved
from .history import History, calculation_runs


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
_TEXT = dict(type='string', minLength=0, maxLength=4096)
_STATEMENT = dict(type='string', minLength=1, maxLength=4096, pattern=r'\S')
_TIME = dict(type='string', format='date-time')
_RELATION = dict(enum=['supports', 'challenges', 'context'])


def _justification(kind, **target):
    return _object(
        dict(
            justification_id=_ID,
            kind=dict(const=kind),
            **target,
            relation=_RELATION,
            reason=_STATEMENT,
        )
    )


DEFINITIONS = {
    'StudyAnswerAlternativeMapping1': _object(
        dict(
            alternative_id=_ID,
            calculation_version_ids=dict(
                type='array', items=_ID, maxItems=64, uniqueItems=True
            ),
        )
    ),
    'StudyAnswerCell1': _object(
        dict(
            alternative_id=_ID,
            criterion_id=_ID,
            calculation_version_id=_ID,
            run_id=_ID,
            note=_TEXT,
            evaluation=dict(
                anyOf=[{'$ref': '#/$defs/CriterionEvaluation1'}, dict(type='null')],
                description=(
                    "The cited run's evaluation of this criterion, filled by the application "
                    'from the calculation when the draft or version is saved; a value sent by a '
                    'client is replaced, never trusted.'
                ),
            ),
        )
    ),
    'StudyAnswerJustification1': dict(
        oneOf=[
            _justification('calculation_version', calculation_version_id=_ID),
            _justification('run', calculation_version_id=_ID, run_id=_ID),
            _justification('evidence_version', evidence_version_id=_ID),
        ]
    ),
    'StudyAnswerDeliverable1': _object(dict(deliverable_id=_ID, text=_STATEMENT)),
    'StudyAnswerInterpretation1': _object(
        dict(
            observations=_TEXT,
            interpretation=_TEXT,
            qualifications=_TEXT,
            open_deliverables=dict(
                type='array', items={'$ref': '#/$defs/StudyAnswerDeliverable1'}, maxItems=64
            ),
        )
    ),
    # Stated, never inferred: a recommended alternative, a no-go for the only alternative, or
    # no recommendation because the evidence is insufficient or contested.
    'StudyAnswerOutcome1': dict(
        oneOf=[
            _object(
                dict(kind=dict(const='recommended'), alternative_id=_ID, reason=_STATEMENT)
            ),
            _object(dict(kind=dict(const='no_go'), alternative_id=_ID, reason=_STATEMENT)),
            _object(
                dict(
                    kind=dict(const='no_recommendation'),
                    basis=dict(enum=['insufficient_evidence', 'contested_evidence']),
                    reason=_STATEMENT,
                )
            ),
        ]
    ),
    'StudyAnswerUncertainty1': _object(
        dict(uncertainty_id=_ID, statement=_STATEMENT, stated_range=_TEXT, effect=_TEXT)
    ),
    'StudyAnswerNextAnalysis1': _object(dict(statement=_TEXT, resolves=_TEXT)),
    'StudyAnswerExplorationBasis1': _object(
        dict(
            calculation_version_id=_ID,
            estimate_id=dict(
                **_NULL_ID,
                description='The estimate the figure explores; null until estimates are recorded.',
            ),
            shown_outputs=dict(
                type='array', items={'$ref': '#/$defs/PortRef'}, maxItems=16, uniqueItems=True
            ),
        )
    ),
    'StudyAnswerContent1': _object(
        dict(
            schema_version=dict(const='1'),
            brief_version_id=dict(
                **_NULL_ID,
                description='The saved brief version answered; required to save a version.',
            ),
            alternative_mappings=dict(
                type='array',
                items={'$ref': '#/$defs/StudyAnswerAlternativeMapping1'},
                maxItems=32,
            ),
            comparison=dict(
                type='array', items={'$ref': '#/$defs/StudyAnswerCell1'}, maxItems=1024
            ),
            justifications=dict(
                type='array', items={'$ref': '#/$defs/StudyAnswerJustification1'}, maxItems=256
            ),
            interpretation={'$ref': '#/$defs/StudyAnswerInterpretation1'},
            outcome=dict(
                anyOf=[{'$ref': '#/$defs/StudyAnswerOutcome1'}, dict(type='null')],
                description='Null only in a draft; a saved version states its outcome.',
            ),
            decisive_uncertainties=dict(
                type='array', items={'$ref': '#/$defs/StudyAnswerUncertainty1'}, maxItems=64
            ),
            next_analysis={'$ref': '#/$defs/StudyAnswerNextAnalysis1'},
            exploration_basis=dict(
                anyOf=[{'$ref': '#/$defs/StudyAnswerExplorationBasis1'}, dict(type='null')]
            ),
        )
    ),
    'StudyAnswerDraft1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            revision=_ID,
            based_on_version_id=_NULL_ID,
            content={'$ref': '#/$defs/StudyAnswerContent1'},
            updated_by=_ID,
            updated_at=_TIME,
        )
    ),
    'StudyAnswerVersion1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            answer_version_id=_ID,
            version_number=dict(type='integer', minimum=1, maximum=9007199254740991),
            predecessor_version_id=_NULL_ID,
            content={'$ref': '#/$defs/StudyAnswerContent1'},
            created_by=_ID,
            created_at=_TIME,
            digest=dict(type='string', pattern='^[0-9a-f]{64}$'),
        )
    ),
    'StudyAnswerState1': _object(
        dict(
            draft=dict(anyOf=[{'$ref': '#/$defs/StudyAnswerDraft1'}, dict(type='null')]),
            latest_version=dict(
                anyOf=[{'$ref': '#/$defs/StudyAnswerVersion1'}, dict(type='null')]
            ),
        )
    ),
    'StudyAnswerDraftSave1': _object(
        dict(
            command_id=_ID,
            expected_revision=_NULL_ID,
            content={'$ref': '#/$defs/StudyAnswerContent1'},
        )
    ),
    'StudyAnswerVersionSave1': _object(dict(command_id=_ID, expected_revision=_ID)),
    'StudyAnswerVersionSaved1': _object(
        dict(
            version={'$ref': '#/$defs/StudyAnswerVersion1'},
            draft={'$ref': '#/$defs/StudyAnswerDraft1'},
        )
    ),
    'StudyAnswerVersionPage1': _object(
        dict(
            items=dict(
                type='array', items={'$ref': '#/$defs/StudyAnswerVersion1'}, maxItems=100
            ),
            next_cursor=dict(anyOf=[dict(type='integer', minimum=1), dict(type='null')]),
        )
    ),
}

# The concise answer is a new format; historical content and its digest stay untouched.
DEFINITIONS['StudyAnswerInterpretation2'] = _object(dict(
    interpretation=dict(type='string', maxLength=12292),
))
DEFINITIONS['StudyAnswerCell2'] = deepcopy(DEFINITIONS['StudyAnswerCell1'])
DEFINITIONS['StudyAnswerCell2']['properties']['output_name'] = dict(
    anyOf=[dict(type='string', maxLength=4096), dict(type='null')],
    description='Output name from the cited run model; replaced on save, never trusted.',
)
DEFINITIONS['StudyAnswerCell2']['required'].append('output_name')
for _name in ('Content', 'Draft', 'Version', 'State', 'DraftSave', 'VersionSaved', 'VersionPage'):
    _old = f'StudyAnswer{_name}1'
    _new = f'StudyAnswer{_name}2'
    _definition = json.dumps(DEFINITIONS[_old])
    for _ref in ('Cell', 'Interpretation', 'Content', 'Draft', 'Version'):
        _definition = _definition.replace(f'StudyAnswer{_ref}1', f'StudyAnswer{_ref}2')
    DEFINITIONS[_new] = json.loads(_definition)
    if 'schema_version' in DEFINITIONS[_new]['properties']:
        DEFINITIONS[_new]['properties']['schema_version'] = dict(const='2')
for _name in ('Content', 'Draft', 'Version'):
    DEFINITIONS[f'StudyAnswer{_name}Read2'] = dict(anyOf=[
        {'$ref': f'#/$defs/StudyAnswer{_name}1'},
        {'$ref': f'#/$defs/StudyAnswer{_name}2'},
    ])
for _name in ('State', 'VersionSaved', 'VersionPage'):
    _definition = json.dumps(DEFINITIONS[f'StudyAnswer{_name}2'])
    for _ref in ('Draft', 'Version'):
        _definition = _definition.replace(f'StudyAnswer{_ref}2', f'StudyAnswer{_ref}Read2')
    DEFINITIONS[f'StudyAnswer{_name}Read2'] = json.loads(_definition)


def current_content(content):
    """An editing copy of old content, retaining limitations and unfinished analysis."""
    value = deepcopy(content)
    if value['schema_version'] == '1':
        old = value['interpretation']
        value['schema_version'] = '2'
        for cell in value['comparison']:
            cell['output_name'] = None
        value['interpretation'] = dict(interpretation='\n\n'.join(
            old[key] for key in ('observations', 'interpretation', 'qualifications') if old[key]
        ))
        pending = [item['text'] for item in old['open_deliverables']]
        value['next_analysis']['statement'] = '\n\n'.join(filter(None, [
            value['next_analysis']['statement'], *pending,
        ]))
    return value


_VALIDATORS = {}


def _validator(name):
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(
            {
                '$defs': definitions() | CALCULATION_DEFINITIONS | DEFINITIONS,
                **DEFINITIONS[name],
            },
            format_checker=FormatChecker(),
        )
    return _VALIDATORS[name]


def validate_answer(name, value, *, retained=False):
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
CREATE TABLE IF NOT EXISTS study_answer_drafts(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 revision TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_answer_versions(
 answer_version_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(study_id,version_number)
);
CREATE TRIGGER IF NOT EXISTS study_answer_versions_no_update
 BEFORE UPDATE ON study_answer_versions
 BEGIN SELECT RAISE(ABORT,'saved study answer versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS study_answer_versions_no_delete
 BEFORE DELETE ON study_answer_versions
 BEGIN SELECT RAISE(ABORT,'saved study answer versions are never deleted'); END;
"""


def ensure(store):
    """Register owner tables through the application's single writer."""
    if store.verify_schema():
        return
    with store.connection() as db:
        db.executescript(DDL)


def _now():
    return datetime.now(timezone.utc).isoformat()


def read_stored(row, sid, name, key):
    """A stored answer draft or version, checked against its row identity and digest."""
    if row is None:
        raise DomainError('resource_not_found', 404)
    try:
        value = json.loads(row['payload'])
        validate_answer(name[:-1] + value['schema_version'], value, retained=True)
        if value['study_id'] != sid or value[key] != row[key]:
            raise ValueError('Study answer identity mismatch')
        if name == 'StudyAnswerVersion1' and (
            value['version_number'] != row['version_number']
            or value['digest'] != digest({k: v for k, v in value.items() if k != 'digest'})
        ):
            raise ValueError('Study answer version digest mismatch')
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


def _identity_problems(content):
    problems = []
    for field, key in (
        ('alternative_mappings', 'alternative_id'),
        ('justifications', 'justification_id'),
        ('decisive_uncertainties', 'uncertainty_id'),
    ):
        ids = [item[key] for item in content[field]]
        if len(ids) != len(set(ids)):
            problems.append(issue([field], 'Each item needs its own identity.'))
    cells = [
        (c['alternative_id'], c['criterion_id'], c['calculation_version_id'], c['run_id'])
        for c in content['comparison']
    ]
    if len(cells) != len(set(cells)):
        problems.append(
            issue(['comparison'], 'Each run is cited once per alternative and criterion.')
        )
    return problems


class _Citations:
    """Reads of the cited records through their owners, scoped to one actor and study."""

    def __init__(self, store, actor, sid):
        self.store, self.actor, self.sid = store, actor, sid
        self.calculations = Analyses(store)
        self.briefs = Briefs(store)
        self._versions, self._briefs, self._positions = {}, {}, {}

    def brief(self, version_id):
        if version_id not in self._briefs:
            try:
                self._briefs[version_id] = self.briefs.read(self.actor, self.sid, version_id)
            except DomainError as error:
                if error.status != 404:
                    raise
                self._briefs[version_id] = None
        return self._briefs[version_id]

    def calculation(self, version_id):
        if version_id not in self._versions:
            try:
                self._versions[version_id] = self.calculations.version(
                    self.actor, self.sid, version_id
                )
            except DomainError as error:
                if error.status != 404:
                    raise
                self._versions[version_id] = None
        return self._versions[version_id]

    def run_position(self, version, run_id):
        """The run's insertion position among the calculation version's runs, or None when
        the run is not one of its member configurations' runs."""
        key = version['calculation_version_id']
        if key not in self._positions:
            members, after, positions = version['content']['configuration_revision_ids'], 0, {}
            with self.store.connection() as db:
                while True:
                    rows = calculation_runs(db, self.sid, members, after, 500)
                    positions.update((row['run_id'], row['position']) for row in rows)
                    if len(rows) < 500:
                        break
                    after = rows[-1]['position']
            self._positions[key] = positions
        return self._positions[key].get(run_id)

    def evaluation(self, version, run_id, criterion):
        """The calculations owner's evaluation of ``criterion`` for the cited run."""
        position = self.run_position(version, run_id)
        page = self.calculations.runs(
            self.actor, self.sid, version['calculation_version_id'], limit=1, after=position - 1
        )
        item = page['items'][0] if page['items'] else None
        if item is None or item['run_id'] != run_id:
            raise DomainError('corrupt_retained_record', 409)
        for evaluation in item['evaluations']:
            if evaluation['criterion_id'] == criterion['criterion_id']:
                return evaluation
        return unresolved([criterion], 'criterion_not_bound')[0]

    def output_name(self, version, run_id, criterion):
        binding = next((b for b in version['content']['criterion_bindings']
                        if b['criterion_id'] == criterion['criterion_id']), None)
        if binding is None:
            return None
        retained = History(self.store).read(self.actor, self.sid, run_id)
        model = retained.get('model_snapshot')
        if model is None:
            return None
        target = binding['output']
        instance = next((i for i in model['instances']
                         if i['instance_id'] == target['instance_id']), None)
        if instance is None:
            return None
        definition = next(d for d in model['definitions']
                          if d['definition_version_id'] == instance['definition_version_id'])
        return next((p['name'] for p in definition['ports']
                     if p['port_id'] == target['port_id']), None)

    def estimate(self, estimate_id):
        try:
            return Estimates(self.store).read(self.actor, self.sid, estimate_id)
        except DomainError as error:
            if error.status != 404:
                raise
            return None

    def evidence(self, evidence_version_id):
        with self.store.connection() as db:
            return (
                db.execute(
                    'SELECT 1 FROM evidence WHERE study_id=? AND evidence_version_id=?',
                    (self.sid, evidence_version_id),
                ).fetchone()
                is not None
            )


def _resolve(citations, content, *, complete):
    """Check every reference of ``content`` against this study and return the content with
    each table cell's evaluation filled from its cited run. ``complete`` adds the rules a
    saved version must meet: a pinned brief, every alternative mapped and a stated outcome."""
    content = deepcopy(content)
    problems = _identity_problems(content)
    brief = None
    if content['brief_version_id'] is not None:
        brief = citations.brief(content['brief_version_id'])
        if brief is None:
            problems.append(
                issue(['brief_version_id'], 'The brief version must be saved in this study.')
            )
    elif complete:
        problems.append(
            issue(['brief_version_id'], 'Choose the brief version this answer answers.')
        )
    alternatives = (
        {a['alternative_id'] for a in brief['content']['alternatives']} if brief else set()
    )
    criteria = {c['criterion_id']: c for c in brief['content']['criteria']} if brief else {}

    analysis_pins, model_pins = {}, {}

    def calculation(path, version_id):
        version = citations.calculation(version_id)
        if version is None:
            problems.append(issue(path, 'The calculation version must exist in this study.'))
        elif complete:
            # One selected version per logical object, across every kind of answer citation.
            identities = (
                (analysis_pins, version['calculation_id'], version_id, 'analysis'),
                (model_pins, version['content']['model_id'],
                 version['content']['model_revision_id'], 'model'),
            )
            for pins, identity, pin, kind in identities:
                prior = pins.setdefault(identity, pin)
                if prior != pin:
                    problems.append(issue(path,
                        f'This answer cites multiple versions of the same {kind}. '
                        f'Select one {kind} version. Create a distinct analysis for a '
                        'complementary investigation; do not substitute pins automatically.'))
        return version

    mapped = {}
    for index, mapping in enumerate(content['alternative_mappings']):
        path = ['alternative_mappings', index]
        if mapping['alternative_id'] not in alternatives:
            problems.append(
                issue(
                    path + ['alternative_id'], 'The alternative must be in the brief version.'
                )
            )
        for position, version_id in enumerate(mapping['calculation_version_ids']):
            calculation(path + ['calculation_version_ids', position], version_id)
        mapped[mapping['alternative_id']] = set(mapping['calculation_version_ids'])
    if complete and brief and set(mapped) != alternatives:
        problems.append(
            issue(
                ['alternative_mappings'],
                'Map every alternative of the brief version, even to no calculation.',
            )
        )

    for index, cell in enumerate(content['comparison']):
        path = ['comparison', index]
        cell['evaluation'] = None
        cell['output_name'] = None
        criterion = criteria.get(cell['criterion_id'])
        if cell['alternative_id'] not in alternatives:
            problems.append(
                issue(
                    path + ['alternative_id'], 'The alternative must be in the brief version.'
                )
            )
        if criterion is None:
            problems.append(
                issue(path + ['criterion_id'], 'The criterion must be in the brief version.')
            )
        if cell['calculation_version_id'] not in mapped.get(cell['alternative_id'], set()):
            problems.append(
                issue(
                    path + ['calculation_version_id'],
                    'Cite a calculation version mapped to this alternative.',
                )
            )
            continue
        version = calculation(path + ['calculation_version_id'], cell['calculation_version_id'])
        if version is None or criterion is None:
            continue
        if citations.run_position(version, cell['run_id']) is None:
            problems.append(
                issue(
                    path + ['run_id'], 'The run must belong to the cited calculation version.'
                )
            )
            continue
        pinned = version['content']['brief_version_id']
        if pinned not in (None, content['brief_version_id']):
            other = citations.brief(pinned)
            same = other and any(c == criterion for c in other['content']['criteria'])
            if not same:
                problems.append(
                    issue(
                        path + ['criterion_id'],
                        'The calculation evaluates a different definition of this criterion.',
                    )
                )
                continue
        cell['evaluation'] = citations.evaluation(version, cell['run_id'], criterion)
        cell['output_name'] = citations.output_name(version, cell['run_id'], criterion)

    for index, item in enumerate(content['justifications']):
        path = ['justifications', index]
        if item['kind'] == 'evidence_version':
            if not citations.evidence(item['evidence_version_id']):
                problems.append(issue(path, 'The evidence version must exist in this study.'))
            continue
        version = calculation(path + ['calculation_version_id'], item['calculation_version_id'])
        if (
            item['kind'] == 'run'
            and version
            and citations.run_position(version, item['run_id']) is None
        ):
            problems.append(
                issue(
                    path + ['run_id'], 'The run must belong to the cited calculation version.'
                )
            )

    outcome = content['outcome']
    if outcome is None:
        if complete:
            problems.append(
                issue(['outcome'], 'State the outcome: a recommendation, or why there is none.')
            )
    elif outcome['kind'] != 'no_recommendation':
        if outcome['alternative_id'] not in alternatives:
            problems.append(
                issue(
                    ['outcome', 'alternative_id'],
                    'The alternative must be in the brief version.',
                )
            )
        elif outcome['kind'] == 'no_go' and len(alternatives) != 1:
            problems.append(
                issue(
                    ['outcome'],
                    'No-go applies to a study with one alternative; recommend one or none.',
                )
            )

    basis = content['exploration_basis']
    if basis is not None:
        version = calculation(
            ['exploration_basis', 'calculation_version_id'], basis['calculation_version_id']
        )
        if basis['estimate_id'] is not None:
            estimate = citations.estimate(basis['estimate_id'])
            if (
                estimate is None
                or estimate['calculation_version_id'] != basis['calculation_version_id']
            ):
                problems.append(
                    issue(
                        ['exploration_basis', 'estimate_id'],
                        'Cite an estimate of this exact calculation version in this study.',
                    )
                )
            elif estimate['state'] not in ('ready', 'assessed'):
                problems.append(
                    issue(
                        ['exploration_basis', 'estimate_id'],
                        'Wait for the estimate assessment to finish before citing it.',
                    )
                )
            elif any(
                output not in [t['target'] for t in estimate['request']['tolerances']]
                for output in basis['shown_outputs']
            ):
                problems.append(
                    issue(
                        ['exploration_basis', 'shown_outputs'],
                        'Show outputs assessed by the cited estimate.',
                    )
                )
        if version is not None:
            bound = [b['output'] for b in version['content']['criterion_bindings']]
            if any(output not in bound for output in basis['shown_outputs']):
                problems.append(
                    issue(
                        ['exploration_basis', 'shown_outputs'],
                        'Show outputs bound to criteria in the calculation version.',
                    )
                )
    if problems:
        # Paths name the answer content as a draft save sends it.
        fields = [dict(p, path='/content' + p['path']) for p in problems[:20]]
        raise DomainError('invalid_request', 422, fields=fields)
    return content


class StudyAnswers:
    def __init__(self, store):
        self.store = store

    def _draft(self, db, sid):
        row = db.execute(
            'SELECT * FROM study_answer_drafts WHERE study_id=?', (sid,)
        ).fetchone()
        return read_stored(row, sid, 'StudyAnswerDraft1', 'revision') if row else None

    def _latest(self, db, sid):
        row = db.execute(
            'SELECT * FROM study_answer_versions WHERE study_id=? '
            'ORDER BY version_number DESC LIMIT 1',
            (sid,),
        ).fetchone()
        return (
            read_stored(row, sid, 'StudyAnswerVersion1', 'answer_version_id') if row else None
        )

    def state(self, actor, sid):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return dict(draft=self._draft(db, sid), latest_version=self._latest(db, sid))

    def read(self, actor, sid, version):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return read_stored(
                db.execute(
                    'SELECT * FROM study_answer_versions WHERE study_id=? AND answer_version_id=?',
                    (sid, version),
                ).fetchone(),
                sid,
                'StudyAnswerVersion1',
                'answer_version_id',
            )

    def versions(self, actor, sid, *, limit=20, before=None):
        if not 1 <= limit <= 100:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            params = [sid]
            sql = 'SELECT * FROM study_answer_versions WHERE study_id=?'
            if before is not None:
                sql += ' AND version_number<?'
                params.append(before)
            rows = db.execute(
                sql + ' ORDER BY version_number DESC LIMIT ?', (*params, limit + 1)
            ).fetchall()
            items = [
                read_stored(row, sid, 'StudyAnswerVersion1', 'answer_version_id')
                for row in rows[:limit]
            ]
            return dict(
                items=items,
                next_cursor=items[-1]['version_number'] if len(rows) > limit else None,
            )

    def _replayed(self, actor, sid, category, body):
        """The stored outcome of a repeated command, before any citation is re-read."""
        row = self.store.replay(actor, sid, category, body['command_id'], body)
        return row['result'] if row else None

    def save_draft(self, actor, sid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
        validate_answer('StudyAnswerDraftSave2', body)
        replayed = self._replayed(actor, sid, 'answer_draft', body)
        if replayed is not None:
            return replayed
        # Cited records are immutable and never deleted, so they are read before the write.
        content = _resolve(_Citations(self.store, actor, sid), body['content'], complete=False)

        def operation(db):
            previous = self._draft(db, sid)
            self.store.cas(
                previous['revision'] if previous else None, body['expected_revision']
            )
            draft = dict(
                schema_version='2',
                study_id=sid,
                revision=uid(),
                based_on_version_id=previous['based_on_version_id'] if previous else None,
                content=content,
                updated_by=actor,
                updated_at=_now(),
            )
            validate_answer('StudyAnswerDraft2', draft, retained=True)
            db.execute(
                'INSERT INTO study_answer_drafts VALUES(?,?,?) ON CONFLICT(study_id) '
                'DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
                (sid, draft['revision'], canonical(draft).decode()),
            )
            return draft

        return self.store.command(
            actor,
            sid,
            'answer_draft',
            body['command_id'],
            body,
            operation,
            attribute=lambda draft: [('answer_draft', sid, draft['revision'])],
        )

    def save_version(self, actor, sid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
            current = self._draft(db, sid)
        validate_answer('StudyAnswerVersionSave1', body)
        replayed = self._replayed(actor, sid, 'answer_version', body)
        if replayed is not None:
            return replayed
        self.store.cas(current['revision'] if current else None, body['expected_revision'])
        # Cells are re-read from their runs, so the version stores the evaluations as of now.
        content = current_content(current['content'])
        validate_answer('StudyAnswerContent2', content)
        content = _resolve(_Citations(self.store, actor, sid), content, complete=True)
        basis = content['exploration_basis']
        if basis is not None:
            if basis['estimate_id'] is None:
                raise DomainError(
                    'invalid_request',
                    422,
                    fields=[
                        issue(
                            ['content', 'exploration_basis', 'estimate_id'],
                            'Prepare and check joint exploration before publishing this answer. '
                            'An answer without interactive exploration may leave its basis '
                            'unassigned.',
                        )
                    ],
                )
            ready = preparation(
                self.store,
                actor,
                sid,
                basis['estimate_id'],
                dict(shown_outputs=basis['shown_outputs']),
            )
            if not ready['ready']:
                raise DomainError(
                    'invalid_request',
                    422,
                    fields=[
                        dict(p, path='/content/exploration_basis' + p['path'])
                        for g in ready['groups']
                        for p in g['problems']
                    ][:20],
                )

        def operation(db):
            draft = self._draft(db, sid)
            self.store.cas(draft['revision'] if draft else None, body['expected_revision'])
            latest = self._latest(db, sid)
            version = dict(
                schema_version='2',
                study_id=sid,
                answer_version_id=uid(),
                version_number=latest['version_number'] + 1 if latest else 1,
                predecessor_version_id=latest['answer_version_id'] if latest else None,
                content=content,
                created_by=actor,
                created_at=_now(),
            )
            version['digest'] = digest(version)
            validate_answer('StudyAnswerVersion2', version, retained=True)
            db.execute(
                'INSERT INTO study_answer_versions VALUES(?,?,?,?)',
                (
                    version['answer_version_id'],
                    sid,
                    version['version_number'],
                    canonical(version).decode(),
                ),
            )
            # The draft continues from the saved version with a new revision.
            nextdraft = dict(
                draft,
                schema_version='2',
                revision=uid(),
                based_on_version_id=version['answer_version_id'],
                content=deepcopy(content),
                updated_by=actor,
                updated_at=version['created_at'],
            )
            db.execute(
                'UPDATE study_answer_drafts SET revision=?,payload=? WHERE study_id=?',
                (nextdraft['revision'], canonical(nextdraft).decode(), sid),
            )
            return dict(version=version, draft=nextdraft)

        return self.store.command(
            actor,
            sid,
            'answer_version',
            body['command_id'],
            body,
            operation,
            attribute=lambda saved: [
                ('answer_version', sid, saved['version']['answer_version_id'])
            ],
        )
