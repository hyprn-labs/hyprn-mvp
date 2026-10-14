import { quantityDefinitions } from './quantityDefinitions';
import { unitLabel } from './unitLabels';
import { DataTable, Panel, formatNumber } from './design';
import { Button, TextInput, TextArea, Select, Disclosure } from './design';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ConfigurationRevision, PortRef, RunHistoryRead6, DefinitionChange } from './contract';
import type { Projection, Snapshot } from './GraphView';
import type { EditorGuard, Selection } from './workspaceModel';

export function parsePortMetadata(text: string, ports: Array<{ port_id: string }>): DefinitionChange[] {
  if (new TextEncoder().encode(text).length > 2 * 1024 * 1024) throw new Error('Paste exceeds 2 MiB.');
  const lines = text.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
  const header = lines.shift()!.split('\t');
  if (header[0] !== 'port_id' || header.length < 2 || new Set(header).size !== header.length || header.slice(1).some(column => !['name', 'code_symbol', 'units'].includes(column))) throw new Error('Row 1: use port_id followed only by name, code_symbol or units; columns must be unique.');
  if (!lines.length || lines.length > 256) throw new Error('Paste requires 1–256 metadata rows.');
  const seen = new Set<string>();
  return lines.map((line, i) => {
    const cells = line.split('\t'), id = cells[0];
    const fail = (reason: string): never => { throw new Error(`Row ${i + 2}: ${reason}`); };
    if (cells.length !== header.length) fail('column count differs from the header.');
    if (!ports.some(p => p.port_id === id) || seen.has(id)) fail('port_id must belong to the selected component and occur once.');
    seen.add(id);
    const fields: { name?: string; code_symbol?: string; units?: string } = {};
    header.slice(1).forEach((column, j) => {
      const value = cells[j + 1];
      if (value.length > 4096 || value.includes('\0')) fail(`${column} is invalid or too long.`);
      if (column === 'code_symbol' && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(value)) fail('code_symbol must be a Python identifier.');
      if (column === 'name' && !value.trim()) fail('name is required.');
      fields[column as keyof typeof fields] = value;
    });
    return { kind: 'update_port', port_id: id, fields };
  });
}

export type VariableContext = { kind: 'model' } | { kind: 'configuration_draft'; inputs: Array<{ target: PortRef; value: string; units: string; statement: string }> }
  | { kind: 'configuration'; configuration: ConfigurationRevision } | { kind: 'run'; history: RunHistoryRead6 };
