"""Advance a saved analysis through existing run and estimate owners.

One durable receipt per version pins reused or submitted runs. This is a dispatcher step,
not a scheduler: launches, containment, uncertain-outcome reconciliation and numerical work
remain with their existing owners. Closing a client never interrupts preparation.
"""
from collections import Counter
from contextlib import nullcontext
import json
import time
from uuid import UUID, uuid5

from .calculations import Analyses, validate_calculation
from .calculation_estimates import Estimates
from .contracts import DomainError, issue
from .history import History, calculation_runs
from .execution import Submissions

CATEGORY = 'analysis_execution'
ADMISSION_LIMIT = 10
PAGE_SIZE = 20


def identity(version_id):
    return str(uuid5(UUID(version_id), CATEGORY))


class AnalysisExecution:
    def __init__(self, store):
        self.store = store
        self.analyses = Analyses(store)
        self._cursor = None
        self._rotation = 0

    def read(self, actor, sid, version_id):
        self.analyses.version(actor, sid, version_id)
        with self.store.connection() as db:
            receipt = self.store.command_receipt(db, sid, CATEGORY, identity(version_id))
        return receipt['result'] if receipt else None

    def launch(self, actor, sid, version_id, body):
        validate_calculation('AnalysisLaunch1', body)
        version = self.analyses.version(actor, sid, version_id)
        if version['schema_version'] != '4':
            raise DomainError('invalid_request', 422, fields=[issue(
                ['calculation_version_id'],
                'Create a new analysis version with explicit estimate settings before launching.',
            )])
        payload = dict(calculation_version_id=version_id)
        request = dict(payload, members=version['content']['configuration_revision_ids'],
                       estimate_plan=version['content']['estimate_plan'],
                       run_commands={str(uuid5(UUID(identity(version_id)), member)): member
                                     for member in version['content']['configuration_revision_ids']},
                       estimate_command=str(uuid5(UUID(identity(version_id)), 'estimate')))

        def accept(db):
            agent = self.store.agent_actor(db, actor)
            row = db.execute('SELECT delegation_id FROM agent_delegations '
                             'WHERE agent_actor_id=? AND study_id=? AND revoked_at IS NULL',
                             (actor, sid)).fetchone() if agent else None
            delegation = self.store.live_delegation(db, row['delegation_id']) if row else None
            if agent and (delegation is None or 'submit' not in delegation['effects']):
                raise DomainError('forbidden', 403)
            request['authority'] = dict(actor_id=actor,
                delegation_id=delegation['delegation_id'] if delegation else None)
            members = request['members']
            rows = calculation_runs(db, sid, members, 0, 10001)
            if len(rows) > 10000:
                raise DomainError('limit_exceeded', 413)
            # Choose once, at launch. Later runs cannot silently change the fitted data.
            latest = {r['configuration_revision_id']: r['run_id'] for r in rows}
            request['reused_runs'] = {r['command_id']: r['run_id'] for r in db.execute(
                'SELECT command_id,run_id FROM execution_operations WHERE actor_id=? '
                'AND run_id IN (SELECT value FROM json_each(?))',
                (actor, json.dumps(list(latest.values())))).fetchall()}
            return dict(
                schema_version='3', last_progress_at=time.time(),
                calculation_version_id=version_id, state='calculating',
                admission_state='ready',
                reason=None, completed_count=0, total_count=len(members), estimate_id=None,
                runs=[dict(configuration_revision_id=m, run_id=latest.get(m),
                           reused=m in latest, completed=False) for m in members],
            )

        return self.store.command(
            actor, sid, CATEGORY, identity(version_id), payload, accept,
            receipt_state='pending_remote', request=request,
        )

    def _recovery(self, db, actor, sid, version_id):
        self.store.authorize(db, actor, sid)
        saved = self.store.command_receipt(db, sid, CATEGORY, identity(version_id))
        if saved is None:
            return None, 'This analysis has not been launched.'
        original_actor = saved['actor_id']
        original_agent = self.store.agent_actor(db, original_actor)
        if actor != original_actor and (not original_agent
                or actor != original_agent['delegator_actor_id']):
            return saved, 'Only the launching actor or its delegating engineer can resume this analysis.'
        try:
            self.store.authorize(db, actor, sid, write=True)
            agent = self.store.agent_actor(db, actor)
            if agent:
                row = db.execute('SELECT delegation_id FROM agent_delegations '
                                 'WHERE agent_actor_id=? AND study_id=? AND revoked_at IS NULL',
                                 (actor, sid)).fetchone()
                delegation = self.store.live_delegation(db, row['delegation_id']) if row else None
                if delegation is None or 'submit' not in delegation['effects']:
                    return saved, 'Current permission to submit calculations is required.'
        except DomainError:
            return saved, 'Current permission to submit calculations is required.'
        if (saved['state'] == 'pending_remote' and saved['result']['state'] == 'needs_review'
                and self.store.analysis_authorized(db, saved, sid)):
            pending = db.execute('SELECT 1 FROM analysis_reconciliation_intents i '
                'LEFT JOIN analysis_reconciliation_results r ON r.study_id=i.study_id '
                'AND r.command_id=i.command_id WHERE i.study_id=? AND i.analysis_command=? '
                'AND r.command_id IS NULL', (sid, identity(version_id))).fetchone()
            if pending:
                return saved, 'Native execution reconciliation is already queued.'
            if Submissions(self.store, None, None).analysis_uncertain_runs(db, sid, saved):
                return saved, None
            return saved, 'The uncertain run has no intact prepared request to reconcile safely.'
        if (saved['state'] != 'committed' or saved['result']['state'] != 'failed'
                or saved['result'].get('admission_state') not in ('revoked', 'stopped')):
            return saved, 'Only an execution interrupted by replaced credentials can be resumed.'
        if not self.store.analysis_authorized(db, saved, sid):
            return saved, 'The original execution authority was revoked or continuity cannot be verified.'
        children = Submissions(self.store, None, None).analysis_authority_failures(db, sid, saved)
        if children is None:
            return saved, 'A run has an execution outcome or preparation failure that cannot be safely resumed.'
        if saved['result'].get('admission_state') == 'stopped' and (
                not children or saved['result']['reason'] !=
                'A calculation could not start. Review its run diagnostics.'):
            return saved, 'Only a proven unlaunched authorization interruption can be resumed.'
        return saved, None

    def recovery(self, actor, sid, version_id):
        self.analyses.version(actor, sid, version_id)
        with self.store.connection() as db:
            _, reason = self._recovery(db, actor, sid, version_id)
        return dict(schema_version='1', can_resume=reason is None, reason=reason)

    def resume(self, actor, sid, version_id, body):
        validate_calculation('AnalysisResume1', body)
        self.analyses.version(actor, sid, version_id)
        def apply(db):
            saved, reason = self._recovery(db, actor, sid, version_id)
            if reason:
                raise DomainError('analysis_resume_unavailable', 409, fields=[issue([], reason)])
            if saved['result']['state'] == 'needs_review':
                runs = Submissions(self.store, None, None).analysis_uncertain_runs(db, sid, saved)
                db.execute('INSERT INTO analysis_reconciliation_intents VALUES(?,?,?,?,?,?)',
                    (sid, body['command_id'], identity(version_id), actor,
                     json.dumps(runs), json.dumps(saved['result'])))
                result = dict(saved['result'], state='calculating', admission_state='waiting',
                              reason='Checking whether the uncertain calculations started.')
                db.execute('UPDATE receipts SET result=? WHERE scope=? AND category=? '
                           "AND command_id=? AND state='pending_remote'",
                           (json.dumps(result), sid, CATEGORY, identity(version_id)))
                return result
            result = dict(saved['result'], state='calculating', admission_state='ready', reason=None)
            # No launch happens here. The dispatcher first reconciles every pinned run,
            # and command replay recovers any accepted child not yet copied to this result.
            db.execute('INSERT INTO analysis_execution_resumptions VALUES(?,?,?,?,?,?)',
                       (sid, body['command_id'], identity(version_id), actor,
                        json.dumps(saved['result']), json.dumps(result)))
            submissions = Submissions(self.store, None, None)
            children = submissions.analysis_authority_failures(db, sid, saved)
            submissions.resume_analysis_preparation(db, actor, sid, saved, body['command_id'], children)
            db.execute("UPDATE receipts SET state='pending_remote',result=? WHERE scope=? "
                       "AND category=? AND command_id=? AND state='committed'",
                       (json.dumps(result), sid, CATEGORY, identity(version_id)))
            return result
        return self.store.command(actor, sid, 'analysis_resume', body['command_id'],
                                  dict(calculation_version_id=version_id), apply)

    def cancel(self, actor, sid, version_id, body=None):
        validate_calculation('AnalysisLaunch1', {} if body is None else body)
        self.analyses.version(actor, sid, version_id)
        with self.store.connection(write=True) as db:
            self.store.authorize(db, actor, sid, write=True)
            saved = self.store.command_receipt(db, sid, CATEGORY, identity(version_id))
            if saved is None:
                raise DomainError('resource_not_found', 404)
            result = saved['result']
            if saved['state'] != 'pending_remote':
                return result
            result.update(schema_version='2', state='cancelled', admission_state='cancelled',
                          reason='Analysis cancelled. Already accepted runs retain their records.')
            self._save(db, sid, identity(version_id), result, True)
            return result

    def process_one(self, submissions):
        # Identity pagination rotates across actors and studies; payload reads retain RLS.
        if hasattr(self.store, 'database'):
            jobs = self.store.background_jobs(CATEGORY, after=self._cursor, limit=PAGE_SIZE)
            if not jobs and self._cursor is not None:
                jobs = self.store.background_jobs(CATEGORY, limit=PAGE_SIZE)
            if jobs:
                self._cursor = jobs[-1]['work_id']
            counts = Counter(job['actor_id'] for job in jobs)
            progressed = False
            for job in self._rotate(jobs):
                with self.store.background_actor(CATEGORY, job['work_id']) as admitted:
                    if admitted:
                        progressed = self._step(
                            dict(scope=job['study_id'], command_id=job['work_id'],
                                 actor_id=job['actor_id']), submissions,
                            max(1, ADMISSION_LIMIT // counts[job['actor_id']]),
                        ) or progressed
            return progressed
        with self.store.connection() as db:
            rows = db.execute(
                'SELECT scope,command_id,actor_id FROM receipts WHERE category=? '
                "AND state='pending_remote' AND command_id>? ORDER BY command_id LIMIT ?",
                (CATEGORY, self._cursor or '', PAGE_SIZE),
            ).fetchall()
            if not rows and self._cursor is not None:
                self._cursor = None
                rows = db.execute(
                    'SELECT scope,command_id,actor_id FROM receipts WHERE category=? '
                    "AND state='pending_remote' ORDER BY command_id LIMIT ?",
                    (CATEGORY, PAGE_SIZE),
                ).fetchall()
        if rows:
            self._cursor = rows[-1]['command_id']
        counts = Counter(row['actor_id'] for row in rows)
        progressed = False
        for row in self._rotate(rows):
            progressed = self._step(
                row, submissions, max(1, ADMISSION_LIMIT // counts[row['actor_id']])) or progressed
        return progressed

    def _rotate(self, rows):
        # Rotate the first admitted plan even when every page wraps, so a
        # partially occupied actor queue cannot repeatedly favor one study.
        if not rows:
            return rows
        offset = self._rotation % len(rows)
        self._rotation += 1
        return rows[offset:] + rows[:offset]

    def _save(self, db, sid, command, result, terminal=False):
        saved = self.store.command_receipt(db, sid, CATEGORY, command)
        if not saved or saved['state'] != 'pending_remote':
            return
        previous = {m['configuration_revision_id']: m for m in saved['result']['runs']}
        for member in result['runs']:
            old = previous[member['configuration_revision_id']]
            if member['run_id'] is None:
                member['run_id'] = old['run_id']
            elif old['run_id'] not in (None, member['run_id']):
                raise DomainError('corrupt_retained_record', 409)
            member['completed'] = member['completed'] or old['completed']
        result['completed_count'] = sum(m['completed'] for m in result['runs'])
        result['schema_version'] = '3'
        result['last_progress_at'] = saved['result'].get('last_progress_at')
        meaningful = ('state', 'completed_count', 'estimate_id', 'runs')
        if any(result.get(k) != saved['result'].get(k) for k in meaningful):
            result['last_progress_at'] = time.time()
        validate_calculation('AnalysisExecution3', result, retained=True)
        if not terminal and result == saved['result']:
            return
        db.execute(
            'UPDATE receipts SET result=?,state=? WHERE scope=? AND category=? '
            "AND command_id=? AND state='pending_remote'",
            (json.dumps(result), 'committed' if terminal else 'pending_remote',
             sid, CATEGORY, command),
        )

    def _step(self, row, submissions, quota=ADMISSION_LIMIT):
        with self.store.analysis_scope(row['scope'], row['command_id']):
            return self._step_scoped(row, submissions, quota)

    def _step_scoped(self, row, submissions, quota):
        sid, command, actor = row['scope'], row['command_id'], row['actor_id']
        with self.store.connection() as db:
            saved = self.store.command_receipt(db, sid, CATEGORY, command)
        if not saved or saved['state'] != 'pending_remote':
            return
        result = saved['result']
        original = json.dumps(result, sort_keys=True)
        previous_reason = result.get('reason')
        reconciled = None
        result.update(schema_version='2', admission_state='ready', reason=None)
        terminal = False
        try:
            authority = (self.store.analysis_authority(actor, sid, command)
                         if (saved['request'] or {}).get('authority') else nullcontext())
            with authority:
                reconciled = submissions.reconcile_analysis_intent(sid, saved)
                if reconciled is False:
                    result.update(state='needs_review', admission_state='needs_review', reason=(
                        'Execution could not be proven unstarted. No calculation was retried. '
                        'Ask the administrator to inspect the native execution record '
                        'before resuming.'))
                else:
                    terminal = self._advance(actor, sid, command, result, submissions, quota)
        except DomainError as exc:
            if exc.status == 429:
                result.update(admission_state='waiting', reason='Waiting for execution capacity.')
            elif 'attestation' in exc.code:
                result.update(admission_state='invalid_attestation',
                              reason='Current execution attestation is required: ' + exc.code)
            elif exc.status == 503:
                result.update(admission_state='unavailable',
                              reason='Execution admission is temporarily unavailable: ' + exc.code)
            else:
                revoked = exc.code == 'analysis_authority_revoked'
                reason = {
                    'analysis_run_failed': 'A calculation failed. Review its run before creating a new analysis version.',
                    'analysis_run_preparation_failed': 'A calculation could not start. Review its run diagnostics.',
                    'forbidden': 'A required operation was forbidden. Review its access diagnostics.',
                    'resource_not_found': 'A required analysis resource was not available. Review its access or resource diagnostics.',
                }.get(exc.code, 'Permission to execute this analysis was lost.' if revoked else
                      'Analysis preparation stopped: ' + exc.code.replace('_', ' '))
                result.update(state='failed', admission_state='revoked' if revoked else 'stopped',
                              reason=reason)
                terminal = True
        finally:
            if (reconciled is None and result['state'] == 'needs_review'
                    and (previous_reason or '').startswith(
                        'Execution could not be proven unstarted.')):
                result['reason'] = previous_reason
            # Preserve earlier accepted members even if a later admission/read fails.
            with self.store.connection(write=True) as db:
                self._save(db, sid, command, result, terminal)
        return original != json.dumps(result, sort_keys=True)

    def _advance(self, actor, sid, command, result, submissions, quota):
        version = self.analyses.version(actor, sid, result['calculation_version_id'])
        terminal = False
        complete = 0
        needs_review = False
        # A child acceptance and its immutable parent link commit together, but a
        # crashed dispatcher may not yet have copied the run id into this projection.
        # Reconcile all such links before admitting anything: an uncertain later
        # member must also stop earlier members that have not been submitted yet.
        with self.store.connection() as db:
            accepted = {r['child_command']: r['run_id'] for r in db.execute(
                'SELECT child_command,run_id FROM analysis_execution_children '
                "WHERE study_id=? AND analysis_command=? AND child_category='run'",
                (sid, command)).fetchall()}
        for member in result['runs']:
            if member['run_id'] is None:
                child = str(uuid5(UUID(command), member['configuration_revision_id']))
                member['run_id'] = accepted.get(child)
        # Inspect all pinned runs before dispatch: uncertainty must never be retried.
        for member in result['runs']:
            if member['completed']:
                complete += 1
                continue
            if member['run_id'] is None:
                continue
            run = submissions.read(actor, sid, member['run_id'])
            if run['state'] == 'uncertain':
                needs_review = True
            elif run['state'] == 'preparation_failed':
                raise DomainError('analysis_run_preparation_failed', 409)
            elif run['state'] == 'recorded':
                retained = History(self.store).retained_projection(actor, sid, member['run_id'])
                outcome = (retained.history.get('results') or {}).get('execution')
                if not isinstance(outcome, dict) or outcome.get('state') != 'finished':
                    raise DomainError('analysis_run_failed', 409)
                member['completed'] = True
                complete += 1
                result['completed_count'] = complete
        result['completed_count'] = complete
        result['state'] = 'needs_review' if needs_review else 'calculating'
        result['admission_state'] = 'needs_review' if needs_review else 'ready'
        result['reason'] = (
            'A calculation has an uncertain execution outcome. Resume analysis requests '
            'a native check before any unstarted work can continue.'
        ) if needs_review else None
        if needs_review:
            return False
        admitted = 0
        for member in result['runs']:
            if member['run_id'] is not None:
                continue
            if admitted >= quota:
                result.update(admission_state='waiting', reason='Waiting for the next admission pass.')
                break
            run = submissions.submit(actor, sid, dict(
                command_id=str(uuid5(UUID(command), member['configuration_revision_id'])),
                configuration_revision_id=member['configuration_revision_id'],
            ), admission_limit=ADMISSION_LIMIT)
            member['run_id'] = run['run_id']
            admitted += 1
            with self.store.connection(write=True) as db:
                self._save(db, sid, command, result)
            if run['state'] == 'uncertain':
                result.update(state='needs_review', admission_state='needs_review',
                              reason='Resolve the uncertain run before continuing.')
                return False
        if complete == result['total_count']:
            plan = version['content']['estimate_plan']
            if plan is None:
                result['state'], terminal = 'complete', True
            else:
                estimates = Estimates(self.store)
                estimate = estimates.build(actor, sid, dict(
                    command_id=str(uuid5(UUID(command), 'estimate')),
                    calculation_version_id=version['calculation_version_id'],
                    tolerances=plan['tolerances'],
                ), pinned_runs={m['configuration_revision_id']: m['run_id']
                                for m in result['runs']})
                result['estimate_id'] = estimate['estimate_id']
                result['state'] = 'validating'
                if estimate['state'] in ('ready', 'assessed', 'failed'):
                    passed = (
                        len(estimate['groups']) == estimate['total_groups']
                        and all(len(g['outputs']) == len(plan['tolerances'])
                                and all(o['reason'] is None and o['metrics'] is not None
                                        and o['metrics']['target_met']
                                        and o['metrics']['failed_count'] == 0
                                        and o['metrics']['assessed_count'] > 0
                                        for o in g['outputs'])
                                for g in estimate['groups'])
                        and estimate['state'] == 'ready'
                    )
                    result['state'] = 'complete' if passed else 'failed'
                    result['reason'] = None if passed else (
                        'Surrogate validation did not pass for every requested output. '
                        'Review the results and create a new version to change the settings.'
                    )
                    terminal = True
        return terminal
