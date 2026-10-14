"""No secret reaches an agent through a read tool (tooling spec section 10.4, T-3-15).

Projections are allowlists. The recorded study reads are seeded at run time with token-shaped
strings, ``Bearer`` values, session cookie and cross-site request token names and values,
provider keys and filesystem paths: in every field the projections do not name, in an extra
unknown field of every object, in the session the tool runs under and in the owners' error
replies. No read output and no tool error on any surface contains any of them.

Text written by people or agents (names, evidence, statements, source, diagnostics) is
returned verbatim inside ``untrusted_content`` by design (tooling spec section 10.1), and a
revision token is the owner's opaque marker returned for the next write; neither is seeded.
"""

import asyncio
import copy
import json
import secrets

import pytest

from hyprn_mvp_app.agent_tools import projections
from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, REGISTRY
from hyprn_mvp_app.agent_tools.spec import SURFACES, ToolContext, ToolError
from test_agent_read_tools import CASES, NOW, READER, RECORDED, RecordedApi, Refused, walk

# Assembled at run time so that no secret-shaped literal sits in the source.
COOKIE = 'hyprn' + '_mvp' + '_session'


def secret_seeds():
    value = secrets.token_urlsafe(24)
    root = '/'.join(('', 'home', 'engineer', '.config', 'hyprn-mvp'))
    return [
        'hyprn' + '_mvp' + '_mcp_' + secrets.token_urlsafe(32),
        'Bearer ' + secrets.token_urlsafe(32),
        COOKIE + '=' + secrets.token_urlsafe(32),
        'X-CSRF-Token: ' + secrets.token_urlsafe(32),
        'sk-' + secrets.token_urlsafe(40),
        root + '/credentials-' + value + '.json',
        'C:' + '\\'.join(('', 'Users', 'engineer', 'App' + 'Data', 'hyprn-mvp-' + value)),
        'process-' + value,
    ]


# Fields of the recorded reads that no projection names (hashes, locks, receipts, paths and
# native identities). Revision tokens and authored text are returned by design and not seeded.
NEVER_PROJECTED = {
    'digest',
    'model_digest',
    'bundle_digest',
    'results_digest',
    'configuration_digest',
    'approach_digest',
    'closure_digest',
    'root_approach_digest',
    'source_configuration_digest',
    'catalog_digest',
    'engine_source_sha256',
    'evaluator_sha256',
    'command_id',
    'receipt_url',
    'lock_path',
    'originating_draft_revision',
    'study_revision',
    'expected_study_revision',
    'code_symbol',
    'created_by',
    'updated_by',
    'policy_digest',
    'image_digest',
}


def fuzzed(data, seeds):
    """The recorded reads with a seed in every never-projected string and in an extra unknown
    field of every object."""
    data = copy.deepcopy(data)
    counter = iter(range(10**9))

    def seed():
        return seeds[next(counter) % len(seeds)]

    def visit(node):
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if key in NEVER_PROJECTED and isinstance(value, str):
                    node[key] = seed()
                else:
                    visit(value)
            node['native_' + 'token'] = seed()
            node[COOKIE] = seed()
        elif isinstance(node, list):
            for item in node:
                visit(item)

    for key, value in data.items():
        if key != 'study_id':
            visit(value)
    # The served study read carries a secret in a field the contract never had.
    data['study']['session'] = seeds[0]
    return data


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(projections, 'utc_now', lambda: NOW)


def session(seeds):
    return {'study_id': RECORDED['study_id'], 'token': seeds[2], 'csrf_token': seeds[3]}


def run(api, surface, name, arguments, seeds):
    ctx = ToolContext(
        surface=surface, stage=LOCAL_STAGE, effects=READER, api=api, session=session(seeds)
    )
    return asyncio.run(REGISTRY.invoke(name, copy.deepcopy(arguments), ctx))


def leaks(text, seeds):
    return [s for s in seeds if s in text or s.split(' ', 1)[-1].split('=', 1)[-1] in text]


@pytest.mark.parametrize('surface', SURFACES)
def test_no_read_output_contains_a_seeded_secret_on_any_surface(surface):
    seeds = secret_seeds()
    data = fuzzed(RECORDED, seeds)
    outputs = 0
    for case, (name, arguments) in CASES.items():
        api = RecordedApi(data, validate=False)
        result = run(api, surface, name, arguments, seeds)
        assert leaks(json.dumps(result, ensure_ascii=False), seeds) == [], case
        outputs += 1
    assert outputs == len(CASES)


@pytest.mark.parametrize(
    'status,code',
    [(400, 'invalid_request'), (403, 'forbidden'), (404, 'resource_not_found'), (500, 'x')],
)
def test_no_tool_error_contains_a_seeded_secret_from_an_owner_reply(status, code):
    seeds = secret_seeds()
    api = RecordedApi()

    async def refuse(session, method, path, json_body=None, params=None):
        body = {
            'error': {
                'code': code,
                'message': ' '.join(seeds),
                'fields': [{'path': seeds[5], 'message': seeds[1]}],
                'request_id': seeds[7],
            }
        }
        from hyprn_mvp_app.agent_tools.api_client import ApiResponse

        return ApiResponse(status, body, None)

    api.request = refuse
    for case, (name, arguments) in CASES.items():
        with pytest.raises(ToolError) as caught:
            run(api, 'local_mcp', name, arguments, seeds)
        text = json.dumps(caught.value.envelope(), ensure_ascii=False) + str(caught.value)
        assert leaks(text, seeds) == [], case


def test_the_fuzz_is_not_vacuous():
    seeds = secret_seeds()
    data = fuzzed(RECORDED, seeds)
    strings = [v for _, v in walk(data) if isinstance(v, str)]
    assert all(any(s == v for v in strings) for s in seeds)
    # Seeded values still reach the served bodies the tools read.
    api = RecordedApi(data, validate=False)
    run(api, 'local_mcp', 'get_run_results', {'run_id': RECORDED['runs'][0]['run_id']}, seeds)
    assert api.calls
    with pytest.raises(Refused):
        api.serve('/api/1/elsewhere', [])
