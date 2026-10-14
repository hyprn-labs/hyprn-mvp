"""Study-owned approach authoring with exact, bounded scientific references.

The resolver reads only enumerated reference kinds. Private model I/O occurs
outside application transactions; command commits recheck all local witnesses.
Historical reads use retained bytes alone. Nothing here imports candidate code.
"""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import UUID, uuid5

from .approach_closure import (
    KEYS, MAX_BYTES, MAX_CONTENT, MAX_DEPTH, MAX_ENTITIES,
    build_closure, validate_closure, validate_saved, closure_schema, ReferenceIssue,
)
from .execution_bundle import validate_retained_bundle
from .history import History, approach_runs, validate_binding
from .contracts import DomainError, canonical, digest, uid, validate
from .store import evidence_snapshot, exact_evidence


def _signed(value):
    value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
    return value


def _now():
    return datetime.now(timezone.utc).isoformat()


def _retained(callback):
    """Stored corruption exposes no stored text or foreign identifiers."""
    try:
        return callback()
    except (ValueError, KeyError, TypeError, RecursionError, UnicodeError) as exc:
        raise DomainError('corrupt_retained_record', 409) from exc


def saved_version(row, sid):
    """Interpret one stored ``approach_versions`` row of study ``sid``: pure, never a current head.

    Returns the validated ``{version, closure}`` (``validate_saved``) whose identity matches the
    row's columns. Undecodable or invalid stored data and an identity mismatch are
    ``corrupt_retained_record`` 409. Callers read the row in their own authorized connection and
    keep it as their write-time witness (Approaches commands, approach resolution and the
    Configurations approach pin).
    """
    saved = _retained(lambda: validate_saved(json.loads(row['payload']), study_id=sid))
    if any(saved['version'][k] != row[k] for k in ('approach_version_id', 'approach_id', 'study_id', 'version_number')):
        raise DomainError('corrupt_retained_record', 409)
    return saved


