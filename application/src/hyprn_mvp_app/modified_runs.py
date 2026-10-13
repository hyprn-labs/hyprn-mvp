"""Data-only retained origins; derivation creates no numerical input or process."""
from copy import deepcopy
import json

from .contracts import DomainError, canonical, digest, validate
from .history import History, complete_outcome
from .readiness import runtime_comparison, runtime_identity


def unsupported():
    return DomainError('unsupported_record_version',422,fields=[dict(path='/configuration',code='invalid',
        message='This retained configuration is unsupported. Create a new configuration.',element_ref=None)])


def context_changed(source,study):
    return any(source[key]!=study[key] for key in ('description','boundary'))


def changes(source,candidate):
    """Deterministic bounded scientific delta; never client-authored claims."""
    missing=object();records=[];summaries=[]
    def summary(value):
        if value is missing:return 'Not present'
        return (value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,allow_nan=False))[:512]
    def walk(before,after,path):
        if before is not missing and after is not missing and canonical(before)==canonical(after):return
        if isinstance(before,dict) and isinstance(after,dict):
            for key in sorted(set(before)|set(after)):
                walk(before.get(key,missing),after.get(key,missing),path+'/'+key.replace('~','~0').replace('/','~1'))
        elif isinstance(before,list) and isinstance(after,list):
            for index in range(max(len(before),len(after))):
                walk(before[index] if index<len(before) else missing,after[index] if index<len(after) else missing,path+'/'+str(index))
        else:
            if len(records)>=4096:raise DomainError('limit_exceeded',413)
            records.append(dict(path=path,before_digest=None if before is missing else digest(before),after_digest=None if after is missing else digest(after)))
            summaries.append(dict(path=path,before=summary(before),after=summary(after)))
    previous=deepcopy(source)
    for item in previous['inputs']:item.setdefault('result_binding',None)
    for key in ('name','inputs','criteria','numerical','context_snapshot','evidence_snapshots'):
        walk(previous[key],candidate[key],'/'+key)
    if source.get('schema_version') in ('3','4') or candidate.get('schema_version') in ('3','4'):
        # Assumption identity survives reordering; citation identity includes its
        # relationship so simultaneous supports/challenges remain independent.
        def assumptions(config):
            return {a['assumption_id']:{**a,'evidence_links':{
                link['evidence_version_id']+':'+link['relation']:link for link in a['evidence_links']}}
                for a in config.get('assumptions',[])}
        walk(assumptions(source),assumptions(candidate),'/assumptions')
        walk({eid:True for eid in source.get('general_context_evidence_version_ids',[])},
             {eid:True for eid in candidate.get('general_context_evidence_version_ids',[])},
             '/general_context_evidence_version_ids')
    if source.get('schema_version')=='4' or candidate.get('schema_version')=='4':
        walk(source.get('approach_binding'),candidate.get('approach_binding'),'/approach_binding')
    return records,summaries


def seedable(payload):
    """Explicit refusal before integrity checks: only deterministic configurations 1-4 seed."""
    config=payload.get('frozen',{}).get('configuration',{})
    if config.get('schema_version') not in ('1','2','3','4'):raise unsupported()
    if config.get('numerical',{}).get('mode')!='deterministic':raise unsupported()


