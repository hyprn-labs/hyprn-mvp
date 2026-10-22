"""Read tools: compact, honest projections of the owners' stored records.

Each read tool calls only its declared public API operations, recomputes nothing and keeps
nothing between calls. Its projection pairs every id with a name, gives every quantity its
unit, never shows an unavailable output as a number, keeps the outcome facets separate, wraps
every text written by others in ``untrusted_content``, stays within 24 KB (naming what it
dropped) and pages lists through opaque cursors bound to the tool. ``get_run_status`` reads
the owner's light run status exactly once per call.

Two tiers (ND-14): golden projections over recorded public API reads of one synthetic study
(``fixtures/recorded_api.json``, every body validated against the contract when served), and
the same tools through the real application, middleware and agent route allowlist on a fresh
synthetic store with a recorded-response modeling transport. No modeling service, runtime or
live store.
"""

import asyncio
import base64
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.agent_tools import projections
from hyprn_mvp_app.agent_tools.api_client import ApiClient, ApiResponse
from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, REGISTRY
from hyprn_mvp_app.agent_tools.spec import ToolContext, ToolError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIXTURES = HERE / 'fixtures'
RECORDED = json.loads((FIXTURES / 'recorded_api.json').read_text(encoding='utf-8'))
GOLDEN_PATH = FIXTURES / 'golden_projections.json'
CONTRACT = json.loads((REPO / 'contracts/hyprn-mvp.openapi.yaml').read_text(encoding='utf-8'))
NOW = datetime(2026, 10, 14, 8, 0, 30, tzinfo=timezone.utc)
READER = frozenset({'read', 'outside_study'})
REQUEST_ID = '00000000-0000-4000-8000-0000000000aa'
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

S = RECORDED['study_id']
M1 = RECORDED['models'][0]['model_id']
R1, R2 = (r['model_revision_id'] for r in RECORDED['model_revisions'][M1])
CV1, CV2 = (c['configuration']['configuration_revision_id'] for c in RECORDED['configurations'])
RUN1, RUN2, RUN3 = (r['run_id'] for r in RECORDED['runs'])
E1V2, E2V1, E3V1 = (e['evidence_version_id'] for e in RECORDED['evidence_heads'])
ANSWER1 = min(RECORDED['study_answer_versions'])
CALC = RECORDED['calculations'][0]['calculation_id']
CALC1, CALC2 = sorted(RECORDED['calculation_versions'])

# Tool and arguments of every golden projection.
CASES = {
    'get_study_overview': ('get_study_overview', {}),
    'get_capabilities': ('get_capabilities', {}),
    'check_execution_readiness': ('check_execution_readiness', {}),
    'get_study_brief_draft': ('get_study_brief', {}),
    'get_study_brief_latest_version': ('get_study_brief', {'which': 'latest_version'}),
    'get_study_brief_version_1_criteria': (
        'get_study_brief',
        {'which': 'version_number', 'version_number': 1, 'sections': ['criteria']},
    ),
    'list_study_brief_versions_first_page': ('list_study_brief_versions', {'limit': 1}),
    'list_models': ('list_models', {}),
    'get_model_draft': ('get_model', {'model_id': M1}),
    'get_model_latest_with_source': (
        'get_model',
        {'model_id': M1, 'which': 'latest', 'include_source_for': ['Range']},
    ),
    'list_model_versions': ('list_model_versions', {'model_id': M1}),
    'get_assumption_evidence_draft': ('get_assumption_evidence', {'model_id': M1}),
    'get_assumption_evidence_version': (
        'get_assumption_evidence',
        {'model_id': M1, 'which': 'version', 'model_version_id': R2},
    ),
    'get_model_explanation_draft': ('get_model_explanation', {'model_id': M1}),
    'get_model_explanation_of_version_2': (
        'get_model_explanation',
        {'model_id': M1, 'model_version_id': R2},
    ),
    'get_model_explanation_of_version_1': (
        'get_model_explanation',
        {'model_id': M1, 'model_version_id': R1},
    ),
    'list_evidence': ('list_evidence', {}),
    'list_evidence_all_versions_of_a_model': (
        'list_evidence',
        {'view': 'all', 'filter': {'model_id': M1}},
    ),
    'read_evidence_first_100_characters': (
        'read_evidence',
        {'evidence_version_id': E2V1, 'max_chars': 100},
    ),
    'read_evidence_without_title': ('read_evidence', {'evidence_version_id': E3V1}),
    'list_configurations': ('list_configurations', {}),
    'get_configuration': ('get_configuration', {'configuration_version_id': CV2}),
    'list_result_sources': ('list_result_sources', {}),
    'list_runs': ('list_runs', {}),
    'get_run_status': ('get_run_status', {'run_ids': [RUN3, RUN1, RUN2]}),
    'get_run_results_recorded': ('get_run_results', {'run_id': RUN1}),
    'get_run_results_failed_with_diagnostics': (
        'get_run_results',
        {'run_id': RUN2, 'include_diagnostics': True},
    ),
    'get_run_results_without_results': ('get_run_results', {'run_id': RUN3}),
    'get_study_answer_draft': ('get_study_answer', {}),
    'get_study_answer_version_1': (
        'get_study_answer',
        {'answer_version_id': ANSWER1},
    ),
    'compare_runs': (
        'compare_runs',
        {'run_ids': [RUN1, RUN2, RUN3], 'outputs': ['Range.range', 'Mass closure.mtow', 'Range.x']},
    ),
    'list_analyses': ('list_analyses', {}),
    'list_calculations_of_another_model_version': (
        'list_analyses',
        {'model_version_id': R1},
    ),
    'get_calculation_latest': ('get_analysis', {'calculation_id': CALC}),
    'get_calculation_version_1': ('get_analysis', {'calculation_version_id': CALC1}),
    'list_calculation_versions_first_page': (
        'list_analysis_versions',
        {'calculation_id': CALC, 'limit': 1},
    ),
    'get_analysis_runs': ('get_analysis_runs', {'calculation_version_id': CALC2}),
    'list_reference_marks': ('list_reference_marks', {}),
}
READ_TOOLS = {
    'get_study_overview',
    'get_capabilities',
    'check_execution_readiness',
    'get_study_brief',
    'list_study_brief_versions',
    'list_models',
    'get_model',
    'list_model_versions',
    'get_assumption_evidence',
    'get_model_explanation',
    'list_evidence',
    'read_evidence',
    'list_configurations',
    'get_configuration',
    'list_result_sources',
    'list_runs',
    'get_run_status',
    'get_run_results',
    'compare_runs',
    'get_study_answer',
    'list_analyses',
    'get_analysis',
    'list_analysis_versions',
    'get_analysis_runs',
    'list_reference_marks',
}


