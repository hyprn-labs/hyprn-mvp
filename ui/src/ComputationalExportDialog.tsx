import { useEffect, useId, useRef, useState } from 'react';
import { ApiError, HyprnMvpApi, accessLostText, accessUnverifiedText } from './api';
import { useAccessLoss } from './accessLoss';
import type { Diagnostic, PublicReceipt, RecordCreateRequest, RecordPreviewRequest, RecordRequestRead as RecordRequest, RunLabel } from './api';
import { Button, DialogFrame, Disclosure, Progress, StatusTag } from './design';

type Command = { kind:'preview'; body:RecordPreviewRequest } | { kind:'create'; body:RecordCreateRequest };
const omissionLabels:Record<string,string>={authinfos:'Authentication information',comments:'Administrative comments',logs:'Administrative logs',process_checkpoints:'Process checkpoints'};
const pending = (record:RecordRequest|null) => record?.state === 'queued' || record?.state === 'building';
function blocker(code?:string, fields:Diagnostic[] = []) {
  if (code === 'limit_exceeded' && fields.length) return fields.map(field => field.message).join(' ');
  if (code === 'reference_conflict') return 'The record changed since review. Review the record again before creating the record export.';
  if (code === 'resource_not_found' || code === 'forbidden') return 'This record is no longer available to you. No record export was downloaded.';
  if (code === 'limit_exceeded') return 'The record exceeds the export limits, or too many requests are waiting. No record export was created.';
  if (code === 'unsafe_export') return 'Material from this run could not pass the export safety checks. No record export was created.';
  if (code === 'incomplete_record' || code === 'record_incomplete') return 'Required material is missing or could not be verified. No record export was created.';
  return 'The record could not be prepared. Your selection is preserved; check the request or review again.';
}
function RunList({title,items,empty}:{title:string;items:RunLabel[];empty:string}) {
  return <section aria-label={title}><h4>{title} ({items.length})</h4>{items.length ? <ul>{items.map(item=><li key={item.run_id}>{item.name || 'Unnamed run'}</li>)}</ul> : <p>{empty}</p>}</section>;
}

