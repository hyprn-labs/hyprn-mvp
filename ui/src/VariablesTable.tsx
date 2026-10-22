import { OpenLink } from './design';
import { quantityDefinitions } from './quantityDefinitions';
import { unitLabel } from './unitLabels';
import { DataTable, Panel, Button, QuantityDirection } from './design/components';
import { TextInput, Select, SectionHelp } from './design/primitives';
import { formatNumber } from './design/numbers';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ConfigurationRevisionRead6, PortRef, RunHistoryRead6 } from './contract';
import type { Projection, Snapshot } from './GraphView';
import type { Selection } from './workspaceModel';

export type VariableContext =
  | { kind: 'model' }
  | {
      kind: 'configuration_draft';
      inputs: Array<{ target: PortRef; value: string; units: string; statement: string }>;
    }
  | { kind: 'configuration'; configuration: ConfigurationRevisionRead6 }
  | { kind: 'run'; history: RunHistoryRead6 };
export const quantityKey = (ref: PortRef) => `${ref.instance_id}/${ref.port_id}`;
const outputReasonLabels: Record<string, string> = {
  producer_failed: 'Producer failed',
  unassigned: 'Not assigned',
  nonfinite: 'Non-finite value',
  unavailable: 'Unavailable',
};
export function variableRows(snapshot: Snapshot, projection: Projection, context: VariableContext) {
  const quantities = quantityDefinitions(snapshot);
  return projection.nodes.flatMap((node) =>
    node.ports.map((port) => {
      const target = { instance_id: node.instance.instance_id, port_id: port.port_id };
      const key = quantityKey(target),
        incoming = snapshot.connections.filter((c) => quantityKey(c.target_ref) === key),
        outgoing = snapshot.connections.filter((c) => quantityKey(c.source_ref) === key);
      const configuration =
        context.kind === 'configuration'
          ? context.configuration
          : context.kind === 'run'
            ? context.history.configuration
            : null;
      const assignment = configuration?.inputs.find((i) => quantityKey(i.target) === key);
      const proposal =
        context.kind === 'configuration_draft'
          ? context.inputs.find((i) => quantityKey(i.target) === key)
          : undefined;
      const output =
        context.kind === 'run'
          ? context.history.results?.outputs.find((o) => quantityKey(o.target) === key)
          : undefined;
      let value = 'Declared · not computed',
        availability = 'not_computed',
        provenance = '',
        valueUnits = '';
      if (context.kind !== 'model') {
        value = incoming.length ? 'Connected reference' : 'Not computed';
        if (proposal) {
          provenance = proposal.statement;
          valueUnits = proposal.units;
          if (proposal.value.trim() && Number.isFinite(Number(proposal.value))) {
            value = proposal.value;
            availability = 'explicit';
          } else {
            value = 'Explicit value required';
            availability = 'missing';
          }
        } else if (assignment) {
          value = String(assignment.value);
          valueUnits = assignment.units;
          availability = 'explicit';
          provenance = `${assignment.provenance.kind}: ${assignment.provenance.statement}`;
        }
        if (context.kind === 'run' && port.direction === 'output') {
          provenance = 'Retained run output';
          valueUnits = output?.units ?? '';
          if (
            output?.availability === 'available' &&
            output.value !== null &&
            Number.isFinite(output.value)
          ) {
            value = String(output.value);
            availability = 'available';
          } else {
            value = 'not computed';
            availability = 'unavailable';
            provenance += output?.reason
              ? ' · ' +
                (Object.hasOwn(outputReasonLabels, output.reason)
                  ? outputReasonLabels[output.reason]
                  : 'Unknown reason')
              : ' · no verified value retained';
          }
        }
      }
      return {
        definition:
          quantities.find(
            (q) =>
              q.instance.instance_id === node.instance.instance_id &&
              q.port.port_id === port.port_id,
          )?.statement ?? null,
        key,
        target,
        instance: node.instance,
        port,
        incoming,
        outgoing,
        value,
        valueUnits,
        availability,
        provenance,
      };
    }),
  );
}
export type VariableRow = ReturnType<typeof variableRows>[number];
export function selectionHas(row: VariableRow, selection: Selection) {
  if (selection.kind === 'instance') return selection.instance_id === row.instance.instance_id;
  if (selection.kind === 'variable') return quantityKey(selection) === row.key;
  const ids =
    selection.kind === 'connection_group'
      ? selection.connection_ids
      : selection.kind === 'connection'
        ? [selection.connection_id]
        : [];
  return [...row.incoming, ...row.outgoing].some((c) => ids.includes(c.connection_id));
}
/** Display value of one quantity in its context (Scientific-states.md): an explicit value with
 * its own recorded unit, "unassigned" for a free input without a value, "not computed" for a
 * missing run output and "computed when run" before a run exists. A connected input in a run
 * shows the exact value its producer recorded, with the producer's unit and identity. The
 * export projection (`variableRows`) is unchanged. */
