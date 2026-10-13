import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { SectionHeader, Button, Panel, Select, TextArea, TextInput, StatusTag, DialogFrame } from './design';
import { ApiError, HyprnMvpApi, accessLostText, message, type EvidenceRecord, type EvidenceResourceRef1, type EvidenceCreate3, type EvidenceRevise3, type ModelRevisionRead4, type ConfigurationRevision } from './api';
import { EvidenceRecordBody, evidenceAccessLost, evidenceTitle } from './EvidenceView';
import { cleanGuard, type EditorGuard, type WorkspaceLink } from './workspaceModel';
import { EvidenceIndex, useCurrentAssumptions } from './EvidenceIndex';
import { useAccessLoss } from './accessLoss';
export { EvidenceRecordBody } from './EvidenceView';
export type EvidenceScopeOption = { label: string; scope: EvidenceResourceRef1 };
type Draft = { title: string; content: string; refs: string; scope: EvidenceResourceRef1; expected?: string; command?: EvidenceCreate3 | EvidenceRevise3; saved?: EvidenceRecord; stale: boolean; revoked: boolean };
const uncertainMessage = 'The evidence may already be saved. Check the original command before trying again.';
// In-memory only, isolated by API/session/study/owner. Commands survive dialog unmount without retargeting.
const drafts = new WeakMap<HyprnMvpApi, Map<string, Draft>>();
export function EvidenceEditor({ api, studyId, ownerKey, scopes, record, onSaved, onHandle, onUnavailable }: {
  api: HyprnMvpApi; studyId: string; ownerKey: string; scopes: EvidenceScopeOption[]; record?: EvidenceRecord;
  onSaved: (record: EvidenceRecord) => void; onHandle: (handle: EditorGuard) => void; onUnavailable?: () => void;
}) {
  const actor = api.actor, key = JSON.stringify([actor, studyId, ownerKey, record?.evidence_version_id ?? 'new']);
  if (!drafts.has(api)) drafts.set(api, new Map());
  const cache = drafts.get(api)!;
  if (!cache.has(key)) cache.set(key, { title: record && 'title' in record ? record.title : '', content: record?.content ?? '', refs: record?.source_refs.join('\n') ?? '', scope: record && 'resource_scope' in record ? record.resource_scope : scopes[0].scope, expected: record?.evidence_version_id, stale: false, revoked: false });
  const [draft] = useState(() => cache.get(key)!);
  const unresolved = [...cache.entries()].some(([owner, value]) => JSON.parse(owner)[0] === actor && !!value.command);
  const [, render] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState(''), [latest, setLatest] = useState<EvidenceRecord | null>(null);
  const controller = useRef<AbortController | null>(null), generation = useRef(0), locked = useRef(false), form = useRef<HTMLFieldSetElement>(null);
  const callbacks = useRef({ onSaved, onUnavailable }); callbacks.current = { onSaved, onUnavailable };
  const update = () => render(n => n + 1);
  const dirty = !draft.saved && (!!draft.command || draft.title !== (record && 'title' in record ? record.title : '') || draft.content !== (record?.content ?? '') || draft.refs !== (record?.source_refs.join('\n') ?? '') || JSON.stringify(draft.scope) !== JSON.stringify(record && 'resource_scope' in record ? record.resource_scope : scopes[0].scope));
  useEffect(() => { if (draft.saved) callbacks.current.onSaved(draft.saved); return () => { generation.current++; controller.current?.abort(); }; }, [key]);
  function revoke() { draft.title = ''; draft.content = ''; draft.refs = ''; draft.saved = undefined; draft.revoked = true; setLatest(null); callbacks.current.onUnavailable?.(); }
  async function perform(action: (signal: AbortSignal) => Promise<EvidenceRecord | null>) {
    if (locked.current || draft.revoked) return false;
    locked.current = true; setBusy(true); setError(''); controller.current = new AbortController(); const token = generation.current;
    try {
      const saved = await action(controller.current.signal);
      if (actor !== api.actor || token !== generation.current) return false;
      if (saved) { draft.command = undefined; draft.saved = saved; cache.delete(key); callbacks.current.onSaved(saved); }
      update(); return !!saved;
    } catch (e) {
      if (actor === api.actor && token === generation.current) {
        if (evidenceAccessLost(e)) { revoke(); setError('Access to this evidence is no longer available. Choose another record or remove the attachment.'); }
        else if (e instanceof ApiError && e.detail.code === 'stale_revision') { draft.command = undefined; draft.stale = true; setError('A newer evidence version was saved. Your edits are kept. Review the latest version before saving.'); }
        else if (draft.command && api.pending?.body.command_id === draft.command.command_id) setError(uncertainMessage);
        else { draft.command = undefined; setError('Evidence was not saved. Your edits are kept. Correct the reported fields and try again. ' + message(e)); }
        update();
      }
      return false;
    } finally { locked.current = false; if (token === generation.current) setBusy(false); }
  }
  async function save() {
    if (draft.saved) return true;
    if (unresolved || draft.stale || api.pending || draft.revoked) return false;
    const invalid = !draft.title.trim() ? 'Enter a title.' : !draft.content.trim() ? 'Enter an evidence note.' : '';
    const refs = draft.refs ? draft.refs.split('\n') : [];
    const limits = draft.title.length > 200 || draft.content.length > 4096 || refs.length > 1000 || refs.some(ref => ref.length > 4096);
    if (invalid || limits) { setError(invalid || 'Title: at most 200 characters. Evidence note and each source reference: at most 4096 characters; at most 1000 references.'); form.current?.querySelector<HTMLInputElement | HTMLTextAreaElement>(!draft.title.trim() ? 'input' : 'textarea')?.focus(); return false; }
    return perform(async signal => {
      const command: EvidenceCreate3 = { command_id: crypto.randomUUID(), evidence_schema_version: '3', title: draft.title, content: draft.content, source_refs: refs, resource_scope: structuredClone(draft.scope), kind: 'note' };
      draft.command = record ? { ...command, expected_revision: draft.expected! } : command; update();
      return record ? api.reviseEvidence(studyId, record.evidence_id, draft.command as EvidenceRevise3, signal) : api.createEvidenceCommand(studyId, command, signal);
    });
  }
  async function recover(retry = false) {
    return perform(async signal => {
      const id = draft.command?.command_id; if (!id) return null;
      if (retry) await api.retryOriginal();
      // Reconcile only the matching original; an unrelated owner command is never consumed.
      if (api.pending?.body.command_id === id) await api.reconcile();
      if (api.pending?.body.command_id === id && api.retryReady) { setError(uncertainMessage); return null; }
      const receipt = await api.evidenceReceipt(studyId, id, signal);
      if (receipt.state === 'committed' && receipt.result) return receipt.result;
      if (receipt.state === 'rejected') { draft.command = undefined; draft.stale = receipt.error?.code === 'stale_revision'; throw new Error('The original evidence command was rejected. Your edits are kept.'); }
      throw new Error('The original evidence command is not yet resolved.');
    });
  }
  async function review() {
    await perform(async signal => { const family = await api.evidenceFamily(studyId, record!.evidence_id, signal); setLatest(family.head); return null; });
  }
  function discard() {
    if (draft.command) return;
    draft.title = record && 'title' in record ? record.title : ''; draft.content = record?.content ?? ''; draft.refs = record?.source_refs.join('\n') ?? ''; draft.scope = record && 'resource_scope' in record ? record.resource_scope : scopes[0].scope;
    draft.saved = undefined; draft.stale = false; draft.expected = record?.evidence_version_id; setError(''); setLatest(null); update();
  }
  useLayoutEffect(() => { onHandle({ dirty, save, discard }); });
  const options = scopes.some(option => JSON.stringify(option.scope) === JSON.stringify(draft.scope)) ? scopes : [{ label: 'Context of this version', scope: draft.scope }, ...scopes];
  return <>
    {record && <p>Saving creates a new evidence version. Existing attachments keep the version they cite.</p>}
    {busy && <p role="status"><StatusTag tone="running">{record ? 'Saving new version…' : 'Saving evidence…'}</StatusTag></p>}
    {error && error !== uncertainMessage && <p role="alert">{error}</p>}
    {draft.command && !busy && !draft.revoked && <aside className="evidence-recovery"><StatusTag tone="warning">Outcome uncertain</StatusTag><p role="alert">{uncertainMessage}</p><Button onClick={() => void recover()}>Check original command</Button>{api.retryReady && api.pending?.body.command_id === draft.command.command_id && <Button onClick={() => void recover(true)}>Retry original command</Button>}</aside>}
    {draft.stale && !draft.revoked && <><Button disabled={busy} onClick={() => void review()}>Review latest version</Button>{latest && <section aria-label="Latest evidence version"><EvidenceRecordBody record={latest} /><p>Your edited title, note, references and context are kept. Review them against this version before reapplying.</p><Button disabled={busy} onClick={() => { draft.expected = latest.evidence_version_id; draft.stale = false; setLatest(null); setError(''); update(); }}>Reapply edits to this version</Button></section>}</>}
    {!draft.revoked && !draft.saved && <fieldset ref={form} className="form-stack" disabled={busy || !!api.pending || unresolved}>
      <label>Title<TextInput aria-label="Title" autoFocus value={draft.title} maxLength={200} onChange={e => { draft.title = e.target.value; update(); }} /></label>
      <label>Evidence note<TextArea aria-label="Evidence note" value={draft.content} maxLength={4096} onChange={e => { draft.content = e.target.value; update(); }} /></label>
      <label>Source references<TextArea aria-label="Source references" value={draft.refs} onChange={e => { draft.refs = e.target.value; update(); }} /></label><p>Source references are inert text, one per line.</p>
      <label>Context<Select aria-label="Context" value={JSON.stringify(draft.scope)} onChange={e => { draft.scope = options.find(option => JSON.stringify(option.scope) === e.target.value)!.scope; update(); }}>{options.map(option => <option key={JSON.stringify(option.scope)} value={JSON.stringify(option.scope)}>{option.label}</option>)}</Select></label>
      <Button variant="primary" disabled={draft.stale} onClick={() => void save()}>{record ? 'Save new version' : 'Create evidence'}</Button>
    </fieldset>}
    {(api.pending || unresolved) && !draft.command && <p>Check the original command before making more changes.</p>}
  </>;
}

