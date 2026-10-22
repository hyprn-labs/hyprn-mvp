"""Actual HTTP/JWT approach proof over explicitly scoped native infrastructure.

No frozen generator captures, transport doubles or computed records are seeded.
NativeJourney supplies the production private client and isolated attestation.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json

from aiida import orm
from combined_fixture import NativeJourney
from hyprn_mvp_app.store import canonical,digest,uid


def source(raw):
    return dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())


def step(title):
    return dict(step_id=uid(),title=title,purpose='Explain the physical calculation',rationale='Explicit authored method',remaining_work='',
        intent=dict(transformation='F = m v / t',inputs='Mass, velocity and duration',outputs='Force',depends_on_step_ids=[]),
        implementation_state='proposed',implementation_refs=[],assumption_refs=[],evidence_links=[])


class ApproachJourney(NativeJourney):
    def process_count(self):return orm.QueryBuilder(backend=self.backend).append(orm.CalcJobNode).count()

    def evidence(self,title,*,previous=None):
        body=dict(command_id=uid(),evidence_schema_version='3',title=title,kind='note',content='Authored synthetic calibration context; no validity claim',
            source_refs=['Fixture analytical specification'],resource_scope=dict(scope_version='1',kind='study',study_id=self.sid))
        path='evidence'
        if previous:
            path='evidence-families/'+previous['evidence_id']+'/versions';body['expected_revision']=previous['evidence_version_id']
        value=self.request('POST',path,body,201)
        assert self.request('POST',path,body,201)==value
        return value

    def save_approach(self,content):
        state=self.request('GET','approach');revision=state['draft']['revision'] if state['draft'] else None
        body=dict(schema_version='1',expected_revision=revision,content=content)
        preview=self.request('POST','approach/preview',body)
        (self.scope.root/'evidence'/('approach-preview-'+str(len(self.events))+'.json')).write_text(json.dumps(dict(body=body,preview=preview),indent=2))
        if preview['issues']:
            from hyprn_mvp_app.approach_closure import build_closure
            from uuid import UUID,uuid5
            candidate=dict(schema_version='1',approach_id=state['draft']['approach_id'] if state['draft'] else str(uuid5(UUID(self.sid),'approach-preview-family')),
                approach_version_id=str(uuid5(UUID(self.sid),'preview:'+digest(content))),study_id=self.sid,version_number=1,predecessor_version_id=None,
                content=content,created_by=self.actor,created_at='1970-01-01T00:00:00Z')
            candidate['digest']=digest(candidate)
            build_closure(candidate,preview['resolved'],study_id=self.sid)
            raise AssertionError(preview['issues'])
        command=dict(body,command_id=uid(),expected_preview_digest=preview['preview_digest'])
        draft=self.request('POST','approach/draft',command)
        assert self.request('POST','approach/draft',command)==draft
        assert self.request('GET','commands/'+command['command_id']+'?category=approach_draft')['result']==draft
        self.request('POST','approach/draft',command|{'content':content|{'question':'Conflicting replay'}},409)
        self.request('POST','approach/draft',command|{'command_id':uid()},409)
        body=dict(schema_version='1',expected_revision=draft['revision'],content=content)
        preview=self.request('POST','approach/preview',body)
        command=dict(schema_version='1',command_id=uid(),expected_revision=draft['revision'],expected_preview_digest=preview['preview_digest'])
        saved=self.request('POST','approach/versions',command,201)
        assert self.request('POST','approach/versions',command,201)==saved
        assert self.request('GET','commands/'+command['command_id']+'?category=approach_version')['result']==saved
        return saved['saved']

    def model(self,name,edits):
        """Commit a Model4 revision: a format-4 edit envelope upgrades the new draft, and every
        created port declares typed units (a string spelling becomes its declaration)."""
        study=self.http.get('/api/1/studies/'+self.sid).json()['data']
        body=dict(command_id=uid(),expected_revision=study['revision'],name=name,template='empty')
        draft=self.request('POST','models',body,201)
        mp='models/'+draft['model_id']
        body=dict(schema_version='4',command_id=uid(),expected_revision=draft['draft_revision'],
            edits=declared(edits))
        draft=self.request('POST',mp+'/edits',body)
        assert self.request('POST',mp+'/edits',body)==draft
        body=dict(command_id=uid(),expected_revision=draft['draft_revision'])
        model=self.request('POST',mp+'/commits',body)
        assert model['schema_version']=='4'
        assert 'quantity_definitions/1' in model['required_capabilities']
        assert not self.canary()['candidate_side_effect']
        return draft,model

    def configuration(self,model,name,inputs,evidence):
        """A configuration request 6: explicit inputs only, no criteria and no approach."""
        study=self.http.get('/api/1/studies/'+self.sid).json()['data']
        numerical=dict(mode='deterministic',initialization=[],solvers=[],design_variables=[],
            objectives=[],constraints=[],optimizer=None,uncertainty=None,
            derivatives=dict(method='none',form=None,check=None))
        return dict(schema_version='6',study_id=self.sid,model_id=model['model_id'],
            model_revision_id=model['model_revision_id'],name=name,inputs=inputs,
            numerical=numerical,
            context_source=dict(kind='current_study',expected_study_revision=study['revision']),
            notes=['Explicit analytical test'],assumptions=[],
            general_context_evidence_version_ids=[evidence['evidence_version_id']],derivation=None)

    def save_configuration(self,value):
        n=self.process_count();preview=self.request('POST','configurations/preview',value)
        assert preview['schema_version']=='8' and 'criteria' not in preview['resolved_candidate']
        body=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=value,expected_preview_digest=preview['candidate_digest'])
        saved=self.request('POST','configurations',body,201)
        assert self.request('POST','configurations',body,201)==saved
        assert saved['schema_version']=='9' and saved['configuration']['schema_version']=='6'
        assert 'approach_closure' not in saved and 'criteria' not in saved['configuration']
        self.request('POST','configurations',body|{'expected_preview_digest':'0'*64},409)
        assert self.process_count()==n and not self.canary()['candidate_side_effect']
        return saved

    def execute(self,saved):
        body=dict(command_id=uid(),configuration_revision_id=saved['configuration']['configuration_revision_id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(lambda _:self.request('POST','runs',body,202),range(2)))
        assert rows[0]==rows[1]
        rid=rows[0]['run_id'];n=self.process_count()
        self.dispatch(rid,prepare_only=True)
        assert self.process_count()==n and not self.canary()['candidate_side_effect']
        self.dispatch(rid);detail=self.request('GET','runs/'+rid)
        assert detail['state']=='recorded' and not detail['history']['errors'],json.dumps(detail)
        self.recorded_without_criteria(detail)
        assert self.process_count()==n+1
        self.dispatch(rid);assert self.process_count()==n+1
        assert self.request('POST','runs',body,202)['run_id']==rid
        payload=self.payload(rid);node=orm.load_node(payload['history']['association']['process_uuid'])
        assert node.is_finished_ok and not node.base.caching.is_created_from_cache
        assert node.outputs.results.creator.uuid==node.uuid
        files={p:base64.b64decode(b) for p,b in payload['bundle']['files'].items()}
        prepared=json.loads(files['preparation.json']);generator=json.loads(files['provenance/generator.json'])
        assert prepared['entrypoint']['protocol']=='hyprn_mvp.openmdao.program/1'
        assert any(p.startswith('generated/base/') for p in files)
        assert 'app/lib/whats_opt/openmdao_generator.rb' in json.dumps(generator)
        for item in prepared['files']:
            assert hashlib.sha256(files[item['path']]).hexdigest()==item['sha256']
        proof=dict(prepared=prepared,generator=generator,source_hashes={p:hashlib.sha256(b).hexdigest() for p,b in files.items()},
            process_uuid=node.uuid,run_id=rid,results=detail['history']['results'])
        (self.scope.root/'evidence'/('native-run-'+rid+'.json')).write_text(json.dumps(proof,indent=2))
        return rid,detail,node


def literal(target,value,units,eid):
    return dict(kind='literal',target=target,value=value,units=units,provenance=dict(kind='manual',statement='Explicit analytical input',evidence_version_ids=[eid]))


def declaration(units):
    """The typed declaration of one unit spelling: empty is dimensionless, never unspecified."""
    return {'kind':'dimensionless'} if units=='' else {'kind':'physical','expression':units}


def declared(edits):
    """Edits whose created ports carry typed unit declarations, as Model4 requires."""
    edits=deepcopy(edits)
    for edit in edits:
        if edit['kind']!='create_definition':
            continue
        for port in edit['ports']:
            if isinstance(port['units'],str):
                port['units']=declaration(port['units'])
    return edits
