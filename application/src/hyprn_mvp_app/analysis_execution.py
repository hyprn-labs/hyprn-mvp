"""Advance a saved analysis through existing run and estimate owners.

One durable receipt per version pins reused or submitted runs. This is a dispatcher step,
not a scheduler: launches, containment, uncertain-outcome reconciliation and numerical work
remain with their existing owners. Closing a client never interrupts preparation.
"""
import json
from uuid import UUID, uuid5

from .calculations import Analyses, validate_calculation
from .calculation_estimates import Estimates
from .contracts import DomainError, issue
from .history import History, calculation_runs

CATEGORY = 'analysis_execution'


def identity(version_id):
    return str(uuid5(UUID(version_id), CATEGORY))


class AnalysisExecution:
    def __init__(self, store):
        self.store = store
        self.analyses = Analyses(store)

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
        request = dict(calculation_version_id=version_id)

        def accept(db):
            members = version['content']['configuration_revision_ids']
            rows = calculation_runs(db, sid, members, 0, 10001)
            if len(rows) > 10000:
                raise DomainError('limit_exceeded', 413)
            # Choose once, at launch. Later runs cannot silently change the fitted data.
            latest = {r['configuration_revision_id']: r['run_id'] for r in rows}
            return dict(
                schema_version='1', calculation_version_id=version_id, state='calculating',
                reason=None, completed_count=0, total_count=len(members), estimate_id=None,
                runs=[dict(configuration_revision_id=m, run_id=latest.get(m),
                           reused=m in latest, completed=False) for m in members],
            )

        return self.store.command(
            actor, sid, CATEGORY, identity(version_id), request, accept,
            receipt_state='pending_remote', request=request,
        )

    def process_one(self, submissions):
        with self.store.background_actor(CATEGORY) as admitted:
            return self._process_one(submissions) if admitted else False

    def _process_one(self, submissions):
        with self.store.connection() as db:
            rows = db.execute(
                'SELECT scope,command_id,actor_id FROM receipts WHERE category=? '
                "AND state='pending_remote' ORDER BY rowid LIMIT 20", (CATEGORY,),
            ).fetchall()
        # Waiting for one analysis must not starve another analysis's acceptance.
        for row in rows:
            self._step(row, submissions)
        return bool(rows)

    def _step(self, row, submissions):
        sid, command, actor = row['scope'], row['command_id'], row['actor_id']
        with self.store.connection() as db:
            saved = self.store.command_receipt(db, sid, CATEGORY, command)
        result = saved['result']
        terminal = False
        try:
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid, write=True)
            version = self.analyses.version(actor, sid, result['calculation_version_id'])
            complete = 0
            needs_review = False
            for member in result['runs']:
                if member['completed']:
                    complete += 1
                    continue
                if member['run_id'] is None:
                    # Stable commands recover a crash between acceptance and receipt update.
                    run = submissions.submit(actor, sid, dict(
                        command_id=str(uuid5(UUID(command), member['configuration_revision_id'])),
                        configuration_revision_id=member['configuration_revision_id'],
                    ))
                    member['run_id'] = run['run_id']
                run = submissions.read(actor, sid, member['run_id'])
                if run['state'] == 'uncertain':
                    needs_review = True
                elif run['state'] == 'preparation_failed':
                    raise DomainError('analysis_run_preparation_failed', 409)
                elif run['state'] == 'recorded':
                    retained = History(self.store).retained(actor, sid, member['run_id'])
                    outcome = (retained.history.get('results') or {}).get('execution')
                    if not isinstance(outcome, dict) or outcome.get('state') != 'finished':
                        raise DomainError('analysis_run_failed', 409)
                    member['completed'] = True
                    complete += 1
            result['completed_count'] = complete
            result['state'] = 'needs_review' if needs_review else 'calculating'
            result['reason'] = (
                'Resolve the uncertain run before continuing.' if needs_review else None
            )
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
        except DomainError as exc:
            # Busy fitting is safe to wait for; no accepted work is submitted twice.
            if exc.status != 429:
                reason = {
                    'analysis_run_failed': (
                        'A calculation failed. Review its run before creating a new analysis version.'
                    ),
                    'analysis_run_preparation_failed': (
                        'A calculation could not start. Review its run diagnostics.'
                    ),
                    'forbidden': 'Permission to execute this analysis was lost.',
                    'resource_not_found': 'An analysis dependency is no longer accessible.',
                }.get(exc.code, 'Analysis preparation stopped: ' + exc.code.replace('_', ' '))
                result.update(state='failed', reason=reason)
                terminal = True
        validate_calculation('AnalysisExecution1', result, retained=True)
        with self.store.connection(write=True) as db:
            db.execute(
                'UPDATE receipts SET result=?,state=? WHERE scope=? AND category=? '
                "AND command_id=? AND state='pending_remote'",
                (json.dumps(result), 'committed' if terminal else 'pending_remote',
                 sid, CATEGORY, command),
            )
