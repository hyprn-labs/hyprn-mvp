"""Conclusion: the study answer (ADR-0008, ADR-0010; tooling spec section 4.8). The study answer
owner (``study_answer``) keeps one draft and immutable, numbered versions per study; each version
pins a saved brief version. These tools read the answer, change its draft section by section and
save a version through the public API. The outcome is always stated by the author: finished runs,
met criteria and evidence notes never create or decide an answer."""

from copy import deepcopy

from ...contracts import uid
from ..projections import (
    cap,
    command_id,
    label,
    missing,
    quantity,
    read,
    ref,
    report,
    send,
    study_path,
    tool_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolError, ToolSpec

STATE = ('GET', '/api/1/studies/{study_id}/answer')
VERSION = ('GET', '/api/1/studies/{study_id}/answer/versions/{version_id}')
SAVE_DRAFT = ('POST', '/api/1/studies/{study_id}/answer/draft')
SAVE_VERSION = ('POST', '/api/1/studies/{study_id}/answer/versions')
SECTIONS = (
    'brief_version_id',
    'alternative_mappings',
    'comparison',
    'justifications',
    'interpretation',
    'outcome',
    'decisive_uncertainties',
    'next_analysis',
    'exploration_basis',
    'completion',
    'scientific_review',
)
ANSWER_PRIORITIES = [
    ('justifications', 'justifications', 'get_study_answer'),
    ('comparison', 'table cells', 'get_study_answer'),
    ('interpretation', 'interpretation', 'the study answer in HYPRN MVP'),
]
EMPTY_CONTENT = dict(
    schema_version='2',
    brief_version_id=None,
    alternative_mappings=[],
    comparison=[],
    justifications=[],
    interpretation=dict(interpretation=''),
    outcome=None,
    decisive_uncertainties=[],
    next_analysis=dict(statement='', resolves=''),
    exploration_basis=None,
)


def _current(content):
    value = deepcopy(content)
    if value['schema_version'] == '1':
        old = value['interpretation']
        value['schema_version'] = '2'
        for cell in value['comparison']:
            cell['output_name'] = None
        value['interpretation'] = dict(interpretation='\n\n'.join(
            old[k] for k in ('observations', 'interpretation', 'qualifications') if old[k]
        ))
        value['next_analysis']['statement'] = '\n\n'.join(filter(None, [
            value['next_analysis']['statement'], *[d['text'] for d in old['open_deliverables']],
        ]))
    return value


REVIEW_ASPECTS = ('brief_fidelity', 'source_basis', 'physical_validity', 'sensitivity')


def _publication(content):
    value = _current(content)
    if value['schema_version'] != '3':
        value.update(schema_version='3', completion=dict(state='interim', deliverables=[]),
                     scientific_review={key: dict(state='unassessed', explanation='')
                                        for key in REVIEW_ASPECTS})
    return value


def version_label(version):
    number = version['version_number']
    return label(
        'answer_version',
        version['answer_version_id'],
        'Answer version ' + str(number),
        number=number,
    )


def _alternative(alternative_id):
    return ref('alternative', alternative_id, None, missing='call_get_study_brief')


def _calculation(version_id):
    return ref('calculation_version', version_id, None, missing='not_in_this_read')


def _run(run_id):
    return ref('run', run_id, None, missing='call_get_run_results')


# The calculation owner's evaluation words; anything else is reported as unknown, never echoed.
OUTCOMES = frozenset({'met', 'not_met', 'measured', 'unresolved'})
REASONS = frozenset(
    {
        'threshold_comparison',
        'measured',
        'criterion_not_bound',
        'run_not_recorded',
        'retained_record_invalid',
        'convergence_unresolved',
        'required_output_unavailable',
        'invalid_criterion_or_units',
    }
)


def _evaluation(evaluation):
    """The cited run's criterion evaluation as the calculation reported it when saved: the
    outcome word with its reason and, when measured, the value with its unit."""
    if evaluation is None:
        return missing('not_evaluated')
    return dict(
        outcome=evaluation['outcome'] if evaluation['outcome'] in OUTCOMES else 'unknown',
        reason=evaluation['reason'] if evaluation['reason'] in REASONS else 'unknown',
        **quantity(
            None,
            evaluation['value'],
            evaluation['units'],
            unavailable=None if evaluation['value'] is not None else 'not_computed',
        ),
    )


def _cited(item):
    if item['kind'] == 'evidence_version':
        return ref(
            'evidence_version', item['evidence_version_id'], None, missing='call_read_evidence'
        )
    if item['kind'] == 'run':
        return dict(
            _run(item['run_id']), calculation_version=_calculation(item['calculation_version_id'])
        )
    return _calculation(item['calculation_version_id'])


def _price_basis(basis):
    """Only exact retained monetary fields; cost descriptions remain untrusted author text."""
    return {
        'quantity': {'instance_id': basis['instance_id'], 'port_id': basis['port_id']},
        'catalogue_expression': basis['catalogue_expression'],
        'price_year': basis['price_year'],
        'economic_basis': untrusted('economic basis', text=basis['economic_basis']),
        'model_version': ref('model_version', basis['model_revision_id'], None,
                             missing='call_get_model'),
        'model_digest': basis['model_digest'],
        'explanation_version': ref('model_explanation_version', basis['explanation_version_id'],
                                   None, missing='call_get_model_explanation'),
        'explanation_digest': basis['explanation_digest'],
        'evidence_links': [dict(evidence_version_id=link['evidence_version_id'],
                                relation=link['relation']) for link in basis['evidence_links']],
    }


def content_projection(content):
    """The answer content: cited ids apart from the authors' texts (untrusted)."""
    content = _current(content)
    outcome, interpretation = content['outcome'], content['interpretation']
    if outcome is None:
        stated = missing('no_outcome_stated')
    else:
        stated = {'outcome_kind': outcome['kind']}
        if 'alternative_id' in outcome:
            stated['alternative'] = _alternative(outcome['alternative_id'])
        if 'basis' in outcome:
            stated['basis'] = outcome['basis']
        stated['reason'] = untrusted('outcome reason', text=outcome['reason'])
    basis = content['exploration_basis']
    return {
        'completion': (
            dict(state=content['completion']['state'], deliverables=[
                dict(deliverable_id=d['deliverable_id'], state=d['state'],
                     explanation=untrusted('deliverable assessment', text=d['explanation']))
                for d in content['completion']['deliverables']
            ]) if content['schema_version'] == '3' else missing('completion_not_assessed')
        ),
        'scientific_review': {
            key: dict(state=item['state'],
                      explanation=untrusted('scientific review', text=item['explanation']))
            for key, item in content.get('scientific_review', {}).items()
            if key in REVIEW_ASPECTS
        },
        'brief_version': ref(
            'brief_version', content['brief_version_id'], None, missing='call_get_study_brief'
        )
        if content['brief_version_id']
        else missing('no_brief_version'),
        'alternative_mappings': [
            {
                'alternative': _alternative(m['alternative_id']),
                'calculation_versions': [_calculation(v) for v in m['calculation_version_ids']],
            }
            for m in content['alternative_mappings']
        ],
        'outcome': stated,
        'decisive_uncertainties': [
            dict(
                label(
                    'decisive_uncertainty', u['uncertainty_id'], 'Decisive uncertainty ' + str(n)
                ),
                text=untrusted(
                    'decisive uncertainty',
                    text={k: u[k] for k in ('statement', 'stated_range', 'effect')},
                ),
            )
            for n, u in enumerate(content['decisive_uncertainties'], 1)
        ],
        'next_analysis': untrusted(
            'next analysis',
            text={k: content['next_analysis'][k] for k in ('statement', 'resolves')},
        ),
        'exploration_basis': missing('not_chosen')
        if basis is None
        else {
            'calculation_version': _calculation(basis['calculation_version_id']),
            'estimate': missing('no_estimate')
            if basis['estimate_id'] is None
            else ref('estimate', basis['estimate_id'], None, missing='not_in_this_read'),
            'shown_outputs': [
                {
                    'instance_id': o['instance_id'],
                    'port_id': o['port_id'],
                    'name': missing('call_get_model'),
                }
                for o in basis['shown_outputs']
            ],
        },
        'comparison': [
            {
                'alternative': _alternative(c['alternative_id']),
                'criterion': ref(
                    'criterion', c['criterion_id'], None, missing='call_get_study_brief'
                ),
                'calculation_version': _calculation(c['calculation_version_id']),
                'run': _run(c['run_id']),
                'evaluation': _evaluation(c['evaluation']),
                **({'monetary_basis': _price_basis(c['monetary_basis'])}
                   if content['schema_version'] == '3' and c.get('monetary_basis') else {}),
                'note': untrusted('table note', text=c['note']),
            }
            for c in content['comparison']
        ],
        'justifications': [
            dict(
                label('justification', j['justification_id'], 'Justification ' + str(n)),
                cites=_cited(j),
                relation=j['relation'],
                reason=untrusted('justification reason', text=j['reason']),
            )
            for n, j in enumerate(content['justifications'], 1)
        ],
        'interpretation': untrusted(
            'interpretation',
            text={
                k: interpretation[k] for k in ('interpretation',)
            },
        ),

    }


async def get_study_answer(arguments, ctx):
    """The answer draft (with its revision_token), the latest saved version or one exact one."""
    version_id = arguments.get('answer_version_id')
    which = arguments.get('which', 'draft')
    if version_id is not None:
        version = (
            await read(
                ctx,
                study_path(ctx, 'answer', 'versions', version_id),
                next_step='Call get_study_answer without answer_version_id first.',
            )
        )['data']
        projection = {'which': 'answer_version_id'}
    else:
        state = (await read(ctx, study_path(ctx, 'answer')))['data']
        latest = state.get('latest_version')
        projection = {'which': which}
        if which == 'draft':
            draft = state.get('draft')
            projection['latest_version'] = (
                version_label(latest) if latest else missing('no_saved_version')
            )
            if draft is None:
                projection['draft'] = missing('no_draft')
                projection['revision_token'] = None
                return projection
            projection['revision_token'] = draft['revision']
            projection['updated_at'] = draft['updated_at']
            projection.update(content_projection(draft['content']))
            return cap(projection, ANSWER_PRIORITIES)
        if latest is None:
            projection['answer_version'] = missing('no_saved_version')
            return projection
        version = latest
    projection['answer_version'] = dict(version_label(version), created_at=version['created_at'])
    projection.update(content_projection(version['content']))
    return cap(projection, ANSWER_PRIORITIES)


GET_STUDY_ANSWER = ToolSpec(
    name='get_study_answer',
    title='Read the study answer',
    description=(
        'Returns the study answer: the brief version it answers, each alternative with the '
        'analysis versions that back it, the alternatives x criteria table (each cell cites '
        "one run of an analysis version and carries that run's criterion evaluation: met, "
        'not_met, measured with its value and unit, or unresolved with its reason), the '
        'justifications (cited analysis versions, runs and evidence versions with their '
        'relation and reason), the interpretation, the outcome, the decisive uncertainties, '
        'the next analysis and the answer exploration basis. which: "draft" (default) reads '
        'the working draft and returns its revision_token (null when there is no draft yet); '
        '"latest_version" reads the latest saved version. answer_version_id instead reads that '
        "exact saved version, which never changes. The text is the authors', inside "
        'untrusted_content blocks. Guidance: get_playbook("conclusion").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'which': {
                'type': 'string',
                'enum': ['draft', 'latest_version'],
                'description': 'Which answer to read (default "draft").',
            },
            'answer_version_id': uuid_schema('An exact saved answer version to read instead.'),
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('study_answer',),
    outcome='none',
    activity_label='Read: study answer',
    handler=get_study_answer,
    api_operations=(STATE, VERSION),
)

# ---- Writes ------------------------------------------------------------------------------

_UUID = {'type': 'string', 'format': 'uuid', 'minLength': 36, 'maxLength': 36}
_TEXT = {'type': 'string', 'maxLength': 4096}
_STATEMENT = {'type': 'string', 'minLength': 1, 'maxLength': 4096}
_RELATION = {'type': 'string', 'enum': ['supports', 'challenges', 'context']}


def _items(maximum, required, properties, description):
    return {
        'type': 'array',
        'maxItems': maximum,
        'items': {
            'type': 'object',
            'additionalProperties': False,
            'required': list(required),
            'properties': properties,
        },
        'description': description,
    }


CONTENT_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'minProperties': 1,
    'description': (
        'The sections to change. A section given replaces that section whole; a section left '
        'out stays as it is.'
    ),
    'properties': {
        'brief_version_id': {
            'type': ['string', 'null'],
            'maxLength': 36,
            'description': (
                'The saved brief version the answer answers (from list_study_brief_versions).'
            ),
        },
        'alternative_mappings': _items(
            32,
            ('alternative_id', 'calculation_version_ids'),
            {
                'alternative_id': _UUID,
                'calculation_version_ids': {
                    'type': 'array',
                    'maxItems': 64,
                    'uniqueItems': True,
                    'items': _UUID,
                },
            },
            'Each brief alternative with the analysis versions that back it (possibly none, '
            'possibly across models). A version needs every alternative listed.',
        ),
        'comparison': _items(
            1024,
            ('alternative_id', 'criterion_id', 'calculation_version_id', 'run_id'),
            {
                'alternative_id': _UUID,
                'criterion_id': _UUID,
                'calculation_version_id': _UUID,
                'run_id': _UUID,
                'note': _TEXT,
            },
            'Table cells: one run of an analysis version mapped to the alternative, cited for '
            'one brief criterion. The evaluation is filled from the calculation, never given.',
        ),
        'justifications': _items(
            256,
            ('kind', 'relation', 'reason'),
            {
                'justification_id': _UUID,
                'kind': {
                    'type': 'string',
                    'enum': ['calculation_version', 'run', 'evidence_version'],
                },
                'calculation_version_id': _UUID,
                'run_id': _UUID,
                'evidence_version_id': _UUID,
                'relation': _RELATION,
                'reason': _STATEMENT,
            },
            'Cited records with their relation: a calculation_version (calculation_version_id), a '
            'run (calculation_version_id and run_id) or an evidence_version (evidence_version_id).',
        ),
        'interpretation': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'interpretation': {'type': 'string', 'maxLength': 12292}},
            'description': 'Concise interpretation including necessary qualifications and limits.',
        },
        'outcome': {
            'type': ['object', 'null'],
            'additionalProperties': False,
            'required': ['kind', 'reason'],
            'properties': {
                'kind': {'type': 'string', 'enum': ['recommended', 'no_go', 'no_recommendation']},
                'alternative_id': _UUID,
                'basis': {
                    'type': 'string',
                    'enum': ['insufficient_evidence', 'contested_evidence'],
                },
                'reason': _STATEMENT,
            },
            'description': (
                'recommended (alternative_id): the alternative to pursue (go when there is one); '
                'no_go (alternative_id): only for a study with one alternative; '
                'no_recommendation (basis): the evidence is insufficient or contested.'
            ),
        },
        'decisive_uncertainties': _items(
            64,
            ('statement',),
            {
                'uncertainty_id': _UUID,
                'statement': _STATEMENT,
                'stated_range': _TEXT,
                'effect': _TEXT,
            },
            'Assumptions, inputs or unresolved criteria that, within the stated range, would '
            'change the recommended alternative.',
        ),
        'next_analysis': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'statement': _TEXT, 'resolves': _TEXT},
            'description': (
                'The most valuable analysis before committing and what it would resolve.'
            ),
        },
        'exploration_basis': {
            'type': ['object', 'null'],
            'additionalProperties': False,
            'required': ['calculation_version_id'],
            'properties': {
                'calculation_version_id': _UUID,
                'estimate_id': {
                    **_UUID,
                    'type': ['string', 'null'],
                    'description': 'The exact checked estimate from prepare_answer_exploration.',
                },
                'shown_outputs': {
                    'type': 'array',
                    'maxItems': 16,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'required': ['instance_id', 'port_id'],
                        'properties': {'instance_id': _UUID, 'port_id': _UUID},
                    },
                },
            },
            'description': (
                'The analysis version the answer exploration shows and the '
                'bound outputs it shows.'
            ),
        },
    },
}
CONTENT_SCHEMA['properties']['completion'] = dict(
    type='object', additionalProperties=False, required=['state', 'deliverables'],
    properties=dict(
        state=dict(enum=['interim', 'complete']),
        deliverables=_items(
            32, ('deliverable_id', 'state', 'explanation'),
            dict(deliverable_id=_UUID, state=dict(enum=['fulfilled', 'pending', 'unavailable']),
                 explanation=_STATEMENT),
            'Assess each exact requested brief deliverable. Pending work remains interim.',
        ),
    ),
)
CONTENT_SCHEMA['properties']['scientific_review'] = dict(
    type='object', additionalProperties=False, required=list(REVIEW_ASPECTS),
    properties={key: dict(type='object', additionalProperties=False,
                         required=['state', 'explanation'], properties=dict(
                             state=dict(enum=['checked', 'limited', 'unassessed']),
                             explanation=_TEXT)) for key in REVIEW_ASPECTS},
    description='Separate brief/inequality fidelity, inspected sources, physical adequacy and '
                'sensitivity. Explain checks and limits; '
                'surrogate accuracy is not physics validation.',
)
ITEM_IDS = {
    'justifications': 'justification_id',
    'decisive_uncertainties': 'uncertainty_id',
}


