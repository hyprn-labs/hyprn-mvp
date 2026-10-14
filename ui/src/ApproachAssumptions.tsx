import type { ApproachResolution } from './api';
import type { ApproachContent } from './api';
import { createContext, useContext, useEffect, useId, useImperativeHandle, useLayoutEffect, useRef, useState, type ReactNode, type Ref, type RefObject } from 'react';
import { Assumptions } from './Assumptions';
import { EvidencePicker } from './EvidencePicker';
import { EvidenceRecordBody } from './EvidenceView';
import { Button, DialogFrame, Panel, Select, TextInput, TextArea, ActionDialog, ActionIcon } from './design';
import { ApiError, HyprnMvpApi, accessLostText, accessUnverifiedText, message, descriptiveApproach } from './api';
import { useAccessLoss } from './accessLoss';
import { modelLabel, instanceName } from './ApproachReferences';
import type { ApproachAssumption1, ApproachAssumptionRef1, ApproachEvidenceLink1, ApproachQuestionClaim1, ApproachSavedRead3, ApproachStep1, ApproachCase1, EvidenceSnapshotRead, ModelRevisionRead4, ConfigurationRevision, ModelAssumption } from './contract';

export type ApproachHandoff = { studyId:string; modelId:string; source:ApproachSavedRead3; proposal:ApproachAssumption1; referencedRevision?:string };
type Props={api?:HyprnMvpApi;studyId?:string;content:ApproachContent;resolved?:ApproachResolution;onChange?:(content:ApproachContent)=>void;disabled?:boolean;baseVersion?:string|null;onHandoff?:(value:ApproachHandoff)=>void;onOpenModel?:(modelId:string)=>void;onEditingChange?:(dirty:boolean)=>void;onAccessLost?:()=>void;contextLabel?:string;children:ReactNode};
type Context=Props&{onEditing:(key:string,dirty:boolean)=>void;models:ModelRevisionRead4[];configurations:ConfigurationRevision[];records:EvidenceSnapshotRead[];addRecords:(records:EvidenceSnapshotRead[])=>void};
const Context=createContext<Context|null>(null);
function useAnnotations(){const value=useContext(Context);if(!value)throw new Error('Approach annotations require exact context.');return value;}
export function ApproachAnnotations(props:Props){
  const [editors,setEditors]=useState<string[]>([]);const editing=editors.length>0;
  useLayoutEffect(()=>{props.onEditingChange?.(editing);return()=>props.onEditingChange?.(false);},[editing]);
  const [models,setModels]=useState<ModelRevisionRead4[]>([]),[configurations,setConfigurations]=useState<ConfigurationRevision[]>([]),[records,setRecords]=useState<EvidenceSnapshotRead[]>([]),[error,setError]=useState('');
  const [denied,setDenied]=useState(false);
  const key=JSON.stringify([props.content.model_bindings,props.content.steps.flatMap(s=>s.assumption_refs),props.content.assumptions.flatMap(a=>a.evidence_links),props.content.steps.flatMap(s=>s.evidence_links),props.content.cases.flatMap(c=>c.evidence_links),descriptiveApproach(props.content).limit_items]);
  useEffect(()=>{
    const abort=new AbortController(),api=props.api,sid=props.studyId,actor=api?.actor,session=api?.csrf;
    const valid=()=>!abort.signal.aborted&&actor===api?.actor&&session===api?.csrf;
    setDenied(false);setModels(props.resolved?.models??[]);setConfigurations(props.resolved?.configurations??[]);setRecords(props.resolved?.evidence??[]);setError('');
    if(!api||!sid)return ()=>abort.abort();
    const read=api.fence({studyId:sid});
    const modelRefs=props.content.model_bindings;
    const configIds=[...new Set(props.content.steps.flatMap(s=>s.assumption_refs.flatMap(r=>r.kind==='configuration'?[r.configuration_revision_id]:[])))];
    const evidenceIds=[...new Set([...props.content.assumptions,...props.content.steps,...props.content.cases,...(descriptiveApproach(props.content).limit_items)].flatMap(a=>a.evidence_links.map(l=>l.evidence_version_id)))];
    // Closed content bounds limit work; only two referenced reads run at once.
    async function collect<T>(jobs:Array<()=>Promise<T>>){let next=0;const values:T[]=[];await Promise.all([0,1].map(async()=>{while(valid()&&next<jobs.length){const index=next++;values[index]=await jobs[index]();}}));return values;}
    void (async()=>{
      const m=await collect(modelRefs.map(b=>()=>api.revision(sid,b.model_id,b.model_revision_id,abort.signal)));
      const c=await collect(configIds.map(id=>()=>api.configuration(sid,id,abort.signal)));
      const cited=[...m,...c.map(x=>x.configuration)].flatMap(x=>'assumptions'in x?x.assumptions.flatMap(a=>a.evidence_links.map(l=>l.evidence_version_id)):[]);
      const e=await collect([...new Set([...evidenceIds,...cited])].map(id=>()=>api.evidenceVersion(sid,id,abort.signal)));
      if(valid()){setModels(m);setConfigurations(c.map(x=>x.configuration));setRecords(e);}
    })().catch(async error=>{
      if(!valid())return;
      // Shared classification; a confirmed denial is signalled to every host of this study.
      const outcome=await api.readFailed(error,read);
      if(outcome==='access-lost'){props.onAccessLost?.();setDenied(true);setModels([]);setConfigurations([]);setRecords([]);return;}
      if(outcome==='stale'||!valid())return;
      if(outcome==='transient'){setError(accessUnverifiedText);setModels([]);setConfigurations([]);setRecords([]);}
      else setError(message(error));
    }).finally(read.done);
    return()=>{abort.abort();read.done();};
  },[props.api,props.studyId,key,props.resolved]);
  if(denied)return <p role="alert">Access to this resource is no longer available.</p>;
  return <Context.Provider value={{...props,onEditing:(key,dirty)=>setEditors(old=>dirty?(old.includes(key)?old:[...old,key]):old.includes(key)?old.filter(id=>id!==key):old),models,configurations,records,addRecords:items=>setRecords(old=>items.length?[...old.filter(r=>!items.some(n=>n.evidence_version_id===r.evidence_version_id)),...items]:[])}}>{error&&<p role="alert">Referenced assumptions or evidence could not be loaded. {error}</p>}{props.children}</Context.Provider>;
}
function Citations({
  links,
  label,
  onChange,
  brief = false,
}: {
  brief?: boolean;
  links: ApproachEvidenceLink1[];
  label: string;
  onChange?: (links: ApproachEvidenceLink1[]) => void;
}) {
  const { api, studyId, records, addRecords, disabled, onEditing } = useAnnotations(),
    [picker, setPicker] = useState(false),
    [editing, setEditing] = useState<{ index: number; value: ApproachEvidenceLink1 } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null),
    invoker = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (editing) {
      dialog.current?.showModal();
      dialog.current?.querySelector('select')?.focus();
    }
  }, [!!editing]);
  const dirty = !!editing && JSON.stringify(editing.value) !== JSON.stringify(links[editing.index]);
  useLayoutEffect(() => {
    if (editing) onEditing('citation/' + label, dirty);
    return () => {
      if (editing) onEditing('citation/' + label, false);
    };
  }, [dirty, !!editing]);
  function close() {
    dialog.current?.close();
    setEditing(null);
    invoker.current?.focus();
  }
  return (
    <section className={brief ? 'assumption-evidence' : undefined} aria-label={label + ' evidence'}>
      {!links.length && !brief && <p className="context-line">No evidence linked</p>}
      {links.map((link, index) => (
        <div
          className={brief ? 'assumption-evidence-row' : 'evidence-record'}
          key={link.evidence_version_id + link.relation}
        >
          <div className={brief ? undefined : 'section-actions'}>
            {!brief && (
              <span>
                {link.relation === 'supports'
                  ? 'Supports'
                  : link.relation === 'challenges'
                    ? 'Challenges'
                    : 'Context'}
              </span>
            )}
            {records.find((r) => r.evidence_version_id === link.evidence_version_id) ? (
              <EvidenceRecordBody
                compact
                brief={brief}
                relation={brief ? link.relation : undefined}
                record={records.find((r) => r.evidence_version_id === link.evidence_version_id)!}
              />
            ) : (
              <span>Evidence unavailable</span>
            )}
            {onChange && (
              <>
                <Button
                  disabled={disabled}
                  onClick={() => {
                    invoker.current = document.activeElement as HTMLElement;
                    setEditing({ index, value: structuredClone(link) });
                  }}
                >
                  Edit citation
                </Button>
                <Button
                  disabled={disabled}
                  onClick={() => onChange(links.filter((_, i) => i !== index))}
                >
                  Remove citation
                </Button>
              </>
            )}
          </div>
          {link.locator && <p className="context-line">{link.locator}</p>}
        </div>
      ))}
      {onChange && api && studyId && (
        <Button
          aria-label={'Add evidence to ' + label}
          disabled={disabled || links.length >= 64}
          onClick={() => setPicker(true)}
        >
          Add evidence
        </Button>
      )}
      {picker && api && studyId && (
        <EvidencePicker
          onDirty={(dirty) => onEditing('evidence/' + label, dirty)}
          api={api}
          studyId={studyId}
          ownerKey={label}
          label={label}
          scope={{ scope_version: '1', kind: 'study', study_id: studyId }}
          assumption
          onRecords={addRecords}
          onClose={() => setPicker(false)}
          onAttach={(record, relation) => {
            if (
              relation &&
              !links.some(
                (l) =>
                  l.evidence_version_id === record.evidence_version_id && l.relation === relation,
              )
            )
              onChange?.([...links, { evidence_version_id: record.evidence_version_id, relation }]);
            setPicker(false);
          }}
        />
      )}
      {editing && (
        <DialogFrame
          ref={dialog}
          aria-label="Edit citation"
          onCancel={(e) => {
            e.preventDefault();
            close();
          }}
        >
          <h2>Edit citation</h2>
          <p>{label}</p>
          <label>
            Relationship
            <Select
              aria-label="Citation relationship"
              disabled={disabled}
              value={editing.value.relation}
              onChange={(e) =>
                setEditing({
                  ...editing,
                  value: {
                    ...editing.value,
                    relation: e.target.value as ApproachEvidenceLink1['relation'],
                  },
                })
              }
            >
              <option value="supports">Supports</option>
              <option value="challenges">Challenges</option>
              <option value="context">Context</option>
            </Select>
          </label>
          <label>
            Location in evidence
            <TextInput
              aria-label="Evidence locator"
              maxLength={512}
              disabled={disabled}
              value={editing.value.locator ?? ''}
              onChange={(e) =>
                setEditing({ ...editing, value: { ...editing.value, locator: e.target.value } })
              }
            />
          </label>
          <div className="actions">
            <Button
              disabled={disabled}
              variant="primary"
              onClick={() => {
                onChange?.(links.map((l, i) => (i === editing.index ? editing.value : l)));
                close();
              }}
            >
              Apply citation
            </Button>
            <Button onClick={close}>Cancel</Button>
          </div>
        </DialogFrame>
      )}
    </section>
  );
}
export function ApproachAssumptions({
  showHeading = true,
  brief = false,
}: { showHeading?: boolean; brief?: boolean } = {}) {
  const ctx = useAnnotations(),
    { api, studyId, content, records, onChange, disabled, addRecords } = ctx;
  const [error, setError] = useState(''),
    [handoff, setHandoff] = useState<ApproachAssumption1 | null>(null);
  return (
    <section className="approach-basis">
      <Assumptions
        showHeading={showHeading}
        brief={brief}
        approach
        ownerKey={studyId ?? 'retained'}
        ownerLabel="Modeling approach"
        items={content.assumptions}
        records={records}
        itemActions={
          onChange && api
            ? (a) =>
                (a as ApproachAssumption1).role === 'proposed_model_condition' && (
                  <Button
                    disabled={disabled}
                    aria-label={'Implement condition: ' + a.statement}
                    onClick={() => setHandoff(a as ApproachAssumption1)}
                  >
                    Implement in model
                  </Button>
                )
            : undefined
        }
        editable={
          onChange && api && studyId
            ? {
                api,
                studyId,
                scope: { scope_version: '1', kind: 'study', study_id: studyId },
                disabled,
                onRecords: addRecords,
                onDirty: (dirty) => ctx.onEditing('assumption', dirty),
                onChange: (items) => {
                  if (
                    content.steps.some((s) =>
                      s.assumption_refs.some(
                        (r) =>
                          r.kind === 'approach' &&
                          !items.some((a) => a.assumption_id === r.assumption_id),
                      ),
                    )
                  ) {
                    setError(
                      'A method step uses this assumption. ' +
                        'Remove its reference before removing the assumption.',
                    );
                    return;
                  }
                  setError('');
                  onChange({ ...content, assumptions: items as ApproachAssumption1[] });
                },
              }
            : undefined
        }
      />
      {error && <p role="alert">{error}</p>}
      {handoff && <Handoff proposal={handoff} onClose={() => setHandoff(null)} />}
    </section>
  );
}
function describe(ref:ApproachAssumptionRef1,ctx:Context){
  // Owner labels name the owner once: Modeling approach, Model or Component, Configuration.
  if(ref.kind==='approach'){const assumption=ctx.content.assumptions.find(a=>a.assumption_id===ref.assumption_id);return {assumption,label:'Modeling approach · '+(assumption?.role==='overall_method'?'Overall method assumption':'Proposed model condition')};}
  if(ref.kind==='configuration'){const c=ctx.configurations.find(c=>c.configuration_revision_id===ref.configuration_revision_id);return {assumption:c&&'assumptions'in c?c.assumptions.find(a=>a.assumption_id===ref.assumption_id):undefined,label:`Configuration · ${c?.name??'Unavailable'} · version ${ref.configuration_revision_id.slice(0,8)}`};}
  const b=ctx.content.model_bindings.find(b=>b.binding_id===ref.binding_id),m=ctx.models.find(m=>m.model_revision_id===b?.model_revision_id),a=m&&'assumptions'in m?m.assumptions.find(a=>a.assumption_id===ref.assumption_id):undefined;
  return {assumption:a,label:m?`${modelLabel(m)} · ${a?.owner.kind==='instance'?'Component · '+instanceName(m,a.owner.instance_id):'Model'}`:'Model assumption unavailable'};
}
export function ApproachStepContext({step}:{step:ApproachStep1}){
  const ctx=useAnnotations(),{content,onChange,disabled}=ctx,[choosing,setChoosing]=useState(false);
  const update=(next:ApproachStep1)=>onChange?.({...content,steps:content.steps.map(s=>s.step_id===next.step_id?next:s)});
  return <section aria-label={step.title+' assumptions and evidence'}>{step.assumption_refs.map((ref,index)=>{const item=describe(ref,ctx);return <div className="evidence-record" key={JSON.stringify(ref)}><p className="context-copy">{item.assumption?.statement??'Assumption unavailable'}</p><p className="context-line">{item.label}</p>{ref.kind==='model'&&ref.origin&&<p className="context-line">Implements a proposed condition from approach version {ref.origin.approach_version_id.slice(0,8)}.</p>}{item.assumption&&<Citations links={item.assumption.evidence_links} label={'Assumption for '+step.title}/>}<div className="section-actions">{onChange&&ref.kind==='model'&&ctx.onOpenModel&&<ActionDialog title="Edit assumption at its owner" label="Open model owner"><p>This reference uses a committed model version. Editing the current model draft does not change this approach reference. Save a model version and explicitly select it to update the explanation.</p><Button disabled={disabled} onClick={()=>{const b=content.model_bindings.find(b=>b.binding_id===ref.binding_id);if(b)ctx.onOpenModel?.(b.model_id);}}>Open model draft</Button></ActionDialog>}{onChange&&<Button disabled={disabled} onClick={()=>update({...step,assumption_refs:step.assumption_refs.filter((_,i)=>i!==index)})}>Remove assumption reference</Button>}</div></div>;})}{onChange&&<Button aria-label={"Link assumption to "+step.title} disabled={disabled} onClick={()=>setChoosing(true)}>Link assumption</Button>}{choosing&&<AssumptionPicker step={step} onChoose={ref=>{if(!step.assumption_refs.some(r=>JSON.stringify(r)===JSON.stringify(ref)))update({...step,assumption_refs:[...step.assumption_refs,ref]});setChoosing(false);}} onClose={()=>setChoosing(false)}/>}<Citations links={step.evidence_links} label={step.title+' rationale'} onChange={onChange?links=>update({...step,evidence_links:links}):undefined}/></section>;
}
export function ApproachCaseContext({item}:{item:ApproachCase1}){const {content,onChange}=useAnnotations();return <Citations links={item.evidence_links} label={item.title+' case'} onChange={onChange?links=>onChange({...content,cases:content.cases.map(c=>c.case_id===item.case_id?{...c,evidence_links:links}:c)}):undefined}/>;}
function AssumptionPicker({step,onChoose,onClose}:{step:ApproachStep1;onChoose:(ref:ApproachAssumptionRef1)=>void;onClose:()=>void}){
  const ctx=useAnnotations(),dialog=useRef<HTMLDialogElement>(null),[configs,setConfigs]=useState<ConfigurationRevision[]>(ctx.configurations),[error,setError]=useState('');
  useEffect(()=>{const invoking=document.activeElement as HTMLElement;dialog.current?.showModal();let active=true;const actor=ctx.api?.actor;if(ctx.api&&ctx.studyId)void ctx.api.configurations(ctx.studyId).then(items=>{if(active&&ctx.api?.actor===actor)setConfigs(items.map(c=>c.configuration));}).catch(e=>{if(active)setError(message(e));});return()=>{active=false;invoking?.focus();};},[]);
  const choices:Array<{ref:ApproachAssumptionRef1;label:string}>=ctx.content.assumptions.map(a=>({ref:{kind:'approach',assumption_id:a.assumption_id},label:`Approach · ${a.statement}`}));
  for(const b of ctx.content.model_bindings){const m=ctx.models.find(m=>m.model_revision_id===b.model_revision_id);if(m&&'assumptions'in m)for(const a of m.assumptions)choices.push({ref:{kind:'model',binding_id:b.binding_id,assumption_id:a.assumption_id,origin:null},label:`${modelLabel(m)} · ${a.owner.kind==='instance'?instanceName(m,a.owner.instance_id):'Model'} · ${a.statement}`});}
  for(const c of configs)if('assumptions'in c)for(const a of c.assumptions)choices.push({ref:{kind:'configuration',configuration_revision_id:c.configuration_revision_id,assumption_id:a.assumption_id},label:`Configuration ${c.name} · ${c.configuration_revision_id.slice(0,8)} · ${a.statement}`});
  return <DialogFrame ref={dialog} aria-label="Link assumption" onCancel={e=>{e.preventDefault();onClose();}}><h2>Link assumption to {step.title}</h2><p>Assumptions stay with their owner. Model and configuration versions are read-only.</p><div className="hf-action-list">{choices.map(c=><Button key={JSON.stringify(c.ref)} disabled={ctx.disabled||step.assumption_refs.some(r=>JSON.stringify(r)===JSON.stringify(c.ref))} onClick={()=>onChoose(c.ref)}>{c.label}</Button>)}</div>{!choices.length&&<p>No assumptions available. Add an approach assumption or link a model version containing assumptions.</p>}{error&&<p role="alert">{error}</p>}<Button onClick={onClose}>Cancel</Button></DialogFrame>;
}