# ---- The recorded API double ------------------------------------------------------------


def _response_validators():
    found = []
    for template, operations in CONTRACT['paths'].items():
        operation = operations.get('get')
        content = (operation or {}).get('responses', {}).get('200', {}).get('content', {})
        if 'application/json' not in content:
            continue
        schema = dict(content['application/json']['schema'], components=CONTRACT['components'])
        pattern = re.compile('/api/1' + re.sub(r'\{[a-z_]+\}', '[^/]+', template))
        found.append((pattern, Draft202012Validator(schema, format_checker=FormatChecker())))
    return found


VALIDATORS = _response_validators()


def contract_problems(path, envelope):
    matches = [v for pattern, v in VALIDATORS if pattern.fullmatch(path)]
    assert len(matches) == 1, path
    return sorted(e.message[:200] for e in matches[0].iter_errors(envelope))


class Refused(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code


def _limit(pairs, default=100):
    text = dict(pairs).get('limit', str(default))
    if not text.isdecimal() or not 1 <= int(text) <= 100:
        raise Refused(400, 'invalid_request')
    return int(text)


def _page(items, key, pairs, default=100):
    """The edge's id-cursor page: the items after the cursor id, ``limit`` of them."""
    limit, cursor = _limit(pairs, default), dict(pairs).get('cursor')
    if cursor is not None:
        ids = [key(item) for item in items]
        if cursor not in ids:
            raise Refused(404, 'resource_not_found')
        items = items[ids.index(cursor) + 1 :]
    selected = items[:limit]
    return selected, (key(selected[-1]) if len(items) > limit else None)


def _offset_page(items, pairs, default=100):
    """An owner-opaque cursor (the double encodes an offset)."""
    limit, cursor = _limit(pairs, default), dict(pairs).get('cursor')
    start = 0
    if cursor is not None:
        try:
            start = int(base64.urlsafe_b64decode(cursor.encode()).decode())
        except ValueError:
            raise Refused(400, 'invalid_request') from None
    selected = items[start : start + limit]
    end = start + len(selected)
    return selected, (
        base64.urlsafe_b64encode(str(end).encode()).decode() if end < len(items) else None
    )


class RecordedApi:
    """Serves recorded public API reads of one study with the API client's interface, records
    every request and validates every body it serves against the public contract."""

    def __init__(self, data=None, *, validate=True):
        self.data = copy.deepcopy(RECORDED if data is None else data)
        self.validate = validate
        self.calls = []
        self.base = '/api/1/studies/' + self.data['study_id']

    async def request(self, session, method, path, json_body=None, params=None):
        pairs = list(params.items()) if isinstance(params, dict) else list(params or ())
        pairs = [(str(k), str(v)) for k, v in pairs]
        self.calls.append((method, path, tuple(pairs)))
        assert method == 'GET' and json_body is None
        try:
            data, extra = self.serve(path, pairs)
        except Refused as refused:
            body = {
                'error': {'code': refused.code, 'message': refused.code, 'request_id': REQUEST_ID}
            }
            return ApiResponse(refused.status, body, REQUEST_ID)
        from hyprn_mvp_app.contracts import public_record_view

        if '/run-status' in path:
            data = [{**item, 'facets': {'execution': item['facets']['execution']}} for item in data]
        if '/result-sources' in path:
            data = {
                **data,
                'items': [
                    {
                        **item,
                        'outcomes': {
                            k: v for k, v in item['outcomes'].items() if k != 'applicability'
                        },
                    }
                    for item in data['items']
                ],
            }
        if self.validate:
            data = public_record_view(data)
        body = dict(schema_version='1', request_id=REQUEST_ID, data=data, **extra)
        if self.validate:
            assert contract_problems(path, body) == [], path
        return ApiResponse(200, body, REQUEST_ID)

    def serve(self, path, pairs):
        d = self.data
        if path == '/api/1/capabilities':
            return d['capabilities'], {}
        if not path.startswith(self.base):
            raise Refused(404, 'resource_not_found')
        parts = path[len(self.base) :].strip('/').split('/') if path != self.base else []
        query = dict(pairs)
        if parts == []:
            return d['study'], {}
        head = parts[0]
        if parts == ['brief']:
            return d['brief'], {}
        if parts == ['brief', 'versions']:
            return self.brief_versions(pairs), {}
        if parts == ['answer']:
            return d['study_answer'], {}
        if parts[:2] == ['answer', 'versions'] and len(parts) == 3:
            return self.lookup(d['study_answer_versions'], parts[2]), {}
        if parts == ['unit-catalog']:
            return d['unit_catalog'], {}
        if parts == ['execution-readiness']:
            return d['readiness'], {}
        if parts == ['models']:
            items, after = _page(d['models'], lambda m: m['model_id'], pairs)
            return items, {'next_cursor': after}
        if head == 'models':
            return self.model(parts[1:], pairs)
        if parts == ['evidence']:
            return self.evidence(pairs)
        if head == 'evidence' and (len(parts) == 2 or parts[2:] == ['source-inspection']):
            found = [e for e in d['evidence_versions'] if e['evidence_version_id'] == parts[1]]
            if not found:
                raise Refused(404, 'resource_not_found')
            if len(parts) == 3:
                return dict(schema_version='1', evidence_version_id=parts[1],
                            basis='author_supplied', retrieval=None), {}
            return found[0], {}
        if parts == ['configurations']:
            key = lambda c: c['configuration']['configuration_revision_id']  # noqa: E731
            items, after = _page(d['configurations'], key, pairs)
            return items, {'next_cursor': after}
        if head == 'configurations' and len(parts) == 2:
            found = [
                c
                for c in d['configurations']
                if c['configuration']['configuration_revision_id'] == parts[1]
            ]
            if not found:
                raise Refused(404, 'resource_not_found')
            return found[0], {}
        if head in ('analyses', 'analysis-versions'):
            legacy = 'calculations' if head == 'analyses' else 'calculation-versions'
            return self.calculations([legacy, *parts[1:]], pairs), {}
        if head in ('calculations', 'calculation-versions', 'reference-marks'):
            return self.calculations(parts, pairs), {}
        if parts == ['configuration-summaries']:
            query = dict(pairs)
            items = [
                {
                    'configuration_revision_id': c['configuration']['configuration_revision_id'],
                    'configuration_id': c['configuration']['configuration_id'],
                    'model_id': c['configuration']['model_id'],
                    'model_revision_id': c['configuration']['model_revision_id'],
                    'name': c['configuration']['name'],
                    'input_count': len(c['configuration']['inputs']),
                }
                for c in d['configurations']
                if query.get('model_revision_id') in (None, c['configuration']['model_revision_id'])
            ]
            selected, after = _page(items, lambda c: c['configuration_revision_id'], pairs, 50)
            return selected, {'next_cursor': after}
        if parts[:2] == ['brief', 'versions'] and len(parts) == 3:
            found = [v for v in d['brief_versions'] if v['brief_version_id'] == parts[2]]
            if not found:
                raise Refused(404, 'resource_not_found')
            return found[0], {}
        if parts == ['result-sources']:
            items, after = _offset_page(d['result_sources'], pairs, 25)
            return {'items': items, 'next_cursor': after}, {}
        if parts == ['runs']:
            items, after = _page(d['runs'], lambda r: r['run_id'], pairs)
            return items, {'next_cursor': after}
        if head == 'runs' and len(parts) == 2:
            return self.lookup(d['run_details'], parts[1]), {}
        if parts == ['run-status']:
            ids = [v for k, v in pairs if k == 'run_id']
            if set(query) != {'run_id'} or not 1 <= len(ids) <= 20 or len(set(ids)) != len(ids):
                raise Refused(400, 'invalid_request')
            return [self.lookup(d['run_status'], i) for i in ids], {}
        raise Refused(404, 'resource_not_found')

    def calculations(self, parts, pairs):
        """The calculations owner's reads: positional integer cursors, newest versions first."""
        d, query = self.data, dict(pairs)

        def position(key, default=0):
            text = query.get(key)
            if text is not None and not text.isdecimal():
                raise Refused(400, 'invalid_request')
            return default if text is None else int(text)

        limit = _limit(pairs, 20)
        if parts == ['reference-marks']:
            model = query.get('model_id')
            return {'items': [m for m in d['reference_marks'] if model in (None, m['model_id'])]}
        if parts == ['calculations']:
            items = [
                c
                for c in d['calculations']
                if query.get('model_revision_id')
                in (None, c['latest_version']['content']['model_revision_id'])
            ]
            start = position('after')
            selected = items[start : start + limit]
            more = start + limit < len(items)
            return {'items': selected, 'next_cursor': start + limit if more else None}
        if parts[0] == 'calculations':
            family = [c for c in d['calculations'] if c['calculation_id'] == parts[1]]
            if not family:
                raise Refused(404, 'resource_not_found')
            if len(parts) == 2:
                return family[0]
            versions = sorted(
                (
                    v
                    for v in d['calculation_versions'].values()
                    if isinstance(v, dict) and v['calculation_id'] == parts[1]
                ),
                key=lambda v: -v['version_number'],
            )
            before = position('before', 1 << 53)
            items = [v for v in versions if v['version_number'] < before]
            selected = items[:limit]
            more = len(items) > limit
            after = selected[-1]['version_number'] if more else None
            return {'items': selected, 'next_cursor': after}
        version = self.lookup(d['calculation_versions'], parts[1])
        if len(parts) == 2:
            return version
        items = d['calculation_runs'][parts[1]]
        start = position('after')
        selected = items[start : start + limit]
        more = start + limit < len(items)
        return {
            'calculation_version_id': parts[1],
            'items': selected,
            'next_cursor': start + limit if more else None,
        }

    @staticmethod
    def lookup(table, key):
        if key not in table:
            raise Refused(404, 'resource_not_found')
        return table[key]

    def brief_versions(self, pairs):
        """The owner's page: newest first, the versions numbered below ``before``."""
        query = dict(pairs)
        if set(query) - {'limit', 'before'} or len(query) != len(pairs):
            raise Refused(400, 'invalid_request')
        items, limit = self.data['brief_versions'], _limit(pairs, 20)
        if 'before' in query:
            if not query['before'].isdecimal():
                raise Refused(400, 'invalid_request')
            items = [i for i in items if i['version_number'] < int(query['before'])]
        selected = items[:limit]
        after = selected[-1]['version_number'] if len(items) > limit else None
        return {'items': selected, 'next_cursor': after}

    def model(self, parts, pairs):
        d, model_id = self.data, parts[0]
        draft = self.lookup(d['model_drafts'], model_id)
        if len(parts) == 1:
            return draft, {}
        revisions = d['model_revisions'][model_id]
        if parts[1:] == ['revisions']:
            items, after = _page(revisions, lambda r: r['model_revision_id'], pairs, 50)
            return items, {'next_cursor': after}
        if parts[1] == 'revisions' and len(parts) == 3:
            if parts[2] not in {r['model_revision_id'] for r in revisions}:
                raise Refused(404, 'resource_not_found')
            return d['model_revision'][parts[2]], {}
        if parts[1:] == ['explanation']:
            return d['model_explanations'][model_id]['state'], {}
        if parts[1] == 'revisions' and len(parts) == 4 and parts[3] == 'explanation':
            explanation = d['model_explanations'][model_id]['versions'].get(parts[2])
            return {
                'model_id': model_id,
                'model_revision_id': parts[2],
                'explanation': explanation,
            }, {}
        if parts[1:] == ['assumption-evidence']:
            query = dict(pairs)
            table = d['assumption_evidence'][model_id]
            if query.get('draft_revision') == draft['draft_revision']:
                return table['draft'], {}
            return self.lookup(table, query.get('model_revision_id')), {}
        raise Refused(404, 'resource_not_found')

    def evidence(self, pairs):
        query = dict(pairs)
        view = query.get('view', 'heads')
        records = self.data['evidence_heads' if view == 'heads' else 'evidence_versions']
        for key in ('model_id', 'model_revision_id', 'run_id', 'configuration_revision_id'):
            if key in query:
                records = [
                    r for r in records if (r.get('resource_scope') or {}).get(key) == query[key]
                ]
        items, after = _offset_page(records, pairs, 50)
        return items, {'next_cursor': after}


SESSION = {'study_id': S, 'token': 'session-value', 'csrf_token': 'csrf-value'}


def context(api, effects=READER, session=SESSION):
    return ToolContext(
        surface='claude_managed', stage=LOCAL_STAGE, effects=effects, api=api, session=session
    )


def invoke(api, name, arguments):
    return asyncio.run(REGISTRY.invoke(name, arguments, context(api)))


def refusal(api, name, arguments):
    with pytest.raises(ToolError) as caught:
        invoke(api, name, arguments)
    return caught.value


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(projections, 'utc_now', lambda: NOW)


def run_case(case, data=None, *, validate=True):
    api = RecordedApi(data, validate=validate)
    name, arguments = CASES[case]
    return invoke(api, name, copy.deepcopy(arguments)), api


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


# ---- Golden projections -----------------------------------------------------------------


def test_the_recorded_reads_are_valid_public_api_responses():
    api = RecordedApi()
    for case in CASES:
        name, arguments = CASES[case]
        invoke(api, name, copy.deepcopy(arguments))
    assert len(api.calls) > len(CASES)


def test_every_read_tool_has_a_golden_projection():
    assert {name for name, _ in CASES.values()} == READ_TOOLS
    offered = {t.name for t in REGISTRY.offered('claude_managed', LOCAL_STAGE, READER)}
    # The new preparation lifecycle has public-owner acceptance in its own test module.
    from test_agent_exploration_tools import READ_TOOLS as EXPLORATION_READS
    assert READ_TOOLS | EXPLORATION_READS | {'get_playbook'} == offered


@pytest.mark.parametrize('case', sorted(CASES))
def test_golden_projection_matches_and_stays_within_the_result_cap(case):
    golden = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))
    result, _ = run_case(case)
    assert result == golden[case]
    assert projections.size(result) <= projections.MAX_RESULT_BYTES
    assert 'truncated' not in result


