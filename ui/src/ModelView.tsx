import { Button, Panel, Tabs, TextInput } from './design';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { EvidenceSnapshot, PortRead3 } from './contract';
import { GraphView, project, type Node, type RevealTarget, type Snapshot } from './GraphView';
import { XdsmView } from './XdsmView';
import { QuantitiesTable, type PortPasteAction, type VariableContext } from './VariablesTable';
import { SelectionInspector } from './SelectionInspector';
import type { MethodLink, MethodLinks } from './modelMethods';
import type { EditorGuard, Selection } from './workspaceModel';

/** Approach step context: its components are highlighted and scope the quantities table. */
export type ModelFocus = { instances: Set<string>; ports: Set<string>; links: Set<string> };
/** Draft authoring (Models page, current draft): the model editor renders its actions into the
 * canvas toolbar host and its editable Details (model or component) into the details host. */
export type ModelAuthoring = (hosts: { toolbar: HTMLDivElement | null; details: HTMLDivElement | null }) => ReactNode;

/**
 * The canonical model view: Graph | XDSM on top in a bounded
 * canvas, Details beside it, and the quantities table below at full width in its own scroll
 * region. One component everywhere a model is shown: Models (draft and versions), Run ›
 * Model, configuration "View model version" and approach "Open model version". It reads the
 * snapshot it is given and never fetches or substitutes another model.
 */