class _Resolver:
    def __init__(self, service, actor, sid):
        self.service, self.store = service, service.store
        self.actor, self.sid = actor, sid
        self.tables = {table: {} for table in KEYS}
        self.pins = {}
        self.history = History(self.store)
        self.runs = {}
        self.active = set()

    def row(self, sql, params):
        # SQL comes exclusively from this module's fixed statements.
        with self.store.connection() as db:
            self.store.authorize(db, self.actor, self.sid)
            row = db.execute(sql, params).fetchone()
            if row is None:
                raise DomainError('resource_not_found', 404)
            row = dict(row)
        key = (sql, tuple(params))
        if key in self.pins and self.pins[key] != row:
            raise DomainError('reference_conflict')
        self.pins[key] = row
        return row

    def recheck(self, db):
        self.store.authorize(db, self.actor, self.sid)
        for (sql, params), expected in self.pins.items():
            row = db.execute(sql, params).fetchone()
            if row is None or dict(row) != expected:
                raise DomainError('reference_conflict')
        try:
            self.history.recheck(db, self.actor, self.sid, self.runs.values())
        except DomainError as error:
            # Authorized above in this transaction: a vanished retained run is a changed witness.
            if error.code == 'resource_not_found':
                raise DomainError('reference_conflict') from None
            raise

    def add(self, table, record):
        key = record[KEYS[table]]
        previous = self.tables[table].get(key)
        if previous is not None and previous != record:
            raise DomainError('reference_conflict')
        self.tables[table][key] = deepcopy(record)
        limits = dict(approach_versions=63, models=32, configurations=64, run_contexts=64, evidence=1000)
        if (len(self.tables[table]) > limits[table]
                or sum(map(len, self.tables.values())) >= MAX_ENTITIES
                or len(self.tables['configurations']) + len(self.tables['run_contexts']) > 64
                or len(canonical(self.resolution())) > MAX_BYTES):
            raise DomainError('limit_exceeded', 413)

    def resolution(self):
        return {k: [deepcopy(rows[i]) for i in sorted(rows)] for k, rows in self.tables.items()}

    def evidence(self, version):
        if version in self.tables['evidence']:
            return
        # The raw row is this resolver's write-time witness; Store interprets it.
        row = self.row('SELECT * FROM evidence WHERE study_id=? AND evidence_version_id=?', (self.sid, version))
        record = _retained(lambda: exact_evidence(row['payload'], self.sid, version))
        self.add('evidence', evidence_snapshot(record))

    def links(self, links):
        for link in links:
            self.evidence(link['evidence_version_id'])

    def model(self, mid, revision):
        self.row('SELECT * FROM model_associations WHERE study_id=? AND model_id=?', (self.sid, mid))
        if revision in self.tables['models']:
            if self.tables['models'][revision]['model_id'] != mid:
                raise DomainError('reference_conflict')
            return
        # Coordinator authenticates association and exact response identity.
        model = self.service.coordinator.read(self.actor, self.sid, mid,
            '/revisions/' + revision, response_schema='ModelRevisionResponse4')['data']
        self.add('models', model)
        for assumption in model.get('assumptions', []):
            self.links(assumption['evidence_links'])

    def saved(self, version):
        if version in self.tables['approach_versions']:
            return
        row = self.row('SELECT * FROM approach_versions WHERE study_id=? AND approach_version_id=?', (self.sid, version))
        saved = saved_version(row, self.sid)
        for table in KEYS:
            for record in saved['closure'][table]:
                self.add(table, record)

    def frozen(self, frozen, revision):
        validate('FrozenConfigurationRead8', frozen, remote=True)
        config, model = frozen['configuration'], frozen['model_snapshot']
        if (config['study_id'] != self.sid or config['configuration_revision_id'] != revision
                or model['model_id'] != config['model_id']
                or model['model_revision_id'] != config['model_revision_id']):
            raise DomainError('reference_conflict')
        self.add('configurations', config)
        self.add('models', model)
        for record in config['evidence_snapshots']:
            self.add('evidence', record)
        for assumption in model.get('assumptions', []):
            self.links(assumption['evidence_links'])
        if config.get('approach_binding'):
            closure = _retained(lambda: validate_closure(frozen['approach_closure'], study_id=self.sid))
            pin = config['approach_binding']
            if (closure['digest'] != pin['closure_digest']
                    or closure['root_approach_version_id'] != pin['approach_version_id']
                    or closure['root_approach_digest'] != pin['approach_digest']):
                raise DomainError('reference_conflict')
            for table in KEYS:
                for record in closure[table]:
                    self.add(table, record)
        for item in config['inputs']:
            if item.get('result_binding'):
                self.run(item['result_binding']['source_run_id'])
        for field in ('context_source', 'derivation'):
            source = config.get(field)
            if source and 'source_run_id' in source:
                self.run(source['source_run_id'])

    def configuration(self, revision):
        if revision in self.tables['configurations']:
            return
        self.enter('configurations', revision)
        try:
            row = self.row('SELECT * FROM configurations WHERE study_id=? AND configuration_revision_id=?', (self.sid, revision))
            self.frozen(_retained(lambda: json.loads(row['payload'])), revision)
        finally:
            self.active.remove(('configurations', revision))

    def enter(self, kind, identity):
        key = (kind, identity)
        if key in self.active:
            raise DomainError('reference_conflict')
        if len(self.active) >= MAX_DEPTH:
            raise DomainError('limit_exceeded', 413)
        self.active.add(key)

    def run(self, run_id):
        if run_id in self.tables['run_contexts']:
            return
        self.enter('run_contexts', run_id)
        try:
            with self.store.connection() as db:
                row, receipt = self.history.run_row(db, self.actor, self.sid, run_id)
            if receipt is None:
                raise DomainError('resource_not_found', 404)
            # Rechecked by History.recheck in the command transaction (see recheck).
            self.runs[run_id] = dict(run_id=run_id, row_digest=digest(row), receipt_digest=digest(receipt))
            if row['state'] != 'recorded' or not row['store_uuid'] or not row['process_uuid']:
                raise DomainError('reference_conflict')
            def retained():
                payload = json.loads(row['payload'])
                history = validate_binding(row, payload, receipt)
                if not history['bundle_verified']:
                    raise ValueError('Verified retained bundle required')
                bundle = payload['bundle']
                raw = {p: base64.b64decode(v, validate=True) for p, v in bundle['files'].items()}
                validate_retained_bundle(dict(manifest=bundle['manifest'], files=raw), payload['request'], payload['frozen'])
                return payload, history
            payload, history = _retained(retained)
            revision = row['configuration_revision_id']
            stored = self.row('SELECT * FROM configurations WHERE study_id=? AND configuration_revision_id=?', (self.sid, revision))
            if _retained(lambda: json.loads(stored['payload'])) != payload['frozen']:
                raise DomainError('reference_conflict')
            config, model = payload['frozen']['configuration'], payload['frozen']['model_snapshot']
            context = _signed(
                dict(
                    schema_version='2'
                    if history['results'] is not None
                    and history['results']['schema_version'] == '2'
                    else '1',
                    run_id=run_id,
                    study_id=self.sid,
                    request=payload['request'],
                    association=history['association'],
                    configuration_revision_id=revision,
                    configuration_digest=config['digest'],
                    model_revision_id=model['model_revision_id'],
                    model_digest=model['digest'],
                    context=config['context_snapshot'],
                    results=history['results'],
                    assessment=history['assessment'],
                    runtime=payload['bundle']['manifest']['runtime'],
                    errors=history['errors'],
                )
            )
            validate('ApproachRunContextRead2', context, remote=True)
            self.add('run_contexts', context)
            self.frozen(payload['frozen'], revision)
        finally:
            self.active.remove(('run_contexts', run_id))

    def content(self, content):
        # Prior closures are already validated and authorized retained sources.
        for step in content['steps']:
            for ref in step['assumption_refs']:
                if ref['kind'] == 'model' and ref['origin']:
                    self.saved(ref['origin']['approach_version_id'])
                elif ref['kind'] == 'configuration':
                    self.configuration(ref['configuration_revision_id'])
        for basis in content['basis_refs']:
            if basis['kind'] == 'configuration':
                self.configuration(basis['configuration_revision_id'])
            else:
                self.run(basis['run_id'])
        for binding in content['model_bindings']:
            self.model(binding['model_id'], binding['model_revision_id'])
        for record in content['steps'] + content['assumptions'] + content['cases'] + content.get('limit_items', []):
            self.links(record['evidence_links'])