export function useApproachEditGuard(key:string,dirty:boolean){const ctx=useAnnotations();useLayoutEffect(()=>{ctx.onEditing(key,dirty);return()=>ctx.onEditing(key,false);},[key,dirty]);}
function Handoff({proposal,onClose}:{proposal:ApproachAssumption1;onClose:()=>void}){
  const ctx=useAnnotations(),{api,studyId,content,onChange,baseVersion,onHandoff}=ctx;
  const dialog=useRef<HTMLDialogElement>(null),generation=useRef(0);
  const [source,setSource]=useState<ApproachSavedRead3|null>(null),[models,setModels]=useState<Array<{model_id:string;name:string}>>([]),[mid,setMid]=useState(''),[versions,setVersions]=useState<Array<{model_revision_id:string}>>([]),[snapshot,setSnapshot]=useState<ModelRevisionRead4|null>(null),[assumption,setAssumption]=useState(''),[stepId,setStepId]=useState(''),[remaining,setRemaining]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[draftInfo,setDraftInfo]=useState('');
  useEffect(()=>{const invoking=document.activeElement as HTMLElement;dialog.current?.showModal();const token=++generation.current,actor=api?.actor;setBusy(true);if(api&&studyId&&baseVersion)void Promise.all([api.approachVersion(studyId,baseVersion),api.models(studyId).then(items=>Promise.all(items.map(async m=>({model_id:m.model_id,name:(await api.model(studyId,m.model_id)).name}))))]).then(([s,m])=>{if(token===generation.current&&actor===api.actor){setSource(s);setModels(m);}}).catch(e=>{if(token===generation.current)setError(message(e));}).finally(()=>{if(token===generation.current)setBusy(false);});else{setBusy(false);setError('Save an approach version containing this proposed condition before implementing it.');}return()=>{generation.current++;invoking?.focus();};},[]);
  useApproachEditGuard('handoff',!!remaining);
  const savedProposal=source?.version.content.assumptions.find(a=>a.assumption_id===proposal.assumption_id&&a.role==='proposed_model_condition');
  const exact=!!savedProposal&&JSON.stringify(savedProposal)===JSON.stringify(proposal);
  async function chooseModel(id:string){if(!api||!studyId)return;const token=++generation.current,actor=api.actor;setMid(id);setSnapshot(null);setAssumption('');setVersions([]);setDraftInfo('');if(!id)return;setBusy(true);setError('');try{const [entries,draft]=await Promise.all([api.revisions(studyId,id),api.model(studyId,id)]);if(token!==generation.current||actor!==api.actor)return;setVersions(entries);const referenced=content.model_bindings.filter(b=>b.model_id===id).map(b=>b.model_revision_id.slice(0,8));setDraftInfo(`Authoring opens the current saved draft ${draft.draft_revision.slice(0,8)}. ${referenced.length?'The approach references committed version(s) '+referenced.join(', ')+', which remain unchanged.':'No version of this model is currently linked to the approach.'} Review the current draft before applying the condition.`);}catch(e){if(token===generation.current)setError(message(e));}finally{if(token===generation.current)setBusy(false);}}
  async function chooseVersion(id:string){if(!api||!studyId)return;const token=++generation.current,actor=api.actor;setSnapshot(null);setAssumption('');if(!id)return;setBusy(true);setError('');try{const value=await api.revision(studyId,mid,id);if(token===generation.current&&actor===api.actor)setSnapshot(value);}catch(e){if(token===generation.current)setError(message(e));}finally{if(token===generation.current)setBusy(false);}}
  const target=snapshot&&'assumptions'in snapshot?snapshot.assumptions.find(a=>a.assumption_id===assumption):undefined;
  function replace(){if(!source||!exact||!snapshot||!target||!onChange)return;const step=content.steps.find(s=>s.step_id===stepId);if(!step){setError('Choose the method step whose implementation contains this assumption.');return;}if(step.implementation_state==='proposed'&&!remaining.trim()){setError('Describe the remaining implementation work for this partially linked step.');return;}
    const binding=content.model_bindings.find(b=>b.model_revision_id===snapshot.model_revision_id)??{binding_id:crypto.randomUUID(),model_id:snapshot.model_id,model_revision_id:snapshot.model_revision_id};
    const ref:ApproachAssumptionRef1={kind:'model',binding_id:binding.binding_id,assumption_id:target.assumption_id,origin:{approach_version_id:source.version.approach_version_id,assumption_id:proposal.assumption_id,digest:source.version.digest}};
    onChange({...content,model_bindings:content.model_bindings.some(b=>b.binding_id===binding.binding_id)?content.model_bindings:[...content.model_bindings,binding],assumptions:content.assumptions.filter(a=>a.assumption_id!==proposal.assumption_id),steps:content.steps.map(s=>{let refs=s.assumption_refs.map(r=>r.kind==='approach'&&r.assumption_id===proposal.assumption_id?ref:r);if(s.step_id!==stepId)return {...s,assumption_refs:refs};if(!refs.some(r=>JSON.stringify(r)===JSON.stringify(ref)))refs=[...refs,ref];return {...s,assumption_refs:refs,implementation_refs:s.implementation_refs.some(r=>r.binding_id===binding.binding_id)?s.implementation_refs:[...s.implementation_refs,{kind:'model',binding_id:binding.binding_id}],...(s.implementation_state==='proposed'?{implementation_state:'partial',remaining_work:remaining}:{})};})});onClose();
  }
  return <DialogFrame ref={dialog} aria-label="Implement proposed condition" onCancel={e=>{e.preventDefault();onClose();}}><h2>Implement proposed condition</h2><p className="context-copy">{proposal.statement}</p>{source&&<p>Source: approach v{source.version.version_number} (read-only). This version keeps the original proposal.</p>}{source&&!exact&&<p role="alert">This condition differs from the saved version. Save a new approach version before continuing.</p>}<label>Target model<Select aria-label="Condition target model" disabled={busy||!exact} value={mid} onChange={e=>void chooseModel(e.target.value)}><option value="">Choose model</option>{models.map(m=><option key={m.model_id} value={m.model_id}>{m.name}</option>)}</Select></label>{draftInfo&&<p>{draftInfo}</p>}{onHandoff&&<Button disabled={busy||!exact||!mid||ctx.disabled} onClick={()=>{if(source&&studyId){onClose();onHandoff({studyId,modelId:mid,source,proposal,referencedRevision:content.model_bindings.find(b=>b.model_id===mid)?.model_revision_id});}}}>Open model assumption editor</Button>}
    {mid&&<section><h3>Link an acknowledged model assumption</h3><p>After applying the model command and saving a model version, select the assumption here. This also resumes a handoff after reloading. Resolve any uncertain original command first.</p><label>Committed model version<Select aria-label="Condition committed model version" disabled={busy} value={snapshot?.model_revision_id??''} onChange={e=>void chooseVersion(e.target.value)}><option value="">Choose committed version</option>{versions.map(v=><option key={v.model_revision_id} value={v.model_revision_id}>{v.model_revision_id.slice(0,8)} (read-only)</option>)}</Select></label>{snapshot&&<><label>Model assumption<Select aria-label="Committed model assumption" value={assumption} onChange={e=>setAssumption(e.target.value)}><option value="">Choose assumption</option>{'assumptions'in snapshot&&snapshot.assumptions.map(a=><option key={a.assumption_id} value={a.assumption_id}>{a.owner.kind==='instance'?instanceName(snapshot,a.owner.instance_id):'Model'} · {a.statement}</option>)}</Select></label>{target&&<p className="context-copy">{target.statement}</p>}<label>Method step<Select aria-label="Condition method step" value={stepId} onChange={e=>setStepId(e.target.value)}><option value="">Choose method step</option>{content.steps.map(s=><option key={s.step_id} value={s.step_id}>{s.title}</option>)}</Select></label>{content.steps.find(s=>s.step_id===stepId)?.implementation_state==='proposed'&&<label>Remaining implementation work<TextInput aria-label="Condition remaining work" value={remaining} onChange={e=>setRemaining(e.target.value)}/></label>}<p>The selected model version will be linked to this step. Other references stay unchanged. The active proposal becomes a model assumption reference that keeps its original approach version.</p></>}</section>}{error&&<p role="alert">{error}</p>}{busy&&<p role="status">Loading records…</p>}<div className="actions"><Button disabled={busy||ctx.disabled||!exact||!target||!stepId||!!api?.pending} variant="primary" onClick={replace}>Replace with model assumption</Button><Button onClick={onClose}>Keep proposed condition</Button></div></DialogFrame>;
}

