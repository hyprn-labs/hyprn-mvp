import { useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Select, DialogFrame, ActionDialog, SectionHeader } from './design';
import { HyprnMvpApi, accessLostText, accessUnverifiedText, message, type ReadFence } from './api';
import { useAccessLoss } from './accessLoss';
import type { ApproachClosureRead3, ApproachSelection1, ApproachSavedRead3, ApproachVersionSummaryRead2, ApproachCursor1, ModelRevisionRead4 } from './contract';
import { ApproachReader } from './ApproachPanel';
import { CaseNavigation, type CaseNavigationTarget } from './workspaceModel';

/** Navigation control only: identity comes from an exact pin, never a name match. */
export function CaseContextLink({ target, returnKey, label, children }: { target: CaseNavigationTarget; returnKey: string; label: string; children: ReactNode }) {
  const open = useContext(CaseNavigation);
  if (!open) return null;
  return <Button variant="quiet" size="sm" className="case-context-link" data-case-return={returnKey} aria-label={label} onClick={() => open(target, returnKey)}>{children}</Button>;
}

/** Exact retained content only. This view never fetches a current approach. */
export function ConfigurationApproachRecord({ selection, closure, actions }: { actions?:ReactNode; selection: ApproachSelection1 | null; closure?: ApproachClosureRead3 | null }) {
  if (!selection) return <section className="configuration-section configuration-approach"><SectionHeader level={3} title="Modeling approach" actions={actions}/><p className="context-line">No modeling approach is linked.</p></section>;
  const version = closure?.approach_versions.find(v => v.approach_version_id === selection.approach_version_id);
  if (!version || !closure) return <section className="configuration-section configuration-approach"><SectionHeader level={3} title="Modeling approach" actions={actions}/><p role="status">The linked modeling approach could not be loaded. The link to its version is unchanged.</p></section>;
  // Correlate the exact ancestor with its closure branch; never promote old bytes.
  const record: ApproachSavedRead3 | null = closure.schema_version === '3' ? {version,closure} :
    version.schema_version === '1' ? {version,closure} : null;
  if (!record) return <p>The linked modeling approach is unavailable.</p>;
  const item = version.content.cases.find(c => c.case_id === selection.case_id);
  const caseLabel = selection.case_id === null ? 'No specific case' : item ? item.title : 'Case not in this approach version';
  return <section className="configuration-section configuration-approach" aria-label="Linked modeling approach"><SectionHeader level={3} title="Modeling approach" actions={<><ActionDialog width="workspace" title="Linked modeling approach" label="View modeling approach"><ApproachReader source={{kind:'retained',record}}/></ActionDialog>{actions}</>}/><p>{version.content.question}</p><p className="context-line">Approach version {version.version_number} · {caseLabel}{!actions && <> <CaseContextLink target={{approach_version_id: selection.approach_version_id, case_id: selection.case_id}} returnKey={'configuration-case:' + selection.approach_version_id + ':' + (selection.case_id ?? 'none')} label={`View case in approach: ${selection.case_id === null ? 'no specific case' : caseLabel}, approach v${version.version_number}`}>View case in approach</CaseContextLink></>}</p></section>;
}

