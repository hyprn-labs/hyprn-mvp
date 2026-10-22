import { DialogActions } from './design';
import { quantityDefinitions } from './quantityDefinitions';
import { unitLabel } from './unitLabels';
import { DataTable } from './design';
import { Button, DialogFrame, SectionHeader } from './design';
import { useEffect, useRef, useState } from 'react';
import { ApiError, HyprnMvpApi, message, sourceText, validateEditCommand } from './api';
import type { ApplyRead4, ModelDraftRead4, ModelRevisionRead4, ConfigurationRevisionRead6, ConfigurationCandidate, ConfigurationCandidate6, ConfigurationPreview3, EvidenceSnapshot } from './api';
import { configurationContext, modelAssumptions, recordLimitations, recordedModelAssumptions, unreadableModelAssumptions, configurationCriteria } from './recordViews';

/** Assumption changes cannot be compared when either side's format is unreadable; say so. */
const unreadableAssumptions = (models: Array<ModelDraftRead4 | ModelRevisionRead4 | null>) => models.some(model => unreadableModelAssumptions(modelAssumptions(model)));
function UnreadableAssumptions({ models }: { models: Array<ModelDraftRead4 | ModelRevisionRead4 | null> }) {
  return unreadableAssumptions(models) ? <p>{recordLimitations.modelAssumptionsUnreadable} Assumption changes are not shown.</p> : null;
}
export type ChangeProposal = { before: ModelDraftRead4; command: ApplyRead4; invoker: HTMLElement | null; safe: string; apply: string; finish: (result: ModelDraftRead4 | null) => void };
function differences(before: ModelDraftRead4, after: ModelDraftRead4) {
  const rows: Array<{ id: string; label: string; before: string; after: string }> = [];
  const add = (id: string, label: string, a: string, b: string) => { if (a !== b) rows.push({ id, label, before: a || 'None', after: b || 'None' }); };
  if (before.name !== after.name) add('model', 'Model name', before.name, after.name);
  function name(snapshot: ModelDraftRead4, id: string) {
    const instance = snapshot.instances.find(i => i.instance_id === id), peers = snapshot.instances.filter(i => i.name === instance?.name);
    return (instance?.name ?? 'Unavailable component') + (peers.length > 1 ? ` · instance ${peers.findIndex(i => i.instance_id === id) + 1}` : '');
  }
  for (const id of new Set([...before.instances, ...after.instances].map(i => i.instance_id))) {
    const a = before.instances.find(i => i.instance_id === id), b = after.instances.find(i => i.instance_id === id);
    const ad = before.definitions.find(d => d.definition_version_id === a?.definition_version_id), bd = after.definitions.find(d => d.definition_version_id === b?.definition_version_id);
    const label = name(b ? after : before, id);
    if (!a || !b) add(id, 'Component', a ? label : 'Not present', b ? label : 'Removed');
    else add(id + '-name', 'Component name', a.name, b.name);
    const ports = (d: typeof ad) => d?.ports.map(p => `${p.direction}: ${p.name}${p.name === p.code_symbol ? '' : ` (${p.code_symbol})`} · ${unitLabel(p.units)}`).join('\n') ?? '';
    add(id + '-ports', label + ' · ports', ports(ad), ports(bd));
    const definitions = (model: ModelDraftRead4) => quantityDefinitions(model).filter(q => q.instance.instance_id === id).map(q => q.port.code_symbol + ': ' + (q.statement ?? 'No definition')).join('\n');
    add(id + '-definitions', label + ' · quantity definitions', definitions(before), definitions(after));
    if (a && b && JSON.stringify(ad?.source_refs) !== JSON.stringify(bd?.source_refs)) {
      const text = (m: ModelDraftRead4, d: typeof ad) => m.source_files.filter(s => d?.source_refs.includes(s.sha256)).map(sourceText).join('\n');
      add(id + '-source', label + ' · source', text(before, ad), text(after, bd));
    } else if (!a && bd?.source_refs.length) add(id + '-source', label + ' · source', '', 'Starter source — add output equations before running');
    // Notes (annotations) are not shown or authored in the UI; they stay in the record.
  }
  const endpoint = (m: ModelDraftRead4, ref: { instance_id: string; port_id: string }) => { const i = m.instances.find(i => i.instance_id === ref.instance_id); const p = m.definitions.find(d => d.definition_version_id === i?.definition_version_id)?.ports.find(p => p.port_id === ref.port_id); return `${name(m, ref.instance_id)} · ${p?.code_symbol ?? 'Unavailable port'}`; };
  for (const id of new Set([...before.connections, ...after.connections].map(c => c.connection_id))) {
    const format = (m: ModelDraftRead4) => { const c = m.connections.find(c => c.connection_id === id); return c ? `${endpoint(m, c.source_ref)} → ${endpoint(m, c.target_ref)}` : ''; };
    add(id, 'Connection', format(before), format(after));
  }
  // Unreadable formats are stated beside the table; their items are never compared as absent.
  const unreadable = unreadableAssumptions([before, after]);
  const aItems = unreadable ? [] : recordedModelAssumptions(modelAssumptions(before)), bItems = unreadable ? [] : recordedModelAssumptions(modelAssumptions(after));
  for (const id of new Set([...aItems, ...bItems].map(item => item.assumption_id))) {
    const a = aItems.find(item => item.assumption_id === id), b = bItems.find(item => item.assumption_id === id), item = b ?? a!;
    const owner = item.owner.kind === 'model' ? 'Model' : name(b ? after : before, item.owner.instance_id);
    add(id + '-statement', owner + ' · assumption', a?.statement ?? '', b?.statement ?? '');
    const links = (value: typeof a) => value?.evidence_links.map(link => (link.relation === 'supports' ? 'Supports' : link.relation === 'challenges' ? 'Challenges' : 'Context') + ' · ' + link.evidence_version_id).join('\n') ?? '';
    add(id + '-citations', owner + ' · assumption evidence', links(a), links(b));
  }
  return rows;
}
function DifferenceTable({ before, after }: { before: ModelDraftRead4; after: ModelDraftRead4 }) {
  return <><div className="table-scroll" tabIndex={0}><DataTable className="change-table"><thead><tr><th>Change</th><th>Before</th><th>After</th></tr></thead><tbody>{differences(before, after).map(row => <tr key={row.id}><th scope="row"><div className="exact-proposal">{row.label}</div></th><td><div className="exact-proposal">{row.before}</div></td><td><div className="exact-proposal">{row.after}</div></td></tr>)}</tbody></DataTable></div><UnreadableAssumptions models={[before, after]} /></>;
}

