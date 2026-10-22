"""Finite operational observations, never execution authorization or diagnostics."""
from datetime import datetime, timezone
import math
import re
import sqlite3
from .database import DatabaseUnavailable
import sys
import time
from time import time as wall_time
from .contracts import DomainError

PUBLICATION_INTERVAL = 10
OBSERVATION_LIFETIME = 30
CAPABILITY = 'flat_explicit_scalar'
# Terminal invalidation is retried briefly under store lock contention. Each attempt
# also waits up to the store busy timeout; afterwards the 30 s lifetime still expires 'ready'.
STOP_ATTEMPTS = 3
STOP_BACKOFF = 0.5

def transient_lock_error(error):
    """SQLITE_BUSY after the store busy timeout: another connection held the lock.

    The failed statement or COMMIT left nothing behind (Store.connection rolls back), so the
    trusted dispatcher may repeat its idempotent iteration later. Never a data error. (Kept
    outside store.py, which is an attested execution source.)

    SQLITE_LOCKED (base code 6, "database table is locked") is a conflict inside
    one connection or shared cache that waiting cannot clear; it is not transient.
    """
    if isinstance(error, DatabaseUnavailable):
        return True
    if not isinstance(error, sqlite3.OperationalError):
        return False
    code = getattr(error, 'sqlite_errorcode', None)
    if code is not None:
        return code & 0xff == 5  # SQLITE_BUSY (incl. extended codes)
    return str(error) == 'database is locked'

def valid_observation_time(value):
    # Bound before isfinite (huge Python integers can overflow float conversion),
    # and keep both timestamps representable by the public date-time contract.
    return type(value) in (int,float) and 0 <= value <= 253402300769 and math.isfinite(value)

def runtime_identity(value):
    """Closed nonsecret identity, never paths, files or attestation documents."""
    fields={'image_digest','architecture','python_version','worker_entrypoint','policy_digest'}
    if not isinstance(value,dict) or set(value)!=fields or any(type(v) is not str for v in value.values()):
        raise ValueError('Invalid runtime identity')
    if (re.fullmatch(r'sha256:[0-9a-f]{64}',value['image_digest']) is None
            or re.fullmatch(r'[0-9a-f]{64}',value['policy_digest']) is None
            or value['architecture'] not in {'arm64','aarch64','amd64','x86_64'}
            or re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',value['python_version']) is None
            or value['worker_entrypoint']!='hyprn_mvp_integration.worker'):
        raise ValueError('Invalid runtime identity')
    return dict(value)

class ObservationPublisher:
    """Called only by the existing trusted dispatcher; no parallel heartbeat."""
    def __init__(self, store, native, *, monotonic=time.monotonic, sleep=time.sleep):
        self.store, self.native, self.monotonic, self.sleep = store, native, monotonic, sleep
        self.last = None
        self.stalled = False
        self.ready_window = None

    def ready(self):
        """Owner's successfully published observation; never a user-scoped read."""
        now = wall_time()
        return (self.ready_window is not None
                and self.ready_window[0] <= now < self.ready_window[1])

    def stall(self, iterations, error):
        """The dispatcher failed `iterations` consecutive iterations on store
        contention. Readiness must not keep 'ready' while nothing can be dispatched: log once at
        error level and publish 'unavailable' now (and on every refresh until recovery)."""
        if not self.stalled:
            self.stalled = True
            print(f'dispatcher: ERROR store contention for {iterations} consecutive iterations ({error}); '
                  'publishing executor unavailable until an iteration succeeds', file=sys.stderr, flush=True)
        self.last = None
        self.ready_window = None
        try:
            self.refresh()
        except (sqlite3.OperationalError, DatabaseUnavailable) as failure:
            if not transient_lock_error(failure):
                raise
            # Still locked: the next iteration's refresh retries (self.last is None).

    def recovered(self):
        """An iteration succeeded after a stall: republish the real state immediately."""
        if self.stalled:
            self.stalled = False
            self.last = None
            print('dispatcher: store contention cleared; readiness republished', file=sys.stderr, flush=True)

    def refresh(self):
        tick = self.monotonic()
        if self.last is not None and tick-self.last < PUBLICATION_INTERVAL:
            return False
        self.last = tick
        self.ready_window = None
        # A slow authority check must not manufacture a newer freshness window.
        observed = wall_time()
        if self.stalled:
            try:
                self.store.publish_execution_observation('unavailable', 'executor_unavailable', observed)
            except (sqlite3.OperationalError, DatabaseUnavailable) as error:
                if transient_lock_error(error):
                    self.last = None
                raise
            return True
        runtime = None
        try:
            if self.native.require_attestation() is not True:
                raise RuntimeError('Attestation not confirmed')
            # Existing native operation verifies the selection against its
            # attestation fingerprint; only these five fields enter the store.
            runtime = runtime_identity(self.native.bundle_runtime()['runtime'])
            status, reason = 'ready', None
        except OSError:
            status, reason = 'unavailable', 'executor_unavailable'
        except (RuntimeError, ValueError, TypeError, KeyError):
            status, reason = 'unavailable', 'attestation_invalid'
        try:
            self.store.publish_execution_observation(status, reason, observed, runtime)
        except (sqlite3.OperationalError, DatabaseUnavailable) as error:
            # Not published: let the dispatcher's next iteration try again, not 10 s later.
            if transient_lock_error(error):
                self.last = None
            raise
        if status == 'ready':
            self.ready_window = (observed, observed + OBSERVATION_LIFETIME)
        return True

    def stopped(self):
        """Terminal invalidation is immediate, even inside the normal 10s throttle.

        Bounded retries under store lock contention. Returns whether it was
        published; a lock that outlasts the retries never masks why the dispatcher exits.
        """
        self.ready_window = None
        for attempt in range(STOP_ATTEMPTS):
            try:
                self.store.publish_execution_observation('unavailable', 'executor_unavailable', wall_time())
                return True
            except (sqlite3.OperationalError, DatabaseUnavailable) as error:
                if not transient_lock_error(error):
                    raise
                if attempt + 1 < STOP_ATTEMPTS:
                    self.sleep(STOP_BACKOFF * 2 ** attempt)
        print('executor: unavailable observation not published (store busy); readiness turns stale within '
              f'{OBSERVATION_LIFETIME} s', file=sys.stderr, flush=True)
        return False

