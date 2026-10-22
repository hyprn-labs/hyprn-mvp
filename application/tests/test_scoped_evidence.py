"""Typed immutable evidence through authenticated API and isolated real model HTTP."""
from hyprn_mvp_app.contracts import authored_schema
import copy
import json
import os
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.store import Store, digest
from test_api import ORIGIN, post, uid, model4_revision, configuration_request, configuration_commit, study
from test_ui_discovery import api, private_http, scoped_evidence_root

ROOT = Path(__file__).resolve().parents[2]


def retained_criterion(store, sid):
    """A retained configuration 1 with one criterion, stored exactly as an earlier release saved
    it: criteria exist only on retained records, never on a configuration 6."""
    from execution_fixtures import fixture
    frozen = fixture('chain')['frozen']; config = frozen['configuration']; model = frozen['model_snapshot']
    output = next(dict(instance_id=i['instance_id'], port_id=p['port_id']) for i in model['instances']
                  for d in model['definitions'] if d['definition_version_id'] == i['definition_version_id']
                  for p in d['ports'] if p['direction'] == 'output')
    config.update(study_id=sid, configuration_id=uid(), configuration_revision_id=uid(),
                  criteria=[dict(criterion_id=uid(), target=output, operator='ge', threshold=0, units='', evidence_version_ids=[])])
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (config['configuration_revision_id'], config['configuration_id'], sid, json.dumps(frozen)))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)', (config['configuration_id'], sid, config['configuration_revision_id']))
        db.execute('INSERT INTO model_associations VALUES(?,?,?)', (sid, config['model_id'], uid()))
    return config


@pytest.fixture
def scoped(api):
    c, store = api[0], api[1]; s, model = model4_revision(api); sid = s['study_id']
    base = dict(scope_version='1', study_id=sid)
    binding = dict(base, model_id=model['model_id'], model_revision_id=model['model_revision_id'])
    definition = next(d for d in model['definitions'] if d['kind'] == 'explicit_component')
    instances = [i for i in model['instances'] if i['definition_version_id'] == definition['definition_version_id']]
    port = next(p for p in definition['ports'] if p['direction'] == 'output')
    cfg = configuration_request(api, s, model)
    frozen = post(c, f'/studies/{sid}/configurations', configuration_commit(api, cfg), 201)['data']
    assert frozen['configuration']['schema_version'] == '6' and 'criteria' not in frozen['configuration']
    revision = frozen['configuration']['configuration_revision_id']
    run = post(c, f'/studies/{sid}/runs', dict(command_id=uid(), configuration_revision_id=revision), 202)['data']
    retained = retained_criterion(store, sid)
    scopes = dict(
        study=dict(base, kind='study'), model_revision=dict(binding, kind='model_revision'),
        definition_version=dict(binding, kind='definition_version', definition_id=definition['definition_id'], definition_version_id=definition['definition_version_id']),
        instance=dict(binding, kind='instance', instance_id=instances[0]['instance_id']),
        port=dict(binding, kind='port', instance_id=instances[0]['instance_id'], port_id=port['port_id']),
        connection=dict(binding, kind='connection', connection_id=model['connections'][0]['connection_id']),
        configuration=dict(base, kind='configuration', configuration_revision_id=revision),
        run=dict(base, kind='run', run_id=run['run_id']),
        criterion=dict(base, kind='criterion', configuration_revision_id=retained['configuration_revision_id'],
                       criterion_id=retained['criteria'][0]['criterion_id']))
    return s, model, cfg, frozen, scopes, instances


def note(scope, **extra):
    return dict(evidence_schema_version='2', command_id=uid(), resource_scope=scope,
                kind='note', content='Exact α evidence\r\n', source_refs=['Observation 1'], **extra)


def snapshot(record):
    return {k:record[k] for k in ('evidence_version_id','kind','content','source_refs','evidence_schema_version','resource_scope') if k in record}


def rows(store, table):
    with store.connection() as db:
        return [tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]