export const quantityKey = (ref: PortRef) => `${ref.instance_id}/${ref.port_id}`;
const outputReasonLabels: Record<string, string> = { producer_failed: 'Producer failed', unassigned: 'Not assigned', nonfinite: 'Non-finite value', unavailable: 'Unavailable' };
export function variableRows(snapshot: Snapshot, projection: Projection, context: VariableContext) {
  const quantities = quantityDefinitions(snapshot);
  return projection.nodes.flatMap(node => node.ports.map(port => {
    const target = { instance_id: node.instance.instance_id, port_id: port.port_id };
    const key = quantityKey(target), incoming = snapshot.connections.filter(c => quantityKey(c.target_ref) === key), outgoing = snapshot.connections.filter(c => quantityKey(c.source_ref) === key);
    const configuration = context.kind === 'configuration' ? context.configuration : context.kind === 'run' ? context.history.configuration : null;
    const assignment = configuration?.inputs.find(i => quantityKey(i.target) === key);
    const proposal = context.kind === 'configuration_draft' ? context.inputs.find(i => quantityKey(i.target) === key) : undefined;
    const output = context.kind === 'run' ? context.history.results?.outputs.find(o => quantityKey(o.target) === key) : undefined;
    let value = 'Declared · not computed', availability = 'not_computed', provenance = '', valueUnits = '';
    if (context.kind !== 'model') {
      value = incoming.length ? 'Connected reference' : 'Not computed';
      if (proposal) {
        provenance = proposal.statement; valueUnits = proposal.units;
        if (proposal.value.trim() && Number.isFinite(Number(proposal.value))) { value = proposal.value; availability = 'explicit'; }
        else { value = 'Explicit value required'; availability = 'missing'; }
      } else if (assignment) { value = String(assignment.value); valueUnits = assignment.units; availability = 'explicit'; provenance = `${assignment.provenance.kind}: ${assignment.provenance.statement}`; }
      if (context.kind === 'run' && port.direction === 'output') {
        provenance = 'Retained run output'; valueUnits = output?.units ?? '';
        if (output?.availability === 'available' && output.value !== null && Number.isFinite(output.value)) { value = String(output.value); availability = 'available'; }
        else { value = 'not computed'; availability = 'unavailable'; provenance += output?.reason ? ` · ${Object.hasOwn(outputReasonLabels, output.reason) ? outputReasonLabels[output.reason] : 'Unknown reason'}` : ' · no verified value retained'; }
      }
    }
    return { definition: quantities.find(q => q.instance.instance_id === node.instance.instance_id && q.port.port_id === port.port_id)?.statement ?? null, key, target, instance: node.instance, port, incoming, outgoing, value, valueUnits, availability, provenance };
  }));
}
export type VariableRow = ReturnType<typeof variableRows>[number];
export function selectionHas(row: VariableRow, selection: Selection) {
  if (selection.kind === 'instance') return selection.instance_id === row.instance.instance_id;
  if (selection.kind === 'variable') return quantityKey(selection) === row.key;
  const ids = selection.kind === 'connection_group' ? selection.connection_ids : selection.kind === 'connection' ? [selection.connection_id] : [];
  return [...row.incoming, ...row.outgoing].some(c => ids.includes(c.connection_id));
}
export type PortPasteScope = { study_id: string; model_id: string; draft_revision: string; instance_id: string; definition_version_id: string };
export type PortPasteAction = (scope: PortPasteScope, text: string, saveAuthoring?: boolean) => Promise<boolean>;
/** Display value of one quantity in its context (Scientific-states.md): an explicit value with
 * its own recorded unit, "unassigned" for a free input without a value, "not computed" for a
 * missing run output and "computed when run" before a run exists. A connected input in a run
 * shows the exact value its producer recorded, with the producer's unit and identity. The
 * export projection (`variableRows`) is unchanged. */
export function quantityValue(row: VariableRow, rows: VariableRow[], context: VariableContext, name: (id: string) => string): { value: number | null; text: string; units: string; provenance: string; missing: boolean } {
  const none = { value: null, units: '', missing: true };
  if (row.port.direction === 'input' && row.incoming.length) {
    const source = row.incoming[0].source_ref, producer = rows.find(r => r.key === quantityKey(source));
    const from = `From ${name(source.instance_id)} · ${producer?.port.code_symbol ?? 'unavailable output'}`;
    if (context.kind === 'run' && producer?.availability === 'available') return { value: Number(producer.value), text: producer.value, units: producer.valueUnits, provenance: from, missing: false };
    return { ...none, text: context.kind === 'run' ? 'not computed' : 'computed when run', provenance: from };
  }
  if (['available', 'explicit'].includes(row.availability) && row.value.trim() !== '' && Number.isFinite(Number(row.value)))
    return { value: Number(row.value), text: row.value, units: row.valueUnits, provenance: row.availability === 'available' ? 'Computed by this run' : row.provenance, missing: false };
  if (row.port.direction === 'output') {
    if (context.kind === 'run') return { ...none, text: 'not computed', provenance: row.provenance.replace(/^Retained run output · /, '').replace(/^no verified value retained$/, 'No verified value') };
    return { ...none, text: 'computed when run', provenance: '' };
  }
  return { ...none, text: 'unassigned', provenance: row.provenance };
}
/** The value's own recorded unit, shown beside it only when it differs from the quantity's
 * declared unit (the Unit column); a received value is never silently relabelled. */
function recordedUnit(units: string, row: VariableRow) {
  const recorded = units || 'Dimensionless';
  return recorded.toLocaleLowerCase() === unitLabel(row.port.units).toLocaleLowerCase() ? '' : recorded;
}


