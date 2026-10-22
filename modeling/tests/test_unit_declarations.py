"""Actual isolated private HTTP/JWT unit lifecycle, never candidate execution."""
import copy
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'deployment/tests'),str(ROOT/'contracts/tests')]
import scoped_fixture as guard
from checks import PROJECTION_SCOPE
guard.validate_scope(PROJECTION_SCOPE)  # Guard before helper import or interaction.
from units_model_fixture import PrivateModel
from test_modeling_contract import uid,source,creation,digest,numerical,validate,canonical,raw_hash


@pytest.fixture(scope='module')
def service():
    backend=PrivateModel()
    try:yield backend
    finally:backend.close()


def create(c,version='3'):
    body=dict(command_id=uid(),expected_revision=None,study_id=c.study,name='Unit intent',template='empty')
    if version=='3':body['schema_version']='3'
    return c.call('POST','/models',body,status=201)['data']


def edit(c,m,edits,version='3',status=200):
    body=dict(command_id=uid(),expected_revision=m['draft_revision'],edits=edits)
    if version=='3':body['schema_version']='3'
    return c.call('POST','/models/'+m['model_id']+'/edits',body,status=status)


def commit(c,m):
    return c.call('POST','/models/'+m['model_id']+'/commits',dict(command_id=uid(),expected_revision=m['draft_revision']))['data']


def edits(units=None):
    result=creation()
    for p in result[0]['ports']:p['units']=copy.deepcopy(units or {'kind':'unspecified'})
    result[0]['source']=source(b"open('/store/forbidden-candidate-import', 'w').write('candidate imported')\r\nraise RuntimeError('candidate must never execute')\r\n# <%= File.write('/tmp/erb-canary', 'bad') %>\r\noutputs['y'] = inputs['x']\r\n")
    return result


def config(m,c):
    ins=[]
    incoming=[x['target_ref'] for x in m['connections']]
    defs={d['definition_version_id']:d for d in m['definitions']}
    for i in m['instances']:
        for p in defs[i['definition_version_id']]['ports']:
            target=dict(instance_id=i['instance_id'],port_id=p['port_id'])
            if p['direction']=='input' and target not in incoming:
                u=p['units']; unit=u if isinstance(u,str) else (u.get('expression',''))
                ins.append(dict(target=target,value=2,units=unit,provenance=dict(kind='manual',statement='Explicit',evidence_version_ids=[])))
    return dict(schema_version='3',study_id=c.study,model_id=m['model_id'],model_revision_id=m['model_revision_id'],name='Static units',inputs=ins,criteria=[],numerical=numerical(),context_snapshot=dict(description='test',boundary='',notes=[]),evidence_snapshots=[],required_capabilities=['flat_explicit_scalar'])


def prepare(c,m,status=200):
    cfg=config(m,c);cfg.update(configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None)
    cfg['digest']=digest(cfg)
    return c.call('POST','/models/'+m['model_id']+'/prepare-execution',dict(command_id=uid(),model_revision_id=m['model_revision_id'],configuration_snapshot=cfg,configuration_digest=cfg['digest']),status=status)


def test_capability_catalog_and_scoped_jwt(service):
    c=service
    cap=c.call('GET','/capabilities')['data']
    assert '1.3' in cap['contract_versions'] and '3' in cap['schema_versions']
    assert cap['execution_versions']['bundle_versions']==['10','11']
    assert any(x['id']=='unit_declarations' and x['version']=='1' and x['supported'] for x in cap['capabilities'])
    cat=c.call('GET','/unit-catalog')['data'];validate('UnitCatalog1',cat)
    assert len(cat['supported_units'])==48 and len(json.dumps(cat).encode())<16384
    for kwargs,code in [({'expired':True},401),({'key':b'wrong'},401),({'permissions':[]},403),({'wrong_hash':True},401)]:
        c.call('GET','/unit-catalog',status=code,**kwargs)

