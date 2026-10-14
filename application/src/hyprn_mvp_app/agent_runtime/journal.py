"""The action journal: one append-only row per agent tool call.

A call is journaled ``intended`` before it can change anything (with its argument digest and
the fresh command ids of a mutating tool), and then records exactly one outcome:
``complete`` (the records created or changed, guard warnings and, for writes, the bounded
result), ``refuse``, ``fail`` or ``uncertain``, each with a reason code from the closed list
and its HYPRN MVP message. A call refused at admission is journaled ``refused`` directly.
Raw arguments, client text and agent text are never stored; the store's triggers keep the
intent fixed and the outcome written once. Reconciliation of uncertain outcomes is not here.
Every statement runs through ``records`` on a write transaction of the one ``Store``.
"""

import json
import sqlite3

from ..contracts import canonical, uid
from . import limits
from . import records as rows
from .delegations import iso

# The closed reason list (03-UI-SPEC "Reason codes and messages"): the state a reason ends a
# call in and its message. Placeholders are filled only with HYPRN MVP text (schema paths and
# problems, record names and readiness reasons from HYPRN MVP's own records and validators).
REASONS = {
    'agent_disabled': ('refused', 'Assistant access is off for this installation.'),
    'access_lost': ('refused', "The assistant's access to this study had ended."),
    'budget_exhausted': (
        'refused',
        'The assistant reached the limit of '
        f'{limits.MAX_API_CALLS_PER_SESSION} API calls for one session.',
    ),
    'repeated_errors': ('refused', 'The assistant repeated the same invalid call too often.'),
    'run_limit_call': (
        'refused',
        f'One call can submit at most {limits.MAX_RUNS_PER_CALL} runs.',
    ),
    'run_limit_queued': (
        'refused',
        f'At most {limits.MAX_QUEUED_RUNS_PER_ACTOR} runs from this assistant can wait or run '
        'at once.',
    ),
    'run_limit_session': (
        'refused',
        f'The assistant reached the limit of {limits.MAX_RUNS_PER_SESSION} runs for one session.',
    ),
    'invalid_input': ('refused', 'The request was not valid: {field} {problem}.'),
    'guard_blocked': ('refused', 'The text of {field} contains {what}.'),
    'conflict': (
        'refused',
        '{record} changed after the assistant read it. The other change was kept.',
    ),
    'not_ready': ('refused', "Runs can't start now: {reason}."),
    'human_only': (
        'refused',
        'Only a person can delete saved work, archive or restore, or change access.',
    ),
    'forbidden': ('refused', 'This action is not available to assistants.'),
    'not_found': ('refused', 'The record is not available to this assistant.'),
    'backend_unavailable': ('failed', 'The modeling service was unavailable.'),
    'internal': ('failed', 'An internal error stopped the call.'),
    'outcome_unknown': (
        'uncertain',
        "The outcome of this call is not known. Don't resubmit; check the records before "
        'making more changes.',
    ),
}
_DEFAULTS = {
    'field': '(input)',
    'problem': 'is not valid',
    'what': 'content that is not allowed',
    'record': 'The record',
    'reason': 'execution is not ready',
}
MAX_MESSAGE = 512
MAX_PARAMETER = 200


class Duplicate(Exception):
    """The session already journaled a call with this call id."""


def message(code, params=None):
    """The HYPRN MVP message of reason ``code`` with its placeholders filled."""
    _, template = REASONS[code]
    values = dict(_DEFAULTS)
    for key, value in (params or {}).items():
        if key in values and isinstance(value, str) and value:
            values[key] = value[:MAX_PARAMETER]
    return template.format(**values)[:MAX_MESSAGE]


def _json(value):
    return canonical(value).decode()


def find(store, session_id, call_id):
    """The journal row of call ``call_id`` in session ``session_id``; ``None`` when none."""
    with store.connection() as db:
        return rows.action(db, session_id, call_id)


def read(store, action_id):
    """Journal row ``action_id``; ``None`` when there is none."""
    with store.connection() as db:
        return rows.action_by_id(db, action_id)


def _row(intent, state, now):
    return dict(
        action_id=uid(),
        session_id=intent['session_id'],
        delegation_id=intent['delegation_id'],
        study_id=intent['study_id'],
        call_id=intent['call_id'],
        tool=intent['tool'],
        effect=intent['effect'],
        args_sha256=intent['args_sha256'],
        command_ids=_json(list(intent.get('command_ids', ()))),
        state=state,
        created_at=iso(now),
    )


def intend(store, intent, now):
    """Journal call ``intent`` (``session_id``, ``delegation_id``, ``study_id``, ``call_id``,
    ``tool``, ``effect``, ``args_sha256``, ``command_ids``) as ``intended``; returns its
    action id. Raises ``Duplicate`` when the session already journaled the call id."""
    row = _row(intent, 'intended', now)
    try:
        with store.connection(write=True) as db:
            rows.insert_action(db, row)
    except sqlite3.IntegrityError:
        if find(store, intent['session_id'], intent['call_id']) is not None:
            raise Duplicate() from None
        raise
    return row['action_id']