def test_every_request_of_a_read_tool_is_one_of_its_declared_api_operations():
    for case, (name, arguments) in CASES.items():
        result, api = run_case(case)
        declared = [
            re.compile(re.sub(r'\{[a-z_]+\}', '[^/]+', template))
            for method, template in REGISTRY.tool(name).api_operations
        ]
        assert api.calls, case
        for method, path, _ in api.calls:
            assert method == 'GET'
            assert any(p.fullmatch(path) for p in declared), (case, path)


# ---- Tool ownership (ADR-0004) ------------------------------------------------------------

S_ = '/api/1/studies/{study_id}'
# The rows of "Tool ownership (ADR-0004)" for the read tools: tools, API operations (method and
# route template), owners. Effect is read and the stored outcome none for every row.
OWNERSHIP_ROWS = [
    (
        ('get_study_overview',),
        {S_, S_ + '/brief', S_ + '/models', S_ + '/configurations'}
        | {S_ + '/runs', S_ + '/evidence', S_ + '/execution-readiness'},
        {'store', 'brief', 'modeling', 'configuration', 'execution', 'readiness'},
    ),
    (('get_capabilities',), {'/api/1/capabilities', S_ + '/unit-catalog'}, {'api', 'units'}),
    (('check_execution_readiness',), {S_ + '/execution-readiness'}, {'readiness'}),
    (
        ('get_study_brief', 'list_study_brief_versions'),
        {S_ + '/brief', S_ + '/brief/versions'},
        {'brief'},
    ),
    (
        ('get_study_answer',),
        {S_ + '/answer', S_ + '/answer/versions/{version_id}'},
        {'study_answer'},
    ),
    (
        ('list_models', 'get_model', 'list_model_versions', 'get_assumption_evidence'),
        {
            S_ + '/models',
            S_ + '/models/{model_id}',
            S_ + '/models/{model_id}/revisions',
            S_ + '/models/{model_id}/revisions/{revision_id}',
            S_ + '/models/{model_id}/assumption-evidence',
        },
        {'modeling'},
    ),
    (
        ('get_model_explanation',),
        {
            S_ + '/models/{model_id}/explanation',
            S_ + '/models/{model_id}/revisions/{revision_id}/explanation',
        },
        {'explanations'},
    ),
    (
        ('list_evidence', 'read_evidence'),
        {S_ + '/evidence', S_ + '/evidence/{evidence_version_id}',
         S_ + '/evidence/{evidence_version_id}/source-inspection'},
        {'store'},
    ),
    (
        ('list_configurations', 'get_configuration', 'list_result_sources'),
        {S_ + '/configurations', S_ + '/configurations/{revision_id}', S_ + '/result-sources'},
        {'configuration', 'result_bindings'},
    ),
    (
        ('list_runs', 'get_run_results', 'compare_runs'),
        {S_ + '/runs', S_ + '/runs/{run_id}'},
        {'execution', 'history'},
    ),
    (('get_run_status',), {S_ + '/run-status'}, {'execution', 'history'}),
    (
        (
            'list_analyses',
            'get_analysis',
            'list_analysis_versions',
            'get_analysis_runs',
            'list_reference_marks',
        ),
        {
            S_ + '/analyses',
            S_ + '/analyses/{calculation_id}',
            S_ + '/analyses/{calculation_id}/versions',
            S_ + '/analysis-versions/{version_id}',
            S_ + '/analysis-versions/{version_id}/runs',
            S_ + '/reference-marks',
            S_ + '/configuration-summaries',
            S_ + '/brief/versions/{version_id}',
            S_ + '/models/{model_id}/revisions/{revision_id}',
        },
        {'calculations', 'configuration', 'brief', 'modeling', 'history'},
    ),
]