export function ChangePreview({ api, proposal }: { api: HyprnMvpApi; proposal: ChangeProposal }) {
  const dialog = useRef<HTMLDialogElement>(null), safe = useRef<HTMLButtonElement>(null);
  const initialFocus = useRef(true);
  const [command, setCommand] = useState(proposal.command), [base, setBase] = useState(proposal.before);
  const [preview, setPreview] = useState<ModelDraftRead4 | null>(null), [current, setCurrent] = useState<ModelDraftRead4 | null>(null);
  const [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false);
  useEffect(() => {
    const focus = proposal.invoker;
    dialog.current?.showModal(); safe.current?.focus();
    return () => { dialog.current?.close(); requestAnimationFrame(() => { if (focus?.isConnected) focus.focus(); }); };
  }, []);
  useEffect(() => {
    let live = true; setBusy(true); setPreview(null); setError(null);
    void api.previewEdits(base, command).then(value => { if (live) setPreview(value); }).catch(e => { if (live) setError(e); }).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [command, base, api]);
  useEffect(() => {
    if (!initialFocus.current || busy || (!preview && error == null)) return;
    initialFocus.current = false;
    // Disabling the initially focused safe action during the first read can
    // leave focus on the dialog/body. Do not override an explicit user move.
    if (document.activeElement === document.body || document.activeElement === dialog.current || document.activeElement === safe.current) safe.current?.focus();
  }, [busy, preview, error]);
  async function apply() {
    if (!preview || busy || api.pending) return;
    setBusy(true); setError(null);
    try { validateEditCommand(command, preview); proposal.finish(await api.applyCommand(base, command)); }
    catch (e) { setError(e); setPreview(null); }
    finally { setBusy(false); }
  }
  return (
    <DialogFrame
      ref={dialog}
      aria-labelledby="change-preview-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) proposal.finish(null);
      }}
      width="wide"
      className="change-preview"
    >
      <SectionHeader level={2} id="change-preview-title" title="Preview changes" help="model" />
      <p>Save these changes together. Existing configurations and runs stay unchanged.</p>
      {busy && <p role="status">Checking changes…</p>}
      {error != null && (
        <div role="alert">
          <p>{message(error)}</p>
          {error instanceof ApiError &&
            error.detail.fields.map((field, i) => (
              <p key={i}>
                {field.path}: {field.message}
              </p>
            ))}
        </div>
      )}
      {preview && <DifferenceTable before={base} after={preview} />}

      {error != null && !api.pending && (
        <Button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              setCurrent(await api.model(base.study_id, base.model_id));
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          Review current revision
        </Button>
      )}
      {current && (
        <section aria-label="Current revision differences">
          <h3>Current revision differences</h3>
          <p>{current.draft_revision}</p>
          <DifferenceTable before={base} after={current} />
          <Button
            disabled={busy || !!api.pending}
            onClick={() => {
              setBase(current);
              setCommand({
                ...command,
                command_id: crypto.randomUUID(),
                expected_revision: current.draft_revision,
              });
              setCurrent(null);
            }}
          >
            Re-preview preserved proposal
          </Button>
          <p>
            Re-preview keeps every proposed edit and its explicit definition/version references.
            Incompatible references must be corrected in the editor.
          </p>
        </section>
      )}
      {api.pending && (
        <p>
          Check the original command in command recovery. This proposal cannot submit a second
          command while its outcome is uncertain.
        </p>
      )}
      <DialogActions
        primary={
          <Button
            variant="primary"
            disabled={busy || !preview || !!api.pending}
            onClick={() => void apply()}
          >
            {proposal.apply}
          </Button>
        }
      >
        <Button ref={safe} disabled={busy} onClick={() => proposal.finish(null)}>
          {proposal.safe}
        </Button>
      </DialogActions>
    </DialogFrame>
  );
}

