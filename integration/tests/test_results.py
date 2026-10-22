"""Recorded criterion outcomes are computed from verified data, never expressions."""
import copy
import pytest
from test_native_parser import record, envelope


@pytest.mark.parametrize('operator,threshold,outcome', [
    ('lt', 4, 'met'), ('le', 3, 'met'), ('eq', 3, 'met'),
    ('ge', 3, 'met'), ('gt', 4, 'violated'),
])
def test_fixed_criterion_operator_uses_verified_output(operator, threshold, outcome):
    from hyprn_mvp_integration.results import evaluate_criteria, validate_result
    case, request, result = record()
    criterion = dict(criterion_id='criterion', target=result['outputs'][0]['target'],
                     operator=operator, threshold=threshold, units='', evidence_version_ids=[])
    result['criteria'] = [dict(criterion_id='criterion', outcome='unresolved', reason='evaluation_pending')]
    assessed = validate_result(envelope(result), request, case['frozen']['model_snapshot'])
    assessed['criteria'] = evaluate_criteria(assessed, [criterion])
    assert assessed['criteria'] == [dict(criterion_id='criterion', outcome=outcome, reason='threshold_comparison')]
    assert assessed['applicability']['state'] == 'unassessed'


@pytest.mark.parametrize('mode,reason', [('unavailable','required_output_unavailable'),
    ('nonconverged','convergence_unresolved'), ('units','invalid_criterion_or_units'),
    ('expression','invalid_criterion_or_units'), ('tolerance','invalid_criterion_or_units')])
def test_absent_or_invalid_evidence_never_meets_criterion(mode, reason):
    from hyprn_mvp_integration.results import evaluate_criteria, validate_criteria
    case, request, result = record()
    criterion = dict(criterion_id='c', target=result['outputs'][0]['target'], operator='eq', threshold=3, units='')
    if mode == 'unavailable':result['outputs'][0].update(value=None, availability='unavailable')
    if mode == 'nonconverged':result['convergence']['state']='not_converged'
    if mode == 'units':criterion['units']='m'
    if mode == 'expression':criterion['operator']='__import__("os")'
    if mode == 'tolerance':criterion['absolute_tolerance']=-1
    result['criteria']=evaluate_criteria(result,[criterion])
    assert result['criteria']==[dict(criterion_id='c',outcome='unresolved',reason=reason)]
    validate_criteria(result,{'criteria':[criterion]})
    result['criteria'][0].update(outcome='met',reason='threshold_comparison')
    with pytest.raises(ValueError):validate_criteria(result,{'criteria':[criterion]})


def test_equality_tolerance_is_explicit_and_strict_inequality_stays_strict():
    from hyprn_mvp_integration.results import evaluate_criteria
    _, _, result=record()
    criterion=dict(criterion_id='c',target=result['outputs'][0]['target'],operator='eq',threshold=3.01,units='',absolute_tolerance=.02)
    assert evaluate_criteria(result,[criterion])[0]['outcome']=='met'
    criterion.update(operator='gt',threshold=3)
    assert evaluate_criteria(result,[criterion])[0]['outcome']=='violated'


@pytest.mark.parametrize('raw', ['{', '', '[]', '{"reason":"exited","exit_code":0,"output":""}',
    '{"reason":"exited","exit_code":true,"output":""}'])
def test_truncated_missing_or_invalid_envelope_is_rejected(raw):
    from hyprn_mvp_integration.results import validate_result
    case,request,_=record()
    with pytest.raises((ValueError,KeyError,TypeError)):
        validate_result(raw,request,case['frozen']['model_snapshot'])