def test_each_read_tool_spec_equals_its_tool_ownership_row():
    covered = set()
    for tools, operations, owners in OWNERSHIP_ROWS:
        specs = [REGISTRY.tool(name) for name in tools]
        for tool in specs:
            assert (tool.effect, tool.outcome, tool.stage, tool.gate) == (
                'read',
                'none',
                'read_only',
                None,
            ), tool.name
            assert {m for m, _ in tool.api_operations} == {'GET'}, tool.name
            assert {t for _, t in tool.api_operations} <= operations, tool.name
            assert set(tool.owners) <= owners and tool.owners, tool.name
            assert tool.annotations['readOnlyHint'] is True
            assert tool.annotations['destructiveHint'] is False
        assert {t for tool in specs for _, t in tool.api_operations} == operations, tools
        assert {o for tool in specs for o in tool.owners} == owners, tools
        covered |= set(tools)
    assert covered == READ_TOOLS
    entry = {name for name, t in ((t.name, t) for t in REGISTRY.tools) if t.client_meta}
    assert entry == {'get_playbook', 'get_study_overview'}


# ---- Honest projections -------------------------------------------------------------------

AUTHORED = {
    'name',
    'title',
    'description',
    'boundary',
    'statement',
    'content',
    'question',
    'scope',
    'limitations',
    'open_questions',
    'purpose',
    'rationale',
    'remaining_work',
    'transformation',
    'label',
    'message',
    'run_name',
    'model_name',
    'instance_name',
    'output_name',
    'case_name',
    'configuration_name',
    'locator',
    'observations',
    'interpretation',
}
FREE_TEXT_KEYS = {'inputs', 'outputs'}  # only where they hold text (an approach step intent)
MARKER = 'QZV'


