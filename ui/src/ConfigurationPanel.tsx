import { OpenLink } from './design';
import { DialogActions } from './design';
import type {
  ConfigurationRequest4,
  ConfigurationPreview4,
  ConfigurationPreview6,
  ConfigurationPreview7,
} from './contract';
import { Assumptions } from './Assumptions';
import { ModelAssumptionsLink } from './ConfigurationRecord';
import { ConfigurationChanges, ModelAssumptionChanges, evidenceUseChange } from './ChangePreview';
import { EvidenceReferences, evidenceAccessLost } from './EvidenceView';
import {
  Button,
  Panel,
  DataTable,
  Field,
  TextInput,
  TextArea,
  Select,
  DialogFrame,
  StatusTag,
  RecordState,
  PageHeader,
  formatNumber,
} from './design';
import { ActionDialog, SectionHeader } from './Presentation';
import { RecordedConfiguration } from './RecordedConfiguration';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, HyprnMvpApi, accessLostText, accessUnverifiedText, message } from './api';
import { useAccessLoss } from './accessLoss';
import type { ConfigurationCandidate, ConfigurationRevisionRead6, FrozenConfigurationRead7, ModelDraftRead5, ModelRevisionRead5, PortRef, Study } from './api';
import type { EvidenceRecord, EvidenceResourceRef1 } from './api';
import { configurationContext, evidenceSnapshotView, configurableModel, criteriaFreeSeed, modelAssumptions, recordLimitations, recordedModelAssumptions } from './recordViews';
import { EvidencePicker } from './EvidencePicker';
import type { EditorGuard } from './workspaceModel';
import { ResultPicker, type ResultSource } from './ResultPicker';
import type { ConfigurationRequest6, ConfigurationPreview8, ConfigurationAssumption, ResultBinding, PublicReceipt, ModifiedRunSeedRead6, RuntimeComparison } from './api';

import { UnitEditor, UnitGuidance, useUnitCatalog } from './UnitEditor';
import { type UnitDraft, resolvedUnit, unitDraft, unitDeclaration, unitLabel, unresolvedModelUnits } from './unitLabels';

