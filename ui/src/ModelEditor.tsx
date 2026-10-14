import type { ApproachHandoff } from './ApproachAssumptions';
import { Assumptions } from './Assumptions';
import { evidenceAccessLost } from './EvidenceView';
import type { ModelAssumption, ConfigurationAssumption, EvidenceRecord } from './api';
import { Button, TextInput, TextArea, Select, FilePicker, Disclosure } from './design';
import { ActionDialog, SectionHeader } from './design';
import { modelSummary, type ComponentExplanation } from './SelectionInspector';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ApiError, HyprnMvpApi, message, sourceFromBytes, sourceFromText, sourceText } from './api';
import type { DefinitionChange4 as DefinitionChange, Edit4 as Edit, ModelDraftRead4, PortRead3 as Port, Source } from './api';
import { SourceEditor } from './SourceEditor';
import { ChangePreview, type ChangeProposal } from './ChangePreview';
import { parsePortMetadata, type PortPasteAction, type PortPasteScope } from './VariablesTable';
import { UnitEditor, UnitGuidance, useUnitCatalog } from './UnitEditor';
import { quantityDefinitions } from './quantityDefinitions';
import { unitDraft, unitLabel, unitDeclaration, type UnitDraft } from './unitLabels';
import type { EditorGuard, Selection } from './workspaceModel';

export type EditorHandle = EditorGuard & { pastePorts?: PortPasteAction };
type Props = { handoff?: ApproachHandoff; hosts: { toolbar: HTMLDivElement | null; details: HTMLDivElement | null }; explain: ComponentExplanation; modelActionHost?: HTMLDivElement | null; api: HyprnMvpApi; model: ModelDraftRead4; onModel: (model: ModelDraftRead4) => void;
  onHandle: (handle: EditorHandle) => void; navigate: (action: () => void) => void; selection: Selection; onSelect: (selection: Selection) => void };
type PortDraft = { port_id?: string; direction: 'input' | 'output' | 'residual'; name: string; code_symbol: string; units: UnitDraft; statement?: string };
const portDraft = (p: Port): PortDraft => ({ port_id: p.port_id, direction: p.direction, name: p.name, code_symbol: p.code_symbol, units: unitDraft(p.units) });