def seeded(data, marker=MARKER):
    """A copy of the recorded reads in which every text written by people or agents ends with
    ``marker``, and so does every component source."""
    data = copy.deepcopy(data)

    def visit(node):
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if isinstance(value, str) and (
                    key in AUTHORED
                    or key in FREE_TEXT_KEYS
                    or (key == 'reason' and {'criterion_id', 'alternative_id'} & set(node))
                    or (key == 'text' and {'question_id', 'attribution'} & set(node))
                ):
                    node[key] = value + ' ' + marker
                elif key == 'source_refs' and isinstance(value, list):
                    node[key] = [v + ' ' + marker for v in value]
                elif key == 'bytes' and node.get('media_type') == 'text/x-python':
                    raw = base64.b64decode(value) + ('# ' + marker + '\n').encode()
                    node[key] = base64.b64encode(raw).decode()
                else:
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(data)
    return data


def seeded_arguments(arguments, marker=MARKER):
    """The same arguments naming the seeded components and outputs."""
    arguments = copy.deepcopy(arguments)
    if 'include_source_for' in arguments:
        arguments['include_source_for'] = [
            n + ' ' + marker for n in arguments['include_source_for']
        ]
    if 'outputs' in arguments:
        arguments['outputs'] = [
            '.'.join(part + ' ' + marker for part in n.split('.')) for n in arguments['outputs']
        ]
    return arguments


def test_every_text_written_by_others_is_inside_untrusted_content():
    data = seeded(RECORDED)
    found = set()
    for case, (name, arguments) in CASES.items():
        api = RecordedApi(data, validate=False)
        result = invoke(api, name, seeded_arguments(arguments))
        for path, value in walk(result):
            if isinstance(value, str) and MARKER in value:
                found.add((case,) + path)
                assert 'untrusted_content' in path, (case, path)
    # Names, titles, statements, evidence, diagnostics and source all reach the projections.
    assert len(found) > 150
    assert {path[0] for path in found} >= set(CASES) - {
        'check_execution_readiness',
        'get_capabilities',
        'get_run_results_without_results',
        'list_model_versions',
        'list_study_brief_versions_first_page',
        'list_calculations_of_another_model_version',
        'get_model_explanation_of_version_1',
    }


def test_every_id_is_paired_with_a_name():
    golden = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))
    pairs = 0
    for case, result in golden.items():
        for path, value in walk(result):
            if not isinstance(value, dict):
                continue
            ids = [k for k in value if k == 'id' or k.endswith('_id')]
            if ids:
                pairs += 1
                assert 'name' in value, (case, path)
                name = value['name']
                assert isinstance(name, str) or set(name) & {'untrusted_content', 'missing'}, (
                    case,
                    path,
                )
            for key, child in value.items():
                if isinstance(child, str) and UUID.fullmatch(child):
                    assert key == 'id' or key.endswith('_id') or key == 'revision_token', (
                        case,
                        path,
                        key,
                    )
    assert pairs > 100


def test_every_quantity_has_a_unit_and_no_unavailable_value_is_a_number():
    golden = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))
    unavailable = 0
    for case, result in golden.items():
        for path, value in walk(result):
            if not isinstance(value, dict):
                continue
            if 'value' in value and isinstance(value['value'], (int, float)):
                assert isinstance(value.get('unit'), str) and value['unit'], (case, path)
            if isinstance(value.get('unavailable'), str):
                unavailable += 1
                assert 'value' not in value and value['unavailable'], (case, path)
    assert unavailable >= 5
    failed = golden['get_run_results_failed_with_diagnostics']
    by_name = {
        o['quantity']['untrusted_content']['text']: o for o in failed['outputs'] if 'quantity' in o
    }
    assert by_name['Range.range'] == {
        'quantity': by_name['Range.range']['quantity'],
        'unavailable': 'producer_failed',
    }
    assert by_name['Mass closure.mtow']['value'] == 22172.0
    # Recorded values keep the precision the owner stored.
    recorded = golden['get_run_results_recorded']['outputs']
    assert 9000.000000000002 in [o.get('value') for o in recorded]


def test_execution_and_criteria_stay_separate_without_invented_scientific_status():
    golden = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))
    keys = {'execution'}
    for case in (
        'get_run_results_recorded',
        'get_run_results_failed_with_diagnostics',
        'get_run_results_without_results',
    ):
        assert set(golden[case]['facets']) == keys
    pending = golden['get_run_results_without_results']
    assert set(pending['facets'].values()) == {'not evaluated'}
    assert pending['outputs'] == pending['criteria'] == {'missing': 'no_retained_results'}
    failed = golden['get_run_results_failed_with_diagnostics']
    assert failed['facets']['execution']['state'] == 'failed'
    assert [c['outcome'] for c in failed['criteria']] == ['unresolved', 'unresolved']
    recorded = golden['get_run_results_recorded']
    assert [c['outcome'] for c in recorded['criteria']] == ['met', 'met']
    assert recorded['criteria'][0]['threshold'] == {'value': 9000, 'unit': 'km', 'operator': 'ge'}
    assert 'message' not in recorded['facets']['execution']
    declared = recorded['model_declared_feasibility']
    assert [o['value'] for o in declared['outputs']] == [1.0]
    assert 'not a HYPRN MVP feasibility outcome' in declared['note']


