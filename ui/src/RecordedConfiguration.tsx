import { ConfigurationRecord, ConfigurationRecordDetails } from './ConfigurationRecord';
import { Button, Panel, StatusTag } from './design';
import { useRef, useState, type ReactNode } from 'react';
import { HyprnMvpApi, accessLostText, message } from './api';
import { useAccessLoss } from './accessLoss';
import { useExecutionReadiness } from './executionReadiness';
import { RunAvailability } from './RunAvailability';
import type { FrozenConfigurationRead7, PortRef } from './contract';

/** Read only the saved pair. Current model/evidence are never substituted.
 * A confirmed denial for its study (its own availability read or any other host)
 * removes the record, its approach closure and the recorded model from display. */
export function RecordedConfiguration({ onViewSourceResult, resourceActionsRef, saved, onCopy, api, activeRun, onSubmit, children }: { onViewSourceResult?: (runId: string, output: PortRef) => void; resourceActionsRef?: (element: HTMLDivElement | null) => void; saved: FrozenConfigurationRead7; onCopy: () => void; api: HyprnMvpApi; activeRun: boolean; onSubmit: (configurationId: string) => Promise<void>; /** Protected recorded action shown beside Run (the "View model version" model view). */ children?: ReactNode }) {
  const studyId = saved.configuration.study_id;
  const availability = useExecutionReadiness(api, studyId);
  const { ready } = availability;
  const [busy, setBusy] = useState(false), [error, setError] = useState(''); const locked = useRef(false);
  const [lost, setLost] = useState<string | null>(null);
  useAccessLoss(api, studyId, change => { if (change.kind === 'access-lost') setLost(saved.configuration.configuration_revision_id); });
  async function run() {
    if (locked.current || !ready || activeRun || api.pending) return;
    locked.current = true; setBusy(true); setError('');
    try { await onSubmit(saved.configuration.configuration_revision_id); } catch(e) { setError(message(e)); }
    finally { locked.current = false; setBusy(false); }
  }
  if (lost === saved.configuration.configuration_revision_id) return <Panel label="Saved configuration" className="recorded-configuration"><p role="alert">{accessLostText}</p></Panel>;
  const c = saved.configuration, model = saved.model_snapshot;
  return <><Panel label="Saved configuration" className="recorded-configuration">
<div className="page-heading configuration-heading"><div><h2>{c.name}</h2><p>Model version {c.model_revision_id.slice(0, 8)}</p></div><div className="section-actions"><StatusTag>Saved · read-only</StatusTag><div className="section-actions" ref={resourceActionsRef} /><ConfigurationRecordDetails configuration={c} /><Button onClick={onCopy}>Copy configuration to draft</Button></div></div>
    <ConfigurationRecord onViewSourceResult={onViewSourceResult} configuration={c} model={model} approachClosure={'approach_closure' in saved ? saved.approach_closure : undefined} />
    <div className="actions configuration-run"><Button variant="primary" disabled={!ready || activeRun || busy || !!api.pending} onClick={() => void run()}>Run this configuration</Button>{children}</div>
    {error && <p role="alert">{error}</p>}{activeRun && <p>A run is pending. Inspect its status before submitting another run.</p>}
    <RunAvailability status={availability} />
  </Panel></>;
}
