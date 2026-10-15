"""Thin owner-session study tools. Every operation goes through the public HTTP API.

No retries, numerical execution, model state or authority live in this adapter.
Scientific bodies use the public operation schemas returned by describe_tool.
"""

from pathlib import Path
import json

from .local_api import ClientError, record_id

S = '/api/1/studies/{study_id}'
M = S + '/models/{model_id}'
# Operation-specific formats belong here, not in scientific reasoning prompts.
OPERATIONS = {
    'get_capabilities': ('GET', '/api/1/capabilities', None),
    'list_studies': ('GET', '/api/1/studies', None),
    'create_study': ('POST', '/api/1/studies', None),
    'get_study': ('GET', S, None),
    'edit_study': ('PATCH', S, None),
    'get_units': ('GET', S + '/unit-catalog', None),
    'get_execution_readiness': ('GET', S + '/execution-readiness', None),
    'create_evidence': ('POST', S + '/evidence', None),
    'get_evidence': ('GET', S + '/evidence/{evidence_id}', None),
    'get_approach': ('GET', S + '/approach', None),
    'preview_approach': ('POST', S + '/approach/preview', None),
    'save_approach_draft': ('POST', S + '/approach/draft', None),
    'save_approach_version': ('POST', S + '/approach/versions', None),
    'get_approach_version': ('GET', S + '/approach/versions/{version_id}', None),
    'create_model': ('POST', S + '/models', '3'),
    'get_model': ('GET', M, None),
    'preview_model': ('POST', M + '/preview', '4'),
    'edit_model': ('POST', M + '/edits', '4'),
    'validate_model': ('POST', M + '/validate', None),
    'save_model_version': ('POST', M + '/commits', None),
    'get_model_version': ('GET', M + '/revisions/{revision_id}', None),
    'preview_configuration': ('POST', S + '/configurations/preview', None),
    'save_configuration': ('POST', S + '/configurations', None),
    'get_configuration': ('GET', S + '/configurations/{revision_id}', None),
    'submit_run': ('POST', S + '/runs', None),
    'get_run': ('GET', S + '/runs/{run_id}', None),
    'get_command': ('GET', S + '/commands/{command_id}', None),
    'get_global_command': ('GET', '/api/1/commands/{command_id}', None),
    'save_answer': ('POST', S + '/answers', None),
    'get_answer': ('GET', S + '/answers/{answer_id}', None),
    'list_prepared_explorations': ('GET', S + '/exploration-requests', None),
    'submit_exploration': ('POST', S + '/exploration-requests', None),
    'get_exploration': ('GET', S + '/exploration-requests/{request_id}', None),
    'preview_exploration_samples': ('POST', S + '/exploration-samples/preview', None),
    'sample_exploration': ('POST', S + '/exploration-samples', None),
    'get_exploration_samples': ('GET', S + '/exploration-samples/{operation_id}', None),
    'control_exploration_samples': (
        'POST',
        S + '/exploration-samples/{operation_id}/controls',
        None,
    ),
    'get_exploration_basis': (
        'GET',
        S + '/answers/{answer_id}/exploration-basis/{revision_id}',
        None,
    ),
    'list_answers': ('GET', S + '/approach/versions/{version_id}/answers', None),
}


def parameters(path):
    return [part[1:-1] for part in path.split('/') if part.startswith('{')]


