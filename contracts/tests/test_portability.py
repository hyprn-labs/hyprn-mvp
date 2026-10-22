import copy
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_modeling_contract import Client,creation,source,uid,validate,digest
# The suite's private services are owned by the test scope for the whole session.
pytest_plugins=('modeling_contract_fixture',)

def test_exact_source_ancestry_and_identity_roundtrip_into_fresh_store():
    c=Client();edits=creation();edits[0]['source']=source(b'\xef\xbb\xbf# caf\xc3\xa9\r\noutputs["y"] = inputs["x"]\r\n')
    m=c.edit(c.create(),edits)['data'];m1=c.commit(m)
    m=c.edit(m,[dict(kind='rename_instance',instance_id=m['instances'][0]['instance_id'],name='Renamed Unicode \u03b1')])['data'];m2=c.commit(m)
    package=c.call('GET',f"/models/{m['model_id']}/export?revision={m2['model_revision_id']}")['data'];validate('ModelPackage',package)
    assert package['files'], 'portable package needs declared exact source/revision file manifest'
    assert [r['model_revision_id'] for r in package['revisions']]==[m1['model_revision_id'],m2['model_revision_id']]
    other=Client(base=os.environ['HYPRN_MVP_MODEL_IMPORT_URL'],study=c.study,key=Path(os.environ['HYPRN_MVP_MODEL_IMPORT_KEY_FILE']).read_bytes().strip())
    body=dict(command_id=uid(),expected_revision=None,study_id=c.study,package=package,preserve_public_ids=True)
    result=other.call('POST','/imports',body,status=201)['data'];assert result['model_id']==m['model_id']
    again=other.call('GET',f"/models/{m['model_id']}/export?revision={m2['model_revision_id']}")['data'];assert again==package
    for pin in (m1,m2): assert other.call('GET',f"/models/{m['model_id']}/revisions/{pin['model_revision_id']}")['data']==pin
    other.call('POST','/imports',{**body,'command_id':uid()},status=409)
    bad=copy.deepcopy(package);bad['revisions'][-1]['source_files'][0]['bytes']='bG9zc3k=';bad['digest']=digest({k:v for k,v in bad.items() if k!='digest'})
    other.call('POST','/imports',{**body,'command_id':uid(),'package':bad},status=409)

def test_public_contract_contains_no_native_routes_or_escape_hatch():
    import json
    root=Path(__file__).resolve().parents[2]
    for p in [root/'contracts/hyprn-mvp.openapi.yaml',root/'contracts/modeling.openapi.yaml']:
        text=p.read_text().lower()
        # Native identifiers as whole field names; "alternative_id" is a study brief field.
        import re
        assert not re.search(r'/api/v1/|_probe|whatsopt_options|(?<![a-z])(native_id|analysis_id|discipline_id)',text)
        assert json.loads(text)['openapi']=='3.1.0'