def retained_record(version):
    """Inert retained manifest fixture; never passed to an execution API."""
    from execution_fixtures import fixture,legacy_fixture,uid,raw_hash,runtime_fixture
    from hyprn_mvp_app.store import canonical,digest
    from test_execution import assemble
    if version=='2':return assemble()
    if version == '10':
        case = fixture()
        prepared = case['prepared']
        prepared.update(schema_version='3', result_protocol_version='2')
        prepared['prepared_digest'] = digest(
            {k: v for k, v in prepared.items() if k != 'prepared_digest'}
        )
        return assemble(case)
    case=legacy_fixture();prepared=case['prepared'];config=case['frozen']['configuration'];selected=runtime_fixture()
    files={**case['files'],'preparation.json':canonical(prepared),'configuration.json':canonical(config),
           'context.json':canonical(config['context_snapshot']),'evidence/index.json':canonical(config['evidence_snapshots']),
           'licenses/model-notices.json':canonical(prepared['license_notices']),**selected['files']}
    manifest=dict(schema_version='1',bundle_id=uid(),run_id=uid(),generator=prepared['generator_identity'],
        runtime=selected['runtime'],dependencies=selected['dependencies'],required_capabilities=prepared['required_capabilities'],
        licenses=['licenses/model-notices.json',*selected['licenses']],result_protocol_version='1',
        prepared_digest=prepared['prepared_digest'],**{k:prepared[k] for k in ('model_digest','model_revision_id','configuration_digest','configuration_revision_id')},
        files=[dict(path=p,size=len(raw),sha256=raw_hash(raw)) for p,raw in sorted(files.items())])
    manifest['bundle_digest']=digest(manifest)
    return dict(manifest=manifest,files=files)


@pytest.mark.parametrize('large',['configuration','source','manifest'])
def test_large_accepted_artifacts_remain_readable_by_parser_and_history(large, monkeypatch):
    """Data-only mutations of a native fixture; these bytes are never executed."""
    import base64, io, json
    from execution_fixtures import fixture, uid, runtime_fixture
    from hyprn_mvp_app.execution import assemble_bundle, validate_retained_bundle, raw_hash, executable_digest
    from hyprn_mvp_app.store import canonical, digest
    from hyprn_mvp_integration import results
    case=fixture();prepared=case['prepared'];files=case['files'];selected=runtime_fixture()
    model=case['frozen']['model_snapshot'];config=case['frozen']['configuration']
    package=prepared['model_package_manifest']
    def rehash(value,key='digest'):value[key]=digest({k:v for k,v in value.items() if k!=key})
    if large=='configuration':config['context_snapshot']['notes']=['n'*4096 for _ in range(40)]
    if large=='source':
        source=model['source_files'][0];old=source['sha256'];raw=base64.b64decode(source['bytes'])+b'# inert padding\n'*9000
        new=raw_hash(raw);source.update(bytes=base64.b64encode(raw).decode(),sha256=new)
        for definition in model['definitions']:
            definition['source_refs']=[new if s==old else s for s in definition['source_refs']]
        del files['sources/'+old+'.py'];files['sources/'+new+'.py']=raw
        for item in prepared['files']:
            if item['path']=='sources/'+old+'.py':item['path']='sources/'+new+'.py'
        mapping=json.loads(files[prepared['entrypoint']['source_map_path']])
        for row in mapping['entries']:
            if row['source_sha256']==old:row.update(source_sha256=new,source_path='sources/'+new+'.py')
        files[prepared['entrypoint']['source_map_path']]=canonical(mapping)
        rehash(model);package['revisions'][-1]=model
        for item in package['files']:
            if item['path']=='sources/'+old+'.py':item.update(path='sources/'+new+'.py',size=len(raw),sha256=new)
            if item['path']=='revisions/'+model['model_revision_id']+'.json':item.update(size=len(canonical(model)),sha256=raw_hash(canonical(model)))
    if large=='manifest':
        selected['files'].update({f'licenses/extra-{i:04d}-'+('x'*80)+'.txt':b'notice' for i in range(700)})
    rehash(config);rehash(package)
    files['model.json']=canonical(model)
    for item in prepared['files']:item.update(size=len(files[item['path']]),sha256=raw_hash(files[item['path']]))
    prepared['files'].sort(key=lambda item:item['path'])
    prepared.update(model_digest=model['digest'],configuration_digest=config['digest'])
    prepared['executable_content_digest']=executable_digest(prepared);rehash(prepared,'prepared_digest')
    bundle=assemble_bundle(uid(),prepared,files,case['frozen'],selected)
    request={k:bundle['manifest'][k] for k in ('run_id','bundle_digest')}
    validate_retained_bundle(bundle,request,case['frozen'])
    raw={**bundle['files'],'manifest.json':canonical(bundle['manifest'])}
    target={'configuration':'configuration.json','source':'model.json','manifest':'manifest.json'}[large]
    assert len(raw[target])>131072
    if large=='source':assert len(raw['preparation.json'])>131072
    class Repository:
        def open(self,path,mode):return io.BytesIO(raw[path])
    # Parser and NativeExecution.read_record share this retained-input reader.
    monkeypatch.setattr(results,'evaluate_criteria',lambda *_:pytest.fail('History reassessed the result'))
    assert results.retained_bundle(Repository(),request)==bundle
    with pytest.raises(ValueError,match='Oversized result'):results.bounded_json(raw[target])


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'[1e999]',b'NaN',b'['*34+b'0'+b']'*34,
    b'['+b'0,'*2000+b'0]',b' '*((32*1024*1024)+1)])
