"""Fixed execution bridge policy; no service restart or candidate execution."""
# P2 live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')
import io
import json
import sys
import pytest
from contextlib import contextmanager
import dispatch_runtime
from hyprn_mvp_app import dispatcher
from test_result_dependencies import source, native


class Native:
    def resolve_results(self, sources):
        return sources


def test_resolve_results_has_exact_one_argument_on_both_ends(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'stdin', type('Input', (), {'buffer': io.BytesIO(b'{"data": []}\n')})())
    assert dispatcher.NativeBridge().resolve_results([]) == []
    request = json.loads(capsys.readouterr().out)
    assert request == {'method':'resolve_results','args':[[]]}
    assert dispatch_runtime.native_call(Native(), **{'method':request['method'],'values':request['args']}) == []


@pytest.mark.parametrize('method,args', [('load_node',['abc']), ('resolve_results',[]),
    ('resolve_results',[[],[]]), ('resolve_results',['native-uuid']), ('resolve_results',[[{'process_uuid':'abc'}]])])
def test_invalid_bridge_calls_fail_before_io_or_native(method,args,monkeypatch,capsys):
    with pytest.raises(ValueError): dispatcher.NativeBridge().call(method,*args)
    assert capsys.readouterr().out == ''
    with pytest.raises(ValueError): dispatch_runtime.native_call(Native(),method,args)


def test_hydration_cannot_resolve_or_attest_on_either_end():
    for method,args in [('resolve_results',[[]]),('require_attestation',[])]:
        with pytest.raises(ValueError): dispatcher.NativeBridge(read_only=True).call(method,*args)
        with pytest.raises(ValueError): dispatch_runtime.native_call(Native(),method,args,read_only=True)


@contextmanager
def wire(monkeypatch,native,*,read_only=False):
    """Exercise actual app/host codecs with an in-process stdio transport only."""
    output=io.StringIO();calls=[]
    class Response:
        def readline(self,limit):
            raw=output.getvalue().encode();output.seek(0);output.truncate()
            method,args=dispatcher.bridge_operation(raw,read_only=read_only);calls.append(method)
            try:response={'data':dispatch_runtime.native_call(native,method,args,read_only=read_only)}
            except (OSError,RuntimeError,ValueError,TimeoutError):response={'error':'native_unavailable'}
            return dispatcher.bridge_encode(response)
    with monkeypatch.context() as scoped:
        scoped.setattr(sys,'stdout',output)
        scoped.setattr(sys,'stdin',type('Input',(),{'buffer':Response()})())
        yield dispatcher.NativeBridge(read_only=read_only),calls


def test_real_native_source_crosses_fixed_wire_unchanged(source,native,monkeypatch):
    with wire(monkeypatch,native) as (bridge,calls):
        assert bridge.resolve_results([source['approved']])==[source['approved']|{'result_uuid':source['results'].uuid}]
    assert calls==['resolve_results']


@pytest.mark.parametrize('field',['process','store','request','value','digest','extra','result_uuid'])
def test_forged_native_pins_never_return_source_results(source,native,monkeypatch,field):
    import copy
    from hyprn_mvp_app.store import uid
    item=copy.deepcopy(source['approved'])
    if field in ('process','store'):item['association'][field+'_uuid']=uid()
    elif field=='request':item['request']['payload_digest']='f'*64
    elif field=='value':item['outputs'][0]['value']=999
    elif field=='digest':item['results_digest']='e'*64
    else:item[field]='untrusted'
    with wire(monkeypatch,native) as (bridge,calls):
        with pytest.raises(ValueError):bridge.resolve_results([item])


@pytest.mark.parametrize('raw',[b'[]\n',b'{"method":"resolve_results","method":"inspect","args":[[]]}\n',
    b'{"method":"resolve_results","args":[[]],"extra":true}\n',
    b'{"method":"resolve_results","args":[NaN]}\n',
    b'{"method":"resolve_results","args":[1e999]}\n',b'{"method":"resolve_results","args":[[]]}',
    b'{"method":[],"args":[]}\n'])
def test_malformed_host_frames_fail_closed(raw):
    with pytest.raises(ValueError):dispatcher.bridge_operation(raw)


