import type { HyprnMvpApi } from './api';
import { Button, Panel, Tabs, TextInput } from './design';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { EvidenceSnapshot, PortRead4, PortRef } from './contract';
import { GraphView, project, type Node, type RevealTarget, type Snapshot } from './GraphView';
import { XdsmView } from './XdsmView';
import { QuantitiesTable, type VariableContext } from './VariablesTable';
import { SelectionInspector, modelSummary } from './SelectionInspector';
import type { Selection } from './workspaceModel';

/** Approach step context: its components are highlighted and scope the quantities table. */
export type ModelFocus = { instances: Set<string>; ports: Set<string>; links: Set<string> };
/** Draft authoring (Models page, current draft): the model editor renders its actions into the
 * canvas toolbar host and its persistent component reader into the details host. */
export type QuantityEditRequest = PortRef & { request: number; invoker: HTMLElement | null };
export type ModelAuthoring = (hosts: {
  pane: string;
  /** Lets the editor reveal the pane that holds what it must focus. */
  showPane: (pane: string) => void;
  onModelExplanation: () => void;
  quantityEdit?: QuantityEditRequest;
  toolbar: HTMLDivElement | null;
  details: HTMLDivElement | null;
}) => ReactNode;

/** One canonical, snapshot-bound model reader: full-width diagram, model explanation
 * and a persistent component editor below it. Shared by draft, configuration and run readers. */
