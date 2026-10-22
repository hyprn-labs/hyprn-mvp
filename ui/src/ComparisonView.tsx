import { ActionGroup, Button, FilePicker, TransferSection } from './design';
import { ActionDialog, DialogActions } from './design';
import { useEffect, useRef, useState, type RefObject } from 'react';
import { HyprnMvpApi, message } from './api';
import type { ApplicationCapabilities, ModelDraftRead5, ModelPackageRead5, Study } from './contract';
import type { Snapshot } from './GraphView';
import {
  checkPackage,
  diagramHtml,
  diagramPng,
  diagramSvg,
  downloadBytes,
  variablesCsv,
  type ExportScope,
} from './exports';

const identity = (snapshot: Snapshot) =>
  'model_revision_id' in snapshot ? snapshot.model_revision_id : snapshot.draft_revision;
/** Export and import of the loaded model scope: portable model record, diagram and quantities. */
export function ComparisonView({
  api,
  study,
  scope,
  root,
  navigate,
  onImported,
  standalone = false,
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
  onImported: (model: ModelDraftRead5) => Promise<void>;
  /** Render the actions in place when no action host is supplied. */
  standalone?: boolean;
}) {
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState('');
  const generation = useRef(0);
  const [packageText, setPackageText] = useState(''),
    [preview, setPreview] = useState<{
      package: ModelPackageRead5;
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
      throw new Error('Open a saved model version before downloading a portable model record.');
    const snapshot = scope.snapshot;
    const value = (
      await api.request<ModelPackageRead5>(
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
      await api.mutate<ModelDraftRead5>(
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
    setNotice('Model imported.');
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
      {scope && (actionHost || standalone) && (
        <ActionDialog title="Export model" actionHost={actionHost} closeLabel="Close">
          {feedback}
          {scope && (
            <>
              <TransferSection
                title="Reusable model"
                description="Portable model record (JSON), including definitions and Python source."
              >
                <Button
                  disabled={busy || !('model_revision_id' in scope.snapshot)}
                  onClick={() => void action(exportPackage)}
                >
                  Download portable model record
                </Button>
                {!('model_revision_id' in scope.snapshot) && <p>Save a model version first.</p>}
              </TransferSection>
              <TransferSection
                title="Current view"
                description={
                  scope.run
                    ? 'Open this run’s Model tab for its diagram and quantities.'
                    : 'Loaded model only; unsaved edits are excluded.'
                }
              >
                <ActionGroup>
                  {(['svg', 'png', 'html', 'csv'] as const).map((kind) => (
                    <Button
                      disabled={busy}
                      key={kind}
                      onClick={() => void action((token) => exportView(kind, token))}
                    >
                      {kind === 'csv' ? 'Quantities CSV' : `Diagram ${kind.toUpperCase()}`}
                    </Button>
                  ))}
                </ActionGroup>
              </TransferSection>
            </>
          )}
        </ActionDialog>
      )}
      {allowImport && (actionHost || standalone) && (
        <ActionDialog
          title="Import model"
          actionHost={actionHost}
          disabled={!!api.pending}
          closeLabel="Close"
        >
          {feedback}
          <p>Portable model record (.json).</p>
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
          {!preview && (
            <DialogActions
              primary={
                <Button disabled={busy || !packageText} onClick={() => void action(previewImport)}>
                  Preview model import
                </Button>
              }
            />
          )}
          {preview && (
            <TransferSection title="Model import preview">
              <p>
                {preview.collision || preview.unsupported.length
                  ? 'Cannot import this model.'
                  : 'Ready to import'}
              </p>
              <p>
                {preview.package.revisions.length} model versions · {preview.package.files.length}{' '}
                files
              </p>
              <p>
                {preview.collision
                  ? 'This model already exists in this study.'
                  : 'Adds a separate model. Existing models stay unchanged.'}
              </p>
              {preview.unsupported.length > 0 && (
                <p role="alert">Unsupported capabilities: {preview.unsupported.join(', ')}</p>
              )}
              <DialogActions
                primary={
                  <Button
                    disabled={
                      busy || !!api.pending || preview.collision || !!preview.unsupported.length
                    }
                    onClick={() => navigate(() => void action(importPackage))}
                  >
                    Import model
                  </Button>
                }
              >
                <Button
                  disabled={busy}
                  onClick={() => {
                    invalidate();
                    setPreview(null);
                  }}
                >
                  Back
                </Button>
              </DialogActions>
            </TransferSection>
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
