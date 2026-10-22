"""Seed pre-brief study context in isolated historical-record fixtures only.

This reproduces the retired receipt format for historical-read tests. It is not an
application operation and must never be imported by production code or used on live stores.
"""

from hyprn_mvp_app.store import DomainError, uid


def seed_legacy_context(store, actor, sid, command, expected, changes):
    if not changes or set(changes) - {'name', 'description', 'boundary'}:
        raise DomainError('invalid_request', 400)

    def apply(db):
        row = store.study_row(db, sid)
        store.cas(row['revision'], expected)
        row.update(changes)
        row['revision'] = uid()
        db.execute(
            'UPDATE studies SET revision=?,name=?,description=?,boundary=? WHERE study_id=?',
            (row['revision'], row['name'], row['description'], row['boundary'], sid),
        )
        return row

    return store.command(
        actor,
        sid,
        'study',
        command,
        dict(operation='update_study', target=sid, expected_revision=expected, changes=changes),
        apply,
        attribute=lambda r: [('study_context', sid, r['revision'])],
    )