export function ModelEditor({ handoff, hosts, explain, modelActionHost, api, model, onModel, onHandle, navigate, selection, onSelect }: Props) {
  const guidance = useUnitCatalog(api, model.study_id, model.model_id);
  function parseMetadata(value: string, rows: Array<{port_id: string}>): DefinitionChange[] {
    return parsePortMetadata(value, rows).map(change => {
      if (change.kind !== 'update_port') throw new Error('Only port metadata can be pasted.');
      const {units, ...fields} = change.fields;
      return {...change, fields: {...fields, ...(units === undefined ? {} : {units: unitDeclaration(units === '' ? {kind:'unspecified'} : units === 'Dimensionless' ? {kind:'dimensionless'} : {kind:'physical',expression:units}, guidance.catalog)})}};
    });
  }
  const [handoffAttempted, setHandoffAttempted] = useState(false), [handoffOwner, setHandoffOwner] = useState('model');
  const selected = selection.kind === 'instance' || selection.kind === 'variable' ? selection.instance_id : '';
  // The local draft and its comparison/CAS base must advance together. A prop
  // refresh can arrive while the user is editing, including an open assumption.
  const [assumptionBase, setAssumptionBase] = useState(model);
  const baselineAssumptions = 'assumptions' in assumptionBase ? assumptionBase.assumptions : [];
  const [assumptions, setAssumptions] = useState<ModelAssumption[]>(baselineAssumptions);
  const [assumptionEditing, setAssumptionEditing] = useState(false), [assumptionEpoch, setAssumptionEpoch] = useState(0);
  const [assumptionRecords, setAssumptionRecords] = useState<EvidenceRecord[]>([]), [assumptionError, setAssumptionError] = useState(''), [assumptionLoading, setAssumptionLoading] = useState(true), [assumptionRevoked, setAssumptionRevoked] = useState(false);
  const assumptionDirty = JSON.stringify(assumptions) !== JSON.stringify(baselineAssumptions);
  const assumptionScope = model.study_id + '/' + model.model_id + '/' + model.draft_revision + '/' + api.actor;
  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setAssumptionRecords([]); setAssumptionLoading(true); setAssumptionError('');
    void api.assumptionEvidence(model.study_id, model.model_id, { draft_revision: model.draft_revision }, controller.signal).then(result => {
      if (!current || result.draft_revision !== model.draft_revision) return;
      setAssumptionRecords(result.evidence); setAssumptionRevoked(false);
    }).catch(e => { if (current) { setAssumptionError(message(e)); if (evidenceAccessLost(e)) { setAssumptionRecords([]); setAssumptionRevoked(true); } } }).finally(() => { if (current) setAssumptionLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [assumptionScope]);
  function assumptionEdits(): Edit[] {
    const edits: Edit[] = baselineAssumptions.filter(a => !assumptions.some(b => b.assumption_id === a.assumption_id)).map(a => ({ kind: 'remove_assumption', assumption_id: a.assumption_id }));
    for (const item of assumptions) {
      const prior = baselineAssumptions.find(a => a.assumption_id === item.assumption_id);
      if (!prior) edits.push({ kind: 'add_assumption', temp_key: 'assumption_' + item.assumption_id.replaceAll('-', ''), owner: item.owner, statement: item.statement, evidence_links: item.evidence_links });
      else if (JSON.stringify(item) !== JSON.stringify(prior)) edits.push({ kind: 'update_assumption', assumption_id: item.assumption_id, statement: item.statement, evidence_links: item.evidence_links });
    }
    return edits;
  }
  function acceptAssumptions(snapshot: ModelDraftRead4) { setAssumptionBase(snapshot); setAssumptions('assumptions' in snapshot ? snapshot.assumptions : []); setAssumptionEditing(false); setAssumptionEpoch(n => n + 1); }
  function assumptionView(owner: ModelAssumption['owner'], label: string) {
    const owns = (a: ModelAssumption) => a.owner.kind === owner.kind && (owner.kind === 'model' || a.owner.kind === 'instance' && a.owner.instance_id === owner.instance_id);
    return <>{assumptionLoading && <p role="status">Loading evidence…</p>}{assumptionError && <p role="alert">{assumptionError}</p>}
      <Assumptions headingLevel={4} ownerKey={model.study_id + '/' + model.model_id + '/' + assumptionBase.draft_revision + '/' + api.actor + '/' + JSON.stringify(owner) + '/' + assumptionEpoch} ownerLabel={label} items={assumptions.filter(owns)} records={assumptionRecords}
        editable={{ api, studyId: model.study_id, scope: { scope_version: '1', kind: 'study', study_id: model.study_id }, disabled: blocked || assumptionRevoked,
          onDirty: setAssumptionEditing, onRecords: records => setAssumptionRecords(old => records.length ? [...old.filter(r => !records.some(n => n.evidence_version_id === r.evidence_version_id)), ...records] : []),
          // Existing items keep their recorded owner object: re-creating it (different key order)
          // made unchanged assumptions compare as edited and sent a spurious update_assumption.
          onChange: (items: ConfigurationAssumption[]) => setAssumptions(old => [...old.filter(a => !owns(a)), ...items.map(a => ({ ...a, owner: old.find(o => o.assumption_id === a.assumption_id && owns(o))?.owner ?? owner }))]) }} />
      {assumptionDirty && <p role="status">Unsaved local edits. Save the model draft to keep these changes.</p>}</>;
  }
  const [loaded, setLoaded] = useState('');
  const [componentSaved, setComponentSaved] = useState(0), [connectionSaved, setConnectionSaved] = useState(0);
  // Component and definition notes (annotations) stay in the record; the UI neither shows nor edits them.
  const [name, setName] = useState('');
  const [text, setText] = useState(''); const [ports, setPorts] = useState<PortDraft[]>([]);
  const [imported, setImported] = useState<Source | null>(null);
  const [selectionAfterSave, setSelectionAfterSave] = useState('');
  const [newName, setNewName] = useState(''); const [inputs, setInputs] = useState(''); const [outputs, setOutputs] = useState('');
  const [from, setFrom] = useState(''); const [to, setTo] = useState('');
  const [proposal, setProposal] = useState<ChangeProposal | null>(null);
  const [targets, setTargets] = useState<string[]>([]), [checked, setChecked] = useState<string[]>([]), [links, setLinks] = useState<string[]>([]);
  const [queued, setQueued] = useState<Array<{ from: string; to: string }>>([]), [renamed, setRenamed] = useState(''), [paste, setPaste] = useState('');
  const [busy, setBusy] = useState(false); const [status, setStatus] = useState('');
  const [error, setError] = useState<unknown>(null); const [review, setReview] = useState<ModelDraftRead4 | null>(null);
  const invoker = useRef<HTMLElement | null>(null);
  const code = useRef<HTMLTextAreaElement>(null);
  const original = useRef({ name: '', text: '', ports: '', source: null as Source | null });
  const instance = model.instances.find(i => i.instance_id === selected);
  const definition = model.definitions.find(d => d.definition_version_id === instance?.definition_version_id);
  const importRequest = useRef(0), importPending = useRef(false);
  const importScope = `${model.study_id}/${model.model_id}/${model.draft_revision}/${selected}/${definition?.definition_version_id ?? ''}`;
  const currentImportScope = useRef(importScope); currentImportScope.current = importScope;
  function cancelImport() {
    importRequest.current++;
    if (importPending.current) { importPending.current = false; setBusy(false); setStatus('Source import discarded after its editing context changed.'); }
  }
  useEffect(() => { cancelImport(); }, [importScope]);
  useEffect(() => () => { importRequest.current++; importPending.current = false; }, []);
  async function importFile(file: File) {
    const request = ++importRequest.current, scope = importScope;
    const current = () => request === importRequest.current && scope === currentImportScope.current;
    importPending.current = true; setBusy(true); setError(null); setStatus('Reading source file…');
    try {
      if (file.size > 256 * 1024) throw new Error('Source must be at most 256 KiB.');
      const bytes = new Uint8Array(await file.arrayBuffer()); if (!current()) return;
      const source = await sourceFromBytes(bytes); if (!current()) return;
      setText(sourceText(source)); setImported(source); setStatus('Source file loaded locally; save to keep it');
    } catch (e) { if (current()) { setError(e); setStatus(''); } }
    finally { if (current()) { importPending.current = false; setBusy(false); } }
  }
  const components = model.instances.filter(i => i.instance_id !== model.root_instance_id);
  const dirty = !!instance && loaded === selected && (name !== original.current.name || text !== original.current.text || JSON.stringify(ports) !== original.current.ports || imported !== null || paste !== '');
  const authoringDirty = dirty || assumptionDirty || assumptionEditing || !!(newName || inputs || outputs || renamed || from || to || queued.length);
  useEffect(() => {
    if (model !== assumptionBase && !authoringDirty && !busy && !proposal && !api.pending) acceptAssumptions(model);
  }, [model, assumptionBase, authoringDirty, busy, proposal, api.pending]);
  useEffect(() => { if (loaded !== selected || !dirty) load(selected); }, [selected, model.draft_revision]);
  useEffect(() => {
    // Wait until the saving fieldset is enabled before restoring error focus.
    if (error && !busy && code.current) {
      const details = code.current.closest('details'); if (details) details.open = true;
      code.current.focus();
    }
  }, [error, busy]);
  function load(mid: string, snapshot = model) {
    cancelImport();
    setPaste('');
    const i = snapshot.instances.find(x => x.instance_id === mid);
    const d = snapshot.definitions.find(x => x.definition_version_id === i?.definition_version_id);
    const source = snapshot.source_files.find(s => d?.source_refs.includes(s.sha256));
    // Selection and source are resolved from one authoritative response, atomically.
    if (!i || !d || !source) { setLoaded(''); setName(''); setText(''); setPorts([]); setImported(null); return; }
    try {
      const decoded = sourceText(source); const quantities = quantityDefinitions(snapshot); const ps = d.ports.map(p => ({...portDraft(p), statement: quantities.find(q => q.instance.instance_id === mid && q.port.port_id === p.port_id)?.statement ?? ''}));
      original.current = { name: i.name, text: decoded, ports: JSON.stringify(ps), source };
      setName(i.name); setText(decoded); setPorts(ps); setImported(null);
      setLoaded(mid); setTargets([mid]); setPaste(''); setError(null); setReview(null);
    } catch (e) { setLoaded(''); setError(e); }
  }
  function propose(edits: Edit[], safe = 'Keep editing', apply = 'Apply changes'): Promise<ModelDraftRead4 | null> {
    if (!guidance.catalog) return Promise.reject(new Error('Unit guidance is unavailable. Retry unit guidance. Your edits are kept.'));
    if (api.pending) return Promise.reject(new Error('Check the original command before making more changes.'));
    const envelope = {command_id:crypto.randomUUID(),expected_revision:assumptionBase.draft_revision};
    const descriptive = assumptionBase.schema_version === '4' || edits.some(e => e.kind === 'revise_definition' && e.changes.some(c => c.kind === 'set_quantity_definition' || c.kind === 'clear_quantity_definition'));
    // The runtime predicate excludes new operations before selecting the legacy envelope.
    const command: import('./contract').ApplyRead4 = descriptive
      ? {...envelope,schema_version:'4',edits:structuredClone(edits)}
      : {...envelope,schema_version:'3',edits:structuredClone(edits) as import('./contract').Edit3[]};
    return new Promise(resolve => setProposal({ before: assumptionBase, invoker: invoker.current, command, safe, apply,
      finish: updated => { setProposal(null); resolve(updated); } }));
  }
  const toggle = (values: string[], id: string) => values.includes(id) ? values.filter(x => x !== id) : [...values, id];
  function connectionEdit(row: { from: string; to: string }, index: number): Edit {
    const [si, sp] = row.from.split('/'), [ti, tp] = row.to.split('/');
    return { kind: 'connect', temp_key: `connection${index}`, source_ref: { instance_id: si, port_id: sp }, target_ref: { instance_id: ti, port_id: tp } };
  }
  async function commitBatch(edits: Edit[], safe = 'Keep editing', apply = 'Apply changes') {
    const updated = await propose(edits, safe, apply);
    if (!updated) return false;
    acceptAssumptions(updated); onModel(updated); setChecked([]); setLinks([]); setStatus('Changes applied'); return true;
  }
  function pasteTarget(scope: PortPasteScope) {
    const target = model.instances.find(i => i.instance_id === scope.instance_id);
    const def = model.definitions.find(d => d.definition_version_id === target?.definition_version_id);
    if (!target || !def || target.instance_id === model.root_instance_id) throw new Error('Select one editable component for port metadata.');
    if (scope.study_id !== model.study_id || scope.model_id !== model.model_id || scope.draft_revision !== model.draft_revision || scope.definition_version_id !== def.definition_version_id) throw new Error('The port paste belongs to a different model draft or definition version. Your text and original scope are preserved; review or discard the paste before retargeting.');
    return { target, def };
  }
  async function pastePorts(scope: PortPasteScope, value: string, saveAuthoring = false) {
    if (saveAuthoring) return save(true, { scope, text: value });
    if (authoringDirty || busy || proposal || api.pending) throw new Error('Save or discard the component draft before starting a table proposal. Your text is preserved.');
    const { target, def } = pasteTarget(scope);
    invoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const changes = parseMetadata(value, def.ports);
    setBusy(true);
    try { return await commitBatch([{ kind: 'revise_definition', temp_key: 'metadata', definition_id: def.definition_id, expected_definition_version_id: def.definition_version_id, changes },
      { kind: 'replace_local_instance_version', instance_id: target.instance_id, expected_definition_version_id: def.definition_version_id, version_ref: { temp_key: 'metadata' } }]); }
    finally { setBusy(false); }
  }
  async function act(action: () => Promise<void>) {
    if (busy) return; invoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; setBusy(true); setError(null); setStatus('Working…');
    try { await action(); } catch (e) { setError(e); setStatus(''); }
    finally { setBusy(false); }
  }
  async function save(all = false, tablePaste?: { scope: PortPasteScope; text: string }): Promise<boolean> {
    if (!(all ? authoringDirty : dirty || assumptionDirty || assumptionEditing) && !tablePaste) return true;
    if (busy || (dirty && (!instance || !definition))) return false;
    invoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setBusy(true); setError(null); setStatus('Saving component…');
    try {
      if (assumptionEditing) throw new Error('Apply or discard the open assumption before saving the model draft.');
      const edits: Edit[] = assumptionEdits();
      let removing = false;
      if (tablePaste) {
        pasteTarget(tablePaste.scope);
        if (tablePaste.scope.instance_id !== selected || !instance || !definition) throw new Error('The port paste is bound to its original component. Your text is preserved.');
        if (paste || JSON.stringify(ports) !== original.current.ports || targets.some(id => id !== selected)) throw new Error('Review conflicting inspector port edits or multiple instance targets before saving the table paste. All edits are preserved.');
      }
      if ((dirty || tablePaste) && instance && definition) {
      const changes: DefinitionChange[] = [];
      const pastedText = tablePaste?.text ?? paste;
      const pasted = pastedText ? parseMetadata(pastedText, ports.filter((p): p is PortDraft & { port_id: string } => !!p.port_id)) : [];
      const editedPorts = ports.map(port => { const change = pasted.find(c => c.kind === 'update_port' && c.port_id === port.port_id); return change?.kind === 'update_port' ? { ...port, ...change.fields } : port; });
      if (new TextEncoder().encode(text).length > 256 * 1024) throw new Error('Python source: maximum size is 256 KiB. Your text is preserved.');
      if (text.includes('\0')) throw new Error(`Python source, line ${text.slice(0, text.indexOf('\0')).split('\n').length}: null characters are invalid. Your text is preserved.`);
      if (text !== original.current.text || imported) {
        changes.push({ kind: 'set_source', source: imported ?? await sourceFromText(text) });
      }
      const baseline = definition.ports;
      for (const p of baseline) if (!editedPorts.some(x => x.port_id === p.port_id)) changes.push({ kind: 'remove_port', port_id: p.port_id });
      editedPorts.forEach((p, index) => {
        const prior = baseline.find(x => x.port_id === p.port_id);
        if (!prior) changes.push({ kind: 'create_port', temp_key: `port${index}`, direction: p.direction, name: p.name, code_symbol: p.code_symbol, units: unitDeclaration(p.units, guidance.catalog), value_type: 'real_scalar' });
        else if (p.name !== prior.name || p.code_symbol !== prior.code_symbol || JSON.stringify(p.units) !== JSON.stringify(unitDraft(prior.units))) changes.push({ kind: 'update_port', port_id: prior.port_id, fields: { name: p.name, code_symbol: p.code_symbol, units: unitDeclaration(p.units, guidance.catalog) } });
      });
      for (const p of editedPorts) {
        if (!p.port_id) continue; // New ports acquire their exact IDs after the first atomic save.
        const prior = quantityDefinitions(model).find(q => q.instance.instance_id === selected && q.port.port_id === p.port_id)?.statement ?? '';
        const statement = p.statement ?? '';
        if (statement !== prior) {
          if (statement && (!statement.trim() || statement.length > 4096)) throw new Error('Quantity definition must be nonblank and at most 4096 characters. Your edits are kept.');
          changes.push(statement ? {kind:'set_quantity_definition',port_id:p.port_id,statement} : {kind:'clear_quantity_definition',port_id:p.port_id});
        }
      }
      if (changes.length) {
        if (!targets.length) throw new Error('Select at least one instance to receive this version.');
        const removed = new Set(changes.flatMap(c => c.kind === 'remove_port' ? [c.port_id] : []));
        for (const connection of model.connections) if ([connection.source_ref, connection.target_ref].some(ref => targets.includes(ref.instance_id) && removed.has(ref.port_id))) edits.push({ kind: 'disconnect', connection_id: connection.connection_id });
        edits.push({ kind: 'revise_definition', temp_key: 'revised', definition_id: definition.definition_id, expected_definition_version_id: definition.definition_version_id, changes });
        for (const id of targets) edits.push({ kind: 'replace_local_instance_version', instance_id: id, expected_definition_version_id: definition.definition_version_id, version_ref: { temp_key: 'revised' } });
      }
      if (name !== original.current.name) edits.push({ kind: 'rename_instance', instance_id: selected, name });
      removing = changes.some(c => c.kind === 'remove_port');
      }
      if (all) {
        if (renamed) { if (!renamed.trim()) throw new Error('Enter a model name. Your pending edits are preserved.'); edits.push({ kind: 'rename_model', name: renamed }); }
        if (newName || inputs || outputs) edits.push(...await newComponentEdits());
        edits.push(...queued.map(connectionEdit));
        if (from || to) { if (!from || !to) throw new Error('Choose both connection endpoints or clear the pending selection. Your edits are preserved.'); edits.push(connectionEdit({ from, to }, queued.length)); }
      }
      if (!edits.length) { setPaste(''); return true; }
      const updated = await propose(edits, removing ? 'Keep ports' : 'Keep editing', removing ? 'Remove ports' : 'Apply changes'); if (!updated) { setStatus('Proposal kept locally'); return false; } acceptAssumptions(updated); onModel(updated); load(selected, updated); if (all) clearAuthoringDraft(); setStatus(all ? 'Authoring changes saved' : 'Component saved'); return true;
    } catch (e) {
      setError(e); setStatus('');
      if (code.current) { const details = code.current.closest('details'); if (details) details.open = true; code.current.focus(); }
      return false;
    } finally { setBusy(false); }
  }
  function clearAuthoringDraft() { setQueued([]); setRenamed(''); setNewName(''); setInputs(''); setOutputs(''); setFrom(''); setTo(''); setPaste(''); setSelectionAfterSave(''); }
  function discard() { acceptAssumptions(model); clearAuthoringDraft(); load(selected); setStatus('Authoring changes discarded'); }
  useEffect(() => { onHandle({ dirty: authoringDirty, save: () => save(true), discard, pastePorts }); });
  useEffect(() => { if (selectionAfterSave && !authoringDirty) { setSelectionAfterSave(''); onSelect({ kind: 'instance', instance_id: selectionAfterSave }); } }, [selectionAfterSave, authoringDirty]);
  async function newComponentEdits(): Promise<Edit[]> {
    const ins = inputs.split(',').map(s => s.trim()).filter(Boolean), outs = outputs.split(',').map(s => s.trim()).filter(Boolean);
    if (!newName.trim() || !outs.length || [...ins, ...outs].some(s => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(s)) || new Set([...ins, ...outs]).size !== ins.length + outs.length) throw new Error('Enter a component name and unique Python port symbols; declare at least one output.');
    // No hidden physical defaults: starter declares access but requires authored output equations.
    const starter = '# Edit the equation for each declared output before running.\n' + ins.map(s => `${s} = inputs[${JSON.stringify(s)}]\n`).join('') + outs.map(s => `# outputs[${JSON.stringify(s)}] = your_equation\n`).join('');
    return [
      { kind: 'create_definition', temp_key: 'component', definition_kind: 'explicit_component', name: newName,
        ports: [...ins.map(s => ({ s, direction: 'input' as const })), ...outs.map(s => ({ s, direction: 'output' as const }))].map((p, i) => ({ temp_key: `port${i}`, name: p.s, code_symbol: p.s, direction: p.direction, value_type: 'real_scalar', units: {kind:'unspecified'} })), source: await sourceFromText(starter) },
      { kind: 'instantiate', temp_key: 'instance', version_ref: { temp_key: 'component' } },
    ];
  }
  async function addComponent() {
    const before = new Set(components.map(i => i.instance_id));
    const updated = await propose(await newComponentEdits());
    if (!updated) { setStatus('Proposal kept locally'); return; }
    const added = updated.instances.find(i => i.instance_id !== updated.root_instance_id && !before.has(i.instance_id));
    acceptAssumptions(updated); onModel(updated); if (added) { load(added.instance_id, updated); setSelectionAfterSave(added.instance_id); } setNewName(''); setInputs(''); setOutputs(''); setStatus('Component added'); setComponentSaved(n => n + 1);
  }
  const endpoints = components.flatMap(i => (model.definitions.find(d => d.definition_version_id === i.definition_version_id)?.ports ?? []).map(p => ({ key: `${i.instance_id}/${p.port_id}`, instance_id: i.instance_id, port: p, label: `${i.name} · ${p.name} (${unitLabel(p.units)})` })));
  const endpointName = (ref: { instance_id: string; port_id: string }) => { const e = endpoints.find(e => e.instance_id === ref.instance_id && e.port.port_id === ref.port_id); return e ? `${components.find(i => i.instance_id === e.instance_id)?.name} · ${e.port.name}` : 'Unavailable port'; };
  const blocked = busy || !!api.pending || !!proposal;
  const choose = (id: string) => onSelect({ kind: 'instance', instance_id: id });
  const componentLabel = instance ? instance.name + (components.filter(i => i.name === instance.name).length > 1 ? ' · instance ' + (components.filter(i => i.name === instance.name).findIndex(i => i.instance_id === selected) + 1) : '') : '';
  const componentAssumptionCount = assumptions.filter(a => a.owner.kind === 'instance').length;
  // Details panel of the canonical model view: nothing selected → the model and its
  // assumptions; a component → What it computes (with the editable source), Why, Assumptions.
  // No ports table and no incoming/outgoing lists: quantities are listed in the table below.
  const details = <section aria-label="Model authoring" className="model-authoring">
    <UnitGuidance guidance={guidance} />
    {handoff && <section className="evidence-record" aria-label="Proposed model condition"><h3>Proposed model condition</h3><p className="context-copy">{handoff.proposal.statement}</p><p>From approach v{handoff.source.version.version_number}. You are editing the current model draft; committed versions remain unchanged.</p>{handoff.proposal.evidence_links.some(l=>l.locator)&&<p>The evidence version and relationship will be saved on the model. Detailed evidence locations stay in the source approach version.</p>}<label>Condition owner<Select aria-label="Condition owner" disabled={blocked||handoffAttempted} value={handoffOwner} onChange={e=>setHandoffOwner(e.target.value)}><option value="model">Whole model</option>{model.instances.filter(i=>i.instance_id!==model.root_instance_id).map((i,n)=><option key={i.instance_id} value={i.instance_id}>{i.name} · instance {n+1}</option>)}</Select></label><Button disabled={blocked||handoffAttempted||dirty||assumptionDirty} onClick={()=>{setHandoffAttempted(true);void act(async()=>{const changed=await commitBatch([{kind:'add_assumption',temp_key:'approach_condition',owner:handoffOwner==='model'?{kind:'model'}:{kind:'instance',instance_id:handoffOwner},statement:handoff.proposal.statement,evidence_links:handoff.proposal.evidence_links.map(({evidence_version_id,relation})=>({evidence_version_id,relation}))}]);if(changed)setStatus('Model assumption saved in draft. Save a model version, then return to the approach to link it explicitly.');else if(!api.pending)setHandoffAttempted(false);});}}>Preview proposed model condition</Button>{handoffAttempted&&<p>Review the original command outcome before continuing. After an acknowledged change, save a model version and return to the approach. No approach record has changed.</p>}</section>}
    {!selected ? <section className="inspector-model" aria-label="Model details"><h3>Model</h3><p className="context-line">{modelSummary(model)}</p>
      <div className="inspector-section">{assumptionView({ kind: 'model' }, 'Model')}<div className="section-actions"><Button disabled={blocked || !assumptionDirty} onClick={() => void save(true)}>Save model draft</Button></div></div>
      <p className="context-line">Component assumptions: {componentAssumptionCount} · shown with each component</p>
    </section>
    : <div className="inspector">{!instance || !definition || loaded !== selected ? <p>Select a component to inspect its code and ports.</p> : <fieldset disabled={blocked}>
        <SectionHeader title={componentLabel} actions={<><ActionDialog title="Edit component version" label="Edit"><dl className="hf-identities"><dt>Component instance</dt><dd>{instance.name}</dd><dt>Definition</dt><dd>{definition.name}</dd><dt>Definition version ID</dt><dd><code>{definition.definition_version_id}</code></dd></dl><fieldset><legend>Instances receiving the next definition version</legend>{components.filter(i => i.definition_version_id === definition.definition_version_id).map(i => <label className="check" key={i.instance_id}><TextInput type="checkbox" aria-label={`Upgrade instance ${i.instance_id}`} checked={targets.includes(i.instance_id)} onChange={() => setTargets(toggle(targets, i.instance_id))} />{i.name} <code title={`Instance ID: ${i.instance_id}`}>({i.instance_id.slice(0, 8)})</code></label>)}<p>Unchecked instances keep their current definition version. Component name and assumptions apply only to the inspected instance.</p></fieldset>
        <label>Component name<TextInput maxLength={4096} value={name} onChange={e => setName(e.target.value)} /></label>
</ActionDialog>
        <ActionDialog title="Edit ports">{error != null && <p role="alert">{message(error)}</p>}<Disclosure><summary>Paste port metadata</summary><label>Component port metadata paste<TextArea value={paste} onChange={e => setPaste(e.target.value)} placeholder="port_id&#9;name&#9;code_symbol&#9;units" /></label><Button onClick={() => { try { const changes = parseMetadata(paste, ports.filter((p): p is PortDraft & { port_id: string } => !!p.port_id)); setPorts(ports.map(port => { const change = changes.find(c => c.kind === 'update_port' && c.port_id === port.port_id); return change?.kind === 'update_port' ? { ...port, ...change.fields } : port; })); setError(null); } catch (e) { setError(e); } }}>Stage port metadata rows</Button><p>Tab-separated header: port_id, then name, code_symbol or units. Blank units mean Not specified; write Dimensionless explicitly or use a supported spelling. Save component previews all source, metadata and assumptions together.</p></Disclosure>{ports.map((p, i) => <div className="port" key={p.port_id ?? i}><p>{p.direction} · real scalar</p><label>Port {i + 1} name<TextInput value={p.name} onChange={e => setPorts(ports.map((x, n) => n === i ? { ...x, name: e.target.value } : x))} /></label><label>Port {i + 1} symbol<TextInput value={p.code_symbol} onChange={e => setPorts(ports.map((x, n) => n === i ? { ...x, code_symbol: e.target.value } : x))} /></label>{p.port_id ? <label>Port {i + 1} definition<TextArea aria-label={'Port '+(i+1)+' definition'} maxLength={4096} value={p.statement ?? ''} onChange={e => setPorts(ports.map((x,n) => n === i ? {...x,statement:e.target.value} : x))}/></label> : <p>Save this port before adding its definition.</p>}<UnitEditor label={`Port ${i + 1} units`} value={p.units} catalog={guidance.catalog} onChange={units => setPorts(ports.map((x, n) => n === i ? { ...x, units } : x))} /><Button className="danger" onClick={() => setPorts(ports.filter((_, n) => n !== i))}>Remove port {i + 1}</Button></div>)}<Button onClick={() => setPorts([...ports, { direction: 'input', name: '', code_symbol: '', units: {kind:'unspecified'} }])}>Add input port</Button><Button onClick={() => setPorts([...ports, { direction: 'output', name: '', code_symbol: '', units: {kind:'unspecified'} }])}>Add output port</Button></ActionDialog></>} />
        <p className="context-line">{definition.name} · {ports.length} {ports.length === 1 ? 'quantity' : 'quantities'} · shown below</p>
        {explain(selected, <Disclosure className="component-source"><summary>Edit source</summary><SourceEditor key={selected} value={text} codeRef={code} error={!!error} onChange={value => { setText(value); setImported(null); }} />
          <div><p>Python source file</p><FilePicker label="Load Python source file" accept=".py,text/x-python" onChange={e => { const file = e.target.files?.[0]; if (file) void importFile(file); }} /></div></Disclosure>)}
        <div className="inspector-section">{assumptionView({ kind: 'instance', instance_id: selected }, 'Component · ' + instance.name)}</div>
        <Button hidden={!dirty && !assumptionDirty} id="save-component" className="primary" disabled={!dirty && !assumptionDirty} onClick={() => void save()}>Save component</Button>{dirty && <span>Unsaved changes</span>}
      </fieldset>}</div>}
  </section>;
  return <>
    {hosts.details && createPortal(details, hosts.details)}
{modelActionHost && createPortal(<ActionDialog title="Model name" label="Rename model"><fieldset disabled={blocked || dirty || assumptionDirty || assumptionEditing}><label>Rename model<TextInput value={renamed} maxLength={4096} placeholder={model.name} onChange={e => setRenamed(e.target.value)} /></label><Button disabled={!renamed.trim()} onClick={() => act(async () => { if (await commitBatch([{ kind: 'rename_model', name: renamed }])) setRenamed(''); })}>Preview model rename</Button></fieldset></ActionDialog>, modelActionHost)}
{hosts.toolbar && createPortal(<>
    {proposal && <ChangePreview api={api} proposal={proposal} />}
    <div role="status" aria-live="polite">{status}</div>
    {error != null && <div role="alert" id="model-errors"><p>{message(error)}</p>{error instanceof ApiError && error.detail.fields.map((f, i) => <p key={i}>{f.path}: {f.message}</p>)}
      {error instanceof ApiError && error.detail.code === 'stale_revision' && <Button onClick={() => act(async () => { setReview(await api.model(model.study_id, model.model_id)); setStatus('Current revision loaded for review'); })}>Review current revision</Button>}</div>}
    {review && <section aria-label="Current revision review"><h3>Current revision</h3><p>{review.draft_revision}</p><pre>{review.source_files.map(s => sourceText(s)).join('\n')}</pre><Button onClick={() => navigate(() => { acceptAssumptions(review); onModel(review); load(selected, review); })}>Load reviewed revision</Button><p>Your unsaved editor text remains above until you explicitly discard it.</p></section>}
<div className="model-authoring-actions">
        <ActionDialog title="Add component" label="＋ Component" completionKey={componentSaved}><fieldset disabled={blocked || dirty || assumptionDirty || assumptionEditing}><label>New component name<TextInput value={newName} maxLength={4096} onChange={e => setNewName(e.target.value)} /></label><label>Input symbols<TextInput value={inputs} onChange={e => setInputs(e.target.value)} aria-describedby="port-help" /></label><label>Output symbols<TextInput value={outputs} onChange={e => setOutputs(e.target.value)} aria-describedby="port-help" /></label><p id="port-help">Comma-separated Python symbols. All ports are real scalars; new ports start Not specified. Choose units in Edit ports before creating a configuration.</p><UnitGuidance guidance={guidance}/><Button className="primary" disabled={!guidance.catalog} onClick={() => act(addComponent)}>Add component</Button></fieldset></ActionDialog>
        <ActionDialog title="Connections" label="Connect ports" completionKey={connectionSaved}><fieldset disabled={blocked || dirty || assumptionDirty || assumptionEditing}>
          <label>Connection output<Select aria-label="Connection output" value={from} onChange={e => setFrom(e.target.value)}><option value="">Choose output</option>{endpoints.filter(e => e.port.direction === 'output').map(e => <option key={e.key} value={e.key}>{e.label}</option>)}</Select></label>
          <label>Connection input<Select aria-label="Connection input" value={to} onChange={e => setTo(e.target.value)}><option value="">Choose input</option>{endpoints.filter(e => e.port.direction === 'input').map(e => <option key={e.key} value={e.key}>{e.label}</option>)}</Select></label>
          <Button variant="primary" disabled={!from || !to} onClick={() => act(async () => { if (await commitBatch([connectionEdit({ from, to }, 0)], 'Keep editing', 'Connect ports')) { setFrom(''); setTo(''); setConnectionSaved(n => n + 1); } })}>Review connection</Button>
          {!!model.connections.length && <h3>Existing connections</h3>}
          <Button disabled={!links.length} onClick={() => act(async () => { await commitBatch(links.map(id => ({ kind: 'disconnect', connection_id: id })), 'Keep connections', 'Disconnect connections'); })}>Disconnect selected connections</Button>
          <ul>{model.connections.map(c => <li key={c.connection_id}><label className="check"><TextInput type="checkbox" aria-label={`Select connection ${c.connection_id}`} checked={links.includes(c.connection_id)} onChange={() => setLinks(toggle(links, c.connection_id))} />{endpointName(c.source_ref)} → {endpointName(c.target_ref)}</label><Button className="danger" aria-label={`Disconnect ${endpointName(c.source_ref)} to ${endpointName(c.target_ref)}`} onClick={() => act(async () => { await commitBatch([{ kind: 'disconnect', connection_id: c.connection_id }], 'Keep connections', 'Disconnect connections'); })}>Disconnect</Button><Button aria-label={`Reconnect ${c.connection_id}`} disabled={!from || !to} onClick={() => act(async () => { if (await commitBatch([{ kind: 'disconnect', connection_id: c.connection_id }, connectionEdit({ from, to }, 0)])) { setFrom(''); setTo(''); } })}>Reconnect to chosen ports</Button></li>)}</ul>
        </fieldset></ActionDialog>
<ActionDialog title="Component actions" label="•••" triggerLabel="Component actions">{instance && definition && loaded === selected && <Button disabled={blocked || dirty || assumptionDirty || assumptionEditing} onClick={() => act(async () => { const before = new Set(model.instances.map(i => i.instance_id)); const updated = await propose([{ kind: 'instantiate', temp_key: 'local_instance', version_ref: { definition_version_id: definition.definition_version_id } }]); if (updated) { const added = updated.instances.find(i => !before.has(i.instance_id)); acceptAssumptions(updated); onModel(updated); if (added) { load(added.instance_id, updated); onSelect({ kind: 'instance', instance_id: added.instance_id }); } } })}>Add another instance</Button>}
<ActionDialog title="Manage components" label="Component actions">        {!components.length && <p>Add a component to start.</p>}
        {!!components.length && <div className="component-list">{components.map(i => <div key={i.instance_id}><label className="check"><TextInput type="checkbox" aria-label={`Select component ${i.instance_id}`} disabled={blocked || dirty || assumptionDirty || assumptionEditing} checked={checked.includes(i.instance_id)} onChange={() => setChecked(toggle(checked, i.instance_id))} />{i.name}</label><Button disabled={blocked} aria-pressed={selected === i.instance_id} onClick={() => choose(i.instance_id)}>Select {i.name}</Button></div>)}</div>}
        <Button disabled={blocked || dirty || assumptionDirty || assumptionEditing || !checked.length} onClick={() => act(async () => { const incident = model.connections.filter(c => checked.includes(c.source_ref.instance_id) || checked.includes(c.target_ref.instance_id)); await commitBatch([...incident.map(c => ({ kind: 'disconnect' as const, connection_id: c.connection_id })), ...checked.map(id => ({ kind: 'remove_instance' as const, instance_id: id }))], 'Keep components', 'Remove components'); })}>Remove selected components</Button>
</ActionDialog>

</ActionDialog>      </div></>, hosts.toolbar)}
  </>;
}
