"""Bounded data-only result protocol and fixed scientific criteria."""

import json
import math
import operator

ASSESSMENT_VERSION = 'fixed-threshold-1'
OPERATORS = {
    'lt': operator.lt,
    'le': operator.le,
    'eq': operator.eq,
    'ge': operator.ge,
    'gt': operator.gt,
}


def evaluate_criteria(result, criteria, unit_conversion=None):
    """Compare in criterion units; tolerance applies to equality only.

    No convergence or applicability is inferred from threshold satisfaction.
    Native conversion is injected only by the attested numerical worker.
    """
    if result.get('schema_version') not in ('1', '2'):
        raise ValueError('Unsupported result format')
    outputs = {(o['target']['instance_id'], o['target']['port_id']): o for o in result['outputs']}
    outcomes = []
    for criterion in criteria:
        outcome, reason = 'unresolved', 'required_output_unavailable'
        output = outputs.get((criterion['target']['instance_id'], criterion['target']['port_id']))
        if result['schema_version'] == '1' and result['convergence']['state'] not in (
            'converged',
            'not_applicable',
        ):
            reason = 'convergence_unresolved'
        elif output and output['availability'] == 'available':
            try:
                value, threshold = output['value'], criterion['threshold']
                absolute, relative = (
                    criterion.get('absolute_tolerance', 0),
                    criterion.get('relative_tolerance', 0),
                )
                if (
                    any(
                        type(v) not in (int, float) or not math.isfinite(v)
                        for v in (value, threshold, absolute, relative)
                    )
                    or min(absolute, relative) < 0
                ):
                    raise ValueError('Invalid tolerance or value')
                old, new = output['units'], criterion['units']
                if bool(old) != bool(new):
                    raise ValueError('Incompatible unit presence')
                if old:
                    if unit_conversion is None:
                        if old != new:
                            raise ValueError('Native conversion required')
                    else:
                        factor, offset = unit_conversion(old, new)
                        if offset:
                            raise ValueError('Affine conversion unsupported')
                        value *= factor
                if not math.isfinite(value) or not math.isfinite(
                    absolute + relative * abs(threshold)
                ):
                    raise ValueError('Nonfinite conversion or tolerance')
                compare = OPERATORS[criterion['operator']]
                met = (
                    abs(value - threshold) <= absolute + relative * abs(threshold)
                    if criterion['operator'] == 'eq'
                    else compare(value, threshold)
                )
                outcome, reason = ('met' if met else 'violated'), 'threshold_comparison'
            except (ValueError, KeyError, TypeError, OverflowError):
                reason = 'invalid_criterion_or_units'
        outcomes.append(
            dict(criterion_id=criterion['criterion_id'], outcome=outcome, reason=reason)
        )
    return outcomes


def validate_criteria(result, configuration):
    """Validate native assessments without importing candidate or numerical code.

    Result protocol 3 and configuration 6 carry no criteria: nothing is evaluated here.
    """
    if result.get('schema_version') == '3' or 'criteria' not in configuration:
        if 'criteria' in result or 'criteria' in configuration:
            raise ValueError('Criteria-free result and configuration must agree')
        return result
    criteria = configuration['criteria']
    claims = result['criteria']
    if len(claims) != len(criteria):
        raise ValueError('Criterion inventory mismatch')
    expected = evaluate_criteria(result, criteria)
    outputs = {(o['target']['instance_id'], o['target']['port_id']): o for o in result['outputs']}
    for c, claim, same_units in zip(criteria, claims, expected):
        if (
            set(claim) != {'criterion_id', 'outcome', 'reason'}
            or claim['criterion_id'] != c['criterion_id']
        ):
            raise ValueError('Criterion identity mismatch')
        output = outputs.get((c['target']['instance_id'], c['target']['port_id']))
        if (
            output
            and output['availability'] == 'available'
            and output['units']
            and c['units']
            and output['units'] != c['units']
        ):
            # Unit conversions are performed by the pinned native worker; never
            # recreate its unit system or silently reinterpret retained claims.
            if claim not in [
                dict(criterion_id=c['criterion_id'], outcome=s, reason=r)
                for s, r in [
                    ('met', 'threshold_comparison'),
                    ('violated', 'threshold_comparison'),
                    ('unresolved', 'invalid_criterion_or_units'),
                ]
            ]:
                raise ValueError('Invalid native criterion claim')
        elif claim != same_units:
            raise ValueError('Inconsistent criterion outcome')
    return result