def test_display_name_is_not_a_native_python_package(service):
    c = service
    name = 'Steady heat-budget screen (12 kW cooling)'
    body = dict(command_id=uid(), expected_revision=None, study_id=c.study,
                name=name, template='empty', schema_version='3')
    created = c.call('POST', '/models', body, status=201)['data']
    assert created['name'] == name
    assert c.call('POST', '/models', body, status=201)['data'] == created
    assert c.call('GET', '/models/' + created['model_id'])['data']['name'] == name


def test_incomplete_commit_restart_and_preparation_gate(service):
    c=service;m=create(c);assert m['schema_version']=='3'
    m=edit(c,m,edits())['data'];pin=commit(c,m);validate('ModelRevision3',pin)
    assert all(p['units']=={'kind':'unspecified'} for p in pin['ports'])
    assert pin['source_files']==[edits()[0]['source']]
    checked=c.call('POST','/models/'+m['model_id']+'/validate',dict(model_revision_id=pin['model_revision_id']))['data']
    assert checked['diagnostics'] and all(d['code']=='unit_unspecified' for d in checked['diagnostics'])
    proof=c.call('POST','/models/'+m['model_id']+'/configuration-compatibility',dict(model_revision_id=pin['model_revision_id'],configuration_candidate=config(pin,c)))['data']
    assert not proof['compatible'] and proof['diagnostics']
    assert all(x['code']=='unit_unspecified' and 'instances/' in x['path'] for x in proof['diagnostics'])
    prepare(c,pin,status=422)
    c.restart()
    assert c.call('GET','/models/'+m['model_id'])['data']==m
    assert c.call('GET','/models/'+m['model_id']+'/revisions/'+pin['model_revision_id'])['data']==pin
    c.call('GET','/models/'+m['model_id'],study=uid(),status=404)


def test_preview_apply_atomic_replay_and_closed_units(service):
    c=service;m=create(c);path='/models/'+m['model_id']
    body=dict(schema_version='3',command_id=uid(),expected_revision=m['draft_revision'],edits=edits({'kind':'dimensionless'}))
    preview=c.call('POST',path+'/preview',{k:v for k,v in body.items() if k!='command_id'})
    assert preview['data']['ports'][0]['units']=={'kind':'dimensionless'}
    assert c.call('GET',path)['data']==m
    first=c.call('POST',path+'/edits',body)
    assert c.call('POST',path+'/edits',body)['data']==first['data']
    c.call('POST',path+'/edits',{**body,'command_id':uid()},status=409)
    c.call('POST',path+'/edits',{**body,'edits':[]},status=409)
    m=first['data']
    for bad in ['',{'kind':'physical','expression':'USD'},{'kind':'physical','expression':'m;evil()'},{'kind':'physical','expression':''},{}]:
        attempt=edits({'kind':'dimensionless'});attempt[0]['ports'][0]['units']=bad
        edit(c,m,attempt,status=422 if (bad.get('expression') if isinstance(bad,dict) else None) in ('USD','m;evil()') else 400)
        assert c.call('GET',path)['data']==m
    attempt=[dict(kind='rename_model',name='rollback'),dict(kind='remove_instance',instance_id=uid())]
    edit(c,m,attempt,status=409);assert c.call('GET',path)['data']==m
    assert prepare(c,commit(c,m))['data']['schema_version']=='3'


def test_exact_active_version_closure_and_retained_unused(service):
    c=service;m=edit(c,create(c),edits())['data'];old=copy.deepcopy(m['definitions'][0]);v=old['definition_version_id']
    changes=[dict(kind='update_port',port_id=p['port_id'],fields={'units':{'kind':'dimensionless'}}) for p in old['ports']]
    revision=dict(kind='revise_definition',temp_key='v2',definition_id=old['definition_id'],expected_definition_version_id=v,changes=changes)
    reply=edit(c,m,[revision]);m=reply['data'];new=reply['created_ids']['v2']['definition_version_id']
    prepare(c,commit(c,m),status=422)  # Creating a newer version does not rebind.
    moves=[dict(kind='replace_local_instance_version',instance_id=i['instance_id'],expected_definition_version_id=v,version_ref=dict(definition_version_id=new)) for i in m['instances']]
    m=edit(c,m,moves[:1])['data'];prepare(c,commit(c,m),status=422)
    m=edit(c,m,moves[1:])['data'];pin=commit(c,m)
    assert next(d for d in pin['definitions'] if d['definition_version_id']==v)==old
    assert prepare(c,pin)['data']['schema_version']=='3'


