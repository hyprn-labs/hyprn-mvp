"""Data-only History4/Seed4 and portable admission with synthetic retained results.

Captured producer bytes are resealed for Model3; nothing is executed. Native numerical
results and offline archives are proven by the native execution and archive tests.
"""
from copy import deepcopy
import base64
import io
import json
import zipfile
import pytest
import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

from test_unit_execution_admission import catalog, case6, repin, assemble, reseal
from hyprn_mvp_app.store import Store, DomainError, canonical, digest, uid
from hyprn_mvp_app.history import History
from hyprn_mvp_app.modified_runs import ModifiedRuns
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_app.execution import validate_frozen_configuration, validate_retained_bundle
from hyprn_mvp_app.computational_export import ComputationalRecords, inspect_record, LIMITS, OMISSIONS, PREREQUISITES, approach_payloads, sha


def retained(tmp_path, catalog, *, linked=False, legacy=False, failed=False, mixed=None):
    store=Store(tmp_path/'history.sqlite');actor=uid()
    study=store.create_study(actor,uid(),'Retained fixture');sid=study['study_id']
    case=case6(catalog, linked=False, legacy=legacy);f=case['frozen'];c=f['configuration'];m=f['model_snapshot']
    c['study_id']=sid;c['context_source']['expected_study_revision']=study['revision'];f['study_revision']=study['revision']
    evidence=store.add_evidence(actor,sid,uid(),dict(evidence_schema_version='3',title='Exact evidence',kind='note',content='Retained original',source_refs=[],resource_scope=dict(scope_version='1',kind='study',study_id=sid)))
    c['evidence_snapshots']=[evidence];c['general_context_evidence_version_ids']=[evidence['evidence_version_id']]
    c['inputs'][0]['provenance']['evidence_version_ids']=[evidence['evidence_version_id']]
    if not legacy:
        old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
        for p in old['ports']:p.update(definition_version_id=old['definition_version_id'],units={'kind':'unspecified'})
        m['definitions'].insert(0,old);m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    repin(case)
    if linked or mixed:
        from test_approach_closure import sample,D,link,resolution,signed
        from hyprn_mvp_app.approach_closure import build_closure
        v=sample(D['ApproachVersion1']);v['study_id']=sid;link(v,m)
        models=[m]
        if mixed:
            from test_unit_execution_admission import explanatory_model
            extra=explanatory_model(m,mixed);models.append(extra);link(v,extra)
            f['schema_version']='5'
        closure=build_closure(v,resolution(models=models),study_id=sid)
        f['approach_closure']=closure
        c['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest=closure['digest'])
        repin(case)
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],sid,json.dumps(f)))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(c['configuration_id'],sid,c['configuration_revision_id']))
    e=dict(store=store,actor=actor,sid=sid,case=case,study=study)
    from test_approach_modified_runs import retain_api
    e['rid']=retain_api(e,f,failed=failed)
    return e


def payload(e):
    with e['store'].connection() as db:return json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(e['rid'],)).fetchone()[0])