def _with_id(item, key):
    return item if key in item else dict(item, **{key: uid()})


def _merged(current, changes):
    """The current draft content with the given sections replaced. New items get an id here,
    so an agent never invents an identity; optional texts default to empty (never a number)
    and table evaluations are left for the application to fill."""
    content = _publication(current)
    for key, value in changes.items():
        if key in ITEM_IDS:
            value = [_with_id(item, ITEM_IDS[key]) for item in value]
        if key == 'decisive_uncertainties':
            value = [dict({'stated_range': '', 'effect': ''}, **item) for item in value]
        if key == 'comparison':
            value = [dict({'note': ''}, **item, evaluation=None, output_name=None) for item in value]
        if key == 'interpretation':
            value = dict(EMPTY_CONTENT['interpretation'], **value)
        if key == 'next_analysis':
            value = dict(EMPTY_CONTENT['next_analysis'], **value)
        if key == 'exploration_basis' and value is not None:
            value = dict({'shown_outputs': [], 'estimate_id': None}, **value)
        content[key] = value
    return content


async def update_study_answer(arguments, ctx):
    """Change the answer draft section by section under the draft revision the agent read."""
    expected = arguments['expected_revision']
    state = (await read(ctx, study_path(ctx, 'answer')))['data']
    draft = state.get('draft')
    if (draft['revision'] if draft else None) != expected:
        raise ToolError(
            'conflict',
            'The study answer draft changed since you read it; nothing was written.',
            fields=({'path': 'expected_revision', 'problem': 'is not the current draft revision'},),
            next_step='Call get_study_answer, apply your change to what it returns and pass its '
            'revision_token as expected_revision.',
        )
    content = _merged(draft['content'] if draft else EMPTY_CONTENT, arguments['content'])
    body = {'command_id': command_id(ctx), 'expected_revision': expected, 'content': content}
    saved = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'answer', 'draft'),
            body,
            tool='update_study_answer',
            conflict_step='Call get_study_answer again and reapply your change.',
        )
    )['data']
    report(ctx, 'answer_draft', saved['study_id'], version_id=saved['revision'])
    projection = {
        'revision_token': saved['revision'],
        'updated_at': saved['updated_at'],
        'changed_sections': sorted(arguments['content']),
    }
    projection.update(content_projection(saved['content']))
    return cap(projection, ANSWER_PRIORITIES)