@pytest.mark.parametrize(
    'case',
    [
        'get_run_status',
        'get_run_results_recorded',
        'get_run_results_failed_with_diagnostics',
        'get_run_results_without_results',
        'list_result_sources',
    ],
)
def test_result_tools_do_not_require_or_recreate_removed_status_fields(case):
    data = copy.deepcopy(RECORDED)
    for detail in data['run_details'].values():
        results = (detail.get('history') or {}).get('results')
        if results:
            for key in ('convergence', 'optimization', 'completeness', 'applicability'):
                results.pop(key, None)
    for item in data['run_status'].values():
        item['facets'] = {'execution': item['facets']['execution']}
    for item in data['result_sources']:
        item['outcomes'].pop('applicability', None)
    # The handler boundary accepts the reduced API shape without filling old fields.
    # Complete recorded responses are contract-validated by the golden cases above.
    actual, _ = run_case(case, data, validate=False)
    expected = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))[case]
    assert actual == expected
    removed = {
        'convergence',
        'optimization',
        'termination',
        'feasibility',
        'completeness',
        'applicability',
    }
    for _, value in walk(actual):
        if isinstance(value, dict):
            assert not removed.intersection(value)


def test_diagnostics_are_bounded_to_1200_characters():
    data = copy.deepcopy(RECORDED)
    results = data['run_details'][RUN2]['history']['results']
    results['execution']['message'] = 'x' * 5000
    result = invoke(
        RecordedApi(data), 'get_run_results', {'run_id': RUN2, 'include_diagnostics': True}
    )
    execution = result['facets']['execution']
    assert len(execution['message']['untrusted_content']['text']) == 1200
    assert execution['message_truncated'] is True


# ---- Truncation -------------------------------------------------------------------------


def oversized():
    data = copy.deepcopy(RECORDED)
    for source in data['model_drafts'][M1]['source_files']:
        raw = ('value = 1  # ' + 'long comment ' * 20 + '\n') * 900
        source['bytes'] = base64.b64encode(raw.encode()).decode()
    return data


def test_oversized_projections_are_capped_with_a_note_naming_what_was_omitted_and_how_to_get_it():
    api = RecordedApi(oversized(), validate=False)
    model = invoke(
        api, 'get_model', {'model_id': M1, 'include_source_for': ['Range', 'Mass closure']}
    )
    assert projections.size(model) <= projections.MAX_RESULT_BYTES
    assert model['truncated']['omitted'][0].startswith('component source')
    assert model['truncated']['how_to_get'][0].startswith('get_model with include_source_for')
    alone = invoke(api, 'get_model', {'model_id': M1, 'include_source_for': ['Range']})
    source = alone['source'][0]['source']
    assert source['truncated'] is True and source['lines'] == 901
    assert source['note'] == 'Shown up to 400 lines; the source has 901.'


def test_cap_keeps_a_projection_that_fits_unchanged_and_refuses_one_it_cannot_fit():
    small = {'a': [1, 2], 'b': 'text'}
    assert projections.cap(small, [('a', 'a', 'x')]) == small
    with pytest.raises(ToolError) as caught:
        projections.cap({'keep': 'x' * 30000}, [('other', 'other', 'nothing')])
    assert caught.value.category == 'too_large'


# ---- Pagination -------------------------------------------------------------------------


def many_runs(count):
    data = copy.deepcopy(RECORDED)
    first = data['runs'][0]
    data['runs'] = [
        dict(first, run_id='5c100000-0000-4000-8000-%012x' % n, command_id=str(uuid4()))
        for n in range(count)
    ]
    return data


@pytest.mark.parametrize('limit', [0, 26, -1])
def test_list_tools_refuse_a_limit_outside_1_to_25(limit):
    for name in ('list_runs', 'list_evidence', 'list_configurations', 'list_models'):
        error = refusal(RecordedApi(), name, {'limit': limit})
        assert error.category == 'invalid_input'
        assert [f['path'] for f in error.fields] == ['limit']


def test_pages_default_to_10_and_cursors_walk_every_item_once():
    data = many_runs(23)
    api = RecordedApi(data)
    first = invoke(api, 'list_runs', {})
    assert len(first['runs']) == 10 and first['next_cursor']
    seen, cursor = [r['id'] for r in first['runs']], first['next_cursor']
    while cursor:
        page = invoke(api, 'list_runs', {'cursor': cursor, 'limit': 25})
        seen += [r['id'] for r in page['runs']]
        cursor = page['next_cursor']
    assert seen == [r['run_id'] for r in data['runs']]
    assert ('limit', '10') in api.calls[0][2]