def test_exact_byte_bound_matches_host_and_app_including_newline(monkeypatch,capsys):
    raw=dispatcher.bridge_request('resolve_results',[[]])
    monkeypatch.setattr(dispatcher,'MAX_MESSAGE',len(raw))
    assert dispatcher.bridge_operation(raw)==('resolve_results',[[]])
    assert dispatch_runtime.native_call(Native(),'resolve_results',[[]])==[]
    monkeypatch.setattr(dispatcher,'MAX_MESSAGE',len(raw)-1)
    with pytest.raises(ValueError):dispatcher.NativeBridge().resolve_results([])
    assert capsys.readouterr().out==''
    with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),'resolve_results',[[]])
    with pytest.raises(ValueError):dispatcher.bridge_operation(raw)


@pytest.mark.parametrize('raw',[b'{"error":"native_unavailable"}\n',b'{"data":[],"extra":true}\n',
    b'{"data":[],"data":[]}\n',b'{"data":1e999}\n',b'[]\n',b'{"data":[]}'])
def test_bad_resolver_response_is_not_success(monkeypatch,raw,capsys):
    monkeypatch.setattr(sys,'stdin',type('Input',(),{'buffer':io.BytesIO(raw)})())
    with pytest.raises(ValueError):dispatcher.NativeBridge().resolve_results([])


def test_transport_loss_is_distinct_from_known_source_refusal(monkeypatch,capsys):
    monkeypatch.setattr(sys,'stdin',type('Input',(),{'buffer':io.BytesIO()})())
    with pytest.raises(ConnectionError):dispatcher.NativeBridge().resolve_results([])


@pytest.mark.parametrize('method,arity',list(dispatcher.BRIDGE_ARITIES.items()))
def test_every_operation_uses_same_arity_and_hydration_policy(method,arity):
    args=[None]*(arity+1)
    with pytest.raises(ValueError):dispatcher.bridge_request(method,args)
    with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),method,args)
    if method!='read_record':
        with pytest.raises(ValueError):dispatcher.bridge_request(method,[None]*arity,read_only=True)
        with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),method,[None]*arity,read_only=True)


@pytest.mark.parametrize('kind',['sources','outputs','boolean','units'])
def test_source_shape_bounds_before_native_lookup(source,kind):
    import copy
    rows=[copy.deepcopy(source['approved'])]
    if kind=='sources':rows*=65
    elif kind=='outputs':rows[0]['outputs']*=501
    elif kind=='boolean':rows[0]['outputs'][0]['value']=True
    else:rows[0]['outputs'][0]['units']='m'*4097
    with pytest.raises(ValueError):dispatcher.bridge_request('resolve_results',[rows])
    with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),'resolve_results',[rows])


@pytest.mark.parametrize('method,args',[('require_attestation',[]),('bundle_runtime',[]),('matches',[{}]),('inspect',['native-id']),('launch',[{},{}]),('read_record',[{},{}]),('resolve_results',[[]])])
def test_exports_mode_has_only_archive_authority(method,args,capsys):
    with pytest.raises(ValueError):dispatcher.NativeBridge(exports_only=True).call(method,*args)
    assert capsys.readouterr().out==''
    with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),method,args,exports_only=True)


@pytest.mark.parametrize('value',[None,'native-id',{}, {'schema_version':1}, {'schema_version':'1','process_uuid':'native-id'}])
def test_archive_request_is_closed_before_native_io(value,capsys):
    with pytest.raises(ValueError):dispatcher.NativeBridge(exports_only=True).archive_record(value)
    assert capsys.readouterr().out==''
    with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),'archive_record',[value],exports_only=True)


