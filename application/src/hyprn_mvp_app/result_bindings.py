"""Authorized retained scalar sources; no model client or native access in web.

The native resolver is injected only by the owned executor, after retained app
authority checks. Its response is evidence to verify, never new source authority.
"""
import base64
from copy import deepcopy
import json

from .history import History, complete_outcome, last_run_position, runs_by_position
from .contracts import DomainError, canonical, check_digest, digest, validate
from .execution_bundle import finite, port_key
# Temporary forwarding alias for test imports only; production code imports it from its owner
# (application/tests/test_module_boundaries.py).
from .execution_bundle import verify_dependencies
from .units import port_units


class ResultBindings:
    def __init__(self, store):
        self.store = store
        self.history = History(store)

    def retained(self, actor, sid, rid):
        """A finished retained run usable as a scalar source (History owns the reading).

        Eligibility added here: exit 0, at most 1000 unique output targets and, for
        configuration 3/4, a complete recorded outcome. Every refusal is
        ``source_result_unavailable`` 409; authorization, absence, contract and
        concurrent-change errors propagate unchanged.
        """
        try:
            run = self.history.retained(actor, sid, rid)
            config = run.history['configuration']; model = run.history['model_snapshot']; results = run.history['results']
            if config['schema_version'] in ('3','4'):
                # History has verified Bundle4/5's full/private pair and complete
                # closure. Require complete recorded outcomes as well before
                # admitting a new-format source into the scalar picker.
                complete_outcome(results,model,config)
            if (results['execution']['state'] != 'finished' or type(results['execution']['exit_code']) is not int
                    or results['execution']['exit_code'] != 0 or len(results['outputs']) > 1000):
                raise ValueError('Source binding invalid')
            targets = [port_key(o['target']) for o in results['outputs']]
            if len(set(targets)) != len(targets):
                raise ValueError('Ambiguous output')
            return run
        except DomainError as error:
            if error.code == 'record_not_ready':
                raise DomainError('source_result_unavailable', 409) from None
            raise
        except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
            raise DomainError('source_result_unavailable', 409) from None

    def _output(self, rid, history, target):
        results = history['results']; config = history['configuration']; model = history['model_snapshot']
        try:
            output = next(o for o in results['outputs'] if o['target'] == target)
            if (output['availability'] != 'available' or not finite(output['value'])
                    or output.get('assigned') is not True or output.get('producer_completed') is not True):
                raise ValueError('Unavailable scalar')
            instance = next(i for i in model['instances'] if i['instance_id'] == target['instance_id'])
            definition = next(d for d in model['definitions'] if d['definition_version_id'] == instance['definition_version_id'])
            port = next(p for p in definition['ports'] if p['port_id'] == target['port_id'] and p['direction'] == 'output')
            units = port_units(model)[(instance['instance_id'],instance['definition_version_id'],port['port_id'])]
            if units != output['units']:
                raise ValueError('Source units mismatch')
            value = dict(
                source_run_id=rid,
                source_output=deepcopy(target),
                results_digest=digest(results),
                source_configuration_digest=config['digest'],
                value=output['value'],
                units=output['units'],
                labels=dict(
                    run_name=config['name'],
                    model_name=None,
                    model_revision_id=model['model_revision_id'],
                    instance_name=instance['name'],
                    output_name=port['name'],
                ),
                outcomes={k: deepcopy(results[k]) for k in ('execution', 'criteria')},
                native_availability='not_rechecked',
            )
            validate('ResultSource2', value)
            return value
        except (StopIteration, ValueError, KeyError, TypeError, DomainError):
            raise DomainError('source_result_unavailable', 409) from None

    def resolve(self, actor, sid, request, *, records=None):
        rid = request['source_run_id']
        if records is None: records = {}
        if rid not in records: records[rid] = self.retained(actor, sid, rid)
        history = records[rid][0]
        value = self._output(rid, history, request['source_output'])
        if value['results_digest'] != request['expected_results_digest']:
            raise DomainError('reference_conflict', 409)
        return value

    def inventory(self, actor, sid, *, limit=25, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise DomainError('invalid_request', 400)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            maximum = last_run_position(db, sid)
            high, position, offset = maximum, 0, 0
            if cursor is not None:
                try:
                    if not isinstance(cursor,str) or len(cursor)>2048: raise ValueError()
                    token=json.loads(base64.urlsafe_b64decode(cursor.encode()))
                    if set(token) != {'study','actor','limit','high','position','offset','checksum'}:raise ValueError()
                    if token['checksum'] != digest({k:v for k,v in token.items() if k!='checksum'}):raise ValueError()
                    if (token['study'],token['actor'],token['limit']) != (sid,actor,limit):raise ValueError()
                    high,position,offset = (token[k] for k in ('high','position','offset'))
                    if any(type(n) is not int for n in (high,position,offset)) or not 0<=position<=high<=maximum or not 0<=offset<=1000:raise ValueError()
                except (ValueError,TypeError,KeyError,UnicodeError):
                    raise DomainError('invalid_request',400) from None
            rows=runs_by_position(db,sid,position,high,100)
        items=[];next_cursor=None
        for row in rows:
            start=offset if row['rowid']==position else 0
            try:
                history,_,_=self.retained(actor,sid,row['run_id'])
                outputs=sorted(history['results']['outputs'],key=lambda o:port_key(o['target']))
            except DomainError as error:
                if error.status in (403,404):raise
                outputs=[]
            for index in range(start,len(outputs)):
                try:items.append(self._output(row['run_id'],history,outputs[index]['target']))
                except DomainError:continue
                if len(items)==limit:
                    position,offset=(row['rowid'],index+1) if index+1<len(outputs) else (row['rowid']+1,0)
                    break
            else:
                position,offset=row['rowid']+1,0
                continue
            break
        if position<=high and rows:
            token=dict(study=sid,actor=actor,limit=limit,high=high,position=position,offset=offset)
            token['checksum']=digest(token)
            next_cursor=base64.urlsafe_b64encode(canonical(token)).decode()
        return dict(items=items,next_cursor=next_cursor)

    def verify_configuration(self, actor, sid, configuration):
        version=configuration.get('schema_version')
        if version not in ('2','3','4'):raise ValueError('Unsupported result-bound configuration version')
        validate('ConfigurationRevision'+version,configuration)
        check_digest(configuration)
        if len({i['result_binding']['source_run_id'] for i in configuration['inputs'] if i.get('result_binding')})>64:
            raise DomainError('limit_exceeded',413)
        records={}
        for item in configuration['inputs']:
            binding=item.get('result_binding')
            if binding is None:continue
            source=self.resolve(actor,sid,dict(source_run_id=binding['source_run_id'],source_output=binding['source_output'],expected_results_digest=binding['results_digest']),records=records)
            if (item['value']!=source['value'] or item['units']!=source['units']
                    or any(binding[k]!=source[k] for k in ('source_configuration_digest','labels'))
                    or binding['original_value']!=source['value'] or binding['original_units']!=source['units']):
                raise DomainError('reference_conflict',409)
        return records

    def dependencies(self, actor, sid, configuration, native):
        """Resolve exact native sources before bundle assembly, never in the web.

        resolve_results takes a list of {source_run_id,request,association,
        results_digest,outputs:[{target,value,units}]}; returns the identical list
        with result_uuid on each row. The native resolver verifies creator links and values
        against its store; any difference from the request is a reference conflict here.
        """
        records=self.verify_configuration(actor,sid,configuration)
        approved=[]
        for rid,(history,payload,_) in sorted(records.items()):
            targets={port_key(i['result_binding']['source_output']) for i in configuration['inputs'] if i.get('result_binding') and i['result_binding']['source_run_id']==rid}
            approved.append(dict(source_run_id=rid,request=payload['request'],association=payload['history']['association'],results_digest=digest(history['results']),
                outputs=[{k:o[k] for k in ('target','value','units')} for o in sorted(history['results']['outputs'],key=lambda o:port_key(o['target'])) if port_key(o['target']) in targets]))
        try:
            resolved=native.resolve_results(deepcopy(approved)) if approved else []
        except (ValueError,KeyError,TypeError,AttributeError):
            raise DomainError('source_result_unavailable',409) from None
        if not isinstance(resolved,list) or len(resolved)!=len(approved):raise DomainError('reference_conflict',409)
        sources=[];by_run={};seen={}
        for wanted,actual in zip(approved,resolved):
            if not isinstance(actual,dict) or set(actual)!=set(wanted)|{'result_uuid'} or canonical({k:v for k,v in actual.items() if k!='result_uuid'})!=canonical(wanted):
                raise DomainError('reference_conflict',409)
            source={k:actual[k] for k in ('source_run_id','request','association','results_digest','result_uuid')}
            source['label']='r'+str(source['result_uuid']).replace('-','')
            validate('NativeSource',source)
            key=(source['association']['store_uuid'],source['result_uuid'])
            if key in seen and seen[key]!=source:raise DomainError('reference_conflict',409)
            if key not in seen:sources.append(source);seen[key]=source
            by_run[source['source_run_id']]=source
        mappings=[]
        for item in configuration['inputs']:
            binding=item.get('result_binding')
            if binding:
                mappings.append(dict(target=item['target'],source_label=by_run[binding['source_run_id']]['label'],
                    **{k:binding[k] for k in ('source_output','results_digest','original_value','original_units','conversion')}))
        result=dict(schema_version='1',sources=sorted(sources,key=lambda s:s['label']),mappings=sorted(mappings,key=lambda m:port_key(m['target'])))
        validate('ResultDependencies1',result)
        return result
