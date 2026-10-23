"""Calculations and reference marks (ADR-0009, ADR-0010).

A calculation has immutable, numbered versions. A version freezes an exact set of
configuration versions, all for one model version, how the set was made, and the binding
of each study criterion of one saved brief version to the model output that measures it.
Runs attach by reference: the runs of a calculation version are the runs of its member
configurations, so running or retrying points never creates a version.

A binding is refused unless the output's bound unit equals the criterion's unit exactly
(dimensionless is the empty unit); no unit is ever converted here. Runs are evaluated from
their integrity-checked retained records only: constraints read met, not met or
unresolved, objectives report the measured value, and an unbound criterion is unresolved.

A version's set is hand-picked by a client, or sampled: generated from reference
configurations by a sampling operation (``calculation_designs``), the only writer of a
sampled design. Clients may carry a sampled design unchanged into a new version.

A reference mark labels one configuration version as a baseline for its model. It is set
and cleared by commands and never changes or pins the configuration.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json

from jsonschema import Draft202012Validator, FormatChecker

from .brief import read_stored as read_brief_row
from .contracts import diagnostics
from .contracts import DomainError, canonical, definitions, digest, issue, uid
from .criterion_evaluation import evaluate_run, unresolved
from .execution_bundle import validate_frozen_configuration
from .history import History, RetainedRecordError, calculation_runs
from .units import port_units


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
_NULL = dict(type='null')
_NULL_ID = dict(anyOf=[_ID, _NULL])
_NAME = dict(type='string', minLength=1, maxLength=256, pattern=r'\S')
_TEXT = dict(type='string', minLength=0, maxLength=4096)
_UNITS = dict(type='string', maxLength=64)
_TIME = dict(type='string', format='date-time')
_COUNT = dict(type='integer', minimum=1, maximum=9007199254740991)
_CURSOR = dict(anyOf=[_COUNT, dict(type='null')])
_HASH = dict(type='string', pattern='^[0-9a-f]{64}$')
_NUMBER = dict(type='number', minimum=-(2**53 - 1), maximum=2**53 - 1)
_SEED = dict(type='integer', minimum=0, maximum=2**32 - 1)
# The largest configuration set one version may freeze.
MAX_MEMBERS = 1000
# The most points one sampled version generates; each point is one configuration version.
MAX_SAMPLED = 128
# Runs evaluated per page: each one is an integrity-checked retained read.
RUN_PAGE = 20

DEFINITIONS = {
    'CriterionBinding1': _object(
        dict(
            criterion_id=_ID,
            output={'$ref': '#/$defs/PortRef'},
        )
    ),
    'HandPickedDesign1': _object(dict(kind=dict(const='hand_picked'))),
    # One sampled input of a reference configuration: a range in the saved assignment's own
    # units (never converted), an optional step grid from the lower bound and an optional
    # explicit co-variation group whose members move together.
    'SampledDimension1': _object(
        dict(
            target={'$ref': '#/$defs/PortRef'},
            lower=_NUMBER,
            upper=_NUMBER,
            units=_UNITS,
            step=dict(
                anyOf=[dict(type='number', exclusiveMinimum=0, maximum=2**53 - 1), _NULL]
            ),
            covary_group=dict(anyOf=[dict(type='string', minLength=1, maxLength=100), _NULL]),
        )
    ),
    'SampledGroup1': _object(
        dict(
            reference_configuration_revision_id=_ID,
            dimensions=dict(
                type='array',
                items={'$ref': '#/$defs/SampledDimension1'},
                minItems=1,
                maxItems=32,
            ),
            training_count=dict(type='integer', minimum=3, maximum=64),
            check_count=dict(type='integer', minimum=2, maximum=64),
        )
    ),
    # One generated point: its group, its partition (check points are kept apart for
    # assessing estimates), its coordinates on the group's independent dimensions and the
    # configuration version that freezes it.
    'SampledPoint1': _object(
        dict(
            group=dict(type='integer', minimum=0, maximum=7),
            partition=dict(enum=['training', 'check']),
            identity=_HASH,
            vector=dict(type='array', items=_NUMBER, minItems=1, maxItems=32),
            configuration_revision_id=_ID,
        )
    ),
    'SampledDesign1': _object(
        dict(
            kind=dict(const='sampled'),
            operation_id=_ID,
            method=dict(const='latin_hypercube'),
            seed=_SEED,
            groups=dict(
                type='array', items={'$ref': '#/$defs/SampledGroup1'}, minItems=1, maxItems=8
            ),
            points=dict(
                type='array',
                items={'$ref': '#/$defs/SampledPoint1'},
                minItems=1,
                maxItems=MAX_SAMPLED,
            ),
            rationale=dict(type='string', minLength=1, maxLength=4096, pattern=r'\S'),
            runtime=definitions()['ExecutionBundle2']['properties']['runtime'],
            design_digest=_HASH,
            design_artifact=_object(
                dict(
                    process_uuid=_ID,
                    store_uuid=_ID,
                    artifact_uuid=_ID,
                    request_sha256=_HASH,
                    result_sha256=_HASH,
                )
            ),
        )
    ),
    # How the set was made: hand-picked, or generated from reference configurations by a
    # sampling operation (only that operation writes a sampled design).
    'CalculationDesign1': dict(
        oneOf=[{'$ref': '#/$defs/HandPickedDesign1'}, {'$ref': '#/$defs/SampledDesign1'}]
    ),
    'CalculationContent1': _object(
        dict(
            schema_version=dict(const='1'),
            name=_NAME,
            description=_TEXT,
            model_id=_ID,
            model_revision_id=_ID,
            configuration_revision_ids=dict(
                type='array', items=_ID, minItems=1, maxItems=MAX_MEMBERS, uniqueItems=True
            ),
            design={'$ref': '#/$defs/CalculationDesign1'},
            brief_version_id=dict(
                **_NULL_ID,
                description=(
                    'The saved study brief version whose criteria the bindings measure; null '
                    'only when nothing is bound.'
                ),
            ),
            criterion_bindings=dict(
                type='array', items={'$ref': '#/$defs/CriterionBinding1'}, maxItems=64
            ),
        )
    ),
    'CalculationVersion1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            calculation_id=_ID,
            calculation_version_id=_ID,
            version_number=_COUNT,
            predecessor_version_id=_NULL_ID,
            content={'$ref': '#/$defs/CalculationContent1'},
            created_by=_ID,
            created_at=_TIME,
            digest=dict(type='string', pattern='^[0-9a-f]{64}$'),
        )
    ),
    'Calculation1': _object(
        dict(
            calculation_id=_ID,
            study_id=_ID,
            latest_version={'$ref': '#/$defs/CalculationVersion1'},
        )
    ),
    'CalculationPage1': _object(
        dict(
            items=dict(type='array', items={'$ref': '#/$defs/Calculation1'}, maxItems=100),
            next_cursor=_CURSOR,
        )
    ),
    'CalculationCreate1': _object(
        dict(command_id=_ID, content={'$ref': '#/$defs/CalculationContent1'})
    ),
    'CalculationVersionSave1': _object(
        dict(
            command_id=_ID,
            expected_version_id=_ID,
            content={'$ref': '#/$defs/CalculationContent1'},
        )
    ),
    'CalculationVersionPage1': _object(
        dict(
            items=dict(
                type='array', items={'$ref': '#/$defs/CalculationVersion1'}, maxItems=100
            ),
            next_cursor=_CURSOR,
        )
    ),
    # One criterion of the pinned brief version for one run. A constraint reads met, not
    # met or unresolved; an objective reports its measured value or is unresolved. The
    # value is null with a reason whenever it is unavailable, never zero.
    'CriterionEvaluation1': _object(
        dict(
            criterion_id=_ID,
            kind=dict(enum=['constraint', 'objective']),
            outcome=dict(enum=['met', 'not_met', 'measured', 'unresolved']),
            reason=dict(
                enum=[
                    'threshold_comparison',
                    'measured',
                    'criterion_not_bound',
                    'run_not_recorded',
                    'retained_record_invalid',
                    'convergence_unresolved',
                    'required_output_unavailable',
                    'invalid_criterion_or_units',
                ]
            ),
            value=dict(anyOf=[dict(type='number'), dict(type='null')]),
            units=_UNITS,
        )
    ),
    'CalculationRun1': _object(
        dict(
            run_id=_ID,
            configuration_revision_id=_ID,
            record_state=dict(enum=['accepted_run', 'dispatching', 'recorded', 'uncertain']),
            evaluations=dict(
                type='array', items={'$ref': '#/$defs/CriterionEvaluation1'}, maxItems=64
            ),
        )
    ),
    'CalculationRunPage1': _object(
        dict(
            calculation_version_id=_ID,
            items=dict(
                type='array', items={'$ref': '#/$defs/CalculationRun1'}, maxItems=RUN_PAGE
            ),
            next_cursor=_CURSOR,
        )
    ),
    'ReferenceMark1': _object(
        dict(
            configuration_revision_id=_ID,
            configuration_id=_ID,
            model_id=_ID,
            model_revision_id=_ID,
            marked_by=_ID,
            marked_at=_TIME,
        )
    ),
    'ReferenceMarkCommand1': _object(
        dict(
            command_id=_ID,
            configuration_revision_id=_ID,
            action=dict(enum=['set', 'clear']),
        )
    ),
    'ReferenceMarkState1': _object(
        dict(
            configuration_revision_id=_ID,
            mark=dict(anyOf=[{'$ref': '#/$defs/ReferenceMark1'}, dict(type='null')]),
        )
    ),
    'ReferenceMarkList1': _object(
        dict(
            items=dict(
                type='array', items={'$ref': '#/$defs/ReferenceMark1'}, maxItems=MAX_MEMBERS
            )
        )
    ),
}

# Boundary-supported designs are a new format; earlier saved versions stay unchanged.
DEFINITIONS['SampledDesign2'] = deepcopy(DEFINITIONS['SampledDesign1'])
DEFINITIONS['SampledDesign2']['properties']['method'] = dict(const='boundary_latin_hypercube')
DEFINITIONS['CalculationDesign2'] = dict(
    oneOf=[
        {'$ref': '#/$defs/HandPickedDesign1'},
        {'$ref': '#/$defs/SampledDesign1'},
        {'$ref': '#/$defs/SampledDesign2'},
    ]
)
for name in ('CalculationContent', 'CalculationVersion'):
    DEFINITIONS[name + '2'] = deepcopy(DEFINITIONS[name + '1'])
    DEFINITIONS[name + '2']['properties']['schema_version'] = dict(const='2')
    DEFINITIONS[name + 'Read2'] = dict(
        oneOf=[
            {'$ref': '#/$defs/' + name + '1'},
            {'$ref': '#/$defs/' + name + '2'},
        ]
    )
DEFINITIONS['CalculationContent2']['properties']['design'] = {
    '$ref': '#/$defs/CalculationDesign2'
}
DEFINITIONS['CalculationVersion2']['properties']['content'] = {
    '$ref': '#/$defs/CalculationContent2'
}
for old, new, field, target in (
    ('Calculation1', 'Calculation2', 'latest_version', 'CalculationVersionRead2'),
    ('CalculationPage1', 'CalculationPage2', 'items', 'Calculation2'),
    ('CalculationVersionPage1', 'CalculationVersionPage2', 'items', 'CalculationVersionRead2'),
    ('CalculationCreate1', 'CalculationCreate2', 'content', 'CalculationContentRead2'),
    (
        'CalculationVersionSave1',
        'CalculationVersionSave2',
        'content',
        'CalculationContentRead2',
    ),
):
    DEFINITIONS[new] = deepcopy(DEFINITIONS[old])
    slot = DEFINITIONS[new]['properties'][field]
    if field == 'items':
        slot['items'] = {'$ref': '#/$defs/' + target}
    else:
        DEFINITIONS[new]['properties'][field] = {'$ref': '#/$defs/' + target}


# Validation terminology is a new saved format; predecessor bytes/digests stay frozen.
DEFINITIONS['SampledGroup2'] = deepcopy(DEFINITIONS['SampledGroup1'])
_group = DEFINITIONS['SampledGroup2']
_group['properties']['validation_count'] = _group['properties'].pop('check_count')
_group['required'] = [
    'validation_count' if name == 'check_count' else name for name in _group['required']
]
DEFINITIONS['SampledPoint2'] = deepcopy(DEFINITIONS['SampledPoint1'])
DEFINITIONS['SampledPoint2']['properties']['partition'] = dict(enum=['training', 'validation'])
for old, new in (('SampledDesign1', 'SampledDesign3'), ('SampledDesign2', 'SampledDesign4')):
    DEFINITIONS[new] = deepcopy(DEFINITIONS[old])
    DEFINITIONS[new]['properties']['groups']['items'] = {'$ref': '#/$defs/SampledGroup2'}
    DEFINITIONS[new]['properties']['points']['items'] = {'$ref': '#/$defs/SampledPoint2'}
DEFINITIONS['CalculationDesign3'] = dict(oneOf=[
    {'$ref': '#/$defs/' + name}
    for name in ('HandPickedDesign1', 'SampledDesign3', 'SampledDesign4')
])
for name in ('CalculationContent', 'CalculationVersion'):
    DEFINITIONS[name + '3'] = deepcopy(DEFINITIONS[name + '2'])
    DEFINITIONS[name + '3']['properties']['schema_version'] = dict(const='3')
    DEFINITIONS[name + 'Read3'] = dict(oneOf=[
        {'$ref': '#/$defs/' + name + str(version)} for version in (1, 2, 3)
    ])
DEFINITIONS['CalculationContent3']['properties']['design'] = {
    '$ref': '#/$defs/CalculationDesign3'
}
DEFINITIONS['CalculationVersion3']['properties']['content'] = {
    '$ref': '#/$defs/CalculationContent3'
}
for old, new, field, target in (
    ('Calculation2', 'Calculation3', 'latest_version', 'CalculationVersionRead3'),
    ('CalculationPage2', 'CalculationPage3', 'items', 'Calculation3'),
    ('CalculationVersionPage2', 'CalculationVersionPage3', 'items', 'CalculationVersionRead3'),
    ('CalculationCreate2', 'CalculationCreate3', 'content', 'CalculationContentRead3'),
    ('CalculationVersionSave2', 'CalculationVersionSave3', 'content', 'CalculationContentRead3'),
):
    DEFINITIONS[new] = deepcopy(DEFINITIONS[old])
    slot = DEFINITIONS[new]['properties'][field]
    if field == 'items':
        slot['items'] = {'$ref': '#/$defs/' + target}
    else:
        DEFINITIONS[new]['properties'][field] = {'$ref': '#/$defs/' + target}


# Execution intent belongs to the saved version; older records remain unchanged.
DEFINITIONS['AnalysisEstimatePlan1'] = _object(dict(
    tolerances=dict(type='array', minItems=1, maxItems=32, items=_object(dict(
        target={'$ref': '#/$defs/PortRef'},
        absolute=dict(type='number', minimum=0, maximum=2**53 - 1),
        relative=dict(type='number', minimum=0, maximum=2**53 - 1),
    ))),
))
for name in ('CalculationContent', 'CalculationVersion'):
    DEFINITIONS[name + '4'] = deepcopy(DEFINITIONS[name + '3'])
    DEFINITIONS[name + '4']['properties']['schema_version'] = dict(const='4')
    DEFINITIONS[name + 'Read4'] = dict(oneOf=[
        {'$ref': '#/$defs/' + name + str(v)} for v in (1, 2, 3, 4)
    ])
DEFINITIONS['CalculationContent4']['properties']['estimate_plan'] = dict(anyOf=[
    {'$ref': '#/$defs/AnalysisEstimatePlan1'}, dict(type='null'),
])
DEFINITIONS['CalculationContent4']['required'].append('estimate_plan')
# A new version may carry an unchanged historical sampled design.
DEFINITIONS['CalculationContent4']['properties']['design'] = dict(oneOf=[
    {'$ref': '#/$defs/' + name}
    for name in ('HandPickedDesign1', 'SampledDesign1', 'SampledDesign2',
                 'SampledDesign3', 'SampledDesign4')
])
DEFINITIONS['CalculationVersion4']['properties']['content'] = {
    '$ref': '#/$defs/CalculationContent4'
}
for old, new, field, target in (
    ('Calculation3', 'Calculation4', 'latest_version', 'CalculationVersionRead4'),
    ('CalculationPage3', 'CalculationPage4', 'items', 'Calculation4'),
    ('CalculationVersionPage3', 'CalculationVersionPage4', 'items', 'CalculationVersionRead4'),
    ('CalculationCreate3', 'CalculationCreate4', 'content', 'CalculationContentRead4'),
    ('CalculationVersionSave3', 'CalculationVersionSave4', 'content', 'CalculationContentRead4'),
):
    DEFINITIONS[new] = deepcopy(DEFINITIONS[old])
    slot = DEFINITIONS[new]['properties'][field]
    if field == 'items':
        slot['items'] = {'$ref': '#/$defs/' + target}
    else:
        DEFINITIONS[new]['properties'][field] = {'$ref': '#/$defs/' + target}


DEFINITIONS['AnalysisLaunch1'] = _object({})
DEFINITIONS['AnalysisResume1'] = _object(dict(
    command_id=DEFINITIONS['CalculationVersion1']['properties']['calculation_id'],
))
DEFINITIONS['AnalysisExecutionRecovery1'] = _object(dict(
    schema_version=dict(const='1'), can_resume=dict(type='boolean'),
    reason=dict(anyOf=[dict(type='string', maxLength=4096), dict(type='null')]),
))
DEFINITIONS['AnalysisExecution1'] = _object(dict(
    schema_version=dict(const='1'),
    calculation_version_id=DEFINITIONS['CalculationVersion1']['properties']['calculation_id'],
    state=dict(enum=['calculating', 'validating', 'complete', 'failed', 'needs_review']),
    reason=dict(anyOf=[dict(type='string', maxLength=4096), dict(type='null')]),
    completed_count=dict(type='integer', minimum=0, maximum=MAX_MEMBERS),
    total_count=dict(type='integer', minimum=1, maximum=MAX_MEMBERS),
    estimate_id=dict(anyOf=[DEFINITIONS['CalculationVersion1']['properties']['calculation_id'],
                           dict(type='null')]),
    runs=dict(type='array', maxItems=MAX_MEMBERS, items=_object(dict(
        configuration_revision_id=DEFINITIONS['CalculationVersion1']['properties'][
            'calculation_id'],
        run_id=dict(anyOf=[DEFINITIONS['CalculationVersion1']['properties']['calculation_id'],
                          dict(type='null')]),
        reused=dict(type='boolean'), completed=dict(type='boolean'),
    ))),
))
DEFINITIONS['AnalysisExecution2'] = deepcopy(DEFINITIONS['AnalysisExecution1'])
DEFINITIONS['AnalysisExecution2']['properties'].update(
    schema_version=dict(const='2'),
    state=dict(enum=['calculating', 'validating', 'complete', 'failed', 'needs_review', 'cancelled']),
    admission_state=dict(enum=['ready', 'waiting', 'unavailable', 'invalid_attestation',
                               'needs_review', 'revoked', 'cancelled', 'stopped']),
)
DEFINITIONS['AnalysisExecution2']['required'].append('admission_state')
DEFINITIONS['AnalysisExecutionRead1'] = dict(anyOf=[
    {'$ref': '#/$defs/AnalysisExecution1'}, dict(type='null'),
])
DEFINITIONS['AnalysisExecutionRead2'] = dict(anyOf=[
    {'$ref': '#/$defs/AnalysisExecution1'}, {'$ref': '#/$defs/AnalysisExecution2'}, dict(type='null'),
])

_VALIDATORS = {}


def _validator(name):
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(
            {'$defs': definitions() | DEFINITIONS, **DEFINITIONS[name]},
            format_checker=FormatChecker(),
        )
    return _VALIDATORS[name]


def validate_calculation(name, value, *, retained=False):
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
CREATE TABLE IF NOT EXISTS calculations(
 calculation_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id)
);
CREATE TABLE IF NOT EXISTS calculation_versions(
 calculation_version_id TEXT PRIMARY KEY,
 calculation_id TEXT NOT NULL REFERENCES calculations(calculation_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(calculation_id,version_number)
);
CREATE TRIGGER IF NOT EXISTS calculations_no_update
 BEFORE UPDATE ON calculations
 BEGIN SELECT RAISE(ABORT,'calculation identities are immutable'); END;
CREATE TRIGGER IF NOT EXISTS calculations_no_delete
 BEFORE DELETE ON calculations
 BEGIN SELECT RAISE(ABORT,'calculations are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS calculation_versions_no_update
 BEFORE UPDATE ON calculation_versions
 BEGIN SELECT RAISE(ABORT,'saved calculation versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS calculation_versions_no_delete
 BEFORE DELETE ON calculation_versions
 BEGIN SELECT RAISE(ABORT,'saved calculation versions are never deleted'); END;
CREATE TABLE IF NOT EXISTS reference_marks(
 configuration_revision_id TEXT PRIMARY KEY
  REFERENCES configurations(configuration_revision_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 payload TEXT NOT NULL
);
"""