/** Quantities of the canonical model view: one table below the canvas, in its
 * own scroll region. A selected component (or an approach step's components) filters and
 * highlights its rows; "Show all quantities" clears that filter. Connections are folded into
 * Direction ("Input · from …", "Output · to …"). */
export function QuantitiesTable({ snapshot, projection, selection, onSelect, context, focus, onPastePorts, onPasteHandle }: { snapshot: Snapshot; projection: Projection; selection: Selection; onSelect: (value: Selection) => void; context: VariableContext; focus?: Set<string>; onPastePorts?: PortPasteAction; onPasteHandle?: (handle: EditorGuard) => void }) {
  const [paste, setPaste] = useState(''), [pasteError, setPasteError] = useState(''), [pasting, setPasting] = useState(false);
  const [pasteScope, setPasteScope] = useState<PortPasteScope | null>(null);
  const pasteInstance = selection.kind === 'instance' || selection.kind === 'variable' ? selection.instance_id : '';
  function discardPaste() { setPaste(''); setPasteScope(null); setPasteError(''); }
  async function savePaste(saveAuthoring = false): Promise<boolean> {
    if (!paste) return true;
    if (pasting || !onPastePorts) return false;
    setPasteError(''); setPasting(true);
    try {
      if (!pasteScope) throw new Error('Select an editable component before entering port metadata. Your text is preserved.');
      const applied = await onPastePorts(pasteScope, paste, saveAuthoring);
      if (applied) discardPaste();
      return applied;
    } catch (e) { setPasteError(e instanceof Error ? e.message : 'Metadata proposal failed; rows kept.'); return false; }
    finally { setPasting(false); }
  }
  const handleCallback = useRef(onPasteHandle); handleCallback.current = onPasteHandle;
  useEffect(() => { onPasteHandle?.({ dirty: !!paste, save: () => savePaste(true), discard: discardPaste }); });
  useEffect(() => () => { handleCallback.current?.({ dirty: false, save: async () => true, discard: () => {} }); }, []);
  const rows = useMemo(() => variableRows(snapshot, projection, context), [snapshot, projection, context]);
  const [search, setSearch] = useState(''),
    [direction, setDirection] = useState('');
  const [sort, setSort] = useState<'variable' | 'component'>('component'), [descending, setDescending] = useState(false);
  // A selected component (or the approach step's components when nothing is selected) scopes the rows.
  const focusKey = [...(focus ?? [])].join('/');
  const [showAll, setShowAll] = useState(false);
  useEffect(() => { setShowAll(false); }, [pasteInstance, focusKey]);
  const focused = projection.nodes.map(n => n.instance.instance_id).filter(id => focus?.has(id));
  const scope = showAll ? [] : pasteInstance ? [pasteInstance] : focused.length < projection.nodes.length ? focused : [];
  const scroll = useRef<HTMLDivElement>(null);
  const selectedKey = selection.kind === 'variable' ? quantityKey(selection) : '';
  useEffect(() => {
    if (!selectedKey) return;
    // Reveal the selected quantity inside the table's own scroll region; the page does not jump.
    const frame = requestAnimationFrame(() => {
      const region = scroll.current, row = Array.from(region?.querySelectorAll<HTMLElement>('[data-variable]') ?? []).find(el => el.dataset.variable === selectedKey);
      if (region && row) region.scrollTop = Math.max(0, row.offsetTop - region.clientHeight / 3);
    });
    return () => cancelAnimationFrame(frame);
  }, [selectedKey]);
  const needle = search.trim().toLocaleLowerCase(), hasValues = context.kind !== 'model';
  const instanceName = (id: string) => { const node = projection.nodes.find(n => n.instance.instance_id === id); const peers = projection.nodes.filter(n => n.instance.name === node?.instance.name); return `${node?.instance.name ?? 'Unavailable component'}${peers.length > 1 ? ' · instance ' + (peers.findIndex(n => n.instance.instance_id === id) + 1) : ''}`; };
  const endpoint = (ref: PortRef) => { const row = rows.find(r => r.key === quantityKey(ref)); return row ? `${instanceName(ref.instance_id)} · ${row.port.code_symbol}` : 'Unavailable quantity'; };
  const values = new Map(rows.map(r => [r.key, quantityValue(r, rows, context, instanceName)]));
  const visible = rows
    .filter(
      (r) =>
        `${r.port.name} ${r.port.code_symbol} ${r.instance.name}`
          .toLocaleLowerCase()
          .includes(needle) &&
        (!scope.length || scope.includes(r.instance.instance_id)) &&
        (!direction || r.port.direction === direction),
    )
    .sort(
      (a, b) =>
        ((sort === 'variable'
          ? a.port.name.localeCompare(b.port.name)
          : a.instance.name.localeCompare(b.instance.name)) || a.key.localeCompare(b.key)) *
        (descending ? -1 : 1),
    );
  function order(next: typeof sort) { setDescending(sort === next ? !descending : false); setSort(next); }
  const flow = (row: VariableRow) => row.port.direction === 'input' ? <>Input<span className="quantity-flow">{row.incoming.length ? row.incoming.map(c => 'from ' + endpoint(c.source_ref)).join(', ') : 'set in configuration'}</span></>
    : row.port.direction === 'output' ? <>Output<span className="quantity-flow">{row.outgoing.length ? row.outgoing.map(c => 'to ' + endpoint(c.target_ref)).join(', ') : 'model result'}</span></> : <>Residual</>;
  const highlighted = (row: VariableRow) => selectionHas(row, selection) || (!pasteInstance && focused.length < projection.nodes.length && focused.includes(row.instance.instance_id));
  const scopeName = scope.length ? scope.map(instanceName).join(', ') : '';
  return (
    <Panel
      className="quantities-panel"
      label="Quantities"
      title="Quantities"
      headingLevel={3}
      actions={
        scope.length ? (
          <Button size="sm" onClick={() => setShowAll(true)}>
            Show all quantities
          </Button>
        ) : undefined
      }
    >
      <section aria-label="Quantities view" className="variables-view">
        <div className="variable-filters">
          <label>
            Find a quantity
            <TextInput type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label>
            Component
            <Select
              aria-label="Component filter"
              value={scope.length === 1 ? scope[0] : ''}
              onChange={(e) => {
                if (e.target.value) onSelect({ kind: 'instance', instance_id: e.target.value });
                else setShowAll(true);
              }}
            >
              <option value="">All components</option>
              {projection.nodes.map((n) => (
                <option key={n.instance.instance_id} value={n.instance.instance_id}>
                  {instanceName(n.instance.instance_id)}
                </option>
              ))}
            </Select>
          </label>
          <label>
            Direction
            <Select
              aria-label="Direction filter"
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
            >
              <option value="">All directions</option>
              {['input', 'output', 'residual'].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </Select>
          </label>
          {(search || direction) && (
            <Button
              variant="quiet"
              onClick={() => {
                setSearch('');
                setDirection('');
              }}
            >
              Clear filters
            </Button>
          )}
        </div>
        <p className="context-line" aria-live="polite">
          Showing {visible.length} of {rows.length} quantities{scopeName && ' · ' + scopeName}
        </p>
        <div
          ref={scroll}
          className="table-scroll variables-scroll quantities-scroll"
          role="region"
          aria-label="Quantities table"
          tabIndex={0}
        >
          <DataTable label="Quantities" dense className="quantities-table">
            <thead>
              <tr>
                <th
                  scope="col"
                  aria-sort={
                    sort === 'variable' ? (descending ? 'descending' : 'ascending') : 'none'
                  }
                >
                  <Button variant="quiet" size="sm" onClick={() => order('variable')}>
                    Quantity
                  </Button>
                </th>
                <th
                  scope="col"
                  aria-sort={
                    sort === 'component' ? (descending ? 'descending' : 'ascending') : 'none'
                  }
                >
                  <Button variant="quiet" size="sm" onClick={() => order('component')}>
                    Component
                  </Button>
                </th>
                <th scope="col">Direction</th>
                <th scope="col">Definition</th>
                <th scope="col">Unit</th>
                {hasValues && (
                  <>
                    <th scope="col" className="hf-th--num">
                      Value
                    </th>
                    <th scope="col">Provenance</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => {
                const value = values.get(row.key)!;
                return (
                  <tr
                    key={row.key}
                    data-variable={row.key}
                    aria-selected={highlighted(row) ? 'true' : undefined}
                  >
                    <th scope="row">
                      <code>{row.port.code_symbol}</code>
                      {row.port.name !== row.port.code_symbol && (
                        <span className="variable-description">{row.port.name}</span>
                      )}
                    </th>
                    <td>
                      <Button
                        variant="quiet"
                        size="sm"
                        aria-label={`Inspect component ${instanceName(row.instance.instance_id)}`}
                        onClick={() =>
                          onSelect({ kind: 'instance', instance_id: row.instance.instance_id })
                        }
                      >
                        {instanceName(row.instance.instance_id)}
                      </Button>
                    </td>
                    <td className="quantity-direction">{flow(row)}</td>
                    <td>{row.definition ?? <span className="context-line">No definition</span>}</td>
                    <td className="unit">{unitLabel(row.port.units)}</td>
                    {hasValues && (
                      <>
                        <td className={value.missing ? 'missing' : 'num'}>
                          {value.value === null ? (
                            value.text
                          ) : (
                            <>
                              <span
                                className="numeric-value"
                                title={`Full precision: ${value.text}`}
                              >
                                {formatNumber(value.value)}
                              </span>
                              {recordedUnit(value.units, row) && (
                                <span className="quantity-value-unit">
                                  {' '}
                                  {recordedUnit(value.units, row)}
                                </span>
                              )}
                            </>
                          )}
                        </td>
                        <td className="quantity-provenance">
                          {value.provenance || 'No provenance specified'}
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
              {!visible.length && (
                <tr>
                  <td colSpan={hasValues ? 7 : 5} className="quantities-empty">
                    No quantities match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </DataTable>
        </div>
        {onPastePorts && context.kind === 'model' && (
          <Disclosure>
            <summary>Paste port metadata</summary>
            <fieldset disabled={pasting}>
              <legend>Port metadata for the selected component</legend>
              <p>
                Component instance:{' '}
                {pasteScope?.instance_id ??
                  (pasteInstance || 'Select a component or variable first')}
                . Other instances keep their version.
              </p>
              {pasteScope && (
                <p className="identity">
                  Paste scope: {pasteScope.study_id} / {pasteScope.model_id} · draft{' '}
                  {pasteScope.draft_revision} · version {pasteScope.definition_version_id}
                </p>
              )}
              <label>
                Port metadata paste
                <TextArea
                  value={paste}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (!value) {
                      discardPaste();
                      return;
                    }
                    if (!paste) {
                      const target = snapshot.instances.find(
                        (i) => i.instance_id === pasteInstance,
                      );
                      setPasteScope(
                        target && 'draft_revision' in snapshot
                          ? {
                              study_id: snapshot.study_id,
                              model_id: snapshot.model_id,
                              draft_revision: snapshot.draft_revision,
                              instance_id: target.instance_id,
                              definition_version_id: target.definition_version_id,
                            }
                          : null,
                      );
                    }
                    setPaste(value);
                  }}
                  placeholder="port_id&#9;name&#9;code_symbol&#9;units"
                />
              </label>
              <p>
                Tab-separated header: port_id, then name, code_symbol or units. Values and
                provenance are not editable here.
              </p>
              {pasteError && <p role="alert">{pasteError}</p>}
              <Button disabled={!paste} onClick={() => void savePaste()}>
                Preview port metadata
              </Button>
              <Button disabled={!paste} onClick={discardPaste}>
                Discard port metadata paste
              </Button>
            </fieldset>
          </Disclosure>
        )}
      </section>
    </Panel>
  );
}
