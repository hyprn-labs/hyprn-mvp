import { unitLabel } from './unitLabels';
import { DataTable } from './design';
import { Button, TextInput, Select, Disclosure, FilePicker } from './design';
import { ActionDialog } from './design';
import { useEffect, useRef, useState, type RefObject } from 'react';
import { HyprnMvpApi, message, sourceText } from './api';
import type { ApplicationCapabilities, ConfigurationRevision, ModelDraftRead4, ModelPackage, Study } from './contract';
import type { Snapshot } from './GraphView';
import { canonical, checkPackage, diagramHtml, diagramPng, diagramSvg, downloadBytes, exactSource, scopeLines, variablesCsv, type ExportScope } from './exports';

type Pair = { snapshot: Snapshot; configuration?: ConfigurationRevision };
type Row = { id: string; status: string; left?: unknown; right?: unknown };
function differences(left: unknown[], right: unknown[], key: (item: any) => string): Row[] {
  const a = new Map(left.map(item => [key(item), item])), b = new Map(right.map(item => [key(item), item]));
  return [...new Set([...a.keys(), ...b.keys()])].map(id => ({ id, status: !a.has(id) ? 'Added / unaligned on left' : !b.has(id) ? 'Removed / unaligned on right' : canonical(a.get(id)) === canonical(b.get(id)) ? 'Unchanged' : 'Changed', left: a.get(id), right: b.get(id) }));
}
/** Context as readers see it: description and boundary. Stored notes are not displayed. */
const shownContext = (pair: Pair) => pair.configuration ? { description: pair.configuration.context_snapshot.description, boundary: pair.configuration.context_snapshot.boundary } : null;
export function compareSnapshots(left: Pair, right: Pair) {
  const ports = (s: Snapshot) => s.instances.flatMap(i => (s.definitions.find(d => d.definition_version_id === i.definition_version_id)?.ports ?? []).map(p => ({ ...p, instance_id: i.instance_id })));
  const definitions = (s: Snapshot) => s.instances.map(i => ({ instance_id: i.instance_id, definition: s.definitions.find(d => d.definition_version_id === i.definition_version_id) }));
  const ref = (v: any) => `${v.target.instance_id}/${v.target.port_id}`;
  const groups: Array<{ name: string; rows: Row[] }> = [
    { name: 'Instances', rows: differences(left.snapshot.instances, right.snapshot.instances, i => i.instance_id) },
    { name: 'Definition versions and source hashes', rows: differences(definitions(left.snapshot), definitions(right.snapshot), d => d.instance_id) },
    { name: 'Ports and units', rows: differences(ports(left.snapshot), ports(right.snapshot), p => `${p.instance_id}/${p.port_id}`) },
    { name: 'Connections', rows: differences(left.snapshot.connections, right.snapshot.connections, c => c.connection_id) },
    // Notes are not displayed; records and exports still carry them unchanged.
    { name: 'Boundary mappings', rows: [{ id: 'model-boundaries', status: canonical(left.snapshot.boundary_mappings) === canonical(right.snapshot.boundary_mappings) ? 'Unchanged' : 'Changed', left: { boundaries: left.snapshot.boundary_mappings }, right: { boundaries: right.snapshot.boundary_mappings } }] },
  ];
  if (left.configuration || right.configuration) {
    groups.push({ name: 'Inputs, units and provenance', rows: differences(left.configuration?.inputs ?? [], right.configuration?.inputs ?? [], ref) },
      { name: 'Criteria', rows: differences(left.configuration?.criteria ?? [], right.configuration?.criteria ?? [], c => c.criterion_id) },
      { name: 'Evidence versions and scopes', rows: differences(left.configuration?.evidence_snapshots ?? [], right.configuration?.evidence_snapshots ?? [], e => e.evidence_version_id) },
      { name: 'Context and numerical settings', rows: [{ id: 'configuration-context', status: canonical([shownContext(left), left.configuration?.numerical ?? null]) === canonical([shownContext(right), right.configuration?.numerical ?? null]) ? 'Unchanged' : 'Changed', left: { context: shownContext(left) ?? undefined, numerical: left.configuration?.numerical }, right: { context: shownContext(right) ?? undefined, numerical: right.configuration?.numerical } }] });
  }
  return groups;
}
// Resolve display labels independently on each side; comparison alignment remains stable-ID based.
function semanticName(pair: Pair, id: string): string {
  const [instanceId, portId] = id.split('/'), instance = pair.snapshot.instances.find(i => i.instance_id === instanceId);
  if (instance) { const peers = pair.snapshot.instances.filter(i => i.name === instance.name), port = pair.snapshot.definitions.find(d => d.definition_version_id === instance.definition_version_id)?.ports.find(p => p.port_id === portId);
    return `${instance.name}${peers.length > 1 ? ` · instance ${peers.findIndex(i => i.instance_id === instanceId) + 1}` : ''}${port ? ` · ${port.name} (${port.code_symbol}) · ${unitLabel(port.units)}` : ''}`; }
  const criterion = pair.configuration?.criteria.find(c => c.criterion_id === id);
  if (criterion) return `Criterion · ${semanticName(pair, `${criterion.target.instance_id}/${criterion.target.port_id}`)}`;
  const connection = pair.snapshot.connections.find(c => c.connection_id === id);
  if (connection) return `${semanticName(pair, `${connection.source_ref.instance_id}/${connection.source_ref.port_id}`)} → ${semanticName(pair, `${connection.target_ref.instance_id}/${connection.target_ref.port_id}`)}`;
  return id === 'model-boundaries' ? 'Model boundaries' : id === 'configuration-context' ? 'Context and numerical settings' : 'Evidence reference';
}
function changedFields(row: Row) {
  function flatten(value: unknown, path = '', result: Record<string, unknown> = {}) {
    if (value !== null && typeof value === 'object') { for (const [key, child] of Object.entries(value)) flatten(child, path ? `${path}.${key}` : key, result); }
    else result[path] = value;
    return result;
  }
  const left = flatten(row.left), right = flatten(row.right);
  return [...new Set([...Object.keys(left), ...Object.keys(right)])].filter(key => JSON.stringify(left[key]) !== JSON.stringify(right[key])).map(key => {
    const exact = /(?:_id|sha256|digest|source_refs)(?:\.|$)/.test(key);
    const display = (value: unknown) => value === undefined ? 'Absent on this side' : value === null ? 'Not specified' : exact ? 'Identifier; see details' : typeof value === 'string' && !value ? '(empty)' : String(value);
    return { field: key.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()), left: display(left[key]), right: display(right[key]) };
  });
}
function sources(snapshot: Snapshot, instanceId: string) {
  const instance = snapshot.instances.find(i => i.instance_id === instanceId), definition = snapshot.definitions.find(d => d.definition_version_id === instance?.definition_version_id);
  if (!instance) return 'Unaligned instance: no source on this side.';
  if (!definition?.source_refs.length) return 'No authored source for this version.';
  return definition.source_refs.map(hash => { const source = snapshot.source_files.find(s => s.sha256 === hash); if (!source) return `Missing source ${hash}`; try { return `SHA-256 ${hash}\n${sourceText(source)}`; } catch { return `Source ${hash} cannot be shown as text; download it separately.`; } }).join('\n\n');
}
const identity = (snapshot: Snapshot) => 'model_revision_id' in snapshot ? snapshot.model_revision_id : snapshot.draft_revision;
export function ComparisonView({
  api,
  study,
  scope,
  root,
  navigate,
  onImported,
  showComparison = false,
  actionHost,
  allowImport = true,
}: {
  actionHost?: HTMLElement | null;
  allowImport?: boolean;
  api: HyprnMvpApi;
  study: Study;
  scope: ExportScope | null;
  root: RefObject<HTMLElement | null>;
  navigate: (action: () => void) => void;
  onImported: (model: ModelDraftRead4) => Promise<void>;
  showComparison?: boolean;
}) {
  const [target, setTarget] = useState('model_revision'),
    [modelId, setModelId] = useState(scope?.snapshot.model_id ?? ''),
    [revisionId, setRevisionId] = useState(''),
    [configurationId, setConfigurationId] = useState('');
  const [right, setRight] = useState<Pair | null>(null),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState('');
  const generation = useRef(0);
  const [packageText, setPackageText] = useState(''),
    [preview, setPreview] = useState<{
      package: ModelPackage;
      collision: boolean;
      unsupported: string[];
      revision: string;
      command: string;
    } | null>(null);
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );
  function invalidate() {
    generation.current++;
    setRight(null);
    setError(null);
    setBusy(false);
  }
  async function action(work: (token: number) => Promise<void>) {
    const token = ++generation.current;
    setBusy(true);
    setError(null);
    setNotice('');
    try {
      await work(token);
    } catch (e) {
      if (token === generation.current) setError(e);
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  const left: Pair | null = scope
    ? {
        snapshot: scope.snapshot,
        configuration:
          scope.values.kind === 'run'
            ? (scope.values.history.configuration ?? undefined)
            : scope.values.kind === 'configuration'
              ? scope.values.configuration
              : undefined,
      }
    : null;
  async function compare(token: number) {
    if (!scope) return;
    setRight(null);
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
    let pair: Pair;
    if (target === 'configuration') {
      if (!uuid.test(configurationId)) throw new Error('Enter a configuration version ID.');
      const frozen = await api.configuration(study.study_id, configurationId);
      pair = { snapshot: frozen.model_snapshot, configuration: frozen.configuration };
    } else if (target === 'current_draft')
      pair = { snapshot: await api.model(study.study_id, scope.snapshot.model_id) };
    else {
      if (!uuid.test(modelId) || !uuid.test(revisionId))
        throw new Error('Enter a model ID and a model version ID.');
      pair = { snapshot: await api.revision(study.study_id, modelId, revisionId) };
    }
    if (token === generation.current) setRight(pair);
  }
  async function exportView(kind: 'csv' | 'svg' | 'png' | 'html', token: number) {
    if (!scope || !root.current) throw new Error('No model is loaded.');
    const suffix = scope.run ?? identity(scope.snapshot);
    if (kind === 'csv') {
      downloadBytes(
        variablesCsv(root.current, scope),
        `hyprn-mvp-variables-${suffix}.csv`,
        'text/csv;charset=utf-8',
      );
      return;
    }
    const svg = diagramSvg(root.current, scope);
    if (kind === 'png') {
      const blob = await diagramPng(svg);
      if (token === generation.current)
        downloadBytes(blob, `hyprn-mvp-diagram-${suffix}.png`, 'image/png');
    } else if (kind === 'html')
      downloadBytes(
        diagramHtml(svg.text),
        `hyprn-mvp-diagram-${suffix}.html`,
        'text/html;charset=utf-8',
      );
    else downloadBytes(svg.text, `hyprn-mvp-diagram-${suffix}.svg`, 'image/svg+xml;charset=utf-8');
  }
  async function exportPackage(token: number) {
    if (!scope || !('model_revision_id' in scope.snapshot))
      throw new Error(
        'Open a saved model version, configuration or run ' +
          'before downloading a portable model record.',
      );
    const snapshot = scope.snapshot;
    const value = (
      await api.request<ModelPackage>(
        `/studies/${study.study_id}/models/${snapshot.model_id}/export` +
        `?model_revision_id=${snapshot.model_revision_id}`,
      )
    ).data;
    if (
      value.model_id !== snapshot.model_id ||
      value.model_revision_id !== snapshot.model_revision_id
    )
      throw new Error('Export identity mismatch.');
    const text = JSON.stringify(value, null, 2);
    await checkPackage(text);
    if (token === generation.current)
      downloadBytes(text, `hyprn-mvp-model-${snapshot.model_revision_id}.json`, 'application/json');
  }
  async function previewImport(token: number) {
    setPreview(null);
    const pkg = await checkPackage(packageText);
    const [caps, models, current] = await Promise.all([
      api.request<ApplicationCapabilities>('/capabilities'),
      api.models(study.study_id),
      api.study(study.study_id),
    ]);
    const supported = [...caps.data.engineering, ...caps.data.modeling];
    const unsupported = pkg.required_capabilities.filter((id) => !supported.includes(id));
    if (token === generation.current)
      setPreview({
        package: pkg,
        collision: models.some((m) => m.model_id === pkg.model_id),
        unsupported,
        revision: current.revision,
        command: crypto.randomUUID(),
      });
  }
  async function importPackage(token: number) {
    if (!preview || preview.collision || preview.unsupported.length)
      throw new Error(
        'Preview a supported portable model record ' +
          'that does not collide with an existing model first.',
      );
    const model = (
      await api.mutate<ModelDraftRead4>(
        `/studies/${study.study_id}/model-imports`,
        {
          command_id: preview.command,
          expected_revision: preview.revision,
          package: preview.package,
        } as { command_id: string },
        'model',
        study.study_id,
      )
    ).data;
    if (token !== generation.current) return;
    setPreview(null);
    setPackageText('');
    setNotice('Model imported with its preserved public identities. No source executed.');
    await onImported(model);
  }
  const feedback = (
    <>
      {busy && <p role="status">Reading or exporting the selected scope…</p>}
      {error != null && <p role="alert">{message(error)}</p>}
      {notice && <p role="status">{notice}</p>}
    </>
  );
  return (
    <section className="resource-portability" aria-label="Import and export">
      {(actionHost || showComparison) && (
        <ActionDialog title="Export model and data" actionHost={actionHost} disabled={!scope}>
          {feedback}
          {scope && (
            <>
              <Disclosure>
                <summary>Export scope</summary>
                <ul className="hf-export-scope">
                  {scopeLines(scope).map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </Disclosure>
              <p>
                {scope.run
                  ? 'Export the model and data saved with this run. ' +
                    'Open this run’s Model tab to export its diagram or displayed quantities.'
                  : 'Download the saved model or the current diagram and quantities.'}
              </p>
              <h3>Model</h3>
              <Button
                disabled={busy || !('model_revision_id' in scope.snapshot)}
                onClick={() => void action(exportPackage)}
              >
                Download portable model record
              </Button>
              {!('model_revision_id' in scope.snapshot) && (
                <p>Save a model version to download its portable model record.</p>
              )}
              <h3>Diagram & data</h3>
              <div className="actions">
                {(['svg', 'png', 'html', 'csv'] as const).map((kind) => (
                  <Button
                    disabled={busy}
                    key={kind}
                    onClick={() => void action((token) => exportView(kind, token))}
                  >
                    {kind === 'csv' ? 'Quantities CSV' : `Diagram ${kind.toUpperCase()}`}
                  </Button>
                ))}
              </div>
              <p>Uses the loaded model; unsaved edits are excluded.</p>
              <Disclosure>
                <summary>Source files</summary>
                {scope.snapshot.source_files.map((source, index) => (
                  <Button
                    key={source.sha256}
                    disabled={busy}
                    onClick={() =>
                      void action(async (token) => {
                        const raw = await exactSource(source);
                        if (token === generation.current)
                          downloadBytes(raw, `source-${source.sha256}.py`, 'text/x-python');
                      })
                    }
                  >
                    Download source {index + 1}
                  </Button>
                ))}
              </Disclosure>
              {showComparison && (
                <>
                  <h2>Compare</h2>
                  <Disclosure>
                    <summary>Comparison identities</summary>
                    <p>
                      Left: model {scope.snapshot.model_id} · {identity(scope.snapshot)}
                      {left?.configuration &&
                        ` · configuration ${left.configuration.configuration_revision_id}`}
                      . Stable IDs align entities; names never establish identity. Numerical
                      multi-run comparison is not provided.
                    </p>
                  </Disclosure>
                  <label>
                    Comparison target
                    <Select
                      value={target}
                      onChange={(e) => {
                        invalidate();
                        setTarget(e.target.value);
                      }}
                    >
                      <option value="model_revision">Model version</option>
                      <option value="configuration">Configuration version</option>
                      <option value="current_draft">Explicit read of current model draft</option>
                    </Select>
                  </label>
                  {target === 'model_revision' && (
                    <>
                      <label>
                        Comparison model ID
                        <TextInput
                          value={modelId}
                          onChange={(e) => {
                            invalidate();
                            setModelId(e.target.value);
                          }}
                        />
                      </label>
                      <label>
                        Comparison model version ID
                        <TextInput
                          value={revisionId}
                          onChange={(e) => {
                            invalidate();
                            setRevisionId(e.target.value);
                          }}
                        />
                      </label>
                    </>
                  )}
                  {target === 'configuration' && (
                    <label>
                      Comparison configuration ID
                      <TextInput
                        value={configurationId}
                        onChange={(e) => {
                          invalidate();
                          setConfigurationId(e.target.value);
                        }}
                      />
                    </label>
                  )}
                  <Button disabled={busy} onClick={() => void action(compare)}>
                    Read comparison target
                  </Button>
                  {left && right && (
                    <section aria-label="Comparison">
                      <h2>Comparison</h2>
                      <Disclosure>
                        <summary>Right side identity</summary>
                        <p>
                          Right: model {right.snapshot.model_id} · {identity(right.snapshot)}
                          {right.configuration &&
                            ` · configuration ${right.configuration.configuration_revision_id}`}
                        </p>
                      </Disclosure>
                      {left.snapshot.model_id !== right.snapshot.model_id && (
                        <p>
                          Unaligned model identities. Added/removed entities are not matched by
                          name.
                        </p>
                      )}
                      {compareSnapshots(left, right).map((group) => (
                        <Disclosure
                          key={group.name}
                          open={group.rows.some((row) => row.status !== 'Unchanged')}
                        >
                          <summary>
                            {group.name} ·{' '}
                            {group.rows.filter((row) => row.status !== 'Unchanged').length}{' '}
                            differences / {group.rows.length} identities
                          </summary>
                          {!group.rows.length && <p>No entries on either side.</p>}
                          {group.rows.map((row) => (
                            <article key={row.id}>
                              <h3>{row.status}</h3>
                              <p>
                                Left:{' '}
                                {row.left === undefined
                                  ? 'Unaligned — no object on this side'
                                  : semanticName(left, row.id)}
                              </p>
                              <p>
                                Right:{' '}
                                {row.right === undefined
                                  ? 'Unaligned — no object on this side'
                                  : semanticName(right, row.id)}
                              </p>
                              {row.status !== 'Unchanged' && (
                                <div className="table-scroll">
                                  <DataTable label="Changed fields">
                                    <thead>
                                      <tr>
                                        <th>Field</th>
                                        <th>Left</th>
                                        <th>Right</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {changedFields(row).map((field) => (
                                        <tr key={field.field}>
                                          <th scope="row">{field.field}</th>
                                          <td>{field.left}</td>
                                          <td>{field.right}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </DataTable>
                                </div>
                              )}
                              <Disclosure>
                                <summary>Identities and raw values</summary>
                                <p>{row.id}</p>
                                <div className="comparison-pair">
                                  <pre tabIndex={0} aria-label="Left semantic value">
                                    {row.left === undefined
                                      ? 'Unaligned'
                                      : JSON.stringify(row.left, null, 2)}
                                  </pre>
                                  <pre tabIndex={0} aria-label="Right semantic value">
                                    {row.right === undefined
                                      ? 'Unaligned'
                                      : JSON.stringify(row.right, null, 2)}
                                  </pre>
                                </div>
                              </Disclosure>
                            </article>
                          ))}
                        </Disclosure>
                      ))}
                      <h3>Side-by-side authored source</h3>
                      {[
                        ...new Set(
                          [...left.snapshot.instances, ...right.snapshot.instances]
                            .filter(
                              (i) =>
                                i.instance_id !== left.snapshot.root_instance_id &&
                                i.instance_id !== right.snapshot.root_instance_id,
                            )
                            .map((i) => i.instance_id),
                        ),
                      ].map((id) => (
                        <article key={id}>
                          <h3>
                            Left: {semanticName(left, id)} · Right: {semanticName(right, id)}
                          </h3>
                          <Disclosure>
                            <summary>Source identity</summary>
                            <p>Instance {id}</p>
                          </Disclosure>
                          <div className="comparison-pair">
                            <pre tabIndex={0} aria-label="Left authored source">
                              {sources(left.snapshot, id)}
                            </pre>
                            <pre tabIndex={0} aria-label="Right authored source">
                              {sources(right.snapshot, id)}
                            </pre>
                          </div>
                        </article>
                      ))}
                    </section>
                  )}
                </>
              )}
            </>
          )}
        </ActionDialog>
      )}
      {allowImport && (actionHost || showComparison) && (
        <ActionDialog title="Import" actionHost={actionHost} disabled={!!api.pending}>
          {feedback}
          <p>Choose a HYPRN MVP portable model record (.json).</p>
          <FilePicker
            label="Portable model record file"
            accept="application/json,.json"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              invalidate();
              setPreview(null);
              setPackageText('');
              if (file)
                void action(async (token) => {
                  if (file.size > 2 * 1024 * 1024 - 512)
                    throw new Error('The portable model record exceeds the 2 MiB limit.');
                  const text = await file.text();
                  if (token === generation.current) setPackageText(text);
                });
            }}
          />
          <Button disabled={busy || !packageText} onClick={() => void action(previewImport)}>
            Preview model import
          </Button>
          {preview && (
            <section aria-label="Model import preview">
              <h3>Ready to import</h3>
              <p>
                {preview.package.revisions.length} model versions ·{' '}
                {preview.package.files.length} files
              </p>
              <p>
                {preview.collision
                  ? 'This model already exists in this study.'
                  : 'Imported as a separate model, keeping its original identity.'}
              </p>
              {preview.unsupported.length > 0 && (
                <p role="alert">Unsupported capabilities: {preview.unsupported.join(', ')}</p>
              )}
              <Button
                disabled={
                  busy || !!api.pending || preview.collision || !!preview.unsupported.length
                }
                onClick={() => navigate(() => void action(importPackage))}
              >
                Import model
              </Button>
              <Button
                disabled={busy}
                onClick={() => {
                  invalidate();
                  setPreview(null);
                }}
              >
                Cancel
              </Button>
            </section>
          )}
          {api.pending && (
            <p role="alert">
              Command outcome is uncertain. Close this dialog and check the original command.
            </p>
          )}
        </ActionDialog>
      )}
      {feedback}
    </section>
  );
}