def test_legacy_edit_mixed_versions_and_exact_source(service):
    c=service;m=edit(c,create(c,'2'),creation(),version='2')['data'];before=commit(c,m)
    m=edit(c,m,[dict(kind='rename_model',name='Typed current draft')])['data']
    assert m['schema_version']=='3' and m['definitions']==before['definitions']
    d=m['definitions'][0]
    m=edit(c,m,[dict(kind='revise_definition',temp_key='new',definition_id=d['definition_id'],expected_definition_version_id=d['definition_version_id'],changes=[dict(kind='rename_definition',name='New explicit version')])])['data']
    pin=commit(c,m)
    assert pin['definitions'][0]==d and pin['definitions'][1]['definition_version_id']!=d['definition_version_id']
    assert all(p['units']=={'kind':'dimensionless'} for p in pin['definitions'][1]['ports'])
    assert pin['source_files']==before['source_files']
    assert c.call('GET','/models/'+m['model_id']+'/revisions/'+before['model_revision_id'])['data']==before
    prepare(c,pin)


def package(c,pin):
    return c.call('GET','/models/'+pin['model_id']+'/export?revision='+pin['model_revision_id'])['data']


def import_model(c,p,status=201):
    return c.call('POST','/imports',dict(command_id=uid(),expected_revision=None,study_id=c.study,package=p,preserve_public_ids=True),status=status)


def test_package_ancestry_import_restore_and_conflicting_definition(service):
    c=service;m=edit(c,create(c,'2'),creation(),version='2')['data'];old=commit(c,m)
    m=edit(c,m,[dict(kind='rename_model',name='Mixed authority')])['data']
    d=m['definitions'][0]
    m=edit(c,m,[dict(kind='revise_definition',temp_key='new',definition_id=d['definition_id'],expected_definition_version_id=d['definition_version_id'],changes=[dict(kind='update_port',port_id=d['ports'][0]['port_id'],fields=dict(units={'kind':'unspecified'}))])])['data']
    latest=commit(c,m);p=package(c,latest);validate('ModelPackage3',p)
    assert p['revisions']==[old,latest]
    other=PrivateModel()
    try:
        # Change the same immutable definition in only the later revision.
        bad=copy.deepcopy(p);last=bad['revisions'][-1];last['definitions'][0]['name']='tampered'
        last['digest']=digest({k:v for k,v in last.items() if k!='digest'})
        bad['digest']=digest({k:v for k,v in bad.items() if k!='digest'})
        import_model(other,bad,status=409)
        restored=import_model(other,p)['data']
        assert restored['definitions']==latest['definitions'] and restored['source_files']==latest['source_files']
        assert package(other,latest)==p
        other.restart()
        assert package(other,latest)==p
        assert other.call('GET','/models/'+old['model_id']+'/revisions/'+old['model_revision_id'])['data']==old
        import_model(other,p,status=409)
    finally:other.close()
    # An incomplete selected immutable version also remains importable data-only.
    draft=edit(c,create(c),edits())['data'];incomplete=commit(c,draft);p=package(c,incomplete)
    other=PrivateModel()
    try:
        restored=import_model(other,p)['data'];assert restored['ports']==incomplete['ports']
        prepare(other,incomplete,status=422)
    finally:other.close()