def test_artifact_decoder_preserves_data_bounds(raw):
    from hyprn_mvp_integration.results import artifact_json
    with pytest.raises(ValueError):artifact_json(raw)


@pytest.mark.parametrize('version',['1','2','10'])
def test_retained_versions_read_without_worker_modeling_or_reassessment(monkeypatch,version):
    import builtins,io
    from hyprn_mvp_app.store import canonical
    from hyprn_mvp_integration import results
    bundle=retained_record(version);request={k:bundle['manifest'][k] for k in ('run_id','bundle_digest')}
    raw={**bundle['files'],'manifest.json':canonical(bundle['manifest'])}
    before=copy.deepcopy(raw)
    class Repository:
        def open(self,path,mode):return io.BytesIO(raw[path])
    original=builtins.__import__
    def blocked(name,*args,**kwargs):
        if any(s in name for s in ('worker','modeling','openmdao')):
            raise AssertionError('Runtime dependency during retained data read: '+name)
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',blocked)
    monkeypatch.setattr(results,'evaluate_criteria',lambda *_:pytest.fail('Recomputed retained assessment'))
    assert results.retained_bundle(Repository(),request)==bundle
    case,record_request,result=record()
    assert results.read_stored_result(result,record_request,case['frozen']['model_snapshot'],
                                     {'version':'fixed-threshold-1'})==result
    assert raw==before


@pytest.mark.parametrize('version',['1','2','10'])
@pytest.mark.parametrize('mode',['raw','request','snapshot','prepared_version','bundle_version','unissued_bundle_version','oversize','duplicate'])
def test_retained_reader_rejects_corruption_or_reports_unsupported(version,mode):
    import io,json
    from hyprn_mvp_app.store import canonical,digest
    from execution_fixtures import raw_hash
    from hyprn_mvp_integration.results import retained_bundle,UnsupportedRecordVersion
    bundle=retained_record(version);manifest=bundle['manifest'];files=bundle['files']
    if mode=='raw':files['model.json']+=b' '
    if mode=='snapshot':manifest['configuration_digest']='f'*64
    if mode=='prepared_version':
        prepared=json.loads(files['preparation.json']);prepared['schema_version']='99'
        prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
        files['preparation.json']=canonical(prepared);manifest['prepared_digest']=prepared['prepared_digest']
        d=next(d for d in manifest['files'] if d['path']=='preparation.json')
        d.update(size=len(files['preparation.json']),sha256=raw_hash(files['preparation.json']))
    if mode=='bundle_version':manifest['schema_version']='99'
    if mode=='unissued_bundle_version':manifest['schema_version']='9'
    if mode=='oversize':manifest['files'][0]['size']=33*1024*1024
    if mode=='duplicate':manifest['files'].append(manifest['files'][0])
    manifest['bundle_digest']=digest({k:v for k,v in manifest.items() if k!='bundle_digest'})
    request={k:manifest[k] for k in ('run_id','bundle_digest')}
    if mode=='request':request['bundle_digest']='f'*64
    class Repository:
        def open(self,path,mode):return io.BytesIO(canonical(manifest) if path=='manifest.json' else files[path])
    with pytest.raises(ValueError) as error:retained_bundle(Repository(),request)
    if mode in ('prepared_version','bundle_version','unissued_bundle_version'):
        assert isinstance(error.value,UnsupportedRecordVersion) and error.value.code=='unsupported_record_version'