export const refKey = (ref: PortRef) => `${ref.instance_id}/${ref.port_id}`;
import { modelPorts } from './modelPorts';
export { modelPorts } from './modelPorts';
type DraftBinding = Omit<ResultBinding, 'conversion'> & { conversion: ResultBinding['conversion'] | null };
type InputDraft = { result_binding?: DraftBinding | null; target: PortRef; value: string; units: string; unitChoice?: UnitDraft; statement: string; kind: 'manual' | 'source'; evidence_version_ids: string[] };
type Draft = { assumptions: ConfigurationAssumption[]; name: string; inputs: InputDraft[]; description: string; boundary: string; /** Stored notes, never shown or edited; sent back unchanged. */ originalNotes: string[]; contextEvidence: string[]; evidence: ConfigurationCandidate['evidence_snapshots'] };
export type ConfigurationHandle = EditorGuard & { copy: (config: ConfigurationRevisionRead6, snapshot: ModelRevisionRead5) => void };
export type ConfigurationInspection = { snapshot: ModelRevisionRead5 | null; inputs: Draft['inputs']; saved: FrozenConfigurationRead7 | null; dirty: boolean; evidence: Draft['evidence'] };
const empty: Draft = { assumptions: [], name: '', inputs: [], description: '', boundary: '', originalNotes: [], contextEvidence: [], evidence: [] };
const numerical: ConfigurationCandidate['numerical'] = { mode: 'deterministic', initialization: [], solvers: [], derivatives: { method: 'none', form: null, check: null }, design_variables: [], objectives: [], constraints: [], optimizer: null, uncertainty: null };
function fromConfig(c: ConfigurationRevisionRead6): Draft {
  // Unsupported formats are refused by copy(); modified seeds exist only for supported formats.
  const context = configurationContext(c), supported = context.kind === 'supported' ? context : null;
  return { description: c.context_snapshot.description, boundary: c.context_snapshot.boundary, assumptions: supported?.assumptions.kind === 'recorded' ? supported.assumptions.items : [], name: c.name, inputs: c.inputs.map(i => ({ target: i.target, value: String(i.value), units: i.units, statement: i.provenance.statement, kind: i.provenance.kind, evidence_version_ids: i.provenance.evidence_version_ids, result_binding: 'result_binding' in i ? i.result_binding : null })), contextEvidence: supported?.generalContext.kind === 'explicit' ? supported.generalContext.evidenceVersionIds : [], originalNotes: c.context_snapshot.notes, evidence: c.evidence_snapshots };
}
export function ConfigurationPanel({ modified, onCancelModified, resourceActionsRef, initialRevision = null, api, model, study, authoringDirty, activeRun, onSubmit, onHandle, onInspection, onEvidenceRecords, onViewSourceResult, onViewModelUnit }: { onViewModelUnit?: (model: ModelRevisionRead5, target: PortRef) => void; modified?: {seed: ModifiedRunSeedRead6; source: ConfigurationRevisionRead6}; onCancelModified?: () => void; onViewSourceResult?: (runId: string, output: PortRef) => void; resourceActionsRef?: (element: HTMLDivElement | null) => void; initialRevision?: ModelRevisionRead5 | null; api: HyprnMvpApi; model: ModelDraftRead5 | ModelRevisionRead5; study: Study; authoringDirty: boolean; activeRun: boolean; onSubmit: (configurationId: string) => Promise<void>; onHandle: (h: ConfigurationHandle) => void; onInspection?: (value: ConfigurationInspection) => void; evidence?: EvidenceRecord[]; onEvidenceRecords: (records: EvidenceRecord[]) => void }) {
  const [seed, setSeed] = useState(modified?.seed);
  const [review, setReview] = useState<
    ConfigurationPreview8 | null
  >(null);
  const restoreReviewFocus = useRef(false);
  const reviewDialog = useRef<HTMLDialogElement>(null), reviewResolve = useRef<((accepted: boolean) => void) | null>(null), reviewInvoker = useRef<HTMLElement | null>(null);
  useEffect(() => { if (review) reviewDialog.current?.showModal(); }, [review]);
  function closeReview(accepted: boolean) { reviewDialog.current?.close(); setReview(null); const resolve = reviewResolve.current; reviewResolve.current = null; resolve?.(accepted); restoreReviewFocus.current = true; }
  useEffect(() => () => { reviewResolve.current?.(false); }, []);
  const [resultTarget, setResultTarget] = useState<string | null>(null);
  const [sourcePreview, setSourcePreview] = useState<
    ConfigurationPreview8 | null
  >(null), [sourceError, setSourceError] = useState('');
  const previewGeneration = useRef(0);
  const original = useRef<{ id: string; draft: Draft } | null>(null);
  const [attachment, setAttachment] = useState<{ label: string; input?: string; scope: EvidenceResourceRef1 | null } | null>(null);
  const [snapshot, setSnapshot] = useState<ModelRevisionRead5 | null>(initialRevision);
  const initialDraft = (): Draft => modified ? {...fromConfig(modified.source), name: modified.source.name + ' — modified'} : initialRevision ? { ...empty, description: study.description, boundary: study.boundary, inputs: modelPorts(initialRevision).filter(p => p.direction === 'input' && !initialRevision.connections.some(c => refKey(c.target_ref) === refKey(p.target))).map(p => ({ target: p.target, value: '', units: resolvedUnit(p.units) ?? '', unitChoice: {kind:'unspecified'}, statement: '', kind: 'manual', evidence_version_ids: [] })) } : { ...empty, description: study.description, boundary: study.boundary };
  const [draft, setDraft] = useState<Draft>(initialDraft); const [baseline, setBaseline] = useState<Draft>(initialDraft);
  const [assumptionDirty, setAssumptionDirty] = useState(false);
  const [ownerGeneration, setOwnerGeneration] = useState(0);
  const [modelEvidence, setModelEvidence] = useState<Draft['evidence']>(modified?.source.evidence_snapshots ?? []);
  const [modelEvidenceError, setModelEvidenceError] = useState('');
  const [modelEvidenceLoading, setModelEvidenceLoading] = useState(false);
  const [retainedEvidence, setRetainedEvidence] = useState<Draft['evidence'] | null>(modified?.source.evidence_snapshots ?? null);
  const [saved, setSaved] = useState<FrozenConfigurationRead7 | null>(null);
  const [copies, setCopies] = useState<FrozenConfigurationRead7[]>([]);
  const [busy, setBusy] = useState(false); const locked = useRef(false);
  useEffect(() => { if (!busy && !review && restoreReviewFocus.current) { restoreReviewFocus.current = false; reviewInvoker.current?.focus(); } }, [busy, review]);
  const [error, setError] = useState<unknown>(null); const [notice, setNotice] = useState('');
  const [bindingEvidence, setBindingEvidence] = useState<Draft['evidence']>([]);
  const [bindingEvidenceError, setBindingEvidenceError] = useState('');
  const [binding, setBinding] = useState<ModelRevisionRead5 | null>(null), [paste, setPaste] = useState(''), [proposal, setProposal] = useState<InputDraft[] | null>(null);
  const [pasteScope, setPasteScope] = useState<string | null>(null), [savingPaste, setSavingPaste] = useState(false);
  const pasteResolution = useRef<((value: Draft | null) => void) | null>(null);
  const guidance = useUnitCatalog(api, study.study_id, model.model_id + '/' + (snapshot?.model_revision_id ?? 'draft'));
  const unresolved = unresolvedModelUnits(snapshot ?? model);
  const configurationScope = `${study.study_id}/${model.model_id}/${snapshot?.model_revision_id ?? ''}`;
  const bindingDialog = useRef<HTMLDialogElement>(null), pasteDialog = useRef<HTMLDialogElement>(null), invoking = useRef<HTMLElement | null>(null);
  const selectedEvidence = useMemo(() => { const ids = new Set([...draft.contextEvidence, ...draft.assumptions.flatMap(a => a.evidence_links.map(l => l.evidence_version_id)), ...recordedModelAssumptions(modelAssumptions(snapshot)).flatMap(a => a.evidence_links.map(l => l.evidence_version_id)), ...draft.inputs.flatMap(i => i.evidence_version_ids)]); return [...draft.evidence, ...modelEvidence.filter(e => !draft.evidence.some(v => v.evidence_version_id === e.evidence_version_id))].filter(e => ids.has(e.evidence_version_id)); }, [draft, snapshot, modelEvidence]);
  const dirty = assumptionDirty || JSON.stringify(draft) !== JSON.stringify(baseline) || !!paste || !!proposal || !!attachment || !!resultTarget;
  const inspectionCallback = useRef(onInspection); inspectionCallback.current = onInspection;
  useEffect(() => { inspectionCallback.current?.({ snapshot, inputs: draft.inputs, saved, dirty, evidence: selectedEvidence }); }, [snapshot, draft.inputs, saved, dirty, selectedEvidence]);
  useEffect(() => {
    const controller = new AbortController(), actor = api.actor;
    setModelEvidenceError('');
    if (retainedEvidence) { setModelEvidence(retainedEvidence); setModelEvidenceLoading(false); return; }
    setModelEvidence([]);
    if (!snapshot || !recordedModelAssumptions(modelAssumptions(snapshot)).some(a => a.evidence_links.length)) { setModelEvidenceLoading(false); return; }
    setModelEvidenceLoading(true);
    void api.assumptionEvidence(study.study_id, model.model_id, { model_revision_id: snapshot.model_revision_id }, controller.signal).then(value => {
      if (controller.signal.aborted || actor !== api.actor) return;
      setModelEvidence(value.evidence.map(evidenceSnapshotView));
      if (value.links.some(link => link.status === 'unavailable')) setModelEvidenceError('This evidence reference could not be resolved. Remove or replace this attachment before saving the configuration.');
    }).catch(e => { if (!controller.signal.aborted && actor === api.actor) { setModelEvidence([]); setModelEvidenceError(message(e)); } }).finally(() => { if (!controller.signal.aborted) setModelEvidenceLoading(false); });
    return () => controller.abort();
  }, [api, study.study_id, model.model_id, snapshot, retainedEvidence]);
  useEffect(() => {
    const controller = new AbortController(), actor = api.actor;
    setBindingEvidence([]); setBindingEvidenceError('');
    if (!binding || !recordedModelAssumptions(modelAssumptions(binding)).some(a => a.evidence_links.length)) return;
    void api.assumptionEvidence(study.study_id, model.model_id, { model_revision_id: binding.model_revision_id }, controller.signal).then(value => {
      if (controller.signal.aborted || actor !== api.actor) return;
      setBindingEvidence(value.evidence.map(evidenceSnapshotView));
      if (value.links.some(link => link.status === "unavailable")) setBindingEvidenceError("This evidence reference could not be resolved. Remove or replace this attachment before saving the configuration.");
    }).catch(e => { if (!controller.signal.aborted && actor === api.actor) setBindingEvidenceError(message(e)); });
    return () => controller.abort();
  }, [api, study.study_id, model.model_id, binding]);
  const ports = modelPorts(snapshot ?? model), inputs = ports.filter(p => p.direction === 'input' && !(snapshot ?? model).connections.some(c => refKey(c.target_ref) === refKey(p.target))), outputs = ports.filter(p => p.direction === 'output');
  const stale = !modified && !initialRevision && !!snapshot && 'draft_revision' in model && snapshot.originating_draft_revision !== model.draft_revision;
  const panel = useRef<HTMLElement>(null);
  function clearEvidence() { setDraft(value => ({ ...value, evidence: [] })); setModelEvidence([]); setBindingEvidence([]); }
  // A confirmed denial reported by any host clears protected evidence from the open
  // draft; the picker clears its own display through the same signal. The draft, its
  // exact approach pin and every other local edit are kept, and nothing is submitted.
  // A saved record on display clears itself (RecordedConfiguration); its draft copy
  // is left untouched so no phantom unsaved edit appears.
  useAccessLoss(api, study.study_id, change => { if (change.kind !== 'access-lost') return; if (!saved || dirty) clearEvidence(); setError(new Error(accessLostText)); });
  async function perform(action: () => Promise<void>): Promise<boolean> {
    if (locked.current) return false; locked.current = true; setBusy(true); setError(null);
    const read = api.fence({ studyId: study.study_id });
    try { await action(); return true; } catch (e) {
      const outcome = await api.readFailed(e, read, { command: true });
      if (outcome === 'transient') setError(new Error(accessUnverifiedText));
      else if (outcome === 'error') { if (evidenceAccessLost(e)) clearEvidence(); setError(e); }
      return false;
    }
    finally { read.done(); locked.current = false; setBusy(false); }
  }
  useEffect(() => { let alive = true; api.configurations(study.study_id).then(v => { if (alive) setCopies(v.filter(v => v.configuration.model_id === model.model_id)); }).catch(e => { if (alive) setError(e); }); return () => { alive = false; }; }, [api, study.study_id, model.model_id]);
  function copy(config: ConfigurationRevisionRead6, retained: ModelRevisionRead5) {
    if (config.model_id !== model.model_id) { setError(new Error('This configuration belongs to another model. Select that model before copying.')); return; }
    const context = configurationContext(config);
    if (context.kind === 'unsupported') { setError(new Error(recordLimitations.configurationUnsupported + ' It cannot be copied here.')); return; }
    if (context.generalContext.kind === 'legacy_unowned' && context.generalContext.evidenceVersionIds.length) { setError(new Error('This older configuration has evidence without explicit attachment ownership. It remains available for inspection and modified runs; create a new configuration to select general context explicitly.')); return; }
    if (config.numerical.mode !== 'deterministic') { setError(new Error('This configuration uses an unsupported numerical mode. It cannot be edited here.')); return; }
    setOwnerGeneration(n => n + 1); setAssumptionDirty(false); setAttachment(null); setResultTarget(null);
    setRetainedEvidence(config.evidence_snapshots); setSnapshot(retained); setDraft(fromConfig(config)); setBaseline(fromConfig(config)); setSaved(null); setError(null);
    setNotice('Configuration copied to an unsaved draft. No run submitted.');
  }
  async function commit(): Promise<boolean> {
    reviewInvoker.current = document.activeElement as HTMLElement;
    if (assumptionDirty || attachment || resultTarget) { setError(new Error('Finish or cancel the source/evidence picker before saving the configuration.')); return false; }
    if (modelEvidenceLoading || modelEvidenceError) { setError(new Error(modelEvidenceError || 'Wait for model evidence to finish loading.')); return false; }
    if (!snapshot || stale || authoringDirty) { setError(new Error('Save model and study changes, then commit the current model version before committing this configuration.')); return false; }
    let candidateDraft = draft;
    if (paste) {
      try {
        const rows = parsePaste();
        const reviewed = await new Promise<Draft | null>(resolve => { pasteResolution.current = resolve; setSavingPaste(true); showPaste(rows); });
        if (!reviewed) return false;
        candidateDraft = reviewed;
      } catch (e) { if (evidenceAccessLost(e)) clearEvidence(); setError(e); return false; }
    }
    let committed = false;
    const successful = await perform(async () => {
      const candidate = request(candidateDraft);
      const proof = await previewCandidate(candidate);
      setSourcePreview(proof);
      if (!proof.compatibility.compatible) throw new Error(proof.compatibility.diagnostics.map(d => `${d.path}: ${d.message}`).join('\n'));
      if (modified) {
        const accepted = await new Promise<boolean>(resolve => { reviewResolve.current = resolve; setReview(proof); });
        if (!accepted) return;
      }
      const body = { command_id: crypto.randomUUID(), expected_revision: null, configuration_id: null, configuration: candidate, expected_preview_digest: proof.candidate_digest };
      try { const result = await api.commitConfiguration6(body); finishSaved(result, candidateDraft); committed = true; }
      catch (e) { if (api.pending?.body.command_id === body.command_id) original.current = { id: body.command_id, draft: candidateDraft }; throw e; }
    });
    return successful && committed;
  }
  function changedField(path: string) {
    const parts = path.split('/').slice(1);
    if (parts[0] === 'inputs') {
      const input = review?.resolved_candidate.inputs[Number(parts[1])] ?? modified?.source.inputs[Number(parts[1])];
      const label = input && ports.find(p => refKey(p.target) === refKey(input.target))?.label;
      return `${label ?? 'Input'} · ${parts.slice(2).join(' · ').replaceAll('_', ' ')}`;
    }
    return parts.join(' · ').replaceAll('_', ' ');
  }
  function changedValue(path: string, side: 'before' | 'after', fallback: string): string {
    // Only format paths reported by the server; never compute the change set.
    let value: unknown = side === 'before' ? modified?.source : review?.resolved_candidate;
    for (const part of path.split('/').slice(1)) value = value && typeof value === 'object' ? (value as Record<string,unknown>)[part.replaceAll('~1','/').replaceAll('~0','~')] : undefined;
    if (path.endsWith('/result_binding')) {
      if (!value) return 'Entered value';
      const binding = value as ResultBinding;
      return `${binding.labels.run_name} · ${binding.labels.instance_name} · ${binding.labels.output_name} · ${formatNumber(binding.original_value)} ${binding.original_units || 'dimensionless'}`;
    }
    if (typeof value === 'number') return formatNumber(value);
    if (value === null) return 'None';
    if (typeof value === 'object' && value !== null && 'content' in value) return String(value.content);
    if (typeof value === 'string') return /digest|sha256/.test(path) ? value.slice(0,12) + '…' : value;
    return fallback;
  }
  /** The new configuration: version 6 only, with no criteria (study criteria are evaluated in
   * calculations) and no approach selection. */
  function request(value: Draft): ConfigurationRequest6 {
    if (!snapshot) throw new Error('Choose a model version.');
    // A seed from an earlier run explains its own refusal before its retained model format does.
    if (seed && !criteriaFreeSeed(seed)) throw new Error('This run was configured before criteria moved to the study brief. Create a new configuration from its inputs instead.');
    if (!configurableModel(snapshot)) throw new Error('This model version uses an earlier format. Save a new version of the model to configure it.');
    if (unresolved.length) throw new Error(unresolved.map(issue => `${issue.component} · ${issue.quantity}: units are not specified. Resolve this active model quantity before configuration.`).join('\n'));
    function units(item: {units: string; unitChoice?: UnitDraft}) {
      const declaration = unitDeclaration(item.unitChoice ?? unitDraft(item.units), guidance.catalog);
      const resolved = resolvedUnit(declaration);
      if (resolved === undefined) throw new Error('Choose Dimensionless or physical units for every entered input.');
      return resolved;
    }
    if (!value.name.trim()) throw new Error('Enter a configuration name.');
    function number(text: string, name: string) { if (!text.trim() || !Number.isFinite(Number(text))) throw new Error(`${name}: Enter an explicit finite value.`); return Number(text); }
    const missing = inputs.find(p => !value.inputs.some(i => refKey(i.target) === refKey(p.target) && (i.result_binding || i.value.trim())));
    if (missing) throw new Error(`${missing.label}: Enter an explicit value.`);
    return { schema_version: '6', study_id: study.study_id, model_id: model.model_id, model_revision_id: snapshot.model_revision_id, name: value.name,
      inputs: value.inputs.map(i => {
        if (!i.statement.trim()) throw new Error('Describe the provenance of every input.');
        const common = { target: i.target, provenance: { kind: i.kind, statement: i.statement, evidence_version_ids: i.evidence_version_ids } };
        return i.result_binding ? { ...common, kind: 'run_result' as const, source_run_id: i.result_binding.source_run_id, source_output: i.result_binding.source_output, expected_results_digest: i.result_binding.results_digest }
          : { ...common, kind: 'literal' as const, value: number(i.value, 'Input'), units: units(i) };
      }), numerical: seed?.configuration.numerical ?? numerical, context_source: seed ? {kind:'source_run', source_run_id:seed.source_run_id, source_configuration_digest:seed.source_configuration_digest, observed_study_revision:seed.current_study_revision, choice_confirmed:true} : { kind: 'current_study', expected_study_revision: study.revision },
      notes: value.originalNotes,
      derivation: seed?.configuration.derivation ?? null,
      context_override: { schema_version: '1', description: value.description, boundary: value.boundary },
      assumptions: value.assumptions,
      general_context_evidence_version_ids: value.contextEvidence };
  }
  function previewCandidate(candidate: ConfigurationRequest6) {
    return api.previewConfiguration6(candidate);
  }
  useEffect(() => {
    const token = ++previewGeneration.current, actor = api.actor;
    setSourcePreview(null); setSourceError('');
    if (!draft.inputs.some(i => i.result_binding) || !snapshot || stale || authoringDirty) return;
    let candidate: ConfigurationRequest6;
    try { candidate = request(draft); } catch (e) { setSourceError(`Complete the configuration to check source units: ${message(e)}`); return; }
    const timer = window.setTimeout(() => {
      void previewCandidate(candidate).then(proof => {
        if (token !== previewGeneration.current || actor !== api.actor) return;
        setSourcePreview(proof);
        if (!proof.compatibility.compatible) setSourceError(proof.compatibility.diagnostics.map(d => d.message).join('\n'));
      }).catch(e => { if (token === previewGeneration.current && actor === api.actor) setSourceError(message(e)); });
    }, 250);
    return () => { window.clearTimeout(timer); previewGeneration.current++; };
  }, [api, draft, snapshot, study.revision, stale, authoringDirty, seed, guidance.catalog]);
  function finishSaved(result: FrozenConfigurationRead7, value: Draft) {
    original.current = null; setSaved(result); setDraft(value); setBaseline(value); setPaste(''); setPasteScope(null);
    setCopies(old => [...old.filter(c => c.configuration.configuration_revision_id !== result.configuration.configuration_revision_id), result]);
    setNotice('Configuration saved. Run is a separate action.');
  }
  async function recover(retry = false) {
    const command = original.current; if (!command) return;
    if (retry) await api.retryOriginal();
    const receipt = api.pending?.body.command_id === command.id ? await api.reconcile() : (await api.request<PublicReceipt>(`/studies/${study.study_id}/commands/${command.id}?category=configuration`)).data;
    if (receipt?.state === 'committed' && receipt.result && 'configuration' in receipt.result) { finishSaved(receipt.result as FrozenConfigurationRead7, command.draft); return; }
    if (receipt?.state === 'rejected') { original.current = null; throw new Error('The original configuration was rejected. Your edits are preserved.'); }
    throw new Error('The original configuration command is not resolved. Its request is kept unchanged.');
  }
  function chooseResult(source: ResultSource) {
    setDraft(d => ({ ...d, inputs: d.inputs.map(i => refKey(i.target) === resultTarget ? { ...i, value: String(source.value), units: source.units, unitChoice: unitDraft(source.units),
      statement: i.statement || `Output ${source.labels.instance_name} · ${source.labels.output_name} from ${source.labels.run_name}.`,
      result_binding: { source_run_id: source.source_run_id, source_output: source.source_output, results_digest: source.results_digest,
        source_configuration_digest: source.source_configuration_digest, original_value: source.value, original_units: source.units, labels: source.labels, conversion: null } } : i) }));
    setResultTarget(null); setNotice('Run result selected. Save the configuration to keep this source.');
  }
  function closePaste(value: Draft | null = null) {
    const resolve = pasteResolution.current; pasteResolution.current = null;
    setProposal(null); setSavingPaste(false); pasteDialog.current?.close(); invoking.current?.focus(); resolve?.(value);
  }
  function discard() {
    setOwnerGeneration(n => n + 1); setAssumptionDirty(false);
    closePaste(); setResultTarget(null); setAttachment(null); setDraft(baseline); setPaste(''); setPasteScope(null); setBinding(null); bindingDialog.current?.close(); setError(null); setNotice('Configuration draft changes discarded.');
  }
  useEffect(() => { onHandle({ dirty, save: async () => !dirty || commit(), discard, copy }); });
  useEffect(() => () => { pasteResolution.current?.(null); pasteResolution.current = null; }, []);
  function editInput(index: number, change: Partial<InputDraft>) { setDraft({ ...draft, inputs: draft.inputs.map((i, n) => n === index ? { ...i, ...change } : i) }); setNotice(''); }
  function evidenceControl(label: string, ids: string[], input?: string) {
    function remove(id: string) { setDraft(d => ({ ...d, contextEvidence: input === undefined ? d.contextEvidence.filter(e => e !== id) : d.contextEvidence, inputs: d.inputs.map(v => refKey(v.target) === input ? { ...v, evidence_version_ids: v.evidence_version_ids.filter(e => e !== id) } : v) })); }
    return <section className="evidence-attachment" aria-label={label}><h4 className="sr-only">{label}</h4><EvidenceReferences records={draft.evidence} ids={ids} label={label} onRemove={remove} /><Button onClick={() => {
      const target = input ? draft.inputs.find(i => refKey(i.target) === input)?.target : undefined;
      const common = { scope_version: '1' as const, study_id: study.study_id };
      setAttachment({ label, input, scope: input ? target && snapshot ? { ...common, kind: 'port', model_id: model.model_id, model_revision_id: snapshot.model_revision_id, ...target } : null : { ...common, kind: 'study' } });
    }}>Add evidence</Button></section>;
  }
  function attachEvidence(record: EvidenceRecord) {
    if (!attachment) return;
    let snapshot: Draft['evidence'][number];
    try { snapshot = evidenceSnapshotView(record); } catch (e) { setError(e); return; }
    const id = record.evidence_version_id, add = (ids: string[]) => [...new Set([...ids, id])];
    setDraft(d => ({ ...d, contextEvidence: !attachment.input ? add(d.contextEvidence) : d.contextEvidence,
      inputs: d.inputs.map(i => refKey(i.target) === attachment.input ? { ...i, evidence_version_ids: add(i.evidence_version_ids) } : i),
      evidence: [...d.evidence.filter(e => e.evidence_version_id !== id), snapshot] }));
    setAttachment(null); setNotice('Evidence attached to this draft. Save the configuration to keep the attachment.');
  }
  function applyBinding(revision: ModelRevisionRead5) {
    setRetainedEvidence(null); setSnapshot(revision); setSaved(null);
    const free = modelPorts(revision).filter(p => p.direction === 'input' && !revision.connections.some(c => refKey(c.target_ref) === refKey(p.target)));
    const next = { ...draft, inputs: free.map(p => draft.inputs.find(i => refKey(i.target) === refKey(p.target)) ?? { target: p.target, value: '', units: resolvedUnit(p.units) ?? '', unitChoice: {kind:'unspecified' as const}, statement: '', kind: 'manual' as const, evidence_version_ids: [] }) };
    const removed = draft.inputs.filter(i => !free.some(p => refKey(p.target) === refKey(i.target))); next.inputs.push(...removed);
    setDraft(next); if (!snapshot && !dirty) setBaseline(next); setBinding(null); bindingDialog.current?.close(); invoking.current?.focus(); setNotice('Model version saved. Enter or review every input.');
  }
  function parsePaste(): InputDraft[] {
      if (pasteScope !== configurationScope) throw new Error('Input paste belongs to a different model binding. Its original text is preserved; discard it before entering assignments for the new binding.');
      if (new TextEncoder().encode(paste).length > 65536) throw new Error('Input paste exceeds 64 KiB.');
      const lines = paste.trimEnd().split(/\r?\n/); if (lines.shift() !== 'instance_id\tport_id\tvalue\tunits\tprovenance') throw new Error('Use the tab-separated header exactly as shown.');
      if (!lines.length || lines.length > 256) throw new Error('Paste requires 1–256 rows.');
      const seen = new Set<string>(); const rows = lines.map((line, n) => { const cells = line.split('\t'); const [instance_id, port_id, value, units, statement] = cells; const key = `${instance_id}/${port_id}`; if (draft.inputs.find(i => refKey(i.target) === key)?.result_binding) throw new Error('Choose Enter a value instead before pasting over a run result.'); if (cells.length !== 5 || seen.has(key) || !inputs.some(p => refKey(p.target) === key) || !value.trim() || !Number.isFinite(Number(value)) || !statement.trim()) throw new Error(`Row ${n + 1}: invalid, duplicate or non-free input assignment.`); seen.add(key); if (!units) throw new Error(`Row ${n + 1}: choose Dimensionless explicitly or provide a supported physical unit spelling.`); const choice: UnitDraft = units === 'Dimensionless' ? {kind:'dimensionless'} : {kind:'physical',expression:units}; unitDeclaration(choice, guidance.catalog); return { ...(draft.inputs.find(i => refKey(i.target) === key)!), value, units: resolvedUnit(choice)!, unitChoice: choice, statement }; });
      return rows;
  }
  function showPaste(rows: InputDraft[]) { setProposal(rows); setError(null); invoking.current = document.activeElement as HTMLElement; pasteDialog.current?.showModal(); pasteDialog.current?.querySelector<HTMLButtonElement>('button')?.focus(); }
  function previewPaste() {
    try { showPaste(parsePaste()); } catch (e) { setError(e); }
  }
  if (saved && !dirty) return <>{error != null && <p role="alert">{message(error)}</p>}{modified && <RuntimeComparisonView comparison={sourcePreview?.runtime_comparison ?? seed!.runtime_comparison} />}<RecordedConfiguration onViewSourceResult={onViewSourceResult} resourceActionsRef={resourceActionsRef} saved={saved} api={api} activeRun={activeRun} onSubmit={onSubmit} onCopy={() => copy(saved.configuration, saved.model_snapshot)} /></>;
  return (
    <section ref={panel} id="configuration" aria-label="Configuration" className="configuration-panel">
      {seed && (
        <section aria-label="Modified run origin">
          <SectionHeader
            title="Create modified run"
            actions={
              <Button disabled={busy || !!api.pending} onClick={onCancelModified}>
                Cancel modified run
              </Button>
            }
          />
          <p>
            Based on run {modified!.source.name}. A new
            configuration and run will keep this source unchanged.
          </p>
          <p>Inputs and evidence come from the source run.</p>
        </section>
      )}
      <PageHeader
        className="configuration-header"
        id="configuration-title"
        title="Configuration"
        titleEditor={
          <TextInput
            className="configuration-name"
            aria-label="Configuration name"
            placeholder="New configuration"
            value={draft.name}
            maxLength={4096}
            disabled={busy || !!api.pending}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
        }
        details={
          <>
            <RecordState state={dirty ? 'changed' : saved ? 'draft' : 'new'} />
            <span className="hf-muted">
              {'name' in model ? model.name : 'Source run model'}
              {!snapshot && ' · Choose a model version'}
            </span>
          </>
        }
        actions={<div className="section-actions" ref={resourceActionsRef} />}
      />
      <Panel>
      {(!snapshot || stale) && (
        <Button
          disabled={busy || authoringDirty || !!api.pending}
          onClick={() =>
            void perform(async () => {
              if (!('draft_revision' in model))
                throw new Error("A modified run keeps its source run's model version.");
              const revision = await api.commitModel(model);
              if (!snapshot) applyBinding(revision);
              else {
                setBinding(revision);
                invoking.current = document.activeElement as HTMLElement;
                bindingDialog.current?.showModal();
                bindingDialog.current?.querySelector<HTMLButtonElement>('button')?.focus();
              }
            })
          }
        >
          Save model version
        </Button>
      )}
      {authoringDirty && <p>Save model and study changes before committing or running.</p>}
      {stale && <p>The model draft changed. Save its current version and review compatibility.</p>}
      {error != null && (
        <div role="alert">
          <p>
            {seed && error instanceof ApiError && error.detail.code === 'stale_revision'
              ? 'Study context changed. Your edits are preserved; ' +
                'refresh the study revision before saving.'
              : message(error)}
          </p>
          {error instanceof ApiError &&
            error.detail.fields.map((d, i) => (
              <p key={i}>
                {d.path}: {d.message}
              </p>
            ))}
        </div>
      )}
      {sourceError && !error && <p role="status">{sourceError}</p>}
      {original.current && (
        <aside className="evidence-recovery">
          <StatusTag tone="warning">Outcome uncertain</StatusTag>
          <p>The configuration request is kept unchanged.</p>
          <Button disabled={busy} onClick={() => void perform(() => recover())}>
            Check original configuration command
          </Button>
          {api.retryReady && (
            <Button disabled={busy} onClick={() => void perform(() => recover(true))}>
              Retry original configuration command
            </Button>
          )}
        </aside>
      )}
      {notice && <p aria-live="polite">{notice}</p>}
      {!modified && copies.length > 0 && (
        <details>
          <summary>Saved configurations</summary>
          <p>Copies are unsaved drafts; no run is submitted.</p>
          {copies
            .slice()
            .reverse()
            .map((c) => (
              <Button
                key={c.configuration.configuration_revision_id}
                disabled={dirty || authoringDirty || busy}
                onClick={() => copy(c.configuration, c.model_snapshot)}
              >
                Copy {c.configuration.name} · {c.configuration.configuration_revision_id}
              </Button>
            ))}
          {dirty && <p>Save or discard the current configuration draft before copying.</p>}
        </details>
      )}
      {seed &&
        error instanceof ApiError &&
        ['stale_revision', 'context_choice_required', 'reference_conflict'].includes(
          error.detail.code,
        ) && (
          <Button
            disabled={busy || !!api.pending}
            onClick={() =>
              void perform(async () => {
                const next = await api.modifiedRunSeedRead(study.study_id, seed.source_run_id);
                if (
                  next.source_run_id !== seed.source_run_id ||
                  next.source_configuration_digest !== seed.source_configuration_digest
                )
                  throw new Error('The source record could not be verified.');
                setSeed(next);
                setNotice(
                  'Study revision refreshed. Your context edits are unchanged; ' +
                    'review and save when ready.',
                );
              })
            }
          >
            Refresh study revision
          </Button>
        )}
      {snapshot && (
        <>
            <SectionHeader
              title="Inputs and provenance"
              help="inputs"
              actions={
                <ActionDialog title="Input tools and model binding" label="Input tools" help="inputs"
                  disabled={busy || !!api.pending || !!original.current}>
                  <section className="form-stack">
                    <h3>Configuration details</h3>{' '}
                    <label>
                      Description
                      <TextArea
                        aria-label="Description"
                        maxLength={4096}
                        value={draft.description}
                        onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                      />
                    </label>
                    <section aria-label="Context evidence">
                      <h3>Context evidence</h3>
                      {evidenceControl('General context evidence', draft.contextEvidence)}
                      <p>Removing an attachment does not delete the source record.</p>
                    </section>
                  </section>
                  <details>
                    <summary>Units help</summary>
                    <p>
                      Unit choices use the same public catalog as model editing. The server checks
                      compatibility and reports conversion provenance. Values are not converted
                      here.
                    </p>
                  </details>
                  {!inputs.length && <p>No inputs required.</p>}
                  <details aria-label="Connected inputs">
                    <summary>Connected inputs · read-only</summary>
                    {ports
                      .filter(
                        (p) =>
                          p.direction === 'input' &&
                          (snapshot ?? model).connections.some(
                            (c) => refKey(c.target_ref) === refKey(p.target),
                          ),
                      )
                      .map((p) => {
                        const source = (snapshot ?? model).connections.find(
                          (c) => refKey(c.target_ref) === refKey(p.target),
                        )!.source_ref;
                        return (
                          <p key={refKey(p.target)}>
                            {p.label} ←{' '}
                            {ports.find((p) => refKey(p.target) === refKey(source))?.label ??
                              refKey(source)}{' '}
                            · {unitLabel(p.units)}; supplied by producer
                          </p>
                        );
                      })}
                  </details>
                  <section className="configuration-section">
                    <h3>Paste input assignments</h3>
                    <p>
                      Tab-separated columns: instance_id, port_id, value, units, provenance. Use
                      Dimensionless explicitly for a dimensionless entry. Maximum256 rows/64KiB.
                      This changes only the local proposal.
                    </p>
                    <pre>
                      instance_id{'\t'}port_id{'\t'}value{'\t'}units{'\t'}provenance
                    </pre>
                    <TextArea
                      aria-label="Input assignment rows"
                      value={paste}
                      onChange={(e) => {
                        if (!paste) setPasteScope(configurationScope);
                        if (!e.target.value) setPasteScope(null);
                        setPaste(e.target.value);
                        setProposal(null);
                      }}
                    />
                    <DialogActions
                      primary={
                        <Button onClick={previewPaste}>Preview input assignments</Button>
                      }
                    />
                    {error != null && <p role="alert">{message(error)}</p>}
                  </section>
                  {snapshot && <p>Model version: {snapshot.model_revision_id}</p>}
                </ActionDialog>
              }
            />
          <fieldset disabled={busy || !!api.pending || !!original.current}>
            <UnitGuidance guidance={guidance} />
            {unresolved.length > 0 && (
              <section aria-label="Unresolved model units">
                <StatusTag tone="advisory">Units incomplete</StatusTag>
                <p>
                  Resolve the listed active model quantities before saving this configuration.
                  Executor readiness is separate.
                </p>
                <ul>
                  {unresolved.map((issue) => (
                    <li key={issue.instance_id + '/' + issue.port_id}>
                      {issue.component} · {issue.quantity}: Not specified · definition version{' '}
                      {issue.definition_version_id}
                      {snapshot && onViewModelUnit && (
                        <OpenLink
                          onClick={() =>
                            onViewModelUnit(snapshot, {
                              instance_id: issue.instance_id,
                              port_id: issue.port_id,
                            })
                          }
                        >
                          View quantity
                        </OpenLink>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <DataTable regionLabel="Configuration inputs" className="configuration-inputs">
              <thead>
                <tr>
                  <th>Free input</th>
                  <th className="hf-th--num">Value</th>
                  <th>Units</th>
                  <th>Provenance</th>
                </tr>
              </thead>
              <tbody>
                {draft.inputs.map((i, index) => {
                  const port = inputs.find((p) => refKey(p.target) === refKey(i.target));
                  const label = port?.label ?? `Incompatible input ${refKey(i.target)}`;
                  const conversion = sourcePreview?.resolved_candidate.inputs.find(
                    (v) => refKey(v.target) === refKey(i.target),
                  )?.result_binding?.conversion;
                  const inputIssue =
                    error == null
                      ? undefined
                      : message(error)
                          .split('\n')
                          .find(
                            (line) =>
                              line.startsWith(`inputs.${index}.`) ||
                              line.startsWith(`inputs[${index}].`),
                          );
                  return (
                    <tr key={refKey(i.target)}>
                      <td>
                        <p>{label}</p>
                        {!port && (
                          <Button
                            onClick={() =>
                              setDraft({
                                ...draft,
                                inputs: draft.inputs.filter((_, n) => n !== index),
                              })
                            }
                          >
                            Remove incompatible input
                          </Button>
                        )}
                        {i.result_binding ? (
                          <p>
                            <StatusTag>Run result</StatusTag>
                          </p>
                        ) : (
                          <>
                            <p>Enter a value</p>
                            <Button onClick={() => setResultTarget(refKey(i.target))}>
                              Use a run result
                            </Button>
                          </>
                        )}
                      </td>
                      <td>
                        {i.result_binding ? (
                          <TextInput
                            className="configuration-value"
                            aria-label={`${label} value`}
                            data-input-key={refKey(i.target)}
                            value={i.value}
                            readOnly
                          />
                        ) : (
                          <Field
                            compact
                            label={`${label} value`}
                            className="configuration-value"
                            unit=""
                            inputProps={{
                              'aria-label': `${label} value`,
                              'data-input-key': refKey(i.target),
                              type: 'number',
                              step: 'any',
                            }}
                            value={i.value}
                            state={
                              !port || inputIssue
                                ? 'invalid'
                                : i.value.trim()
                                  ? 'assigned'
                                  : 'unassigned'
                            }
                            message={
                              inputIssue ??
                              (!port ? 'Input is incompatible with this model version.' : undefined)
                            }
                            onChange={(e) => editInput(index, { value: e.target.value })}
                          />
                        )}
                      </td>
                      <td>
                        {i.result_binding ? (
                          <p aria-label={`${label} units`}>{unitLabel(i.units)}</p>
                        ) : (
                          <UnitEditor
                            label={`${label} units`}
                            resolvedOnly
                            value={i.unitChoice ?? unitDraft(i.units)}
                            catalog={guidance.catalog}
                            onChange={(unitChoice) =>
                              editInput(index, {
                                unitChoice,
                                units: resolvedUnit(unitChoice) ?? '',
                              })
                            }
                          />
                        )}
                        {port && <p>Model units: {unitLabel(port.units)}</p>}
                      </td>
                      <td>
                        <div className="provenance-field">
                          <TextInput
                            aria-label={`${label} provenance`}
                            value={i.statement}
                            maxLength={4096}
                            placeholder="Where does this value come from?"
                            onChange={(e) => editInput(index, { statement: e.target.value })}
                          />
                          {i.result_binding && (
                            <section aria-label={`${label} source`}>
                              <p>
                                Read-only source: {i.result_binding.labels.run_name}
                              </p>
                              <p>
                                {i.result_binding.labels.instance_name} ·{' '}
                                {i.result_binding.labels.output_name}
                              </p>
                              <p>
                                Original source: {i.result_binding.original_value}{' '}
                                {unitLabel(i.result_binding.original_units)}
                              </p>
                              {conversion && (
                                <p>
                                  In model units: × {conversion.factor} →{' '}
                                  {conversion.destination_value}{' '}
                                  {unitLabel(conversion.destination_units)}
                                </p>
                              )}
                              {!conversion && (
                                <p>Source conversion has not been checked for this draft.</p>
                              )}
                              <div className="actions">
                                <OpenLink
                                  disabled={!onViewSourceResult}
                                  onClick={() =>
                                    onViewSourceResult?.(
                                      i.result_binding!.source_run_id,
                                      i.result_binding!.source_output,
                                    )
                                  }
                                >
                                  View source result
                                </OpenLink>
                                <Button
                                  onClick={() =>
                                    editInput(index, {
                                      result_binding: null,
                                      unitChoice: unitDraft(i.units),
                                    })
                                  }
                                >
                                  Enter a value instead
                                </Button>
                              </div>
                            </section>
                          )}
                          {evidenceControl(
                            `${label} evidence`,
                            i.evidence_version_ids,
                            refKey(i.target),
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>
            <p className="input-explanation">
              Connected inputs are supplied by their producers. Blank values are missing; zero is an
              explicit value.
            </p>
            <section className="configuration-section" aria-label="Configuration assumption owners">
              <Assumptions
                key={ownerGeneration}
                ownerKey={ownerGeneration + configurationScope + '/configuration'}
                ownerLabel="Configuration"
                items={draft.assumptions}
                records={draft.evidence}
                editable={
                  {
                        api,
                        studyId: study.study_id,
                        scope: { scope_version: '1', kind: 'study', study_id: study.study_id },
                        disabled: busy || !!api.pending,
                        onDirty: setAssumptionDirty,
                        onChange: (assumptions) => {
                          setDraft((d) => ({ ...d, assumptions }));
                          setNotice(
                            'Unsaved local edits. Save the configuration to keep these changes.',
                          );
                        },
                        onRecords: (records) => {
                          let snapshots: Draft['evidence'];
                          try {
                            snapshots = records.map(evidenceSnapshotView);
                          } catch (e) {
                            setError(e);
                            return;
                          }
                          if (!records.length) {
                            setModelEvidence([]);
                            setBindingEvidence([]);
                          }
                          setDraft((d) => ({
                            ...d,
                            evidence: records.length
                              ? [
                                  ...d.evidence.filter(
                                    (e) =>
                                      !records.some(
                                        (r) => r.evidence_version_id === e.evidence_version_id,
                                      ),
                                  ),
                                  ...snapshots,
                                ]
                              : [],
                          }));
                          onEvidenceRecords(records);
                        },
                      }
                }
              />
              {modelEvidenceLoading && <p role="status">Loading model evidence…</p>}
              {modelEvidenceError && <p role="alert">{modelEvidenceError}</p>}
              <ModelAssumptionsLink api={api} studyId={study.study_id} model={snapshot} records={modelEvidence} />
            </section>
            <Button
              variant={saved && !dirty ? 'secondary' : 'primary'}
              disabled={
                unresolved.length > 0 ||
                !guidance.catalog ||
                stale ||
                authoringDirty ||
                modelEvidenceLoading ||
                !!modelEvidenceError ||
                assumptionDirty
              }
              onClick={() => void commit()}
            >
              Save configuration
            </Button>
            <Button disabled={!dirty} onClick={discard}>
              Discard configuration changes
            </Button>
          </fieldset>
        </>
      )}

      <div className="actions configuration-run">
        <Button disabled>Run this configuration</Button>
        <span className="context-line">Save the configuration before running.</span>
      </div>
      <DialogFrame
        ref={pasteDialog}
        aria-label="Input assignment preview"
        onCancel={(e) => {
          e.preventDefault();
          closePaste();
        }}
      >
        <SectionHeader level={2} title="Input assignment preview" help="inputs" />
        <p>
          {savingPaste
            ? 'Review assignments before saving this configuration. ' +
              'Apply and save validates and commits; Run remains separate.'
            : 'Before → proposed; no configuration has been committed.'}
        </p>
        {proposal?.map((i) => (
          <p key={refKey(i.target)}>
            {refKey(i.target)}:{' '}
            {draft.inputs.find((old) => refKey(old.target) === refKey(i.target))?.value ||
              'Missing'}{' '}
            → {i.value} {i.units || 'dimensionless'} · {i.statement}
          </p>
        ))}
        <DialogActions
          primary={
            <Button
              onClick={() => {
                const next = {
                  ...draft,
                  inputs: draft.inputs.map(
                    (i) => proposal?.find((p) => refKey(p.target) === refKey(i.target)) ?? i,
                  ),
                };
                if (!savingPaste) {
                  setDraft(next);
                  setPaste('');
                  setPasteScope(null);
                }
                closePaste(next);
              }}
            >
              {savingPaste ? 'Apply and save configuration' : 'Apply input assignments'}
            </Button>
          }
        >
          <Button onClick={() => closePaste()}>Keep editing</Button>
        </DialogActions>
      </DialogFrame>
      <DialogFrame
        ref={reviewDialog}
        aria-label="Review modified run"
        onCancel={(e) => {
          e.preventDefault();
          closeReview(false);
        }}
      >
        <SectionHeader level={2} title="Review modified run" help="inputs" />
        {review && (
          <>
            <p>
              These changes were checked by the server against the source run. Saving creates a
              separate configuration; Run is a separate action.
            </p>
            <ConfigurationChanges
              before={modified!.source}
              after={review.resolved_candidate}
              changes={review.changes}
              model={snapshot ?? undefined}
            />
            <DataTable regionLabel="Other changes from source">
              <thead>
                <tr>
                  <th>Changed field</th>
                  <th>Source</th>
                  <th>This attempt</th>
                </tr>
              </thead>
              <tbody>
                {review.changes
                  .filter(
                    (change) =>
                      !evidenceUseChange(change.path) &&
                      !change.path.startsWith('/assumptions') &&
                      !change.path.startsWith('/general_context_evidence_version_ids') &&
                      !change.path.startsWith('/evidence_snapshots'),
                  )
                  .map((change) => (
                    <tr key={change.path}>
                      <th>{changedField(change.path)}</th>
                      <td>{changedValue(change.path, 'before', change.before)}</td>
                      <td>{changedValue(change.path, 'after', change.after)}</td>
                    </tr>
                  ))}
              </tbody>
            </DataTable>
            {!review.changes.length && <p>No scientific configuration changes.</p>}
            <RuntimeComparisonView comparison={review.runtime_comparison} />
          </>
        )}
        <DialogActions
          primary={
            <Button variant="primary" onClick={() => closeReview(true)}>
              Save modified configuration
            </Button>
          }
        >
          <Button onClick={() => closeReview(false)}>Keep editing</Button>
        </DialogActions>
      </DialogFrame>
      <DialogFrame
        ref={bindingDialog}
        aria-label="Review model binding"
        onCancel={() => {
          setBinding(null);
          invoking.current?.focus();
        }}
      >
        <SectionHeader level={2} title="Review model binding" help="model" />
        <p>
          The new model version is saved; your current configuration binding is unchanged until you
          accept. New inputs remain missing, removed inputs require explicit removal, and
          units and evidence are validated by the server before commit.
        </p>
        {binding && (
          <>
            <p>Current model binding → Newly saved model</p>
            <ModelAssumptionChanges
              before={snapshot}
              after={binding}
              beforeEvidence={modelEvidence}
              afterEvidence={bindingEvidence}
            />
            {bindingEvidenceError && <p role="alert">{bindingEvidenceError}</p>}
            <h3>Inputs and source</h3>
            <p>
              {JSON.stringify(snapshot && modelPorts(snapshot)) ===
              JSON.stringify(modelPorts(binding))
                ? 'Input and quantity definitions are unchanged.'
                : 'Input or quantity definitions changed. ' +
                  'Review model binding details before accepting.'}
            </p>
            <p>
              {JSON.stringify(snapshot?.source_files.map((s) => s.sha256)) ===
              JSON.stringify(binding.source_files.map((s) => s.sha256))
                ? 'Source bytes are unchanged.'
                : 'Source files changed. Review the source identities in model binding details.'}
            </p>
            <details>
              <summary>Model binding details</summary>
              <h3>Input and quantity definitions</h3>
              <pre tabIndex={0}>
                {JSON.stringify(
                  { previous: snapshot && modelPorts(snapshot), proposed: modelPorts(binding) },
                  null,
                  2,
                )}
              </pre>
              <h3>Source, context and evidence</h3>
              <pre tabIndex={0}>
                {JSON.stringify(
                  {
                    previous_source: snapshot?.source_files.map((s) => s.sha256),
                    proposed_source: binding.source_files.map((s) => s.sha256),
                    configuration_context: {
                      description: draft.description,
                      boundary: draft.boundary,
                    },
                    retained_evidence: selectedEvidence,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </>
        )}
        <DialogActions
          primary={
            <Button variant="primary" onClick={() => binding && applyBinding(binding)}>
              Use reviewed model version
            </Button>
          }
        >
          <Button
            onClick={() => {
              setBinding(null);
              bindingDialog.current?.close();
              invoking.current?.focus();
            }}
          >
            Keep current binding
          </Button>
        </DialogActions>
      </DialogFrame>
      {resultTarget && (
        <ResultPicker
          api={api}
          studyId={study.study_id}
          label={inputs.find((p) => refKey(p.target) === resultTarget)?.label ?? resultTarget}
          onChoose={chooseResult}
          onClose={() => setResultTarget(null)}
        />
      )}
      {attachment && (
        <EvidencePicker
          api={api}
          studyId={study.study_id}
          label={attachment.label}
          scope={attachment.scope}
          onAttach={attachEvidence}
          onRecords={onEvidenceRecords}
          onClose={() => setAttachment(null)}
        />
      )}
      </Panel>
    </section>
  );
}

export function RuntimeComparisonView({comparison}: {comparison: RuntimeComparison | null | undefined}) {
  if (!comparison) return null;
  return <section aria-label="Runtime comparison"><h3>Runtime</h3><p>{comparison.basis === 'prepared_bundle' ? 'Prepared runtime · saved for this attempt' : 'Provisional runtime · checked again during preparation'}</p><p>{comparison.state === 'same' ? 'Matches the source runtime.' : comparison.state === 'different' ? 'Differs from the source runtime.' : 'Current runtime is unavailable.'}</p>{comparison.basis === 'executor_observation' && comparison.expires_at && <p>Observation expires {comparison.expires_at}.</p>}<details><summary>Runtime identity</summary><dl><dt>Source image</dt><dd>{comparison.source.image_digest}</dd><dt>Source architecture / Python</dt><dd>{comparison.source.architecture} / {comparison.source.python_version}</dd>{comparison.current && <><dt>This attempt image</dt><dd>{comparison.current.image_digest}</dd><dt>This attempt architecture / Python</dt><dd>{comparison.current.architecture} / {comparison.current.python_version}</dd></>}</dl></details></section>;
}
