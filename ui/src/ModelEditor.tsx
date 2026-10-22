import { currentDocumentation, useModelDocumentation } from './modelDocumentation';
import { DialogActions, FormField, ReadingSection } from './design';
import type { ModelExplanationContent2 } from './contract';
import type { QuantityEditRequest } from './ModelView';
import { Assumptions } from './Assumptions';
import { evidenceAccessLost } from './EvidenceView';
import type { ModelAssumption, ConfigurationAssumption, EvidenceRecord } from './api';
import { Button, TextInput, TextArea, Select, FilePicker, DialogFrame } from './design';
import { ActionDialog, SectionHeader } from './design';
import { type ComponentExplanation } from './SelectionInspector';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ApiError, HyprnMvpApi, message, sourceFromBytes, sourceFromText, sourceText } from './api';
import type {
  DefinitionChange4 as DefinitionChange,
  Edit4 as Edit,
  ModelDraftRead4,
  PortRead3 as Port,
  Source,
} from './api';
import { SourceEditor } from './SourceEditor';
import { ChangePreview, type ChangeProposal } from './ChangePreview';
import { UnitEditor, UnitGuidance, useUnitCatalog } from './UnitEditor';
import { quantityDefinitions } from './quantityDefinitions';
import { unitDraft, unitLabel, unitDeclaration, type UnitDraft } from './unitLabels';
import type { EditorGuard, Selection } from './workspaceModel';

export type EditorHandle = EditorGuard;
type Props = {
  hosts: {
    toolbar: HTMLDivElement | null;
    details: HTMLDivElement | null;
    pane: string;
    showPane?: (pane: string) => void;
    quantityEdit?: QuantityEditRequest;
  };
  explain: ComponentExplanation;
  modelActionHost?: HTMLDivElement | null;
  api: HyprnMvpApi;
  model: ModelDraftRead4;
  onModel: (model: ModelDraftRead4) => void;
  onHandle: (handle: EditorHandle) => void;
  navigate: (action: () => void) => void;
  selection: Selection;
  onSelect: (selection: Selection) => void;
};
type PortDraft = {
  port_id?: string;
  direction: 'input' | 'output' | 'residual';
  name: string;
  code_symbol: string;
  units: UnitDraft;
  statement?: string;
};
const portDraft = (p: Port): PortDraft => ({
  port_id: p.port_id,
  direction: p.direction,
  name: p.name,
  code_symbol: p.code_symbol,
  units: unitDraft(p.units),
});

