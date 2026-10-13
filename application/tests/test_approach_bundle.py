"""Bundle5 data admission; captured generation fixtures are synthetically resealed."""
from copy import deepcopy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integration/tests'))
from test_assumptions_execution import case4, repin, assembled
from test_approach_closure import sample,D,link,signed,resolution
from hyprn_mvp_app.approach_closure import build_closure
from hyprn_mvp_app.execution import validate_retained_bundle,validate_frozen_configuration,StaticPreparation
from hyprn_mvp_app.store import canonical,uid
from hyprn_mvp_integration.launcher import verify_execution_bundle
from execution_fixtures import runtime_fixture
from test_result_dependencies import rehash

def case5(linked=True,sid=None):
    case,deps=case4();f=case['frozen'];c=f['configuration'];m=f['model_snapshot']
    if sid:
        c['study_id']=sid
        for e in c['evidence_snapshots']:
            e['study_id']=sid;e['resource_scope']['study_id']=sid
            e['recorded_context']['resource_labels'][0]['resource_id']=sid
    m['root_instance_id']=m['instances'][0]['instance_id'];m['assumptions']=m['assumptions'][:1]
    m['ports']=[p for d in m['definitions'] for p in d['ports']]
    c.update(schema_version='4',approach_binding=None);f.update(schema_version='4',approach_closure=None)
    repin(case)
    if linked:
        v=sample(D['ApproachVersion1']);v['study_id']=c['study_id'];b,_=link(v,m)
        cs=sample(D['ApproachCase1']);cs['binding_id']=b['binding_id'];v['content']['cases']=[cs];signed(v)
        closure=build_closure(v,resolution(models=[m],evidence=c['evidence_snapshots']),study_id=c['study_id'])
        f['approach_closure']=closure
        c['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest=closure['digest'],case_id=cs['case_id'])
        repin(case)
    return case,deps

@pytest.mark.parametrize('linked',[False,True])
def test_exact_bundle5_retained_offline_and_private3(linked):
    case,deps=case5(linked);bundle,request=assembled(case,deps);m=bundle['manifest'];f=case['frozen']
    assert m['schema_version']=='5'
    assert ('approach/closure.json' in bundle['files'])==linked
    assert m['approach_closure_digest']==(f['approach_closure']['digest'] if linked else None)
    assert json.loads(bundle['files']['modeling-configuration.json'])['schema_version']=='3'
    assert 'approach_binding' not in json.loads(bundle['files']['modeling-configuration.json'])
    validate_retained_bundle(bundle,request,f)
    verify_execution_bundle(bundle,request,runtime_fixture())

@pytest.mark.parametrize('change',['missing','field','digest','root','family','case','model','foreign','source','null_case_binding','unused_binding'])
def test_invalid_pin_rejected_before_modeling_call(change):
    case,_=case5();f=case['frozen'];c=f['configuration']
    if change=='missing':f['approach_closure']=None
    elif change=='field':del f['approach_closure']
    elif change=='digest':c['approach_binding']['closure_digest']='f'*64;signed(c)
    elif change=='root':c['approach_binding']['approach_version_id']=uid();signed(c)
    elif change=='family':c['approach_binding']['approach_id']=uid();signed(c)
    elif change=='case':c['approach_binding']['case_id']=uid();signed(c)
    elif change=='model':f['model_snapshot']['name']='Changed';signed(f['model_snapshot'])
    elif change=='foreign':c['study_id']=uid();signed(c)
    elif change=='source':f['model_snapshot']['source_files'][0]['bytes']='eA==';signed(f['model_snapshot'])
    else:
        v=deepcopy(f['approach_closure']['approach_versions'][0])
        if change=='null_case_binding':v['content']['cases'][0]['binding_id']=None
        else:
            v['content']['steps']=[];c['approach_binding']['case_id']=None
        signed(v)
        if change=='unused_binding':
            # Intentionally malformed but correctly rehashed: the builder
            # itself rejects this, so mutate the retained envelope directly.
            closure=deepcopy(f['approach_closure']);closure['approach_versions']=[v]
            closure['root_approach_digest']=v['digest'];signed(closure)
        else:closure=build_closure(v,resolution(models=[f['model_snapshot']],evidence=c['evidence_snapshots']),study_id=c['study_id'])
        f['approach_closure']=closure;c['approach_binding'].update(approach_digest=v['digest'],closure_digest=closure['digest']);signed(c)
    class Unavailable:
        def call(self,*args,**kwargs):pytest.fail('Invalid retained pin crossed modeling boundary')
    with pytest.raises(ValueError):validate_frozen_configuration(f)
    with pytest.raises(ValueError):StaticPreparation(Unavailable())(uid(),c['study_id'],uid(),f)

@pytest.mark.parametrize('change',['raw','manifest_pin','role','extra_role','config','extra_unlinked'])
def test_resealed_bundle_tampering_rejected(change):
    case,deps=case5(change!='extra_unlinked');bundle,request=assembled(case,deps)
    if change=='raw':bundle['files']['approach/closure.json']+=b' '
    elif change=='manifest_pin':bundle['manifest']['approach_digest']='f'*64;rehash(bundle,{})
    elif change=='role':
        next(x for x in bundle['manifest']['files'] if x['path']=='approach/closure.json')['role']='evidence';rehash(bundle,{})
    elif change=='extra_role':
        next(x for x in bundle['manifest']['files'] if x['path']=='context.json')['role']='approach';rehash(bundle,{})
    elif change=='config':
        config=deepcopy(case['frozen']['configuration']);config['approach_binding']['case_id']=uid();signed(config)
        rehash(bundle,{'configuration.json':config})
    else:
        raw=b'{}';bundle['files']['approach/closure.json']=raw
        from hyprn_mvp_app.execution import raw_hash
        bundle['manifest']['files'].append(dict(path='approach/closure.json',size=2,sha256=raw_hash(raw),media_type='application/json',role='approach'));rehash(bundle,{})
    request['bundle_digest']=bundle['manifest']['bundle_digest']
    with pytest.raises(ValueError):verify_execution_bundle(bundle,request,runtime_fixture())

@pytest.mark.parametrize('version',['1','2','3'])
def test_existing_bundle_readers_keep_exact_bytes(version):
    from test_assumptions_execution import legacy_pairing_case
    if version=='3':
        case,deps=case4();bundle,request=assembled(case,deps)
    else:case,bundle,request=legacy_pairing_case(version)
    before=deepcopy(bundle)
    verify_execution_bundle(bundle,request,runtime_fixture())
    assert bundle==before and bundle['manifest']['schema_version']==str(int(version)+1)