def _bounded_json(raw, *, size, depth_limit, collection_limit, kind):
    if len(raw) > size:
        raise ValueError('Oversized ' + kind)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result

    value = json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')),
    )

    def bound(item, depth=0):
        if depth > depth_limit:
            raise ValueError(kind + ' nesting exceeded')
        if isinstance(item, (dict, list)):
            if len(item) > collection_limit:
                raise ValueError(kind + ' collection exceeded')
            for child in item.values() if isinstance(item, dict) else item:
                bound(child, depth + 1)

    bound(value)
    # Reject overflowed JSON numbers as well as NaN tokens.
    json.dumps(value, allow_nan=False)
    return value


def bounded_json(raw):
    return _bounded_json(raw, size=131072, depth_limit=24, collection_limit=2000, kind='result')


def artifact_json(raw):
    # Scientific artifacts use the expanded bundle bound and contract nesting.
    # Closed artifact schemas have at most 2000 inventory entries (1000 model
    # elements); source strings are bounded by the bytes, not stdout policy.
    from hyprn_mvp_app.execution_bundle import MAX_BYTES, MAX_FILES

    return _bounded_json(
        raw, size=MAX_BYTES, depth_limit=32, collection_limit=MAX_FILES, kind='artifact'
    )


def _result_unit(value, model_version):
    """Resolve only the closed retained spelling; never parse or convert units."""
    if isinstance(value, str):
        if len(value) > 4096:
            raise ValueError('Invalid retained unit')
        if model_version == '3' and value:
            return _result_unit({'kind': 'physical', 'expression': value}, '3')
        return value  # Legacy meanings remain exact, including empty string.
    if model_version not in ('3', '4') or not isinstance(value, dict):
        raise ValueError('Invalid retained unit declaration')
    if value == {'kind': 'dimensionless'}:
        return ''
    if (
        set(value) == {'kind', 'expression'}
        and value['kind'] == 'physical'
        and isinstance(value['expression'], str)
        and value['expression']
        in {
            'm',
            'km',
            'cm',
            'mm',
            's',
            'min',
            'h',
            'kg',
            'g',
            'N',
            'Pa',
            'kPa',
            'MPa',
            'K',
            'degC',
            'degF',
            'rad',
            'deg',
            'm/s',
            'km/h',
            'J/kg',
            'kJ/kg',
            'MJ/kg',
            'kg/m**3',
            'g/cm**3',
            'm**2',
            'cm**2',
            'mm**2',
            'm**3',
            'cm**3',
            'mm**3',
            'kg/m**2',
            'g/m**2',
            '1/m**2',
            'J/(kg*K)',
            'kJ/(kg*K)',
            'J',
            'kJ',
            'MJ',
            'W',
            'kW',
            'MW',
            'm**3/s',
            'kg/s',
            'm/s**2',
            'N*m',
            'W/(m*K)',
            'W/(m**2*K)',
        }
    ):
        return value['expression']
    raise ValueError('Unresolved or malformed retained output unit')


