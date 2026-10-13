"""Isolated native node admission only; no generated program is executed."""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'application/tests'))
from test_approach_bundle import case5
from test_assumptions_execution import assembled
from test_result_dependencies import native
from test_submission import NativeDouble
from hyprn_mvp_app.execution import Submissions
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_app.store import Store,uid
from aiida import orm
from checks import NATIVE_BACKEND

@pytest.mark.parametrize('linked',[False,True])
def test_actual_dispatch_empty_dependencies_prepare_and_restart(tmp_path,monkeypatch,linked):
    store=Store(tmp_path/'app.sqlite');actor=uid();study=store.create_study(actor,uid(),'Approach bundle')
    sid=study['study_id'];case,_=case5(linked,sid);c=case['frozen']['configuration']
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],sid,json.dumps(case['frozen'])))
    calls=[];original=ResultBindings.dependencies
    def dependencies(self,*args):
        calls.append(args[2]['schema_version']);return original(self,*args)
    monkeypatch.setattr(ResultBindings,'dependencies',dependencies)
    native=NativeDouble();prepared=[]
    def prepare(*args):prepared.append(True);return case['prepared'],case['files']
    service=Submissions(store,prepare,native)
    run=service.submit(actor,sid,dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    service.dispatch(run['run_id'],prepare_only=True)
    assert calls==['4'] and prepared==[True] and native.launches==0
    def unavailable(*args):pytest.fail('Restart must retain complete preparation')
    Submissions(store,unavailable,native).dispatch(run['run_id'],prepare_only=True)
    assert native.launches==0

@pytest.mark.parametrize('linked',[False,True])
def test_bundle5_native_node_only_boundary(native,linked):
    case,deps=case5(linked);bundle,request=assembled(case,deps)
    with pytest.raises(RuntimeError,match='Node-only boundary stop'):native.launch(bundle,request)
    matches=native.matches(request);assert len(matches)==1
    node=orm.load_node(matches[0]);assert node.inputs.frozen_bundle.base.repository.get_object_content('approach/closure.json') if linked else True
    assert node.base.links.get_outgoing().all()==[]
    with pytest.raises(RuntimeError,match='Existing native request'):native.launch(bundle,request)

def test_corrupt_closure_rejected_before_native_allocation(native):
    case,deps=case5();bundle,request=assembled(case,deps)
    count=lambda:orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.Node).count()
    before=count();bundle['files']['approach/closure.json']+=b'x'
    with pytest.raises(ValueError):native.launch(bundle,request)
    assert count()==before

def test_current_attestation_remains_before_allocation(native,monkeypatch):
    case,deps=case5();bundle,request=assembled(case,deps)
    count=lambda:orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.Node).count()
    before=count()
    def stale():raise RuntimeError('Current runtime attestation required')
    monkeypatch.setattr(native,'require_attestation',stale)
    with pytest.raises(RuntimeError,match='Current runtime attestation'):native.launch(bundle,request)
    assert count()==before


def test_polish_bundle8_actual_dispatch_preparation_and_cold_retry(tmp_path):
    from test_unit_execution_admission import case8,repin
    # Legacy-unit Model4 does not need the new unit table for its own arithmetic.
    case=case8(None,approach_version=None,legacy=True)
    store=Store(tmp_path/'polish.sqlite');actor=uid();sid=store.create_study(actor,uid(),'Polish')['study_id']
    c=case['frozen']['configuration'];c['study_id']=sid;repin(case)
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],sid,json.dumps(case['frozen'])))
    native=NativeDouble();calls=[]
    def prepare(*args):calls.append(True);return case['prepared'],case['files']
    service=Submissions(store,prepare,native);run=service.submit(actor,sid,dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    service.dispatch(run['run_id'],prepare_only=True)
    with store.connection() as db:payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])
    assert payload['bundle']['manifest']['schema_version']=='8'
    def unavailable(*args):pytest.fail('Cold retry must retain exact preparation')
    Submissions(store,unavailable,native).dispatch(run['run_id'],prepare_only=True)
    assert calls==[True] and native.launches==0
