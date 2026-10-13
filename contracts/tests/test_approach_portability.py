"""Data-only portable record bounds remain unchanged."""
import io,zipfile
import pytest
from hyprn_mvp_app import computational_export as exports

@pytest.mark.parametrize('kind',['traversal','expanded','paths'])
def test_offline_reader_rejects_unsafe_archive_before_payload_processing(kind):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        if kind=='traversal':z.writestr('../escape',b'{}')
        elif kind=='paths':
            for i in range(4097):z.writestr(str(i),b'')
        else:
            for i in range(3):z.writestr(str(i),b'x'*(12*1024*1024))
    with pytest.raises((ValueError,exports.DomainError)):exports.inspect_record(stream.getvalue())


@pytest.mark.parametrize('fault',['result_units','result_value','strip_quantities','model_tag','strip_claim','limit_pin'])
def test_portable8_resealed_descriptive_and_result_tampering_rejected(fault):
    import json
    from test_approach_export import ready,rewrite
    from hyprn_mvp_app.store import canonical,digest
    e,(_,_,raw)=ready()
    def alter(manifest,files):
        prefix='hyprn-mvp/runs/'+e['rid']+'/'
        if fault in ('result_units','result_value'):
            path=prefix+'results.json';value=json.loads(files[path])
            value['outputs'][0]['units' if fault=='result_units' else 'value']='wrong' if fault=='result_units' else False
            files[path]=canonical(value)
            row=next(row for row in manifest['runs'] if row['run_id']==e['rid'])
            row['results_digest']=digest(value);files[prefix+'identity.json']=canonical(row)
        elif fault in ('strip_quantities','model_tag'):
            path=prefix+'bundle/model.json' if fault=='strip_quantities' else prefix+'bundle/manifest.json'
            value=json.loads(files[path])
            if fault=='strip_quantities':value['definitions'][0].pop('quantity_definitions')
            else:value['model_schema_version']='3'
            files[path]=canonical(value)
        else:
            path=manifest['approaches'][0]['path'];value=json.loads(files[path])
            version=next(v for v in value['approach_versions'] if v['approach_version_id']==value['root_approach_version_id'])
            if fault=='strip_claim':version['content'].pop('original_question')
            else:version['content']['limit_items'][0]['evidence_links'][0]['evidence_version_id']='00000000-0000-4000-8000-000000000000'
            files[path]=canonical(value)
    with pytest.raises((ValueError,exports.DomainError,KeyError)):exports.inspect_record(rewrite(raw,alter))