export function ModelView({
  api,
  studyId,
  snapshot,
  selection,
  onSelect,
  values = { kind: 'model' },
  evidence = [],
  authoring,
  focus,
  idPrefix = '',
  modelExplanation,
  onEditSelection,
}: {
  api?: HyprnMvpApi;
  studyId?: string;
  modelExplanation?: ReactNode;
  onEditSelection?: (selection: Selection, accepted: () => void) => void;
  snapshot: Snapshot;
  selection: Selection;
  onSelect: (selection: Selection) => void;
  values?: VariableContext;
  evidence?: EvidenceSnapshot[];
  authoring?: ModelAuthoring;
  focus?: ModelFocus;
  /** Distinguishes element IDs when a second view is open in a dialog. */
  idPrefix?: string;
}) {
  const views = ['Graph', 'XDSM'] as const;
  const [view, setView] = useState<(typeof views)[number]>('Graph');
  const [primary, setPrimary] = useState('Diagram');
  const [pane, setPane] = useState('Component');
  const [quantityEdit, setQuantityEdit] = useState<QuantityEditRequest>();
  useEffect(() => {
    if (selection.kind === 'connection' || selection.kind === 'connection_group')
      setPane('Component');
  }, [selection.kind]);
  const [authoringHost, setAuthoringHost] = useState<HTMLDivElement | null>(null);
  const [search, setSearch] = useState('');
  const [pendingReveal, setPendingReveal] = useState<RevealTarget | undefined>();
  const [reveal, setReveal] = useState<RevealTarget | undefined>();
  const searchRequest = useRef(0);
  useEffect(() => {
    if (
      !pendingReveal ||
      !('instance_id' in selection) ||
      selection.instance_id !== pendingReveal.instance_id
    )
      return;
    setReveal(pendingReveal);
    setPendingReveal(undefined);
    setSearch('');
  }, [selection, pendingReveal]);
  function revealSearch(instance_id: string, port_id?: string) {
    setPendingReveal({ instance_id, port_id, request: ++searchRequest.current });
    onSelect(
      port_id ? { kind: 'variable', instance_id, port_id } : { kind: 'instance', instance_id },
    );
  }
  const projection = useMemo(() => project(snapshot), [snapshot]);
  const trace = {
    nodes: focus?.instances ?? new Set<string>(),
    links: focus?.links ?? new Set<string>(),
  };
  const needle = search.trim().toLocaleLowerCase();
  const findings: Array<{ node: Node; port: PortRead4 | undefined }> = needle
    ? projection.nodes.flatMap((n) => [
        ...(`${n.instance.name} ${n.instance.instance_id}`.toLocaleLowerCase().includes(needle)
          ? [{ node: n, port: undefined }]
          : []),
        ...n.ports
          .filter((p) => `${p.name} ${p.code_symbol}`.toLocaleLowerCase().includes(needle))
          .map((port) => ({ node: n, port })),
      ])
    : [];
  const [detailsHost, setDetailsHost] = useState<HTMLDivElement | null>(null);
  const root = useRef<HTMLElement>(null);
  const selectedNode =
    'instance_id' in selection
      ? projection.nodes.find((n) => n.instance.instance_id === selection.instance_id)
      : undefined;
  const selectionMessage =
    selection.kind === 'none'
      ? 'Select a component to inspect its quantities and source'
      : selectedNode
        ? selectedNode.instance.name +
          (selection.kind === 'variable' ? ' · quantity selected' : ' · component selected')
        : 'Connection selected · endpoint mappings below';
  const id = (name: string) => idPrefix + name;
  return (
    <section ref={root} className="connected-views model-view" aria-label="Model view">
      <Tabs
        label="Model views"
        variant="segmented"
        value={primary}
        onChange={setPrimary}
        items={['Diagram', 'Model explanation'].map((label) => ({
          id: label,
          label,
          tabId: id('main-' + label.replaceAll(' ', '-')),
          panelId: id('main-panel-' + label.replaceAll(' ', '-')),
        }))}
      />
      <div
        role="tabpanel"
        id={id('main-panel-Model-explanation')}
        aria-labelledby={id('main-Model-explanation')}
        hidden={primary !== 'Model explanation'}
      >
        <Panel label="Model explanation reader">
          {modelExplanation ?? <p>No explanation is available for this model version.</p>}
        </Panel>
      </div>
      <div
        role="tabpanel"
        id={id('main-panel-Diagram')}
        aria-labelledby={id('main-Diagram')}
        hidden={primary !== 'Diagram'}
      >
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
          </div>
        </div>
        <div className="hf-model-workbench">
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
              <span>{modelSummary(snapshot)}</span>
              <span>{selectionMessage}</span>
            </div>
          </Panel>
          <section className="hf-component-reader" tabIndex={-1} aria-label="Component reader">
            <Tabs
              label="Component reading"
              value={pane}
              onChange={setPane}
              items={['Component', 'Python', 'Quantities'].map((label) => ({
                id: label,
                label,
                tabId: id('reading-' + label),
                panelId: id('reading-panel-' + label),
              }))}
            />
            <div
              id={id('model-details')}
              className="hf-component-content"
              hidden={pane === 'Quantities'}
            >
              <div
                role="tabpanel"
                id={id('reading-panel-' + (pane === 'Quantities' ? 'Component' : pane))}
                aria-labelledby={id('reading-' + (pane === 'Quantities' ? 'Component' : pane))}
              >
                <SelectionInspector
                  api={api}
                  studyId={studyId}
                  snapshot={snapshot}
                  projection={projection}
                  selection={selection}
                  onSelect={onSelect}
                  context={values}
                  evidence={evidence}
                  draftHost={authoring ? setDetailsHost : undefined}

                  pane={pane}
                  onModelExplanation={() => setPrimary('Model explanation')}
                />
              </div>
            </div>
            <div
              role="tabpanel"
              id={id('reading-panel-Quantities')}
              aria-labelledby={id('reading-Quantities')}
              hidden={pane !== 'Quantities'}
            >
              <QuantitiesTable
                snapshot={snapshot}
                projection={projection}
                selection={selection}
                onSelect={onSelect}
                context={values}
                focus={focus?.instances}
                onEditQuantity={
                  onEditSelection
                    ? (target) => {
                        const invoker = document.activeElement as HTMLElement;
                        onEditSelection({ kind: 'variable', ...target }, () => {
                          setQuantityEdit({ ...target, request: ++searchRequest.current, invoker });
                        });
                      }
                    : undefined
                }
              />
            </div>
          </section>
        </div>
      </div>
      {authoring?.({
        toolbar: authoringHost,
        details: detailsHost,
        pane,
        showPane: setPane,
        quantityEdit,
        onModelExplanation: () => setPrimary('Model explanation'),
      })}
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
    </section>
  );
}