def test_real_exports_only_queue_drain_and_same_root_download(tmp_path,monkeypatch):
    import hashlib,base64,zipfile
    from aiida import orm
    from test_computational_archive import record,native as archive_native
    from test_computational_records import retain
    from hyprn_mvp_app.store import Store,uid
    from hyprn_mvp_app.computational_export import records_for_store
    import scoped_fixture as guard
    from checks import PROJECTION_SCOPE,NATIVE_BACKEND
    node,preflight=record();store=Store(tmp_path/'application.sqlite')
    c=retain(store,node,preflight,uid());service=records_for_store(store)
    assert service.root==store.path.parent/'computational-records'
    with store.connection() as db:before={table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in ('configurations','run_associations','outbox')}
    count=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.CalcJobNode).count()
    native=archive_native()
    def forbidden(*args,**kwargs):raise AssertionError('Scientific or model operation reached')
    for method in ('launch','require_attestation','bundle_runtime','matches','inspect','resolve_results'):
        monkeypatch.setattr(native,method,forbidden)
    q=service.enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[c['rid']]))
    assert q['state']=='queued'
    guard.run_export_dispatcher(PROJECTION_SCOPE,native,store.path,q['request_id'])
    preview=service.status(c['actor'],c['sid'],q['request_id']);assert preview['state']=='reviewable',preview
    request=service.enqueue_create(c['actor'],c['sid'],dict(command_id=uid(),preview_id=q['request_id'],expected_preview_digest=preview['preview']['preview_digest']))
    guard.run_export_dispatcher(PROJECTION_SCOPE,native,store.path,request['request_id'])
    ready=service.status(c['actor'],c['sid'],request['request_id']);assert ready['state']=='ready',ready
    raw=records_for_store(Store(store.path)).download(c['actor'],c['sid'],request['request_id'])
    assert hashlib.sha256(raw).hexdigest()==ready['download']['sha256']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert 'computations.aiida' in z.namelist()
        for path,value in c['payload']['bundle']['files'].items():assert z.read('hyprn-mvp/runs/'+c['rid']+'/bundle/'+path)==base64.b64decode(value)
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.CalcJobNode).count()==count
    with store.connection() as db:assert before=={table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in before}
    (PROJECTION_SCOPE.root/'evidence/dispatch-record.zip').write_bytes(raw)
    (PROJECTION_SCOPE.root/'evidence/dispatch-proof.json').write_text(json.dumps(dict(preview=preview,ready=ready,scientific_rows_unchanged=True,native_process_count=count,artifact_root=str(service.root)),indent=2))