def retain_legacy_bytes(name,before,after):
    root=scoped_evidence_root('public-discovery')
    exact={}
    for label,rows in [('before',before),('after',after)]:
        raw=json.dumps(rows,ensure_ascii=False).encode()
        (root/(name+'-'+label+'.json')).write_bytes(raw)
        exact[label]=dict(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
    assert exact['before']==exact['after']
    (root/(name+'-identity.json')).write_text(json.dumps(exact,indent=2)+'\n')


@pytest.mark.parametrize('kind', ['study','model_revision','definition_version','instance','port','connection','configuration','run','criterion'])
def test_all_exact_scope_variants_survive_restart_and_offline_discovery(api, scoped, kind):
    c, store, auth, model, transport, _ = api; s, _, _, _, scopes, _ = scoped
    sid = s['study_id']; path = f'/studies/{sid}/evidence'; scope = scopes[kind]
    if kind in ('study','configuration','run','criterion'): transport.offline = True
    record = post(c, path, note(scope), 201)['data']
    assert record['resource_scope'] == scope and record['evidence_schema_version'] == '2' and 'scope' not in record
    before = rows(store, 'evidence'); transport.offline = True
    restarted = TestClient(create_app(Store(store.path), auth, model), base_url=ORIGIN)
    restarted.cookies.update(c.cookies); restarted.headers.update(c.headers)
    assert restarted.get('/api/1'+path+'/'+record['evidence_version_id']).json()['data'] == record
    listed = restarted.get('/api/1'+path, params={'scope_kind':kind}).json()
    assert listed['data'] == [record] and listed['next_cursor'] is None
    assert rows(store, 'evidence') == before


def test_repeated_instance_ports_are_distinct_and_resolve_the_pinned_version(api, scoped):
    c = api[0]; s, model, _, _, scopes, instances = scoped; sid = s['study_id']; path = f'/studies/{sid}/evidence'
    first = post(c,path,note(scopes['port']),201)['data']
    second_scope = dict(scopes['port'],instance_id=instances[1]['instance_id'])
    second = post(c,path,note(second_scope),201)['data']
    filters = {k:v for k,v in second_scope.items() if k in ('model_id','model_revision_id','instance_id','port_id')}
    assert c.get('/api/1'+path,params=filters).json()['data'] == [second]
    assert first['resource_scope']['port_id'] == second['resource_scope']['port_id']
    root_scope = dict(scopes['port'],instance_id=model['root_instance_id'])
    post(c,path,note(root_scope),404)
    model_path = f"/studies/{sid}/models/{model['model_id']}"
    current = c.get('/api/1'+model_path).json()['data']
    renamed = post(c,model_path+'/edits',dict(schema_version='4',command_id=uid(),expected_revision=current['draft_revision'],edits=[dict(kind='rename_model',name='Later name')]))['data']
    newer = post(c,model_path+'/commits',dict(command_id=uid(),expected_revision=renamed['draft_revision']))['data']
    assert newer['model_revision_id'] != scopes['port']['model_revision_id']
    assert c.get('/api/1'+path+'/'+first['evidence_version_id']).json()['data'] == first
    assert post(c,path,note(scopes['port']),201)['data']['resource_scope'] == scopes['port']


@pytest.mark.parametrize('kind,field', [('study','study_id'),('model_revision','model_id'),('model_revision','model_revision_id'),
    ('definition_version','definition_id'),('definition_version','definition_version_id'),('instance','instance_id'),
    ('port','port_id'),('connection','connection_id'),('configuration','configuration_revision_id'),('run','run_id'),('criterion','criterion_id')])
def test_invalid_or_foreign_reference_creates_no_evidence_or_receipt(api, scoped, kind, field):
    c, store, *_ = api; s, _, _, _, scopes, _ = scoped
    bad = dict(scopes[kind]); bad[field] = uid()
    before = rows(store,'evidence'), rows(store,'receipts')
    post(c,f"/studies/{s['study_id']}/evidence",note(bad),404)
    assert (rows(store,'evidence'),rows(store,'receipts')) == before


def test_criterion_scope_on_a_configuration_without_criteria_creates_no_evidence_or_receipt(api, scoped):
    """A configuration 6 carries no criteria to scope evidence to: any criterion reference on it
    is refused as not found, and nothing is written."""
    c, store, *_ = api; s, _, _, frozen, scopes, _ = scoped
    revision = frozen['configuration']['configuration_revision_id']
    before = rows(store,'evidence'), rows(store,'receipts')
    for criterion in (uid(), scopes['criterion']['criterion_id']):
        bad = dict(scopes['criterion'], configuration_revision_id=revision, criterion_id=criterion)
        post(c,f"/studies/{s['study_id']}/evidence",note(bad),404)
    assert (rows(store,'evidence'),rows(store,'receipts')) == before


def test_current_authority_closed_requests_and_original_command_replay(api, scoped):
    c, store, _, _, transport, actor = api; s, _, _, _, scopes, _ = scoped; sid=s['study_id']; path=f'/studies/{sid}/evidence'
    command=note(scopes['study']); record=post(c,path,command,201)['data']
    assert post(c,path,command,201)['data']==record and len(rows(store,'evidence'))==1
    post(c,path,{**command,'content':'Changed'},409)
    bads=[{**command,'command_id':uid(),'scope':None},{**command,'command_id':uid(),'evidence_schema_version':'3'},
          {**command,'command_id':uid(),'resource_scope':{**scopes['study'],'native_id':1}},
          {**command,'command_id':uid(),'resource_scope':{**scopes['port'],'scope_version':'2'}}]
    for bad in bads:post(c,path,bad,400)
    assert c.post('/api/1'+path,json=note(scopes['study']),headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert TestClient(c.app,base_url=ORIGIN).get('/api/1'+path).status_code==401
    with store.connection(write=True) as db:db.execute("UPDATE memberships SET role='reader' WHERE actor_id=?",(actor,))
    post(c,path,command,403)
    assert c.get('/api/1'+path).status_code==200
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(actor,))
    before=len(transport.calls)
    post(c,path,command,404)
    assert c.get('/api/1'+path).status_code==404
    assert c.get('/api/1'+path+'/'+record['evidence_version_id']).status_code==404
    assert len(transport.calls)==before


def test_legacy_mixed_paging_filters_and_serialized_rows_are_unchanged(api, scoped):
    c, store, *_=api;s,_,_,_,scopes,_=scoped;sid=s['study_id'];path=f'/studies/{sid}/evidence'
    old=post(c,path,dict(command_id=uid(),scope=None,kind='note',content='Legacy',source_refs=[]),201)['data']
    legacy_id=uid();old_ref=post(c,path,dict(command_id=uid(),scope=legacy_id,kind='note',content='Untyped',source_refs=[]),201)['data']
    baseline=rows(store,'evidence')
    new=post(c,path,note(scopes['study']),201)['data']
    first=c.get('/api/1'+path+'?limit=1').json();assert first['data']==[old]
    second=c.get('/api/1'+path,params={'limit':2,'cursor':first['next_cursor']}).json()
    assert second['data']==[old_ref,new] and second['next_cursor'] is None
    assert c.get('/api/1'+path,params={'legacy_scope':legacy_id}).json()['data']==[old_ref]
    assert c.get('/api/1'+path,params={'legacy_scope':'null'}).json()['data']==[old]
    assert c.get('/api/1'+path,params={'scope_kind':'study'}).json()['data']==[new]
    other=study(api);foreign=post(c,f"/studies/{other['study_id']}/evidence",dict(command_id=uid(),scope=None,kind='note',content='Other',source_refs=[]),201)['data']
    for query in ['limit=0','limit=101','limit=1&limit=2','cursor=bad','unknown=x','port_id='+uid(),
                  'scope_kind=run&model_id='+uid(),'model_revision_id='+uid(),'scope_kind=study&legacy_scope=null']:
        assert c.get('/api/1'+path+'?'+query).status_code==400,query
    # Cursors are opaque tokens bound to the study, actor, view and filters: an evidence ID, an
    # unknown ID, another study's page cursor or a cursor under other filters never pages here.
    post(c,f"/studies/{other['study_id']}/evidence",dict(command_id=uid(),scope=None,kind='note',content='Other again',source_refs=[]),201)
    foreign_cursor=c.get(f"/api/1/studies/{other['study_id']}/evidence",params={'limit':1}).json()['next_cursor']
    assert foreign_cursor
    for cursor in [foreign['evidence_version_id'],uid(),foreign_cursor]:assert c.get('/api/1'+path,params={'cursor':cursor}).status_code==400
    assert c.get('/api/1'+path,params={'scope_kind':'study','cursor':old['evidence_version_id']}).status_code==400
    assert c.get('/api/1'+path,params={'scope_kind':'study','cursor':first['next_cursor']}).status_code==400
    assert rows(store,'evidence')[:2]==baseline
    retain_legacy_bytes('legacy-evidence',baseline,rows(store,'evidence')[:2])


def test_full_scope_freezes_and_tampering_cannot_strip_or_replace_it(api, scoped):
    """The server freezes the exact cited evidence (a typed record with its full scope pair, an
    older record without one); a request that supplies its own snapshots, forged, rescoped or
    stripped, is refused before any private call and never replaces the frozen ones."""
    c,store,auth,model,transport,_=api;s,_,cfg,_,scopes,_=scoped;sid=s['study_id'];path=f'/studies/{sid}'
    legacy=post(c,path+'/evidence',dict(command_id=uid(),scope=None,kind='note',content='Old shape',source_refs=[]),201)['data']
    legacy_trial=copy.deepcopy(cfg);legacy_trial['general_context_evidence_version_ids']=[legacy['evidence_version_id']]
    old_frozen=post(c,path+'/configurations',configuration_commit(api,legacy_trial),201)['data']
    assert old_frozen['configuration']['evidence_snapshots']==[snapshot(legacy)]
    old_rows=rows(store,'configurations');old_digest=old_frozen['configuration']['digest']
    typed=post(c,path+'/evidence',note(scopes['port']),201)['data']
    trial=copy.deepcopy(legacy_trial);trial['inputs'][0]['provenance']['evidence_version_ids']=[typed['evidence_version_id']]
    frozen=post(c,path+'/configurations',configuration_commit(api,trial),201)['data']
    expected=sorted([snapshot(legacy),snapshot(typed)],key=lambda x:x['evidence_version_id'])
    assert frozen['configuration']['evidence_snapshots']==expected
    assert snapshot(typed)['resource_scope']==scopes['port'] and snapshot(typed)['evidence_schema_version']=='2'
    assert frozen['configuration']['digest']==digest({k:v for k,v in frozen['configuration'].items() if k!='digest'})
    before=rows(store,'configurations');transport.offline=True;calls=len(transport.calls)
    forged=[dict(snapshot(typed),content='forged'),dict(snapshot(typed),source_refs=['forged']),
            dict(snapshot(typed),resource_scope=scopes['study']),
            {k:v for k,v in snapshot(typed).items() if k not in ('evidence_schema_version','resource_scope')},
            {k:v for k,v in snapshot(typed).items() if k!='resource_scope'}]
    for item in forged:
        altered=dict(copy.deepcopy(trial),evidence_snapshots=[snapshot(legacy),item])
        assert post(c,path+'/configurations/preview',altered,400)['error']['code']=='invalid_request'
        body=dict(configuration_id=None,expected_revision=None,command_id=uid(),configuration=altered,
                  expected_preview_digest=digest(frozen['configuration']))
        assert post(c,path+'/configurations',body,400)['error']['code']=='invalid_request'
    assert len(transport.calls)==calls
    restarted=TestClient(create_app(Store(store.path),auth,model),base_url=ORIGIN);restarted.cookies.update(c.cookies)
    assert restarted.get('/api/1'+path+'/configurations/'+frozen['configuration']['configuration_revision_id']).json()['data']==frozen
    assert rows(store,'configurations')==before and rows(store,'configurations')[:len(old_rows)]==old_rows
    assert old_frozen['configuration']['digest']==old_digest
    retain_legacy_bytes('legacy-configurations',old_rows,rows(store,'configurations')[:len(old_rows)])


def test_scope_schema_pair_is_closed_and_snapshot_pair_is_all_or_neither():
    schemas=[authored_schema() for name in ['model.schema.json','execution.schema.json']]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        assert 'EvidenceResourceRef1' in schema['$defs']
        base=dict(evidence_version_id=uid(),kind='note',content='',source_refs=[])
        validator=Draft202012Validator({**schema,'$ref':'#/$defs/EvidenceSnapshot'},format_checker=FormatChecker())
        validator.validate(base)
        scope=dict(scope_version='1',kind='study',study_id=uid())
        validator.validate(dict(base,evidence_schema_version='2',resource_scope=scope))
        assert not validator.is_valid(dict(base,evidence_schema_version='2'))
        assert not validator.is_valid(dict(base,resource_scope=scope))
        assert not validator.is_valid(dict(base,evidence_schema_version='2',resource_scope={**scope,'native_url':'private'}))
    assert schemas[0]['$defs']==schemas[1]['$defs']


def test_existing_foreign_resources_are_not_accepted_into_another_study(api, scoped):
    c,store,*_=api;_,_,_,_,scopes,_=scoped
    other=study(api);sid=other['study_id'];before=rows(store,'evidence'),rows(store,'receipts')
    for kind,scope in scopes.items():
        if kind=='study':continue
        post(c,f'/studies/{sid}/evidence',note(dict(scope,study_id=sid)),404)
    assert (rows(store,'evidence'),rows(store,'receipts'))==before


@pytest.mark.parametrize('kind', ['model_revision','definition_version','instance','port','connection'])
def test_model_scoped_evidence_replay_is_local_after_restart_with_current_authority(api, scoped, kind):
    c,store,auth,model,transport,actor=api
    s,_,_,_,scopes,_=scoped; sid=s['study_id']; path=f'/studies/{sid}/evidence'
    command=note(scopes[kind]); original=post(c,path,command,201)['data']
    before=rows(store,'evidence'),rows(store,'receipts')
    transport.offline=True
    restarted=TestClient(create_app(Store(store.path),auth,model),base_url=ORIGIN)
    restarted.cookies.update(c.cookies); restarted.headers.update(c.headers)
    calls=len(transport.calls)
    for client in (c,restarted):
        assert post(client,path,command,201)['data']==original
        assert post(client,path,{**command,'content':'Changed'},409)['error']['code']=='command_payload_conflict'
        post(client,path,{**command,'unexpected':'invalid'},400)
    assert len(transport.calls)==calls
    post(restarted,path,{**command,'command_id':uid()},503)
    assert (rows(store,'evidence'),rows(store,'receipts'))==before
    calls=len(transport.calls)
    with store.connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE actor_id=?",(actor,))
    post(restarted,path,command,403)
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(actor,))
    post(restarted,path,command,404)
    assert len(transport.calls)==calls
    assert (rows(store,'evidence'),rows(store,'receipts'))==before