/** A supplied origin claim beside the agreed question; attribution is never authenticated. */
function QuestionClaim({title,claim}:{title:string;claim:ApproachQuestionClaim1|null}){
  if (!claim?.text.trim()) return null;
  return (
    <div className="study-details-claim">
      <h4>{title}</h4>
      <p className="context-copy">{claim.text}</p>
      <p className="context-line">
        {claim.attribution.kind === 'unknown'
          ? 'Authorship unknown'
          : `Supplied ${claim.attribution.kind === 'human' ? 'human' : 'agent'} attribution`}
        {claim.attribution.label ? ': ' + claim.attribution.label : ''} · Authorship has not been
        verified.
      </p>
    </div>
  );
}

/** The approach page question box opens the shared Study details dialog. */
export function StudyQuestionBox({
  question,
  scope,
  headingId,
  actions,
  onDetails,
  children,
}: {
  question: string;
  scope?: string;
  headingId?: string;
  actions?: ReactNode;
  onDetails?: () => void;
  children?: ReactNode;
}) {
  return (
    <Panel className="approach-question-card" label="Study question">
      <p className="approach-eyebrow">Study question</p>
      <h2 id={headingId} tabIndex={-1} className="approach-question">
        {question || 'No study question'}
      </h2>
      {scope && <p className="context-copy approach-question-scope">{scope}</p>}
      {children}
      {(actions || onDetails) && (
        <div className="approach-question-actions">
          <div className="section-actions">{actions}</div>
          {onDetails && (
            <Button aria-haspopup="dialog" onClick={onDetails}>
              See more details
            </Button>
          )}
        </div>
      )}
    </Panel>
  );
}

