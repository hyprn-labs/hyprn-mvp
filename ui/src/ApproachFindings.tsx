import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, HyprnMvpApi, accessDenied, accessLostText, type ReadFailure, type ReadFence } from './api';
import { useAccessLoss } from './accessLoss';
import type { FrozenConfigurationRead7, ApproachSavedRead3, ApproachUsage1, ApproachUsageCursor1, PublicRunDetail, ResolvedInput2, ResultBinding } from './contract';
import { ActionDialog, Button, DataTable, Disclosure, Panel, Readout, Select, StatusTag } from './design';
import { ApproachCaseContext } from './ApproachAssumptions';
import { RunOutcomes, runOutcomes } from './runStatus';
import { criterionOperators } from './criterionLabels';
import { resolvedUnit, unitLabel } from './unitLabels';
import type { WorkspaceLink } from './workspaceModel';

type Configuration = NonNullable<NonNullable<PublicRunDetail['history']>['configuration']>;
type Row = { usage: ApproachUsage1; configuration?: Configuration; run?: PublicRunDetail; loading?: boolean; error?: string };
type SourceRead = { state: 'loading' | 'error' | 'ready'; run?: PublicRunDetail };
const identity = (usage: ApproachUsage1) => usage.kind + '/' + (usage.kind === 'run' ? usage.run_id : usage.configuration_revision_id);
const sameTarget = (a: {instance_id:string;port_id:string}, b: {instance_id:string;port_id:string}) => a.instance_id === b.instance_id && a.port_id === b.port_id;

/** Equality uses retained numbers and the selected model, never display labels,
 * current model heads, browser digests, or conversion arithmetic. */
export function sourceMatch(input: ResolvedInput2, source: PublicRunDetail): 'verified' | 'unavailable' | 'mismatch' {
  const binding = input.result_binding, history = source.history;
  if (!binding || source.retained_integrity?.schema_version !== '1' || !source.retained_integrity.results_digest || !history?.configuration || !history.model_snapshot || !history.results) return 'unavailable';
  const outputs = history.results.outputs.filter(output => sameTarget(output.target, binding.source_output));
  const instances = history.model_snapshot.instances.filter(instance => instance.instance_id === binding.source_output.instance_id);
  const definitions = history.model_snapshot.definitions.filter(definition => definition.definition_version_id === instances[0]?.definition_version_id);
  const ports = definitions.flatMap(definition => definition.ports.filter(port => port.port_id === binding.source_output.port_id && port.direction === 'output'));
  const output = outputs[0];
  return source.run_id === binding.source_run_id && history.results.run_id === binding.source_run_id &&
    source.retained_integrity.results_digest === binding.results_digest && history.configuration.digest === binding.source_configuration_digest &&
    outputs.length === 1 && instances.length === 1 && definitions.length === 1 && ports.length === 1 &&
    output.availability === 'available' && output.assigned && output.producer_completed && output.value !== null && Number.isFinite(output.value) &&
    output.value === binding.original_value && output.units === binding.original_units && ports[0].units != null && resolvedUnit(ports[0].units) !== undefined && resolvedUnit(ports[0].units) === output.units &&
    input.value === binding.original_value && input.units === binding.original_units && Number.isFinite(input.value)
    ? 'verified' : 'mismatch';
}

export function groupFindings(saved: ApproachSavedRead3, rows: Row[], caseId: string) {
  return [...saved.version.content.cases.filter(item => !caseId || item.case_id === caseId).map(item => ({id:item.case_id,title:item.title,item,rows:rows.filter(row => row.usage.case_id === item.case_id)})),
    ...(!caseId ? [{id:'none',title:'No specific case',item:null,rows:rows.filter(row => row.usage.case_id === null)}] : [])];
}

/** One shared queue persists across review generations. Stale queued work is
 * discarded; already-started transport occupies its slot until it settles. */