export function quantityValue(
  row: VariableRow,
  rows: VariableRow[],
  context: VariableContext,
  name: (id: string) => string,
): { value: number | null; text: string; units: string; provenance: string; missing: boolean } {
  const none = { value: null, units: '', missing: true };
  if (row.port.direction === 'input' && row.incoming.length) {
    const source = row.incoming[0].source_ref,
      producer = rows.find((r) => r.key === quantityKey(source));
    const from = `From ${name(source.instance_id)} · ${producer?.port.code_symbol ?? 'unavailable output'}`;
    if (context.kind === 'run' && producer?.availability === 'available')
      return {
        value: Number(producer.value),
        text: producer.value,
        units: producer.valueUnits,
        provenance: from,
        missing: false,
      };
    return {
      ...none,
      text: context.kind === 'run' ? 'not computed' : 'computed when run',
      provenance: from,
    };
  }
  if (
    ['available', 'explicit'].includes(row.availability) &&
    row.value.trim() !== '' &&
    Number.isFinite(Number(row.value))
  )
    return {
      value: Number(row.value),
      text: row.value,
      units: row.valueUnits,
      provenance: row.availability === 'available' ? 'Computed by this run' : row.provenance,
      missing: false,
    };
  if (row.port.direction === 'output') {
    if (context.kind === 'run')
      return {
        ...none,
        text: 'not computed',
        provenance: row.provenance
          .replace(/^Retained run output · /, '')
          .replace(/^no verified value retained$/, 'No verified value'),
      };
    return { ...none, text: 'computed when run', provenance: '' };
  }
  return { ...none, text: 'unassigned', provenance: row.provenance };
}
/** The value's own recorded unit, shown beside it only when it differs from the quantity's
 * declared unit (the Unit column); a received value is never silently relabelled. */
function recordedUnit(units: string, row: VariableRow) {
  const recorded = units || 'Dimensionless';
  return recorded.toLocaleLowerCase() === unitLabel(row.port.units).toLocaleLowerCase()
    ? ''
    : recorded;
}

/** Quantities of the canonical model view: one table below the canvas, in its
 * own scroll region. A selected component (or an approach step's components) filters and
 * highlights its rows; "Show all quantities" clears that filter. Connections are folded into
 * Direction ("Input · from …", "Output · to …"). */
