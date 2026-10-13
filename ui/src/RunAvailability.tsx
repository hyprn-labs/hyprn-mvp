import { Button, StatusTag } from './design';
import type { useExecutionReadiness } from './executionReadiness';

/** Operational availability only; scientific outcomes belong to retained run results. */
export function RunAvailability({ status }: { status: ReturnType<typeof useExecutionReadiness> }) {
  if (status.ready) return null;
  const reasons = {
    executor_unavailable: 'The execution service is unavailable.',
    attestation_invalid: 'The isolated calculation environment needs verification.',
    modeling_unavailable: 'The modeling service is unavailable.',
    observation_stale: 'Checking execution service availability.',
    capability_unsupported: 'This model is not supported by the current executor.',
  };
  return <div className="run-availability" role="status"><StatusTag tone="advisory">Run unavailable</StatusTag><span>{status.readiness?.reasons.map(r => reasons[r]).join(' ') || status.readinessError || 'Checking execution service availability.'}</span><Button variant="quiet" onClick={() => void status.refreshReadiness()}>Check again</Button></div>;
}