type HumanChange = { id: string; label: string; before: string; after: string; evidence?: boolean };
const relationship = (value: string) => value === 'supports' ? 'Supports' : value === 'challenges' ? 'Challenges' : 'Context';
const evidenceLabel = (records: EvidenceSnapshot[], id: string) => {
  const record = records.find(e => e.evidence_version_id === id);
  return (record && 'title' in record ? record.title : record ? 'Evidence note' : 'Evidence unavailable') + ' · Version ' + id;
};
export const evidenceUseChange = (path: string) => /^\/(inputs|criteria)\/\d+\/(provenance\/)?evidence_version_ids(?:\/|$)/.test(path);
function HumanChanges({rows, label}: {rows: HumanChange[]; label: string}) {
  const value = (text: string, evidence?: boolean) => !text ? 'None' : !evidence ? text : text.split(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i).map((part,index) => index % 2 ? <abbr key={index} title={part}>{part.slice(0,8)}</abbr> : part);
  return <DataTable regionLabel={label}><thead><tr><th>Changed field</th><th>Before</th><th>After</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><th>{row.label}</th><td className="exact-proposal">{value(row.before,row.evidence)}</td><td className="exact-proposal">{value(row.after,row.evidence)}</td></tr>)}</tbody></DataTable>;
}

/** Format only server-reported stable owner/use changes, with exact retained titles. */
export function ConfigurationChanges({before,after,changes,model}: {before: ConfigurationRevisionRead6; after: ConfigurationCandidate | ConfigurationCandidate6; changes: ConfigurationPreview3['changes']; model?: ModelRevisionRead4}) {
  const evidence = (value: typeof before | typeof after, id: string) => evidenceLabel(value.evidence_snapshots,id);
  // Every format that records assumptions and explicit general context (Configuration3 and 4) is read.
  const assumption = (value: typeof before | typeof after, id: string) => { const context = configurationContext(value); return context.kind === 'supported' && context.assumptions.kind === 'recorded' ? context.assumptions.items.find(a => a.assumption_id === id) : undefined; };
  const generalContext = (value: typeof before | typeof after) => { const context = configurationContext(value); return context.kind === 'supported' && context.generalContext.kind === 'explicit' ? context.generalContext.evidenceVersionIds : []; };
  const rows: HumanChange[] = [];
  for (const id of new Set(changes.filter(c => c.path.startsWith('/assumptions/')).map(c => c.path.split('/')[2]))) {
    const a = assumption(before,id), b = assumption(after,id);
    if (a?.statement !== b?.statement) rows.push({id, label:'Configuration assumption',before:a?.statement ?? '',after:b?.statement ?? ''});
    const links = (value: typeof before | typeof after, item: typeof a) => item?.evidence_links.map(link => relationship(link.relation) + ' · ' + evidence(value,link.evidence_version_id)).join('\n') ?? '';
    if (links(before,a) !== links(after,b)) rows.push({evidence:true,id:id+'/links',label:'Evidence for ' + (b?.statement ?? a?.statement ?? 'assumption'),before:links(before,a),after:links(after,b)});
  }
  for (const change of changes.filter(c => c.path.startsWith('/general_context_evidence_version_ids/'))) {
    const id=change.path.split('/')[2];
    rows.push({evidence:true,id:change.path,label:'General context evidence',before:generalContext(before).includes(id) ? evidence(before,id) : '',after:generalContext(after).includes(id) ? evidence(after,id) : ''});
  }
  for (const path of new Set(changes.filter(c => evidenceUseChange(c.path)).map(c => c.path.split('/').slice(0,3).join('/')))) {
    const [,kind,index]=path.split('/');
    const item=kind==='inputs' ? after.inputs[Number(index)] ?? before.inputs[Number(index)] : configurationCriteria(after)[Number(index)] ?? configurationCriteria(before)[Number(index)];
    const instance=model?.instances.find(i=>i.instance_id===item?.target.instance_id);
    const port=model?.definitions.find(d=>d.definition_version_id===instance?.definition_version_id)?.ports.find(p=>p.port_id===item?.target.port_id);
    const labels=(value: typeof before | typeof after) => (kind==='inputs' ? value.inputs[Number(index)]?.provenance.evidence_version_ids : configurationCriteria(value)[Number(index)]?.evidence_version_ids)?.map(id=>evidence(value,id)).join('\n') ?? '';
    rows.push({evidence:true,id:path,label:(kind==='inputs' ? 'Input' : 'Criterion')+' evidence · '+(instance?.name ?? 'Component')+' · '+(port?.name ?? 'Output'),before:labels(before),after:labels(after)});
  }
  return rows.length ? <HumanChanges rows={rows} label="Assumption and evidence changes" /> : null;
}