/** Evidence page: current assumptions by owner, then the sources library. */
export function EvidencePanel({ api, studyId, snapshot, configuration, runId, onRecords, onHandle, onOpen }: { api: HyprnMvpApi; studyId: string; snapshot?: ModelRevisionRead4 | null; configuration?: ConfigurationRevision | null; runId?: string; records?: EvidenceRecord[]; onRecords: (records: EvidenceRecord[]) => void; onHandle: (handle: EditorGuard) => void; onOpen?: (target: WorkspaceLink) => void }) {
  const index = useCurrentAssumptions(api, studyId, onOpen);
  const [records, setRecords] = useState<EvidenceRecord[]>([]), [cursor, setCursor] = useState<string | null>(null), [filter, setFilter] = useState('');
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [editing, setEditing] = useState<EvidenceRecord | 'new' | null>(null), [discarding, setDiscarding] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null), invoker = useRef<HTMLElement | null>(null), request = useRef<AbortController | null>(null), generation = useRef(0);
  const handle = useRef<EditorGuard>(cleanGuard()), callback = useRef(onRecords); callback.current = onRecords;
  const actor = api.actor, common = { scope_version: '1' as const, study_id: studyId };
  const scopes: EvidenceScopeOption[] = [{ label: 'Study', scope: { ...common, kind: 'study' } }];
  if (snapshot) {
    const model = { ...common, model_id: snapshot.model_id, model_revision_id: snapshot.model_revision_id };
    scopes.push({ label: 'Model version', scope: { ...model, kind: 'model_revision' } });
    snapshot.definitions.forEach(d => scopes.push({ label: 'Definition ' + d.name, scope: { ...model, kind: 'definition_version', definition_id: d.definition_id, definition_version_id: d.definition_version_id } }));
    snapshot.instances.forEach(i => { scopes.push({ label: 'Component ' + i.name, scope: { ...model, kind: 'instance', instance_id: i.instance_id } }); snapshot.definitions.find(d => d.definition_version_id === i.definition_version_id)?.ports.forEach(p => scopes.push({ label: 'Quantity ' + i.name + ' · ' + p.name, scope: { ...model, kind: 'port', instance_id: i.instance_id, port_id: p.port_id } })); });
    snapshot.connections.forEach(c => scopes.push({ label: 'Connection ' + c.connection_id.slice(0, 8), scope: { ...model, kind: 'connection', connection_id: c.connection_id } }));
  }
  if (configuration) { scopes.push({ label: 'Configuration version', scope: { ...common, kind: 'configuration', configuration_revision_id: configuration.configuration_revision_id } }); configuration.criteria.forEach(c => scopes.push({ label: 'Criterion ' + c.criterion_id.slice(0, 8), scope: { ...common, kind: 'criterion', configuration_revision_id: configuration.configuration_revision_id, criterion_id: c.criterion_id } })); }
  if (runId) scopes.push({ label: 'Run', scope: { ...common, kind: 'run', run_id: runId } });
  function clear() { setRecords([]); callback.current([]); setCursor(null); }
  async function refresh(more = false) {
    request.current?.abort(); const controller = new AbortController(); request.current = controller; const token = ++generation.current;
    setLoading(true); setError('');
    try { const page = await api.evidencePage(studyId, { view: 'heads', limit: 20, ...(more && cursor ? { cursor } : {}) }, controller.signal); if (token !== generation.current || actor !== api.actor) return; const values = more ? [...records.filter(r => !page.data.some(n => n.evidence_id === r.evidence_id)), ...page.data] : page.data; setRecords(values); callback.current(values); setCursor(page.next_cursor); }
    catch (e) { if (token === generation.current && actor === api.actor) { if (evidenceAccessLost(e)) { clear(); setEditing(null); } setError('Evidence could not be loaded. Refresh evidence to try again. ' + message(e)); } }
    finally { if (token === generation.current) setLoading(false); }
  }
  useEffect(() => { clear(); setEditing(null); void refresh(); return () => { generation.current++; request.current?.abort(); }; }, [api, studyId, actor]);
  // A denial confirmed by any host of this study (for example an assumptions read) clears the library as its own denial does.
  useAccessLoss(api, studyId, change => { if (change.kind !== 'access-lost') return; generation.current++; request.current?.abort(); clear(); setEditing(null); setLoading(false); setError('Evidence could not be loaded. Refresh evidence to try again. ' + accessLostText); });
  useEffect(() => { if (editing) dialog.current?.showModal(); else dialog.current?.close(); }, [editing]);
  useEffect(() => { onHandle(editing ? { dirty: handle.current.dirty, save: () => handle.current.save(), discard: () => handle.current.discard() } : cleanGuard()); });
  function close() { if (api.pending?.category === 'evidence' && api.pending.study === studyId) return; if (handle.current.dirty) setDiscarding(true); else setEditing(null); }
  function open(record: EvidenceRecord | 'new') { invoker.current = document.activeElement as HTMLElement; setDiscarding(false); setEditing(record); }
  const visible = records.filter(record => (evidenceTitle(record) + ' ' + record.content).toLowerCase().includes(filter.toLowerCase()));
  return <section aria-label="Evidence" className="evidence-page"><SectionHeader level={2} title="Evidence" actions={<Button variant="primary" onClick={() => open('new')}>New evidence</Button>} /><p className="evidence-page-intro">Sources and observations used in this study.</p>
    <EvidenceIndex framed state={index.state} onRetry={index.retry} intro="Current assumptions: the latest saved approach version, current model drafts and the latest version of each configuration. Add or edit an assumption where it belongs." />
    <section aria-label="Evidence library">{error && <p role="alert">{error}</p>}
    <Panel title="Sources" headingLevel={3} actions={<Button disabled={loading} onClick={() => void refresh()}>Refresh evidence</Button>}>
      <div className="evidence-filters"><label>Filter evidence<TextInput type="search" value={filter} onChange={e => setFilter(e.target.value)} /></label><p>{visible.length} of {records.length} loaded records</p></div>
      {loading && <p role="status">Loading evidence…</p>}{!loading && !error && !records.length && <p>No evidence yet. Create evidence to save a source or observation.</p>}
      {!loading && records.length > 0 && !visible.length && <p>No matching evidence in the loaded records. Clear the filter or load more evidence.</p>}
      {visible.map(record => <article className="evidence-record" key={record.evidence_version_id}><EvidenceRecordBody record={record} library={{ api, studyId }} onUnavailable={() => { clear(); setError('Access to this evidence is no longer available. Choose another record or remove the attachment.'); }} action={<Button size="sm" onClick={() => open(record)}>Edit</Button>} /></article>)}
      {cursor && <Button disabled={loading} onClick={() => void refresh(true)}>Load more</Button>}
    </Panel></section>
    <DialogFrame ref={dialog} aria-label={editing === 'new' ? 'New evidence' : 'Edit evidence'} onCancel={e => { e.preventDefault(); close(); }} onClose={() => invoker.current?.isConnected && invoker.current.focus()}>
      <h2>{editing === 'new' ? 'New evidence' : 'Edit evidence'}</h2>
      {editing && <EvidenceEditor key={JSON.stringify([actor, studyId, editing === 'new' ? 'new' : editing.evidence_version_id])} api={api} studyId={studyId} ownerKey="library" scopes={scopes} record={editing === 'new' ? undefined : editing} onHandle={value => { handle.current = value; onHandle(value); }} onUnavailable={clear} onSaved={() => { setEditing(null); void refresh(); }} />}
      <div className="actions">{discarding ? <section aria-label="Unsaved evidence changes"><p>Discard unsaved evidence changes?</p><Button onClick={() => setDiscarding(false)}>Keep editing</Button><Button variant="danger" onClick={() => { handle.current.discard(); setEditing(null); setDiscarding(false); }}>Discard changes</Button></section> : <Button onClick={close}>Cancel</Button>}</div>
    </DialogFrame>
  </section>;
}
