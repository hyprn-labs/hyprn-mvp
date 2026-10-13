import { unitLabel } from './unitLabels';
import { Assumptions } from './Assumptions';
import { EvidenceReferences } from './EvidenceView';
import { ActionDialog, Button, Panel, SectionHeader } from './design';
import { useEffect, useId, useState, type ReactNode } from 'react';
import type { EvidenceSnapshot, PortRef, Source } from './contract';
import { sourceText } from './api';
import { groupSelected, type Projection, type Snapshot } from './GraphView';
import { modelAssumptions, recordLimitations } from './recordViews';
import type { MethodLink, MethodLinks } from './modelMethods';
import type { Selection } from './workspaceModel';
import { quantityKey, variableRows, type VariableContext } from './VariablesTable';

/** Renders "What it computes" (with the given source control) and "Why" for one component. */
export type ComponentExplanation = (instanceId: string, source: ReactNode) => ReactNode;

export function instanceLabel(snapshot: Snapshot, id: string) {
  const item = snapshot.instances.find(i => i.instance_id === id), peers = snapshot.instances.filter(i => i.name === item?.name);
  return item ? `${item.name}${peers.length > 1 ? ` · instance ${peers.findIndex(i => i.instance_id === id) + 1}` : ''}` : 'Unavailable component';
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** "3 components · 2 connections · select a component to see what it computes and why". */
export function modelSummary(snapshot: Snapshot) {
  const components = snapshot.instances.filter(i => i.instance_id !== snapshot.root_instance_id).length;
  return `${plural(components, 'component', 'components')} · ${plural(snapshot.connections.length, 'connection', 'connections')} · select a component to see what it computes and why`;
}
/** "Definition · 4 quantities · shown below": quantities are listed once, in the table below. */
export function componentSummary(snapshot: Snapshot, instanceId: string) {
  const instance = snapshot.instances.find(i => i.instance_id === instanceId);
  const definition = snapshot.definitions.find(d => d.definition_version_id === instance?.definition_version_id);
  return `${definition?.name ?? 'Unavailable definition'} · ${plural(definition?.ports.length ?? 0, 'quantity', 'quantities')} · shown below`;
}

type SourceRead ={ kind: 'text'; text: string } | { kind: 'limit' } | { kind: 'mismatch' } | { kind: 'undecodable' };
/** Verifies retained bytes against their SHA256, then decodes them as text only. Never run. */
export async function verifySource(source: Source, hash: string): Promise<SourceRead> {
  if (source.bytes.length > 350000) return { kind: 'limit' };
  const raw = Uint8Array.from(atob(source.bytes), c => c.charCodeAt(0));
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', raw)), b => b.toString(16).padStart(2, '0')).join('');
  if (digest !== hash || source.sha256 !== hash) return { kind: 'mismatch' };
  try { return { kind: 'text', text: sourceText(source) }; } catch { return { kind: 'undecodable' }; }
}
/** One source file of a component version, SHA-checked and shown as text. */
function VerifiedSource({ source, hash, position, count }: { source?: Source; hash: string; position: number; count: number }) {
  const [value, setValue] = useState<{ source: Source; read: SourceRead } | null>(null);
  useEffect(() => {
    let current = true; setValue(null); if (!source) return;
    verifySource(source, hash).then(read => { if (current) setValue({ source, read }); }, () => { if (current) setValue({ source, read: { kind: 'mismatch' } }); });
    return () => { current = false; };
  }, [source, hash]);
  const identity = <p className="context-line source-identity">File {position} of {count} · SHA-256 {hash}</p>;
  if (!source) return <>{identity}<p role="alert">This source file is missing from the model version.</p></>;
  const read = value?.source === source ? value.read : null;
  if (!read) return <>{identity}<p role="status">Checking source…</p></>;
  if (read.kind === 'limit') return <>{identity}<p role="alert">This source file is too large to show here.</p></>;
  if (read.kind === 'mismatch') return <>{identity}<p role="alert">This file does not match its SHA-256. It is not shown.</p></>;
  if (read.kind === 'undecodable') return <>{identity}<p role="alert">These bytes are not valid UTF-8 text and are not shown.</p></>;
  return <>{identity}<pre tabIndex={0} aria-label="Read-only authored source">{read.text}</pre></>;
}
/** Read-only source of one component version: every file, checked against its SHA256. */
export function ComponentSource({ snapshot, instanceId }: { snapshot: Snapshot; instanceId: string }) {
  const instance = snapshot.instances.find(i => i.instance_id === instanceId);
  const definition = snapshot.definitions.find(d => d.definition_version_id === instance?.definition_version_id);
  const hashes = definition?.source_refs ?? [];
  return <ActionDialog title={'Source · ' + instanceLabel(snapshot, instanceId)} label="View source" size="sm" width="workspace">
    <p className="context-line">Shown as text; never run.</p>
    {!hashes.length && <p>This component version has no source file.</p>}
    {hashes.map((hash, i) => <VerifiedSource key={hash} hash={hash} position={i + 1} count={hashes.length} source={snapshot.source_files.find(s => s.sha256 === hash)} />)}
  </ActionDialog>;
}

/** What the component encodes and why it is used: the linked method steps' authored
 * Transformation, Purpose and rationale, each with its exact approach version. */
export function ComponentWhatWhy({ snapshot, instanceId, methods, onOpenStep, source }: { snapshot: Snapshot; instanceId: string; methods: MethodLinks; onOpenStep?: (link: MethodLink) => void; source: ReactNode }) {
  const id = useId();
  const links = methods.kind === 'loaded' ? methods.links.filter(l => l.instanceIds.includes(instanceId)) : [];
  const exact = 'model_revision_id' in snapshot ? snapshot.model_revision_id : null;
  const status = (none: string) => methods.kind === 'loading' ? <p role="status" className="context-line">Loading method steps…</p>
    : methods.kind === 'unavailable' ? <p className="context-line">Method steps can't be loaded.</p>
    : !links.length ? <p className="context-line">{none}</p> : null;
  const stepLine = (l: MethodLink) => <p className="context-line">Method step {l.stepNumber} · {l.step.title || 'Untitled step'}</p>;
  return <>
    <section className="inspector-section" aria-labelledby={id + '-what'}><h4 id={id + '-what'}>What it computes</h4>
      {status('No method step describes what this component computes.')}
      {links.map(l => <div className="inspector-step" key={l.key}>{stepLine(l)}<p className="context-copy">{l.step.intent.transformation || 'No transformation described.'}</p></div>)}
      {source}
    </section>
    <section className="inspector-section" aria-labelledby={id + '-why'}><h4 id={id + '-why'}>Why</h4>
      {status('No method step explains why this component is used.')}
      {links.map(l => <div className="inspector-step" key={l.key}>
        <p className="context-line">Method step {l.stepNumber} · {l.step.title || 'Untitled step'} · {l.versionNumber === null ? 'approach draft' : 'Approach version ' + l.versionNumber}{exact !== null && l.modelRevisionIds.includes(exact) ? '' : ' · linked to Model version ' + l.modelRevisionIds.map(r => r.slice(0, 8)).join(', ')}</p>
        <p><strong>Purpose. </strong>{l.step.purpose || 'No purpose described.'}</p>
        <p><strong>Why this method. </strong>{l.step.rationale || 'No rationale described.'}</p>
        {onOpenStep && <Button size="sm" variant="quiet" onClick={() => onOpenStep(l)}>Open step {l.stepNumber} in modeling approach →</Button>}
      </div>)}
    </section>
  </>;
}

/** Details panel of the canonical model view: nothing selected → the
 * model and its assumptions; a component → what it computes, why, and its assumptions;
 * a connection → its endpoints. No ports table, incoming/outgoing lists or notes: the
 * quantities table below the canvas is the one place quantities are listed. */
export function SelectionInspector({ snapshot, projection, selection, onSelect, context, evidence, draftHost, methods, onOpenStep }: { snapshot: Snapshot; projection: Projection; selection: Selection; onSelect: (value: Selection) => void; context: VariableContext; evidence: EvidenceSnapshot[];
  /** Current model draft: the model editor renders the editable model or component details here. */
  draftHost?: (element: HTMLDivElement | null) => void; methods: MethodLinks; onOpenStep?: (link: MethodLink) => void }) {
  const rows = variableRows(snapshot, projection, context);
  const node = projection.nodes.find(n => (selection.kind === 'instance' || selection.kind === 'variable') && n.instance.instance_id === selection.instance_id);
  const row = selection.kind === 'variable' ? rows.find(r => r.key === quantityKey(selection)) : undefined;
  const definition = snapshot.definitions.find(d => d.definition_version_id === node?.instance.definition_version_id);
  const groups = projection.groups.filter(g => groupSelected(g, selection));
  const selectedIds = new Set([node?.instance.instance_id, row?.port.port_id, ...groups.flatMap(g => [g.source, g.target, ...g.links.map(l => l.connection_id)])].filter(Boolean));
  // Notes (annotations) are kept in the record but not shown.
  const assumptions = modelAssumptions(snapshot);
  const related = evidence.filter(e => 'resource_scope' in e && ('model_revision_id' in snapshot) && 'model_revision_id' in e.resource_scope && e.resource_scope.model_revision_id === snapshot.model_revision_id &&
    (e.resource_scope.kind === 'model_revision' || ('instance_id' in e.resource_scope && selectedIds.has(e.resource_scope.instance_id) && (e.resource_scope.kind !== 'port' || !row || e.resource_scope.port_id === row.port.port_id)) || (e.resource_scope.kind === 'definition_version' && e.resource_scope.definition_version_id === definition?.definition_version_id) || (e.resource_scope.kind === 'connection' && selectedIds.has(e.resource_scope.connection_id))));
  const endpoint = (ref: PortRef) => { const entry = rows.find(r => r.key === quantityKey(ref)); return <Button onClick={() => onSelect({ kind: 'instance', instance_id: ref.instance_id })}>{entry ? `${instanceLabel(snapshot, entry.instance.instance_id)} · ${entry.port.name}${entry.port.name === entry.port.code_symbol ? '' : ` (${entry.port.code_symbol})`} · ${unitLabel(entry.port.units)}` : 'Unavailable endpoint'}</Button>; };
  const explain: ComponentExplanation = (instanceId, source) => <ComponentWhatWhy snapshot={snapshot} instanceId={instanceId} methods={methods} onOpenStep={onOpenStep} source={source} />;
  const componentAssumptions = assumptions.kind === 'recorded' ? assumptions.items.filter(a => a.owner.kind === 'instance').length : 0;
  const unreadable = (text: ReactNode) => <><SectionHeader title="Assumptions" level={4} /><p className="context-line">{text}</p></>;
  return <Panel label="Selection inspector" className="selection-inspector" title="Details" bodyClassName="panel-body">
    {draftHost && (selection.kind === 'none' || node) && <div ref={draftHost} className="inspector-draft" />}
    {!draftHost && selection.kind === 'none' && <section className="inspector-model" aria-label="Model details">
      <h3>Model</h3>
      <p className="context-line">{modelSummary(snapshot)}</p>
      <div className="inspector-section">{assumptions.kind === 'recorded' ? <Assumptions ownerKey={('model_revision_id' in snapshot ? snapshot.model_revision_id : snapshot.draft_revision) + '/model'} headingLevel={4} ownerLabel="Model" items={assumptions.modelOwned} records={evidence} />
        : unreadable(assumptions.kind === 'not_in_format' ? recordLimitations.modelAssumptionsNotInFormat : recordLimitations.modelAssumptionsUnreadable)}</div>
      {assumptions.kind === 'recorded' && <p className="context-line">Component assumptions: {componentAssumptions} · shown with each component</p>}
    </section>}
    {node && !draftHost && <>
      <h3>{instanceLabel(snapshot, node.instance.instance_id)}</h3>
      <p className="context-line">{componentSummary(snapshot, node.instance.instance_id)}</p>
      {explain(node.instance.instance_id, <div className="section-actions"><ComponentSource snapshot={snapshot} instanceId={node.instance.instance_id} /></div>)}
      <div className="inspector-section">{assumptions.kind === 'recorded' ? <Assumptions headingLevel={4} ownerKey={snapshot.model_id + '/' + node.instance.instance_id} ownerLabel={'Component · ' + instanceLabel(snapshot, node.instance.instance_id)} items={assumptions.items.filter(a => a.owner.kind === 'instance' && a.owner.instance_id === node.instance.instance_id)} records={evidence} />
        : unreadable(assumptions.kind === 'not_in_format' ? recordLimitations.modelAssumptionsNotInFormat : recordLimitations.modelAssumptionsUnreadable)}</div>
    </>}
    {groups.map(group => <div key={group.key}><h3>Connections · {group.links.length}</h3>{group.links.map(link => <article key={link.connection_id} data-selected-link={link.connection_id}><Button aria-pressed={selection.kind === 'connection' && selection.connection_id === link.connection_id} onClick={() => onSelect({ kind: 'connection', connection_id: link.connection_id })}>Connection {group.links.indexOf(link) + 1}: {rows.find(r => r.key === quantityKey(link.source_ref))?.port.code_symbol ?? 'Unavailable'} → {rows.find(r => r.key === quantityKey(link.target_ref))?.port.code_symbol ?? 'Unavailable'}</Button><p>From</p>{endpoint(link.source_ref)}<p>To</p>{endpoint(link.target_ref)}</article>)}</div>)}
    {!!related.length && <p>Related evidence</p>}<EvidenceReferences records={related} ids={related.map(e => e.evidence_version_id)} />
  </Panel>;
}