@pytest.mark.parametrize('kind',['result','assessment'])
def test_unknown_stored_outcome_version_is_partial_diagnostic(kind):
    from hyprn_mvp_integration.results import read_stored_result,UnsupportedRecordVersion
    case,request,result=record();assessment={'version':'fixed-threshold-1'}
    if kind=='result':result['schema_version']='99'
    else:assessment['version']='future-evaluator'
    with pytest.raises(UnsupportedRecordVersion):
        read_stored_result(result,request,case['frozen']['model_snapshot'],assessment)


@pytest.mark.integration
@pytest.mark.parametrize('kind', ['units','throw'])
def test_real_native_criteria_and_failed_raw_artifacts_are_retained(kind):
    import hashlib
    import json
    from pathlib import Path
    from execution_fixtures import current_fixture as fixture,uid
    from hyprn_mvp_app.store import digest
    from hyprn_mvp_app.execution import assemble_bundle
    from execution_fixtures import scoped_native_runtime
    from aiida import orm
    runtime=scoped_native_runtime()  # The scope's own backend and attested worker only.
    attestation=runtime.require_attestation()
    case=fixture('units') if kind=='units' else fixture(downstream="outputs['y']=12\nraise RuntimeError('retained failure')\n")
    config=case['frozen']['configuration']
    if kind=='units':
        config['criteria']=[dict(criterion_id=uid(),target=case['targets']['distance']['travel'],operator='eq',threshold=2000,units='m',evidence_version_ids=[])]
    else:
        config['criteria']=[dict(criterion_id=uid(),target=case['targets'][name][port],operator='eq',threshold=value,units='',evidence_version_ids=[])
                            for name,port,value in [('linear','u',7),('square','y',12)]]
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    prepared=case['prepared'];prepared['configuration_digest']=config['digest']
    from hyprn_mvp_app.execution import executable_digest
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    bundle=assemble_bundle(uid(),prepared,case['files'],case['frozen'],runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=config['study_id'],command_id=uid(),payload_digest=digest({'case':kind}),bundle_digest=bundle['manifest']['bundle_digest'])
    native=runtime.launch(bundle,request)
    # Preserve exact failure bytes and identities before assertions, including
    # unsuccessful verification attempts. These are new-store evidence only.
    node=orm.load_node(native['process_uuid'])
    raw=node.outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')
    assessment=node.outputs.assessment.get_dict() if 'assessment' in node.outputs else None
    from execution_fixtures import scoped_evidence_root
    evidence=scoped_evidence_root()/('retained-'+kind+'-'+node.uuid)
    evidence.mkdir()
    (evidence/'result.json').write_bytes(raw)
    (evidence/'record.json').write_text(json.dumps(dict(request=request,native=native,
        assessment=assessment,attestation=attestation,manifest=bundle['manifest'],
        raw_sha256=hashlib.sha256(raw).hexdigest()),sort_keys=True,indent=2)+'\n')
    assert [c['outcome'] for c in native['results']['criteria']]==(['met'] if kind=='units' else ['met','unresolved'])
    from hyprn_mvp_integration import results
    assert assessment==dict(version='fixed-threshold-1',
        evaluator_sha256=hashlib.sha256(Path(results.__file__).read_bytes()).hexdigest())
    assert node.inputs.request.get_dict()==request
    assert {k:native['results'][k] for k in ('run_id','bundle_digest')}=={
        k:bundle['manifest'][k] for k in ('run_id','bundle_digest')}
    assert native['process_state']=='finished'
    assert native['results']['schema_version'] == '2'
    assert (
        not {'convergence', 'optimization', 'applicability', 'completeness'}
        & native['results'].keys()
    )
    assert b'HYPRN_MVP_RESULT_V2 ' in raw
    assert runtime.retained_bundle(node.uuid)==bundle
    envelope=json.loads(raw)
    origins=[json.loads(line.removeprefix('HYPRN_MVP_NATIVE_ORIGINS_V1 '))
        for line in envelope['output'].splitlines() if line.startswith('HYPRN_MVP_NATIVE_ORIGINS_V1 ')]
    assert len(origins)==1
    assert len(origins[0]['components'])==len(case['frozen']['model_snapshot']['instances'])
    classes=origins[0]['group']+[c for component in origins[0]['components'] for c in component['classes']]
    assert classes and all(c['path'].startswith('generated/') and
        c['sha256']==hashlib.sha256(bundle['files'][c['path']]).hexdigest() for c in classes)
    if kind=='throw':
        assert native['exit_status']==301
        by_target={(o['target']['instance_id'],o['target']['port_id']):o for o in native['results']['outputs']}
        upstream=by_target[tuple(case['targets']['linear']['u'][k] for k in ('instance_id','port_id'))]
        downstream=by_target[tuple(case['targets']['square']['y'][k] for k in ('instance_id','port_id'))]
        assert upstream['value']==7 and upstream['availability']=='available'
        assert downstream['value'] is None and downstream['availability']=='unavailable'
        assert downstream['assigned'] and not downstream['producer_completed']
        assert downstream['reason']=='producer_failed'
        assert native['results']['criteria'][1]['reason']=='required_output_unavailable'
        assert b'RuntimeError' in raw
    else:
        assert native['exit_status']==0
        assert [(o['value'],o['units'],o['availability']) for o in native['results']['outputs']]==[(2,'km','available')]
        assert native['results']['criteria'][0]['reason']=='threshold_comparison'
    assert (evidence/'result.json').read_bytes()==node.outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')