class ModifiedRuns:
    def __init__(self,store):self.store=store;self.history=History(store)

    def retained(self,actor,sid,rid):
        """A terminal retained run usable as a modified-run seed (History owns the reading).

        Eligibility added here: a deterministic configuration 1-4, a finished (exit 0) or
        failed (exit 1) complete outcome and a closed runtime identity. Refusals are
        ``incomplete_record`` 422, except ``record_not_ready``, ``unsupported_record_version``,
        ``resource_not_found`` and ``reference_conflict``, which propagate.
        """
        try:
            run=self.history.retained(actor,sid,rid,admit=seedable)
            config=run.history['configuration'];model=run.history['model_snapshot'];result=run.history['results']
            manifest=run.payload['bundle']['manifest']
            if (result['execution']['state'] not in ('finished','failed') or type(result['execution']['exit_code']) is not int
                    or result['execution']['exit_code']!=(0 if result['execution']['state']=='finished' else 1)):
                raise ValueError('Source record identity mismatch')
            complete_outcome(result,model,config)
            runtime_identity(manifest['runtime'])
            # Bundle4/5/6 authenticate the complete immutable citation closure.
            # Seed reads must remain possible when today's library is offline;
            # preview/commit separately rechecks exact selected evidence rows.
            # Configuration 1/2 bundles do not authenticate that closure, so each
            # retained snapshot is compared, field by field, with its immutable
            # stored evidence version. This is a consistency check only: a mismatch
            # refuses, and the stored row is never returned or merged.
            if config['schema_version'] not in ('3','4'):
                for snapshot in config['evidence_snapshots']:
                    stored=self.store.evidence_version(actor,sid,snapshot['evidence_version_id'])
                    if any(stored.get(k)!=v for k,v in snapshot.items()):raise ValueError('Source evidence mismatch')
            return run
        except DomainError as error:
            if error.code in ('resource_not_found','reference_conflict','unsupported_record_version','record_not_ready'):raise
            raise DomainError('incomplete_record',422) from None
        except (ValueError,KeyError,TypeError,AttributeError,OverflowError,RecursionError):raise DomainError('incomplete_record',422) from None

    def seed(self,actor,sid,rid):
        history,payload,_=self.retained(actor,sid,rid);config=history['configuration'];study=self.store.study(actor,sid)
        changed=context_changed(config['context_snapshot'],study);inputs=[]
        for item in config['inputs']:
            binding=item.get('result_binding')
            if binding:
                inputs.append(dict(kind='run_result',target=deepcopy(item['target']),source_run_id=binding['source_run_id'],
                    source_output=deepcopy(binding['source_output']),expected_results_digest=binding['results_digest'],provenance=deepcopy(item['provenance'])))
            else:inputs.append(dict(kind='literal',**{k:deepcopy(item[k]) for k in ('target','value','units','provenance')}))
        request=dict(schema_version='2',study_id=sid,model_id=config['model_id'],model_revision_id=config['model_revision_id'],name=config['name'],
            inputs=inputs,criteria=deepcopy(config['criteria']),numerical=deepcopy(config['numerical']),notes=deepcopy(config['context_snapshot']['notes']),
            evidence_version_ids=[s['evidence_version_id'] for s in config['evidence_snapshots']],
            context_source=dict(kind='source_run',source_run_id=rid,source_configuration_digest=config['digest'],observed_study_revision=study['revision'],choice_confirmed=not changed),
            derivation=dict(source_run_id=rid,source_configuration_digest=config['digest']))
        source_runtime=runtime_identity(payload['bundle']['manifest']['runtime'])
        if config['schema_version'] in ('3','4'):
            request['schema_version']=config['schema_version']
            request.pop('evidence_version_ids')
            request.update(assumptions=deepcopy(config['assumptions']),
                general_context_evidence_version_ids=deepcopy(config['general_context_evidence_version_ids']))
        value=dict(schema_version='1',source_run_id=rid,source_configuration_digest=config['digest'],model_snapshot=deepcopy(history['model_snapshot']),configuration=request,
            source_context=deepcopy(config['context_snapshot']),current_context=dict(description=study['description'],boundary=study['boundary'],notes=deepcopy(request['notes'])),
            current_study_revision=study['revision'],context_changed=changed,requires_context_choice=changed,source_runtime=source_runtime,
            runtime_comparison=runtime_comparison(self.store,actor,sid,source_runtime))
        if config['schema_version']=='3':value['schema_version']='2'
        elif config['schema_version']=='4':
            pin=config['approach_binding']
            request.update(approach_selection={k:pin[k] for k in ('approach_version_id','case_id')} if pin else None,
                context_override=dict(schema_version='1',**{k:config['context_snapshot'][k] for k in ('description','boundary')}))
            value.update(schema_version={'3':'3','4':'4','6':'6'}[history['history_schema_version']],source_configuration=deepcopy(config),approach_closure=deepcopy(history['approach_closure']))
        validate('ModifiedRunSeed'+value['schema_version'],value)
        return value

    def authoring(self,actor,sid,request,study):
        origin=request['derivation'];record=self.retained(actor,sid,origin['source_run_id']);config=record[0]['configuration']
        if config['schema_version']=='4' and request['schema_version']!='4':
            raise DomainError('invalid_configuration',422,fields=[dict(path='/schema_version',code='invalid',
                message='Use configuration version 4 and explicitly keep, change or remove the approach selection.',element_ref=None)])
        if origin['source_configuration_digest']!=config['digest']:raise DomainError('reference_conflict',409)
        if request['model_id']!=config['model_id'] or request['model_revision_id']!=config['model_revision_id']:
            raise DomainError('reference_conflict',409,fields=[dict(path='/model_revision_id',code='invalid',
                message='A modified run retains its source model version. Create a new configuration to use a different model version and select its compatible approach.',element_ref=None)])
        selection=request['context_source']
        if selection['kind']=='source_run':
            if any(selection[k]!=origin[k] for k in ('source_run_id','source_configuration_digest')):raise DomainError('reference_conflict',409)
            self.store.cas(study['revision'],selection['observed_study_revision'])
            if context_changed(config['context_snapshot'],study) and not selection['choice_confirmed']:raise DomainError('context_choice_required',409)
            context=config['context_snapshot']
        else:
            self.store.cas(study['revision'],selection['expected_study_revision']);context=study
        return record,dict(description=context['description'],boundary=context['boundary'],notes=deepcopy(request['notes']))