def validate_result(raw, request, model, *, result_schema_version='1'):
    """Accept data only, bound to the immutable native inputs and port inventory."""
    envelope = bounded_json(raw)
    if (
        envelope['reason'] != 'exited'
        or type(envelope['exit_code']) is not int
        or envelope['exit_code'] != 0
    ):
        raise ValueError('Worker did not exit normally')
    prefix = 'HYPRN_MVP_RESULT_V' + result_schema_version + ' '
    lines = [
        line[len(prefix) :] for line in envelope['output'].splitlines() if line.startswith(prefix)
    ]
    if len(lines) != 1 or any(
        line.startswith('HYPRN_MVP_RESULT_V') and not line.startswith(prefix)
        for line in envelope['output'].splitlines()
    ):
        raise ValueError('Ambiguous worker result')
    result = bounded_json(lines[0])
    if (
        result_schema_version not in ('1', '2', '3')
        or result['schema_version'] != result_schema_version
        or any(result[key] != request[key] for key in ('run_id', 'bundle_digest'))
    ):
        raise ValueError('Result identity mismatch')
    fields = {
        'schema_version',
        'run_id',
        'bundle_digest',
        'execution',
        'outputs',
        'artifacts',
    }
    # Protocol 3 records execution and outputs only; criteria belong to calculations.
    if result_schema_version in ('1', '2'):
        fields.add('criteria')
    if result_schema_version == '1':
        fields |= {'convergence', 'optimization', 'completeness', 'applicability'}
    if set(result) != fields:
        raise ValueError('Unexpected result field')
    if model.get('schema_version') not in ('1', '2', '3', '4'):
        raise ValueError('Unsupported result model version')
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    if len(definitions) != len(model['definitions']) or len(
        {i['instance_id'] for i in model['instances']}
    ) != len(model['instances']):
        raise ValueError('Ambiguous result model inventory')
    if model['schema_version'] == '4':
        flattened = []
        for d in definitions.values():
            ports = d['ports']
            ids = {p['port_id'] for p in ports}
            if len(ids) != len(ports) or len({isinstance(p['units'], str) for p in ports}) > 1:
                raise ValueError('Ambiguous retained definition')
            descriptions = d.get('quantity_definitions', [])
            seen_descriptions = set()
            if not isinstance(descriptions, list) or len(descriptions) > 1000:
                raise ValueError('Quantity bound')
            for q in descriptions:
                if (
                    set(q) != {'port_id', 'statement'}
                    or q['port_id'] not in ids
                    or q['port_id'] in seen_descriptions
                    or not isinstance(q['statement'], str)
                    or not q['statement'].strip()
                    or len(q['statement']) > 4096
                ):
                    raise ValueError('Invalid retained quantity definition')
                seen_descriptions.add(q['port_id'])
            for p in ports:
                if p['definition_version_id'] != d['definition_version_id']:
                    raise ValueError('Retained port owner')
                if p['units'] != {'kind': 'unspecified'}:
                    _result_unit(p['units'], '4')
            flattened.extend(ports)
        if flattened != model['ports']:
            raise ValueError('Retained port aggregate')
    for instance in model['instances']:
        definition = definitions[instance['definition_version_id']]
        if len({p['port_id'] for p in definition['ports']}) != len(definition['ports']):
            raise ValueError('Ambiguous result port inventory')
        for p in definition['ports']:
            if p['definition_version_id'] != definition['definition_version_id']:
                raise ValueError('Result port owner mismatch')
            if model['schema_version'] in ('3', '4'):
                _result_unit(p['units'], model['schema_version'])
    expected = {
        (i['instance_id'], p['port_id']): _result_unit(p['units'], model['schema_version'])
        for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports']
        if p['direction'] == 'output'
    }
    seen = set()
    for output in result['outputs']:
        if set(output) != {
            'target',
            'value',
            'units',
            'availability',
            'reason',
            'producer_completed',
            'assigned',
        }:
            raise ValueError('Unexpected output field')
        if set(output['target']) != {'instance_id', 'port_id'}:
            raise ValueError('Invalid target')
        target = (output['target']['instance_id'], output['target']['port_id'])
        if target in seen or target not in expected or output['units'] != expected[target]:
            raise ValueError('Output inventory mismatch')
        seen.add(target)
        if type(output['producer_completed']) is not bool or type(output['assigned']) is not bool:
            raise ValueError('Invalid completion evidence')
        if output['availability'] == 'available':
            if (
                not output['producer_completed']
                or not output['assigned']
                or output['reason'] is not None
                or type(output['value']) not in (int, float)
                or not math.isfinite(output['value'])
            ):
                raise ValueError('Invalid available value')
        elif (
            output['availability'] != 'unavailable'
            or output['value'] is not None
            or not isinstance(output['reason'], str)
        ):
            raise ValueError('Unavailable output must be explicit')
    if seen != set(expected):
        raise ValueError('Missing output record')
    available = sum(o['availability'] == 'available' for o in result['outputs'])
    if result_schema_version == '1':
        if result['completeness'] != dict(
            expected=len(expected),
            available=available,
            failed=sum(not o['producer_completed'] for o in result['outputs']),
            unavailable=len(expected) - available,
        ):
            raise ValueError('Inconsistent completeness')
        if result['applicability'] != dict(state='unassessed', evidence_refs=[]):
            raise ValueError('Untrusted scientific evidence claim')
        if result['convergence'] != dict(state='not_applicable', diagnostics_ref=None) or result[
            'optimization'
        ] != dict(termination='not_applicable', feasibility='not_applicable'):
            raise ValueError('Unsupported numerical status')
    # This workload has no candidate-produced files.
    if result['artifacts']:
        raise ValueError('Untrusted scientific evidence claim')
    execution = result['execution']
    if (
        set(execution) != {'state', 'exit_code', 'message'}
        or execution['state'] not in ('finished', 'failed')
        or type(execution['exit_code']) is not int
        or execution['exit_code'] != (0 if execution['state'] == 'finished' else 1)
        or not isinstance(execution['message'], str)
        or len(execution['message']) > 4096
        or (execution['state'] == 'finished' and available != len(expected))
    ):
        raise ValueError('Invalid execution status')
    return result


