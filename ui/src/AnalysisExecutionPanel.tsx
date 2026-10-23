import { useEffect, useRef, useState } from 'react';
import { message, type HyprnMvpApi } from './api';
import { useStudyRead } from './calculationReads';
import type {
  AnalysisExecutionRead2,
  AnalysisExecutionRecovery1,
  CalculationVersionRead4,
} from './contract';
import { ActionGroup, Button, Progress, StatusTag } from './design';

export function AnalysisExecutionPanel({
  api,
  study,
  version,
  onProgress,
}: {
  api: HyprnMvpApi;
  study: string;
  version: CalculationVersionRead4;
  onProgress: (execution: AnalysisExecutionRead2) => void;
}) {
  const [execution, setExecution] = useState<AnalysisExecutionRead2>(null);
  const [recovery, setRecovery] = useState<AnalysisExecutionRecovery1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const read = useStudyRead(api, study);
  const progress = useRef('');
  const changed = useRef(onProgress);
  changed.current = onProgress;
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    const load = () =>
      void read(
        async (signal) => {
          const value = await api.analysisExecution(study, version.calculation_version_id, signal);
          const recovery =
            value?.state === 'failed' || value?.state === 'needs_review'
              ? await api.analysisRecovery(study, version.calculation_version_id, signal)
              : null;
          return { value, recovery };
        },
        ({ value, recovery }) => {
          if (stopped) return;
          setExecution(value);
          setRecovery(recovery);
          setLoading(false);
          setError(null);
          const signature = JSON.stringify([
            value?.state,
            value?.completed_count,
            value?.runs.map((r) => r.run_id),
          ]);
          if (progress.current !== signature) changed.current(value);
          progress.current = signature;
          if (
            value &&
            (!['complete', 'failed', 'cancelled', 'needs_review'].includes(value.state) ||
              (value.schema_version === '2' &&
                value.state === 'needs_review' &&
                value.admission_state === 'waiting'))
          )
            timer = window.setTimeout(load, 2000);
        },
        (e) => {
          if (!stopped) {
            setError(e);
            setLoading(false);
            setExecution(null);
            setRecovery(null);
          }
        },
      );
    load();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [study, version.calculation_version_id, refresh]);
  async function launch(resume = false) {
    setLaunching(true);
    setError(null);
    try {
      if (resume) await api.resumeAnalysis(study, version.calculation_version_id);
      else await api.launchAnalysis(study, version.calculation_version_id);
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(e);
    } finally {
      setLaunching(false);
    }
  }
  if (version.schema_version !== '4')
    return (
      <p className="context-copy">
        These results use earlier analysis settings. Create a new version to prepare calculations
        and validated estimates together.
      </p>
    );
  const reason = recovery?.can_resume
    ? execution?.state === 'needs_review'
      ? 'Resume to check whether these calculations started before continuing.'
      : 'The analysis was interrupted. Resume to continue using its saved calculations.'
    : execution?.reason || recovery?.reason;
  const checking =
    execution?.schema_version === '2' &&
    execution.state === 'needs_review' &&
    execution.admission_state === 'waiting';
  const busy = execution && (checking || ['calculating', 'validating'].includes(execution.state));
  return (
    <div className="hf-flow">
      {loading && <p role="status">Loading execution…</p>}
      {busy && (
        <Progress
          label={
            checking
              ? 'Checking execution records'
              : execution.schema_version === '2' && execution.admission_state === 'waiting'
                ? 'Waiting to continue'
                : execution.state === 'calculating'
                  ? 'Calculating points'
                  : 'Fitting and validating surrogate'
          }
          count={
            execution.state === 'calculating'
              ? { completed: execution.completed_count, total: execution.total_count }
              : undefined
          }
        />
      )}
      {execution && !busy && (
        <StatusTag
          tone={
            execution.state === 'complete'
              ? 'ok'
              : execution.state === 'failed' && !recovery?.can_resume
                ? 'alarm'
                : 'warning'
          }
        >
          {execution.state === 'complete'
            ? `${execution.completed_count}/${execution.total_count} calculated`
            : recovery?.can_resume
              ? 'Paused'
              : execution.state === 'failed'
                ? 'Failed'
                : execution.state === 'cancelled'
                  ? 'Cancelled'
                  : 'Needs review'}
        </StatusTag>
      )}
      {reason && <p role="status">{reason}</p>}
      {recovery?.can_resume && (
        <ActionGroup>
          <Button
            variant="primary"
            disabled={launching || !!api.pending}
            onClick={() => void launch(true)}
          >
            {launching ? 'Resuming…' : 'Resume analysis'}
          </Button>
        </ActionGroup>
      )}
      {!loading && !execution && !error && (
        <ActionGroup>
          <Button
            variant="primary"
            disabled={launching || !!api.pending}
            onClick={() => void launch()}
          >
            Launch analysis
          </Button>
        </ActionGroup>
      )}
      {error != null && (
        <div className="hf-flow">
          <p role="alert">{message(error)}</p>
          <Button onClick={() => setRefresh((v) => v + 1)}>Reload execution</Button>
        </div>
      )}
    </div>
  );
}