def _outcome(state, now, outcome_class, code, params, api_operations, warnings, records, result):
    return dict(
        api_operations=_json(list(api_operations)[: limits.MAX_API_OPERATIONS]),
        outcome_class=outcome_class,
        reason_code=code,
        reason_message=None if code is None else message(code, params),
        warnings=_json(list(warnings)[: limits.MAX_WARNINGS]),
        records=_json(list(records)[: limits.MAX_RECORDS]),
        result_json=result,
        state=state,
        completed_at=iso(now),
    )


def refused(store, intent, code, now, *, outcome_class, params=None):
    """Journal call ``intent`` as refused at admission with reason ``code`` (no API call was
    made); returns its action id, or ``None`` when the session already journaled the call
    id (a duplicate delivery keeps its one row)."""
    if REASONS[code][0] != 'refused':
        raise ValueError('Not a refusal reason')
    row = dict(
        _row(intent, 'refused', now),
        **_outcome('refused', now, outcome_class, code, params, (), (), (), None),
    )
    try:
        with store.connection(write=True) as db:
            rows.insert_action(db, row)
    except sqlite3.IntegrityError:
        if find(store, intent['session_id'], intent['call_id']) is not None:
            return None
        raise
    return row['action_id']


def _finish(store, action_id, outcome, session_id=None, runs=0):
    with store.connection(write=True) as db:
        moved = rows.finish_action(db, action_id, outcome)
        if moved and runs and session_id is not None:
            rows.add_runs_submitted(db, session_id, runs)
    return moved


def stored_result(result):
    """``result`` as the bounded JSON text a write's journal row keeps (``None`` for none)."""
    if result is None:
        return None
    text = _json(result)
    if len(text.encode()) > limits.RESULT_CAP_BYTES:
        text = _json({'result_omitted': 'larger than the journal keeps'})
    return text


def complete(
    store,
    action_id,
    now,
    *,
    records=(),
    warnings=(),
    result=None,
    api_operations=(),
    session_id=None,
):
    """Record that call ``action_id`` completed: the records it created or changed
    , its guard warnings and, for writes, its result (at most 24 KB). The runs among
    the records are added to the session's submitted-run counter. Whether the row moved."""
    records = list(records)[: limits.MAX_RECORDS]
    runs = sum(1 for r in records if r.get('kind') == 'run')
    outcome = _outcome(
        'completed', now, 'ok', None, None, api_operations, warnings, records, stored_result(result)
    )
    return _finish(store, action_id, outcome, session_id, runs)


def _end(
    store,
    action_id,
    state,
    code,
    now,
    outcome_class,
    params,
    api_operations,
    warnings,
    records,
    session_id,
):
    if REASONS[code][0] != state:
        raise ValueError('The reason does not end a call in that state')
    records = list(records)[: limits.MAX_RECORDS]
    runs = sum(1 for r in records if r.get('kind') == 'run')
    outcome = _outcome(
        state, now, outcome_class, code, params, api_operations, warnings, records, None
    )
    return _finish(store, action_id, outcome, session_id, runs)


def refuse(
    store,
    action_id,
    code,
    now,
    *,
    outcome_class,
    params=None,
    api_operations=(),
    warnings=(),
    records=(),
    session_id=None,
):
    """Record that call ``action_id`` was refused with reason ``code``: nothing changed."""
    return _end(
        store,
        action_id,
        'refused',
        code,
        now,
        outcome_class,
        params,
        api_operations,
        warnings,
        records,
        session_id,
    )


def fail(
    store,
    action_id,
    code,
    now,
    *,
    outcome_class,
    params=None,
    api_operations=(),
    warnings=(),
    records=(),
    session_id=None,
):
    """Record that call ``action_id`` failed with reason ``code``: nothing changed."""
    return _end(
        store,
        action_id,
        'failed',
        code,
        now,
        outcome_class,
        params,
        api_operations,
        warnings,
        records,
        session_id,
    )


def uncertain(
    store,
    action_id,
    now,
    *,
    outcome_class,
    api_operations=(),
    warnings=(),
    records=(),
    session_id=None,
):
    """Record that the outcome of call ``action_id`` is not known (``outcome_unknown``): it is
    never re-sent; the records it reported are kept."""
    return _end(
        store,
        action_id,
        'uncertain',
        'outcome_unknown',
        now,
        outcome_class,
        None,
        api_operations,
        warnings,
        records,
        session_id,
    )


def loads(text):
    """A JSON column of a journal row as data."""
    return json.loads(text) if text is not None else None