def _observation(row, now):
    fields={'status','reason','observed_at','expires_at'}
    if not isinstance(row, dict) or set(row) not in (fields,fields|{'runtime'}):
        return None
    start, end = row['observed_at'], row['expires_at']
    if not valid_observation_time(start) or type(end) not in (int,float) or not valid_observation_time(now):
        return None
    if not 0 <= start <= now or end != start+OBSERVATION_LIFETIME:
        return None
    if not ((row['status']=='ready' and row['reason'] is None) or
            (row['status']=='unavailable' and row['reason'] in ('executor_unavailable','attestation_invalid'))):
        return None
    return row

def compare_runtimes(source,current,*,basis,observed_at=None,expires_at=None):
    source=runtime_identity(source)
    try: current=runtime_identity(current)
    except ValueError: current=None
    return dict(source=source,current=current,
        state='unavailable' if current is None else ('same' if current==source else 'different'),
        basis=basis,observed_at=observed_at,expires_at=expires_at)

def runtime_comparison(store,actor,study,source):
    """Authorized app-only preview; no model/native I/O or launch authority."""
    with store.connection() as db: store.authorize(db,actor,study)
    observed=store.execution_observation()
    now=wall_time()  # Storage latency must not extend the observation lifetime.
    with store.connection() as db: store.authorize(db,actor,study)
    row=_observation(observed,now)
    current=None;start=end=None
    if row is not None and row['status']=='ready' and now<row['expires_at']:
        try: current=runtime_identity(row.get('runtime'))
        except ValueError: pass
        else:
            start=_stamp(row['observed_at']);end=_stamp(row['expires_at'])
    return compare_runtimes(source,current,basis='executor_observation',observed_at=start,expires_at=end)

def _stamp(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat().replace('+00:00','Z')

def execution_readiness(store, model, actor, study):
    with store.connection() as db:
        store.authorize(db, actor, study)
    model_reason = None
    try:
        status, payload = model.call(actor, study, 'GET', '/capabilities',
                                     response_schema='CapabilitiesResponseRead3', resources=[study])
        if status != 200:
            raise ValueError('Unexpected capabilities status')
        capabilities = [c for c in payload['data']['capabilities'] if c['id']==CAPABILITY]
        if len(capabilities)!=1:
            raise ValueError('Ambiguous capability')
        if capabilities[0]['supported'] is not True:
            model_reason = 'capability_unsupported'
    except (DomainError, OSError, ValueError, KeyError, TypeError):
        model_reason = 'modeling_unavailable'
    # No lock spans bounded private I/O. Recheck authority and freshness afterward.
    with store.connection() as db:
        store.authorize(db, actor, study)
    observed = store.execution_observation()
    now = wall_time()
    row = _observation(observed, now)
    stale = row is None or now >= row['expires_at']
    reasons = ['observation_stale'] if stale else ([row['reason']] if row['reason'] else [])
    if model_reason:
        reasons.append(model_reason)
    status = 'unknown' if stale else ('unavailable' if reasons else 'ready')
    return dict(readiness_schema_version='1', capability=CAPABILITY, status=status, reasons=reasons,
                observed_at=_stamp(row['observed_at']) if row else None,
                expires_at=_stamp(row['expires_at']) if row else None)


def supports_descriptive_execution(capabilities, model):
    """Check the exact backend contract; operational readiness remains separate."""
    if not isinstance(capabilities,dict):return False
    execution=capabilities.get('execution_versions',{})
    pairs = [('8','2'), ('10','3')]
    if not any(
        bundle in execution.get('bundle_versions', [])
        and artifact in execution.get('artifact_versions', [])
        for bundle, artifact in pairs
    ) or 'hyprn_mvp.openmdao.program/1' not in execution.get('program_protocols', []):
        return False
    if model['schema_version'] not in capabilities.get('schema_versions',[]):return False
    advertised={(c.get('id'),c.get('version')) for c in capabilities.get('capabilities',[]) if c.get('supported') is True}
    return all((name.split('/')[0],name.split('/')[1] if '/' in name else '1') in advertised
               for name in model['required_capabilities'])