@pytest.mark.parametrize('shape', ['legacy','paired','version_only','scope_only'])
@pytest.mark.parametrize('action', ['configuration-compatibility','prepare-execution'])
def test_private_evidence_snapshot_pair_is_enforced_on_real_http(api, scoped, shape, action):
    from hyprn_mvp_app.store import DomainError
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    _,_,_,model,_,actor=api
    s,pin,_,frozen,scopes,_=scoped
    # The private configuration 5 the application projects from the saved configuration 6.
    cfg=project_scientific_configuration(copy.deepcopy(frozen['configuration']))
    item=dict(evidence_version_id=uid(),kind='note',content='Private contract test',source_refs=[])
    if shape in ('paired','version_only'):item['evidence_schema_version']='2'
    if shape in ('paired','scope_only'):item['resource_scope']=scopes['port']
    cfg['evidence_snapshots']=[item]
    cfg['digest']=digest({k:v for k,v in cfg.items() if k!='digest'})
    if action=='configuration-compatibility':
        candidate={k:v for k,v in cfg.items() if k not in ('configuration_id','configuration_revision_id','parent_revision_id','digest')}
        body=dict(model_revision_id=pin['model_revision_id'],configuration_candidate=candidate)
    else:
        body=dict(command_id=uid(),model_revision_id=pin['model_revision_id'],configuration_snapshot=cfg,configuration_digest=cfg['digest'])
    # Deliberately omit client schema validation: exercise the signed private HTTP boundary.
    def invoke():return model.call(actor,s['study_id'],'POST',f"/models/{pin['model_id']}/{action}",body,resources=[pin['model_id']])
    if shape in ('version_only','scope_only'):
        with pytest.raises(DomainError) as failure:invoke()
        assert failure.value.status==400 and failure.value.code=='invalid_request'
    else:
        status,result=invoke()
        assert status==200
        if action=='configuration-compatibility':assert result['data']['compatible'] is True
        else:assert (result['data']['schema_version'],result['data']['result_protocol_version'])==('4','3')