export function ModelView({ snapshot, selection, onSelect, values = { kind: 'model' }, evidence = [], authoring, onPastePorts, onPasteHandle, methods = { kind: 'none' }, onOpenStep, focus, idPrefix = '' }: {
  snapshot: Snapshot; selection: Selection; onSelect: (selection: Selection) => void; values?: VariableContext; evidence?: EvidenceSnapshot[];
  authoring?: ModelAuthoring; onPastePorts?: PortPasteAction; onPasteHandle?: (handle: EditorGuard) => void;
  methods?: MethodLinks; onOpenStep?: (link: MethodLink) => void; focus?: ModelFocus;
  /** Distinguishes element IDs when a second view is open in a dialog. */
  idPrefix?: string;
}) {
  const views = ['Graph', 'XDSM'] as const;
  const [view, setView] = useState<typeof views[number]>('Graph');
  const [detailsOpen, setDetailsOpen] = useState(true);
  const [authoringHost, setAuthoringHost] = useState<HTMLDivElement | null>(null);
  const [search, setSearch] = useState('');
  useEffect(() => { if (selection.kind !== 'none') setDetailsOpen(true); }, [selection]);
  const [pendingReveal, setPendingReveal] = useState<RevealTarget | undefined>();
  const [reveal, setReveal] = useState<RevealTarget | undefined>();
  const searchRequest = useRef(0);
  useEffect(() => {
    if (!pendingReveal || !('instance_id' in selection) || selection.instance_id !== pendingReveal.instance_id) return;
    setReveal(pendingReveal); setPendingReveal(undefined); setSearch('');
  }, [selection, pendingReveal]);
  function revealSearch(instance_id: string, port_id?: string) {
    setPendingReveal({ instance_id, port_id, request: ++searchRequest.current });
    onSelect({ kind: 'instance', instance_id });
  }
  const projection = useMemo(() => project(snapshot), [snapshot]);
  const trace = { nodes: focus?.instances ?? new Set<string>(), links: focus?.links ?? new Set<string>() };
  const needle = search.trim().toLocaleLowerCase();
  const findings: Array<{ node: Node; port: PortRead3 | undefined }> = needle ? projection.nodes.flatMap(n => [
    ...(`${n.instance.name} ${n.instance.instance_id}`.toLocaleLowerCase().includes(needle) ? [{ node: n, port: undefined }] : []),
    ...n.ports.filter(p => `${p.name} ${p.code_symbol}`.toLocaleLowerCase().includes(needle)).map(port => ({ node: n, port }))]) : [];
  const [detailsHost, setDetailsHost] = useState<HTMLDivElement | null>(null);
  const id = (name: string) => idPrefix + name;
  return (
    <section className="connected-views model-view" aria-label="Model view">
      <div className="connected-toolbar">
        <Tabs
          variant="segmented"
          label="Model projections"
          value={view}
          onChange={(value) => setView(value as typeof view)}
          items={views.map((name) => ({
            id: name,
            label: name,
            tabId: id('projection-' + name),
            panelId: id('panel-' + name),
          }))}
        />
        <div className="panel-toggles">
          {selection.kind !== 'none' && (
            <Button variant="quiet" size="sm" onClick={() => onSelect({ kind: 'none' })}>
              Clear selection
            </Button>
          )}
          <Button
            size="sm"
            aria-label="Details"
            aria-controls={id('model-details')}
            aria-expanded={detailsOpen}
            onClick={() => setDetailsOpen(!detailsOpen)}
          >
            {detailsOpen ? 'Hide' : 'Show'} Details
          </Button>
        </div>
      </div>
      <div className={`connected-workbench ${detailsOpen ? '' : 'details-closed'}`}>
        <Panel className="connected-main" bodyClassName="canvas-body" label="Model canvas">
          <div className="canvas-toolbar">
            <label className="canvas-search">
              <span className="sr-only">Search loaded model</span>
              <TextInput
                placeholder="Search this model…"
                type="search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPendingReveal(undefined);
                }}
              />
            </label>
            {needle && (
              <div
                className="search-findings"
                role="region"
                aria-label="Loaded model search results"
              >
                <Button onClick={() => setSearch('')}>Clear search</Button>
                {findings.map(({ node, port }) => (
                  <Button
                    key={node.instance.instance_id + (port?.port_id ?? '')}
                    onClick={() => revealSearch(node.instance.instance_id, port?.port_id)}
                  >
                    {node.instance.name}
                    {port && ` · ${port.name} (${port.code_symbol})`}
                  </Button>
                ))}
                {!findings.length && <p>No matches in this model.</p>}
              </div>
            )}
            <div className="model-creation" ref={setAuthoringHost} />
          </div>
          <div
            hidden={view !== 'Graph'}
            role="tabpanel"
            id={id('panel-Graph')}
            aria-labelledby={id('projection-Graph')}
          >
            <GraphView
              projection={projection}
              selection={selection}
              onSelect={onSelect}
              trace={trace}
              highlightedPorts={focus?.ports}
              reveal={view === 'Graph' ? reveal : undefined}
            />
          </div>
          <div
            hidden={view !== 'XDSM'}
            role="tabpanel"
            id={id('panel-XDSM')}
            aria-labelledby={id('projection-XDSM')}
          >
            <XdsmView
              projection={projection}
              selection={selection}
              onSelect={onSelect}
              trace={trace}
              reveal={view === 'XDSM' ? reveal : undefined}
            />
          </div>
          <div className="canvas-footer">
            <span>
              {projection.nodes.length}{' '}
              {projection.nodes.length === 1 ? 'component' : 'components'}{' '}
              · {snapshot.connections.length}{' '}
              {snapshot.connections.length === 1 ? 'connection' : 'connections'}
            </span>
            <span>Select a component to inspect its source and method</span>
          </div>
        </Panel>
        <div id={id('model-details')} className="connected-inspector" hidden={!detailsOpen}>
          <SelectionInspector
            snapshot={snapshot}
            projection={projection}
            selection={selection}
            onSelect={onSelect}
            context={values}
            evidence={evidence}
            draftHost={authoring ? setDetailsHost : undefined}
            methods={methods}
            onOpenStep={onOpenStep}
          />
        </div>
      </div>
      {authoring?.({ toolbar: authoringHost, details: detailsHost })}
      {!!projection.invalid.length && (
        <div role="alert">
          <p>
            ⚠ {projection.invalid.length} invalid links have unavailable or incompatible endpoints.
          </p>
          {projection.invalid.map((l) => (
            <p key={l.connection_id}>
              Connection {l.connection_id}: {l.source_ref.instance_id}/{l.source_ref.port_id} →{' '}
              {l.target_ref.instance_id}/{l.target_ref.port_id}
            </p>
          ))}
        </div>
      )}
      <QuantitiesTable
        snapshot={snapshot}
        projection={projection}
        selection={selection}
        onSelect={onSelect}
        context={values}
        focus={focus?.instances}
        onPastePorts={onPastePorts}
        onPasteHandle={onPasteHandle}
      />
    </section>
  );
}
