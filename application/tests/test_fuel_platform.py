"""Isolated regressions for deployed fuel-study boundary defects; no calculations."""
from copy import deepcopy
import json
import pytest
from hyprn_mvp_app.store import uid, DomainError
from hyprn_mvp_app.modeling import validate, VALIDATORS
from hyprn_mvp_app.approach import Approaches
from test_assumption_authoring import env
from test_approach_service import run_env, content, req, signed


@pytest.mark.parametrize('version', ['1', '2'])
def test_public_model_preview_accepts_projected_revision_without_writing(env, version):
    e=env;transport=e['transport'];original=transport.__call__
    if version=='1':
        transport.draft.pop('assumptions');transport.draft['schema_version']='1'
    before=deepcopy(transport.draft)
    def native_projection(method,path,raw,headers):
        status,response=original(method,path,raw,headers)
        if path.endswith('/preview'):response['data']['draft_revision']=uid()
        return status,response
    e['coord'].model.transport=native_projection
    body=dict(expected_revision=before['draft_revision'],edits=[])
    if version=='2':body['schema_version']='2'
    url=f"/api/1/studies/{e['sid']}/models/{e['mid']}/preview"
    response=e['client'].post(url,json=body)
    assert response.status_code==200,response.text
    assert response.json()['data']['draft_revision']!=before['draft_revision']
    assert transport.draft==before
    body['expected_revision']=uid()
    assert e['client'].post(url,json=body).status_code==409
    assert transport.draft==before


@pytest.mark.parametrize('representation', ['hex','dashed'])
def test_run_basis_retains_exact_native_store_representation(run_env,representation):
    e=run_env;identity=uid()
    if representation=='hex':identity=identity.replace('-','')
    with e['store'].connection(write=True) as db:
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(e['rid'],)).fetchone()[0])
        payload['history']['association']['store_uuid']=identity;signed(payload['history'])
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),e['rid']))
        db.execute('UPDATE run_associations SET store_uuid=? WHERE run_id=?',(identity,e['rid']))
    c=content();c['basis_refs']=[dict(kind='run',run_id=e['rid'],reason='Prior experiment',relation='context')]
    preview=Approaches(e['store'],None).preview(e['actor'],e['sid'],req(c))
    assert preview['resolved']['run_contexts'][0]['association']['store_uuid']==identity
    with e['store'].connection() as db:
        assert json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(e['rid'],)).fetchone()[0])==payload


@pytest.mark.parametrize('identity', ['92bb47fc2cd942bea79f1966425973a4','92bb47fc-2cd9-42be-a79f-1966425973a4'])
def test_archive_request_accepts_exact_native_repository_identity(identity):
    from test_approach_closure import sample,D
    value=sample(D['ArchiveRecordRequest1'])
    item=sample(D['ArchiveRecordRequest1']['properties']['computations']['items'])
    item['association']['store_uuid']=identity;value['computations']=[item]
    validate('ArchiveRecordRequest1',value)


@pytest.mark.parametrize('identity', ['92BB47FC2CD942BEA79F1966425973A4','{92bb47fc-2cd9-42be-a79f-1966425973a4}','urn:uuid:92bb47fc-2cd9-42be-a79f-1966425973a4','g'*32,'0'*31,'0'*33]+[value+suffix for value in ('92bb47fc2cd942bea79f1966425973a4','92bb47fc-2cd9-42be-a79f-1966425973a4') for suffix in ('\n','\r\n',' ','\t')])
@pytest.mark.parametrize('schema',['ApproachRunContext1','ArchiveRecordRequest1'])
def test_native_store_contract_rejects_noncanonical_or_malformed_forms(identity,schema):
    from test_approach_closure import sample,D
    value=sample(D[schema])
    if schema=='ArchiveRecordRequest1':
        item=sample(D[schema]['properties']['computations']['items']);value['computations']=[item]
    else:item=value
    item['association']['store_uuid']=identity
    with pytest.raises(DomainError):validate(schema,value)


def test_retained_byte_limit_is_actionable_before_allocating_export(run_env,tmp_path,monkeypatch):
    from hyprn_mvp_app.computational_export import ComputationalRecords,LIMITS
    e=run_env;service=ComputationalRecords(e['store'],tmp_path/'exports')
    monkeypatch.setitem(LIMITS,'expanded_bytes',1)
    with pytest.raises(DomainError) as error:
        service.enqueue_preview(e['actor'],e['sid'],dict(command_id=uid(),selected_run_ids=[e['rid']]))
    assert error.value.status==413
    assert error.value.fields[0]['code']=='expanded_bytes_limit'
    assert 'required computational ancestors cannot be omitted' in error.value.fields[0]['message']
    with e['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM computational_record_requests').fetchone()[0]==0


def test_pending_export_limit_has_distinct_recovery_and_replay(run_env,tmp_path):
    from hyprn_mvp_app.computational_export import ComputationalRecords
    e=run_env;service=ComputationalRecords(e['store'],tmp_path/'exports')
    body=dict(command_id=uid(),selected_run_ids=[e['rid']])
    first=service.enqueue_preview(e['actor'],e['sid'],body)
    for _ in range(7):service.enqueue_preview(e['actor'],e['sid'],dict(body,command_id=uid()))
    with pytest.raises(DomainError) as error:service.enqueue_preview(e['actor'],e['sid'],dict(body,command_id=uid()))
    assert error.value.fields[0]['code']=='pending_requests_limit'
    assert service.enqueue_preview(e['actor'],e['sid'],body)==first


def test_async_limit_keeps_only_curated_diagnostics(run_env,tmp_path,monkeypatch):
    from hyprn_mvp_app.computational_export import ComputationalRecords,LIMITS
    e=run_env;service=ComputationalRecords(e['store'],tmp_path/'exports')
    q=service.enqueue_preview(e['actor'],e['sid'],dict(command_id=uid(),selected_run_ids=[e['rid']]))
    monkeypatch.setitem(LIMITS,'expanded_bytes',1)
    assert service.process_one(lambda _:pytest.fail('Limit must reject before native export'))
    error=service.status(e['actor'],e['sid'],q['request_id'])['error']
    assert error['code']=='limit_exceeded' and error['fields'][0]['code']=='expanded_bytes_limit'


def test_backend_limit_cannot_leak_arbitrary_fields(run_env,tmp_path):
    from hyprn_mvp_app.computational_export import ComputationalRecords
    e=run_env;service=ComputationalRecords(e['store'],tmp_path/'exports')
    q=service.enqueue_preview(e['actor'],e['sid'],dict(command_id=uid(),selected_run_ids=[e['rid']]))
    def native(_):
        raise DomainError('limit_exceeded',413,fields=[dict(path='/private/secrets',code='expanded_bytes_limit',message='sensitive backend path',element_ref=None)])
    assert service.process_one(native)
    error=service.status(e['actor'],e['sid'],q['request_id'])['error']
    assert error['fields']==[]
