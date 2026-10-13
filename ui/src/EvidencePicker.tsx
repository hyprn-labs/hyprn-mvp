import { useEffect, useRef, useState } from 'react';
import { Button, DialogFrame, Select, TextInput, StatusTag } from './design';
import { EvidenceEditor } from './EvidencePanel';
import { cleanGuard, type EditorGuard } from './workspaceModel';
import { EvidenceRecordBody, evidenceAccessLost, evidenceTitle } from './EvidenceView';
import { HyprnMvpApi, message, type EvidenceRecord, type EvidenceResourceRef1, type AssumptionEvidenceLink } from './api';

type Props = {
  api: HyprnMvpApi; studyId: string; label: string; scope: EvidenceResourceRef1 | null;
  ownerKey?: string; assumption?: boolean; onDirty?: (dirty: boolean) => void;
  onAttach: (record: EvidenceRecord, relation?: AssumptionEvidenceLink['relation']) => void;
  onRecords: (records: EvidenceRecord[]) => void; onClose: () => void;
};
/** Keying by owner prevents late reads, drafts or committed receipts from attaching elsewhere. */
export function EvidencePicker(props: Props) {
  const owner = JSON.stringify([props.api.actor, props.studyId, props.ownerKey ?? props.label, props.scope, props.assumption ?? false]);
  return <ScopedEvidencePicker key={owner} {...props} ownerKey={owner} />;
}
function ScopedEvidencePicker({ api, studyId, label, scope, ownerKey, assumption = false, onAttach, onRecords, onClose, onDirty }: Props & { ownerKey: string }) {
  const [records, setRecords] = useState<EvidenceRecord[]>([]), [mode, setMode] = useState<'existing' | 'new'>('existing');
  const [filter, setFilter] = useState(''), [selected, setSelected] = useState<EvidenceRecord | null>(null), [saved, setSaved] = useState(false);
  const [relation, setRelation] = useState<AssumptionEvidenceLink['relation'] | ''>(''), [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [loaded, setLoaded] = useState(false), [discarding, setDiscarding] = useState(false), [revoked, setRevoked] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null), generation = useRef(0), request = useRef<AbortController | null>(null), locked = useRef(false);
  const editor = useRef<EditorGuard>(cleanGuard());
  const callbacks = useRef({ onAttach, onRecords }); callbacks.current = { onAttach, onRecords };
  const actor = api.actor;
  function clear() { setRecords([]); setSelected(null); setCursor(null); setRevoked(true); callbacks.current.onRecords([]); }
  async function refresh(more = false) {
    request.current?.abort(); const controller = new AbortController(); request.current = controller; const token = ++generation.current;
    setLoading(true); setError('');
    try { const page = await api.evidencePage(studyId, { view: 'heads', limit: 20, ...(more && cursor ? { cursor } : {}) }, controller.signal); if (token !== generation.current || actor !== api.actor) return; const values = more ? [...records.filter(r => !page.data.some(n => n.evidence_id === r.evidence_id)), ...page.data] : page.data; setRecords(values); callbacks.current.onRecords(values); setCursor(page.next_cursor); setLoaded(true); setRevoked(false); }
    catch (e) { if (token === generation.current && actor === api.actor) { if (evidenceAccessLost(e)) clear(); setError('Evidence could not be loaded. Refresh evidence to try again. ' + message(e)); } }
    finally { if (token === generation.current) setLoading(false); }
  }
  useEffect(() => { const invoking = document.activeElement as HTMLElement; dialog.current?.showModal(); void refresh(); return () => { onDirty?.(false); generation.current++; request.current?.abort(); invoking?.isConnected && invoking.focus(); }; }, [api, studyId, actor]);
  async function attach() {
    if (!selected || locked.current || revoked) return;
    if (assumption && !relation) { setError('Choose a relationship.'); dialog.current?.querySelector('select')?.focus(); return; }
    locked.current = true; setLoading(true); setError(''); const token = ++generation.current; request.current?.abort(); const controller = new AbortController(); request.current = controller;
    try {
      const exact = await api.evidenceVersion(studyId, selected.evidence_version_id, controller.signal);
      if (token !== generation.current || actor !== api.actor) return;
      if (exact.study_id !== studyId) throw new Error('Evidence belongs to another study.');
      callbacks.current.onRecords([exact, ...records.filter(record => record.evidence_version_id !== exact.evidence_version_id)]);
      callbacks.current.onAttach(exact, relation || undefined);
    } catch (e) { if (token === generation.current && actor === api.actor) { if (evidenceAccessLost(e)) clear(); setError('Access to this evidence is no longer available. Choose another record or remove the attachment. ' + message(e)); } }
    finally { locked.current = false; if (token === generation.current) setLoading(false); }
  }
  function close() {
    if (api.pending?.category === 'evidence' && api.pending.study === studyId) { setMode('new'); return; }
    if (editor.current.dirty) setDiscarding(true); else onClose();
  }
  const visible = records.filter(record => (evidenceTitle(record) + ' ' + record.content).toLowerCase().includes(filter.toLowerCase()));
  return <DialogFrame ref={dialog} className="evidence-picker" aria-label={'Add evidence to ' + label} onCancel={e => { e.preventDefault(); close(); }}>
    <h2>Add evidence to {label}</h2><p>Creating evidence saves it to the library. Attach evidence separately to use it in this draft.</p>
    {error ? <p role="alert">{error}</p> : revoked && mode === 'existing' && <p role="alert">Access to this evidence is no longer available. Choose another record or remove the attachment.</p>}
    <div className="actions"><Button disabled={loading} aria-pressed={mode === 'existing'} onClick={() => setMode('existing')}>Choose existing</Button><Button disabled={loading || !scope || revoked} aria-pressed={mode === 'new'} onClick={() => setMode('new')}>Create new</Button></div>
    {!scope && <p>Choose a valid resource before creating evidence.</p>}
    <div hidden={mode !== 'existing'}><label>Find evidence<TextInput type="search" value={filter} onChange={e => setFilter(e.target.value)} /></label><Button disabled={loading} onClick={() => void refresh()}>Refresh evidence</Button>
      {loading && <p role="status">Loading evidence…</p>}{loaded && !loading && !visible.length && <p>No matching evidence in the loaded records. Clear the filter or load more evidence.</p>}
      <div className="evidence-options">{visible.map(record => <article className="evidence-record" key={record.evidence_version_id}><EvidenceRecordBody record={record} library={{ api, studyId }} onUnavailable={clear} onSelectVersion={value => { setSelected(value); setSaved(false); }} action={<Button disabled={loading || revoked} aria-pressed={selected?.evidence_version_id === record.evidence_version_id} onClick={() => { setSelected(record); setSaved(false); }}>Choose {evidenceTitle(record)} · Version {record.evidence_version_id.slice(0, 8)}</Button>} /></article>)}</div>
      {cursor && <Button disabled={loading} onClick={() => void refresh(true)}>Load more</Button>}
    </div>
    {scope && <div hidden={mode !== 'new'}><p>Context: {scope.kind === 'port' ? 'Model quantity' : scope.kind === 'study' ? 'Study' : scope.kind.replaceAll('_', ' ')}. The attachment target is {label}.</p><EvidenceEditor api={api} studyId={studyId} ownerKey={ownerKey} scopes={[{ label: scope.kind === 'study' ? 'Study' : 'Selected resource', scope }]} onHandle={handle => { editor.current = handle; onDirty?.(handle.dirty); }} onUnavailable={clear} onSaved={record => { setSelected(record); setSaved(true); callbacks.current.onRecords([record, ...records]); }} /></div>}
    {saved && <p role="status">Evidence saved to the library. Attach it to {label} to use it here.</p>}
    {selected && !revoked && <section aria-label="Selected evidence"><p>{evidenceTitle(selected)} · Version {selected.evidence_version_id.slice(0, 8)}</p></section>}
    {assumption && !revoked && <><label>Relationship<Select aria-label="Relationship" value={relation} onChange={e => setRelation(e.target.value as typeof relation)}><option value="">Choose relationship</option><option value="supports">Supports</option><option value="challenges">Challenges</option><option value="context">Context</option></Select></label><p>A citation records your interpretation; it does not validate the assumption.</p></>}
    <div className="evidence-footer actions">{selected && !revoked && (mode === 'existing' || saved) && <Button variant="primary" disabled={loading || !!api.pending} onClick={() => void attach()}>Attach evidence</Button>}
      {discarding ? <><p>Discard unsaved evidence changes?</p><Button onClick={() => setDiscarding(false)}>Keep editing</Button><Button variant="danger" onClick={() => { editor.current.discard(); onClose(); }}>Discard changes</Button></> : <Button onClick={close}>Cancel</Button>}
    </div>
  </DialogFrame>;
}