class ReadQueue {
  private active = 0;
  private pending: Array<() => void> = [];
  read<T>(valid: () => boolean, fetch: () => Promise<T>): Promise<T | undefined> {
    return new Promise((resolve,reject) => {
      this.pending.push(() => {
        if (!valid()) { resolve(undefined); this.pump(); return; }
        this.active++;
        fetch().then(resolve,reject).finally(() => { this.active--; this.pump(); });
      });
      this.pump();
    });
  }
  private pump() { while (this.active < 2 && this.pending.length) this.pending.shift()!(); }
}

const queues = new WeakMap<HyprnMvpApi,ReadQueue>();
function queueFor(api:HyprnMvpApi){let queue=queues.get(api);if(!queue){queue=new ReadQueue();queues.set(api,queue);}return queue;}

function RunFacets({run}:{run:PublicRunDetail}) {
  const results=run.history?.results;
  if (!results) return <p>{['accepted_run','prepared','dispatching'].includes(run.state) ? 'Not yet available' : 'Results unavailable'}</p>;
  // Execution and Criteria only; a failure keeps its bounded diagnostic beside Execution.
  return <><RunOutcomes variant="ledger" outcomes={runOutcomes(run)} executionDetail={results.execution.state==='failed'?results.execution.message:undefined}/><ul aria-label="Individual criterion outcomes">{results.criteria.map((item,index)=><li key={item.criterion_id}><StatusTag tone={item.outcome==='met'?'ok':item.outcome==='violated'?'alarm':'advisory'}>{item.outcome==='met'?'Met':item.outcome==='violated'?'Not met':'Not evaluated'}</StatusTag> · Criterion {index+1} · {item.reason.replaceAll('_',' ')}</li>)}</ul></>;
}

function RecordedOutputs({run}:{run:PublicRunDetail}) {
  const [all,setAll]=useState(false),outputs=run.history?.results?.outputs??[];
  const name=(target:{instance_id:string;port_id:string})=>{
    const model=run.history?.model_snapshot,instance=model?.instances.find(item=>item.instance_id===target.instance_id),port=model?.definitions.find(item=>item.definition_version_id===instance?.definition_version_id)?.ports.find(item=>item.port_id===target.port_id);
    return instance&&port?`${instance.name} · ${port.name}`:`${target.instance_id} / ${target.port_id}`;
  };
  return <><div className="section-actions"><h4>Outputs</h4><ActionDialog title="Full-precision values" label="Full-precision values"><DataTable regionLabel="Full-precision output values"><thead><tr><th>Output</th><th>Value</th><th>Units</th></tr></thead><tbody>{outputs.map((output,index)=><tr key={index}><td>{name(output.target)}</td><td>{output.availability==='available'&&output.value!==null&&Number.isFinite(output.value)?String(output.value):'not computed'}</td><td>{unitLabel(output.units)}</td></tr>)}</tbody></DataTable></ActionDialog></div><div className="run-key-outputs">{(all?outputs:outputs.slice(0,4)).map((output,index)=><div key={index}><Readout size="sm" label={name(output.target)} value={output.availability==='available'&&output.value!==null&&Number.isFinite(output.value)?output.value:null} unit={unitLabel(output.units)}/>{output.reason&&<p>{output.availability} · {output.reason}</p>}</div>)}</div>{outputs.length>4&&<Button aria-expanded={all} onClick={()=>setAll(value=>!value)}>{all?'Show fewer outputs':`Show all ${outputs.length} outputs`}</Button>}</>;
}