export type StudyDetailsHandle={open:(focus?:'limits')=>void};
/** Study details separates the question, current approach, assumptions, limits and open questions
 * for the exact content
 * of the surrounding ApproachAnnotations (current draft, a saved or a retained version).
 * Editable only where that context is (approach edit mode); read-only everywhere else. */
export function StudyDetailsDialog({ref}:{ref?:Ref<StudyDetailsHandle>}){
  const dialog=useRef<HTMLDialogElement>(null),invoker=useRef<HTMLElement|null>(null),limits=useRef<HTMLHeadingElement>(null),id=useId();
  useImperativeHandle(ref,()=>({open(focus){
    invoker.current=document.activeElement as HTMLElement;dialog.current?.showModal();
    if(focus==='limits')requestAnimationFrame(()=>{limits.current?.scrollIntoView({block:'start'});limits.current?.focus();});
  }}),[]);
  const close=()=>dialog.current?.close();
  // Native close normally restores focus; keep it on the opener when the browser does not.
  return <DialogFrame ref={dialog} aria-labelledby={id} className="action-dialog study-details-dialog" onClose={()=>{const active=document.activeElement;if(invoker.current?.isConnected&&(active===document.body||!active||dialog.current?.contains(active)))invoker.current.focus();}}>
    <div className="dialog-heading"><h2 id={id}>Study details</h2><Button variant="quiet" icon={<ActionIcon name="close"/>} aria-label="Close Study details" onClick={close}/></div>
    <div className="dialog-body"><StudyDetails limitsHeading={limits}/></div>
    <div className="dialog-footer"><Button onClick={close}>Done</Button></div>
  </DialogFrame>;
}
function StudyDetails({limitsHeading}:{limitsHeading:RefObject<HTMLHeadingElement|null>}){
  const {content,onChange,disabled,contextLabel}=useAnnotations();
  const [editing,setEditing]=useState<{limit_id:string;statement:string;evidence_links:ApproachEvidenceLink1[]}|null>(null);
  const dialog=useRef<HTMLDialogElement>(null),invoker=useRef<HTMLElement|null>(null);
  useApproachEditGuard('limit',!!editing);
  const described=descriptiveApproach(content),limits=described.limit_items;
  function begin(item?:typeof editing){invoker.current=document.activeElement as HTMLElement;setEditing(item??{limit_id:crypto.randomUUID(),statement:'',evidence_links:[]});}
  useEffect(()=>{if(editing){dialog.current?.showModal();dialog.current?.querySelector('textarea')?.focus();}},[!!editing]);
  function close(){dialog.current?.close();setEditing(null);invoker.current?.focus();}
  function update(items:typeof limits){onChange?.({...described,limit_items:items});}
  return (
    <div className="study-details">
      <p className="context-line">{contextLabel ?? 'Current approach draft'}</p>
      <section aria-label="Study question" className="study-details-section">
        <h3>Study question</h3>
        <p className="context-copy study-details-question">
          {content.question || 'No study question'}
        </p>
        <QuestionClaim title="Original wording" claim={described.original_question} />
        <QuestionClaim title="Elaboration" claim={described.elaboration} />
      </section>
      {content.scope.trim() && (
        <section aria-label="Current approach" className="study-details-section">
          <h3>Current approach</h3>
          <p className="context-copy">{content.scope}</p>
        </section>
      )}
      {(content.assumptions.length > 0 || onChange) && (
        <section aria-label="Study assumptions" className="study-details-section">
          <h3>Assumptions</h3>
          <ApproachAssumptions showHeading={false} brief />
        </section>
      )}
      {(limits.length > 0 || content.limitations.trim() || onChange) && (
        <section aria-label="Study limits" className="study-details-section study-limits-section">
          <h3 ref={limitsHeading} tabIndex={-1}>
            Limits
          </h3>
          {onChange && (
            <Button disabled={disabled || limits.length >= 256} onClick={() => begin()}>
              Add limit
            </Button>
          )}
          {limits.map((item) => (
            <article className="study-limit-item" key={item.limit_id}>
              <p className="context-copy">{item.statement}</p>
              <Citations
                brief
                links={item.evidence_links}
                label={item.statement}
                onChange={
                  onChange
                    ? (links) =>
                        update(
                          limits.map((l) =>
                            l.limit_id === item.limit_id ? { ...l, evidence_links: links } : l,
                          ),
                        )
                    : undefined
                }
              />
              {onChange && (
                <div className="section-actions">
                  <Button
                    disabled={disabled}
                    aria-label={'Edit limit: ' + item.statement}
                    onClick={() => begin(structuredClone(item))}
                  >
                    Edit limit
                  </Button>
                  <ActionDialog
                    title={'Remove limit: ' + item.statement}
                    label="Remove limit"
                    disabled={disabled}
                  >
                    <p>
                      Remove {item.statement} from this draft? Saved versions and linked records
                      remain unchanged.
                    </p>
                    <Button
                      disabled={disabled}
                      onClick={() => update(limits.filter((l) => l.limit_id !== item.limit_id))}
                    >
                      Remove this limit
                    </Button>
                  </ActionDialog>
                </div>
              )}
            </article>
          ))}
          {content.limitations.trim() && (
            <article className="study-limit-item">
              <p className="context-copy">{content.limitations}</p>
            </article>
          )}
        </section>
      )}
      {content.open_questions.trim() && (
        <section aria-label="Open questions" className="study-details-section">
          <h3>Open questions</h3>
          <p className="context-copy">{content.open_questions}</p>
        </section>
      )}
      {editing && (
        <DialogFrame
          ref={dialog}
          aria-label="Edit study limit"
          onCancel={(e) => {
            e.preventDefault();
            close();
          }}
        >
          <h2>Edit study limit</h2>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (!editing.statement.trim()) return;
              update(
                limits.some((l) => l.limit_id === editing.limit_id)
                  ? limits.map((l) => (l.limit_id === editing.limit_id ? editing : l))
                  : [...limits, editing],
              );
              close();
            }}
          >
            <label>
              Limit statement
              <TextArea
                aria-label="Limit statement"
                required
                maxLength={4096}
                value={editing.statement}
                onChange={(e) => setEditing({ ...editing, statement: e.target.value })}
              />
            </label>
            <div className="actions">
              <Button
                type="submit"
                variant="primary"
                disabled={disabled || !editing.statement.trim()}
              >
                Apply limit
              </Button>
              <Button type="button" onClick={close}>
                Cancel
              </Button>
            </div>
          </form>
        </DialogFrame>
      )}
    </div>
  );
}

