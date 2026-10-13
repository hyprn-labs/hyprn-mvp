"""Bounded UI-C driver: real app jobs, a captured genuine archive transport reply.

Only the separately guarded native producer imports AiiDA. This helper never
executes candidates or drains scientific work. Every browser test gets a copy
of fresh fixture records, not a production migration.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import checks
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.computational_export import records_for_store
from hyprn_mvp_app.store import Store,DomainError


class ExportFixture:
    def __init__(self,scope):
        self.scope=scope
        checks.PROJECTION_SCOPE=scope
        native=checks.fixture.allocate_scope(checks.fixture.new_scope())
        command=[native.interpreter,'-B',str(checks.REPO/'deployment/tests/api_c_fixture.py'),'--ui-c']
        result=subprocess.run(command,cwd=checks.REPO,env=checks.fixture.clean_environment(native),capture_output=True,text=True)
        for label,text in [('stdout',result.stdout),('stderr',result.stderr)]:
            (scope.root/'evidence'/('native-material.'+label+'.log')).write_text(text)
        (scope.root/'evidence/native-material-command.json').write_text(json.dumps(dict(command=command,scope=str(native.root),exit=result.returncode)))
        assert result.returncode==0,result.stderr
        self.material=native.root/'artifacts/material'
        assert Path(json.loads(result.stdout.splitlines()[-1])['material'])==self.material
        native=checks.fixture.Scope(**{**json.loads((native.root/'scope.json').read_text()),'root':native.root})
        checks.fixture.scoped_path(native,'artifacts/material')
        self.count=0
        self.data={};self.props={}
        self.reset()

    def reset(self):
        self.count+=1
        directory=self.scope.root/'artifacts'/('export-'+str(self.count))
        shutil.copytree(self.material,directory)
        value=json.loads((directory/'fixture.json').read_text())
        store=Store(directory/'application.sqlite')
        with store.connection(write=True) as db:
            db.execute('DELETE FROM computational_record_requests')
            db.execute("DELETE FROM receipts WHERE category IN ('computational_record_preview','computational_record_create')")
        class OfflineModel:
            def call(self,*args,**kwargs):raise DomainError('backend_unavailable',503)
        self.data.clear();self.data.update(value,store=store,client=TestClient(create_app(store,Auth(store,self.scope.url),OfflineModel()),base_url=self.scope.url))
        self.props.clear();self.props.update(sid=value['sid'],rid=value['rid'],ancestor=value['ancestor'])
        self.preflight=json.loads((directory/'archive-preflight.json').read_text())
        self.response=json.loads((directory/'archive-response.json').read_text())
        self.service=records_for_store(store)
        with store.connection() as db:
            self.scientific=hashlib.sha256(repr([tuple(r) for r in db.execute('SELECT * FROM outbox')]).encode()).hexdigest()

    def control(self,control):
        assert set(control)=={'action'}
        action=control['action'];store=self.data['store']
        if action=='reset':self.reset();return self.props
        if action in ('revoke','restore'):
            with store.connection(write=True) as db:
                if action=='revoke':db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(self.data['sid'],self.data['actor']))
                else:db.execute('INSERT INTO memberships VALUES(?,?,?)',(self.data['sid'],self.data['actor'],'owner'))
            return {}
        if action=='building':
            class Interrupted(BaseException):pass
            def fault(point):
                if point=='claimed':raise Interrupted()
            self.service.fault=fault
            try:self.service.process_one(lambda value:(_ for _ in ()).throw(AssertionError('Must stop before archive call')))
            except Interrupted:pass
            finally:self.service.fault=lambda point:None
            return {}
        if action in ('process','fail'):
            def archive(value):
                assert value==self.preflight,'Unexpected archive selection'
                if action=='fail':raise DomainError('reference_conflict',409)
                return copy.deepcopy(self.response)
            processed=self.service.process_one(archive)
            return {'processed':processed}
        assert action=='evidence'
        with store.connection() as db:
            assert self.scientific==hashlib.sha256(repr([tuple(r) for r in db.execute('SELECT * FROM outbox')]).encode()).hexdigest()
            return {'requests':[dict(r) for r in db.execute('SELECT request_id,kind,command_id,state FROM computational_record_requests')], 'scientific_unchanged':True}
