"""Offline native archive scope remains computational, not explanatory."""
import io,json,zipfile
from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
from hyprn_mvp_integration.computational_export import Export
from hyprn_mvp_app.store import digest
from test_approach_export import ready,SCOPE

def test_offline_native_archive_excludes_failed_basis_and_preserves_result_creator():
    e,(_,_,raw)=ready();path=SCOPE.root/'evidence/approach-computations.aiida'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        m=json.loads(z.read('manifest.json'));path.write_bytes(z.read('computations.aiida'))
    _,_,preflight,_=e['service']._collect(e['actor'],e['sid'],[e['rid']])
    with ArchiveFormatSqlZip().open(path,'r') as archive:
        inventory,_,_=Export(e['native'],preflight).inspect(archive.get_backend())
        assert digest(inventory)==m['native_inventory_digest']
        from hyprn_mvp_app.computational_export import inspect_record
        assert inspect_record(raw,native_inventory=inventory)==m
        processes={n['uuid'] for n in inventory['nodes'] if n['node_type'].startswith('process.')}
        assert processes=={e['node'].uuid,e['source']['node'].uuid}
        assert e['failed']['association']['process_uuid'] not in processes


def test_resealed_wrapper_cannot_forge_mapping_against_verified_native_inventory():
    from copy import deepcopy
    import pytest
    from hyprn_mvp_app.store import uid,canonical
    from hyprn_mvp_app.computational_export import inspect_record,DomainError
    from test_approach_export import rewrite
    e,(_,_,raw)=ready();path=SCOPE.root/'evidence/approach-binding.aiida'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:path.write_bytes(z.read('computations.aiida'))
    _,_,preflight,_=e['service']._collect(e['actor'],e['sid'],[e['rid']])
    with ArchiveFormatSqlZip().open(path,'r') as archive:inventory,_,_=Export(e['native'],preflight).inspect(archive.get_backend())
    def swap(m,files):
        row=next(r for r in m['runs'] if r['run_id']==e['rid']);row['process_uuid']=uid()
        files['hyprn-mvp/runs/'+e['rid']+'/identity.json']=canonical(row)
    with pytest.raises((ValueError,DomainError),match='process scope'):
        inspect_record(rewrite(raw,swap),native_inventory=inventory)
    changed=deepcopy(inventory)
    row=next(r for r in changed['repositories'] if r['path']=='configuration.json');row['sha256']='f'*64
    def reseal(m,files):m['native_inventory_digest']=digest(changed)
    with pytest.raises((ValueError,DomainError),match='frozen bytes'):
        inspect_record(rewrite(raw,reseal),native_inventory=changed)
