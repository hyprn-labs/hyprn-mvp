"""Trusted app-side executor: local store/lock owner, fixed stdio native bridge.

Not a public endpoint. Started by the owned host executor via docker exec; the
model service gets neither this channel nor application/native storage access.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import select
import sqlite3
import math
import hashlib
from uuid import UUID
from .execution_bundle import closed
from .execution import StaticPreparation,Submissions
from .modeling import ModelingClient
from .store import Store
from .readiness import ObservationPublisher,transient_lock_error
from .computational_export import records_for_store

MAX_MESSAGE=64*1024*1024
# A store lock held past the busy timeout is transient contention, never a reason to
# exit. The failed transaction rolled back; the iteration is repeated after a capped backoff
# (claim-before-launch and reconciliation-only dispatching/uncertain states prevent any
# double launch). Bounded one-shot modes give up after a fixed number of attempts.
LOCK_BACKOFF_INITIAL=0.5
LOCK_BACKOFF_MAX=30
ONE_SHOT_LOCK_ATTEMPTS=5
# After this many consecutive failed iterations the serving loop publishes
# 'unavailable' (error-level log) so readiness never reports 'ready' through a stall.
STALL_ITERATIONS=3
# The exponent is capped, so the delay stays finite at any attempt count.
LOCK_BACKOFF_MAX_EXPONENT=16

def lock_backoff(attempt):
    return min(LOCK_BACKOFF_MAX,LOCK_BACKOFF_INITIAL*2**min(max(attempt-1,0),LOCK_BACKOFF_MAX_EXPONENT))

def wait_out_lock(error,attempt,*,bounded):
    """Re-raise anything but transient lock contention (and bounded modes past their attempts);
    otherwise log and wait. True means the owned host closed stdin during the wait."""
    if not transient_lock_error(error) or (bounded and attempt>=ONE_SHOT_LOCK_ATTEMPTS):raise error
    delay=lock_backoff(attempt)
    # stdout is the native bridge; diagnostics go to the owned service log.
    print(f'dispatcher: store busy ({error}); attempt {attempt}, retrying in {delay:g} s',file=sys.stderr,flush=True)
    return bool(select.select([sys.stdin],[],[],delay)[0])

BRIDGE_ARITIES={'require_attestation':0,'bundle_runtime':0,'launch':2,
                'matches':1,'inspect':1,'read_record':2,'resolve_results':1,'archive_record':1}
MAX_ARCHIVE=16*1024*1024
MAX_INVENTORY=4*1024*1024

def bridge_encode(value):
    raw=json.dumps(value,allow_nan=False).encode('utf-8')+b'\n'
    if len(raw)>MAX_MESSAGE:raise ValueError('Native bridge bound')
    return raw

def bridge_decode(raw):
    if not raw or len(raw)>MAX_MESSAGE or not raw.endswith(b'\n'):
        raise ValueError('Invalid native bridge frame')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Duplicate bridge field')
            value[key]=item
        return value
    value=json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite bridge value')))
    bridge_encode(value)  # Reject overflowed numbers and enforce one byte policy.
    if not isinstance(value,dict):raise ValueError('Closed bridge envelope required')
    return value

def bridge_request(method,values,*,read_only=False,exports_only=False):
    """Shared framing/arity policy; caller authorization stays in Submissions."""
    if (not isinstance(method,str) or method not in BRIDGE_ARITIES or not isinstance(values,list)
            or len(values)!=BRIDGE_ARITIES[method] or (read_only and method!='read_record')
            or (exports_only and method!='archive_record') or (method=='archive_record' and not exports_only)):
        raise ValueError('Unexpected bridge operation')
    raw=bridge_encode(dict(method=method,args=values))
    if method=='archive_record':closed('ArchiveRecordRequest1',values[0])
    if method=='resolve_results':
        sources=values[0]
        if not isinstance(sources,list) or len(sources)>64:raise ValueError('Source count bound')
        runs=[];count=0
        for source in sources:
            if not isinstance(source,dict) or set(source)!={'source_run_id','request','association','results_digest','outputs'}:
                raise ValueError('Closed approved source required')
            # NativeSource validates the common pin fields. Temporary result
            # fields are schema witnesses only, never transmitted or retained.
            pin={k:source[k] for k in ('source_run_id','request','association','results_digest')}
            closed('NativeSource',pin | dict(result_uuid='00000000-0000-0000-0000-000000000000',label='r'+'0'*32))
            if source['request']['run_id']!=source['source_run_id']:raise ValueError('Source request mismatch')
            runs.append(source['source_run_id']);outputs=source['outputs'];keys=[]
            if not isinstance(outputs,list) or not 0<len(outputs)<=1000:raise ValueError('Source output bound')
            count+=len(outputs)
            if count>1000:raise ValueError('Source scalar count bound')
            for output in outputs:
                if not isinstance(output,dict) or set(output)!={'target','value','units'}:raise ValueError('Closed source scalar required')
                closed('PortRef',output['target'])
                try:finite=type(output['value']) in (int,float) and math.isfinite(output['value'])
                except OverflowError:finite=False
                if (not finite
                        or not isinstance(output['units'],str) or len(output['units'])>4096):
                    raise ValueError('Invalid source scalar')
                keys.append((output['target']['instance_id'],output['target']['port_id']))
            if keys!=sorted(set(keys)):raise ValueError('Distinct ordered outputs required')
        if runs!=sorted(set(runs)):raise ValueError('Distinct ordered sources required')
    return raw

def bridge_operation(raw,*,read_only=False,exports_only=False):
    request=bridge_decode(raw)
    if set(request)!={'method','args'}:raise ValueError('Unexpected bridge operation')
    bridge_request(request['method'],request['args'],read_only=read_only,exports_only=exports_only)
    return request['method'],request['args']


def archive_response(value):
    """Shared pre-decode bounds plus the exact closed private archive schema."""
    fields={'schema_version','origin_store_uuid','inventory','inventory_digest','archive_sha256','archive_size','archive_base64'}
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('Closed archive response required')
    size=value['archive_size'];encoded=value['archive_base64']
    if (type(size) is not int or not 0<=size<=MAX_ARCHIVE or not isinstance(encoded,str)
            or len(encoded)>((MAX_ARCHIVE+2)//3)*4 or len(encoded)!=((size+2)//3)*4):
        raise ValueError('Native archive byte bound')
    from .contracts import canonical,digest
    if len(canonical(value['inventory']))>MAX_INVENTORY:raise ValueError('Native inventory bound')
    closed('ArchiveRecordResponse1',value)
    raw=base64.b64decode(encoded,validate=True)
    if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=value['archive_sha256'] or digest(value['inventory'])!=value['inventory_digest']:
        raise ValueError('Archive byte/inventory identity mismatch')
    return value

def encode_files(value):
    return {**value,'files':{p:base64.b64encode(raw).decode() for p,raw in value['files'].items()}}

def decode_files(value):
    return {**value,'files':{p:base64.b64decode(raw,validate=True) for p,raw in value['files'].items()}}

def encode_record(value):
    return {**value,'bundle':encode_files(value['bundle']) if value['bundle'] is not None else None,
            'artifacts':{p:base64.b64encode(raw).decode() for p,raw in value['artifacts'].items()}}

def decode_record(value):
    return {**value,'bundle':decode_files(value['bundle']) if value['bundle'] is not None else None,
            'artifacts':{p:base64.b64decode(raw,validate=True) for p,raw in value['artifacts'].items()}}

class NativeBridge:
    def __init__(self,*,read_only=False,exports_only=False):self.read_only=read_only;self.exports_only=exports_only
    def call(self,method,*args):
        raw=bridge_request(method,list(args),read_only=self.read_only,exports_only=self.exports_only)
        print(raw.decode('utf-8'),end='',flush=True)
        raw=sys.stdin.buffer.readline(MAX_MESSAGE+1)
        if not raw or len(raw)>MAX_MESSAGE:raise ConnectionError('Native bridge unavailable')
        value=bridge_decode(raw)
        if set(value)!={'data'}:
            if method=='resolve_results':raise ValueError('Source result unavailable')
            raise RuntimeError('Native operation unavailable')
        return value['data']
    def require_attestation(self):return self.call('require_attestation')
    def bundle_runtime(self):return decode_files(self.call('bundle_runtime'))
    def launch(self,bundle,request):return self.call('launch',encode_files(bundle),request)
    def matches(self,request):return self.call('matches',request)
    def inspect(self,process):return self.call('inspect',process)
    def read_record(self,request,association):return decode_record(self.call('read_record',request,association))
    def resolve_results(self,sources):return self.call('resolve_results',sources)
    def archive_record(self,preflight):return archive_response(self.call('archive_record',preflight))


def export_once(store,request_id=None):
    return records_for_store(store).process_one(NativeBridge(exports_only=True).archive_record,request_id=request_id)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id')
    parser.add_argument('--hydrate',action='store_true')
    parser.add_argument('--actor-id')
    parser.add_argument('--study-id')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--exports-only',action='store_true')
    parser.add_argument('--export-request')
    parser.add_argument('--with-exports',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--fault',choices=['after_prepare','before_claim','after_claim'])
    args=parser.parse_args()
    if args.exports_only:
        if (not (args.once or args.export_request) or any((args.run_id,args.hydrate,args.actor_id,args.study_id,args.prepare_only,args.fault,args.with_exports))):
            parser.error('Exports require bounded mode and no execution options')
    elif args.export_request:parser.error('Export request requires exports-only mode')
    if args.export_request:
        try:
            if str(UUID(args.export_request))!=args.export_request:raise ValueError()
        except ValueError:parser.error('Canonical export request identity required')
    if args.with_exports and any((args.once,args.run_id,args.hydrate,args.exports_only,args.prepare_only,args.fault)):
        parser.error('Export iterations belong to the owned serving loop')
    if args.hydrate:
        if not all((args.actor_id,args.study_id,args.run_id)) or any((args.prepare_only,args.once,args.fault)):
            parser.error('Hydration requires exact actor/study/run and no execution options')
    elif args.actor_id or args.study_id:parser.error('Actor/study are for authorized hydration only')
    if (args.prepare_only or args.fault) and not args.run_id:parser.error('Explicit run required')
    bounded=bool(args.once or args.run_id or args.exports_only or args.hydrate)
    store=None;contended=0
    while store is None:
        # Opening runs the additive migration's write transaction, whose COMMIT also
        # waits for every reader: the executor must not die at start either.
        try:store=Store(os.environ['HYPRN_MVP_APP_STORE'])
        except sqlite3.OperationalError as error:
            contended+=1
            if wait_out_lock(error,contended,bounded=bounded):return
    if args.exports_only:
        export_once(store,args.export_request)
        return
    if args.hydrate:
        # No model client, credentials, attestation or dispatch in this path.
        Submissions(store,None,NativeBridge(read_only=True)).hydrate(args.actor_id,args.study_id,args.run_id)
        return
    model=ModelingClient(os.environ['HYPRN_MVP_MODEL_URL'],Path(os.environ['HYPRN_MVP_MODEL_KEY_FILE']).read_bytes().strip())
    native=NativeBridge()
    service=Submissions(store,StaticPreparation(model),native)
    observation=ObservationPublisher(store,native)
    if args.fault:
        def fault(point):
            if point==args.fault:os._exit(77)
        service.fault=fault
    primary=None;stalled=False
    try:
        while True:
            try:
                if args.with_exports:export_once(store)
                observation.refresh()
                with store.connection() as db:
                    runs=[args.run_id] if args.run_id else [r[0] for r in db.execute(
                        "SELECT run_id FROM outbox WHERE state IN ('accepted_run','dispatching') AND COALESCE(json_extract(payload,'$.preparation_state'),'')!='preparation_failed' ORDER BY rowid LIMIT 100")]
                # Export work remains available while the current worker cannot be
                # attested. This observation never authorizes execution: dispatch
                # still performs its own current attestation check.
                if args.with_exports and store.execution_observation()['status']!='ready':runs=[]
                for run in runs:
                    service.dispatch(run,prepare_only=args.prepare_only)
            except sqlite3.OperationalError as error:
                contended+=1
                if transient_lock_error(error) and contended>=STALL_ITERATIONS:
                    observation.stall(contended,error);stalled=True
                if wait_out_lock(error,contended,bounded=bounded):return
                continue
            contended=0
            if stalled:observation.recovered();stalled=False
            if args.once or args.run_id:return
            # Detect the owned host exiting even while idle; do not leave app orphans.
            if select.select([sys.stdin],[],[],1)[0]:return
    except BaseException as error:
        primary=error
        raise
    finally:
        # IN-01: the exit cause propagates; a failing terminal publication is only logged then.
        try:observation.stopped()
        except Exception as failure:
            if primary is None:raise
            print(f'dispatcher: unavailable observation not published at exit ({failure!r}); readiness '
                  'turns stale within its lifetime',file=sys.stderr,flush=True)

if __name__=='__main__':main()