class UnsupportedRecordVersion(ValueError):
    """A retained record remains intact but cannot be interpreted by this reader."""

    code = 'unsupported_record_version'


def read_stored_result(result, request, model, assessment=None, *, result_schema_version=None):
    """Read recorded outcomes as data; never recompute using today's evaluator."""
    if result.get('schema_version') not in ('1', '2', '3'):
        raise UnsupportedRecordVersion('Unsupported retained result version')
    if result_schema_version is not None and result['schema_version'] != result_schema_version:
        raise ValueError('Retained result does not match its bundle protocol')
    if result['schema_version'] == '3' and assessment is not None:
        raise ValueError('Result protocol 3 has no criterion evaluator')
    if assessment is not None and assessment.get('version') != 'fixed-threshold-1':
        raise UnsupportedRecordVersion('Unsupported retained assessment version')
    raw = json.dumps(
        dict(
            reason='exited',
            exit_code=0,
            output='HYPRN_MVP_RESULT_V'
            + result['schema_version']
            + ' '
            + json.dumps(result, allow_nan=False),
        ),
        allow_nan=False,
    )
    return validate_result(raw, request, model, result_schema_version=result['schema_version'])


def _prepared_v1(manifest, prepared, files):
    if prepared.get('schema_version') != '1':
        raise UnsupportedRecordVersion('Unsupported retained artifact version for bundle1')
    # Historical graph material is evidence only. No current execution validator
    # or graph compiler is called, and older assessments are never recalculated.
    if manifest['generator'] != prepared['generator_identity']:
        raise ValueError('Retained generator mismatch')


def _prepared_v2(manifest, prepared, files):
    if prepared.get('schema_version') not in ('2', '3', '4'):
        raise UnsupportedRecordVersion('Unsupported retained artifact version for bundle2/3/4')
    if manifest['generator'] != prepared['generator_identity']:
        raise ValueError('Retained generator mismatch')
    for key in ('entrypoint', 'executable_content_digest', 'result_protocol_version'):
        if manifest[key] != prepared[key]:
            raise ValueError('Retained program binding mismatch')
    entry = prepared['entrypoint']
    if entry['protocol'] != 'hyprn_mvp.openmdao.program/1' or (
        prepared['schema_version'],
        prepared['result_protocol_version'],
    ) not in (('2', '1'), ('3', '2'), ('4', '3')):
        raise UnsupportedRecordVersion('Unsupported retained program or result protocol')
    for key in ('module_path', 'bindings_path', 'source_map_path'):
        if entry[key] not in files:
            raise ValueError('Missing retained program file')