export function QuantitiesTable({
  snapshot,
  projection,
  selection,
  onSelect,
  context,
  focus,
  onEditQuantity,
}: {
  snapshot: Snapshot;
  projection: Projection;
  selection: Selection;
  onSelect: (value: Selection) => void;
  context: VariableContext;
  focus?: Set<string>;
  onEditQuantity?: (target: PortRef) => void;
}) {
  const selectedInstance =
    selection.kind === 'instance' || selection.kind === 'variable' ? selection.instance_id : '';
  const rows = useMemo(
    () => variableRows(snapshot, projection, context),
    [snapshot, projection, context],
  );
  const [search, setSearch] = useState(''),
    [direction, setDirection] = useState('');
  const [sort, setSort] = useState<'variable' | 'component'>('component'),
    [descending, setDescending] = useState(false);
  // A selected component (or the approach step's components when nothing is selected) scopes the rows.
  const focusKey = [...(focus ?? [])].join('/');
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    setShowAll(false);
  }, [selectedInstance, focusKey]);
  const focused = projection.nodes
    .map((n) => n.instance.instance_id)
    .filter((id) => focus?.has(id));
  const scope = showAll
    ? []
    : selectedInstance
      ? [selectedInstance]
      : focused.length < projection.nodes.length
        ? focused
        : [];
  const scroll = useRef<HTMLDivElement>(null);
  const selectedKey = selection.kind === 'variable' ? quantityKey(selection) : '';
  useEffect(() => {
    if (!selectedKey) return;
    // Reveal the selected quantity inside the table's own scroll region; the page does not jump.
    const frame = requestAnimationFrame(() => {
      const region = scroll.current?.querySelector<HTMLElement>('.hf-table-wrap'),
        row = Array.from(region?.querySelectorAll<HTMLElement>('[data-variable]') ?? []).find(
          (el) => el.dataset.variable === selectedKey,
        );
      if (region && row) {
        const offset = row.getBoundingClientRect().top - region.getBoundingClientRect().top;
        region.scrollTop = Math.max(0, region.scrollTop + offset - region.clientHeight / 3);
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [selectedKey]);
  const needle = search.trim().toLocaleLowerCase(),
    hasValues = context.kind !== 'model';
  const instanceName = (id: string) => {
    const node = projection.nodes.find((n) => n.instance.instance_id === id);
    const peers = projection.nodes.filter((n) => n.instance.name === node?.instance.name);
    return (
      (node?.instance.name ?? 'Unavailable component') +
      (peers.length > 1
        ? ' · instance ' + (peers.findIndex((n) => n.instance.instance_id === id) + 1)
        : '')
    );
  };
  const endpoint = (ref: PortRef) => {
    const row = rows.find((r) => r.key === quantityKey(ref));
    return row
      ? `${instanceName(ref.instance_id)} · ${row.port.code_symbol}`
      : 'Unavailable quantity';
  };
  const values = new Map(rows.map((r) => [r.key, quantityValue(r, rows, context, instanceName)]));
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
  const showComponent = scope.length !== 1;
  const showDefinition = visible.some((row) => row.definition !== null);
  function order(next: typeof sort) {
    setDescending(sort === next ? !descending : false);
    setSort(next);
  }
  const flow = (row: VariableRow) =>
    row.port.direction === 'input' ? (
      <>
        <QuantityDirection direction="input" connected={!!row.incoming.length} />
        <span className="quantity-flow">
          {row.incoming.length
            ? row.incoming.map((c) => (
                <span className="quantity-flow" key={c.connection_id}>
                  from {endpoint(c.source_ref)}
                </span>
              ))
            : 'set in configuration'}
        </span>
      </>
    ) : row.port.direction === 'output' ? (
      <>
        <QuantityDirection direction="output" connected={!!row.outgoing.length} />
        <span className="quantity-flow">
          {row.outgoing.length
            ? row.outgoing.map((c) => (
                <span className="quantity-flow" key={c.connection_id}>
                  to {endpoint(c.target_ref)}
                </span>
              ))
            : 'model result'}
        </span>
      </>
    ) : (
      <>Residual</>
    );
  const highlighted = (row: VariableRow) =>
    (selection.kind !== 'instance' && selectionHas(row, selection)) ||
    (!selectedInstance &&
      focused.length < projection.nodes.length &&
      focused.includes(row.instance.instance_id));
  const scopeName = scope.length ? scope.map(instanceName).join(', ') : '';
  return (
    <Panel
      className="quantities-panel"
      label="Quantities"
      title="Quantities"
      help={<SectionHelp topic="quantities" />}
      headingLevel={3}
      actions={
        <>
          {scope.length > 0 && <Button size="sm" onClick={() => setShowAll(true)}>
            Show all quantities
          </Button>}
        </>
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
                if (e.target.value) {
                  setShowAll(false);
                  onSelect({ kind: 'instance', instance_id: e.target.value });
                } else setShowAll(true);
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
        <div ref={scroll} className="table-scroll variables-scroll quantities-scroll">
          <DataTable
            label="Quantities"
            regionLabel="Quantities table"
            dense
            className="quantities-table"
          >
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
                {showComponent && (
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
                )}
                <th scope="col">Direction</th>
                {showDefinition && <th scope="col">Definition</th>}
                <th scope="col">Unit</th>
                {onEditQuantity && <th scope="col">Actions</th>}
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
                    {showComponent && (
                      <td>
                        <OpenLink
                          size="sm"
                          aria-label={`Inspect component ${instanceName(row.instance.instance_id)}`}
                          onClick={() =>
                            onSelect({ kind: 'instance', instance_id: row.instance.instance_id })
                          }
                        >
                          {instanceName(row.instance.instance_id)}
                        </OpenLink>
                      </td>
                    )}
                    <td className="quantity-direction">{flow(row)}</td>
                    {showDefinition && (
                      <td className="quantity-definition">
                        {row.definition ?? <span className="context-line">No definition</span>}
                      </td>
                    )}
                    <td className="unit">{unitLabel(row.port.units)}</td>
                    {onEditQuantity && (
                      <td>
                        <Button size="sm" onClick={() => onEditQuantity(row.target)}>
                          Edit quantity
                        </Button>
                      </td>
                    )}
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
                  <td
                    colSpan={
                      3 +
                      Number(!!onEditQuantity) +
                      Number(showComponent) +
                      Number(showDefinition) +
                      (hasValues ? 2 : 0)
                    }
                    className="quantities-empty"
                  >
                    No quantities match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </DataTable>
        </div>
      </section>
    </Panel>
  );
}