/** Closing preserves accepted work and command identity; it never cancels a job. */
export function ComputationalExportDialog({api,studyId,runId,name}:{api:HyprnMvpApi;studyId:string;runId:string;name:string}) {
  const dialog=useRef<HTMLDialogElement>(null), trigger=useRef<HTMLButtonElement>(null), mounted=useRef(true), working=useRef(false);
  const heading=useId();
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[record,setRecord]=useState<RecordRequest|null>(null),[review,setReview]=useState<RecordRequest|null>(null);
  const [command,setCommand]=useState<Command|null>(null),[uncertain,setUncertain]=useState(false),[error,setError]=useState(''),[readFailed,setReadFailed]=useState(false),[needsReview,setNeedsReview]=useState(false);
  const [pollAttempt,setPollAttempt]=useState(0);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  /** A denial confirmed by any host of this study clears the reviewed record and stops polling. */
  useAccessLoss(api,studyId,change=>{if(change.kind!=='access-lost')return;setRecord(null);setReview(null);setNeedsReview(false);setReadFailed(true);setError(accessLostText);});
  useEffect(()=>{if(open)dialog.current?.showModal();else dialog.current?.close();},[open]);
  function accept(value:RecordRequest) { setRecord(value);setUncertain(false);setReadFailed(false);setError('');if(value.kind==='preview'&&value.state==='reviewable')setReview(value); }
  useEffect(()=>{
    if(!open||!pending(record)||readFailed)return;
    let cancelled=false;let timer:ReturnType<typeof setTimeout>;
    const read=api.fence({studyId});
    async function poll(){
      try {const value=await api.computationalRecord(studyId,record!.request_id,read.signal);if(!cancelled&&read.valid())accept(value);}
      catch(failure){
        // One classification with the run's other reads. A confirmed denial clears through
        // the session signal; a transient study probe keeps the request and polls again.
        const outcome=await api.readFailed(failure,read);
        if(cancelled)return;
        if(outcome==='transient'){setError(accessUnverifiedText);setPollAttempt(n=>n+1);}
        else if(outcome==='error'){setReadFailed(true);setError(failure instanceof ApiError?blocker(failure.detail.code, failure.detail.fields):'Status could not be checked. The original request is preserved.');}
      }
      finally{read.done();}
    }
    timer=setTimeout(()=>void poll(),1000);
    return()=>{cancelled=true;clearTimeout(timer);read.abort();read.done();};
  },[api,studyId,open,record,readFailed,pollAttempt]);
  async function perform(action:()=>Promise<void>){
    if(working.current)return;working.current=true;setBusy(true);setError('');const actor=api.actor;
    try{await action();}catch(failure){if(mounted.current&&api.actor===actor)setError(failure instanceof ApiError?blocker(failure.detail.code, failure.detail.fields):failure instanceof Error?failure.message:'This request could not be completed.');}
    finally{working.current=false;if(mounted.current&&api.actor===actor)setBusy(false);}
  }
  async function send(next:Command){
    setCommand(next);const actor=api.actor;
    try{const value=next.kind==='preview'?await api.previewComputationalRecord(studyId,next.body):await api.createComputationalRecord(studyId,next.body);if(mounted.current&&api.actor===actor)accept(value);}
    catch(failure){if(mounted.current&&api.actor===actor){setUncertain(api.pending?.body.command_id===next.body.command_id);if(failure instanceof ApiError&&failure.detail.code==='reference_conflict')setNeedsReview(true);}throw failure;}
  }
  function newReview(){void perform(async()=>{setNeedsReview(false);setReview(null);setRecord(null);setReadFailed(false);await send({kind:'preview',body:{command_id:crypto.randomUUID(),selected_run_ids:[runId]}});});}
  async function receipt(){
    if(!command)return;
    const id=command.body.command_id,category='computational_record_'+command.kind;
    // A global recovery control may already have reconciled this command.
    const value=api.pending?.body.command_id===id?await api.reconcile():(await api.request<PublicReceipt>(`/studies/${studyId}/commands/${id}?category=${category}`)).data;
    if(!mounted.current)return;
    if(value?.result&&'request_id' in value.result)accept(value.result);
    else if(value?.state==='rejected'){setUncertain(false);setError(blocker(value.error?.code, value.error?.fields));}
  }
  function primary(){
    if(needsReview||!record||record.state==='failed'){newReview();return;}
    if(record.state==='reviewable'&&review?.preview){void perform(()=>send({kind:'create',body:{command_id:crypto.randomUUID(),preview_id:review.request_id,expected_preview_digest:review.preview!.preview_digest}}));return;}
    if(record.state==='ready'&&record.download)void perform(async()=>{
      let blob:Blob;const read=api.fence({studyId});
      try{blob=await api.downloadComputationalRecord(studyId,record.request_id,record.download!);}
      catch(failure){
        // The package read is classified like every other read of this run.
        const outcome=await api.readFailed(failure,read);
        if(outcome==='access-lost'||outcome==='stale')return;
        if(outcome==='transient')throw new Error(accessUnverifiedText);
        if(mounted.current&&failure instanceof ApiError&&['forbidden','resource_not_found'].includes(failure.detail.code))setReadFailed(true);throw failure;}
      finally{read.done();}
      if(!read.valid())return;
      if(!mounted.current)return;
      const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='hyprn-mvp-computational-record.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
  }
  const preview=record?.preview??review?.preview;
  const approach = record?.preview ? (record.schema_version === '2' ? record.preview.approach_summary : null) : review?.schema_version === '2' ? review.preview?.approach_summary : null;
  const waiting=pending(record),failed=record?.state==='failed';
  const label=needsReview?'Review again':record?.state==='ready'?'Download record export':record?.state==='reviewable'?'Create record export':waiting?'Waiting for record':record||command?'Review again':'Review record';
  return <><Button ref={trigger} aria-haspopup="dialog" onClick={()=>setOpen(true)}>Export computational record</Button>
    <DialogFrame ref={dialog} className="action-dialog" aria-labelledby={heading} onKeyDown={event=>{
      if(event.key!=='Tab')return;
      const controls=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), summary, [href], [tabindex="0"]')).filter(element=>element.getClientRects().length>0);
      const first=controls[0],last=controls[controls.length-1];
      if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    }} onCancel={event=>{event.preventDefault();setOpen(false);}} onClose={()=>{setOpen(false);trigger.current?.focus();}}>
      <header className="dialog-heading"><h2 id={heading}>Export computational record</h2></header>
      <div className="dialog-body">
        {!preview&&<><p><strong>{name||'Unnamed run'}</strong></p><p>Review the computation, its upstream dependencies and scientific context before creating the record export.</p></>}
        {waiting&&!readFailed&&<Progress label={record?.state==='queued'?'Queued':'Building record'} message="Waiting to prepare the record. Closing this dialog does not cancel the request."/>}
        {record&&!waiting&&<p role="status"><StatusTag tone={readFailed?'warning':failed?'alarm':'ok'}>{readFailed?'Status needs checking':failed?'Export failed':record.state==='ready'?'Ready to download':'Review ready'}</StatusTag></p>}
        {preview&&<>
          <h3>Included computations</h3>
          <RunList title="Selected runs" items={preview.selected} empty="No selected runs."/>
          <RunList title="Computational ancestors" items={preview.computational_ancestors} empty="No additional computational dependencies."/>
          <RunList title="Configuration origins" items={preview.derivation_context_only} empty="No separate configuration origins."/>
          {preview.derivation_context_only.length>0&&<p>Configuration origins provide context for changes; their full computation artifacts are not included.</p>}
          <p>{preview.context_count} context records · {preview.evidence_count} evidence records</p>
          {approach&&<section aria-label="Included modeling approach"><h3>Modeling approach</h3><dl className="hf-record-details"><dt>Saved approach versions</dt><dd>{approach.approach_version_ids.length}</dd><dt>Referenced model versions</dt><dd>{approach.model_count}</dd><dt>Evidence versions</dt><dd>{approach.evidence_count}</dd><dt>Earlier-work configurations</dt><dd>{approach.basis_configuration_ids.length}</dd><dt>Earlier-work runs</dt><dd>{approach.basis_run_ids.length}</dd></dl><p>Includes the approach explanation and the records it references. Earlier work provides scientific context; it does not add execution artifacts or establish valid numerical inputs.</p></section>}
          <h3>Computational record export</h3><p>Inspection only. Runtime portability is unverified.</p>
          <p>{preview.reexecution_prerequisites.retained_material_complete?'All material is included. Running it again would need separate runtime verification.':'Prerequisites for later re-execution have not been established.'}</p>
          <p>Limits: {preview.limits.selected_runs} selected runs, {preview.limits.computational_runs} computations, {preview.limits.logical_paths} files, {preview.limits.expanded_bytes/1048576} MiB expanded.</p>
          {preview.omissions.length>0&&<section aria-label="Omissions"><h4>Omitted from the record export</h4><ul>{preview.omissions.map(item=><li key={item}>{omissionLabels[item]??item.replaceAll('_',' ')}</li>)}</ul></section>}
          {preview.blockers.length>0&&<section role="alert"><h4>Cannot create this record export</h4><ul>{preview.blockers.map((item,index)=><li key={index}>{item.message}</li>)}</ul></section>}
        </>}
        {(error||failed)&&<p role="alert">{error||blocker(record?.error?.code, record?.error?.fields)}</p>}
        {uncertain&&<><p>The command outcome is uncertain. Check the original command before trying again.</p><Button disabled={busy} onClick={()=>void perform(receipt)}>Check original export command</Button>{api.retryReady&&api.pending?.body.command_id===command?.body.command_id&&<Button disabled={busy} onClick={()=>void perform(async()=>{await api.retryOriginal();await receipt();})}>Retry original export command</Button>}</>}
        {readFailed&&record&&<Button disabled={busy} onClick={()=>void perform(async()=>accept(await api.computationalRecord(studyId,record.request_id)))}>Check request status</Button>}
        <Disclosure><summary>Details</summary><dl className="hf-record-details"><dt>Selected run</dt><dd>{runId}</dd>{command&&<><dt>Original command</dt><dd>{command.body.command_id}</dd></>}{record&&<><dt>Request</dt><dd>{record.request_id}</dd></>}{preview&&<><dt>Calculation archive limit</dt><dd>{preview.limits.native_archive_bytes/1048576} MiB</dd><dt>Record export size limit</dt><dd>{preview.limits.wrapper_bytes/1048576} MiB</dd><dt>Per-file limit</dt><dd>{preview.limits.per_file_bytes/1048576} MiB</dd><dt>Inventory limit</dt><dd>{preview.limits.inventory_bytes/1048576} MiB</dd><dt>Metadata limit</dt><dd>{preview.limits.metadata_bytes/1048576} MiB</dd><dt>Reviewed inventory</dt><dd>{preview.inventory_digest}</dd><dt>Preview SHA-256</dt><dd>{preview.preview_digest}</dd>{[...preview.selected,...preview.computational_ancestors,...preview.derivation_context_only].map(item=><div key={item.run_id}><dt>{item.name||'Unnamed run'}</dt><dd>Run {item.run_id}<br/>Model version {item.model_revision_id}</dd></div>)}</>}{record?.download&&<><dt>Record export SHA-256</dt><dd>{record.download.sha256}</dd><dt>Record export size (bytes)</dt><dd>{record.download.size}</dd></>}</dl></Disclosure>
      </div>
      <footer className="dialog-footer section-actions"><Button onClick={()=>setOpen(false)}>Close</Button><Button variant="primary" disabled={busy||waiting||uncertain||readFailed||!!api.pending||!!preview?.blockers.length} onClick={primary}>{label}</Button></footer>
    </DialogFrame></>;
}
