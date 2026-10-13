import { useEffect, useRef, useState } from 'react';
import { Button, DialogFrame, StatusTag, TextInput } from './design';
import { unitLabel } from './unitLabels';
import { HyprnMvpApi, message, type ResultSource } from './api';
import { RunOutcomes, resultOutcomes } from './runStatus';

/** Inventory contains retained public labels and verified scalar bytes only. */
export function ResultPicker({ api, studyId, label, onChoose, onClose }: {
  api: HyprnMvpApi; studyId: string; label: string;
  onChoose: (source: ResultSource) => void; onClose: () => void;
}) {
  const [items, setItems] = useState<ResultSource[]>([]), [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [loaded, setLoaded] = useState(false), [error, setError] = useState(''), [filter, setFilter] = useState('');
  const dialog = useRef<HTMLDialogElement>(null), generation = useRef(0), locked = useRef(false);
  const actor = api.actor;
  async function load(next?: string) {
    if (locked.current) return; locked.current = true; setBusy(true); setError('');
    const token = generation.current;
    try {
      const page = await api.resultSourcesPage(studyId, 25, next);
      if (token !== generation.current || actor !== api.actor) return;
      setItems(old => next ? [...old, ...page.items] : page.items); setCursor(page.next_cursor); setLoaded(true);
    } catch (e) { if (token === generation.current && actor === api.actor) setError(message(e)); }
    finally { locked.current = false; if (token === generation.current) setBusy(false); }
  }
  useEffect(() => {
    const invoking = document.activeElement as HTMLElement;
    const element = dialog.current; element?.showModal(); void load();
    return () => { generation.current++; element?.close(); requestAnimationFrame(() => { if (invoking?.isConnected) invoking.focus(); }); };
  }, [api, studyId, actor]);
  const visible = items.filter(i => `${i.labels.run_name} ${i.labels.model_name ?? ''} ${i.labels.instance_name} ${i.labels.output_name} ${i.source_run_id}`.toLowerCase().includes(filter.toLowerCase()));
  return <DialogFrame ref={dialog} className="evidence-picker" aria-label={`Use a run result for ${label}`} onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose(); } }} onCancel={e => { e.preventDefault(); onClose(); }}>
    <h2>Use a run result</h2><p>Choose a run output for {label}. Execution and criteria are reported separately. Criteria are fixed-threshold checks, not a scientific assessment.</p>
    <label>Filter loaded results<TextInput type="search" value={filter} onChange={e => setFilter(e.target.value)} /></label>
    {busy && <p role="status"><StatusTag tone="running">Loading results…</StatusTag></p>}
    {error && <div role="alert"><p>{error}</p><Button disabled={busy} onClick={() => void load(loaded && cursor ? cursor : undefined)}>Retry results</Button></div>}
    {loaded && !items.length && <p>No available run results in the loaded page.</p>}
    {loaded && !!items.length && !visible.length && <p>No matching results in the loaded page.</p>}
    <div className="evidence-options">{visible.map(i => <article className="evidence-record" key={`${i.source_run_id}/${i.source_output.instance_id}/${i.source_output.port_id}`}>
      <h3>{i.labels.run_name} · {i.source_run_id.slice(0, 8)}</h3>
      <p>{i.labels.model_name ?? 'Unnamed model'} · Model version {i.labels.model_revision_id.slice(0, 8)}</p>
      <p>Component: {i.labels.instance_name} · Output: {i.labels.output_name}</p>
      <p><strong>{i.value} {unitLabel(i.units)}</strong></p>
      <RunOutcomes outcomes={resultOutcomes(i.outcomes.execution, i.outcomes.criteria)} />
      <p>Units as produced by the source run. Availability is checked again before the run.</p>
      <Button disabled={busy} onClick={() => onChoose(i)}>Use this result · {i.labels.instance_name} · {i.labels.output_name}</Button>
    </article>)}</div>
    <div className="evidence-footer">{cursor && <Button disabled={busy} onClick={() => void load(cursor)}>Load more</Button>}<Button onClick={onClose}>Cancel</Button></div>
  </DialogFrame>;
}
