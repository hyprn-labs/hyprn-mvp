"""Build genuine archive material in a separately guarded native-only child.

No HTTP, candidate execution, or production data. The API tests copy these fresh
application records and immutable native/package bytes into their own stores.
"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]


def main(*,context=False):
    import scoped_fixture as guard
    scope=guard.scope_from_environment()
    if sys.executable!=guard.APPROVED_PYTHON or scope.interpreter!=guard.APPROVED_PYTHON:
        raise ValueError('Reviewed native fixture interpreter required')
    sys.path[:0]=[str(ROOT/'deployment'),str(ROOT/'application/src'),str(ROOT/'application/tests'),
        str(ROOT/'integration/src'),str(ROOT/'integration/tests')]
    import checks
    checks.PROJECTION_SCOPE,checks.NATIVE_BACKEND=guard.create_native_fixture(scope)
    import test_computational_archive as fixture
    from test_computational_records import retain
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store,uid
    from hyprn_mvp_app.computational_export import records_for_store
    original=fixture.fixture
    names=iter(('Configuration origin','Sizing result','Modified comparison'))
    def fresh():
        case=original();c=case['frozen']['configuration']
        if context:c['name']=next(names)
        c.update(configuration_id=uid(),configuration_revision_id=uid())
        case['prepared']['configuration_revision_id']=c['configuration_revision_id']
        return case
    fixture.fixture=fresh
    directory=scope.root/'artifacts/material';directory.mkdir()
    store=Store(directory/'application.sqlite')
    actor=Auth(store,'http://127.0.0.1:19999').provision('owner','correct horse battery staple')
    if context:
        origin,origin_preflight=fixture.record();parent=retain(store,origin,origin_preflight,actor)
    source,preflight=fixture.record();source_record=retain(store,source,preflight,actor)
    if context:
        from hyprn_mvp_app.store import digest
        assemble=fixture.assemble_bundle
        def derived(rid,prepared,files,frozen,runtime,dependencies=None):
            c=frozen['configuration'];pc=parent['payload']['frozen']['configuration']
            c['derivation']=dict(source_run_id=parent['rid'],source_configuration_revision_id=pc['configuration_revision_id'],source_configuration_digest=pc['digest'],source_runtime=parent['payload']['bundle']['manifest']['runtime'],changes=[])
            c['digest']=digest({k:v for k,v in c.items() if k!='digest'})
            return assemble(rid,prepared,files,frozen,runtime,dependencies)
        fixture.assemble_bundle=derived
    node,preflight=fixture.record(upstream=(source,preflight));case=retain(store,node,preflight,actor)
    if context:
        for saved in (parent,source_record,case):
            item=saved['preflight']['computations'][0]
            retained=fixture.native().read_record(item['request'],item['association'])
            saved['payload']['status']={key:retained[key] for key in ('process_state','exit_status')}
            with store.connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(saved['payload']),saved['rid']))
    service=records_for_store(store)
    def archived(value):
        response=fixture.native().archive_record(value)
        (directory/'archive-preflight.json').write_text(json.dumps(value))
        (directory/'archive-response.json').write_text(json.dumps(response))
        return response
    preview_body=dict(command_id=uid(),selected_run_ids=[case['rid']])
    preview=service.enqueue_preview(actor,case['sid'],preview_body)
    assert service.process_one(archived)
    preview=service.status(actor,case['sid'],preview['request_id']);assert preview['state']=='reviewable',preview
    create_body=dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest'])
    ready=service.enqueue_create(actor,case['sid'],create_body)
    assert service.process_one(fixture.native().archive_record)
    ready=service.status(actor,case['sid'],ready['request_id']);assert ready['state']=='ready',ready
    assert service.download(actor,case['sid'],ready['request_id'])
    # Capture the actual durable post-build/pre-publication window; the public
    # status must hide its internal preview until reviewable/ready.
    building=service.enqueue_preview(actor,case['sid'],dict(command_id=uid(),selected_run_ids=[case['rid']]))
    class Crash(BaseException):pass
    def fault(point):
        if point=='built':raise Crash()
    service.fault=fault
    try:service.process_one(fixture.native().archive_record)
    except Crash:pass
    with store.connection(write=True) as db:
        building_row=dict(db.execute('SELECT * FROM computational_record_requests WHERE request_id=?',(building['request_id'],)).fetchone())
        assert building_row['state']=='building' and json.loads(building_row['payload_json'])['preview']
        # Keep this snapshot separate so ordinary capacity fixtures start empty.
        db.execute('DELETE FROM computational_record_requests WHERE request_id=?',(building['request_id'],))
        db.execute('DELETE FROM receipts WHERE command_id=?',(building_row['command_id'],))
    service.fault=lambda point:None
    failed=service.enqueue_preview(actor,case['sid'],dict(command_id=uid(),selected_run_ids=[case['rid']]))
    def blocked(preflight):raise ValueError('private /private/native/path API_TOKEN=do-not-disclose')
    assert service.process_one(blocked)
    assert service.status(actor,case['sid'],failed['request_id'])['state']=='failed'
    metadata=dict(actor=actor,sid=case['sid'],rid=case['rid'],ancestor=source_record['rid'],
        preview=preview,ready=ready,preview_body=preview_body,create_body=create_body,
        building_row=building_row,failed_id=failed['request_id'])
    (directory/'fixture.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(dict(material=str(directory),native_scope=str(scope.root))))


if __name__=='__main__':
    assert sys.argv[1:] in ([],['--ui-c'])
    main(context=sys.argv[1:]==['--ui-c'])