UPDATE_STUDY_ANSWER = ToolSpec(
    name='update_study_answer',
    title='Change the study answer draft',
    description=(
        'Changes the study answer draft. expected_revision: the revision_token of your last '
        'get_study_answer (null when the study has no answer draft yet). content: only the '
        'sections to change (brief_version_id, alternative_mappings, comparison, '
        'justifications, interpretation, outcome, decisive_uncertainties, next_analysis, '
        'exploration_basis); a section given replaces that section whole (keep the ids of '
        'items you keep, omit the id of a new item and one is assigned), a section left out '
        "stays as it is. Cite only records of this study you have read; a table cell's "
        'evaluation is filled from the cited run, never written by you. State the outcome '
        'yourself; never infer it from finished runs or met criteria, and never invent '
        'confidence numbers. Returns the new revision_token and the whole draft. Guidance: '
        'get_playbook("conclusion").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['expected_revision', 'content'],
        'properties': {
            'expected_revision': {
                'type': ['string', 'null'],
                'maxLength': 36,
                'description': 'The revision_token of the draft you read, or null for none.',
            },
            'content': CONTENT_SCHEMA,
        },
    },
    effect='draft',
    stage='authoring',
    surfaces=SURFACES,
    owners=('study_answer',),
    outcome='receipt:answer_draft',
    activity_label='Changed: study answer draft',
    handler=update_study_answer,
    api_operations=(STATE, SAVE_DRAFT),
    attribution_kind='answer_draft',
)