def test_all_active_ports_and_unused_definition_readiness(service):
    c=service
    for direction in ('input','output'):
        es=edits({'kind':'dimensionless'})
        next(p for p in es[0]['ports'] if p['direction']==direction)['units']={'kind':'unspecified'}
        m=commit(c,edit(c,create(c),es)['data']);prepare(c,m,status=422)
        proof=c.call('POST','/models/'+m['model_id']+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=config(m,c)))['data']
        assert len(proof['diagnostics'])==2  # Includes the internally connected occurrence.
    es=edits({'kind':'dimensionless'});unused=edits()[0];unused['temp_key']='unused';es.append(unused)
    m=commit(c,edit(c,create(c),es)['data']);prepare(c,m)


def test_assumptions_and_resolved_incompatible_connections(service):
    c=service;es=edits({'kind':'physical','expression':'m'})
    # Keep assumption/reference fields exactly as accepted by the existing model2 contract.
    links=[dict(evidence_version_id=uid(),relation='supports')]
    es.append(dict(kind='add_assumption',temp_key='assumption',owner=dict(kind='model'),statement='Explicit unit basis',evidence_links=links))
    m=edit(c,create(c),es)['data'];pin=commit(c,m)
    assert pin['assumptions']==m['assumptions'] and len(pin['assumptions'])==1
    assert pin['assumptions'][0]['evidence_links']==links
    for units in ('kg','degC'):
        bad=edits({'kind':'physical','expression':'m'});bad[0]['ports'][0]['units']['expression']=units
        unchanged=create(c);edit(c,unchanged,bad,status=422)
        assert c.call('GET','/models/'+unchanged['model_id'])['data']==unchanged
    # An old protocol cannot smuggle legacy strings into the new writer.
    edit(c,m,creation(),version='2',status=422)


def test_actionable_unsupported_incompatible_and_prepare_diagnostics(service):
    c=service;m=create(c)
    bad=edits({'kind':'physical','expression':'USD'})
    response=edit(c,m,bad,status=422)
    assert response['error']['fields'][0]['code']=='unit_unsupported'
    assert response['error']['fields'][0]['path']=='edits/0/ports/0/units'
    bad=edits({'kind':'physical','expression':'K'});bad[0]['ports'][0]['units']['expression']='degC'
    response=edit(c,m,bad,status=422)
    assert response['error']['fields'][0]['code']=='unit_incompatible'
    assert response['error']['fields'][0]['element_ref']
    pin=commit(c,edit(c,m,edits())['data'])
    response=prepare(c,pin,status=422)
    assert response['error']['fields'][0]['code']=='unit_unspecified'


def test_model3_requires_private3_configuration(service):
    c=service;m=commit(c,edit(c,create(c),edits({'kind':'dimensionless'}))['data'])
    cfg=config(m,c);cfg['schema_version']='2'
    c.call('POST','/models/'+m['model_id']+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg),status=422)


def test_physical_static_preparation_and_configuration_unit_diagnostics(service):
    import base64
    c=service;m=commit(c,edit(c,create(c),edits({'kind':'physical','expression':'J/kg'}))['data'])
    cfg=config(m,c);cfg['inputs'][0]['units']='MJ/kg';cfg['inputs'][0]['value']=1
    path='/models/'+m['model_id']
    proof=c.call('POST',path+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg))['data']
    assert proof['compatible'] and proof['input_interpretations'][0]['conversion']['destination_value']==1000000
    catalog=c.call('GET','/unit-catalog')['data']
    assert proof['input_interpretations'][0]['conversion']['catalog_digest']==catalog['catalog_digest']
    for unit,code in [('USD','unit_unsupported'),('kg','unit_incompatible')]:
        bad=copy.deepcopy(cfg);bad['inputs'][0]['units']=unit
        result=c.call('POST',path+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=bad))['data']
        assert not result['compatible']
        issue=next(x for x in result['diagnostics'] if x['code']==code)
        assert issue['path']=='inputs/0/units' and issue['element_ref']==cfg['inputs'][0]['target']['port_id']
    artifact = prepare(c, m)['data']
    validate('PreparedModelArtifact3', artifact)
    binding=next(f for f in artifact['files'] if f['path']=='generated/bindings.json')
    blob=c.call('GET','/preparations/'+artifact['preparation_id']+'/files/'+binding['file_id'])['data']
    bindings=json.loads(base64.b64decode(blob['bytes']))
    assert all(p['units']=='J/kg' for kind in ('inputs','outputs') for p in bindings[kind])
    catalog_file=next(f for f in artifact['files'] if f['path']=='provenance/patched/config/modeling.units.json')
    blob=c.call('GET','/preparations/'+artifact['preparation_id']+'/files/'+catalog_file['file_id'])['data']
    assert json.loads(base64.b64decode(blob['bytes']))['catalog_digest']==catalog['catalog_digest']