def test_an_altered_or_foreign_cursor_is_invalid_input():
    api = RecordedApi(many_runs(12))
    cursor = invoke(api, 'list_runs', {})['next_cursor']
    raw = bytearray(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
    tampered = raw.replace(b'5c100000', b'5c100001')
    altered = base64.urlsafe_b64encode(bytes(tampered)).decode().rstrip('=')
    flipped = cursor[:-1] + ('A' if cursor[-1] != 'A' else 'B')
    foreign = projections.encode_cursor('list_configurations', CV1)
    for bad in (altered, flipped, foreign, 'not a cursor', cursor + '=', '!' * 10):
        error = refusal(api, 'list_runs', {'cursor': bad})
        assert error.category == 'invalid_input'
        assert error.fields == (
            {'path': 'cursor', 'problem': 'must be a next_cursor of this tool'},
        )
    assert projections.decode_cursor('list_runs', cursor) == '5c100000-0000-4000-8000-000000000009'


def test_brief_versions_page_newest_first_and_an_unknown_number_is_not_found():
    api = RecordedApi()
    first = invoke(api, 'list_study_brief_versions', {'limit': 1})
    assert [v['number'] for v in first['versions']] == [2] and first['next_cursor']
    rest = invoke(api, 'list_study_brief_versions', {'limit': 1, 'cursor': first['next_cursor']})
    assert [v['number'] for v in rest['versions']] == [1] and rest['next_cursor'] is None
    assert rest['versions'][0]['predecessor'] == {'missing': 'first_version'}
    foreign = projections.encode_cursor('list_runs', 2)
    assert refusal(api, 'list_study_brief_versions', {'cursor': foreign}).category == (
        'invalid_input'
    )
    absent = refusal(api, 'get_study_brief', {'which': 'version_number', 'version_number': 3})
    assert absent.category == 'not_found'
    mismatched = refusal(api, 'get_study_brief', {'version_number': 1})
    assert mismatched.category == 'invalid_input'


def test_brief_criteria_keep_their_priority_units_and_no_score():
    criteria = invoke(RecordedApi(), 'get_study_brief', {'sections': ['criteria']})['criteria']
    assert [c['priority'] for c in criteria] == [1, 2, 3]
    assert criteria[0]['threshold'] == {'value': 9000, 'unit': 'km', 'operator': 'ge'}
    assert criteria[0]['absolute_tolerance'] == {'value': 50, 'unit': 'km'}
    assert [(c['criterion_kind'], c.get('direction'), c.get('unit')) for c in criteria[1:]] == [
        ('objective', 'minimize', 'kg'),
        ('objective', 'minimize', 'MJ/km'),
    ]
    assert not any({'weight', 'score', 'rank'} & set(c) for c in criteria)


def test_model_version_cursors_are_bound_to_their_model():
    data = copy.deepcopy(RECORDED)
    revisions = data['model_revisions'][M1]
    data['model_revisions'][M1] = revisions * 6
    for n, item in enumerate(data['model_revisions'][M1]):
        item = dict(item, model_revision_id='53100000-0000-4000-8000-%012x' % n)
        data['model_revisions'][M1][n] = item
    api = RecordedApi(data)
    first = invoke(api, 'list_model_versions', {'model_id': M1})
    assert [v['number'] for v in first['versions']] == list(range(1, 11))
    second = invoke(api, 'list_model_versions', {'model_id': M1, 'cursor': first['next_cursor']})
    assert [v['number'] for v in second['versions']] == [11, 12]
    other = str(uuid4())
    error = refusal(api, 'list_model_versions', {'model_id': other, 'cursor': first['next_cursor']})
    assert error.category == 'invalid_input'


# ---- Run status ---------------------------------------------------------------------------


def test_run_status_makes_exactly_one_light_read_per_call_and_keeps_nothing_between_calls():
    data = copy.deepcopy(RECORDED)
    api = RecordedApi(data)
    first = invoke(api, 'get_run_status', {'run_ids': [RUN1, RUN3]})
    assert api.calls == [
        ('GET', '/api/1/studies/' + S + '/run-status', (('run_id', RUN1), ('run_id', RUN3)))
    ]
    assert [r['state'] for r in first['runs']] == ['recorded', 'accepted_run']
    # The owner's state changes; the next call reads it again (no status cache).
    api.data['run_status'][RUN3]['state'] = 'dispatching'
    second = invoke(api, 'get_run_status', {'run_ids': [RUN1, RUN3]})
    assert len(api.calls) == 2
    assert [r['state'] for r in second['runs']] == ['recorded', 'dispatching']


def test_run_status_shows_unrecorded_and_unprojected_times_as_missing_with_their_reason():
    golden = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))
    pending, recorded, unrecorded = golden['get_run_status']['runs']
    assert pending['times'] == {
        'submitted_at': '2026-10-14T07:58:00.000000Z',
        'started_at': {'missing': 'not_projected'},
        'finished_at': {'missing': 'not_projected'},
    }
    assert pending['waiting_s'] == 150
    assert pending['facets']['execution'] == {'missing': 'not_recorded'}
    assert pending['criteria'] == {'missing': 'not_recorded'}
    assert pending['process_state'] == pending['exit_status'] == {'missing': 'not_recorded'}
    assert unrecorded['times']['submitted_at'] == {'missing': 'not_recorded'}
    assert recorded['waiting_s'] == unrecorded['waiting_s'] == {'missing': 'no_longer_waiting'}
    assert recorded['exit_status'] == 0 and recorded['process_state'] == 'finished'


def test_run_status_answers_nothing_when_one_id_is_not_a_run_of_the_study():
    api = RecordedApi()
    error = refusal(api, 'get_run_status', {'run_ids': [RUN1, str(uuid4())]})
    assert error.category == 'not_found' and len(api.calls) == 1
    for bad in ([], [str(uuid4()) for _ in range(21)], [RUN1, RUN1], ['RUN1']):
        assert refusal(api, 'get_run_status', {'run_ids': bad}).category == 'invalid_input'
    assert len(api.calls) == 1


# ---- Errors -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    'status,code,category',
    [
        (404, 'resource_not_found', 'not_found'),
        (403, 'forbidden', 'access_lost'),
        (401, 'unauthenticated', 'session_expired'),
        (503, 'backend_unavailable', 'unavailable'),
        (429, 'rate_limited', 'busy'),
        (500, 'internal_error', 'internal'),
    ],
)
def test_owner_refusals_become_agent_error_categories_and_are_never_retried(status, code, category):
    api = RecordedApi()

    def refuse(path, pairs):
        raise Refused(status, code)

    api.serve = refuse
    error = refusal(api, 'get_run_results', {'run_id': RUN1})
    assert error.category == category
    assert len(api.calls) == 1


def test_a_404_on_the_study_itself_is_access_lost():
    api = RecordedApi()
    api.base = '/api/1/studies/' + str(uuid4())
    error = refusal(api, 'get_study_overview', {})
    assert error.category == 'access_lost'


def test_capabilities_report_an_unavailable_unit_catalog_without_failing():
    api = RecordedApi()
    serve = api.serve

    def without_units(path, pairs):
        if path.endswith('/unit-catalog'):
            raise Refused(503, 'backend_unavailable')
        return serve(path, pairs)

    api.serve = without_units
    result = invoke(api, 'get_capabilities', {})
    assert result['units'] == {'unavailable': 'modeling_unavailable'}
    assert 'cancellation' in result['unavailable']


# ---- Through the real application ---------------------------------------------------------


class RecordedModeling:
    """The modeling double of the real application: every private call is answered as
    unavailable, which the application reports through its own reads."""

    def call(self, *_, **__):
        from hyprn_mvp_app.contracts import DomainError

        raise DomainError('backend_unavailable', 503, outcome='unknown')


