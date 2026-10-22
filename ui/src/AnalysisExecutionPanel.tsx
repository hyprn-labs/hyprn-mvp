import { useEffect, useRef, useState } from 'react';
import { message, type HyprnMvpApi } from './api';
import { useStudyRead } from './calculationReads';
import type { AnalysisExecution1, CalculationVersionRead4 } from './contract';
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
  onProgress: (execution: AnalysisExecution1 | null) => void;
}) {
  const [execution, setExecution] = useState<AnalysisExecution1 | null>(null);
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
        (signal) => api.analysisExecution(study, version.calculation_version_id, signal),
        (value) => {
          if (stopped) return;
          setExecution(value);
          setLoading(false);
          setError(null);
          const signature = JSON.stringify([
            value?.state,
            value?.completed_count,
            value?.runs.map((r) => r.run_id),
          ]);
          if (progress.current !== signature) changed.current(value);
          progress.current = signature;
          if (value && !['complete', 'failed'].includes(value.state))
            timer = window.setTimeout(load, 2000);
        },
        (e) => {
          if (!stopped) {
            setError(e);
            setLoading(false);
            setExecution(null);
          }
        },
      );
    load();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [study, version.calculation_version_id, refresh]);
  async function launch() {
    setLaunching(true);
    setError(null);
    try {
      await api.launchAnalysis(study, version.calculation_version_id);
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
  const busy = execution && ['calculating', 'validating'].includes(execution.state);
  return (
    <div className="hf-flow">
      {loading && <p role="status">Loading execution…</p>}
      {busy && (
        <Progress
          label={
            execution.state === 'calculating'
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
              : execution.state === 'failed'
                ? 'alarm'
                : 'warning'
          }
        >
          {execution.state === 'complete'
            ? `${execution.completed_count}/${execution.total_count} calculated`
            : execution.state === 'failed'
              ? 'Failed'
              : 'Needs review'}
        </StatusTag>
      )}
      {execution?.reason && <p role="status">{execution.reason}</p>}
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