def test_model3_template_and_missing_units_distinction(service):
    c=service
    m=c.call('POST','/models',dict(schema_version='3',command_id=uid(),expected_revision=None,study_id=c.study,name='Example',template='two_component_example'),status=201)['data']
    validate('ModelDraft3',m)
    assert all(p['units']=={'kind':'dimensionless'} for p in m['ports'])
    bad=edits();del bad[0]['ports'][0]['units']
    response=edit(c,m,bad,status=400)
    assert response['error']['code']=='invalid_request' and response['error']['fields']==[]


def quantity_edit(m, statement='Specific energy at the selected boundary'):
    d=m['definitions'][-1]
    return dict(kind='revise_definition',temp_key='described',definition_id=d['definition_id'],
                expected_definition_version_id=d['definition_version_id'],changes=[dict(
                    kind='set_quantity_definition',port_id=d['ports'][0]['port_id'],statement=statement)])


def test_quantity_atomic_preview_selective_rebind_replay_and_exact_history(service):
    c=service;m=edit(c,create(c),edits({'kind':'dimensionless'}))['data'];old=commit(c,m)
    d=m['definitions'][0];iid=m['instances'][0]['instance_id'];path='/models/'+m['model_id']
    change=quantity_edit(m)
    moves=[change,dict(kind='replace_local_instance_version',instance_id=iid,
        expected_definition_version_id=d['definition_version_id'],version_ref=dict(temp_key='described'))]
    body=dict(schema_version='4',command_id=uid(),expected_revision=m['draft_revision'],edits=moves)
    preview=c.call('POST',path+'/preview',{k:v for k,v in body.items() if k!='command_id'})['data']
    assert preview['schema_version']=='4' and preview['definitions'][-1]['quantity_definitions']==[
        dict(port_id=d['ports'][0]['port_id'],statement=change['changes'][0]['statement'])]
    assert c.call('GET',path)['data']==m
    response=c.call('POST',path+'/edits',body);new=response['data']
    assert c.call('POST',path+'/edits',body)['data']==new
    c.call('POST',path+'/edits',{**body,'edits':[]},status=409)
    c.call('POST',path+'/edits',{**body,'command_id':uid()},status=409)
    assert new['definitions'][0]==d and new['source_files']==old['source_files']
    assert new['annotations']==old['annotations']
    described=new['definitions'][-1]
    assert described['annotations']==d['annotations']
    assert [{**p,'definition_version_id':d['definition_version_id']} for p in described['ports']]==d['ports']
    assert [i['instance_id'] for i in new['instances']]==[i['instance_id'] for i in m['instances']]
    assert [i['definition_version_id'] for i in new['instances']]==[described['definition_version_id'],d['definition_version_id']]
    pin=commit(c,new);assert c.call('GET',path+'/revisions/'+old['model_revision_id'])['data']==old
    cap=c.call('GET','/capabilities')['data']
    assert '4' in cap['schema_versions'] and any(x['id']=='quantity_definitions' and x['version']=='1' and x['supported'] for x in cap['capabilities'])
    artifact=prepare(c,pin)['data']
    proof=c.call('POST',path+'/configuration-compatibility',dict(model_revision_id=pin['model_revision_id'],configuration_candidate=config(pin,c)))['data']
    assert proof['input_interpretations'][0]['conversion']['catalog_digest']==c.call('GET','/unit-catalog')['data']['catalog_digest']
    assert artifact['model_package_manifest']==package(c,pin)
    assert artifact['model_package_manifest']['schema_version']=='4'
    clear=quantity_edit(new);clear['changes']=[dict(kind='clear_quantity_definition',port_id=d['ports'][0]['port_id'])]
    cleared=c.call('POST',path+'/edits',dict(schema_version='4',command_id=uid(),expected_revision=new['draft_revision'],edits=[clear]))['data']
    assert cleared['definitions'][-1]['quantity_definitions']==[]
    assert cleared['definitions'][-2]==described