async def save_study_answer_version(arguments, ctx):
    """Save the current draft as the next numbered version, with its cells re-read."""
    body = {'command_id': command_id(ctx), 'expected_revision': arguments['expected_revision']}
    saved = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'answer', 'versions'),
            body,
            tool='save_study_answer_version',
            conflict_step='Call get_study_answer, check the draft and save again with its '
            'revision_token.',
            field_map=lambda pointer: tool_path(str(pointer).removeprefix('/content'), 'draft'),
        )
    )['data']
    version, draft = saved['version'], saved['draft']
    report(
        ctx,
        'answer_version',
        version['study_id'],
        version_id=version['answer_version_id'],
        number=version['version_number'],
    )
    return {
        'answer_version': dict(version_label(version), created_at=version['created_at']),
        'draft': {'revision_token': draft['revision'], 'based_on': version_label(version)},
    }


SAVE_STUDY_ANSWER_VERSION = ToolSpec(
    name='save_study_answer_version',
    title='Save a study answer version',
    description=(
        'Saves the current study answer draft as the next numbered version, which never '
        'changes afterwards; table cells are re-read from their cited runs. A version needs '
        'the brief version it answers, every alternative of that brief mapped (even to no '
        'calculation) and a stated outcome. expected_revision: the revision_token of the '
        'draft you checked. Returns the version number and id and the continuing draft. '
        'Guidance: get_playbook("conclusion").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['expected_revision'],
        'properties': {
            'expected_revision': {
                'type': 'string',
                'minLength': 36,
                'maxLength': 36,
                'description': 'The revision_token of the draft to save.',
            }
        },
    },
    effect='record',
    stage='authoring',
    surfaces=SURFACES,
    owners=('study_answer',),
    outcome='receipt:answer_version',
    activity_label='Saved: study answer version',
    handler=save_study_answer_version,
    api_operations=(SAVE_VERSION,),
    attribution_kind='answer_version',
)

TOOLS = (GET_STUDY_ANSWER, UPDATE_STUDY_ANSWER, SAVE_STUDY_ANSWER_VERSION)
