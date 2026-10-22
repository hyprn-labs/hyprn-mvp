"""Durable data-only computational records. Native archive authority is injected.

No native imports, model clients, scientific submission, or current-model reads.
A request-owned artifact is published only after closure and inventory checks.
"""
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
from uuid import UUID
import zipfile
from datetime import datetime

from .contracts import DomainError, canonical, data_json, digest, uid, validate
from .execution_bundle import result_history_version, validate_assumption_closure
from .history import History, complete_outcome
from .locations import refuse_location
from .modified_runs import ModifiedRuns
from .result_bindings import ResultBindings

LIMITS = dict(selected_runs=16, computational_runs=64, logical_paths=4096,
    expanded_bytes=33554432, native_archive_bytes=16777216, wrapper_bytes=33554432,
    per_file_bytes=16777216, inventory_bytes=4194304, metadata_bytes=1048576)
OMISSIONS = ['authinfos', 'comments', 'logs', 'process_checkpoints']
PREREQUISITES = dict(retained_material_complete=True, runtime_portability='unverified')
POLICY = 'record-policy-1'
LIMIT_DIAGNOSTICS = {
    'expanded_bytes_limit': dict(path='/selected_run_ids',code='expanded_bytes_limit',
        message='Selected runs and their required records exceed the 32 MiB expanded export limit. Export fewer runs. If one run still exceeds the limit, its complete record cannot currently be exported; required computational ancestors cannot be omitted.',element_ref=None),
    'pending_requests_limit': dict(path='/computational-records',code='pending_requests_limit',
        message='Too many export requests are pending. Wait for an existing request to finish before creating another.',element_ref=None),
}


def export_limit(code):
    return DomainError('limit_exceeded',413,fields=[dict(LIMIT_DIAGNOSTICS[code])])


def safe_export_error(error):
    """Keep only our exact fixed diagnostics, never backend-controlled text."""
    allowed={'resource_not_found','forbidden','reference_conflict','limit_exceeded','incomplete_record','record_not_ready','unsafe_export'}
    if not isinstance(error,DomainError) or error.code not in allowed:
        return DomainError('unsafe_export',422)
    fields=[dict(field) for field in error.fields
            if error.code=='limit_exceeded' and field in LIMIT_DIAGNOSTICS.values()]
    return DomainError(error.code,error.status,fields=fields[:1])