def update_payload(e,p):
    with e['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(p),e['rid']))


@pytest.mark.parametrize('linked',[False,True])
def test_history4_exact_units_sources_restart_and_later_model_edits(tmp_path,catalog,linked):
    e=retained(tmp_path,catalog,linked=linked);p=payload(e);before=canonical(p)
    h=History(e['store']).read(e['actor'],e['sid'],e['rid']);validate('RunHistory4',h)
    assert h['history_schema_version']=='4' and h['errors']==[]
    assert h['model_snapshot']==p['frozen']['model_snapshot'] and h['configuration']==p['frozen']['configuration']
    assert h['approach_closure']==p['frozen']['approach_closure']
    model=deepcopy(e['case']['frozen']['model_snapshot']);model['name']='Changed current model'
    model['definitions'][-1]['ports'][0]['units']={'kind':'physical','expression':'MJ/kg'}
    restarted=Store(tmp_path/'history.sqlite')
    assert History(restarted).read(e['actor'],e['sid'],e['rid'])==h
    for item in h['artifacts']:
        if item['name']=='model.json':
            raw,_=History(restarted).read(e['actor'],e['sid'],e['rid'],item['artifact_id'])
            assert raw==canonical(p['frozen']['model_snapshot'])
    assert canonical(payload(e))==before


@pytest.mark.parametrize('linked',[False,True])
@pytest.mark.parametrize('failed',[False,True])
def test_seed4_exact_context_evidence_and_result_eligibility(tmp_path,catalog,linked,failed,monkeypatch):
    e=retained(tmp_path,catalog,linked=linked,failed=failed);p=payload(e);c=p['frozen']['configuration']
    monkeypatch.setattr(e['store'],'evidence_version',lambda *a:pytest.fail('Seed fetched current evidence'))
    seed=ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid']);validate('ModifiedRunSeed4',seed)
    assert seed['source_configuration']==c and seed['model_snapshot']==p['frozen']['model_snapshot']
    assert seed['approach_closure']==p['frozen']['approach_closure']
    assert seed['configuration']['general_context_evidence_version_ids']==c['general_context_evidence_version_ids']
    assert seed['configuration']['inputs'][0]['provenance']==c['inputs'][0]['provenance']
    request=seed['configuration'];request['context_source']['choice_confirmed']=True
    ModifiedRuns(e['store']).authoring(e['actor'],e['sid'],request,e['store'].study(e['actor'],e['sid']))
    if failed:
        with pytest.raises(DomainError,match='source_result_unavailable'):ResultBindings(e['store']).retained(e['actor'],e['sid'],e['rid'])
    else:assert ResultBindings(e['store']).retained(e['actor'],e['sid'],e['rid'])[0]['results']==p['history']['results']


@pytest.mark.parametrize('change',['model','revision','downgrade','context'])
def test_modified_seed_fixed_boundary_and_explicit_context_choice(tmp_path,catalog,change):
    e=retained(tmp_path,catalog);service=ModifiedRuns(e['store']);r=service.seed(e['actor'],e['sid'],e['rid'])['configuration']
    r['context_source']['choice_confirmed']=True
    if change=='model':r['model_id']=uid()
    elif change=='revision':r['model_revision_id']=uid()
    elif change=='downgrade':r['schema_version']='3'
    else:r['context_source']['choice_confirmed']=False
    with pytest.raises(DomainError):service.authoring(e['actor'],e['sid'],r,e['store'].study(e['actor'],e['sid']))


@pytest.mark.parametrize('mixed',[None,'physical','unspecified'])
@pytest.mark.parametrize('change',['raw','source','association','result_units','partial'])
def test_corruption_partial_failure_and_units_never_repaired(tmp_path,catalog,change,mixed):
    e=retained(tmp_path,catalog,legacy=bool(mixed),mixed=mixed);p=payload(e)
    if change=='raw':p['bundle']['files']['model.json']=base64.b64encode(b'{}').decode()
    elif change=='source':p['frozen']['model_snapshot']['source_files'][0]['bytes']='eA=='
    elif change=='association':p['history']['association']['process_uuid']=uid()
    elif change=='result_units':p['history']['results']['outputs'][0]['units']='MJ/kg'
    else:p['history']['errors']=[dict(code='missing_result',partial=True)];p['history']['results']=None
    p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'});update_payload(e,p)
    if change in ('raw','source','association'):assert History(e['store']).read(e['actor'],e['sid'],e['rid'])['errors']==[dict(code='corrupt_retained_record',partial=True)]
    with pytest.raises(DomainError):ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid'])


def test_legacy_history_seed_and_raw_payload_are_unchanged(tmp_path,catalog):
    e=retained(tmp_path,catalog,legacy=True);before=canonical(payload(e));h=History(e['store']).read(e['actor'],e['sid'],e['rid'])
    validate('RunHistory3',h);validate('ModifiedRunSeed3',ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid']))
    assert h['history_schema_version']=='3' and all(isinstance(p['units'],str) for p in h['model_snapshot']['ports'])
    assert canonical(payload(e))==before


@pytest.mark.parametrize('mixed',[None,'physical','unspecified'])
def test_read_seed_and_export_reauthorize_without_allocation(tmp_path,catalog,mixed):
    e=retained(tmp_path,catalog,legacy=bool(mixed),mixed=mixed);s=ComputationalRecords(e['store'],tmp_path/'records')
    body=dict(command_id=uid(),selected_run_ids=[e['rid']]);q=s.enqueue_preview(e['actor'],e['sid'],body)
    assert s.enqueue_preview(e['actor'],e['sid'],body)==q
    with pytest.raises(DomainError,match='command_payload_conflict'):s.enqueue_preview(e['actor'],e['sid'],dict(body,selected_run_ids=[uid()]))
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(e['actor'],))
    for action in (lambda:History(e['store']).read(e['actor'],e['sid'],e['rid']),lambda:ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid']),lambda:s.status(e['actor'],e['sid'],q['request_id'])):
        with pytest.raises(DomainError):action()
    assert s.process_one(lambda _:pytest.fail('Archive called after revocation'))


@pytest.mark.parametrize('missing',['schema_version','study_revision','wrong_version','forged_revision'])
def test_default_frozen5_wrapper_remains_strict(catalog,missing):
    case=case6(catalog);f=case['frozen']
    if missing=='wrong_version':f['schema_version']='4'
    elif missing=='forged_revision':f['study_revision']={'forged':True}
    else:del f[missing]
    with pytest.raises(ValueError):validate_frozen_configuration(f)
    b,r=assemble(case6(catalog))
    with pytest.raises(ValueError):validate_retained_bundle(b,r,f)


def portable(e):
    """Synthetic native-container transport: data-only reader, no offline AiiDA proof."""
    s=ComputationalRecords(e['store'],SCOPE.root/'artifacts'/uid())
    records,roles,preflight,_=s._collect(e['actor'],e['sid'],[e['rid']])
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('metadata.json',canonical(dict(export_version='main_0001',aiida_version='2.9.3')))
        z.writestr('db.sqlite3',b'SQLite format 3\0synthetic-container-not-a-database')
    native=stream.getvalue()
    files,mapping,inventory,_=s._package(records,roles,preflight,native,100,2)
    indices,summary,_=approach_payloads(records)
    manifest=dict(schema_version='2',kind='hyprn-mvp-computational-record',origin_store_uuid=preflight['origin_store_uuid'],selected_run_ids=[e['rid']],computational_run_ids=[e['rid']],derivation_context_run_ids=[],runs=mapping,inventory=inventory,native_inventory_digest='a'*64,omissions=OMISSIONS,classification='inspection_only',reexecution_prerequisites=PREREQUISITES,limits=LIMITS,approaches=indices,approach_summary=summary)
    manifest['manifest_digest']=digest(manifest)
    return {**{p:v for p,(_,v) in files.items()},'manifest.json':canonical(manifest)}


def archive(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p,raw in files.items():z.writestr(p,raw)
    return stream.getvalue()


@pytest.mark.parametrize('linked',[False,True])
def test_portable_bundle6_offline_data_only_read_without_fabricated_study_revision(tmp_path,catalog,linked):
    e=retained(tmp_path,catalog,linked=linked);files=portable(e);before=deepcopy(files)
    manifest=inspect_record(archive(files))
    assert manifest['schema_version']=='2' and manifest['classification']=='inspection_only' and files==before
    assert not any(p.endswith('frozen.json') for p in files)


@pytest.mark.parametrize('change',['raw','path','oversized','wrong_pair','declaration','closure'])
def test_portable_tampering_and_bounds_fail_closed(tmp_path,catalog,change):
    e=retained(tmp_path,catalog,linked=True);files=portable(e);manifest=json.loads(files['manifest.json'])
    path=next(p for p in files if p.endswith('/bundle/model.json'))
    if change=='raw':files[path]+=b' '
    elif change=='path':files['../escape']=b'x'
    elif change=='oversized':files['manifest.json']=b' '*(LIMITS['metadata_bytes']+1)
    else:
        m=json.loads(files[path])
        if change=='wrong_pair':m['schema_version']='2'
        elif change=='declaration':m['definitions'][-1]['ports'][0]['units']={'kind':'unspecified'}
        else:
            path=manifest['approaches'][0]['path'];m=json.loads(files[path]);m['models'][0]['name']='Changed closure'
        files[path]=canonical(m)
        for item in manifest['inventory']:
            if item['path']==path:item.update(size=len(files[path]),sha256=sha(files[path]))
        manifest['manifest_digest']=digest({k:v for k,v in manifest.items() if k!='manifest_digest'});files['manifest.json']=canonical(manifest)
    with pytest.raises((ValueError,DomainError)):inspect_record(archive(files))


@pytest.mark.parametrize('change',['model2','config3','missing_closure','extra_wrapper','digest','source','catalog','binding','unresolved'])
def test_raw_bundle_mode_still_validates_exact_science(catalog,change):
    case=case6(catalog);b,r=assemble(case)
    raw={k:deepcopy(case['frozen'][k]) for k in ('model_snapshot','configuration','approach_closure')}
    validate_retained_bundle(b,r,raw,raw_snapshot=True)
    if change=='model2':raw['model_snapshot']['schema_version']='2'
    elif change=='config3':raw['configuration']['schema_version']='3'
    elif change=='missing_closure':del raw['approach_closure']
    elif change=='extra_wrapper':raw['study_revision']='invented'
    elif change=='digest':raw['configuration']['digest']='f'*64
    elif change=='source':raw['model_snapshot']['source_files'][0]['bytes']='eA=='
    elif change=='unresolved':
        raw['model_snapshot']['definitions'][0]['ports'][0]['units']={'kind':'unspecified'}
        raw['model_snapshot']['ports']=deepcopy([p for d in raw['model_snapshot']['definitions'] for p in d['ports']])
        raw['model_snapshot']['digest']=digest({k:v for k,v in raw['model_snapshot'].items() if k!='digest'})
    else:
        # Repin every manifest/preparation hash around semantic catalog/binding corruption.
        if change=='catalog':
            from test_unit_execution_admission import CATALOG_PATH
            value=json.loads(case['files'][CATALOG_PATH]);value['catalog_digest']='f'*64
            case['files'][CATALOG_PATH]=canonical(value)
        else:
            path=case['prepared']['entrypoint']['bindings_path'];value=json.loads(case['files'][path]);value['outputs'][0]['units']='MJ/kg';case['files'][path]=canonical(value)
        repin(case)
        for p,v in case['files'].items():b['files'][p]=v
        b['files']['preparation.json']=canonical(case['prepared'])
        b['manifest'].update(prepared_digest=case['prepared']['prepared_digest'],executable_content_digest=case['prepared']['executable_content_digest'],generator=case['prepared']['generator_identity'])
        reseal(b,r)
    with pytest.raises((ValueError,DomainError,KeyError)):validate_retained_bundle(b,r,raw,raw_snapshot=True)


@pytest.mark.parametrize('units',['','MJ/kg','kg/m**3'])
def test_complete_outcome_exact_engine_strings_and_active_version(catalog,units):
    from hyprn_mvp_app.modified_runs import complete_outcome
    case=case6(catalog);m=case['frozen']['model_snapshot'];c=case['frozen']['configuration']
    for definition in m['definitions']:
        for port in definition['ports']:port['units']={'kind':'physical','expression':units} if units else {'kind':'dimensionless'}
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    outputs=[dict(target=dict(instance_id=i['instance_id'],port_id=p['port_id']),units=units,value=0,availability='available',reason=None,producer_completed=True,assigned=True)
             for i in m['instances'] for d in m['definitions'] if d['definition_version_id']==i['definition_version_id'] for p in d['ports'] if p['direction']=='output']
    result=dict(schema_version='1',run_id=uid(),bundle_digest='a'*64,execution=dict(state='finished',exit_code=0,message='Synthetic'),convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),outputs=outputs,criteria=[dict(criterion_id=k['criterion_id'],outcome='unresolved',reason='Synthetic') for k in c['criteria']],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    complete_outcome(result,m,c)
    result['outputs'][0]['units']='J/kg' if units!='J/kg' else 'MJ/kg'
    with pytest.raises(ValueError):complete_outcome(result,m,c)


def test_incomplete_package3_is_data_only_and_never_a_frozen_run(catalog):
    case=case6(catalog);m=case['frozen']['model_snapshot']
    m['definitions'][0]['ports'][0]['units']={'kind':'unspecified'}
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']]);repin(case)
    package=case['prepared']['model_package_manifest'];before=canonical(package)
    validate('ModelPackage3',package)
    assert canonical(package)==before
    with pytest.raises((ValueError,DomainError)):validate_frozen_configuration(case['frozen'])


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_history_seed_raw_portable_outage_exact(tmp_path,catalog,declaration,monkeypatch):
    e=retained(tmp_path,catalog,legacy=True,mixed=declaration);p=payload(e);before=canonical(p)
    monkeypatch.setattr(e['store'],'evidence_version',lambda *a:pytest.fail('Current evidence fetched'))
    h=History(e['store']).read(e['actor'],e['sid'],e['rid']);validate('RunHistory4',h)
    assert h['errors']==[] and h['model_snapshot']==p['frozen']['model_snapshot']
    assert h['configuration']==p['frozen']['configuration'] and h['approach_closure']==p['frozen']['approach_closure']
    restarted=Store(tmp_path/'history.sqlite')
    assert History(restarted).read(e['actor'],e['sid'],e['rid'])==h
    seed=ModifiedRuns(restarted).seed(e['actor'],e['sid'],e['rid']);validate('ModifiedRunSeed4',seed)
    assert seed['schema_version']=='4' and seed['model_snapshot']==h['model_snapshot']
    assert seed['source_configuration']==h['configuration'] and seed['approach_closure']==h['approach_closure']
    seed['configuration']['context_source']['choice_confirmed']=True
    ModifiedRuns(restarted).authoring(e['actor'],e['sid'],seed['configuration'],restarted.study(e['actor'],e['sid']))
    files=portable(e);assert inspect_record(archive(files))['classification']=='inspection_only'
    for item in h['artifacts']:
        if item['name']=='model.json':
            raw,_=History(restarted).read(e['actor'],e['sid'],e['rid'],item['artifact_id'])
            assert raw==canonical(p['frozen']['model_snapshot'])
    assert canonical(payload(e))==before


def mixed_api_checks(wire,root):
    """A seed from a run configured before criteria moved to the study brief still reads
    exactly, but its earlier-format request is refused at preview and save: nothing is
    written and the seed is unchanged."""
    report=[]
    for choice in ('preserve','remove'):
        directory=root/choice;directory.mkdir();e=mixed_api_app(directory,wire,root/'source.sqlite')
        c=e['client'];service=ModifiedRuns(e['store'])
        seed=service.seed(e['actor'],e['sid'],e['rid']);validate('ModifiedRunSeed4',seed)
        request=deepcopy(seed['configuration']);request['context_source']['choice_confirmed']=True
        if choice=='remove':request['approach_selection']=None
        with e['store'].connection() as db:before=db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]
        url='/api/1/studies/'+e['sid']+'/configurations';preview=c.post(url+'/preview',json=request)
        assert preview.status_code==422 and preview.json()['error']['code']=='unsupported_record_version',preview.text
        command=dict(command_id=uid(),configuration_id=None,expected_revision=None,
            configuration=request,expected_preview_digest='0'*64)
        saved=c.post(url,json=command)
        assert saved.status_code==422 and saved.json()['error']['code']=='unsupported_record_version',saved.text
        with e['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==before
        assert service.seed(e['actor'],e['sid'],e['rid'])==seed
        report.append(choice)
    return report


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_seed_reads_exactly_and_its_earlier_request_is_refused(tmp_path,catalog,declaration):
    import subprocess
    from pathlib import Path
    e=retained(tmp_path,catalog,legacy=True,mixed=declaration)
    wire=deepcopy(e['case']);wire['files']={p:base64.b64encode(raw).decode() for p,raw in wire['files'].items()}
    root=guard.scoped_path(SCOPE,'artifacts/mixed-api-'+declaration);root.mkdir()
    (root/'case.json').write_text(json.dumps(wire))
    import sqlite3
    with e['store'].connection() as source,sqlite3.connect(root/'source.sqlite') as target:source.backup(target)
    repo=Path(__file__).resolve().parents[2]
    script="import sys,json,base64;from pathlib import Path;r=Path(sys.argv[1]);sys.path[:0]=[str(r/p) for p in ('deployment','deployment/tests','application/src','application/tests','integration/src','integration/tests','contracts/tests')];from test_unit_history import mixed_api_checks;root=Path(sys.argv[2]);wire=json.loads((root/'case.json').read_text());wire['files']={p:base64.b64decode(v) for p,v in wire['files'].items()};print(json.dumps(mixed_api_checks(wire,root)));assert not any(n.split('.')[0] in ('aiida','openmdao','openturns') for n in sys.modules)"
    command=[guard.APPROVED_CONTRACT_PYTHON,'-B','-c',script,str(repo),str(root)]
    result=subprocess.run(command,env=guard.clean_environment(SCOPE),capture_output=True,text=True)
    guard.scoped_path(SCOPE,'evidence/mixed-api-'+declaration+'.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    assert result.returncode==0,result.stderr


def mixed_api_app(directory,wire,source):
    import sqlite3
    from fastapi.testclient import TestClient
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from test_reuse_api import PrivateModelDouble,ORIGIN
    from test_approach_closure import sample,D
    target=directory/'api.sqlite'
    with sqlite3.connect(source) as original,sqlite3.connect(target) as copied:original.backup(copied)
    store=Store(target);auth=Auth(store,ORIGIN);actor=auth.provision('owner','correct horse battery staple')
    config=wire['frozen']['configuration'];sid=config['study_id'];closure=wire['frozen']['approach_closure']
    with store.connection(write=True) as db:
        db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))
        for model in closure['models']:
            db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,model['model_id'],uid()))
        for version in closure['approach_versions']:
            draft=sample(D['ApproachDraft1']);draft.update(approach_id=version['approach_id'],study_id=sid,base_version_id=version['approach_version_id'],content=deepcopy(version['content']))
            db.execute('INSERT INTO approach_drafts VALUES(?,?,?,?)',(version['approach_id'],sid,draft['revision'],json.dumps(draft)))
            db.execute('INSERT INTO approach_versions VALUES(?,?,?,?,?)',(version['approach_version_id'],version['approach_id'],sid,version['version_number'],json.dumps(dict(version=version,closure=closure))))
        rid=db.execute('SELECT run_id FROM outbox').fetchone()[0]
    class Model(PrivateModelDouble):
        def call(self,actor,sid,method,route,body=None,**kw):
            if route!='/capabilities':return super().call(actor,sid,method,route,body,**kw)
            if self.offline:raise AssertionError('Retained read contacted modeling')
            caps=sample(D['Capabilities']);cap=sample(D['Capabilities']['properties']['capabilities']['items'])
            cap.update(id='resolved_configuration',version='3',supported=True)
            caps.update(contract_versions=['1.2'],schema_versions=['1','2'],capabilities=[cap],generator_identity=deepcopy(self.case['prepared']['generator_identity']))
            return 200,dict(data=caps)
    model=Model(wire);client=TestClient(create_app(store,auth,model),base_url=ORIGIN)
    login=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':login.json()['data']['csrf_token']})
    return dict(store=store,actor=actor,sid=sid,rid=rid,case=wire,model=model,client=client)


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_full_raw_and_portable_reject_resealed_historical_pair(tmp_path,catalog,declaration):
    from hyprn_mvp_app.execution import verify_files,check_digest
    from hyprn_mvp_app.history import validate_binding
    from hyprn_mvp_integration import results
    e=retained(tmp_path,catalog,legacy=True,mixed=declaration);p=payload(e)
    bundle=dict(manifest=deepcopy(p['bundle']['manifest']),files={k:base64.b64decode(v) for k,v in p['bundle']['files'].items()})
    class Repository:
        def open(self,path,mode='rb'):
            return io.BytesIO(canonical(bundle['manifest']) if path=='manifest.json' else bundle['files'][path])
    assert results.retained_bundle(Repository(),p['request'])==bundle
    # Authentic raw files remain unchanged; rebind all outer version/digest identities.
    files=portable(e);manifest=json.loads(files['manifest.json']);prefix='hyprn-mvp/runs/'+e['rid']+'/'
    bundle['manifest']['schema_version']='5';reseal(bundle,p['request'])
    files[prefix+'bundle/manifest.json']=canonical(bundle['manifest'])
    result=json.loads(files[prefix+'results.json']);result['bundle_digest']=bundle['manifest']['bundle_digest']
    files[prefix+'results.json']=canonical(result)
    mapping=manifest['runs'][0];mapping.update(bundle_digest=bundle['manifest']['bundle_digest'],results_digest=digest(result))
    files[prefix+'identity.json']=canonical(mapping)
    for row in manifest['inventory']:
        raw=files[row['path']];row.update(size=len(raw),sha256=sha(raw))
    manifest['manifest_digest']=digest({k:v for k,v in manifest.items() if k!='manifest_digest'})
    files['manifest.json']=canonical(manifest)
    with pytest.raises(ValueError,match='ApproachClosurePreUnits'):inspect_record(archive(files))
    verify_files(bundle['manifest']['files'],bundle['files']);check_digest(bundle['manifest'],'bundle_digest')
    with pytest.raises(ValueError,match='ApproachClosurePreUnits'):results.retained_bundle(Repository(),p['request'])
    p['bundle']['manifest']=bundle['manifest'];p['frozen']['schema_version']='4'
    p['history']['request']=deepcopy(p['request']);p['history']['results']['bundle_digest']=p['request']['bundle_digest']
    p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'});update_payload(e,p)
    with e['store'].connection() as db:
        row=db.execute('SELECT r.*,o.state,o.payload FROM run_associations r JOIN outbox o USING(run_id) WHERE r.run_id=?',(e['rid'],)).fetchone()
        receipt=e['store']._receipt(db,e['sid'],'run',row['command_id'])
        assert validate_binding(row,p,receipt)==p['history']
    h=History(e['store']).read(e['actor'],e['sid'],e['rid'])
    assert h['errors']==[dict(code='corrupt_retained_record',partial=True)] and h['model_snapshot'] is None
    with pytest.raises(DomainError):ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid'])
