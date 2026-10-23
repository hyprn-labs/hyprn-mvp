import { useEffect, useState } from 'react';
import type { HyprnMvpApi } from './api';
import type { StudyActivity1 } from './contract';
import {
  ActionGroup,
  Button,
  OpenLink,
  Progress,
  RecordTimestamp,
  StatusTag,
  StudyActivityPanel,
  ResourceCard,
} from './design';
import type { WorkspaceLink } from './workspaceModel';

const states: Record<string, string> = {
  queued: 'Assistant queued',
  starting: 'Assistant starting',
  running: 'Assistant working',
  waiting: 'Assistant waiting for tools',
  stopping: 'Stopping Assistant',
  blocked: 'Assistant needs attention',
  unavailable: 'Assistant unavailable',
};

/** Independent of chat visibility. Reads are fenced, serialized and paused in hidden tabs. */
export function StudyActivity({
  api,
  study,
  onOpen,
}: {
  api: HyprnMvpApi;
  study: string;
  onOpen: (link: WorkspaceLink) => void;
}) {
  const [data, setData] = useState<StudyActivity1 | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true,
      busy = false,
      lost = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let fence: ReturnType<HyprnMvpApi['fence']> | undefined;
    setData(null);
    setError(false);
    async function read() {
      if (!alive || busy || lost || document.hidden) return;
      if (timer) clearTimeout(timer);
      busy = true;
      const current = api.fence({ studyId: study });
      fence = current;
      let delay = 5000;
      try {
        const next = await api.studyActivity(study, current.signal);
        if (!alive || !current.valid()) return;
        setData(next);
        setError(false);
        if (!next.analyses.length && (!next.assistant_state || next.assistant_state === 'idle'))
          delay = 15000;
      } catch (failure) {
        const outcome = await api.readFailed(failure, current);
        if (!alive || outcome === 'stale') return;
        if (outcome === 'access-lost') {
          lost = true;
          setData(null);
        }
        setError(true);
        delay = 15000;
      } finally {
        current.done();
        busy = false;
        if (alive && !lost) timer = setTimeout(() => void read(), delay);
      }
    }
    const visibility = () => {
      if (!document.hidden) void read();
    };
    const unsubscribe = api.onSessionChange((change) => {
      if (change.kind !== 'access-lost' || change.studyId === study) {
        lost = true;
        fence?.abort();
        setData(null);
        setError(true);
      }
    });
    document.addEventListener('visibilitychange', visibility);
    void read();
    return () => {
      alive = false;
      fence?.abort();
      if (timer) clearTimeout(timer);
      unsubscribe();
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [api, study, retry]);
  const open = (view: WorkspaceLink['view']) => onOpen({ study, view });
  return (
    <StudyActivityPanel>
      {error && (
        <div role="alert" className="hf-flow">
          <p>
            {data
              ? 'Updates unavailable. Showing last confirmed activity.'
              : 'Activity unavailable.'}
          </p>
          <Button onClick={() => setRetry((n) => n + 1)}>Retry</Button>
        </div>
      )}
      {!data && !error && <p role="status">Loading study activity…</p>}
      {data && (
        <>
          <ActionGroup>
            <OpenLink onClick={() => open('model')}>{data.counts.models} models</OpenLink>
            <OpenLink onClick={() => open('configurations')}>
              {data.counts.configuration_versions} configuration versions
            </OpenLink>
            <OpenLink onClick={() => open('runs')}>{data.counts.runs} runs</OpenLink>
            <OpenLink onClick={() => open('calculations')}>
              {data.counts.analyses} analyses
            </OpenLink>
          </ActionGroup>
          {!data.analyses.length && (
            <p role="status">
              {states[data.assistant_state ?? ''] ?? 'No analysis currently running.'}
            </p>
          )}
          {data.analyses.map((analysis) => {
            const active = ['calculating', 'validating'].includes(analysis.state);
            const label =
              analysis.state === 'validating'
                ? 'Validating surrogate'
                : analysis.state === 'calculating'
                  ? 'Calculating'
                  : analysis.state === 'complete'
                    ? 'Calculation finished'
                    : analysis.state === 'cancelled'
                      ? 'Cancelled'
                      : 'Needs attention';
            const pending = analysis.assigned_count - analysis.completed_count;
            const waiting = analysis.total_count - analysis.assigned_count;
            return (
              <ResourceCard
                key={analysis.calculation_version_id}
                level={3}
                title={analysis.name}
                facts={[<RecordTimestamp at={analysis.last_progress_at} label="Last progress" />]}
                actions={
                  <OpenLink
                    onClick={() =>
                      onOpen({
                        study,
                        view: 'calculations',
                        model: analysis.model_id,
                        revision: analysis.revision,
                        calculation_version: analysis.calculation_version_id,
                      })
                    }
                  >
                    Open analysis
                  </OpenLink>
                }
              >
                {active && !error ? (
                  <Progress
                    label={label}
                    count={{ completed: analysis.completed_count, total: analysis.total_count }}
                    message={`${analysis.completed_count} / ${analysis.total_count} runs recorded`}
                  />
                ) : (
                  <StatusTag tone={error ? 'inert' : 'advisory'}>
                    {error ? 'Last confirmed: ' + label : label}
                  </StatusTag>
                )}
                <p className="hf-activity-counts">
                  {pending} submitted · {waiting} awaiting submission
                </p>
              </ResourceCard>
            );
          })}
          {data.has_more_analyses && <p>More active analyses are available in Experiments.</p>}
        </>
      )}
    </StudyActivityPanel>
  );
}