class Approaches:
    def __init__(self, store, coordinator):
        self.store, self.coordinator = store, coordinator

    def _draft(self, db, sid):
        row = db.execute('SELECT * FROM approach_drafts WHERE study_id=?', (sid,)).fetchone()
        if row is None:
            return None
        draft = _retained(lambda: json.loads(row['payload']))
        validate('ApproachDraftRead2', draft, remote=True)
        if any(draft[k] != row[k] for k in ('approach_id', 'study_id', 'revision')):
            raise DomainError('corrupt_retained_record', 409)
        return draft

    def _base(self, actor, sid, expected):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            draft = self._draft(db, sid)
            self.store.cas(draft['revision'] if draft else None, expected)
            return draft

    @staticmethod
    def _summary_row(row):
        value = _retained(lambda: json.loads(row['summary']))
        validate('ApproachVersionSummaryRead2', value, remote=True)
        if any(value[k] != row[k] for k in ('approach_version_id', 'approach_id', 'study_id', 'version_number')):
            raise DomainError('corrupt_retained_record', 409)
        return value

    def state(self, actor, sid):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            draft = self._draft(db, sid)
            row = db.execute('SELECT approach_version_id,approach_id,study_id,version_number,json_remove(json_extract(payload,"$.version"),"$.content") AS summary FROM approach_versions WHERE study_id=? ORDER BY version_number DESC,approach_version_id DESC LIMIT 1', (sid,)).fetchone()
            latest = self._summary_row(row) if row else None
            return dict(draft=draft, latest_version=latest)

    def read(self, actor, sid, version):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            row = db.execute('SELECT * FROM approach_versions WHERE study_id=? AND approach_version_id=?', (sid, version)).fetchone()
            if row is None:
                raise DomainError('resource_not_found', 404)
            return saved_version(row, sid)

    def _preview(self, actor, sid, body):
        validate('ApproachPreviewRequestRead2', body)
        draft = self._base(actor, sid, body['expected_revision'])
        content = deepcopy(body['content'])
        if len(canonical(content)) > MAX_CONTENT:
            raise DomainError('limit_exceeded', 413)
        resolver = _Resolver(self, actor, sid)
        try:
            resolver.content(content)
        finally:
            # Current access takes precedence over remote data and errors.
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid)
        resolution = resolver.resolution()
        # Deterministic temporary root validates proposal semantics only. It is
        # removed from preview data and never persisted as a scientific version.
        namespace = UUID(sid)
        version = _signed(dict(schema_version=content['schema_version'], approach_id=draft['approach_id'] if draft else str(uuid5(namespace, 'approach-preview-family')),
            approach_version_id=str(uuid5(namespace, 'preview:' + digest(content))), study_id=sid,
            version_number=1, predecessor_version_id=None, content=content, created_by=actor,
            created_at='1970-01-01T00:00:00Z'))
        issues = []
        try:
            build_closure(version, resolution, study_id=sid)
        except ReferenceIssue as exc:
            issues = [exc.issue]
        except ValueError as exc:
            if 'limit' in str(exc).lower():
                raise DomainError('limit_exceeded', 413) from exc
            issues = [dict(path='/content', code='invalid_reference', message='Review the exact references and their correspondence before saving.')]
        changes = []
        previous = draft['content'] if draft else {}
        for key, value in content.items():
            if previous.get(key) != value:
                changes.append(dict(path='/content/' + key, kind='changed' if key in previous else 'added', description='Review ' + key.replace('_', ' ') + '.'))
        for key in sorted(previous.keys() - content.keys()):
            changes.append(dict(path='/content/' + key, kind='removed', description='Review removal of ' + key.replace('_', ' ') + '.'))
        coverage = {state: sum(s['implementation_state'] == state for s in content['steps']) for state in ('proposed', 'partial', 'linked')}
        preview = dict(schema_version=closure_schema(version, resolution), expected_revision=body['expected_revision'], changes=changes,
            issues=issues, resolved=resolution, coverage=coverage,
            preview_digest=digest(dict(expected_revision=body['expected_revision'], content=content, resolved=resolution)))
        validate('ApproachPreviewRead4', preview)
        return preview, resolver, draft

    def preview(self, actor, sid, body):
        return self._preview(actor, sid, body)[0]

    @staticmethod
    def _check_preview(preview, expected):
        if preview['preview_digest'] != expected:
            raise DomainError('reference_conflict')
        if preview['issues']:
            raise DomainError('invalid_request', 422, fields=[dict(i, element_ref=None) for i in preview['issues']])

    def _write_draft(self, db, actor, sid, content, previous, *, base=None):
        draft = dict(schema_version=content['schema_version'], approach_id=previous['approach_id'] if previous else uid(), study_id=sid,
            revision=uid(), base_version_id=base if base is not None else previous['base_version_id'] if previous else None,
            content=deepcopy(content), updated_by=actor, updated_at=_now())
        validate('ApproachDraftRead2', draft)
        db.execute('INSERT INTO approach_drafts VALUES(?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
            (draft['approach_id'], sid, draft['revision'], json.dumps(draft)))
        return draft

    def save_draft(self, actor, sid, body):
        body = deepcopy(body)
        validate('ApproachDraftWriteRead2', body)
        replay = self.store.replay(actor, sid, 'approach_draft', body['command_id'], body)
        if replay:
            return replay['result']
        try:
            preview, resolver, _ = self._preview(actor, sid, {k: body[k] for k in ('schema_version', 'expected_revision', 'content')})
        except DomainError:
            # Another request may have committed this same command between
            # initial replay and resolution. Reconcile before returning stale.
            replay = self.store.replay(actor, sid, 'approach_draft', body['command_id'], body)
            if replay:
                return replay['result']
            raise
        def commit(db):
            previous = self._draft(db, sid)
            self.store.cas(previous['revision'] if previous else None, body['expected_revision'])
            resolver.recheck(db)
            self._check_preview(preview, body['expected_preview_digest'])
            return self._write_draft(db, actor, sid, body['content'], previous)
        return self.store.command(actor, sid, 'approach_draft', body['command_id'], body, commit)

    def save_version(self, actor, sid, body):
        body = deepcopy(body)
        validate('ApproachVersionSave1', body)
        replay = self.store.replay(actor, sid, 'approach_version', body['command_id'], body)
        if replay:
            return replay['result']
        try:
            draft = self._base(actor, sid, body['expected_revision'])
            preview, resolver, _ = self._preview(actor, sid, dict(schema_version=draft['schema_version'], expected_revision=body['expected_revision'], content=draft['content']))
        except DomainError:
            replay = self.store.replay(actor, sid, 'approach_version', body['command_id'], body)
            if replay:
                return replay['result']
            raise
        def commit(db):
            previous = self._draft(db, sid)
            self.store.cas(previous['revision'] if previous else None, body['expected_revision'])
            resolver.recheck(db)
            self._check_preview(preview, body['expected_preview_digest'])
            latest = db.execute('SELECT approach_version_id,version_number FROM approach_versions WHERE study_id=? ORDER BY version_number DESC LIMIT 1', (sid,)).fetchone()
            version = _signed(dict(schema_version=previous['schema_version'], approach_id=previous['approach_id'], approach_version_id=uid(), study_id=sid,
                version_number=latest['version_number'] + 1 if latest else 1,
                predecessor_version_id=latest['approach_version_id'] if latest else None,
                content=deepcopy(previous['content']), created_by=actor, created_at=_now()))
            try:
                closure = build_closure(version, preview['resolved'], study_id=sid)
            except ValueError as exc:
                # Real version metadata can cross a byte bound that its
                # temporary preview root did not; preserve atomic rejection.
                if 'limit' in str(exc).lower():
                    raise DomainError('limit_exceeded', 413) from exc
                raise DomainError('reference_conflict') from exc
            saved = dict(version=version, closure=closure)
            db.execute('INSERT INTO approach_versions VALUES(?,?,?,?,?)', (version['approach_version_id'], version['approach_id'], sid, version['version_number'], json.dumps(saved)))
            nextdraft = self._write_draft(db, actor, sid, previous['content'], previous, base=version['approach_version_id'])
            return dict(saved=saved, draft_revision=nextdraft['revision'])
        return self.store.command(actor, sid, 'approach_version', body['command_id'], body, commit)

    def restore(self, actor, sid, body):
        body = deepcopy(body)
        validate('ApproachRestore1', body)
        replay = self.store.replay(actor, sid, 'approach_restore', body['command_id'], body)
        if replay:
            return replay['result']
        def commit(db):
            previous = self._draft(db, sid)
            self.store.cas(previous['revision'] if previous else None, body['expected_revision'])
            row = db.execute('SELECT * FROM approach_versions WHERE study_id=? AND approach_version_id=?', (sid, body['approach_version_id'])).fetchone()
            if row is None:
                raise DomainError('resource_not_found', 404)
            saved = saved_version(row, sid)
            return self._write_draft(db, actor, sid, saved['version']['content'], previous, base=body['approach_version_id'])
        return self.store.command(actor, sid, 'approach_restore', body['command_id'], body, commit)

    def versions(self, actor, sid, query=None):
        query = dict(limit=20, cursor=None) | (query or {})
        validate('ApproachPageRequest1', query)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            params = [sid]
            sql = 'SELECT approach_version_id,approach_id,study_id,version_number,json_remove(json_extract(payload,"$.version"),"$.content") AS summary FROM approach_versions WHERE study_id=?'
            if query['cursor']:
                c = query['cursor']
                sql += ' AND (version_number,approach_version_id)<(?,?)'
                params += [c['version_number'], c['approach_version_id']]
            sql += ' ORDER BY version_number DESC,approach_version_id DESC LIMIT ?'
            rows = db.execute(sql, (*params, query['limit'] + 1)).fetchall()
            items = [self._summary_row(r) for r in rows[:query['limit']]]
            cursor = {k: items[-1][k] for k in ('version_number', 'approach_version_id')} if len(rows) > query['limit'] else None
            return dict(items=items, next_cursor=cursor)

    def usage(self, actor, sid, version, query=None):
        query = dict(limit=20, cursor=None, case_id=None) | (query or {})
        validate('ApproachUsageRequest1', query)
        saved = self.read(actor, sid, version)
        if query['case_id'] is not None and query['case_id'] not in {c['case_id'] for c in saved['version']['content']['cases']}:
            raise DomainError('resource_not_found', 404)
        # Select only small persisted pin projections, never bundle blobs or a
        # new backlink table. SQL pagination bounds work before deserialization:
        # configurations come first in (kind, resource_id) order, then the runs that
        # ``history`` reads for the same version (and case), each half SQL-bounded.
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            fetch, cursor = query['limit'] + 1, query['cursor']
            rows = []
            if cursor is None or cursor['kind'] == 'configuration':
                after = cursor['resource_id'] if cursor else None
                rows = [dict(kind='configuration', resource_id=r['configuration_revision_id'],
                             configuration_revision_id=r['configuration_revision_id'], case_id=r['case_id'])
                        for r in db.execute('''SELECT c.configuration_revision_id,
                    json_extract(c.payload,'$.configuration.approach_binding.case_id') AS case_id
                FROM configurations c WHERE c.study_id=? AND json_extract(c.payload,'$.configuration.approach_binding.approach_version_id')=?
                    AND (? IS NULL OR json_extract(c.payload,'$.configuration.approach_binding.case_id')=?)
                    AND (? IS NULL OR c.configuration_revision_id>?)
                ORDER BY c.configuration_revision_id LIMIT ?''',
                            (sid, version, query['case_id'], query['case_id'], after, after, fetch)).fetchall()]
            if len(rows) < fetch:
                after = cursor['resource_id'] if cursor and cursor['kind'] == 'run' else None
                rows += [dict(kind='run', resource_id=r['run_id'], configuration_revision_id=r['configuration_revision_id'],
                              case_id=r['case_id'])
                         for r in approach_runs(db, sid, version, query['case_id'], after, fetch - len(rows))]
            items = []
            for row in rows[:query['limit']]:
                item = dict(kind=row['kind'], configuration_revision_id=row['configuration_revision_id'], case_id=row['case_id'])
                if row['kind'] == 'run':
                    item['run_id'] = row['resource_id']
                items.append(item)
            cursor = {k: rows[query['limit'] - 1][k] for k in ('kind', 'resource_id')} if len(rows) > query['limit'] else None
            result = dict(items=items, next_cursor=cursor)
            validate('ApproachUsagePage1', result)
            return result

    def receipt(self, actor, sid, category, command):
        validate('ApproachReceiptCategory1', category)
        row = self.store.receipt(actor, sid, category, command)
        result = {k: row[k] for k in ('command_id', 'state', 'result', 'error')}
        validate('ApproachReceiptRead3', result, remote=True)
        return result