@pytest.mark.parametrize('legacy', [True,False])
def test_quantity_semantics_import_notes_membership_and_unresolved(service,legacy):
    c=service;m=edit(c,create(c,'2' if legacy else '3'),creation() if legacy else edits(),version='2' if legacy else '3')['data']
    before=commit(c,m);d=m['definitions'][0];path='/models/'+m['model_id']
    p=package(c,before)
    note=dict(element_ref=d['ports'][0]['port_id'],text='A port-targeted note is not a quantity definition')
    p['revisions'][0]['definitions'][0]['annotations']=[note]
    p['revisions'][0]['digest']=digest({k:v for k,v in p['revisions'][0].items() if k!='digest'})
    record=next(f for f in p['files'] if f['path']=='revisions/'+before['model_revision_id']+'.json')
    raw=canonical(p['revisions'][0]);record.update(size=len(raw),sha256=raw_hash(raw))
    p['digest']=digest({k:v for k,v in p.items() if k!='digest'})
    other=PrivateModel()
    try:
        m=import_model(other,p)['data'];d=m['definitions'][0]
        change=quantity_edit(m)
        def apply(changes,status=200):
            return other.call('POST',path+'/edits',dict(schema_version='4',command_id=uid(),expected_revision=m['draft_revision'],edits=changes),status=status)
        foreign=copy.deepcopy(change);foreign['changes'][0]['port_id']=uid()
        apply([foreign],409)
        stale=copy.deepcopy(change);stale['expected_definition_version_id']=uid();apply([stale],409)
        apply([change,dict(kind='remove_instance',instance_id=uid())],409)
        assert other.call('GET',path)['data']==m
        m=apply([change])['data'];pin=commit(other,m)
        assert pin['definitions'][0]['annotations']==pin['definitions'][1]['annotations']==[note]
        assert pin['definitions'][1]['quantity_definitions']==[dict(port_id=d['ports'][0]['port_id'],statement=change['changes'][0]['statement'])]
        assert [p['units'] for p in pin['definitions'][1]['ports']]==[p['units'] for p in d['ports']]
        exported=package(other,pin)
        prepare(other,pin,status=200 if legacy else 422)
    finally:other.close()
    for bad_kind in ('duplicate','foreign','capability'):
        other=PrivateModel()
        try:
            bad=copy.deepcopy(exported);last=bad['revisions'][-1]
            if bad_kind=='duplicate':last['definitions'][-1]['quantity_definitions'].append(dict(port_id=d['ports'][0]['port_id'],statement='Different duplicate'))
            elif bad_kind=='foreign':last['definitions'][-1]['quantity_definitions'][0]['port_id']=uid()
            else:bad['required_capabilities'].append('unsupported/1')
            last['digest']=digest({k:v for k,v in last.items() if k!='digest'});bad['digest']=digest({k:v for k,v in bad.items() if k!='digest'})
            import_model(other,bad,status=422)
            imported=import_model(other,exported)['data']
            assert imported['definitions']==pin['definitions'] and package(other,pin)==exported
        finally:other.close()