type OverviewQuestion={kind:'loading'}|{kind:'none';draft:boolean}|{kind:'error';text:string}|{kind:'lost'}|{kind:'ready';record:ApproachSavedRead3};
/** Overview question: the latest saved approach version only (a draft is never study
 * context). Reads through the shared session fence; a confirmed denial clears it, and a late
 * reply after sign-out, access loss or leaving Overview is discarded. A retry re-reads only
 * the exact version already selected. Evidence comes from that version's closure. */
export function OverviewStudyQuestion({
  api,
  studyId,
  children,
}: {
  api: HyprnMvpApi;
  studyId: string;
  children: (question: ReactNode, details: ReactNode) => ReactNode;
}) {
  const [state, setState] = useState<OverviewQuestion>({ kind: 'loading' }),
    [attempt, setAttempt] = useState(0);
  const selected = useRef<string | null>(null),
    details = useRef<StudyDetailsHandle>(null);
  useAccessLoss(api, studyId, (change) => {
    selected.current = null;
    setState(change.kind === 'access-lost' ? { kind: 'lost' } : { kind: 'loading' });
  });
  useEffect(() => {
    const read = api.fence({ studyId });
    let current = true;
    const valid = () => current && read.valid();
    setState({ kind: 'loading' });
    void (async () => {
      try {
        let version = selected.current;
        if (!version) {
          const approach = await api.approach(studyId, read.signal);
          if (!valid()) return;
          if (!approach.latest_version) {
            setState({ kind: 'none', draft: !!approach.draft });
            return;
          }
          version = approach.latest_version.approach_version_id;
          selected.current = version;
        }
        const saved = await api.approachVersion(studyId, version, read.signal);
        if (!valid()) return;
        if (saved.version.approach_version_id !== version)
          throw new Error('The saved approach version could not be verified.');
        setState({ kind: 'ready', record: saved });
      } catch (error) {
        if (!current) return;
        const outcome = await api.readFailed(error, read);
        if (!current || outcome === 'stale') return;
        if (outcome === 'access-lost') {
          selected.current = null;
          setState({ kind: 'lost' });
          return;
        }
        setState({
          kind: 'error',
          text:
            outcome === 'transient'
              ? accessUnverifiedText
              : error instanceof ApiError && error.detail.code === 'backend_unavailable'
                ? 'The study question is temporarily unavailable. Retry this read.'
                : message(error),
        });
      } finally {
        read.done();
      }
    })();
    return () => {
      current = false;
      read.abort();
    };
  }, [api, studyId, api.actor, api.csrf, attempt]);
  useEffect(
    () => () => {
      selected.current = null;
    },
    [studyId],
  );
  if (state.kind === 'ready') {
    const record = state.record;
    return (
      <ApproachAnnotations
        content={record.version.content}
        resolved={record.closure}
        contextLabel={'Current saved approach v' + record.version.version_number}
      >
        {children(
          <p className="context-copy">
            <strong>Study question: </strong>
            {record.version.content.question || 'No study question yet'}
          </p>,
          <Button aria-haspopup="dialog" onClick={() => details.current?.open()}>
            See more details
          </Button>,
        )}
        <StudyDetailsDialog ref={details} />
      </ApproachAnnotations>
    );
  }
  return children(
    <div className="overview-question">
      <p>
        <strong>Study question</strong>
      </p>
      {state.kind === 'loading' ? (
        <p role="status">Loading study question…</p>
      ) : state.kind === 'none' ? (
        <>
          <p>No study question yet</p>
          <p className="context-line">
            {state.draft
              ? 'A draft is available, but no approach version has been saved.'
              : 'No saved approach version is available.'}
          </p>
        </>
      ) : state.kind === 'lost' ? (
        <p role="alert">{accessLostText}</p>
      ) : (
        <div role="alert">
          <p>{state.text}</p>
          <Button onClick={() => setAttempt((value) => value + 1)}>Retry study question</Button>
        </div>
      )}
    </div>,
    null,
  );
}
