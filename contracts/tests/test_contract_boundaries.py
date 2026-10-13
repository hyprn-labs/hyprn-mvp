import base64,copy,json,os
from pathlib import Path
from test_modeling_contract import Client,creation,candidate,source,uid,digest,canonical,raw_hash
# The suite's private services are owned by the test scope for the whole session.
pytest_plugins=('modeling_contract_fixture',)

def test_duplicate_valid_body_and_depth_size_are_rejected_before_parsing():
    c=Client();m=c.create();path=f"/models/{m['model_id']}/edits"
    body=dict(command_id=uid(),expected_revision=m['draft_revision'],edits=[])
    raw=canonical(body)[:-1]+b',"edits":[]}'
    c.call('POST',path,raw=raw,status=400)
    c.call('POST',path,raw=b'['*40+b'0'+b']'*40,status=413)
    c.call('POST',path,raw=b' '*2097153,status=413)
    assert c.call('GET',f"/models/{m['model_id']}")['data']==m

def test_units_are_trusted_bounded_linear_compatibility_not_conversion():
    c=Client();edits=creation()
    for p in edits[0]['ports']:p['units']='km'
    m=c.commit(c.edit(c.create(),edits)['data']);cfg=candidate(m,c.study)
    cfg['inputs'][0].update(value=2000,units='m')
    path=f"/models/{m['model_id']}/configuration-compatibility"
    assert c.call('POST',path,dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg))['data']['compatible']
    assert cfg['inputs'][0]['value']==2000
    for unit in ['s','furlong','degC']:
        bad=copy.deepcopy(cfg);bad['inputs'][0]['units']=unit
        assert not c.call('POST',path,dict(model_revision_id=m['model_revision_id'],configuration_candidate=bad))['data']['compatible']
    hot=creation()
    for p in hot[0]['ports']:p['units']='K'
    m=c.commit(c.edit(c.create(),hot)['data']);cfg=candidate(m,c.study);cfg['inputs'][0]['units']='degC'
    assert not c.call('POST',f"/models/{m['model_id']}/configuration-compatibility",dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg))['data']['compatible']

def test_prepared_files_and_receipt_keep_original_scope_and_bytes():
    c=Client();m=c.edit(c.create(),creation())['data'];pin=c.commit(m);cfg=candidate(pin,c.study)
    cfg.update(configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None);cfg['digest']=digest(cfg)
    body=dict(command_id=uid(),model_revision_id=pin['model_revision_id'],configuration_snapshot=cfg,configuration_digest=cfg['digest'])
    p=f"/models/{m['model_id']}/prepare-execution";artifact=c.call('POST',p,body)['data']
    c.edit(m,[dict(kind='rename_instance',instance_id=m['instances'][0]['instance_id'],name='later')])
    assert c.call('POST',p,body)['data']==artifact
    for f in artifact['files']:
        path=f"/preparations/{artifact['preparation_id']}/files/{f['file_id']}"
        assert raw_hash(base64.b64decode(c.call('GET',path)['data']['bytes']))==f['sha256']
        c.call('GET',path,resources=[uid()],status=403)
        Client(study=uid()).call('GET',path,status=404)
    receipt=f"/commands/{body['command_id']}?study_id={c.study}&category=model"
    assert c.call('GET',receipt)['data']['response']['data']==artifact
    c.call('GET',receipt,resources=[uid()],status=403)

def test_flat_port_changes_disconnect_annotation_and_removal():
    c=Client();r=c.edit(c.create(),creation());m=r['data'];ids=r['created_ids'];old=ids['d']['definition_version_id']
    changes=[dict(kind='rename_definition',name='Changed'),dict(kind='update_port',port_id=ids['d']['ports']['x'],fields=dict(name='X label')),dict(kind='create_port',temp_key='extra',direction='input',name='extra',code_symbol='extra',value_type='real_scalar',units=''),dict(kind='remove_port',port_id=ids['d']['ports']['y'])]
    edits=[dict(kind='disconnect',connection_id=ids['wire']['connection_id']),dict(kind='revise_definition',temp_key='new',definition_id=ids['d']['definition_id'],expected_definition_version_id=old,changes=changes),dict(kind='replace_local_instance_version',instance_id=ids['a']['instance_id'],expected_definition_version_id=old,version_ref=dict(temp_key='new')),dict(kind='set_annotation',element_ref=ids['a']['instance_id'],text='explicit annotation'),dict(kind='remove_instance',instance_id=ids['b']['instance_id'])]
    m=c.edit(m,edits)['data'];assert len(m['instances'])==1 and not m['connections']
    assert m['annotations'][0]['text']=='explicit annotation'
    assert {p['code_symbol'] for p in m['definitions'][-1]['ports']}=={'x','extra'}

def test_portable_manifest_tamper_and_lossy_import_rejected_atomically():
    c=Client();m=c.commit(c.edit(c.create(),creation())['data']);pkg=c.call('GET',f"/models/{m['model_id']}/export?revision={m['model_revision_id']}")['data']
    other=Client(base=os.environ['HYPRN_MVP_MODEL_IMPORT_URL'],study=c.study,key=Path(os.environ['HYPRN_MVP_MODEL_IMPORT_KEY_FILE']).read_bytes().strip())
    variants=[]
    for field,value in [('sha256','0'*64),('size',999),('file_id',uid())]:
        bad=copy.deepcopy(pkg);bad['files'][0][field]=value;variants.append((bad,422))
    bad=copy.deepcopy(pkg);bad['files'][0]['path']='../outside';variants.append((bad,400))
    bad=copy.deepcopy(pkg);bad['files']+=bad['files'][:1];variants.append((bad,422))
    bad=copy.deepcopy(pkg);bad['required_capabilities']+=['nested_composition'];variants.append((bad,422))
    bad=copy.deepcopy(pkg);bad['schema_version']='99';variants.append((bad,400))
    bad=copy.deepcopy(pkg);bad['revisions'][0]['source_files'][0]['bytes']='bG9zc3k=';variants.append((bad,422))
    bad=copy.deepcopy(pkg);bad['revisions'][0]['parent_model_revision_id']=uid();variants.append((bad,422))
    for bad,status in variants:
        bad['digest']=digest({k:v for k,v in bad.items() if k!='digest'})
        other.call('POST','/imports',dict(command_id=uid(),expected_revision=None,study_id=c.study,package=bad,preserve_public_ids=True),status=status)
        other.call('GET',f"/models/{m['model_id']}",status=404)
    other.call('POST','/imports',dict(command_id=uid(),expected_revision=None,study_id=c.study,package=pkg,preserve_public_ids=True),status=201)