function SourceInputs({configuration,sources,load,onOpen}:{configuration:Configuration;sources:Map<string,SourceRead>;load:(ids:string[],retry?:boolean)=>void;onOpen:(runId:string)=>void}) {
  const [open,setOpen]=useState(false);
  const inputs=configuration.inputs.flatMap(input=>'result_binding' in input&&input.result_binding?[input]:[]);
  const ids=[...new Set(inputs.map(input=>input.result_binding!.source_run_id))];
  const checked=ids.filter(id=>sources.get(id)?.state==='ready').length,missing=ids.filter(id=>!sources.has(id)),failed=ids.filter(id=>sources.get(id)?.state==='error'),busy=ids.some(id=>sources.get(id)?.state==='loading');
  if(!inputs.length)return null;
  return <section aria-label="Source-linked inputs"><Button aria-expanded={open} onClick={()=>setOpen(value=>!value)}>Review source-linked inputs</Button>{open&&<><p role="status">{checked} / {ids.length} source runs checked / referenced{busy?' · Loading upstream qualifications…':''}</p>{checked===0&&<p>Upstream qualifications not loaded</p>}<p>These qualifications belong to the source runs; they do not change the outcomes shown here.</p><div className="section-actions">{!!missing.length&&<Button disabled={busy} onClick={()=>load(missing)}>{checked||failed.length?'Load more source runs':'Load upstream qualifications'}</Button>}{!!failed.length&&<Button disabled={busy} onClick={()=>load(failed,true)}>Retry upstream read</Button>}</div>{inputs.map((input,index)=>{
    const binding:ResultBinding=input.result_binding!,read=sources.get(binding.source_run_id),match=read?.run?sourceMatch(input,read.run):undefined;
    return <article className="approach-case" key={index}><h4>Source-linked input {index+1}</h4><p>Source output {binding.labels.instance_name} · {binding.labels.output_name}</p><p>Original {String(binding.original_value)} {unitLabel(binding.original_units)}</p><p>Conversion: {unitLabel(binding.conversion.source_units)} → {unitLabel(binding.conversion.destination_units)} · factor {String(binding.conversion.factor)} · received {String(binding.conversion.destination_value)} {unitLabel(binding.conversion.destination_units)}</p>{!read?<p>Not loaded</p>:read.state==='loading'?<p role="status">Loading upstream qualifications…</p>:read.state==='error'||match==='unavailable'?<p role="alert">Upstream record unavailable</p>:match==='mismatch'?<p role="alert">Source binding mismatch</p>:read.run&&<><StatusTag tone="inert">Verified source identity</StatusTag><RunFacets run={read.run}/>{read.run.history?.results?.criteria.some(item=>item.outcome==='violated')&&<p>Upstream criterion not met</p>}{read.run.history?.results?.criteria.some(item=>item.outcome==='unresolved')&&<p>Upstream criterion not evaluated</p>}{!!read.run.history?.errors.length&&<p>Source diagnostics: {read.run.history.errors.map(item=>item.code).join(', ')}</p>}</>}<Button onClick={()=>onOpen(binding.source_run_id)}>View upstream run</Button></article>;
  })}</>}</section>;
}

/** One recorded run (or a configuration without a loaded run) inside its case card: name and
 * short id, the shared Execution · Criteria outcomes, the exact criterion facts, and on demand
 * the run's details and source-linked inputs. Recorded facts only; never a verdict. */
function FindingRow({row,saved,sources,load,retry,onOpen}:{row:Row;saved?:Configuration;sources:Map<string,SourceRead>;load:(ids:string[],retry?:boolean)=>void;retry:()=>void;onOpen:(target:WorkspaceLink)=>void}) {
  // A run without retained history (queued, preparing) is named by its loaded saved configuration.
  const [details,setDetails]=useState(false),{usage,run}=row,configuration=row.configuration??saved;
  const id=usage.kind==='run'?usage.run_id:usage.configuration_revision_id;
  return <article className="approach-finding" aria-label={usage.kind+' '+id}>
    <div className="approach-finding-head"><h4>{configuration?.name??(usage.kind==='run'?'Run':'Configuration')} <span className="approach-finding-id">· {id.slice(0,8)}</span></h4><Button size="sm" onClick={()=>onOpen({view:usage.kind==='run'?'runs':'configurations',...(usage.kind==='run'?{run:usage.run_id}:{configuration:usage.configuration_revision_id})})}>{usage.kind==='run'?'View run':'View configuration'}</Button></div>
    {row.loading&&<p role="status">Loading record…</p>}{row.error&&<><p role="alert">{row.error}</p><Button onClick={retry}>Retry record</Button></>}
    {usage.kind==='configuration'&&configuration&&<p className="context-line">Saved configuration · no run loaded</p>}
    {run&&<><RunOutcomes variant="inline" outcomes={runOutcomes(run)}/>
      {!run.history?.results&&<p className="context-line">{['accepted_run','prepared','dispatching'].includes(run.state)?'Results not yet available':'No results for this run'}</p>}
      <CriterionFacts run={run}/>
      <div className="section-actions approach-finding-actions"><Button size="sm" aria-expanded={details} onClick={()=>setDetails(value=>!value)}>Run details</Button></div>
      {details&&<div className="approach-finding-details"><RunFacets run={run}/>{run.history?.results&&<RecordedOutputs run={run}/>} {!!run.history?.errors.length&&<p>Diagnostics: {run.history.errors.map(item=>item.code).join(', ')}</p>}</div>}</>}
    {configuration&&<SourceInputs configuration={configuration} sources={sources} load={load} onOpen={runId=>onOpen({study:configuration.study_id,view:'runs',run:runId})}/>}
  </article>;
}

