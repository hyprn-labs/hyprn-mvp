"""Small authorized projections of owner records, never an independent workflow state."""
import json
from uuid import UUID, uuid5

from .history import run_count


def analysis_progress(db, study, version):
    """Read current durable execution facts without waiting for an Assistant event."""
    command = str(uuid5(UUID(version), 'analysis_execution'))
    row = db.execute("SELECT result FROM receipts WHERE scope=? "
                     "AND category='analysis_execution' AND command_id=?", (study, command)).fetchone()
    if not row or not row['result']:
        return None
    result = json.loads(row['result'])
    runs = result.get('runs', [])
    return dict(
        calculation_version_id=version, state=result['state'],
        completed_count=result['completed_count'], total_count=result['total_count'],
        assigned_count=sum(r['run_id'] is not None for r in runs),
        reused_count=sum(r['reused'] for r in runs),
        admission_state=result.get('admission_state'),
        last_progress_at=result.get('last_progress_at'),
    )


def read(store, actor, study):
    """Bounded operational reads; no model service, retained bundle or provider calls."""
    with store.connection() as db:
        store.authorize(db, actor, study)
        counts = dict(models=store.model_count(db, actor, study), runs=run_count(db, study))
        for name, table in (('configuration_versions', 'configurations'),
                            ('analyses', 'calculations')):
            counts[name] = db.execute('SELECT count(*) FROM ' + table + ' WHERE study_id=?',
                                      (study,)).fetchone()[0]
        rows = db.execute("SELECT json_extract(result,'$.calculation_version_id') AS version "
                          "FROM receipts WHERE scope=? AND category='analysis_execution' "
                          "AND state='pending_remote' ORDER BY rowid DESC LIMIT 11",
                          (study,)).fetchall()
        analyses = []
        for row in rows[:10]:
            progress = analysis_progress(db, study, row['version'])
            version = db.execute("SELECT json_extract(payload,'$.content.name') AS name, "
                                 "json_extract(payload,'$.content.model_id') AS model_id, "
                                 "json_extract(payload,'$.content.model_revision_id') AS revision "
                                 'FROM calculation_versions WHERE study_id=? '
                                 'AND calculation_version_id=?', (study, row['version'])).fetchone()
            if progress and version:
                analyses.append(dict(progress, name=version['name'],
                                     model_id=version['model_id'], revision=version['revision']))
        conversation = db.execute('SELECT state,active_turn FROM assistant_conversations '
                                  'WHERE study_id=?', (study,)).fetchone()
        return dict(counts=counts, analyses=analyses, has_more_analyses=len(rows) > 10,
                    assistant_state=conversation['state'] if conversation else None)