README = b"""# HYPRN MVP computational record

This inspection-only package retains exact scientific snapshots and a native
AiiDA 2.9.3 archive. The originating store UUID is distinct from any inspection
or import store. Derivation-only records provide context, not native roots.

Use AiiDA's archive info --detailed and archive version facilities, or its
read-only archive backend, in an isolated explicit environment. Do not execute
candidate sources or load process classes while inspecting. Future execution
requires independent runtime, dependency, authorization and scientific review;
runtime portability is unverified. Administrative authinfos, comments, logs and
process checkpoints are omitted. Scientific results and diagnostics are retained.
"""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(value):
    if (not isinstance(value, str) or not value or len(value)>512 or '\\' in value
            or value.startswith('/') or len(value.split('/'))>32
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Unsafe record path')
    return unicodedata.normalize('NFC', value).casefold()


def checked_root(path):
    # The one location rule of the application store (synced folders, symbolic links,
    # Windows-mounted drives) applies to the record root beside it.
    return refuse_location(Path(path).absolute(), what='Computational record root')


def records_for_store(store):
    """One server-owned artifact location shared by dispatcher and web reader."""
    if hasattr(store, 'database'):
        if store.artifact_root is None:
            raise ValueError('Hosted computational record root must be configured explicitly')
        return ComputationalRecords(store, checked_root(store.artifact_root))
    return ComputationalRecords(store,checked_root(store.path.parent/'computational-records'))


def context_material(raw):
    """Context-only ancestors do not traverse native policy; inspect their text."""
    text=raw.decode('utf-8')
    secret=r'(?i)(?:-----BEGIN (?:[A-Z ]*PRIVATE KEY)|(?:(?:api|access|auth|session)[_-]?(?:key|token)|password|secret|authorization)\s*[=:]\s*[\x22\x27]?[A-Za-z0-9+/_.-]{8,}|AKIA[A-Z0-9]{16})'
    if '\x00' in text or re.search(secret,text) or re.search(r'(?i)/(?:Users|home|private/tmp)/',text):
        raise ValueError('Unsafe context-only material')


def zip_entries(raw, maximum, *, metadata=False):
    """Bound all declared expansion before reading any compressed payload."""
    if len(raw)>maximum:raise DomainError('limit_exceeded',413)
    z=zipfile.ZipFile(io.BytesIO(raw))
    entries=z.infolist();seen=set();total=0
    if len(entries)>LIMITS['logical_paths']:raise DomainError('limit_exceeded',413)
    for entry in entries:
        key=safe_path(entry.filename);mode=stat.S_IFMT(entry.external_attr>>16)
        if key in seen or entry.is_dir() or entry.flag_bits&1 or mode not in (0,stat.S_IFREG):
            raise ValueError('Unsafe ZIP entry')
        seen.add(key)
        if entry.file_size>LIMITS['per_file_bytes']:raise DomainError('limit_exceeded',413)
        total+=entry.file_size
    if total>LIMITS['expanded_bytes']:raise export_limit('expanded_bytes_limit')
    if metadata:
        if z.getinfo('metadata.json').file_size>LIMITS['metadata_bytes']:raise DomainError('limit_exceeded',413)
    return z,total,len(entries)


def verify_native(response, preflight):
    if len(canonical(response))>64*1024*1024:raise DomainError('limit_exceeded',413)
    validate('ArchiveRecordResponse1',response)
    if response['schema_version']!='1':
        raise ValueError('Native protocol version')
    inventory=response['inventory']
    if len(canonical(inventory))>LIMITS['inventory_bytes']:raise DomainError('limit_exceeded',413)
    if (response['origin_store_uuid']!=preflight['origin_store_uuid']
            or response['inventory_digest']!=digest(inventory) or inventory['omissions']!=OMISSIONS):
        raise ValueError('Native inventory identity')
    raw=base64.b64decode(response['archive_base64'],validate=True)
    if len(raw)!=response['archive_size'] or sha(raw)!=response['archive_sha256']:
        raise ValueError('Native byte identity')
    nodes={n['uuid']:n for n in inventory['nodes']}
    if len(nodes)!=len(inventory['nodes']):raise ValueError('Duplicate native node')
    processes={k for k,n in nodes.items() if n['node_type']=='process.calculation.calcjob.CalcJobNode.'}
    if processes!={c['association']['process_uuid'] for c in preflight['computations']}:
        raise ValueError('Native process scope')
    links=inventory['links']
    if len({canonical(link) for link in links})!=len(links):raise ValueError('Duplicate native link')
    if any(link['source_uuid'] not in nodes or link['target_uuid'] not in nodes for link in links):
        raise ValueError('Native link scope')
    for computation in preflight['computations']:
        process=computation['association']['process_uuid']
        for label,expected,source in [('request',digest(computation['request']),True),('results',computation['results_digest'],False)]:
            matches=[l for l in links if l['label']==label and l['target_uuid' if source else 'source_uuid']==process]
            if len(matches)!=1 or nodes[matches[0]['source_uuid' if source else 'target_uuid']]['attributes_digest']!=expected:
                raise ValueError('Native public identity mapping')
    repositories=inventory['repositories'];seen=set()
    for item in repositories:
        key=(item['node_uuid'],safe_path(item['path']))
        if key in seen or item['node_uuid'] not in nodes:raise ValueError('Native repository scope')
        seen.add(key)
    z,total,count=zip_entries(raw,LIMITS['native_archive_bytes'],metadata=True)
    with z:
        expected={'metadata.json','db.sqlite3'}|{'repo/'+i['sha256'] for i in repositories}
        if set(z.namelist())!=expected:raise ValueError('Unlisted native payload')
        metadata=data_json(z.read('metadata.json'))
        if (set(metadata)!={'export_version','aiida_version','key_format','compression','ctime','creation_parameters'}
                or metadata['export_version']!='main_0001' or metadata['aiida_version']!='2.9.3'
                or metadata['key_format']!='sha256' or metadata['compression']!=6):
            raise ValueError('Unsupported native metadata')
        datetime.fromisoformat(metadata['ctime'])
        rules=dict(input_calc_forward=False,create_backward=True,return_backward=False,
            input_work_forward=False,call_calc_backward=False,call_work_backward=False,
            input_calc_backward=True,create_forward=True,return_forward=True,
            input_work_backward=True,call_calc_forward=True,call_work_forward=True)
        roots=sorted(c['association']['process_uuid'] for c in preflight['computations'] if c['role']=='selected')
        parameters=metadata['creation_parameters']
        # Pinned AiiDA serializes its starting UUID set without an order guarantee.
        # Normalize only this parsed list; duplicates, foreign/missing roots and
        # every other authority field still differ from the exact expected value.
        if isinstance(parameters,dict):
            starting=parameters.get('entities_starting_set')
            if isinstance(starting,dict) and isinstance(starting.get('node'),list):
                values=starting['node']
                if all(isinstance(value,str) for value in values):starting['node']=sorted(values)
        if parameters!=dict(entities_starting_set={'node':roots},
                include_authinfos=False,include_comments=False,include_logs=False,graph_traversal_rules=rules):
            raise ValueError('Native archive traversal authority')
        for item in repositories:
            data=z.read('repo/'+item['sha256'])
            if len(data)!=item['size'] or sha(data)!=item['sha256']:raise ValueError('Native repository bytes')
        # Force SQLite payload CRC verification too. The injected pinned native
        # operation independently reads its exact rows using ArchiveFormatSqlZip.
        if not z.read('db.sqlite3').startswith(b'SQLite format 3\0'):raise ValueError('Native database missing')
    return raw,total,count


def approach_payloads(records):
    """Collect exact saved closures without following a citation into a store."""
    from .approach_closure import KEYS, validate_closure
    from .execution_bundle import validate_approach_binding
    closures={};tables={k:{} for k in KEYS};sid=None
    for history,_,_ in records.values():
        config=history['configuration']
        if config['schema_version']!='4':continue
        closure=history.get('approach_closure')
        validate_approach_binding(config,history['model_snapshot'],closure)
        if closure is None:continue
        if sid is not None and sid!=config['study_id']:raise ValueError('Foreign approach export study')
        sid=config['study_id'];validate_closure(closure,study_id=sid)
        identity=closure['root_approach_version_id'];raw=canonical(closure)
        if identity in closures and closures[identity]!=raw:raise ValueError('Conflicting approach closure')
        closures[identity]=raw
        for table,key in KEYS.items():
            for row in closure[table]:
                identity=row[key];value=canonical(row)
                if identity in tables[table] and tables[table][identity]!=value:raise ValueError('Conflicting approach entity')
                tables[table][identity]=value
    if not closures:return [],None,{}
    if (sum(map(len,tables.values()))>1000 or len(tables['models'])>32 or len(tables['approach_versions'])>64
            or len(tables['configurations'])+len(tables['run_contexts'])>64):raise DomainError('limit_exceeded',413)
    index=[];files={}
    for identity,raw in sorted(closures.items()):
        closure=data_json(raw);path='hyprn-mvp/approaches/'+identity+'.json'
        for model in closure['models']:
            for source in model['source_files']:context_material(base64.b64decode(source['bytes'],validate=True))
        context_material(raw)
        index.append(dict(approach_version_id=identity,approach_digest=closure['root_approach_digest'],closure_digest=closure['digest'],path=path,sha256=sha(raw),size=len(raw)))
        files[path]=raw
    summary=dict(schema_version='1',approach_version_ids=sorted(tables['approach_versions']),basis_configuration_ids=sorted(tables['configurations']),
        basis_run_ids=sorted(tables['run_contexts']),model_count=len(tables['models']),evidence_count=len(tables['evidence']))
    validate('ApproachExportSummary1',summary)
    return index,summary,files


def inspect_record(raw, *, native_inventory=None):
    """Bounded offline wrapper/scientific inspection; never extract or execute.

    The pinned native ArchiveFormat inspector independently supplies its inventory
    when inspecting native rows. Without it, this checks native ZIP bytes/bounds,
    not native SQLite row semantics or authenticity against an external signer.
    """
    from .execution_bundle import validate_retained_bundle,validate_scientific_snapshot
    z,_,_=zip_entries(raw,LIMITS['wrapper_bytes'])
    with z:
        if z.getinfo('manifest.json').file_size>LIMITS['metadata_bytes']:raise DomainError('limit_exceeded',413)
        manifest=data_json(z.read('manifest.json'));version=manifest.get('schema_version')
        if version not in ('1','2'):raise ValueError('Unsupported portable record')
        validate('ComputationalRecordManifest'+version,manifest)
        if manifest['manifest_digest']!=digest({k:v for k,v in manifest.items() if k!='manifest_digest'}):raise ValueError('Portable manifest digest')
        if manifest['limits']!=LIMITS or manifest['omissions']!=OMISSIONS or manifest['reexecution_prerequisites']!=PREREQUISITES:raise ValueError('Portable policy mismatch')
        inventory=manifest['inventory'];paths=[i['path'] for i in inventory]
        if len(set(map(safe_path,paths)))!=len(paths) or paths!=sorted(paths) or set(z.namelist())!={'manifest.json',*paths}:raise ValueError('Portable inventory mismatch')
        files={}
        for item in inventory:
            value=z.read(item['path'])
            if len(value)!=item['size'] or sha(value)!=item['sha256']:raise ValueError('Portable payload identity')
            files[item['path']]=value
    native=files['computations.aiida'];nz,expanded,count=zip_entries(native,LIMITS['native_archive_bytes'],metadata=True)
    with nz:
        for name in nz.namelist():
            value=nz.read(name)
            if name.startswith('repo/'):
                if name!='repo/'+sha(value):raise ValueError('Native repository digest')
            elif name=='db.sqlite3':
                if not value.startswith(b'SQLite format 3\0'):raise ValueError('Native database missing')
            elif name=='metadata.json':
                metadata=data_json(value)
                if metadata['export_version']!='main_0001' or metadata['aiida_version']!='2.9.3':raise ValueError('Unsupported native metadata')
            else:raise ValueError('Undeclared native archive file')
        if not {'metadata.json','db.sqlite3'}<=set(nz.namelist()):raise ValueError('Incomplete native archive')
    if native_inventory is not None and digest(native_inventory)!=manifest['native_inventory_digest']:raise ValueError('Native inventory mismatch')
    if expanded+sum(len(v) for p,v in files.items() if p!='computations.aiida')+len(canonical(manifest))>LIMITS['expanded_bytes'] or count+len(files)+1>LIMITS['logical_paths']:raise DomainError('limit_exceeded',413)
    closures={}
    for item in manifest.get('approaches',[]):
        identity=item['approach_version_id'];path=item['path']
        if identity in closures or path!='hyprn-mvp/approaches/'+identity+'.json':raise ValueError('Duplicate/noncanonical approach index')
        value=files[path];closure=data_json(value)
        if (item['size']!=len(value) or item['sha256']!=sha(value) or item['closure_digest']!=closure['digest']
                or item['approach_digest']!=closure['root_approach_digest'] or identity!=closure['root_approach_version_id']):raise ValueError('Approach payload identity')
        closures[identity]=closure
    records={};roles={};sid=None
    for mapping in manifest['runs']:
        rid=mapping['run_id'];role=mapping['role'];context_only=role=='derivation_context_only'
        if rid in records:raise ValueError('Duplicate run identity')
        prefix='hyprn-mvp/'+('derivations/' if context_only else 'runs/')+rid+'/'
        if data_json(files[prefix+'identity.json'])!=mapping:raise ValueError('Run identity mapping')
        loc=prefix if context_only else prefix+'bundle/'
        config=data_json(files[loc+'configuration.json']);model=data_json(files[loc+'model.json'])
        if sid is not None and sid!=config['study_id']:raise ValueError('Foreign portable study')
        sid=config['study_id'];pin=config.get('approach_binding');closure=closures.get(pin['approach_version_id']) if pin else None
        frozen=dict(configuration=config,model_snapshot=model)
        if config['schema_version']=='4':frozen['approach_closure']=closure
        # The authenticated portable inventory contains raw scientific snapshots,
        # including context-only records, never a full storage envelope.
        validate_scientific_snapshot(frozen)
        if any(mapping[k]!=v for k,v in dict(configuration_revision_id=config['configuration_revision_id'],configuration_digest=config['digest'],model_revision_id=model['model_revision_id']).items()):raise ValueError('Run configuration mapping')
        history=dict(configuration=config,model_snapshot=model,approach_closure=closure)
        if context_only:
            runtime=data_json(files[loc+'runtime.json'])
            payload=dict(bundle=dict(manifest=dict(runtime=runtime)),history={})
        else:
            bundle_manifest=data_json(files[loc+'manifest.json'])
            bundle_files={p[len(loc):]:v for p,v in files.items() if p.startswith(loc) and p!=loc+'manifest.json'}
            if pin and version=='2':bundle_files['approach/closure.json']=canonical(closure)
            request=dict(run_id=rid,bundle_digest=mapping['bundle_digest'])
            validate_retained_bundle(dict(manifest=bundle_manifest,files=bundle_files),request,frozen,raw_snapshot=True)
            result = data_json(files[prefix + 'results.json'])
            validate('RetainedResultsRead3', result)
            result_history_version(bundle_manifest['schema_version'], result['schema_version'])
            if result['run_id']!=rid or result['bundle_digest']!=mapping['bundle_digest'] or digest(result)!=mapping['results_digest']:raise ValueError('Portable result identity')
            complete_outcome(result,model,config)
            history['results']=result
            artifacts=[dict(path=p[len(prefix+'diagnostics/'):],bytes=base64.b64encode(v).decode()) for p,v in files.items() if p.startswith(prefix+'diagnostics/')]
            payload=dict(bundle=dict(manifest=bundle_manifest,files={p:base64.b64encode(v).decode() for p,v in bundle_files.items()}),request=request,history=dict(association=dict(process_uuid=mapping['process_uuid']),artifacts=artifacts))
        records[rid]=(history,payload,None);roles[rid]=role
    for key in ('selected_run_ids','computational_run_ids','derivation_context_run_ids'):
        if manifest[key]!=sorted(set(manifest[key])):raise ValueError('Unordered portable run inventory')
    selected=set(manifest['selected_run_ids']);computations=set();active=set()
    def walk(rid):
        if rid in active:raise ValueError('Computational ancestry cycle')
        if rid in computations:return
        if rid not in records or roles[rid]=='derivation_context_only':raise ValueError('Missing computational ancestor')
        active.add(rid)
        for item in records[rid][0]['configuration']['inputs']:
            binding=item.get('result_binding')
            if binding:
                source=binding['source_run_id'];walk(source);h=records[source][0];r=h['results']
                if binding['source_configuration_digest']!=h['configuration']['digest'] or binding['results_digest']!=digest(r):raise ValueError('Computational ancestor identity')
        active.remove(rid);computations.add(rid)
    for rid in selected:walk(rid)
    contexts=set()
    for rid in computations:
        derivation=records[rid][0]['configuration'].get('derivation')
        if derivation:
            source=derivation['source_run_id'];h,p,_=records[source]
            if source==rid or derivation['source_configuration_revision_id']!=h['configuration']['configuration_revision_id'] or derivation['source_configuration_digest']!=h['configuration']['digest'] or derivation['source_runtime']!=p['bundle']['manifest']['runtime']:raise ValueError('Derivation identity')
            if source not in computations:contexts.add(source)
    if computations!=set(manifest['computational_run_ids']) or contexts!=set(manifest['derivation_context_run_ids']) or set(records)!=computations|contexts:raise ValueError('Portable run scope')
    if roles!={r:'selected' if r in selected else 'computational_ancestor' if r in computations else 'derivation_context_only' for r in records}:raise ValueError('Portable run role')
    indices,summary,_=approach_payloads(records)
    if version=='1' and any(h['configuration']['schema_version']=='4' for h,_,_ in records.values()):raise ValueError('Config4 requires portable2')
    if version=='2' and (indices!=manifest['approaches'] or summary!=manifest['approach_summary']):raise ValueError('Portable approach summary/index mismatch')
    if native_inventory is not None:
        validate('NativeInventory',native_inventory)
        nodes={n['uuid']:n for n in native_inventory['nodes']}
        links=native_inventory['links'];repositories=native_inventory['repositories']
        if len(nodes)!=len(native_inventory['nodes']) or len({canonical(l) for l in links})!=len(links):raise ValueError('Duplicate native identity')
        processes={identity for identity,node in nodes.items() if node['node_type']=='process.calculation.calcjob.CalcJobNode.'}
        if processes!={records[r][1]['history']['association']['process_uuid'] for r in computations}:raise ValueError('Native/wrapper process scope')
        for rid in computations:
            history,payload,_=records[rid];process=payload['history']['association']['process_uuid']
            def linked(label,incoming):
                matches=[l for l in links if l['label']==label and l['target_uuid' if incoming else 'source_uuid']==process and l['type']==('input_calc' if incoming else 'create')]
                if len(matches)!=1:raise ValueError('Native/wrapper required link')
                return matches[0]['source_uuid' if incoming else 'target_uuid']
            result=linked('results',False);folder=linked('frozen_bundle',True)
            if result not in nodes or nodes[result]['attributes_digest']!=digest(history['results']):raise ValueError('Native/wrapper result identity')
            if folder not in nodes or nodes[folder]['node_type']!='data.core.folder.FolderData.':raise ValueError('Native/wrapper frozen identity')
            rows=[item for item in repositories if item['node_uuid']==folder]
            actual={item['path']:(item['size'],item['sha256']) for item in rows}
            original={p:base64.b64decode(v,validate=True) for p,v in payload['bundle']['files'].items()}
            original['manifest.json']=canonical(payload['bundle']['manifest'])
            expected_files={p:(len(v),sha(v)) for p,v in original.items()}
            if len(rows)!=len(actual) or actual!=expected_files:raise ValueError('Native/wrapper frozen bytes')
    expected,mappings,expected_inventory,_=ComputationalRecords._package(None,records,roles,{},native,expanded,count)
    if mappings!=manifest['runs'] or expected_inventory!=inventory or {p:v for p,(_,v) in expected.items()}!=files:raise ValueError('Portable declared role/content mismatch')
    return manifest


class ComputationalRecords:
    def __init__(self,store,artifact_root,*,fault=lambda point:None):
        self.store=store;self.root=checked_root(artifact_root);self.fault=fault
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)

    def _row(self,db,actor,sid,rid):
        self.store.authorize(db,actor,sid)
        row=db.execute('SELECT * FROM computational_record_requests WHERE study_id=? AND request_id=?',(sid,rid)).fetchone()
        if row is None:raise DomainError('resource_not_found',404)
        return dict(row)

    def _public(self,row):
        payload=json.loads(row['payload_json'])
        value=dict(schema_version='1',request_id=row['request_id'],kind=row['kind'],state=row['state'],
            selected_run_ids=json.loads(row['selected_ids_json']),
            preview=payload.get('preview') if row['state'] not in ('queued','building') else None,
            error=json.loads(row['error_json']) if row['error_json'] else None,
            download=payload.get('download') if row['state']=='ready' else None)
        if payload.get('schema_version')=='2' or payload.get('preview',{}).get('schema_version')=='2':
            value.update(schema_version='2',approach_summary=payload.get('preview',{}).get('approach_summary') if value['preview'] else None)
        return validate('RecordRequestRead',value)

    def _collect(self,actor,sid,selected):
        """Walk numerical ancestry only; direct derivation parents are context."""
        records={};computations=set();visiting=set();retained_bytes=0
        def retained(rid,*,context_only=False):
            nonlocal retained_bytes
            if rid not in records:
                if len(records)>=128:raise DomainError('limit_exceeded',413)
                records[rid]=ModifiedRuns(self.store).retained(actor,sid,rid)
                history,payload,_=records[rid]
                if context_only:
                    config=history['configuration']
                    retained_bytes+=sum(len(canonical(value)) for value in (config,history['model_snapshot'],
                        config['context_snapshot'],config['evidence_snapshots'],payload['bundle']['manifest']['runtime']))
                else:
                    retained_bytes+=sum(f['size'] for f in payload['bundle']['manifest']['files'])
                    retained_bytes+=sum(f['size'] for f in payload['history']['artifacts'])
                if retained_bytes>LIMITS['expanded_bytes']:raise export_limit('expanded_bytes_limit')
            return records[rid]
        def walk(rid):
            if rid in visiting:raise DomainError('unsafe_export',422)
            if rid in computations:return
            if len(computations)+len(visiting)>=64:raise DomainError('limit_exceeded',413)
            visiting.add(rid);history,_,_=retained(rid)
            for item in history['configuration']['inputs']:
                binding=item.get('result_binding')
                if binding:
                    source=binding['source_run_id'];walk(source)
                    source_config=records[source][0]['configuration']
                    source_result=records[source][0]['results']
                    if (source_result['execution']['state']!='finished' or source_result['execution']['exit_code']!=0
                            or binding['source_configuration_digest']!=source_config['digest']
                            or binding['results_digest']!=digest(source_result)):
                        raise DomainError('reference_conflict',409)
                    ResultBindings(self.store).resolve(actor,sid,dict(source_run_id=source,
                        source_output=binding['source_output'],expected_results_digest=binding['results_digest']),records=records)
            visiting.remove(rid);computations.add(rid)
        for rid in selected:walk(rid)
        for rid in sorted(computations):
            derivation=records[rid][0]['configuration'].get('derivation')
            if derivation:
                parent=derivation['source_run_id']
                if parent==rid:raise DomainError('unsafe_export',422)
                history,_,_=retained(parent,context_only=True)
                if (history['configuration']['digest']!=derivation['source_configuration_digest']
                        or history['configuration']['configuration_revision_id']!=derivation['source_configuration_revision_id']
                        or records[parent][1]['bundle']['manifest']['runtime']!=derivation['source_runtime']):
                    raise DomainError('reference_conflict',409)
        origins={str(UUID(records[r][1]['history']['association']['store_uuid'])) for r in computations}
        if len(origins)!=1:raise DomainError('incomplete_record',422)
        approved=[];roles={}
        for rid in sorted(records):
            role='selected' if rid in selected else 'computational_ancestor' if rid in computations else 'derivation_context_only'
            roles[rid]=role
            if rid in computations:
                h,p,_=records[rid]
                approved.append(dict(run_id=rid,request=p['request'],association=p['history']['association'],results_digest=digest(h['results']),role=role))
        preflight=dict(schema_version='1',study_id=sid,origin_store_uuid=origins.pop(),roots=selected,
            computations=approved,policy_version=POLICY)
        validate('ArchiveRecordRequest1',preflight)
        stable=dict(roles=roles,records={r:dict(frozen=p['frozen'],bundle=p['bundle'],history=p['history'])
            for r,(_,p,_) in sorted(records.items())})
        return records,roles,preflight,stable

    def _enqueue(self,actor,sid,kind,body,selected,preview_id=None,expected=None):
        category='computational_record_'+kind
        payload={k:v for k,v in body.items() if k!='command_id'}
        old=self.store.replay(actor,sid,category,body['command_id'],payload)
        if old:
            self._collect(actor,sid,old['result']['selected_run_ids'])
            return old['result']
        records,_,_,_=self._collect(actor,sid,selected)
        modern=any(h['configuration']['schema_version']=='4' for h,_,_ in records.values())
        def apply(db):
            History(self.store).recheck(db,actor,sid,[r[2] for r in records.values()])
            pending=db.execute("SELECT COUNT(*),SUM(study_id=?) FROM computational_record_requests WHERE state IN ('queued','building')",(sid,)).fetchone()
            if pending[0]>=32 or (pending[1] or 0)>=8:raise export_limit('pending_requests_limit')
            if preview_id:
                previous=self._row(db,actor,sid,preview_id)
                if previous['kind']!='preview' or previous['state']!='reviewable':raise DomainError('record_not_ready',409)
                if json.loads(previous['payload_json'])['preview']['preview_digest']!=expected:raise DomainError('reference_conflict',409)
            rid=uid()
            db.execute('INSERT INTO computational_record_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (rid,sid,actor,kind,body['command_id'],digest(payload),json.dumps(selected),preview_id,expected,'queued',0,json.dumps(dict(schema_version='2')) if modern else '{}',None,None,None))
            return self._public(self._row(db,actor,sid,rid))
        return self.store.command(actor,sid,category,body['command_id'],payload,apply,
            attribute=lambda saved:[('computational_record',saved['request_id'],None)])

    def enqueue_preview(self,actor,sid,body):
        validate('RecordPreviewRequest',body)
        selected=sorted(body['selected_run_ids'])
        return self._enqueue(actor,sid,'preview',body,selected)

    def enqueue_create(self,actor,sid,body):
        validate('RecordCreateRequest',body)
        # Replay before resolving a changed/missing preview, preserving command identity.
        payload={k:v for k,v in body.items() if k!='command_id'}
        old=self.store.replay(actor,sid,'computational_record_create',body['command_id'],payload)
        if old:
            self._collect(actor,sid,old['result']['selected_run_ids'])
            return old['result']
        with self.store.connection() as db:previous=self._row(db,actor,sid,body['preview_id'])
        if previous['kind']!='preview' or previous['state']!='reviewable':raise DomainError('record_not_ready',409)
        if json.loads(previous['payload_json'])['preview']['preview_digest']!=body['expected_preview_digest']:raise DomainError('reference_conflict',409)
        self._read_artifact(previous,LIMITS['native_archive_bytes'])
        return self._enqueue(actor,sid,'create',body,json.loads(previous['selected_ids_json']),body['preview_id'],body['expected_preview_digest'])

    def status(self,actor,sid,rid):
        with self.store.connection() as db:row=self._row(db,actor,sid,rid)
        if row['state']!='failed':
            _,_,_,stable=self._collect(actor,sid,json.loads(row['selected_ids_json']))
            expected=json.loads(row['payload_json']).get('app_digest')
            if expected and digest(stable)!=expected:raise DomainError('reference_conflict',409)
        return self._public(row)

    def _path(self,rid,name):
        if str(UUID(rid))!=rid:raise ValueError('Server request identity required')
        checked_root(self.root)
        directory=checked_root(self.root/rid)
        directory.mkdir(mode=0o700,exist_ok=True)
        path=directory/name
        if path.is_symlink():raise ValueError('Owned artifact required')
        return path

    def _read_artifact(self,row,maximum):
        expected=self._path(row['request_id'],'record.zip' if row['kind']=='create' else 'preview.aiida')
        if row['artifact_path']!=str(expected):raise DomainError('incomplete_record',422)
        try:
            fd=os.open(expected,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError()
                raw=stream.read(maximum+1)
            if len(raw)>maximum or sha(raw)!=row['artifact_sha256']:raise ValueError()
            return raw
        except (OSError,ValueError):raise DomainError('incomplete_record',422) from None

    def download(self,actor,sid,rid):
        value=self.status(actor,sid,rid)
        if value['kind']!='create' or value['state']!='ready':raise DomainError('record_not_ready',409)
        with self.store.connection() as db:row=self._row(db,actor,sid,rid)
        raw=self._read_artifact(row,LIMITS['wrapper_bytes'])
        # Authorization and exact retained records are checked again after file I/O.
        self.status(actor,sid,rid)
        return raw

    def _package(self,records,roles,preflight,native,expanded,count):
        files={};mapping=[];total=expanded
        indices,summary,approach_files=approach_payloads(records)
        def put(path,role,raw):
            nonlocal total
            if len(raw)>LIMITS['per_file_bytes']:raise DomainError('limit_exceeded',413)
            if path in files:raise ValueError('Duplicate wrapper path')
            if role!='native_archive':total+=len(raw)
            if total>LIMITS['expanded_bytes']:raise export_limit('expanded_bytes_limit')
            if len(files)+2+count>LIMITS['logical_paths']:raise DomainError('limit_exceeded',413)
            files[path]=(role,raw)
        put('README.md','readme',README);put('computations.aiida','native_archive',native)
        for path,raw in approach_files.items():put(path,'approach',raw)
        for rid,(history,payload,_) in sorted(records.items()):
            config=history['configuration'];role=roles[rid];context_only=role=='derivation_context_only'
            # Check the same retained closure at the packaging boundary, including
            # context-only parents which are intentionally outside native roots.
            # Never resolve an evidence family head or today's resource labels.
            if config['schema_version'] in ('3','4'):
                validate_assumption_closure(config,history['model_snapshot'])
            prefix='hyprn-mvp/'+('derivations/' if context_only else 'runs/')+rid+'/'
            entry=dict(run_id=rid,configuration_revision_id=config['configuration_revision_id'],
                model_revision_id=config['model_revision_id'],role=role,configuration_digest=config['digest'],
                process_uuid=None if context_only else payload['history']['association']['process_uuid'],
                bundle_digest=None if context_only else payload['request']['bundle_digest'],
                results_digest=None if context_only else digest(history['results']))
            mapping.append(entry);put(prefix+'identity.json','identity_mapping',canonical(entry))
            if context_only:
                for source in history['model_snapshot']['source_files']:
                    context_material(base64.b64decode(source['bytes'],validate=True))
                for path,file_role,value in [('configuration.json','configuration',config),('model.json','model',history['model_snapshot']),
                        ('context.json','context',config['context_snapshot']),('evidence.json','evidence',config['evidence_snapshots']),
                        ('runtime.json','runtime',payload['bundle']['manifest']['runtime'])]:
                    raw=canonical(value);context_material(raw);put(prefix+path,file_role,raw)
            else:
                notices={item['path'] for item in payload['bundle']['manifest']['licenses']}
                for path,encoded in payload['bundle']['files'].items():
                    if path=='approach/closure.json':continue  # One indexed wrapper payload; native bytes remain exact.
                    role_map={'configuration.json':'configuration','model.json':'model','context.json':'context'}
                    first=path.split('/')[0]
                    file_role=role_map.get(path,{'sources':'source','generated':'generated','evidence':'evidence','licenses':'license'}.get(first,'runtime'))
                    if path in notices:file_role='license'
                    put(prefix+'bundle/'+path,file_role,base64.b64decode(encoded,validate=True))
                put(prefix+'bundle/manifest.json','identity_mapping',canonical(payload['bundle']['manifest']))
                put(prefix+'results.json','results',canonical(history['results']))
                for item in payload['history']['artifacts']:
                    put(prefix+'diagnostics/'+item['path'],'diagnostics',base64.b64decode(item['bytes'],validate=True))
        keys=[safe_path(p) for p in files]
        if len(set(keys))!=len(keys):raise ValueError('Wrapper path collision')
        if len(files)+1+count>LIMITS['logical_paths']:raise DomainError('limit_exceeded',413)
        inventory=[dict(path=p,role=r,size=len(raw),sha256=sha(raw)) for p,(r,raw) in sorted(files.items())]
        if len(canonical(inventory))>LIMITS['inventory_bytes']:raise DomainError('limit_exceeded',413)
        return files,mapping,inventory,expanded

    def _build(self,row,archive_record):
        actor,sid=row['actor_id'],row['study_id'];selected=json.loads(row['selected_ids_json'])
        records,roles,preflight,stable=self._collect(actor,sid,selected)
        response=archive_record(preflight)
        native,expanded,count=verify_native(response,preflight)
        files,mapping,inventory,_=self._package(records,roles,preflight,native,expanded,count)
        # Archive creation timestamps/ZIP encoding are deliberately excluded from
        # stable review identity. Exact native inventory remains fully bound.
        stable_inventory=[i for i in inventory if i['role']!='native_archive']
        identity=dict(app=stable,native_inventory=response['inventory'],payload_inventory=stable_inventory,
            roots=selected,policy=POLICY,limits=LIMITS)
        review_digest=digest(identity)
        def labels(kind):
            return [dict(run_id=r,name=records[r][0]['configuration']['name'],model_revision_id=records[r][0]['configuration']['model_revision_id'])
                for r in sorted(records) if roles[r]==kind]
        preview=dict(preview_digest=review_digest,selected=labels('selected'),computational_ancestors=labels('computational_ancestor'),
            derivation_context_only=labels('derivation_context_only'),context_count=len(records),
            evidence_count=len({s['evidence_version_id'] for h,_,_ in records.values() for s in h['configuration']['evidence_snapshots']}),
            inventory_digest=digest(dict(native=response['inventory'],payload=stable_inventory)),limits=LIMITS,omissions=OMISSIONS,
            classification='inspection_only',reexecution_prerequisites=PREREQUISITES,blockers=[])
        modern=any(h['configuration']['schema_version']=='4' for h,_,_ in records.values())
        approaches,summary,_=approach_payloads(records)
        if modern:preview.update(schema_version='2',approach_summary=summary)
        validate('RecordPreviewRead',preview)
        manifest=dict(schema_version='1',kind='hyprn-mvp-computational-record',origin_store_uuid=preflight['origin_store_uuid'],
            selected_run_ids=selected,computational_run_ids=sorted(r for r in roles if roles[r]!='derivation_context_only'),
            derivation_context_run_ids=sorted(r for r in roles if roles[r]=='derivation_context_only'),runs=mapping,inventory=inventory,
            native_inventory_digest=response['inventory_digest'],omissions=OMISSIONS,classification='inspection_only',
            reexecution_prerequisites=PREREQUISITES,limits=LIMITS)
        if modern:manifest.update(schema_version='2',approach_summary=summary,approaches=approaches)
        manifest['manifest_digest']=digest(manifest);validate('ComputationalRecordManifest'+manifest['schema_version'],manifest)
        manifest_raw=canonical(manifest)
        if len(manifest_raw)>LIMITS['metadata_bytes']:raise DomainError('limit_exceeded',413)
        if expanded+len(manifest_raw)+sum(len(v) for p,(_,v) in files.items() if p!='computations.aiida')>LIMITS['expanded_bytes']:
            raise export_limit('expanded_bytes_limit')
        if row['kind']=='create' and review_digest!=row['expected_preview_digest']:raise DomainError('reference_conflict',409)
        if row['kind']=='preview':raw=native
        else:
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for path,value in sorted({'manifest.json':manifest_raw,**{p:v for p,(_,v) in files.items()}}.items()):
                    info=zipfile.ZipInfo(path);info.external_attr=(stat.S_IFREG|0o400)<<16
                    z.writestr(info,value,compress_type=zipfile.ZIP_DEFLATED)
            raw=stream.getvalue()
            z,_,_=zip_entries(raw,LIMITS['wrapper_bytes'])
            with z:
                if set(z.namelist())!={'manifest.json'}|set(files):raise ValueError('Wrapper inventory mismatch')
                for item in inventory:
                    value=z.read(item['path'])
                    if sha(value)!=item['sha256'] or len(value)!=item['size']:raise ValueError('Wrapper readback mismatch')
                if z.read('manifest.json')!=manifest_raw:raise ValueError('Manifest readback mismatch')
            inspect_record(raw,native_inventory=response['inventory'])
        return raw,preview,digest(stable),records

    def process_one(self,archive_record,request_id=None):
        with self.store.background_actor('export', request_id) as admitted:
            return self._process_one(archive_record, request_id) if admitted else False

    def _process_one(self,archive_record,request_id=None):
        """One bounded item under the artifact-root owned lock; no native defaults."""
        checked_root(self.root)
        fd=os.open(self.root/'owner.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a+b') as owner:
            try:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return False
            with self.store.connection(write=True) as db:
                query="SELECT * FROM computational_record_requests WHERE state IN ('queued','building')"
                params=()
                if request_id is not None:query+=' AND request_id=?';params=(request_id,)
                found=db.execute(query+' ORDER BY rowid LIMIT 1',params).fetchone()
                if found is None:return False
                row=dict(found);row['generation']+=1;row['state']='building'
                db.execute("UPDATE computational_record_requests SET state='building',generation=? WHERE request_id=?",(row['generation'],row['request_id']))
            try:
                self.fault('claimed')
                raw,preview,app_digest,records=self._build(row,archive_record)
                previous=json.loads(row['payload_json']).get('preview')
                if previous and previous['preview_digest']!=preview['preview_digest']:
                    raise DomainError('reference_conflict',409)
                with self.store.connection(write=True) as db:
                    cursor=db.execute("UPDATE computational_record_requests SET payload_json=? WHERE request_id=? AND state='building' AND generation=?",
                        (json.dumps(dict(preview=preview,app_digest=app_digest)),row['request_id'],row['generation']))
                    if cursor.rowcount!=1:raise DomainError('reference_conflict',409)
                self.fault('built')
                path=self._path(row['request_id'],'record.zip' if row['kind']=='create' else 'preview.aiida')
                temporary=self._path(row['request_id'],'incomplete.tmp')
                # Restart discards only this request's known incomplete file.
                if temporary.exists():temporary.unlink()
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                self.fault('written')
                # Re-collect permissions/evidence/history after native and file I/O.
                _,_,_,current=self._collect(row['actor_id'],row['study_id'],json.loads(row['selected_ids_json']))
                if digest(current)!=app_digest:raise DomainError('reference_conflict',409)
                os.chmod(temporary,0o400);os.replace(temporary,path)
                directory=os.open(path.parent,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
                self.fault('published')
                row.update(artifact_path=str(path),artifact_sha256=sha(raw))
                self._read_artifact(row,LIMITS['wrapper_bytes'])
                payload=dict(preview=preview,app_digest=app_digest,download=dict(sha256=sha(raw),size=len(raw)) if row['kind']=='create' else None)
                with self.store.connection(write=True) as db:
                    History(self.store).recheck(db,row['actor_id'],row['study_id'],[r[2] for r in records.values()])
                    cursor=db.execute("UPDATE computational_record_requests SET state=?,payload_json=?,error_json=NULL,artifact_path=?,artifact_sha256=? WHERE request_id=? AND state='building' AND generation=?",
                        ('ready' if row['kind']=='create' else 'reviewable',json.dumps(payload),str(path),sha(raw),row['request_id'],row['generation']))
                    if cursor.rowcount!=1:raise DomainError('reference_conflict',409)
                return True
            except Exception as error:
                # Never persist a native/backend exception message, row, or path.
                safe=safe_export_error(error)
                with self.store.connection(write=True) as db:
                    db.execute("UPDATE computational_record_requests SET state='failed',error_json=?,artifact_path=NULL,artifact_sha256=NULL WHERE request_id=? AND state='building' AND generation=?",
                        (json.dumps(safe.data()),row['request_id'],row['generation']))
                return True