def describe_tool(name):
    """The shipped public contract is data; never import candidate/model source."""
    if name in ('run_status', 'read_artifact'):
        return dict(
            name=name,
            identifiers=['study_id'],
            arguments=(
                {'run_ids': '1 to 20 distinct canonical run UUIDs'}
                if name == 'run_status'
                else {'run_id': 'canonical UUID', 'artifact_id': 'canonical UUID'}
            ),
            guidance='Read only. Artifact bytes are bounded and SHA-256 verified.',
        )
    if name not in OPERATIONS:
        raise ClientError('Unknown study tool.')
    method, path, version = OPERATIONS[name]
    contract = json.loads(
        (Path(__file__).resolve().parents[2] / 'contracts/hyprn-mvp.openapi.yaml').read_text()
    )
    # Router parameter names can differ from the tool's presentation names.
    template = path.removeprefix('/api/1')
    matching = next((p for p in contract['paths'] if _shape(p) == _shape(template)), None)
    if matching is None or method.lower() not in contract['paths'][matching]:
        raise ClientError('Tool operation is absent from the shipped public contract.')
    operation = contract['paths'][matching][method.lower()]
    body = (
        operation.get('requestBody', {})
        .get('content', {})
        .get('application/json', {})
        .get('schema')
    )
    definitions = {}

    def include(value):
        if isinstance(value, dict):
            ref = value.get('$ref')
            if ref:
                key = ref.rsplit('/', 1)[-1]
                if key not in definitions:
                    definitions[key] = contract['components']['schemas'][key]
                    include(definitions[key])
            for key, item in value.items():
                if key != '$ref':
                    include(item)
        elif isinstance(value, list):
            for item in value:
                include(item)

    include(body)
    return dict(
        name=name,
        identifiers=parameters(path),
        query_arguments=['category'] if name == 'get_command' else [],
        body_schema=body,
        definitions=definitions,
        request_format=version,
        guidance=(
            'Pass identifiers and body in arguments. For model creation/edits omit '
            'body.schema_version; the tool sets the operation-specific format. '
            'Retain command_id before mutations. No automatic retry is performed.'
        ),
    )


def _shape(path):
    return '/'.join('{}' if p.startswith('{') else p for p in path.split('/'))


def unwrap(reply):
    """Normalize ordinary envelopes; raw artifacts have their own operation."""
    body = reply['body']
    if reply['status'] >= 400:
        return dict(
            status=reply['status'], error=body.get('error') if isinstance(body, dict) else None
        )
    if not isinstance(body, dict) or 'data' not in body:
        raise ClientError('Expected an API envelope; use read_artifact for raw downloads.')
    return dict(
        status=reply['status'],
        data=body['data'],
        **{
            k: body[k]
            for k in ('next_cursor', 'request_id', 'created_ids', 'diagnostics')
            if k in body
        },
    )


def invoke(client, name, arguments):
    if not isinstance(arguments, dict):
        raise ClientError('Tool arguments must be an object.')
    if name == 'list_tools':
        if arguments:
            raise ClientError('list_tools takes no arguments.')
        return dict(
            status=200,
            data=dict(
                tools=list(OPERATIONS) + ['run_status', 'read_artifact', 'describe_tool'],
                transport='owner-session public API; no delegated writer authority',
            ),
        )
    if name == 'describe_tool':
        if set(arguments) != {'name'}:
            raise ClientError('describe_tool requires name only.')
        return dict(status=200, data=describe_tool(arguments['name']))
    if name == 'run_status':
        if set(arguments) != {'study_id', 'run_ids'}:
            raise ClientError('run_status requires study_id and run_ids.')
        return unwrap(client.run_status(arguments['study_id'], arguments['run_ids']))
    if name == 'read_artifact':
        if set(arguments) != {'study_id', 'run_id', 'artifact_id'}:
            raise ClientError('read_artifact requires study_id, run_id and artifact_id.')
        ids = {k: record_id(v) for k, v in arguments.items()}
        return client.read_artifact(**ids)
    if name not in OPERATIONS:
        raise ClientError('Unknown study tool; call list_tools.')
    method, path, version = OPERATIONS[name]
    ids = parameters(path)
    allowed = set(ids) | ({'body'} if method != 'GET' else set())
    if name == 'get_command':
        allowed.add('category')
    if set(arguments) != allowed:
        raise ClientError('Expected tool arguments: ' + ', '.join(sorted(allowed)))
    path = path.format(**{k: record_id(arguments[k]) for k in ids})
    if name == 'get_command':
        category = arguments['category']
        if (
            not isinstance(category, str)
            or not category
            or len(category) > 64
            or not all(c in 'abcdefghijklmnopqrstuvwxyz_' for c in category)
        ):
            raise ClientError('Use the receipt category of the original operation.')
        path += '?category=' + category
    elif name == 'get_global_command':
        path += '?category=study_create'
    command = dict(method=method, path=path)
    if method != 'GET':
        body = arguments['body']
        if not isinstance(body, dict):
            raise ClientError('body must be an object.')
        body = dict(body)
        if version:
            if 'schema_version' in body:
                raise ClientError('Omit schema_version; this tool owns the request format.')
            body['schema_version'] = version
        if name == 'submit_run':
            body.setdefault('execution_budget', {'wall_seconds': 300})
        command['body'] = body
    return unwrap(client.request(command))
