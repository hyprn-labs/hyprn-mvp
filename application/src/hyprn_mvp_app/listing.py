"""Bounded read windows. Callers authorize before resolving a scoped cursor."""

from .contracts import DomainError


def window(db, table, identity, clauses, parameters, cursor, limit, *, descending=False):
    """SQL fragments are owner-authored constants; only values come from requests.

    The extra row establishes continuation without decoding or validating it.
    Cursor membership is checked against the same study and filter as the page.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError('invalid_request', 400)
    where = ' AND '.join(clauses)
    values = list(parameters)
    if cursor:
        row = db.execute(
            f'SELECT c.rowid AS position FROM {table} c WHERE {where} AND c.{identity}=?',
            (*values, cursor),
        ).fetchone()
        if row is None:
            raise DomainError('resource_not_found', 404)
        where += ' AND c.rowid' + ('<' if descending else '>') + '?'
        values.append(row['position'])
    return where, values, 'DESC' if descending else 'ASC'


def configuration_filter(sid, model_id=None, model_revision_id=None):
    clauses, values = ['c.study_id=?'], [sid]
    for name, value in [('model_id', model_id), ('model_revision_id', model_revision_id)]:
        if value:
            clauses.append(f"json_extract(c.payload,'$.configuration.{name}')=?")
            values.append(value)
    return clauses, values