@pytest.mark.parametrize(
    'fault',
    [None, 'legacy_field', 'missing', 'duplicate', 'nonfinite', 'unassigned', 'wrong_protocol'],
)
def test_current_result_protocol_retains_scalar_guards_without_aggregate_status(fault):
    import json
    from hyprn_mvp_integration.results import validate_result, read_stored_result
    case, request, legacy = record()
    result = {k: copy.deepcopy(v) for k, v in legacy.items()
              if k not in {'convergence', 'optimization', 'completeness', 'applicability'}}
    result['schema_version'] = '2'
    if fault == 'legacy_field':result['applicability'] = legacy['applicability']
    if fault == 'missing':result['outputs'] = []
    if fault == 'duplicate':result['outputs'] *= 2
    if fault == 'nonfinite':result['outputs'][0]['value'] = float('inf')
    if fault == 'unassigned':result['outputs'][0]['assigned'] = False
    prefix = 'HYPRN_MVP_RESULT_V1 ' if fault == 'wrong_protocol' else 'HYPRN_MVP_RESULT_V2 '
    raw = json.dumps(dict(reason='exited', exit_code=0, output=prefix + json.dumps(result)))
    if fault:
        with pytest.raises(ValueError):
            validate_result(
                raw, request, case['frozen']['model_snapshot'], result_schema_version='2'
            )
    else:
        assert (
            validate_result(
                raw, request, case['frozen']['model_snapshot'], result_schema_version='2'
            )
            == result
        )
        assert read_stored_result(result, request, case['frozen']['model_snapshot']) == result
        assert read_stored_result(legacy, request, case['frozen']['model_snapshot']) == legacy
        with pytest.raises(ValueError):
            validate_result(raw, request, case['frozen']['model_snapshot'])
