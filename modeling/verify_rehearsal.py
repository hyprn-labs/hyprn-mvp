"""Portable export, import into a second modeling service and restart retention.

A manual verification against two disposable test services, never an installation:
HYPRN_MVP_MODEL_URL / HYPRN_MVP_MODEL_KEY_FILE name the source service and
HYPRN_MVP_MODEL_IMPORT_URL / HYPRN_MVP_MODEL_IMPORT_KEY_FILE the import service, whose test
container HYPRN_MVP_MODEL_IMPORT_CONTAINER is restarted and whose native rows are read through
HYPRN_MVP_MODEL_CONTAINER (modeling/tests/native_query.py). The evidence goes to a new folder
below the evidence root (deployment/local_paths.py).
"""
import base64,json,os,subprocess,sys,tempfile,time,urllib.error
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'contracts/tests'))
sys.path.insert(0,str(R/'deployment'))
import local_paths
from test_modeling_contract import Client,creation,source,uid,digest,candidate,canonical,raw_hash
E=Path(tempfile.mkdtemp(prefix='hyprn-mvp-modeling-import-',dir=local_paths.evidence_root()))
c=Client();edits=creation();edits[0]['source']=source(b'\xef\xbb\xbf# caf\xc3\xa9\r\noutputs["y"] = inputs["x"]\r\n')
result=c.edit(c.create(),edits);m=result['data'];ids=result['created_ids'];m1=c.commit(m)
m=c.edit(m,[dict(kind='revise_definition',temp_key='v2',definition_id=ids['d']['definition_id'],expected_definition_version_id=ids['d']['definition_version_id'],changes=[dict(kind='set_source',source=source(b'outputs["y"] = inputs["x"] * 3\n'))]),dict(kind='replace_local_instance_version',instance_id=ids['a']['instance_id'],expected_definition_version_id=ids['d']['definition_version_id'],version_ref=dict(temp_key='v2'))])['data'];m2=c.commit(m)
path=f"/models/{m['model_id']}/export?revision={m2['model_revision_id']}";package=c.call('GET',path)['data']
other=Client(base=os.environ['HYPRN_MVP_MODEL_IMPORT_URL'],study=c.study,key=Path(os.environ['HYPRN_MVP_MODEL_IMPORT_KEY_FILE']).read_bytes().strip())
body=dict(command_id=uid(),expected_revision=None,study_id=c.study,package=package,preserve_public_ids=True)
imported=other.call('POST','/imports',body,status=201)
cfg=candidate(m1,c.study);cfg.update(configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None);cfg['digest']=digest(cfg)
prepare=dict(command_id=uid(),model_revision_id=m1['model_revision_id'],configuration_snapshot=cfg,configuration_digest=cfg['digest'])
prep_path=f"/models/{m['model_id']}/prepare-execution";artifact=other.call('POST',prep_path,prepare)['data']
(E/'portable-package.json').write_bytes(canonical(package));(E/'prepared-artifact.json').write_bytes(canonical(artifact))
sys.path.insert(0,str(R/'modeling/tests'))
from native_query import snapshot as native_snapshot
def snapshot():
    return {t:rows for t,rows in native_snapshot().items() if t in ('modeling_identities','modeling_revisions','modeling_commands')}
before=snapshot()
subprocess.run(['docker','restart',os.environ['HYPRN_MVP_MODEL_IMPORT_CONTAINER']],check=True)
for _ in range(50):
    try: other.call('GET','/capabilities');break
    except (urllib.error.URLError,ConnectionError,TimeoutError):time.sleep(.2)
else:raise RuntimeError('restart did not become ready')
assert snapshot()==before
assert other.call('GET',path)['data']==package
for pin in [m1,m2]:assert other.call('GET',f"/models/{m['model_id']}/revisions/{pin['model_revision_id']}")['data']==pin
assert other.call('POST',prep_path,prepare)['data']==artifact
assert other.call('POST','/imports',body,status=201)['data']==imported['data']
for f in artifact['files']:
    raw=base64.b64decode(other.call('GET',f"/preparations/{artifact['preparation_id']}/files/{f['file_id']}")['data']['bytes']);assert raw_hash(raw)==f['sha256'] and len(raw)==f['size']
assert snapshot()==before
fixture=dict(study_id=c.study,model_id=m['model_id'],model_revision_ids=[m1['model_revision_id'],m2['model_revision_id']],preparation_id=artifact['preparation_id'],package_digest=package['digest'],prepared_digest=artifact['prepared_digest'],package_file_count=len(package['files']),import_command_id=body['command_id'],prepare_command_id=prepare['command_id'],source_sha256=[x['sha256'] for x in m2['source_files']],restart='all modeling rows, exact revisions, manifests, file bytes and receipt replay unchanged')
(E/'portable-fixture.json').write_text(json.dumps(fixture,indent=2)+'\n');print(json.dumps(fixture,indent=2))