type Group = ReturnType<typeof groupFindings>[number];
const plural = (count: number, one: string, many = one + 's') => `${count} ${count === 1 ? one : many}`;
const criterionWord = { met: 'Met', violated: 'Not met', unresolved: 'Not evaluated' } as const;
const criterionTone = { met: 'ok', violated: 'alarm', unresolved: 'advisory' } as const;

/** Exact recorded criterion facts of one loaded run. Each line is a fixed-threshold
 * criterion evaluation from the retained record, never a scientific assessment. */
function CriterionFacts({run}:{run:PublicRunDetail}) {
  const results=run.history?.results,configuration=run.history?.configuration,model=run.history?.model_snapshot;
  if(!results)return null;
  const shown=results.criteria.slice(0,3);
  const portName=(target:{instance_id:string;port_id:string})=>{const instance=model?.instances.find(item=>item.instance_id===target.instance_id),port=model?.definitions.find(item=>item.definition_version_id===instance?.definition_version_id)?.ports.find(item=>item.port_id===target.port_id);return instance&&port?`${instance.name} · ${port.name}`:'Output';};
  return <ul className="approach-result-criteria" aria-label={`Criterion evaluations for run ${run.run_id.slice(0,8)}`}>{shown.map((item,index)=>{
    const declared=configuration?.criteria.find(criterion=>criterion.criterion_id===item.criterion_id);
    const output=declared?results.outputs.find(value=>sameTarget(value.target,declared.target)):undefined;
    const recorded=output&&output.availability==='available'&&output.value!==null&&Number.isFinite(output.value)?`${String(output.value)} ${unitLabel(output.units)}`:'not computed';
    return <li key={item.criterion_id}><StatusTag tone={criterionTone[item.outcome]}>{criterionWord[item.outcome]}</StatusTag> Criterion {index+1}{declared?<> · {portName(declared.target)} {criterionOperators[declared.operator]} {String(declared.threshold)} {unitLabel(declared.units)} · output {recorded}</>:' · criterion definition unavailable'}</li>;
  })}{results.criteria.length>shown.length&&<li>{plural(results.criteria.length-shown.length,'more criterion evaluation')} in this run's details</li>}</ul>;
}

/** One card per case: the case question, its runs and its configurations without a
 * loaded run, honest coverage notes, and "Why this case" (rationale, model version, evidence).
 * Each case appears once on the page. */
function CaseCard({group,complete,cursor,headingId,content,onCreateConfiguration,row}:{group:Group;complete:boolean;cursor:boolean;headingId:string;content:ApproachSavedRead3['version']['content'];onCreateConfiguration?:(caseId:string)=>void;row:(row:Row,saved?:Configuration)=>ReactNode}) {
  const runs=group.rows.filter(row=>row.usage.kind==='run'),loaded=runs.filter(row=>row.run),failed=group.rows.filter(row=>row.error).length,pending=group.rows.filter(row=>row.loading).length;
  const runConfigurations=new Set(runs.map(row=>row.usage.configuration_revision_id));
  // A configuration with a run in this case is named by that run; an unread one stays listed.
  const configurations=group.rows.filter(row=>row.usage.kind==='configuration'&&(!runConfigurations.has(row.usage.configuration_revision_id)||!!row.error));
  const configurationsOnly=group.rows.filter(row=>row.usage.kind==='configuration'&&!runConfigurations.has(row.usage.configuration_revision_id)).length;
  const tag=loaded.length?{tone:'inert' as const,label:plural(loaded.length,'run')+' loaded'}:complete?{tone:'advisory' as const,label:'Not evaluated'}:{tone:'advisory' as const,label:'Coverage incomplete'};
  const item=group.item,binding=item?.binding_id?content.model_bindings.find(b=>b.binding_id===item.binding_id):undefined;
  // Honest coverage notes: what is missing or incomplete is said, never inferred as an outcome.
  const notes=[...(configurationsOnly?[plural(configurationsOnly,'configuration')+' without a loaded run']:[]),...(failed?[plural(failed,'record')+' could not be loaded']:[]),...(pending?[plural(pending,'record')+' loading']:[]),
    ...(!runs.length?[complete?'Not evaluated in the loaded review · no run found for this case':cursor?'No run loaded for this case; more usage is available.':'No run loaded for this case; review coverage is incomplete.']:!complete?['Review coverage is incomplete; more records may exist for this case.']:[])];
  const saved=(id:string)=>group.rows.find(row=>row.usage.kind==='configuration'&&row.usage.configuration_revision_id===id)?.configuration;
  return <article className="approach-case-card" aria-labelledby={headingId}>
    <div className="approach-case-card-head"><div className="approach-case-card-title"><StatusTag tone={tag.tone}>{tag.label}</StatusTag><h3 id={headingId} tabIndex={-1}>{group.title}</h3></div>
      {item&&item.binding_id&&onCreateConfiguration&&<Button aria-label={'Create configuration for '+item.title} onClick={()=>onCreateConfiguration(item.case_id)}>Create configuration</Button>}</div>
    <p className="context-copy approach-case-question">{item?item.question||'Case question not described':'Configurations and runs linked to this approach version without a case.'}</p>
    {!!runs.length&&<div className="approach-case-runs" role="group" aria-label={'Runs · '+group.title}>{runs.map(item=>row(item,saved(item.usage.configuration_revision_id)))}</div>}
    {!!configurations.length&&<div className="approach-case-runs" role="group" aria-label={'Configurations without a loaded run · '+group.title}>{configurations.map(item=>row(item))}</div>}
    {!!notes.length&&<div className="context-line approach-result-coverage">{notes.map(note=><p key={note}>{note}</p>)}</div>}
    {item&&<Disclosure className="approach-case-why"><summary>Why this case</summary><p className="context-copy">{item.rationale||'Rationale not described'}</p><p className="context-line">{binding?'Model version '+binding.model_revision_id.slice(0,8):'Proposed case · no model version selected'}</p><ApproachCaseContext item={item}/></Disclosure>}
  </article>;
}

function RemainingWork({content,headingId,onViewStep}:{content:ApproachSavedRead3['version']['content'];headingId:string;onViewStep?:(stepId:string)=>void}) {
  const steps=content.steps.filter(step=>step.implementation_state!=='linked'||step.remaining_work.trim());
  if(!steps.length)return null;
  return <article className="approach-case-card" aria-labelledby={headingId}>
    <div className="approach-case-card-title"><StatusTag tone="inert">Not computed by this approach</StatusTag><h3 id={headingId} tabIndex={-1}>Remaining method work</h3></div>
    <p className="context-copy">Method steps that are proposed, partially linked or name remaining work. No case coverage is inferred from them.</p>
    <ul className="approach-result-runs">{steps.slice(0,3).map(step=><li key={step.step_id}><p><strong>{step.title||'Untitled step'}</strong> · {step.implementation_state==='proposed'?'Proposed · no model linked':step.implementation_state==='partial'?'Partially linked':'Linked'}</p>{step.remaining_work.trim()&&<p className="context-copy">{step.remaining_work}</p>}</li>)}</ul>
    {steps.length>3&&<p className="context-line">{plural(steps.length-3,'more step')} in Methods</p>}
    {onViewStep&&<Button onClick={()=>onViewStep(steps[0].step_id)}>View remaining method</Button>}
  </article>;
}

/** Live usage is injected only by the saved approach screen. Historical
 * ApproachReader receives its retained closure without this component. */
export function ApproachFindings({api,studyId,saved,onOpen,focusCase,onViewStep,onStudyLimits,onCreateConfiguration}:{api:HyprnMvpApi;studyId:string;saved:ApproachSavedRead3;onOpen:(target:WorkspaceLink)=>void;focusCase?:{id:string;token:number};onViewStep?:(stepId:string)=>void;onStudyLimits?:()=>void;onCreateConfiguration?:(caseId:string)=>void}) {
  const [rows,setRows]=useState<Row[]>([]),[cursor,setCursor]=useState<ApproachUsageCursor1|null>(null),[caseId,setCaseId]=useState(''),[review,setReview]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState(false),[denied,setDenied]=useState(false),[accessUnverified,setAccessUnverified]=useState(false),[sources,setSources]=useState(new Map<string,SourceRead>());
  const [missingCase,setMissingCase]=useState('');
  const generation=useRef(0),queue=useRef(queueFor(api)),cache=useRef(new Map<string,SourceRead>()),failedCursor=useRef<ApproachUsageCursor1|null>(null);
  // Shared session fence for this review: the case filter and refresh generation
  // gate display only; a denial is confirmed against study/actor/session/access.
  const scope=useRef<ReadFence|null>(null);
  const base=useId();
  const actor=api.actor,version=saved.version.approach_version_id;
  const valid=(token:number)=>token===generation.current&&actor===api.actor;
  /** Clear this review. A confirmed denial from any host of this study runs it, and
   * this review's own confirmed denial is signalled so the approach reader clears too. */
  function clearProtected(){generation.current++;cache.current.clear();setSources(new Map());setRows([]);setCursor(null);setLoading(false);setDenied(true);}
  useAccessLoss(api,studyId,change=>{if(change.kind==='access-lost')clearProtected();});
  /** Shared classification with the fence captured when the read started (one
   * in-flight study probe per study and session). A superseded review generation
   * still confirms a denial; only its display updates are dropped. */
  async function failed(e:unknown,token:number,read:ReadFence|null):Promise<ReadFailure>{
    if(!read)return 'stale';
    const outcome=await api.readFailed(e,read);
    if(outcome==='transient'&&valid(token))setAccessUnverified(true);
    return outcome;
  }
  /** A refused source does not disclose its body or erase authorized downstream
   * facts: confirm current study access with the shared probe instead. */
  async function checkStudyAccess(token:number){
    const read=scope.current;if(!read||!valid(token))return;
    const outcome=await api.confirmAccess(read);
    if(!valid(token))return;
    if(outcome==='ok')setAccessUnverified(false);else if(outcome==='transient')setAccessUnverified(true);
  }
  async function detail(usage:ApproachUsage1,token:number){
    if(!valid(token))return;
    const read=scope.current;
    const update=(value:Partial<Row>)=>{if(valid(token))setRows(old=>old.map(row=>identity(row.usage)===identity(usage)?{usage,...value}:row));};
    update({loading:true});
    try {
      const record=await queue.current.read<FrozenConfigurationRead7|PublicRunDetail>(()=>valid(token),()=>usage.kind==='run'?api.run(studyId,usage.run_id):api.configuration(studyId,usage.configuration_revision_id));
      if(!valid(token)||!record)return;
      const run='run_id' in record?record:undefined,configuration='configuration' in record?record.configuration:run?.history?.configuration;
      if(run&&run.run_id!==(usage.kind==='run'?usage.run_id:''))throw new Error('binding');
      if(configuration){const pin='approach_binding' in configuration?configuration.approach_binding:null;
        if(configuration.study_id!==studyId||configuration.configuration_revision_id!==usage.configuration_revision_id||pin?.approach_id!==saved.version.approach_id||pin?.approach_version_id!==version||pin.case_id!==usage.case_id||pin.approach_digest!==saved.version.digest||pin.closure_digest!==saved.closure.digest)throw new Error('binding');
      } else if(!run)throw new Error('binding');
      setAccessUnverified(false);update({configuration:configuration??undefined,run});
    }catch(e){
      const outcome=await failed(e,token,read);
      if(outcome==='access-lost'||outcome==='stale'||!valid(token))return;
      update({error:e instanceof Error&&e.message==='binding'?'Record binding mismatch':'Record unavailable'});
    }
  }
  async function page(next:ApproachUsageCursor1|null,token=generation.current){
    const read=scope.current;
    setLoading(true);setError(false);failedCursor.current=next;
    try{const result=await queue.current.read(()=>valid(token),()=>api.approachUsage(studyId,version,{limit:10,case_id:caseId||null,cursor:next}));
      if(!valid(token)||!result)return;
      if(result.items.some(item=>caseId&&item.case_id!==caseId||item.case_id!==null&&!saved.version.content.cases.some(c=>c.case_id===item.case_id)))throw new Error('binding');
      setRows(old=>{const map=new Map(old.map(row=>[identity(row.usage),row]));for(const usage of result.items)if(!map.has(identity(usage)))map.set(identity(usage),{usage,loading:true});return [...map.values()];});setCursor(result.next_cursor);
      for(const usage of result.items)void detail(usage,token);
    }catch(e){const outcome=await failed(e,token,read);if((outcome==='error'||outcome==='transient')&&valid(token))setError(true);}
    finally{if(valid(token))setLoading(false);}
  }
  function loadSources(ids:string[],retry=false){
    const token=generation.current;
    const batch=[...new Set(ids)].filter(id=>retry?cache.current.get(id)?.state==='error':!cache.current.has(id)).slice(0,10);
    for(const id of batch)cache.current.set(id,{state:'loading'});setSources(new Map(cache.current));
    for(const id of batch)void queue.current.read(()=>valid(token),()=>api.run(studyId,id)).then(run=>{if(valid(token)&&run){setAccessUnverified(false);cache.current.set(id,{state:'ready',run});setSources(new Map(cache.current));}}).catch(async e=>{
      if(!valid(token))return;
      if(accessDenied(e)||e instanceof ApiError&&e.detail.code==='resource_not_found')await checkStudyAccess(token);
      if(valid(token)){cache.current.set(id,{state:'error'});setSources(new Map(cache.current));}
    });
  }
  useLayoutEffect(()=>{const token=++generation.current,read=api.fence({studyId});scope.current=read;setRows([]);setCursor(null);setError(false);setDenied(false);setAccessUnverified(false);cache.current.clear();setSources(new Map());void page(null,token);return()=>{generation.current++;cache.current.clear();read.done();};},[api,actor,studyId,version,caseId,review]);
  const domId=(kind:string,id:string)=>base+'-'+kind+'-'+id;
  // Exact version-qualified case navigation: focus that case's result, never a
  // similarly named case or the first case. Unknown identities are reported.
  useEffect(()=>{
    if(!focusCase)return;
    const known=focusCase.id==='none'||saved.version.content.cases.some(item=>item.case_id===focusCase.id);
    setMissingCase(known?'':focusCase.id);
    let frames=0,frame=0;
    const attempt=()=>{const target=document.getElementById(known?domId('card',focusCase.id):base+'-results');if(target&&target.getClientRects().length){target.focus();target.scrollIntoView({block:'center'});return;}if(++frames<120)frame=requestAnimationFrame(attempt);else document.getElementById(base+'-results')?.focus();};
    frame=requestAnimationFrame(attempt);
    return()=>cancelAnimationFrame(frame);
  },[focusCase?.token,version]);
  // Case definitions belong to the protected approach and clear with it.
  if(denied)return <section className="approach-usage" aria-label="Approach usage"><p role="alert">{accessLostText}</p></section>;
  const incomplete=loading||error||!!cursor||rows.some(row=>row.loading||row.error);
  const groups=groupFindings(saved,rows,caseId);
  const runRows=rows.filter(row=>row.usage.kind==='run'),loadedRuns=runRows.filter(row=>row.run),retained=loadedRuns.filter(row=>row.run!.history?.results).length;
  const configurationsLoaded=rows.filter(row=>row.usage.kind==='configuration'&&row.configuration).length,failedRecords=rows.filter(row=>row.error).length;
  const selectedCase=saved.version.content.cases.find(item=>item.case_id===caseId);
  const coverage=!incomplete?'All usage loaded':error?'A usage page could not be loaded; review coverage is incomplete':cursor?'More usage is available; review coverage is incomplete':loading?'Loading usage; review coverage is incomplete':'Some records are not loaded; review coverage is incomplete';
  const cardGroups=groups.filter(group=>group.item||group.rows.length);
  const row=(item:Row,configuration?:Configuration)=><FindingRow key={identity(item.usage)} row={item} saved={configuration} sources={sources} load={loadSources} retry={()=>void detail(item.usage,generation.current)} onOpen={target=>onOpen({...target,study:studyId})}/>;
  // Results first (recorded facts, exact coverage, no verdict), then one card per case.
  return <section className="approach-usage" aria-label="Approach usage">
    <Panel className="approach-results" label="Results" title="Results" actions={onStudyLimits&&<Button variant="quiet" size="sm" aria-haspopup="dialog" onClick={onStudyLimits}>Study limits</Button>}>
      <p className="approach-eyebrow">Answer to the study question</p>
      <h3 id={base+'-results'} tabIndex={-1} className="approach-results-answer">No study answer has been assessed.</h3>
      <p className="approach-results-summary">{plural(loadedRuns.length,'run')} loaded for {selectedCase?`case ${selectedCase.title} of this`:'this'} approach version. {retained} {retained===1?'has':'have'} results.</p>
      <p className="context-line">Approach v{saved.version.version_number} · {plural(configurationsLoaded,'configuration')} loaded{failedRecords?` · ${plural(failedRecords,'record')} could not be loaded`:''} · {coverage}</p>
      {missingCase&&<p role="alert">This case is not part of approach v{saved.version.version_number}. No other case is shown in its place.</p>}
      <p className="context-line">Criteria are fixed-threshold checks on outputs. They do not answer the study question.</p>
      <div className="section-actions approach-usage-controls"><label>Case filter<Select aria-label="Findings case" value={caseId} onChange={event=>setCaseId(event.target.value)}><option value="">All cases</option>{saved.version.content.cases.map(item=><option key={item.case_id} value={item.case_id}>{item.title}</option>)}</Select></label><Button onClick={()=>setReview(value=>value+1)}>Refresh usage</Button></div>
      <p role="status" className="context-line">{rows.length} usage rows loaded · {rows.filter(row=>row.usage.kind==='configuration').length} configurations · {rows.filter(row=>row.usage.kind==='run').length} runs. {cursor?'More usage is available':!loading&&!error?'All usage loaded':''}</p>
      {loading&&<p role="status">Loading usage…</p>}{error&&<p role="alert">Usage unavailable</p>}{accessUnverified&&<p role="alert">Study access could not be verified. Retry the read.</p>}
    </Panel>
    <div className="approach-case-cards">
      {cardGroups.map(group=><CaseCard key={group.id} group={group} complete={!incomplete} cursor={!!cursor} headingId={domId('card',group.id)} content={saved.version.content} onCreateConfiguration={onCreateConfiguration} row={row}/>)}
      {!cardGroups.length&&<p>No cases</p>}
      {!caseId&&<RemainingWork content={saved.version.content} headingId={base+'-remaining'} onViewStep={onViewStep}/>}
    </div>
    {cursor&&!error&&<Button disabled={loading} onClick={()=>void page(cursor)}>Load more usage</Button>}{error&&<Button disabled={loading} onClick={()=>void page(failedCursor.current)}>Retry usage page</Button>}
  </section>;
}
