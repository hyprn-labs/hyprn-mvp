"""Only synthetic off-cloud SQLite stores, never current application storage."""
import sqlite3
import pytest
from hyprn_mvp_app.store import Store, DomainError, uid, SCHEMA

@pytest.fixture
def env(tmp_path):
    store=Store(tmp_path/'app.sqlite3');actor=uid();sid=store.create_study(actor,uid(),'Preserved')['study_id']
    return store,actor,sid

def insert(db,sid,aid,vid):
    db.execute('INSERT INTO approach_drafts VALUES(?,?,?,?)',(aid,sid,uid(),'{}'))
    db.execute('INSERT INTO approach_versions VALUES(?,?,?,?,?)',(vid,aid,sid,1,'{}'))

def test_additive_reopen_preserves_records_and_creates_no_draft(env):
    store,actor,sid=env
    before=store.study(actor,sid)
    Store(store.path)
    assert store.study(actor,sid)==before
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM approach_drafts').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM approach_versions').fetchone()[0]==0

def test_version_immutable_unique_and_foreign_key(env):
    store,actor,sid=env;aid,vid=uid(),uid()
    with store.connection(write=True) as db:insert(db,sid,aid,vid)
    for sql in ('UPDATE approach_versions SET payload=? WHERE approach_version_id=?','DELETE FROM approach_versions WHERE approach_version_id=?'):
        with pytest.raises(sqlite3.IntegrityError):
            with store.connection(write=True) as db:db.execute(sql,('{}',vid) if sql.startswith('UPDATE') else (vid,))
    with pytest.raises(sqlite3.IntegrityError):
        with store.connection(write=True) as db:db.execute('INSERT INTO approach_versions VALUES(?,?,?,?,?)',(uid(),aid,sid,1,'{}'))
    with pytest.raises(sqlite3.IntegrityError):
        with store.connection(write=True) as db:db.execute('INSERT INTO approach_drafts VALUES(?,?,?,?)',(uid(),sid,uid(),'{}'))

def test_atomic_command_rejection_rolls_back_both_tables_and_retains_receipt(env):
    store,actor,sid=env;command=uid()
    def fail(db):
        insert(db,sid,uid(),uid())
        raise DomainError('invalid_request',400)
    with pytest.raises(DomainError):store.command(actor,sid,'approach_version',command,{},fail)
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM approach_drafts').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM approach_versions').fetchone()[0]==0
        assert db.execute('SELECT state FROM receipts WHERE command_id=?',(command,)).fetchone()[0]=='rejected'

def test_receipt_replay_cas_and_authorization(env):
    store,actor,sid=env;aid,vid,command=uid(),uid(),uid()
    def write(db):
        insert(db,sid,aid,vid);return {'approach_version_id':vid}
    first=store.command(actor,sid,'approach_version',command,{},write)
    assert store.command(actor,sid,'approach_version',command,{},lambda _:pytest.fail('duplicate write'))==first
    with pytest.raises(DomainError):store.command(actor,sid,'approach_version',command,{'changed':1},write)
    with pytest.raises(DomainError):store.command(uid(),sid,'approach_version',command,{},write)
    with pytest.raises(DomainError):store.cas(uid(),uid())

def test_version_cannot_attach_to_another_study_family(env):
    store,actor,sid=env;aid=uid()
    other=store.create_study(actor,uid(),'Other')['study_id']
    with store.connection(write=True) as db:
        db.execute('INSERT INTO approach_drafts VALUES(?,?,?,?)',(aid,sid,uid(),'{}'))
    with pytest.raises(sqlite3.IntegrityError):
        with store.connection(write=True) as db:
            db.execute('INSERT INTO approach_versions VALUES(?,?,?,?,?)',(uid(),aid,other,1,'{}'))

def test_upgrade_of_populated_previous_schema_preserves_original_bytes(tmp_path):
    path=tmp_path/'old.sqlite3';sid,actor,eid,cid=uid(),uid(),uid(),uid()
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.split('CREATE TABLE IF NOT EXISTS approach_drafts')[0])
        db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(sid,uid(),'Original','First\\nSecond',''))
        db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))
        db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(eid,uid(),sid,' { "original": true } '))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(cid,uid(),sid,'{ "record": 1e0 }'))
        before={t:db.execute('SELECT * FROM '+t).fetchall() for t in ('studies','memberships','evidence','configurations')}
    store=Store(path)
    with store.connection() as db:
        assert {t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in before}==before
        assert db.execute('SELECT COUNT(*) FROM approach_drafts').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM approach_versions').fetchone()[0]==0