def retained_bundle(repository, request):
    """Read bounded AiiDA repository bytes and verify the immutable request pin."""
    from hyprn_mvp_app.contracts import canonical, check_digest
    from hyprn_mvp_app.execution_bundle import verify_files, safe_path, MAX_BYTES

    with repository.open('manifest.json', mode='rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    manifest = artifact_json(raw)
    readers = {
        '1': _prepared_v1,
        '2': _prepared_v2,
        '3': _prepared_v2,
        '4': _prepared_v2,
        '5': _prepared_v2,
        '6': _prepared_v2,
        '8': _prepared_v2,
        '10': _prepared_v2,
        '11': _prepared_v2,
    }
    reader = readers.get(manifest.get('schema_version'))
    if reader is None:
        raise UnsupportedRecordVersion('Unsupported retained bundle version')
    from hyprn_mvp_app.execution_bundle import bundle_layout

    layout = bundle_layout(manifest)
    manifest_fields = {
        'schema_version',
        'bundle_id',
        'run_id',
        'prepared_digest',
        'model_revision_id',
        'configuration_revision_id',
        'model_digest',
        'configuration_digest',
        'files',
        'generator',
        'dependencies',
        'runtime',
        'required_capabilities',
        'licenses',
        'result_protocol_version',
        'bundle_digest',
    }
    if layout in ('2', '3', '4', '5', '6', '8', '9', '11'):
        manifest_fields |= {'entrypoint', 'executable_content_digest'}
    if layout in ('3', '4', '5', '6', '8', '9', '11'):
        manifest_fields |= {'modeling_configuration_digest', 'result_dependencies'}
    if layout in ('5', '6', '8', '9'):
        manifest_fields |= {'approach_digest', 'approach_closure_digest'}
    if layout in ('8', '9', '11'):
        manifest_fields.add('model_schema_version')
    if manifest['schema_version'] in ('10', '11'):
        manifest_fields.add('input_schema_version')
    if set(manifest) != manifest_fields:
        raise ValueError('Unexpected retained manifest fields')
    if manifest['result_protocol_version'] != {'10': '2', '11': '3'}.get(manifest['schema_version'], '1'):
        raise UnsupportedRecordVersion('Unsupported retained result protocol')
    check_digest(manifest, 'bundle_digest')
    if any(manifest[k] != request[k] for k in ('run_id', 'bundle_digest')):
        raise ValueError('Native request/bundle mismatch')
    files = {}
    if len(manifest['files']) > 2000:
        raise ValueError('File count exceeded')
    total = 0
    for item in manifest['files']:
        safe_path(item['path'])
        size = item['size']
        if type(size) is not int or not 0 <= size <= 32 * 1024 * 1024:
            raise ValueError('Invalid artifact size')
        total += size
        if total > 32 * 1024 * 1024:
            raise ValueError('Bundle size exceeded')
        with repository.open(item['path'], mode='rb') as stream:
            files[item['path']] = stream.read(size + 1)
    verify_files(manifest['files'], files)
    if layout in ('3', '4', '5', '6', '8', '9', '11'):
        # Data-only validation, imported here so worker results1 remains stdlib
        # at import time. No runtime attestation, native lookup or model fetch.
        from hyprn_mvp_app.execution_bundle import validate_retained_bundle

        reader(manifest, artifact_json(files['preparation.json']), files)
        model = artifact_json(files['model.json'])
        config = artifact_json(files['configuration.json'])
        if config['study_id'] != request['scope']:
            raise ValueError('Retained study mismatch')
        bundle = dict(manifest=manifest, files=files)
        frozen = dict(configuration=config, model_snapshot=model)
        if config['schema_version'] == '4':
            frozen['approach_closure'] = (
                artifact_json(files['approach/closure.json'])
                if 'approach/closure.json' in files
                else None
            )
        validate_retained_bundle(bundle, request, frozen, raw_snapshot=True)
        return bundle
    prepared = artifact_json(files['preparation.json'])
    prepared_fields = {
        'schema_version',
        'preparation_id',
        'model_id',
        'model_revision_id',
        'model_digest',
        'configuration_revision_id',
        'configuration_digest',
        'required_capabilities',
        'generator_identity',
        'dependency_requirements',
        'model_package_manifest',
        'files',
        'license_notices',
        'prepared_digest',
    }
    if layout == '2':
        prepared_fields |= {'entrypoint', 'executable_content_digest', 'result_protocol_version'}
    if set(prepared) != prepared_fields:
        raise ValueError('Unexpected retained preparation fields')
    check_digest(prepared, 'prepared_digest')
    if manifest['prepared_digest'] != prepared['prepared_digest']:
        raise ValueError('Retained preparation mismatch')
    verify_files(
        prepared['files'], {item['path']: files[item['path']] for item in prepared['files']}
    )
    reader(manifest, prepared, files)
    model = artifact_json(files['model.json'])
    config = artifact_json(files['configuration.json'])
    check_digest(model)
    check_digest(config)
    for key, value in dict(
        model_digest=model['digest'],
        configuration_digest=config['digest'],
        model_revision_id=model['model_revision_id'],
        configuration_revision_id=config['configuration_revision_id'],
    ).items():
        if manifest[key] != value or prepared[key] != value:
            raise ValueError('Scientific snapshot mismatch')
    if files['context.json'] != canonical(config['context_snapshot']) or files[
        'evidence/index.json'
    ] != canonical(config['evidence_snapshots']):
        raise ValueError('Evidence snapshot mismatch')
    return dict(manifest=manifest, files=files)
