"""Thin owner-session study tools. Every operation goes through the public HTTP API.

No retries, numerical execution, model state or authority live in this adapter.
Scientific bodies use the public operation schemas returned by describe_tool.
"""

from pathlib import Path
import json
from urllib.parse import urlencode

from .local_api import ClientError, record_id

S = '/api/1/studies/{study_id}'
M = S + '/models/{model_id}'
# Operation-specific formats belong here, not in scientific reasoning prompts.
OPERATIONS = {
    'get_capabilities': ('GET', '/api/1/capabilities', None),
    'list_studies': ('GET', '/api/1/studies', None),
    'create_study': ('POST', '/api/1/studies', None),
    'get_study': ('GET', S, None),
    'get_units': ('GET', S + '/unit-catalog', None),
    'get_execution_readiness': ('GET', S + '/execution-readiness', None),
    'create_evidence': ('POST', S + '/evidence', None),
    'revise_evidence': ('POST', S + '/evidence-families/{evidence_id}/versions', None),
    'get_evidence': ('GET', S + '/evidence/{evidence_id}', None),
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
    'get_study_brief': ('GET', S + '/brief', None),
    'save_study_brief_draft': ('POST', S + '/brief/draft', None),
    'save_study_brief_version': ('POST', S + '/brief/versions', None),
    'get_model_explanation': ('GET', M + '/explanation', None),
    'save_model_explanation_draft': ('POST', M + '/explanation/draft', None),
    'save_model_explanation_version': ('POST', M + '/explanation/versions', None),
    'get_study_answer': ('GET', S + '/answer', None),
    'save_study_answer_draft': ('POST', S + '/answer/draft', None),
    'save_study_answer_version': ('POST', S + '/answer/versions', None),
    'list_analyses': ('GET', S + '/analyses', None),
    'create_analysis': ('POST', S + '/analyses', None),
    'save_analysis_version': ('POST', S + '/analyses/{calculation_id}/versions', None),
    'get_analysis_version': ('GET', S + '/analysis-versions/{version_id}', None),
    'get_analysis_runs': ('GET', S + '/analysis-versions/{version_id}/runs', None),
    'launch_analysis': ('POST', S + '/analysis-versions/{version_id}/execution', None),
    'get_analysis_execution': ('GET', S + '/analysis-versions/{version_id}/execution', None),
    'run_analysis': ('POST', S + '/analysis-versions/{version_id}/run-requests', None),
    'set_reference_mark': ('POST', S + '/reference-marks', None),
    'list_reference_marks': ('GET', S + '/reference-marks', None),
    'sample_analysis': ('POST', S + '/analysis-samples', None),
    'get_analysis_samples': ('GET', S + '/analysis-samples/{operation_id}', None),
    'list_analysis_samples': ('GET', S + '/analysis-samples', None),
    'build_analysis_estimate': ('POST', S + '/analysis-estimates', None),
    'get_analysis_estimate': ('GET', S + '/analysis-estimates/{estimate_id}', None),
    'list_analysis_estimates': (
        'GET',
        S + '/analysis-versions/{version_id}/estimates',
        None,
    ),
    'get_analysis_exploration': (
        'GET',
        S + '/analysis-versions/{version_id}/exploration',
        None,
    ),
    'check_analysis_preparation': (
        'POST',
        S + '/analysis-estimates/{estimate_id}/preparation',
        None,
    ),
    'predict_analysis': (
        'POST',
        S + '/analysis-estimates/{estimate_id}/predictions',
        None,
    ),
}

QUERY_ARGUMENTS = {
    'list_analyses': ('limit', 'after', 'model_revision_id'),
    'get_analysis_runs': ('limit', 'after', 'configuration_revision_id'),
    'list_analysis_estimates': ('cursor',),
    'list_reference_marks': ('model_id',),
    'get_analysis_exploration': ('group', 'estimate_id'),
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
    if name in ('create_evidence', 'revise_evidence'):
        structured = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / 'contracts/schemas/evidence-content.schema.json'
            ).read_text()
        )
        for definition in definitions.values():
            properties = definition.get('properties', {})
            if 'content' in properties:
                properties['content'] = {
                    'oneOf': [properties['content'], structured],
                    'description': 'A structured source/explanation object is serialized into the immutable note content by this tool. Plain text stays an unquoted note.',
                }
    authorship = {
        'save_model_explanation_draft': (
            'Model explanation: physical meaning, equations, assumptions, applicability '
            'and input-to-output logic only. Put sampling counts, training/validation partitions, '
            'accuracy targets and numerical checks in analysis content.description '
            '(Analysis details) and structured design/assessment records. '
        ),
        'create_analysis': (
            'Use content format 4 with estimate_plan null for calculations only or explicit tolerances. '
            'Use content.description for Analysis details: investigation rationale, '
            'sampling/validation plan and accuracy targets. Exact settings and results stay '
            'in design/assessment records; physical equations stay in model explanation. '
        ),
    }
    authorship['sample_analysis'] = (
        'Save estimate_plan (null or explicit output tolerances) before launch_analysis; '
        'get_analysis_execution reports automatic calculation, fitting and validation. '
        'Change settings only in a new version. Use validation_count for held-out points. Training and validation are point roles; '
        'both receive calculated model results. Method selection consumes the first '
        'validation point; the remainder assess numerical accuracy independently. '
    )
    authorship['launch_analysis'] = (
        'Launch once with body {}. Repeating returns the same execution. Existing member runs '
        'are pinned and reused; missing runs and surrogate validation advance automatically. '
        'Read get_analysis_execution; do not submit a separate fit for this version. '
    )
    authorship['save_analysis_version'] = authorship['create_analysis']
    return dict(
        name=name,
        identifiers=parameters(path),
        query_arguments=['category']
        if name == 'get_command'
        else list(QUERY_ARGUMENTS.get(name, ())),
        body_schema=body,
        definitions=definitions,
        request_format=version,
        guidance=authorship.get(name, '')
        + (
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
    required = set(ids) | ({'body'} if method != 'GET' else set())
    if name == 'get_command':
        required.add('category')
    allowed = required | set(QUERY_ARGUMENTS.get(name, ()))
    if not required <= set(arguments) <= allowed:
        raise ClientError('Expected tool arguments: ' + ', '.join(sorted(allowed)))
    path_ids = {k: record_id(arguments[k]) for k in ids}
    path = path.format(**path_ids)
    query = {}
    for key in QUERY_ARGUMENTS.get(name, ()):
        if key not in arguments:
            continue
        value = arguments[key]
        if key in ('limit', 'after', 'group'):
            upper = {'limit': 100, 'group': 10000, 'after': 9007199254740991}[key]
            if type(value) is not int or not 1 <= value <= upper:
                raise ClientError(key + ' must be a positive integer within the public limit.')
            query[key] = value
        else:
            query[key] = record_id(value)
    if query:
        path += '?' + urlencode(query)
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
        if name in ('create_evidence', 'revise_evidence') and isinstance(
            body.get('content'), dict
        ):
            body['content'] = 'HYPRN evidence/1\n' + json.dumps(
                body['content'], ensure_ascii=False, separators=(',', ':')
            )
        if name == 'submit_run':
            body.setdefault('execution_budget', {'wall_seconds': 300})
        command['body'] = body
    return unwrap(client.request(command))
