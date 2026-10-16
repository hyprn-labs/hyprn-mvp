"""Read-only proof against retained records of the test's own scratch scope; no calculation is
launched. The retained records are those written in the same scope by
``test_results.py::test_real_native_criteria_and_failed_raw_artifacts_are_retained``."""
import copy
import json
import pytest
from execution_fixtures import scoped_evidence_root

def evidence(name,record,count):
    from hyprn_mvp_app.store import digest
    from hyprn_mvp_app.execution import raw_hash
    summary=dict(request=record['request'],association={k:record[k] for k in ('store_uuid','process_uuid')},
        bundle_digest=record['bundle']['manifest']['bundle_digest'],bundle_version=record['bundle']['manifest']['schema_version'],
        results_digest=digest(record['results']),assessment=record['assessment'],
        artifacts={p:raw_hash(raw) for p,raw in record['artifacts'].items()},node_count=count,candidate_executions=0)
    (scoped_evidence_root()/('read-'+name+'.json')).write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')


@pytest.fixture
def retained_native():
    from execution_fixtures import scoped_native_runtime
    native=scoped_native_runtime()
    retained=sorted(scoped_evidence_root().glob('retained-throw-*/record.json'))
    assert len(retained)==1, 'Exactly one retained failed record of this scope is required; it is never looked up elsewhere'
    record=json.loads(retained[0].read_text())
    return native,record['request'],{k:record['native'][k] for k in ('store_uuid','process_uuid')}


def test_actual_retained_failed_record_exact_results_and_artifacts(retained_native,monkeypatch):
    from aiida import orm
    from hyprn_mvp_integration import results
    from hyprn_mvp_app.dispatcher import encode_record,decode_record
    native,request,association=retained_native
    def forbidden(*args,**kwargs):raise AssertionError('History attempted scientific work')
    for name in ('launch','require_attestation','bundle_runtime','matches'):
        monkeypatch.setattr(native,name,forbidden)
    monkeypatch.setattr(results,'evaluate_criteria',forbidden)
    node=orm.load_node(association['process_uuid'])
    count=orm.QueryBuilder().append(orm.CalcJobNode).count()
    before=node.outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')
    record=native.read_record(request,association)
    assert record['request']==request and record['results']==node.outputs.results.get_dict()
    assert record['assessment']==node.outputs.assessment.get_dict()
    retained_manifest = json.loads(
        node.inputs.frozen_bundle.base.repository.get_object_content('manifest.json')
    )
    assert record['bundle']['manifest'] == retained_manifest and not record['errors']
    outputs=record['results']['outputs']
    assert sorted(o['value'] for o in outputs if o['availability']=='available')==[7]
    assert [o['value'] for o in outputs if o['availability']=='unavailable']==[None]
    assert record['artifacts']['result.json']==before and b'RuntimeError' in before
    assert decode_record(encode_record(record))==record
    assert orm.QueryBuilder().append(orm.CalcJobNode).count()==count
    assert node.outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')==before
    evidence('retained-failure',record,count)


@pytest.mark.parametrize('field',['store_uuid','process_uuid','run_id','scope','command_id','payload_digest','bundle_digest','extra'])
def test_native_read_rejects_every_forged_association_before_bytes(retained_native,field):
    native,request,association=retained_native
    request=copy.deepcopy(request);association=copy.deepcopy(association)
    if field in association:association[field]='00000000-0000-0000-0000-000000000000'
    elif field=='extra':request[field]='forged'
    else:request[field]='forged'
    with pytest.raises(ValueError):native.read_record(request,association)


def test_actual_schema1_remains_data_only_and_byte_identical(retained_native,monkeypatch):
    from aiida import orm
    from hyprn_mvp_integration import results
    native,_,_=retained_native
    def forbidden(*args,**kwargs):raise AssertionError('Historical record was executed or reassessed')
    for name in ('launch','require_attestation','bundle_runtime','matches'):
        monkeypatch.setattr(native,name,forbidden)
    monkeypatch.setattr(results,'evaluate_criteria',forbidden)
    nodes=orm.QueryBuilder().append(orm.CalcJobNode,filters={'process_type':'aiida.calculations:hyprn_mvp.scalar'},project='*').all()
    count=len(nodes)
    for (node,) in nodes:
        repo=node.inputs.frozen_bundle.base.repository
        manifest=repo.get_object_content('manifest.json',mode='rb')
        if json.loads(manifest)['schema_version']!='1' or 'results' not in node.outputs:continue
        request=node.inputs.request.get_dict()
        record=native.read_record(request,dict(store_uuid=native.store_uuid,process_uuid=node.uuid))
        assert record['bundle']['manifest']['schema_version']=='1'
        assert record['results']==node.outputs.results.get_dict()
        assert not record['errors']
        assert repo.get_object_content('manifest.json',mode='rb')==manifest
        assert all(repo.get_object_content(p,mode='rb')==raw for p,raw in record['bundle']['files'].items())
        evidence('schema1',record,count)
        break
    else:pytest.fail('Missing retained schema1 record in the new store')
    assert len(orm.QueryBuilder().append(orm.CalcJobNode,filters={'process_type':'aiida.calculations:hyprn_mvp.scalar'},project='*').all())==count