/** Presentation selection; the public configuration preview validates the exact pin. */
export function ConfigurationApproachPicker({api,studyId,model,value,onChange,onDirty,disabled}: {api:HyprnMvpApi;studyId:string;model:ModelRevisionRead4;value:ApproachSelection1|null;onChange:(value:ApproachSelection1|null)=>void;onDirty:(dirty:boolean)=>void;disabled?:boolean}) {
  const [opened,setOpened]=useState(false);
  const [record,setRecord]=useState<ApproachSavedRead3|null>(null),[error,setError]=useState('');
  const [versions,setVersions]=useState<ApproachVersionSummaryRead2[]>([]),[cursor,setCursor]=useState<ApproachCursor1|null>(null);
  const [choice,setChoice]=useState<ApproachSavedRead3|null>(null),[caseId,setCaseId]=useState(''),[loading,setLoading]=useState(false);
  const [recordRetry,setRecordRetry]=useState(false),[recordAttempt,setRecordAttempt]=useState(0);
  // Latest dialog read wins for display only; a denial is confirmed by the shared
  // session fence (study/actor/session/access epoch), never by this generation.
  const dialog=useRef<HTMLDialogElement>(null),generation=useRef(0),invoker=useRef<HTMLElement|null>(null),reads=useRef(new Set<ReadFence>());
  const dirty=opened&&(choice?.version.approach_version_id!==(value?.approach_version_id??undefined)||(caseId||null)!==(value?.case_id??null));
  useLayoutEffect(()=>{onDirty(dirty);return()=>onDirty(false);},[dirty,onDirty]);
  function fence(){const read=api.fence({studyId});reads.current.add(read);return {read,done:()=>{read.done();reads.current.delete(read);}};}
  /** Confirmed denial (by this picker, its host or any other host): clear protected displayed content only. The configuration's pin (`value`) is unchanged and nothing is submitted. */
  function clearProtected(){
    generation.current++;
    setRecord(null);setChoice(null);setVersions([]);setCursor(null);setCaseId('');setLoading(false);setRecordRetry(false);
    setError(accessLostText);
  }
  useAccessLoss(api,studyId,clearProtected);
  /** Shared classification; `latest` gates messages of superseded dialog reads, never the denial. */
  async function readFailed(error:unknown,read:ReadFence,latest:()=>boolean,onTransient?:()=>void){
    const outcome=await api.readFailed(error,read);
    if(outcome==='transient'&&latest()){setError(accessUnverifiedText);onTransient?.();}
    else if(outcome==='error'&&latest())setError(message(error));
  }
  useEffect(()=>{setRecord(null);setError('');setRecordRetry(false);if(!value)return;const {read,done}=fence();
    api.approachVersion(studyId,value.approach_version_id,read.signal).then(r=>{if(read.valid())setRecord(r);}).catch(e=>readFailed(e,read,()=>true,()=>setRecordRetry(true))).finally(done);
    return()=>{read.abort();done();};},[api,studyId,value?.approach_version_id,recordAttempt]);
  useEffect(()=>()=>{generation.current++;},[api,studyId,model.model_revision_id]);
  useEffect(()=>()=>{reads.current.forEach(read=>{read.abort();read.done();});reads.current.clear();},[]);
  const compatible=(r:ApproachSavedRead3)=>r.version.content.model_bindings.filter(b=>b.model_id===model.model_id&&b.model_revision_id===model.model_revision_id);
  async function load(more=false){const token=++generation.current,latest=()=>token===generation.current,{read,done}=fence();setLoading(true);setError('');try{const p=await api.approachVersions(studyId,{limit:20,...(more&&cursor?{cursor}:{})},read.signal);if(read.valid()&&latest()){setVersions(v=>more?[...v,...p.items]:p.items);setCursor(p.next_cursor);}}catch(e){await readFailed(e,read,latest);}finally{done();if(latest())setLoading(false);}}
  async function choose(id:string){const token=++generation.current,latest=()=>token===generation.current;setChoice(null);setCaseId('');setError('');if(!id)return;const {read,done}=fence();setLoading(true);try{const r=await api.approachVersion(studyId,id,read.signal);if(read.valid()&&latest())setChoice(r);}catch(e){await readFailed(e,read,latest);}finally{done();if(latest())setLoading(false);}}
  function close(){generation.current++;setLoading(false);setOpened(false);dialog.current?.close();invoker.current?.focus();}
  const mismatch=!!choice&&!compatible(choice).length;
  return <><ConfigurationApproachRecord selection={value} closure={record?.closure} actions={<><Button disabled={disabled} onClick={()=>{invoker.current=document.activeElement as HTMLElement;setOpened(true);setChoice(record);setCaseId(value?.case_id??'');dialog.current?.showModal();void load();}}>{value?'Change modeling approach':'Link modeling approach'}</Button>{value&&recordRetry&&<Button onClick={()=>setRecordAttempt(n=>n+1)}>Retry loading modeling approach</Button>}{value&&<Button disabled={disabled} onClick={()=>onChange(null)}>Remove approach link</Button>}</>}/>{error&&<p role="alert">{error}</p>}
    <DialogFrame ref={dialog} aria-labelledby="configuration-approach-title" onCancel={e=>{e.preventDefault();close();}}><h2 id="configuration-approach-title">Choose modeling approach</h2><div className="form-stack"><p>Choose a saved approach version that references this model version. Inputs and criteria remain unchanged.</p><label>Saved approach version<Select aria-label="Saved approach version" disabled={loading} value={choice?.version.approach_version_id??''} onChange={e=>void choose(e.target.value)}><option value="">Choose a version</option>{versions.map(v=><option key={v.approach_version_id} value={v.approach_version_id}>Approach version {v.version_number}</option>)}</Select></label>{cursor&&<Button disabled={loading} onClick={()=>void load(true)}>Load more approach versions</Button>}{choice&&<><p>{choice.version.content.question}</p>{mismatch?<p role="alert">This approach does not reference the configuration’s model version. Choose another approach version or remove the link; the model is not changed here.</p>:<label>Intended case<Select aria-label="Intended case" value={caseId} onChange={e=>setCaseId(e.target.value)}><option value="">No specific case</option>{choice.version.content.cases.filter(c=>compatible(choice).some(b=>b.binding_id===c.binding_id)).map(c=><option key={c.case_id} value={c.case_id}>{c.title}</option>)}</Select></label>}</>}{loading&&<p role="status">Loading saved approach…</p>}{error&&<p role="alert">{error}</p>}<div className="actions"><Button variant="primary" disabled={!choice||mismatch||loading} onClick={()=>{if(choice){onChange({approach_version_id:choice.version.approach_version_id,case_id:caseId||null});close();}}}>Use selected approach</Button><Button onClick={close}>Keep current choice</Button></div></div></DialogFrame>
  </>;
}
