"""Exact reviewed source offers never grant candidate-content exemptions."""
from pathlib import Path
import hashlib
import json
import sys
import pytest
import hyprn_mvp_integration.computational_export as archive

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'deployment'))
import modeling_runtime  # noqa: E402

# Every support source the modeling image build copies into its provenance inputs, with the
# path it has inside a prepared artifact. Exported records carry these bytes, and sensitive()
# must accept them without any allowance.
CURRENT_SUPPORT=sorted((name,'provenance/support/'+Path(name).name) for name in modeling_runtime.support_sources())
IDENTITIES='provenance/support/'+modeling_runtime.SCHEMA_IDENTITY_FILE


def test_support_inventory_is_the_build_inventory_without_schema_copies():
    assert ('deployment/modeling_runtime.py','provenance/support/modeling_runtime.py') in CURRENT_SUPPORT
    assert len({path for _,path in CURRENT_SUPPORT})==len(CURRENT_SUPPORT)
    assert set(modeling_runtime.support_sources())|set(modeling_runtime.SCHEMA_IDENTITY_SOURCES)=={
        name for name in modeling_runtime.source_hashes() if not name.endswith('.patch')}
    assert not set(modeling_runtime.support_sources())&set(modeling_runtime.SCHEMA_IDENTITY_SOURCES)


@pytest.mark.parametrize('source,path',CURRENT_SUPPORT)
def test_current_support_sources_pass_without_any_allowance(source,path):
    raw=(ROOT/source).read_bytes()
    archive.sensitive(raw)
    assert path not in archive.AUDITED_PROVENANCE
    assert not archive.audited_provenance({path},path,raw)
    assert not archive.audited_provenance({'sources/candidate.py'},'sources/candidate.py',raw)
    with pytest.raises(ValueError):archive.sensitive(raw+b'\nAPI_TOKEN=credential-value')


def test_artifacts_record_schema_identities_instead_of_schema_copies():
    # The capture by the pinned producer records the current schema identities.
    from execution_fixtures import criteria_free_fixture
    files=criteria_free_fixture()['files']
    assert not any(path in files for path in ('provenance/support/'+Path(name).name for name in modeling_runtime.SCHEMA_IDENTITY_SOURCES))
    recorded=json.loads(files[IDENTITIES])
    assert recorded==modeling_runtime.schema_identities()
    for item in recorded['schemas']:
        raw=(ROOT/item['path']).read_bytes()
        assert item['sha256']==hashlib.sha256(raw).hexdigest() and item['size']==len(raw)
    inventory=json.loads(files['provenance/generator.json'])['patched_files']
    assert any(f['path']==IDENTITIES and f['sha256']==hashlib.sha256(files[IDENTITIES]).hexdigest() for f in inventory)
    archive.sensitive(files[IDENTITIES])


def test_exact_provenance_allowances_match_the_producer_fixture():
    from execution_fixtures import fixture
    case=fixture();matched=set()
    for path,sha in archive.AUDITED_PROVENANCE.items():
        raw=case['files'].get(path)
        if raw is not None and hashlib.sha256(raw).hexdigest()==sha:
            matched.add(path)
            assert archive.audited_provenance({path},path,raw)
            assert not archive.audited_provenance(set(),path,raw)
    assert matched==set(archive.AUDITED_PROVENANCE)


def test_provenance_and_license_allowances_are_closed_finite_inventories():
    assert archive.AUDITED_PROVENANCE=={
        'provenance/upstream.tar.gz':'4937188df6ea12daa8a2b00767005e3649d2974ab6e634409f7756043ef0b360',
        'provenance/upstream/app/models/user.rb':'f9b2f06d3cd1331cfe447a91143e3c03a69cfd6853ba642821d4cd5d11a051d1',
        'provenance/patched/app/models/user.rb':'f9b2f06d3cd1331cfe447a91143e3c03a69cfd6853ba642821d4cd5d11a051d1',
        'provenance/patches/030-configuration.patch':'05b318ea908336e2c7ce371f4250fdc1264c73c1bf0d719e381e80f43465adff'}
    assert not hasattr(archive,'AUDITED_PROVENANCE_REVISIONS')
    assert archive.AUDITED_LICENSES=={
        'licenses/native/aio_pika-9.5.8.dist-info/METADATA':'f15ca6ca8696f6520f98e1667cf788da9b2e8b722caec89e73328ddaaad6b71f',
        'licenses/native/shortuuid-1.0.13.dist-info/METADATA':'76f39eb41b4bb36f8e36682178ff470d36153c9a49e6d451db0ae9e4a81f5819',
        'licenses/native/charset_normalizer-3.5.2.dist-info/METADATA':'89ce6362bb7be88558f4be99a98f5d1b4da93d19cd0323e5ee0bac05cf883dfb',
        'licenses/worker/charset_normalizer-3.5.2.dist-info/METADATA':'89ce6362bb7be88558f4be99a98f5d1b4da93d19cd0323e5ee0bac05cf883dfb',
        'licenses/native/jedi-0.18.2.dist-info/METADATA':'f21e26976fba61c1ed460d48988b44b61103fcd8058a3ace8e0061417b7effa3',
        'licenses/native/psutil-7.2.2.dist-info/METADATA':'525f8ba78523cf7bc3759d62a105e7c57fd679ea702402b9449fb0746aa0217f',
        'licenses/worker/tomli-2.5.0.dist-info/METADATA':'0d7d3b46cb99dac60216978cebca446f9ec3a21fd3e1f9650086a2e373654e27'}



def test_historical_artifact_passes_the_export_content_check():
    import base64
    import gzip

    path = ROOT / 'integration/tests/fixtures/native-programs-pre-schema-split.json.gz'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        '3fdd2de1275704b7b3fa2a59a409ecaef00bb1f18ea13bfff7bd4325ae1ea018'
    )
    capture = json.loads(gzip.decompress(raw))
    for row in capture['cases']['chain']['prepared']['files']:
        if row['role'] != 'provenance':
            continue
        data = base64.b64decode(capture['blobs'][row['sha256']], validate=True)
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        if not archive.audited_provenance({row['path']}, row['path'], data):
            archive.sensitive(data)
    assert path.read_bytes() == raw