@pytest.mark.parametrize('kind',['raw','encoded','inventory','extra','version'])
def test_archive_response_bounds_before_base64_decode(monkeypatch,kind):
    from hyprn_mvp_app.store import uid
    value=dict(schema_version='1',origin_store_uuid=uid(),archive_base64='',archive_size=0,archive_sha256='a'*64,inventory={},inventory_digest='b'*64)
    if kind=='raw':value['archive_size']=16*1024*1024+1
    elif kind=='encoded':value['archive_base64']='A'*(((16*1024*1024+2)//3)*4+4)
    elif kind=='inventory':value['inventory']={'oversize':'x'*(4*1024*1024)}
    elif kind=='extra':value['secret']='no'
    else:value['schema_version']=1
    def forbidden(*args,**kwargs):raise AssertionError('Decoded before bounds/schema validation')
    monkeypatch.setattr(dispatcher.base64,'b64decode',forbidden)
    with pytest.raises(ValueError):dispatcher.archive_response(value)


@pytest.mark.parametrize('args',[['--exports-only'],['--export-request','not-a-uuid'],['--exports-only','--once','--run-id','x'],['--exports-only','--once','--hydrate'],['--exports-only','--once','--prepare-only']])
def test_exports_cli_rejects_mixed_or_unbounded_modes_before_store(args,monkeypatch):
    monkeypatch.setattr(sys,'argv',['dispatcher',*args])
    monkeypatch.setattr(dispatcher,'Store',lambda *a:pytest.fail('Store opened for invalid mode'))
    with pytest.raises(SystemExit):dispatcher.main()


def test_shared_record_root_refuses_symlink_and_cloud(tmp_path):
    from hyprn_mvp_app.computational_export import records_for_store
    from types import SimpleNamespace
    link=tmp_path/'computational-records';link.symlink_to(tmp_path/'elsewhere')
    for path in (tmp_path/'application.sqlite',tmp_path/'CloudStorage/app.sqlite'):
        with pytest.raises(ValueError):records_for_store(SimpleNamespace(path=path))


@pytest.mark.parametrize('args',[['--exports-only'],['--exports-only','--once','--serve'],['--exports-only','--once','--native-fault','before_node'],['--exports-only','--once','--hydrate'],['--export-request','bad']])
def test_host_exports_cli_rejects_mixed_modes_before_runtime(args,monkeypatch):
    monkeypatch.setattr(sys,'argv',['dispatch_runtime',*args])
    monkeypatch.setattr(dispatch_runtime.application_runtime,'check',lambda:pytest.fail('Runtime touched for invalid mode'))
    with pytest.raises(SystemExit):dispatch_runtime.main()


@pytest.mark.parametrize('mode',['exports','serve'])
def test_host_mode_wiring_requires_no_startup_attestation(mode,monkeypatch):
    from checks import PROJECTION_SCOPE
    from test_computational_archive import native
    from hyprn_mvp_integration.calculation import NativeExecution
    value=native();calls=[]
    monkeypatch.setattr(value,'require_attestation',lambda:pytest.fail('Data work gated on worker readiness'))
    monkeypatch.setattr(NativeExecution,'from_environment',lambda:value)
    monkeypatch.setattr(dispatch_runtime,'ROOT',PROJECTION_SCOPE.root)
    monkeypatch.setenv('AIIDA_PATH',str(PROJECTION_SCOPE.root/'aiida'))
    monkeypatch.setattr(dispatch_runtime.application_runtime,'check',lambda:calls.append('owned-app-check'))
    monkeypatch.setattr(dispatch_runtime.signal,'signal',lambda *a:None)
    # P5 N4: main() now refuses unbound; this isolated wiring test opts out explicitly.
    monkeypatch.setattr(dispatch_runtime,'require_bound_release',lambda:None)
    def child(actual,command,**options):
        assert actual is value
        assert options['exports_only']==(mode=='exports') and options['allow_exports']==(mode=='serve')
        assert ('--exports-only' in command)==(mode=='exports')
        assert ('--with-exports' in command)==(mode=='serve')
        calls.append('child');return 0
    monkeypatch.setattr(dispatch_runtime,'bridge_child',child)
    monkeypatch.setattr(sys,'argv',['dispatch_runtime',*(['--exports-only','--once'] if mode=='exports' else ['--serve'])])
    assert dispatch_runtime.main()==0 and calls==['owned-app-check','child']


def test_serving_drains_one_export_before_observation_and_skips_unready_science(tmp_path,monkeypatch):
    from hyprn_mvp_app.store import Store,uid
    from test_computational_archive import record
    from test_computational_records import retain
    node,preflight=record();store=Store(tmp_path/'application.sqlite');c=retain(store,node,preflight,uid())
    with store.connection(write=True) as db:db.execute("UPDATE outbox SET state='accepted_run'")
    key=tmp_path/'model.key';key.write_text('synthetic')
    monkeypatch.setenv('HYPRN_MVP_APP_STORE',str(store.path));monkeypatch.setenv('HYPRN_MVP_MODEL_URL','http://invalid.local')
    monkeypatch.setenv('HYPRN_MVP_MODEL_KEY_FILE',str(key));events=[]
    monkeypatch.setattr(dispatcher,'ModelingClient',lambda *a:object())
    class Service:
        def __init__(self,*args):pass
        def dispatch(self,*args,**kwargs):pytest.fail('Unready scientific dispatch reached')
    class Observation:
        def __init__(self,*args):pass
        def refresh(self):
            events.append('observation');store.publish_execution_observation('unavailable','attestation_invalid',1000.)
        def stopped(self):events.append('stopped')
    monkeypatch.setattr(dispatcher,'Submissions',Service);monkeypatch.setattr(dispatcher,'ObservationPublisher',Observation)
    monkeypatch.setattr(dispatcher,'export_once',lambda *a:events.append('one-export'))
    monkeypatch.setattr(dispatcher.select,'select',lambda *a:([True],[],[]))
    monkeypatch.setattr(sys,'argv',['dispatcher','--with-exports'])
    dispatcher.main()
    assert events==['one-export','observation','stopped']


def test_archive_mode_and_arity_match_both_ends(monkeypatch,capsys):
    for values in ([],[{},{}]):
        with pytest.raises(ValueError):dispatcher.bridge_request('archive_record',values,exports_only=True)
        with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),'archive_record',values,exports_only=True)
    for options in ({},{'read_only':True},{'read_only':True,'exports_only':True}):
        with pytest.raises(ValueError):dispatcher.bridge_request('archive_record',[{}],**options)
        with pytest.raises(ValueError):dispatch_runtime.native_call(Native(),'archive_record',[{}],**options)
    monkeypatch.setattr(dispatcher,'MAX_MESSAGE',32)
    with pytest.raises(ValueError):dispatcher.NativeBridge(exports_only=True).archive_record({'schema_version':'1','padding':'x'*64})
    assert capsys.readouterr().out==''
