"""Native-store evidence around the backend-independent HTTP suite."""
import os
import sys
from native_query import native_connection,snapshot
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'contracts/tests'))
from test_modeling_contract import Client,creation,candidate,uid
# The suite's private services are owned by the test scope for the whole session.
pytest_plugins=('modeling_contract_fixture',)

def database_snapshot(domain_only=False):
    return snapshot(domain_only)

def test_preview_and_compatibility_allocate_no_rows_or_sequences():
    c=Client();m=c.create();before=database_snapshot()
    c.call('POST',f"/models/{m['model_id']}/preview",dict(expected_revision=m['draft_revision'],edits=creation()))
    assert database_snapshot()==before
    m=c.commit(c.edit(m,creation())['data']);cfg=candidate(m,c.study);before=database_snapshot()
    for _ in range(3):
        r=c.call('POST',f"/models/{m['model_id']}/configuration-compatibility",dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg))
        assert r['data']['compatible']
    assert database_snapshot()==before

def test_rejected_batch_preserves_all_native_rows_and_exact_sources():
    c=Client();m=c.edit(c.create(),creation())['data'];before=database_snapshot(True)
    c.edit(m,[dict(kind='rename_instance',instance_id=m['instances'][0]['instance_id'],name='must rollback'),dict(kind='remove_instance',instance_id=m['instances'][1]['instance_id'])],status=409)
    assert database_snapshot(True)==before

def test_same_names_do_not_autojoin_native_ports():
    c=Client();edits=creation()[:-1];m=c.edit(c.create(),edits)['data']
    assert m['connections']==[]
    with native_connection() as conn:
        native=conn.execute('select native_id from modeling_identities where public_id=?',(m['model_id'],)).fetchone()[0]
        count=conn.execute('select count(*) from connections c join variables v on v.id=c.from_id join disciplines d on d.id=v.discipline_id where d.analysis_id=?',(native,)).fetchone()[0]
        assert count==0

def test_concurrent_same_command_has_one_effect_and_one_receipt():
    c=Client();m=c.create();body=dict(command_id=uid(),expected_revision=m['draft_revision'],edits=creation());path='/models/'+m['model_id']+'/edits'
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:c.call('POST',path,body),range(3)))
    assert all(r['data']==results[0]['data'] for r in results)
    with native_connection() as conn:
        assert conn.execute('select count(*) from modeling_commands where command_id=?',(body['command_id'],)).fetchone()[0]==1
    assert len(c.call('GET','/models/'+m['model_id'])['data']['instances'])==2

def test_native_sources_are_exact_and_prepare_never_imports_candidate():
    import base64
    c=Client();edits=creation();raw=b"raise RuntimeError('candidate must never execute on model service')\r\n# \xc3\xa9\r\n"
    from test_modeling_contract import source,digest
    edits[0]['source']=source(raw);draft=c.edit(c.create(),edits)['data'];m=c.commit(draft)
    cfg=candidate(m,c.study);cfg.update(configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None);cfg['digest']=digest(cfg)
    c.call('POST','/models/'+m['model_id']+'/prepare-execution',dict(command_id=uid(),model_revision_id=m['model_revision_id'],configuration_snapshot=cfg,configuration_digest=cfg['digest']))
    with native_connection() as conn:
        rows=conn.execute("select o.python_source from openmdao_discipline_impls o join modeling_identities i on i.native_id=o.discipline_id and i.kind='instance' where i.model_id=?",(m['model_id'],)).fetchall()
        assert len(rows)==2 and all(row[0].encode()==raw for row in rows)