def ensure(store):
    """Register owner tables through the application's single writer."""
    if store.verify_schema():
        return
    with store.connection() as db:
        db.executescript(DDL)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read_version(row, sid):
    if row is None:
        raise DomainError('resource_not_found', 404)
    try:
        value = json.loads(row['payload'])
        validate_calculation('CalculationVersionRead4', value, retained=True)
        if (
            value['study_id'] != sid
            or value['calculation_version_id'] != row['calculation_version_id']
            or value['calculation_id'] != row['calculation_id']
            or value['version_number'] != row['version_number']
            or value['digest'] != digest({k: v for k, v in value.items() if k != 'digest'})
        ):
            raise ValueError('Calculation version identity mismatch')
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


def _frozen_configuration(db, sid, revision):
    """The study's saved configuration version, validated as a frozen record (schema, digests,
    model pairing) before any of its pins are trusted; ``None`` when absent."""
    row = db.execute(
        'SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?',
        (sid, revision),
    ).fetchone()
    if row is None:
        return None
    try:
        frozen = json.loads(row['payload'])
        validate_frozen_configuration(frozen)
        configuration = frozen['configuration']
        if (
            configuration['study_id'] != sid
            or configuration['configuration_revision_id'] != revision
        ):
            raise ValueError('Configuration identity mismatch')
        return frozen
    except (ValueError, TypeError, KeyError, DomainError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


def independent_dimensions(dimensions):
    """The dimensions that carry one coordinate each: every uncovaried dimension and the first
    of each co-variation group, in declaration order."""
    seen, result = set(), []
    for dimension in dimensions:
        group = dimension['covary_group']
        if group is None or group not in seen:
            result.append(dimension)
        if group is not None:
            seen.add(group)
    return result


def _output_ports(model):
    """(instance_id, port_id) -> bound unit for every output port of the model version."""
    units = port_units(model)
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    return {
        (i['instance_id'], p['port_id']): units[
            (i['instance_id'], i['definition_version_id'], p['port_id'])
        ]
        for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports']
        if p['direction'] == 'output'
    }


def _version_written(version):
    """The calculation version an accepted create or save wrote, for agent attribution."""
    return [
        ('calculation_version', version['calculation_id'], version['calculation_version_id'])
    ]


class Analyses:
    def __init__(self, store):
        self.store = store

    # Reads ---------------------------------------------------------------------------

    def _latest(self, db, sid, cid):
        row = db.execute(
            'SELECT * FROM calculation_versions WHERE study_id=? AND calculation_id=? '
            'ORDER BY version_number DESC LIMIT 1',
            (sid, cid),
        ).fetchone()
        return _read_version(row, sid) if row else None

    def _family(self, db, sid, cid):
        if (
            db.execute(
                'SELECT 1 FROM calculations WHERE study_id=? AND calculation_id=?', (sid, cid)
            ).fetchone()
            is None
        ):
            raise DomainError('resource_not_found', 404)
        latest = self._latest(db, sid, cid)
        if latest is None:
            raise DomainError('corrupt_retained_record', 409)
        return dict(calculation_id=cid, study_id=sid, latest_version=latest)

    def list(self, actor, sid, *, limit=20, after=None, model_revision_id=None):
        """Calculations in creation order; with ``model_revision_id``, only those whose latest
        version uses that model version, filtered before paging."""
        if not 1 <= limit <= 100:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            rows = db.execute(
                'SELECT c.rowid,c.calculation_id FROM calculations c WHERE c.study_id=? '
                'AND c.rowid>? AND (CAST(? AS TEXT) IS NULL OR (SELECT json_extract(v.payload,'
                "'$.content.model_revision_id') FROM calculation_versions v WHERE "
                'v.calculation_id=c.calculation_id ORDER BY v.version_number DESC LIMIT 1)=?) '
                'ORDER BY c.rowid LIMIT ?',
                (sid, after or 0, model_revision_id, model_revision_id, limit + 1),
            ).fetchall()
            items = [self._family(db, sid, row['calculation_id']) for row in rows[:limit]]
            return dict(
                items=items, next_cursor=rows[limit - 1]['rowid'] if len(rows) > limit else None
            )

    def read(self, actor, sid, cid):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return self._family(db, sid, cid)

    def versions(self, actor, sid, cid, *, limit=20, before=None):
        if not 1 <= limit <= 100:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            self._family(db, sid, cid)
            params = [sid, cid]
            sql = 'SELECT * FROM calculation_versions WHERE study_id=? AND calculation_id=?'
            if before is not None:
                sql += ' AND version_number<?'
                params.append(before)
            rows = db.execute(
                sql + ' ORDER BY version_number DESC LIMIT ?', (*params, limit + 1)
            ).fetchall()
            items = [_read_version(row, sid) for row in rows[:limit]]
            return dict(
                items=items,
                next_cursor=items[-1]['version_number'] if len(rows) > limit else None,
            )

    def _version(self, db, sid, version_id):
        return _read_version(
            db.execute(
                'SELECT * FROM calculation_versions WHERE study_id=? AND calculation_version_id=?',
                (sid, version_id),
            ).fetchone(),
            sid,
        )

    def latest(self, db, sid, cid):
        """The calculation's latest version, read in the caller's transaction."""
        return self._family(db, sid, cid)['latest_version']

    def version(self, actor, sid, version_id):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            return self._version(db, sid, version_id)

    def runs(
        self, actor, sid, version_id, *, limit=RUN_PAGE, after=None,
        configuration_revision_id=None,
    ):
        """One page of the version's runs (its member configurations' runs), in insertion
        order, each evaluated against the pinned brief version's criteria."""
        if not 1 <= limit <= RUN_PAGE:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            version = self._version(db, sid, version_id)
            content = version['content']
            criteria = []
            if content['brief_version_id'] is not None:
                criteria = self._brief(db, sid, content['brief_version_id'])['content'][
                    'criteria'
                ]
            members = content['configuration_revision_ids']
            if configuration_revision_id is not None:
                if configuration_revision_id not in members:
                    raise DomainError('resource_not_found', 404)
                members = [configuration_revision_id]
            rows = calculation_runs(db, sid, members, after or 0, limit + 1)
        bindings = {b['criterion_id']: b['output'] for b in content['criterion_bindings']}
        history, items = History(self.store), []
        for row in rows[:limit]:
            if row['state'] != 'recorded':
                evaluations = unresolved(criteria, 'run_not_recorded')
            else:
                try:
                    results = history.retained_projection(actor, sid, row['run_id']).history['results']
                    evaluations = evaluate_run(results, criteria, bindings)
                except RetainedRecordError:
                    evaluations = unresolved(criteria, 'retained_record_invalid')
                except DomainError as error:
                    if error.status in (403, 404):
                        raise
                    evaluations = unresolved(criteria, 'retained_record_invalid')
            items.append(
                dict(
                    run_id=row['run_id'],
                    configuration_revision_id=row['configuration_revision_id'],
                    record_state=row['state'],
                    evaluations=evaluations,
                )
            )
        return dict(
            calculation_version_id=version_id,
            items=items,
            next_cursor=rows[limit - 1]['position'] if len(rows) > limit else None,
        )

    # Writes --------------------------------------------------------------------------

    def _brief(self, db, sid, brief_version_id):
        return read_brief_row(
            db.execute(
                'SELECT * FROM study_brief_versions WHERE study_id=? AND brief_version_id=?',
                (sid, brief_version_id),
            ).fetchone(),
            sid,
            'StudyBriefVersion1',
            'brief_version_id',
        )

    def _check_content(self, db, actor, sid, content):
        """Members, model version, brief version and bindings, read in the write
        transaction; every problem is reported, nothing is repaired or converted."""
        problems = []
        try:
            self.store.model_association(db, actor, sid, content['model_id'], write=True)
        except DomainError as error:
            if error.status != 404:
                raise
            raise DomainError(
                'invalid_request',
                422,
                fields=[issue(['model_id'], 'The model must belong to this study.')],
            ) from None
        model = None
        for index, revision in enumerate(content['configuration_revision_ids']):
            frozen = _frozen_configuration(db, sid, revision)
            if frozen is None:
                problems.append(
                    issue(
                        ['configuration_revision_ids', index],
                        'Every configuration version must exist in this study.',
                    )
                )
                continue
            configuration = frozen['configuration']
            if (
                configuration['model_id'] != content['model_id']
                or configuration['model_revision_id'] != content['model_revision_id']
            ):
                problems.append(
                    issue(
                        ['configuration_revision_ids', index],
                        "Every configuration version must use the calculation's model version.",
                    )
                )
            elif model is None:
                model = frozen['model_snapshot']
        if content['design']['kind'] == 'sampled':
            problems += self._sampled_problems(db, sid, content)
        plan = content.get('estimate_plan')
        if plan is not None:
            if content['design']['kind'] != 'sampled':
                problems.append(issue(['estimate_plan'], 'Estimates require a sampled design.'))
            outputs = _output_ports(model) if model is not None else {}
            targets = [(t['target']['instance_id'], t['target']['port_id'])
                       for t in plan['tolerances']]
            if len(set(targets)) != len(targets) or not set(targets) <= set(outputs):
                problems.append(issue(['estimate_plan', 'tolerances'],
                                      'Choose each output of this model version at most once.'))

        if problems:
            raise DomainError('invalid_request', 422, fields=problems[:20])
        # Monetary values carry the immutable price basis of the exact model version.
        # Analysis cannot silently acquire a basis from a later draft or explanation.
        if model is not None:
            from .explanations import quantity_price_basis
            from .units import monetary_expression
            for (instance_id, port_id), expression in _output_ports(model).items():
                if monetary_expression(expression) is not None:
                    quantity_price_basis(db, sid, model, dict(instance_id=instance_id, port_id=port_id))
        bindings = content['criterion_bindings']
        if content['brief_version_id'] is None:
            if bindings:
                raise DomainError(
                    'invalid_request',
                    422,
                    fields=[
                        issue(
                            ['brief_version_id'],
                            'Bindings need the saved brief version whose criteria they measure.',
                        )
                    ],
                )
            return
        try:
            brief = self._brief(db, sid, content['brief_version_id'])
        except DomainError as error:
            if error.status != 404:
                raise
            raise DomainError(
                'invalid_request',
                422,
                fields=[
                    issue(['brief_version_id'], 'The brief version must exist in this study.')
                ],
            ) from None
        criteria = {c['criterion_id']: c for c in brief['content']['criteria']}
        outputs = _output_ports(model)
        seen = set()
        for index, binding in enumerate(bindings):
            path = ['criterion_bindings', index]
            criterion = criteria.get(binding['criterion_id'])
            if criterion is None:
                problems.append(issue(path, 'The criterion must be in the brief version.'))
                continue
            if binding['criterion_id'] in seen:
                problems.append(issue(path, 'Each criterion is bound at most once.'))
                continue
            seen.add(binding['criterion_id'])
            key = (binding['output']['instance_id'], binding['output']['port_id'])
            if key not in outputs:
                problems.append(
                    issue(path, 'The binding must name an output of the model version.')
                )
            elif outputs[key] != criterion['units']:
                problems.append(
                    issue(
                        path,
                        "The output's units must equal the criterion's units exactly; "
                        'units are never converted.',
                    )
                )
        if problems:
            raise DomainError('invalid_request', 422, fields=problems[:20])

    def _sampled_problems(self, db, sid, content):
        """A sampled design names its members exactly, point by point, and every reference
        configuration is a saved version of the calculation's model version."""
        design, problems = content['design'], []
        if content['configuration_revision_ids'] != [
            p['configuration_revision_id'] for p in design['points']
        ]:
            problems.append(
                issue(
                    ['configuration_revision_ids'],
                    "A sampled version's members are exactly its design points, in order.",
                )
            )
        for index, group in enumerate(design['groups']):
            frozen = _frozen_configuration(
                db, sid, group['reference_configuration_revision_id']
            )
            if (
                frozen is None
                or frozen['configuration']['model_revision_id']
                != (content['model_revision_id'])
            ):
                problems.append(
                    issue(
                        ['design', 'groups', index, 'reference_configuration_revision_id'],
                        "Every reference must be a configuration version of the calculation's "
                        'model version.',
                    )
                )
        for index, point in enumerate(design['points']):
            if point['group'] >= len(design['groups']) or len(point['vector']) != len(
                independent_dimensions(design['groups'][point['group']]['dimensions'])
            ):
                problems.append(
                    issue(['design', 'points', index], 'The point does not fit its group.')
                )
        return problems

    @staticmethod
    def _public_design(content, latest):
        """Clients write hand-picked sets. A sampled design is written only by its sampling
        operation; a client may carry it unchanged into a new version (to rename or re-bind)."""
        if content['design']['kind'] == 'hand_picked':
            return
        if latest is None or (
            content['design'] != latest['content']['design']
            or content['configuration_revision_ids']
            != latest['content']['configuration_revision_ids']
        ):
            raise DomainError(
                'invalid_request',
                422,
                fields=[
                    issue(
                        ['content', 'design'],
                        'A sampled design is generated by a sampling operation; adding or '
                        'removing points by hand makes a hand-picked version.',
                    )
                ],
            )

    def _insert(self, db, actor, sid, cid, content, latest):
        version = dict(
            schema_version=content['schema_version'],
            study_id=sid,
            calculation_id=cid,
            calculation_version_id=uid(),
            version_number=latest['version_number'] + 1 if latest else 1,
            predecessor_version_id=latest['calculation_version_id'] if latest else None,
            content=deepcopy(content),
            created_by=actor,
            created_at=_now(),
        )
        version['digest'] = digest(version)
        validate_calculation('CalculationVersionRead4', version, retained=True)
        db.execute(
            'INSERT INTO calculation_versions VALUES(?,?,?,?,?)',
            (
                version['calculation_version_id'],
                cid,
                sid,
                version['version_number'],
                canonical(version).decode(),
            ),
        )
        return version

    def create(self, actor, sid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
        validate_calculation('CalculationCreate4', body)

        def operation(db):
            self._public_design(body['content'], None)
            self._check_content(db, actor, sid, body['content'])
            cid = uid()
            db.execute('INSERT INTO calculations VALUES(?,?)', (cid, sid))
            return self._insert(db, actor, sid, cid, body['content'], None)

        return self.store.command(
            actor,
            sid,
            'calculation_create',
            body['command_id'],
            body,
            operation,
            attribute=_version_written,
        )

    def save_version(self, actor, sid, cid, body):
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
            self._family(db, sid, cid)
        validate_calculation('CalculationVersionSave4', body)

        def operation(db):
            latest = self._latest(db, sid, cid)
            self.store.cas(latest['calculation_version_id'], body['expected_version_id'])
            if body['content']['model_id'] != latest['content']['model_id']:
                raise DomainError(
                    'invalid_request',
                    422,
                    fields=[issue(['content', 'model_id'], 'A calculation keeps its model.')],
                )
            self._public_design(body['content'], latest)
            self._check_content(db, actor, sid, body['content'])
            return self._insert(db, actor, sid, cid, body['content'], latest)

        return self.store.command(
            actor,
            sid,
            'calculation_version',
            body['command_id'],
            dict(body, calculation_id=cid),
            operation,
            attribute=_version_written,
        )

    def insert_generated(self, db, actor, sid, cid, content, expected_version_id):
        """Save a version a sampling operation generated, in the caller's write transaction:
        the first version of a new calculation ``cid`` when ``expected_version_id`` is null,
        otherwise the next version after exactly that latest version."""
        validate_calculation('CalculationContentRead4', content)
        latest = None
        if expected_version_id is not None:
            latest = self.latest(db, sid, cid)
            self.store.cas(latest['calculation_version_id'], expected_version_id)
            if content['model_id'] != latest['content']['model_id']:
                raise DomainError(
                    'invalid_request',
                    422,
                    fields=[issue(['content', 'model_id'], 'A calculation keeps its model.')],
                )
        self._check_content(db, actor, sid, content)
        if latest is None:
            db.execute('INSERT INTO calculations VALUES(?,?)', (cid, sid))
        return self._insert(db, actor, sid, cid, content, latest)

    # Reference marks -----------------------------------------------------------------

    def marks(self, actor, sid, *, model_id=None):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            rows = db.execute(
                'SELECT configuration_revision_id,payload FROM reference_marks '
                'WHERE study_id=?',
                (sid,),
            ).fetchall()
        items = []
        for row in rows:
            try:
                mark = json.loads(row['payload'])
                validate_calculation('ReferenceMark1', mark, retained=True)
                if mark['configuration_revision_id'] != row['configuration_revision_id']:
                    raise ValueError('Reference mark identity mismatch')
            except (ValueError, TypeError) as exc:
                raise DomainError('corrupt_retained_record', 409) from exc
            if model_id is None or mark['model_id'] == model_id:
                items.append(mark)
        items.sort(key=lambda mark: (mark['marked_at'], mark['configuration_revision_id']))
        return dict(items=items)

    def mark(self, actor, sid, body):
        """Set or clear the reference mark of one configuration version; the
        configuration itself is never read for change, rewritten or pinned."""
        body = deepcopy(body)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
        validate_calculation('ReferenceMarkCommand1', body)
        revision = body['configuration_revision_id']

        def operation(db):
            frozen = _frozen_configuration(db, sid, revision)
            if frozen is None:
                raise DomainError(
                    'invalid_request',
                    422,
                    fields=[
                        issue(
                            ['configuration_revision_id'],
                            'The configuration version must exist in this study.',
                        )
                    ],
                )
            current = db.execute(
                'SELECT payload FROM reference_marks WHERE configuration_revision_id=?',
                (revision,),
            ).fetchone()
            if body['action'] == 'clear':
                if current is not None:
                    db.execute(
                        'DELETE FROM reference_marks WHERE configuration_revision_id=?',
                        (revision,),
                    )
                return dict(configuration_revision_id=revision, mark=None)
            if current is not None:
                return dict(
                    configuration_revision_id=revision, mark=json.loads(current['payload'])
                )
            if (
                db.execute(
                    'SELECT COUNT(*) FROM reference_marks WHERE study_id=?', (sid,)
                ).fetchone()[0]
                >= MAX_MEMBERS
            ):
                raise DomainError('limit_exceeded', 413)
            configuration = frozen['configuration']
            mark = dict(
                configuration_revision_id=revision,
                configuration_id=configuration['configuration_id'],
                model_id=configuration['model_id'],
                model_revision_id=configuration['model_revision_id'],
                marked_by=actor,
                marked_at=_now(),
            )
            validate_calculation('ReferenceMark1', mark, retained=True)
            db.execute(
                'INSERT INTO reference_marks VALUES(?,?,?)',
                (revision, sid, canonical(mark).decode()),
            )
            return dict(configuration_revision_id=revision, mark=mark)

        return self.store.command(
            actor,
            sid,
            'reference_mark',
            body['command_id'],
            body,
            operation,
            attribute=lambda state: [
                ('reference_mark', state['configuration_revision_id'], None)
            ],
        )


# Compatibility import for retained wire consumers; there is one owner and writer.
Calculations = Analyses
