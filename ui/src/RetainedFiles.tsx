import { OpenLink } from './design';
import { useState } from 'react';
import type { HistoryArtifact } from './contract';
import { ActionDialog, Button, DataTable, Select, TextInput } from './design';
const recordRoles = ['source', 'model', 'configuration', 'context', 'evidence', 'retrieved'];
const programRoles = ['generated', 'preparation', 'locks'];
const category = (role: string) => recordRoles.includes(role) ? 'calculation' : programRoles.includes(role) ? 'program' : 'provenance';
const roleNames: Record<string, string> = { source: 'Authored source', model: 'Model version', configuration: 'Configuration', context: 'Study context', evidence: 'Evidence', retrieved: 'Execution output', generated: 'Generated program', preparation: 'Preparation record', locks: 'Dependency lock', provenance: 'Provenance', licenses: 'License notice' };
/** Only presentation filters and pagination; downloads stay with the verified API client. */
export function RetainedFiles({ artifacts, busy, read }: { artifacts: HistoryArtifact[]; busy: boolean; read: (a: HistoryArtifact, mode: 'download' | 'preview') => void }) {
  const [kind, setKind] = useState('calculation'), [filter, setFilter] = useState(''), [page, setPage] = useState(0);
  const visible = artifacts.filter(a => (!kind || category(a.role) === kind) && `${a.name} ${roleNames[a.role] ?? a.role}`.toLowerCase().includes(filter.toLowerCase()));
  const pages = Math.max(1, Math.ceil(visible.length / 20)), current = Math.min(page, pages - 1);
  return <section aria-label="Run files"><div className="evidence-filters"><label>File group<Select value={kind} onChange={e => { setKind(e.target.value); setPage(0); }}><option value="">All files ({artifacts.length})</option>{[['calculation', 'Calculation records'], ['program', 'Executable program'], ['provenance', 'Provenance & licenses']].map(([value, label]) => <option key={value} value={value}>{label} ({artifacts.filter(a => category(a.role) === value).length})</option>)}</Select></label><label>Find a file<TextInput type="search" value={filter} onChange={e => { setFilter(e.target.value); setPage(0); }} /></label></div>
    <DataTable regionLabel="Run files table" className="hf-files-table"><thead><tr><th>File</th><th>Content</th><th>Size</th><th>Actions</th></tr></thead><tbody>{visible.slice(current * 20, (current + 1) * 20).map(a => <tr key={a.artifact_id}><th scope="row" className="hf-file-name">{a.name}</th><td>{roleNames[a.role] ?? a.role}</td><td>{a.size.toLocaleString('en-US')} bytes</td><td><div className="section-actions"><ActionDialog purpose="reader" title={a.name} label="Details" size="sm"><dl className="hf-record-details"><dt>SHA-256</dt><dd><code>{a.sha256}</code></dd><dt>Artifact ID</dt><dd>{a.artifact_id}</dd></dl><p>Downloads are byte-for-byte copies of the run's files. Text previews are limited to 64 KiB.</p></ActionDialog><OpenLink size="sm" disabled={busy || a.size > 64 * 1024} onClick={() => read(a, 'preview')}>Preview</OpenLink><Button size="sm" disabled={busy} onClick={() => read(a, 'download')}>Download</Button></div></td></tr>)}</tbody></DataTable>
    {!visible.length && <p>No files in this selection.</p>}
    <div className="hf-file-pagination"><p aria-live="polite">{visible.length} files · Page {current + 1} of {pages}</p><Button size="sm" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous files</Button><Button size="sm" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>Next files</Button></div>
  </section>;
}