export function ModelAssumptionChanges({before,after,beforeEvidence=[],afterEvidence=[]}: {before: ModelRevisionRead4 | null; after: ModelRevisionRead4; beforeEvidence?: EvidenceSnapshot[]; afterEvidence?: EvidenceSnapshot[]}) {
  const unreadable=unreadableAssumptions([before,after]);
  const a=unreadable ? [] : recordedModelAssumptions(modelAssumptions(before)), b=unreadable ? [] : recordedModelAssumptions(modelAssumptions(after));
  const rows: HumanChange[]=[];
  for (const id of new Set([...a,...b].map(item=>item.assumption_id))) {
    const old=a.find(item=>item.assumption_id===id), next=b.find(item=>item.assumption_id===id), item=next ?? old!;
    const source=next ? after : before;
    const owner=item.owner.kind === 'model' ? 'Model' : source?.instances.find(i=>item.owner.kind === 'instance' && i.instance_id===item.owner.instance_id)?.name ?? 'Component';
    const links=(value:typeof old,records:EvidenceSnapshot[])=>value?.evidence_links.map(link=>relationship(link.relation)+' · '+evidenceLabel(records,link.evidence_version_id)).join('\n') ?? '';
    if(old?.statement !== next?.statement) rows.push({id,label:owner+' · assumption',before:old?.statement ?? '',after:next?.statement ?? ''});
    if(JSON.stringify(old?.evidence_links ?? [])!==JSON.stringify(next?.evidence_links ?? [])) rows.push({evidence:true,id:id+'/links',label:owner+' · assumption evidence',before:links(old,beforeEvidence),after:links(next,afterEvidence)});
  }
  return <section aria-label="Model assumption changes"><h3>Model assumption changes</h3>{unreadable ? <UnreadableAssumptions models={[before, after]} /> : rows.length ? <HumanChanges rows={rows} label="Model assumption changes" /> : <p>No model assumption changes.</p>}</section>;
}