def _store_runs(store, sid, count):
    """``count`` runs of one saved configuration, inserted as the execution owner stores them
    (association, outbox state and the stored status and results paths)."""
    frozen = copy.deepcopy(RECORDED['configurations'][0])
    configuration = frozen['configuration']
    configuration['study_id'] = sid
    cv = configuration['configuration_revision_id']
    results = RECORDED['run_details'][RUN1]['history']['results']
    ids = []
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations(configuration_revision_id,configuration_id,study_id,'
            'payload) VALUES(?,?,?,?)',
            (cv, configuration['configuration_id'], sid, json.dumps(frozen)),
        )
        for n in range(count):
            run_id, recorded = str(uuid4()), n % 2 == 0
            db.execute(
                'INSERT INTO run_associations(run_id,study_id,configuration_revision_id,'
                'command_id,store_uuid,process_uuid,accepted_at) VALUES(?,?,?,?,?,?,?)',
                (run_id, sid, cv, str(uuid4()), None, None, '2026-10-14T07:00:00.000000Z'),
            )
            payload = {'status': {'process_state': 'finished', 'exit_status': 0}}
            if recorded:
                payload['history'] = {'results': dict(results, run_id=run_id)}
            db.execute(
                'INSERT INTO outbox(run_id,state,payload) VALUES(?,?,?)',
                (run_id, 'recorded' if recorded else 'accepted_run', json.dumps(payload)),
            )
            ids.append(run_id)
    return ids


class CountingClient:
    def __init__(self, client):
        self.client, self.calls = client, []

    async def request(self, session, method, path, json_body=None, params=None):
        self.calls.append((method, path))
        return await self.client.request(session, method, path, json_body, params)


@pytest.fixture
def application(tmp_path):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store

    store = Store(tmp_path / 'read-tools.sqlite')
    auth = Auth(store, LOOPBACK_ORIGIN)
    owner = str(uuid4())
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (owner, 'owner', 'unused'),
        )
    sid = store.create_study(owner, str(uuid4()), 'Hydrogen aircraft sizing')['study_id']
    evidence = store.add_evidence(
        owner,
        sid,
        str(uuid4()),
        dict(
            evidence_schema_version='3',
            title='Mission profile note',
            kind='note',
            content='Cruise at Mach 0.78 at 35,000 ft.',
            source_refs=['Mission requirements, p. 12'],
            resource_scope=dict(scope_version='1', kind='study', study_id=sid),
        ),
    )
    runs = _store_runs(store, sid, 14)
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Coding agent (local)')
        delegation = store.create_delegation(
            db, agent, sid, 'reader', ('read', 'outside_study'), time.time() + 3600
        )
    session = auth.mint_agent_session(delegation['delegation_id'])
    app = create_app(store, auth, RecordedModeling())
    return dict(app=app, session=session, sid=sid, runs=runs, evidence=evidence)


def test_read_tools_pass_the_agent_route_allowlist_through_the_real_application(application):
    async def calls():
        async with ApiClient(application['app'], LOOPBACK_ORIGIN) as client:
            counting = CountingClient(client)
            ctx = context(counting, session=application['session'])
            version = application['evidence']['evidence_version_id']
            results = {}
            for name, arguments in (
                ('get_study_overview', {}),
                ('get_capabilities', {}),
                ('check_execution_readiness', {}),
                ('get_study_brief', {}),
                ('list_study_brief_versions', {}),
                ('list_models', {}),
                ('list_evidence', {}),
                ('read_evidence', {'evidence_version_id': version}),
                ('list_configurations', {}),
                ('list_runs', {'limit': 25}),
                ('get_run_status', {'run_ids': application['runs'][:3]}),
            ):
                results[name] = await REGISTRY.invoke(name, arguments, ctx)
            return results, counting.calls

    results, calls = asyncio.run(calls())
    overview = results['get_study_overview']
    assert overview['runs']['count'] == 14 and overview['evidence']['count'] == 1
    assert overview['runs']['by_state'] == {'accepted_run': 7, 'recorded': 7}
    assert overview['brief'] == {
        'draft': {'missing': 'no_draft'},
        'latest_version': {'missing': 'no_saved_version'},
    }
    assert results['get_study_brief'] == {
        'which': 'draft',
        'draft': {'missing': 'no_draft'},
        'latest_version': {'missing': 'no_saved_version'},
    }
    assert results['list_study_brief_versions'] == {'versions': [], 'next_cursor': None}
    assert results['get_capabilities']['units'] == {'unavailable': 'modeling_unavailable'}
    assert 'modeling_unavailable' in results['check_execution_readiness']['reasons']
    assert results['read_evidence']['content']['untrusted_content']['text'].startswith('Cruise')
    assert len(results['list_runs']['runs']) == 14
    states = [r['state'] for r in results['get_run_status']['runs']]
    assert states == ['recorded', 'accepted_run', 'recorded']
    assert results['list_configurations']['configurations'][0]['name']['untrusted_content']
    assert all(method == 'GET' for method, _ in calls)


def test_run_status_through_the_application_is_one_read_and_under_one_second_at_p95(application):
    async def timed():
        durations = []
        async with ApiClient(application['app'], LOOPBACK_ORIGIN) as client:
            counting = CountingClient(client)
            ctx = context(counting, session=application['session'])
            for _ in range(20):
                counting.calls.clear()
                start = time.perf_counter()
                result = await REGISTRY.invoke(
                    'get_run_status', {'run_ids': application['runs']}, ctx
                )
                durations.append(time.perf_counter() - start)
                assert counting.calls == [
                    ('GET', '/api/1/studies/' + application['sid'] + '/run-status')
                ]
                assert len(result['runs']) == 14
        return sorted(durations)

    durations = asyncio.run(timed())
    assert durations[int(0.95 * len(durations)) - 1] < 1.0


def test_structured_evidence_fields_are_separate_untrusted_bounded_content():
    from hyprn_mvp_app.evidence_content import write_content
    api = RecordedApi()
    record = next(row for row in api.data['evidence_versions'] if row['evidence_version_id'] == E2V1)
    fields = dict(excerpt='Exact source statement.', source_reference='Report A',
                  location='p. 7', explanation='This supports only the reference condition.')
    record['content'] = write_content(fields)
    result = invoke(api, 'read_evidence', {'evidence_version_id': E2V1})
    assert result['source_excerpt']['untrusted_content']['text'] == fields
    assert result['source_excerpt']['untrusted_content']['kind'] == 'author-supplied source transcription'
    assert result['source_excerpt_truncated'] is False
    limited = invoke(api, 'read_evidence', {'evidence_version_id': E2V1, 'max_chars': 5})
    assert limited['source_excerpt_truncated'] is True
    assert all(len(value) <= 5 for value in limited['source_excerpt']['untrusted_content']['text'].values())
