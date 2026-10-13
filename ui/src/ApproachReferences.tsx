import { unitLabel } from './unitLabels';
import { useEffect, useRef, useState } from 'react';
import { Button, Checkbox, Select, StatusTag } from './design';
import { HyprnMvpApi, message } from './api';
import type { ApproachElementRef1, ApproachModelBinding1, ModelRevisionRead4 } from './contract';

export const referenceKey = (ref: ApproachElementRef1) => [ref.kind,ref.binding_id,'instance_id' in ref?ref.instance_id:'','port_id' in ref?ref.port_id:'','connection_id' in ref?ref.connection_id:''].join('/');
export function instanceName(model: ModelRevisionRead4, id: string) {
  const item=model.instances.find(i=>i.instance_id===id), peers=model.instances.filter(i=>i.name===item?.name);
  return item ? item.name+(peers.length>1 ? ` · instance ${peers.findIndex(i=>i.instance_id===id)+1}` : '') : 'Unavailable component';
}
export function modelLabel(model: ModelRevisionRead4) { return `${model.instances.find(i=>i.instance_id===model.root_instance_id)?.name ?? 'Model'} · version ${model.model_revision_id.slice(0,8)}`; }
export function elementOptions(model: ModelRevisionRead4, binding: ApproachModelBinding1) {
  const items:Array<{ref:ApproachElementRef1;label:string}>=[{ref:{kind:'model',binding_id:binding.binding_id},label:'Whole model'}];
  for(const instance of model.instances.filter(i=>i.instance_id!==model.root_instance_id)){
    items.push({ref:{kind:'instance',binding_id:binding.binding_id,instance_id:instance.instance_id},label:instanceName(model,instance.instance_id)});
    const ports=model.definitions.find(d=>d.definition_version_id===instance.definition_version_id)?.ports??[];
    for(const port of ports)items.push({ref:{kind:'port',binding_id:binding.binding_id,instance_id:instance.instance_id,port_id:port.port_id},label:`${instanceName(model,instance.instance_id)} · ${port.code_symbol} · ${port.direction} · ${unitLabel(port.units)}`});
  }
  const endpoint=(ref:{instance_id:string;port_id:string})=>{
    const instance=model.instances.find(i=>i.instance_id===ref.instance_id);
    const port=model.definitions.find(d=>d.definition_version_id===instance?.definition_version_id)?.ports.find(p=>p.port_id===ref.port_id);
    return `${instanceName(model,ref.instance_id)} · ${port ? `${port.code_symbol} · ${unitLabel(port.units)}` : 'Unavailable quantity'}`;
  };
  for(const connection of model.connections)items.push({ref:{kind:'connection',binding_id:binding.binding_id,connection_id:connection.connection_id},label:`${endpoint(connection.source_ref)} → ${endpoint(connection.target_ref)}`});
  return items;
}

/** The picker reads exact committed snapshots; its local selection is explanation
 * correspondence only and never changes model composition. */
export function ApproachReferencePicker({api,studyId,bindings,refs,onChange,disabled}:{api:HyprnMvpApi;studyId:string;bindings:ApproachModelBinding1[];refs:ApproachElementRef1[];onChange:(binding:ApproachModelBinding1,refs:ApproachElementRef1[])=>void;disabled:boolean}){
  const [models,setModels]=useState<Array<{id:string;name:string}>>([]),[mid,setMid]=useState(''),[versions,setVersions]=useState<Array<{model_revision_id:string}>>([]),[snapshot,setSnapshot]=useState<ModelRevisionRead4|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const generation=useRef(0);
  useEffect(()=>{const token=++generation.current,actor=api.actor;setLoading(true);void api.models(studyId).then(async items=>Promise.all(items.map(async item=>({id:item.model_id,name:(await api.model(studyId,item.model_id)).name})))).then(items=>{if(token===generation.current&&actor===api.actor){setModels(items);setLoading(false);}}).catch(e=>{if(token===generation.current&&actor===api.actor){setError(message(e));setLoading(false);}});return()=>{generation.current++;};},[api,studyId]);
  async function chooseModel(id:string){const token=++generation.current,actor=api.actor;setMid(id);setSnapshot(null);setVersions([]);setError('');if(!id)return;setLoading(true);try{const found=await api.revisions(studyId,id);if(token===generation.current&&actor===api.actor)setVersions(found);}catch(e){if(token===generation.current&&actor===api.actor)setError(message(e));}finally{if(token===generation.current)setLoading(false);}}
  async function chooseVersion(id:string){const token=++generation.current,actor=api.actor;setSnapshot(null);setError('');if(!id)return;setLoading(true);try{const found=await api.revision(studyId,mid,id);if(token===generation.current&&actor===api.actor)setSnapshot(found);}catch(e){if(token===generation.current&&actor===api.actor)setError(message(e));}finally{if(token===generation.current)setLoading(false);}}
  const newBinding=useRef<ApproachModelBinding1|null>(null);
  let binding=snapshot&&bindings.find(b=>b.model_id===snapshot.model_id&&b.model_revision_id===snapshot.model_revision_id);
  if(snapshot&&!binding){if(newBinding.current?.model_revision_id!==snapshot.model_revision_id)newBinding.current={binding_id:crypto.randomUUID(),model_id:snapshot.model_id,model_revision_id:snapshot.model_revision_id};binding=newBinding.current;}
  return <fieldset className="form-stack" disabled={disabled}><legend>Link model elements</legend><p>Choose a committed model version, then its components, quantities or connections. This does not modify the model.</p>
    <label>Model<Select aria-label="Implementation model" value={mid} onChange={e=>void chooseModel(e.target.value)}><option value="">Choose model</option>{models.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</Select></label>
    {mid&&<label>Model version<Select aria-label="Implementation model version" disabled={loading} value={snapshot?.model_revision_id??''} onChange={e=>void chooseVersion(e.target.value)}><option value="">Choose committed version</option>{versions.map(v=><option key={v.model_revision_id} value={v.model_revision_id}>{v.model_revision_id.slice(0,8)} (read-only)</option>)}</Select></label>}
    {loading&&<p role="status">Loading model references…</p>}{error&&<p role="alert">{error}</p>}
    {snapshot&&binding&&<div className="approach-reference-options" role="group" aria-label="Model elements">{elementOptions(snapshot,binding).map(item=><label key={referenceKey(item.ref)}><Checkbox checked={refs.some(ref=>referenceKey(ref)===referenceKey(item.ref))} onChange={e=>{const next=refs.filter(ref=>referenceKey(ref)!==referenceKey(item.ref));if(e.target.checked)next.push(item.ref);onChange(binding!,next);}} />{item.label}</label>)}</div>}
    {!!refs.length&&<p><StatusTag tone="inert">{refs.length} references selected</StatusTag></p>}
    {refs.map((ref,i)=><div key={referenceKey(ref)} className="approach-reference-row"><span>{ref.kind} · reference {i+1}{snapshot&&binding?.binding_id===ref.binding_id ? ` · ${elementOptions(snapshot,binding).find(item=>referenceKey(item.ref)===referenceKey(ref))?.label??'Unavailable reference'}`:''}</span><Button onClick={()=>{const owner=bindings.find(b=>b.binding_id===ref.binding_id);if(owner)onChange(owner,refs.filter((_,n)=>n!==i));}}>Remove reference {i+1}</Button></div>)}
  </fieldset>;
}
