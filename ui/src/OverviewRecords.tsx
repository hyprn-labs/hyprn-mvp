import { RecordAttribution } from './attribution';
import { configurationCounts, runLabel } from './recordLabels';
import { Button, Panel, SectionHeader, StatusTag } from './design';
import { useEffect, useState } from 'react';
import { HyprnMvpApi, message } from './api';
import type { Study } from './api';
import { RunOutcomes, runOutcomes } from './runStatus';
import type { PublicRunDetail, RunHistoryItem } from './contract';
import type { WorkspaceLink } from './workspaceModel';

type ReadState<T> = { kind: 'loading' } | { kind: 'error'; error: unknown } | { kind: 'ready'; records: T[]; total: number; allRecords: T[] };
const limit = 5;

function useRecent<T>(api: HyprnMvpApi, studyId: string, read: (studyId: string) => Promise<T[]>) {
  const [attempt, retry] = useState(0);
  const [state, setState] = useState<ReadState<T>>({ kind: 'loading' });
  useEffect(() => {
    let current = true;
    const actor = api.actor;
    setState({ kind: 'loading' });
    // Public collections are in insertion order. Read every page before taking
    // the bounded tail; UUID order and timestamps would invent a chronology.
    void read(studyId).then(records => {
      if (current && actor === api.actor) setState({ kind: 'ready', records: records.slice(-limit).reverse(), total: records.length, allRecords: records });
    }, error => {
      if (current && actor === api.actor) setState({ kind: 'error', error });
    });
    return () => { current = false; };
  }, [api, studyId, read, attempt]);
  return { state, retry: () => retry(value => value + 1) };
}

function RecentRunOutcome({ api, studyId, run }: { api: HyprnMvpApi; studyId: string; run: RunHistoryItem }) {
  const [detail, setDetail] = useState<PublicRunDetail | null>(null), [failed, setFailed] = useState(false);
  useEffect(() => {
    let current = true; const actor = api.actor; let timer: ReturnType<typeof setTimeout> | undefined;
    setDetail(null); setFailed(false);
    async function read() {
      try {
        const value = await api.run(studyId, run.run_id);
        if (!current || actor !== api.actor) return;
        setDetail(value); setFailed(false);
        if (!value.history?.results && !['preparation_failed', 'uncertain'].includes(value.state) && !['finished', 'excepted', 'killed'].includes(value.process_state ?? '')) timer = setTimeout(read, 5000);
      } catch { if (current && actor === api.actor) { setFailed(true); timer = setTimeout(read, 10000); } }
    }
    void read(); return () => { current = false; if (timer) clearTimeout(timer); };
  }, [api, studyId, run.run_id]);
  return <RunOutcomes outcomes={runOutcomes(detail, failed)}>{failed && <small>Could not refresh status. Retrying.</small>}</RunOutcomes>;
}

export function OverviewRecords({ api, study, onOpen }: { api: HyprnMvpApi; study: Study; onOpen: (target: WorkspaceLink) => void }) {
  const configurations = useRecent(api, study.study_id, api.configurations);
  const runs = useRecent(api, study.study_id, api.runs);
  return <>
    <Panel className="recent-runs overview-card" label="Recent runs">
      <SectionHeader level={2} id="recent-runs-title" title="Recent runs" actions={<Button variant="quiet" onClick={() => onOpen({ study: study.study_id, view: 'runs' })}>View all runs</Button>} />
      {runs.state.kind === 'loading' && <p role="status" aria-busy="true">Loading recent runs…</p>}
      {runs.state.kind === 'error' && <><p role="alert">Could not load recent runs: {message(runs.state.error)}</p><Button onClick={runs.retry}>Retry recent runs</Button></>}
      {runs.state.kind === 'ready' && <>
        <p className="context-line">{runs.state.records.length} of {runs.state.total} runs · Latest added first</p>
        {runs.state.total === 0 ? <p>This study has no runs yet. Save a configuration, then run the model.</p> : <ol>{runs.state.records.map(run => <li key={run.run_id}>
          <div>
            <Button variant="quiet" aria-label={`Open run ${run.run_id}`}
              onClick={() => onOpen({ study: study.study_id, view: 'runs', run: run.run_id })}>
              {runLabel(run)} · {run.run_id.slice(0, 8)}
            </Button>
            <RecordAttribution kind="run" id={run.run_id} line />
          </div>
          <RecentRunOutcome api={api} studyId={study.study_id} run={run} />
        </li>)}</ol>}
      </>}
    </Panel>
    <Panel className="recent-configurations overview-card" label="Recent configurations">
      <SectionHeader level={2} id="recent-configurations-title" title="Recent configurations" actions={<Button variant="quiet" onClick={() => onOpen({ study: study.study_id, view: 'configurations' })}>View all configurations</Button>} />
      {configurations.state.kind === 'loading' && <p role="status" aria-busy="true">Loading recent configurations…</p>}
      {configurations.state.kind === 'error' && <><p role="alert">Could not load recent configurations: {message(configurations.state.error)}</p><Button onClick={configurations.retry}>Retry recent configurations</Button></>}
      {configurations.state.kind === 'ready' && <>
        <p className="context-line">{configurationCounts(configurations.state.allRecords)} · Showing {configurations.state.records.length} recent versions</p>
        {configurations.state.total === 0 ? <p>No saved configurations in this study. Choose a model to prepare and save a configuration.</p> : <ol>{configurations.state.records.map(({ configuration: c }) => <li key={c.configuration_revision_id}>
          <div>
            <Button variant="quiet"
              aria-label={`${c.name} · Open configuration ${c.configuration_revision_id}`}
              onClick={() => onOpen({ study: study.study_id, view: 'configurations',
                configuration: c.configuration_revision_id })}>
              {c.name}
            </Button>
            <RecordAttribution kind="configuration_version" id={c.configuration_revision_id} line />
          </div>
          <StatusTag tone="inert">Version {c.configuration_revision_id.slice(0, 8)} · read-only</StatusTag>
        </li>)}</ol>}
      </>}
    </Panel>
  </>;
}