export function ModelEditor({
  hosts,
  explain,
  modelActionHost,
  api,
  model,
  onModel,
  onHandle,
  navigate,
  selection,
  onSelect,
}: Props) {
  const documentation = useModelDocumentation(api, model);
  const [documentationForm, setDocumentationForm] = useState<{
    owner: string;
    description: string;
    limits: string;
  } | null>(null);
  const documentationBase = useRef('');
  const documentationSnapshot = useRef<{
    content: ModelExplanationContent2;
    revision: string | null;
  } | null>(null);
  const beforeDocumentationEdit = useRef<ModelAssumption[]>([]);
  const [documentationSaved, setDocumentationSaved] = useState(0);
  const documentationDirty =
    !!documentationForm && JSON.stringify(documentationForm) !== documentationBase.current;
  const quantityDialog = useRef<HTMLDialogElement>(null);
  const [quantityNotice, setQuantityNotice] = useState('');
  const [quantityPort, setQuantityPort] = useState('');
  const quantityInvoker = useRef<HTMLElement | null>(null);
  // Quantities open from the Component actions menu, which closes first; focus returns to its trigger.
  const componentActions = useRef<HTMLSpanElement>(null);
  const handledQuantityRequest = useRef(0);
  const guidance = useUnitCatalog(api, model.study_id, model.model_id);
  // Model format 4 edits only where the service advertises them; a failed read keeps the
  // earlier choice (format 4 only for quantity definitions or an existing format 4 draft).
  const [format4, setFormat4] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api
      .capabilities(controller.signal)
      .then((c) => setFormat4(c.model_formats.edit_request.includes('4')))
      .catch(() => setFormat4(false));
    return () => controller.abort();
  }, [api]);

  const selected =
    selection.kind === 'instance' || selection.kind === 'variable' ? selection.instance_id : '';
  // The local draft and its comparison/CAS base must advance together. A prop
  // refresh can arrive while the user is editing, including an open assumption.
  const [assumptionBase, setAssumptionBase] = useState(model);
  const baselineAssumptions = 'assumptions' in assumptionBase ? assumptionBase.assumptions : [];
  const [assumptions, setAssumptions] = useState<ModelAssumption[]>(baselineAssumptions);
  const [assumptionEditing, setAssumptionEditing] = useState(false),
    [assumptionEpoch, setAssumptionEpoch] = useState(0);
  const [assumptionRecords, setAssumptionRecords] = useState<EvidenceRecord[]>([]),
    [assumptionError, setAssumptionError] = useState(''),
    [assumptionLoading, setAssumptionLoading] = useState(true),
    [assumptionRevoked, setAssumptionRevoked] = useState(false);
  const assumptionDirty = JSON.stringify(assumptions) !== JSON.stringify(baselineAssumptions);
  const assumptionScope =
    model.study_id + '/' + model.model_id + '/' + model.draft_revision + '/' + api.actor;
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setAssumptionRecords([]);
    setAssumptionLoading(true);
    setAssumptionError('');
    void api
      .assumptionEvidence(
        model.study_id,
        model.model_id,
        { draft_revision: model.draft_revision },
        controller.signal,
      )
      .then((result) => {
        if (!current || result.draft_revision !== model.draft_revision) return;
        setAssumptionRecords(result.evidence);
        setAssumptionRevoked(false);
      })
      .catch((e) => {
        if (current) {
          setAssumptionError(message(e));
          if (evidenceAccessLost(e)) {
            setAssumptionRecords([]);
            setAssumptionRevoked(true);
          }
        }
      })
      .finally(() => {
        if (current) setAssumptionLoading(false);
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [assumptionScope]);
  function assumptionEdits(): Edit[] {
    const edits: Edit[] = baselineAssumptions
      .filter((a) => !assumptions.some((b) => b.assumption_id === a.assumption_id))
      .map((a) => ({ kind: 'remove_assumption', assumption_id: a.assumption_id }));
    for (const item of assumptions) {
      const prior = baselineAssumptions.find((a) => a.assumption_id === item.assumption_id);
      if (!prior)
        edits.push({
          kind: 'add_assumption',
          temp_key: 'assumption_' + item.assumption_id.replaceAll('-', ''),
          owner: item.owner,
          statement: item.statement,
          evidence_links: item.evidence_links,
        });
      else if (JSON.stringify(item) !== JSON.stringify(prior))
        edits.push({
          kind: 'update_assumption',
          assumption_id: item.assumption_id,
          statement: item.statement,
          evidence_links: item.evidence_links,
        });
    }
    return edits;
  }
  function acceptAssumptions(snapshot: ModelDraftRead4) {
    setAssumptionBase(snapshot);
    setAssumptions('assumptions' in snapshot ? snapshot.assumptions : []);
    setAssumptionEditing(false);
    setAssumptionEpoch((n) => n + 1);
  }
  function assumptionView(owner: ModelAssumption['owner'], label: string, editable = true) {
    const owns = (a: ModelAssumption) =>
      a.owner.kind === owner.kind &&
      (owner.kind === 'model' ||
        (a.owner.kind === 'instance' && a.owner.instance_id === owner.instance_id));
    return (
      <>
        {assumptionLoading && <p role="status">Loading evidence…</p>}
        {assumptionError && <p role="alert">{assumptionError}</p>}
        <Assumptions
          headingLevel={4}
          ownerKey={
            model.study_id +
            '/' +
            model.model_id +
            '/' +
            assumptionBase.draft_revision +
            '/' +
            api.actor +
            '/' +
            JSON.stringify(owner) +
            '/' +
            assumptionEpoch
          }
          ownerLabel={label}
          items={assumptions.filter(owns)}
          records={assumptionRecords}
          editable={
            editable
              ? {
                  api,
                  studyId: model.study_id,
                  scope: { scope_version: '1', kind: 'study', study_id: model.study_id },
                  disabled: blocked || assumptionRevoked,
                  onDirty: setAssumptionEditing,
                  onRecords: (records) =>
                    setAssumptionRecords((old) =>
                      records.length
                        ? [
                            ...old.filter(
                              (r) =>
                                !records.some(
                                  (n) => n.evidence_version_id === r.evidence_version_id,
                                ),
                            ),
                            ...records,
                          ]
                        : [],
                    ),
                  // Existing items keep their recorded owner object: re-creating it (different key order)
                  // made unchanged assumptions compare as edited and sent a spurious update_assumption.
                  onChange: (items: ConfigurationAssumption[]) =>
                    setAssumptions((old) => [
                      ...old.filter((a) => !owns(a)),
                      ...items.map((a) => ({
                        ...a,
                        owner:
                          old.find((o) => o.assumption_id === a.assumption_id && owns(o))?.owner ??
                          owner,
                      })),
                    ]),
                }
              : undefined
          }
        />
        {editable && assumptionDirty && (
          <p role="status">Unsaved local edits. Save the model draft to keep these changes.</p>
        )}
      </>
    );
  }
  const [loaded, setLoaded] = useState('');
  const [componentSaved, setComponentSaved] = useState(0),
    [connectionSaved, setConnectionSaved] = useState(0);
  const [name, setName] = useState('');
  const [explanation, setExplanation] = useState('');
  const [text, setText] = useState('');
  const [ports, setPorts] = useState<PortDraft[]>([]);
  const [imported, setImported] = useState<Source | null>(null);
  const [selectionAfterSave, setSelectionAfterSave] = useState('');
  const [newName, setNewName] = useState('');
  const [inputs, setInputs] = useState('');
  const [outputs, setOutputs] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [proposal, setProposal] = useState<ChangeProposal | null>(null);
  const [targets, setTargets] = useState<string[]>([]),
    [checked, setChecked] = useState<string[]>([]),
    [links, setLinks] = useState<string[]>([]);
  const [queued, setQueued] = useState<Array<{ from: string; to: string }>>([]),
    [renamed, setRenamed] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [review, setReview] = useState<ModelDraftRead4 | null>(null);
  const invoker = useRef<HTMLElement | null>(null);
  const code = useRef<HTMLTextAreaElement>(null);
  const errorFocused = useRef<unknown>(null);
  const original = useRef({
    name: '',
    explanation: '',
    text: '',
    ports: '',
    source: null as Source | null,
  });
  const instance = model.instances.find((i) => i.instance_id === selected);
  const definition = model.definitions.find(
    (d) => d.definition_version_id === instance?.definition_version_id,
  );
  const importRequest = useRef(0),
    importPending = useRef(false);
  const importScope = `${model.study_id}/${model.model_id}/${model.draft_revision}/${selected}/${definition?.definition_version_id ?? ''}`;
  const currentImportScope = useRef(importScope);
  currentImportScope.current = importScope;
  function cancelImport() {
    importRequest.current++;
    if (importPending.current) {
      importPending.current = false;
      setBusy(false);
      setStatus('Source import discarded after its editing context changed.');
    }
  }
  useEffect(() => {
    cancelImport();
  }, [importScope]);
  useEffect(
    () => () => {
      importRequest.current++;
      importPending.current = false;
    },
    [],
  );
  async function importFile(file: File) {
    const request = ++importRequest.current,
      scope = importScope;
    const current = () => request === importRequest.current && scope === currentImportScope.current;
    importPending.current = true;
    setBusy(true);
    setError(null);
    setStatus('Reading source file…');
    try {
      if (file.size > 256 * 1024) throw new Error('Source must be at most 256 KiB.');
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (!current()) return;
      const source = await sourceFromBytes(bytes);
      if (!current()) return;
      setText(sourceText(source));
      setImported(source);
      setStatus('Source file loaded locally; save to keep it');
    } catch (e) {
      if (current()) {
        setError(e);
        setStatus('');
      }
    } finally {
      if (current()) {
        importPending.current = false;
        setBusy(false);
      }
    }
  }
  const components = model.instances.filter((i) => i.instance_id !== model.root_instance_id);
  const dirty =
    !!instance &&
    loaded === selected &&
    (name !== original.current.name ||
      explanation !== original.current.explanation ||
      text !== original.current.text ||
      JSON.stringify(ports) !== original.current.ports ||
      imported !== null);
  const authoringDirty =
    dirty ||
    documentationDirty ||
    assumptionDirty ||
    assumptionEditing ||
    !!(
      newName ||
      inputs ||
      outputs ||
      (renamed && renamed !== model.name) ||
      from ||
      to ||
      queued.length
    );
  useEffect(() => {
    if (model !== assumptionBase && !authoringDirty && !busy && !proposal && !api.pending)
      acceptAssumptions(model);
  }, [model, assumptionBase, authoringDirty, busy, proposal, api.pending]);
  useEffect(() => {
    if (loaded !== selected || !dirty) load(selected);
  }, [selected, model.draft_revision]);
  useEffect(() => {
    // Each new error restores focus once: wait until the saving fieldset is enabled and the
    // Python pane is shown, then focus the source editor. Later tab changes are the user's.
    if (!error) {
      errorFocused.current = null;
      return;
    }
    if (busy || documentationForm || !code.current || errorFocused.current === error) return;
    if (hosts.showPane && hosts.pane !== 'Python') {
      hosts.showPane('Python');
      return;
    }
    errorFocused.current = error;
    const details = code.current.closest('details');
    if (details) details.open = true;
    code.current.focus();
  }, [error, busy, hosts.pane]);
  function load(mid: string, snapshot = model) {
    cancelImport();
    const i = snapshot.instances.find((x) => x.instance_id === mid);
    const d = snapshot.definitions.find(
      (x) => x.definition_version_id === i?.definition_version_id,
    );
    const source = snapshot.source_files.find((s) => d?.source_refs.includes(s.sha256));
    // Selection and source are resolved from one authoritative response, atomically.
    if (!i || !d || !source) {
      setLoaded('');
      setName('');
      setExplanation('');
      setText('');
      setPorts([]);
      setImported(null);
      return;
    }
    try {
      const decoded = sourceText(source);
      const quantities = quantityDefinitions(snapshot);
      const ps = d.ports.map((p) => ({
        ...portDraft(p),
        statement:
          quantities.find((q) => q.instance.instance_id === mid && q.port.port_id === p.port_id)
            ?.statement ?? '',
      }));
      const explanation = snapshot.annotations.find((a) => a.element_ref === mid)?.text ?? '';
      original.current = {
        name: i.name,
        explanation,
        text: decoded,
        ports: JSON.stringify(ps),
        source,
      };
      setName(i.name);
      setExplanation(explanation);
      setText(decoded);
      setPorts(ps);
      setImported(null);
      setLoaded(mid);
      setTargets([mid]);
      setError(null);
      setReview(null);
    } catch (e) {
      setLoaded('');
      setError(e);
    }
  }
  function propose(
    edits: Edit[],
    safe = 'Keep editing',
    apply = 'Apply changes',
  ): Promise<ModelDraftRead4 | null> {
    if (!guidance.catalog)
      return Promise.reject(
        new Error('Unit guidance is unavailable. Retry unit guidance. Your edits are kept.'),
      );
    if (api.pending)
      return Promise.reject(new Error('Check the original command before making more changes.'));
    const envelope = {
      command_id: crypto.randomUUID(),
      expected_revision: assumptionBase.draft_revision,
    };
    // A format 4 edit upgrades an earlier draft, and only a format 4 model version can be
    // configured, so every edit uses it where the service supports it.
    const descriptive =
      format4 ||
      assumptionBase.schema_version === '4' ||
      edits.some(
        (e) =>
          e.kind === 'revise_definition' &&
          e.changes.some(
            (c) => c.kind === 'set_quantity_definition' || c.kind === 'clear_quantity_definition',
          ),
      );
    // The runtime predicate excludes new operations before selecting the legacy envelope.
    const command: import('./contract').ApplyRead4 = descriptive
      ? { ...envelope, schema_version: '4', edits: structuredClone(edits) }
      : {
          ...envelope,
          schema_version: '3',
          edits: structuredClone(edits) as import('./contract').Edit3[],
        };
    return new Promise((resolve) =>
      setProposal({
        before: assumptionBase,
        invoker: invoker.current,
        command,
        safe,
        apply,
        finish: (updated) => {
          setProposal(null);
          resolve(updated);
        },
      }),
    );
  }
  const toggle = (values: string[], id: string) =>
    values.includes(id) ? values.filter((x) => x !== id) : [...values, id];
  function connectionEdit(row: { from: string; to: string }, index: number): Edit {
    const [si, sp] = row.from.split('/'),
      [ti, tp] = row.to.split('/');
    return {
      kind: 'connect',
      temp_key: `connection${index}`,
      source_ref: { instance_id: si, port_id: sp },
      target_ref: { instance_id: ti, port_id: tp },
    };
  }
  async function commitBatch(edits: Edit[], safe = 'Keep editing', apply = 'Apply changes') {
    const updated = await propose(edits, safe, apply);
    if (!updated) return false;
    acceptAssumptions(updated);
    onModel(updated);
    setChecked([]);
    setLinks([]);
    setStatus('Changes applied');
    return true;
  }
  async function act(action: () => Promise<void>) {
    if (busy) return;
    invoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setBusy(true);
    setError(null);
    setStatus('Working…');
    try {
      await action();
    } catch (e) {
      setError(e);
      setStatus('');
    } finally {
      setBusy(false);
    }
  }
  async function save(all = false): Promise<boolean> {
    if (
      !(all ? authoringDirty : dirty || documentationDirty || assumptionDirty || assumptionEditing)
    )
      return true;
    if (busy || (dirty && (!instance || !definition))) return false;
    invoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setBusy(true);
    setError(null);
    setStatus('Saving component…');
    let modelSaved = false;
    try {
      if (assumptionEditing)
        throw new Error('Apply or discard the open assumption before saving the model draft.');
      const edits: Edit[] = assumptionEdits();
      let removing = false;
      if (dirty && instance && definition) {
        const changes: DefinitionChange[] = [];
        const editedPorts = ports;
        if (new TextEncoder().encode(text).length > 256 * 1024)
          throw new Error('Python source: maximum size is 256 KiB. Your text is preserved.');
        if (text.includes('\0'))
          throw new Error(
            `Python source, line ${text.slice(0, text.indexOf('\0')).split('\n').length}: ` +
              'null characters are invalid. Your text is preserved.',
          );
        if (text !== original.current.text || imported) {
          changes.push({ kind: 'set_source', source: imported ?? (await sourceFromText(text)) });
        }
        const baseline = definition.ports;
        for (const p of baseline)
          if (!editedPorts.some((x) => x.port_id === p.port_id))
            changes.push({ kind: 'remove_port', port_id: p.port_id });
        editedPorts.forEach((p, index) => {
          const prior = baseline.find((x) => x.port_id === p.port_id);
          if (!prior)
            changes.push({
              kind: 'create_port',
              temp_key: `port${index}`,
              direction: p.direction,
              name: p.name,
              code_symbol: p.code_symbol,
              units: unitDeclaration(p.units, guidance.catalog),
              value_type: 'real_scalar',
            });
          else if (
            p.name !== prior.name ||
            p.code_symbol !== prior.code_symbol ||
            JSON.stringify(p.units) !== JSON.stringify(unitDraft(prior.units))
          )
            changes.push({
              kind: 'update_port',
              port_id: prior.port_id,
              fields: {
                name: p.name,
                code_symbol: p.code_symbol,
                units: unitDeclaration(p.units, guidance.catalog),
              },
            });
        });
        for (const p of editedPorts) {
          // New ports acquire their exact IDs after the first atomic save.
          if (!p.port_id) continue;
          const prior =
            quantityDefinitions(model).find(
              (q) => q.instance.instance_id === selected && q.port.port_id === p.port_id,
            )?.statement ?? '';
          const statement = p.statement ?? '';
          if (statement !== prior) {
            if (statement && (!statement.trim() || statement.length > 4096))
              throw new Error(
                'Quantity definition must be nonblank and at most 4096 ' +
                  'characters. Your edits are kept.',
              );
            changes.push(
              statement
                ? { kind: 'set_quantity_definition', port_id: p.port_id, statement }
                : { kind: 'clear_quantity_definition', port_id: p.port_id },
            );
          }
        }
        if (changes.length) {
          if (!targets.length)
            throw new Error('Select at least one instance to receive this version.');
          const removed = new Set(
            changes.flatMap((c) => (c.kind === 'remove_port' ? [c.port_id] : [])),
          );
          for (const connection of model.connections)
            if (
              [connection.source_ref, connection.target_ref].some(
                (ref) => targets.includes(ref.instance_id) && removed.has(ref.port_id),
              )
            )
              edits.push({ kind: 'disconnect', connection_id: connection.connection_id });
          edits.push({
            kind: 'revise_definition',
            temp_key: 'revised',
            definition_id: definition.definition_id,
            expected_definition_version_id: definition.definition_version_id,
            changes,
          });
          for (const id of targets)
            edits.push({
              kind: 'replace_local_instance_version',
              instance_id: id,
              expected_definition_version_id: definition.definition_version_id,
              version_ref: { temp_key: 'revised' },
            });
        }
        if (name !== original.current.name)
          edits.push({ kind: 'rename_instance', instance_id: selected, name });
        if (explanation !== original.current.explanation)
          edits.push({ kind: 'set_annotation', element_ref: selected, text: explanation });
        removing = changes.some((c) => c.kind === 'remove_port');
      }
      if (all) {
        if (renamed && renamed !== model.name) {
          if (!renamed.trim())
            throw new Error('Enter a model name. Your pending edits are preserved.');
          edits.push({ kind: 'rename_model', name: renamed });
        }
        if (newName || inputs || outputs) edits.push(...(await newComponentEdits()));
        edits.push(...queued.map(connectionEdit));
        if (from || to) {
          if (!from || !to)
            throw new Error(
              'Choose both connection endpoints or clear the pending selection. ' +
                'Your edits are preserved.',
            );
          edits.push(connectionEdit({ from, to }, queued.length));
        }
      }
      if (edits.length) {
        const updated = await propose(
          edits,
          removing ? 'Keep quantities' : 'Keep editing',
          removing ? 'Remove quantities' : 'Apply changes',
        );
        if (!updated) {
          setStatus('Proposal kept locally');
          return false;
        }
        modelSaved = true;
        acceptAssumptions(updated);
        onModel(updated);
        load(selected, updated);
      }
      if (documentationForm && documentationDirty) {
        const content = documentationSnapshot.current!.content;
        const { owner, description, limits } = documentationForm;
        const next =
          owner === 'model'
            ? { ...content, represents: description, limits }
            : {
                ...content,
                component_details: [
                  ...content.component_details.filter((item) => item.instance_id !== owner),
                  { instance_id: owner, description, limits },
                ],
              };
        await documentation.save(next, documentationSnapshot.current!.revision);
        documentationBase.current = JSON.stringify(documentationForm);
      }
      setDocumentationForm(null);
      setDocumentationSaved((n) => n + 1);
      if (all) clearAuthoringDraft();
      setStatus(all ? 'Authoring changes saved' : 'Component saved');
      return true;
    } catch (e) {
      setError(e);
      setStatus(
        modelSaved ? 'Model changes were saved. Description and limits still need saving.' : '',
      );
      if (code.current && !documentationForm) {
        const details = code.current.closest('details');
        if (details) details.open = true;
        code.current.focus();
      }
      return false;
    } finally {
      setBusy(false);
    }
  }
  function clearAuthoringDraft() {
    setQueued([]);
    setRenamed('');
    setNewName('');
    setInputs('');
    setOutputs('');
    setFrom('');
    setTo('');
    setSelectionAfterSave('');
  }
  function discard() {
    setDocumentationForm(null);
    acceptAssumptions(model);
    clearAuthoringDraft();
    load(selected);
    setStatus('Authoring changes discarded');
  }
  useEffect(() => {
    onHandle({ dirty: authoringDirty, save: () => save(true), discard });
  });
  useEffect(() => {
    if (selectionAfterSave && !authoringDirty) {
      setSelectionAfterSave('');
      onSelect({ kind: 'instance', instance_id: selectionAfterSave });
    }
  }, [selectionAfterSave, authoringDirty]);
  async function newComponentEdits(): Promise<Edit[]> {
    const ins = inputs
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      outs = outputs
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    if (
      !newName.trim() ||
      !outs.length ||
      [...ins, ...outs].some((s) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(s)) ||
      new Set([...ins, ...outs]).size !== ins.length + outs.length
    )
      throw new Error(
        'Enter a component name and unique Python quantity symbols; declare at least one output.',
      );
    // No hidden physical defaults: starter declares access but requires authored output equations.
    const starter =
      '# Edit the equation for each declared output before running.\n' +
      ins.map((s) => `${s} = inputs[${JSON.stringify(s)}]\n`).join('') +
      outs.map((s) => `# outputs[${JSON.stringify(s)}] = your_equation\n`).join('');
    return [
      {
        kind: 'create_definition',
        temp_key: 'component',
        definition_kind: 'explicit_component',
        name: newName,
        ports: [
          ...ins.map((s) => ({ s, direction: 'input' as const })),
          ...outs.map((s) => ({ s, direction: 'output' as const })),
        ].map((p, i) => ({
          temp_key: `port${i}`,
          name: p.s,
          code_symbol: p.s,
          direction: p.direction,
          value_type: 'real_scalar',
          units: { kind: 'unspecified' },
        })),
        source: await sourceFromText(starter),
      },
      { kind: 'instantiate', temp_key: 'instance', version_ref: { temp_key: 'component' } },
    ];
  }
  async function addComponent() {
    const before = new Set(components.map((i) => i.instance_id));
    const updated = await propose(await newComponentEdits());
    if (!updated) {
      setStatus('Proposal kept locally');
      return;
    }
    const added = updated.instances.find(
      (i) => i.instance_id !== updated.root_instance_id && !before.has(i.instance_id),
    );
    acceptAssumptions(updated);
    onModel(updated);
    if (added) {
      load(added.instance_id, updated);
      setSelectionAfterSave(added.instance_id);
    }
    setNewName('');
    setInputs('');
    setOutputs('');
    setStatus('Component added');
    setComponentSaved((n) => n + 1);
  }
  const endpoints = components.flatMap((i) =>
    (
      model.definitions.find((d) => d.definition_version_id === i.definition_version_id)?.ports ??
      []
    ).map((p) => ({
      key: `${i.instance_id}/${p.port_id}`,
      instance_id: i.instance_id,
      port: p,
      label: `${i.name} · ${p.name} (${unitLabel(p.units)})`,
    })),
  );
  const endpointName = (ref: { instance_id: string; port_id: string }) => {
    const e = endpoints.find(
      (e) => e.instance_id === ref.instance_id && e.port.port_id === ref.port_id,
    );
    return e
      ? `${components.find((i) => i.instance_id === e.instance_id)?.name} · ${e.port.name}`
      : 'Unavailable port';
  };
  useEffect(() => {
    const request = hosts.quantityEdit;
    if (
      !request ||
      request.request === handledQuantityRequest.current ||
      selected !== request.instance_id ||
      loaded !== selected
    )
      return;
    const exists = ports.some((port) => port.port_id === request.port_id);
    handledQuantityRequest.current = request.request;
    quantityInvoker.current = request.invoker;
    setQuantityPort(request.port_id);
    setQuantityNotice(
      exists
        ? ''
        : 'This quantity has a pending removal in your component edits. ' +
            'Keep editing, save the removal, or discard component changes to restore it.',
    );
    quantityDialog.current?.showModal();
    requestAnimationFrame(() =>
      quantityDialog.current
        ?.querySelector<HTMLTextAreaElement>(
          `[data-port-definition="${CSS.escape(request.port_id)}"]`,
        )
        ?.focus(),
    );
  }, [hosts.quantityEdit, loaded, selected, ports]);
  const blocked = busy || !!api.pending || !!proposal;
  const choose = (id: string) => onSelect({ kind: 'instance', instance_id: id });
  const componentLabel = instance
    ? instance.name +
      (components.filter((i) => i.name === instance.name).length > 1
        ? ' · instance ' +
          (components
            .filter((i) => i.name === instance.name)
            .findIndex((i) => i.instance_id === selected) +
            1)
        : '')
    : '';
  // Details panel of the canonical model view: nothing selected → the model and its
  // assumptions; a component → What it computes (with the editable source), Why, Assumptions.
  // No ports table and no incoming/outgoing lists: quantities are listed in the table below.
  function editDocumentation(owner: string) {
    const isModel = owner === 'model';
    const item = documentation.content?.component_details.find(
      (value) => value.instance_id === owner,
    );
    const title = isModel ? 'Edit model' : 'Edit component';
    return (
      <ActionDialog
        title={title}
        label={title}
        closeLabel="Cancel"
        disabled={blocked || documentation.loading || !!documentation.error}
        completionKey={documentationSaved}
        onOpen={() => {
          const form = {
            owner,
            description: isModel
              ? (documentation.content?.represents ?? '')
              : (item?.description ??
                model.annotations.find((a) => a.element_ref === owner)?.text ??
                ''),
            limits: isModel ? (documentation.content?.limits ?? '') : (item?.limits ?? ''),
          };
          documentationBase.current = JSON.stringify(form);
          documentationSnapshot.current = {
            content: structuredClone(currentDocumentation(documentation.content)),
            revision: documentation.revision,
          };
          beforeDocumentationEdit.current = assumptions;
          setDocumentationForm(form);
          if (isModel) setRenamed(model.name);
        }}
        onDismiss={() => {
          if (blocked) return false;
          setDocumentationForm(null);
          documentation.retry();
          setAssumptions(beforeDocumentationEdit.current);
          setAssumptionEditing(false);
          setAssumptionEpoch((n) => n + 1);
          if (isModel) setRenamed('');
          else setName(original.current.name);
        }}
      >
        {documentationForm?.owner === owner && (
          <fieldset className="hf-form-stack" disabled={blocked}>
            <FormField label={isModel ? 'Model name' : 'Component name'}>
              <TextInput
                maxLength={4096}
                value={isModel ? renamed : name}
                onChange={(e) => (isModel ? setRenamed(e.target.value) : setName(e.target.value))}
              />
            </FormField>
            <ReadingSection tone="sunken" aria-label="Description">
              <FormField label="Description" optional>
                <TextArea
                  aria-label={isModel ? 'Model description' : 'Component description'}
                  maxLength={isModel ? 16384 : 4096}
                  value={documentationForm.description}
                  onChange={(e) =>
                    setDocumentationForm({ ...documentationForm, description: e.target.value })
                  }
                />
              </FormField>
            </ReadingSection>
            <ReadingSection tone="sunken" aria-label="Assumptions">
              {assumptionView(
                isModel ? { kind: 'model' } : { kind: 'instance', instance_id: owner },
                isModel ? 'Model' : 'Component · ' + instance?.name,
              )}
            </ReadingSection>
            <ReadingSection tone="sunken" aria-label="Limits">
              <FormField label="Limits" optional>
                <TextArea
                  aria-label={isModel ? 'Model limits' : 'Component limits'}
                  maxLength={isModel ? 16384 : 4096}
                  value={documentationForm.limits}
                  onChange={(e) =>
                    setDocumentationForm({ ...documentationForm, limits: e.target.value })
                  }
                />
              </FormField>
            </ReadingSection>
            {error != null && (
              <p role="alert">
                {status && <>{status} </>}
                {message(error)}
              </p>
            )}
            <DialogActions
              primary={
                <Button
                  disabled={blocked || assumptionEditing || !!api.pending}
                  onClick={() => void save(isModel)}
                >
                  Save draft
                </Button>
              }
            />
          </fieldset>
        )}
      </ActionDialog>
    );
  }
  const details = (
    <section aria-label="Model authoring" className="model-authoring">
      <UnitGuidance guidance={guidance} />
      {!selected ? (
        <section className="inspector-model" aria-label="Model details">
          <h3>Model</h3>
          <div hidden={documentationForm?.owner === 'model'}>
            {documentation.content?.represents && (
              <ReadingSection tone="sunken" aria-label="Description">
                <h4>Description</h4>
                <p className="context-copy">{documentation.content.represents}</p>
              </ReadingSection>
            )}
            <ReadingSection tone="sunken" aria-label="Assumptions">
              {assumptionView({ kind: 'model' }, 'Model', false)}
            </ReadingSection>
            {documentation.content?.limits && (
              <ReadingSection tone="sunken" aria-label="Limits">
                <h4>Limits</h4>
                <p className="context-copy">{documentation.content.limits}</p>
              </ReadingSection>
            )}
          </div>
        </section>
      ) : (
        <div className="inspector">
          {!instance || !definition || loaded !== selected ? (
            <p>Select a component to inspect its code and quantities.</p>
          ) : (
            <fieldset disabled={blocked}>
              <div hidden={hosts.pane !== 'Component'}>
                <SectionHeader
                  title={componentLabel}
                  actions={
                    <>
                      {editDocumentation(selected)}

                      {createPortal(
                        <DialogFrame
                          ref={quantityDialog}
                          className="action-dialog hf-quantity-dialog"
                          aria-label={quantityPort ? 'Edit quantity' : 'Manage quantities'}
                          onClose={() => {
                            const invoker = quantityInvoker.current;
                            if (invoker?.isConnected && invoker.checkVisibility()) invoker.focus();
                            else
                              componentActions.current
                                ?.querySelector<HTMLElement>('button')
                                ?.focus();
                          }}
                        >
                          <div className="dialog-heading">
                            <SectionHeader
                              level={2}
                              title={quantityPort ? 'Edit quantity' : 'Manage quantities'}
                              help="quantities"
                            />
                          </div>
                          <div className="dialog-body">
                            {quantityNotice && <p role="status">{quantityNotice}</p>}
                            {error != null && <p role="alert">{message(error)}</p>}
                            {!quantityPort && (
                              <>
                                {components.filter(
                                  (i) =>
                                    i.definition_version_id === definition.definition_version_id,
                                ).length > 1 && (
                                  <fieldset className="form-stack">
                                    <legend>Also apply code and quantity changes to</legend>
                                    {components
                                      .filter(
                                        (i) =>
                                          i.definition_version_id ===
                                            definition.definition_version_id &&
                                          i.instance_id !== instance.instance_id,
                                      )
                                      .map((i) => (
                                        <label className="check" key={i.instance_id}>
                                          <TextInput
                                            type="checkbox"
                                            aria-label={'Also update ' + i.name}
                                            checked={targets.includes(i.instance_id)}
                                            onChange={() =>
                                              setTargets(toggle(targets, i.instance_id))
                                            }
                                          />
                                          {i.name}
                                        </label>
                                      ))}
                                  </fieldset>
                                )}
                              </>
                            )}
                            {ports.map(
                              (p, i) =>
                                (!quantityPort || p.port_id === quantityPort) && (
                                  <div className="hf-quantity-fields" key={p.port_id ?? i}>
                                    <p className="hf-quantity-kind">
                                      {p.direction === 'input'
                                        ? 'Input quantity'
                                        : 'Output quantity'}
                                    </p>
                                    <label>
                                      {quantityPort ? 'Name' : `Quantity ${i + 1} name`}
                                      <TextInput
                                        aria-label={`Quantity ${i + 1} name`}
                                        value={p.name}
                                        onChange={(e) =>
                                          setPorts(
                                            ports.map((x, n) =>
                                              n === i ? { ...x, name: e.target.value } : x,
                                            ),
                                          )
                                        }
                                      />
                                    </label>
                                    <label>
                                      {quantityPort ? 'Symbol' : `Quantity ${i + 1} symbol`}
                                      <TextInput
                                        aria-label={`Quantity ${i + 1} symbol`}
                                        value={p.code_symbol}
                                        onChange={(e) =>
                                          setPorts(
                                            ports.map((x, n) =>
                                              n === i ? { ...x, code_symbol: e.target.value } : x,
                                            ),
                                          )
                                        }
                                      />
                                    </label>
                                    {p.port_id ? (
                                      <label>
                                        {quantityPort
                                          ? 'Definition'
                                          : `Quantity ${i + 1} definition`}
                                        <TextArea
                                          aria-label={'Quantity ' + (i + 1) + ' definition'}
                                          data-port-definition={p.port_id}
                                          maxLength={4096}
                                          value={p.statement ?? ''}
                                          onChange={(e) =>
                                            setPorts(
                                              ports.map((x, n) =>
                                                n === i ? { ...x, statement: e.target.value } : x,
                                              ),
                                            )
                                          }
                                        />
                                      </label>
                                    ) : (
                                      <p>Save this quantity before adding its definition.</p>
                                    )}
                                    <UnitEditor
                                      label={`Quantity ${i + 1} units`}
                                      value={p.units}
                                      catalog={guidance.catalog}
                                      onChange={(units) =>
                                        setPorts(
                                          ports.map((x, n) => (n === i ? { ...x, units } : x)),
                                        )
                                      }
                                    />
                                    {!quantityPort && (
                                      <Button
                                        className="danger"
                                        onClick={() => setPorts(ports.filter((_, n) => n !== i))}
                                      >
                                        Remove quantity {i + 1}
                                      </Button>
                                    )}
                                  </div>
                                ),
                            )}
                            {!quantityPort && (
                              <>
                                <Button
                                  onClick={() =>
                                    setPorts([
                                      ...ports,
                                      {
                                        direction: 'input',
                                        name: '',
                                        code_symbol: '',
                                        units: { kind: 'unspecified' },
                                      },
                                    ])
                                  }
                                >
                                  Add input quantity
                                </Button>
                                <Button
                                  onClick={() =>
                                    setPorts([
                                      ...ports,
                                      {
                                        direction: 'output',
                                        name: '',
                                        code_symbol: '',
                                        units: { kind: 'unspecified' },
                                      },
                                    ])
                                  }
                                >
                                  Add output quantity
                                </Button>
                              </>
                            )}
                            {quantityNotice && (
                              <Button onClick={() => setQuantityPort('')}>Manage quantities</Button>
                            )}
                          </div>
                          <DialogActions
                            primary={
                              <Button
                                disabled={!dirty}
                                onClick={() => {
                                  quantityDialog.current?.close();
                                  void save();
                                }}
                              >
                                Preview quantity changes
                              </Button>
                            }
                          >
                            <Button onClick={() => quantityDialog.current?.close()}>Done</Button>
                          </DialogActions>
                        </DialogFrame>,
                        document.body,
                      )}
                    </>
                  }
                />
                <ReadingSection
                  tone="sunken"
                  aria-label="Description"
                  hidden={documentationForm?.owner === selected}
                >
                  <h4>Description</h4>
                  <p className="context-copy">
                    {documentation.content?.component_details.find(
                      (item) => item.instance_id === selected,
                    )?.description ??
                      (explanation || 'No description')}
                  </p>
                </ReadingSection>
              </div>
              {explain(
                selected,
                <div className="component-source">
                  <SourceEditor
                    key={selected}
                    value={text}
                    codeRef={code}
                    error={!!error}
                    onChange={(value) => {
                      setText(value);
                      setImported(null);
                    }}
                  />
                  <div>
                    <FilePicker
                      label="Load Python source file"
                      accept=".py,text/x-python"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void importFile(file);
                      }}
                    />
                  </div>
                </div>,
              )}
              <div hidden={hosts.pane !== 'Component' || documentationForm?.owner === selected}>
                <ReadingSection tone="sunken" aria-label="Assumptions">
                  {assumptionView(
                    { kind: 'instance', instance_id: selected },
                    'Component · ' + instance.name,
                    false,
                  )}
                </ReadingSection>
                {documentation.content?.component_details.find(
                  (item) => item.instance_id === selected,
                )?.limits && (
                  <ReadingSection tone="sunken" aria-label="Limits">
                    <h4>Limits</h4>
                    <p className="context-copy">
                      {
                        documentation.content.component_details.find(
                          (item) => item.instance_id === selected,
                        )?.limits
                      }
                    </p>
                  </ReadingSection>
                )}
              </div>
              <Button
                hidden={!dirty && !assumptionDirty}
                id="save-component"
                variant="primary"
                disabled={!dirty && !assumptionDirty}
                onClick={() => void save()}
              >
                Save component
              </Button>
              {dirty && <span>Unsaved changes</span>}
            </fieldset>
          )}
        </div>
      )}
    </section>
  );
  return (
    <>
      {proposal && <ChangePreview api={api} proposal={proposal} />}
      {documentation.error && (
        <div role="alert">
          {documentation.error}
          <Button onClick={documentation.retry}>Retry documentation</Button>
        </div>
      )}
      {hosts.details && createPortal(details, hosts.details)}
      {modelActionHost && createPortal(editDocumentation('model'), modelActionHost)}
      {hosts.toolbar &&
        createPortal(
          <>
            <div role="status" aria-live="polite">
              {status}
            </div>
            {error != null && (
              <div role="alert" id="model-errors">
                <p>{message(error)}</p>
                {error instanceof ApiError &&
                  error.detail.fields.map((f, i) => (
                    <p key={i}>
                      {f.path}: {f.message}
                    </p>
                  ))}
                {error instanceof ApiError && error.detail.code === 'stale_revision' && (
                  <Button
                    onClick={() =>
                      act(async () => {
                        setReview(await api.model(model.study_id, model.model_id));
                        setStatus('Current revision loaded for review');
                      })
                    }
                  >
                    Review current revision
                  </Button>
                )}
              </div>
            )}
            {review && (
              <section aria-label="Current revision review">
                <h3>Current revision</h3>
                <p>{review.draft_revision}</p>
                <pre>{review.source_files.map((s) => sourceText(s)).join('\n')}</pre>
                <Button
                  onClick={() =>
                    navigate(() => {
                      acceptAssumptions(review);
                      onModel(review);
                      load(selected, review);
                    })
                  }
                >
                  Load reviewed revision
                </Button>
                <p>Your unsaved editor text remains above until you explicitly discard it.</p>
              </section>
            )}
            <div className="model-authoring-actions">
              <ActionDialog
                title="Add component"
                label="＋ Component"
                completionKey={componentSaved}
              >
                <fieldset disabled={blocked || dirty || assumptionDirty || assumptionEditing}>
                  <label>
                    New component name
                    <TextInput
                      value={newName}
                      maxLength={4096}
                      onChange={(e) => setNewName(e.target.value)}
                    />
                  </label>
                  <label>
                    Input symbols
                    <TextInput
                      value={inputs}
                      onChange={(e) => setInputs(e.target.value)}
                      aria-describedby="port-help"
                    />
                  </label>
                  <label>
                    Output symbols
                    <TextInput
                      value={outputs}
                      onChange={(e) => setOutputs(e.target.value)}
                      aria-describedby="port-help"
                    />
                  </label>
                  <p id="port-help">
                    Comma-separated Python symbols. All quantities are real scalars; new quantities
                    start Not specified. Use Edit quantity to choose units before creating a
                    configuration.
                  </p>
                  <UnitGuidance guidance={guidance} />
                  <DialogActions
                    primary={
                      <Button
                        variant="primary"
                        disabled={
                          blocked ||
                          dirty ||
                          assumptionDirty ||
                          assumptionEditing ||
                          !guidance.catalog
                        }
                        onClick={() => act(addComponent)}
                      >
                        Add component
                      </Button>
                    }
                  />
                </fieldset>
              </ActionDialog>
              <ActionDialog
                title="Connections"
                label="Connect quantities"
                completionKey={connectionSaved}
              >
                <fieldset disabled={blocked || dirty || assumptionDirty || assumptionEditing}>
                  <label>
                    Connection output
                    <Select
                      aria-label="Connection output"
                      value={from}
                      onChange={(e) => setFrom(e.target.value)}
                    >
                      <option value="">Choose output</option>
                      {endpoints
                        .filter((e) => e.port.direction === 'output')
                        .map((e) => (
                          <option key={e.key} value={e.key}>
                            {e.label}
                          </option>
                        ))}
                    </Select>
                  </label>
                  <label>
                    Connection input
                    <Select
                      aria-label="Connection input"
                      value={to}
                      onChange={(e) => setTo(e.target.value)}
                    >
                      <option value="">Choose input</option>
                      {endpoints
                        .filter((e) => e.port.direction === 'input')
                        .map((e) => (
                          <option key={e.key} value={e.key}>
                            {e.label}
                          </option>
                        ))}
                    </Select>
                  </label>
                  <DialogActions
                    primary={
                      <Button
                        variant="primary"
                        disabled={
                          blocked || dirty || assumptionDirty || assumptionEditing || !from || !to
                        }
                        onClick={() =>
                          act(async () => {
                            if (
                              await commitBatch(
                                [connectionEdit({ from, to }, 0)],
                                'Keep editing',
                                'Connect quantities',
                              )
                            ) {
                              setFrom('');
                              setTo('');
                              setConnectionSaved((n) => n + 1);
                            }
                          })
                        }
                      >
                        Review connection
                      </Button>
                    }
                  />
                  {!!model.connections.length && <h3>Existing connections</h3>}
                  <Button
                    disabled={!links.length}
                    onClick={() =>
                      act(async () => {
                        await commitBatch(
                          links.map((id) => ({ kind: 'disconnect', connection_id: id })),
                          'Keep connections',
                          'Disconnect connections',
                        );
                      })
                    }
                  >
                    Disconnect selected connections
                  </Button>
                  <ul>
                    {model.connections.map((c) => (
                      <li key={c.connection_id}>
                        <label className="check">
                          <TextInput
                            type="checkbox"
                            aria-label={`Select connection ${c.connection_id}`}
                            checked={links.includes(c.connection_id)}
                            onChange={() => setLinks(toggle(links, c.connection_id))}
                          />
                          {endpointName(c.source_ref)} → {endpointName(c.target_ref)}
                        </label>
                        <Button
                          className="danger"
                          aria-label={
                            `Disconnect ${endpointName(c.source_ref)} to ` +
                            endpointName(c.target_ref)
                          }
                          onClick={() =>
                            act(async () => {
                              await commitBatch(
                                [{ kind: 'disconnect', connection_id: c.connection_id }],
                                'Keep connections',
                                'Disconnect connections',
                              );
                            })
                          }
                        >
                          Disconnect
                        </Button>
                        <Button
                          aria-label={`Reconnect ${c.connection_id}`}
                          disabled={!from || !to}
                          onClick={() =>
                            act(async () => {
                              if (
                                await commitBatch([
                                  { kind: 'disconnect', connection_id: c.connection_id },
                                  connectionEdit({ from, to }, 0),
                                ])
                              ) {
                                setFrom('');
                                setTo('');
                              }
                            })
                          }
                        >
                          Reconnect to chosen quantities
                        </Button>
                      </li>
                    ))}
                  </ul>
                </fieldset>
              </ActionDialog>
              <span ref={componentActions}>
                <ActionDialog
                  title="Component actions"
                  label="•••"
                  triggerLabel="Component actions"
                >
                  {instance && definition && loaded === selected && (
                    <Button
                      onClick={() => {
                        quantityInvoker.current = document.activeElement as HTMLElement;
                        quantityInvoker.current.closest('dialog')?.close();
                        setQuantityPort('');
                        setQuantityNotice('');
                        quantityDialog.current?.showModal();
                      }}
                    >
                      Manage quantities
                    </Button>
                  )}
                  {instance && definition && loaded === selected && (
                    <Button
                      disabled={blocked || dirty || assumptionDirty || assumptionEditing}
                      onClick={() =>
                        act(async () => {
                          const before = new Set(model.instances.map((i) => i.instance_id));
                          const updated = await propose([
                            {
                              kind: 'instantiate',
                              temp_key: 'local_instance',
                              version_ref: {
                                definition_version_id: definition.definition_version_id,
                              },
                            },
                          ]);
                          if (updated) {
                            const added = updated.instances.find((i) => !before.has(i.instance_id));
                            acceptAssumptions(updated);
                            onModel(updated);
                            if (added) {
                              load(added.instance_id, updated);
                              onSelect({ kind: 'instance', instance_id: added.instance_id });
                            }
                          }
                        })
                      }
                    >
                      Add another instance
                    </Button>
                  )}
                  <ActionDialog title="Manage components" label="Component actions">
                    {' '}
                    {!components.length && <p>Add a component to start.</p>}
                    {!!components.length && (
                      <div className="component-list">
                        {components.map((i) => (
                          <div key={i.instance_id}>
                            <label className="check">
                              <TextInput
                                type="checkbox"
                                aria-label={`Select component ${i.instance_id}`}
                                disabled={blocked || dirty || assumptionDirty || assumptionEditing}
                                checked={checked.includes(i.instance_id)}
                                onChange={() => setChecked(toggle(checked, i.instance_id))}
                              />
                              {i.name}
                            </label>
                            <Button
                              disabled={blocked}
                              aria-pressed={selected === i.instance_id}
                              onClick={() => choose(i.instance_id)}
                            >
                              Select {i.name}
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                    <Button
                      disabled={
                        blocked || dirty || assumptionDirty || assumptionEditing || !checked.length
                      }
                      onClick={() =>
                        act(async () => {
                          const incident = model.connections.filter(
                            (c) =>
                              checked.includes(c.source_ref.instance_id) ||
                              checked.includes(c.target_ref.instance_id),
                          );
                          await commitBatch(
                            [
                              ...incident.map((c) => ({
                                kind: 'disconnect' as const,
                                connection_id: c.connection_id,
                              })),
                              ...checked.map((id) => ({
                                kind: 'remove_instance' as const,
                                instance_id: id,
                              })),
                            ],
                            'Keep components',
                            'Remove components',
                          );
                        })
                      }
                    >
                      Remove selected components
                    </Button>
                  </ActionDialog>
                </ActionDialog>
              </span>{' '}
            </div>
          </>,
          hosts.toolbar,
        )}
    </>
  );
}
