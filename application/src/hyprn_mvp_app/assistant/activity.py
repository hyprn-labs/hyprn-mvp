"""Bounded observed tool activity; provider arguments, results and reasoning stay private."""

import hashlib
import math

from ..agent_tools.registry import REGISTRY

LIMIT = 40
NATIVE_LABELS = {'web_search': 'Search sources', 'web_fetch': 'Read source'}


def stamp(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 253402300799 else None


def label(name, native):
    if native:
        return NATIVE_LABELS.get(name, 'Research tool')
    try:
        return REGISTRY.tool(name).title
    except (KeyError, TypeError):
        return 'Tool operation'


def read(db, current):
    """Current-turn facts only; SQL projects bounded safe fields without loading tool bodies."""
    if not current or not current['active_turn']:
        return {'steps': [], 'has_earlier_steps': False}
    study, turn = current['study_id'], current['active_turn']
    admitted = db.execute('SELECT provider_event FROM assistant_turns '
        'WHERE study_id=? AND turn_id=?', (study, turn)).fetchone()
    if not admitted or not admitted[0]:
        return {'steps': [], 'has_earlier_steps': False}
    start = db.execute('SELECT position FROM assistant_events WHERE study_id=? AND event_id=?',
                       (study, admitted[0])).fetchone()
    if not start:
        return {'steps': [], 'has_earlier_steps': False}
    rows = db.execute("SELECT e.event_id,e.event_type,json_extract(e.payload,'$.name') AS name, "
        "json_extract(e.payload,'$._received_at') AS started, "
        "json_extract(e.payload,'$.session_thread_id') AS child, "
        "json_extract(r.payload,'$._received_at') AS finished, "
        "json_extract(r.payload,'$.is_error') AS result_error, r.event_id AS result_id, "
        't.delivery,t.is_error FROM assistant_events e '
        'LEFT JOIN assistant_tool_results t ON t.study_id=e.study_id '
        'AND t.event_id=e.event_id AND t.turn_id=? '
        'LEFT JOIN assistant_events r ON r.study_id=e.study_id AND r.position=('
        'SELECT max(x.position) FROM assistant_events x WHERE x.study_id=e.study_id '
        'AND x.reference_id=e.event_id AND x.position>e.position '
        "AND x.event_type IN ('agent.tool_result','user.custom_tool_result')) "
        "WHERE e.study_id=? AND e.position>? AND e.event_type IN "
        "('agent.custom_tool_use','agent.tool_use') ORDER BY e.position DESC LIMIT ?",
        (turn, study, start[0], LIMIT + 1)).fetchall()
    steps = []
    for row in reversed(rows[:LIMIT]):
        native = row['event_type'] == 'agent.tool_use'
        delivery = row['delivery']
        if delivery == 'waiting':
            state = 'waiting'
        elif delivery == 'uncertain':
            state = 'uncertain'
        elif delivery in ('ready', 'accepted'):
            state = 'failed' if row['is_error'] else 'completed'
        elif native and row['result_id']:
            state = ('failed' if row['result_error'] in (True, 1, 'true') else
                     'completed' if row['result_error'] in (False, 0, 'false') else 'returned')
        else:
            state = 'running'
        started = stamp(row['started'])
        finished = stamp(row['finished']) if state in ('completed', 'failed', 'returned') else None
        if started is not None and finished is not None and finished < started:
            finished = None
        steps.append(dict(
            step_id=hashlib.sha256((study + ':' + row['event_id']).encode()).hexdigest(),
            label=label(row['name'], native), state=state,
            actor='reviewer' if row['child'] else 'assistant',
            started_at=started, finished_at=finished,
        ))
    return {'steps': steps, 'has_earlier_steps': len(rows) > LIMIT}
