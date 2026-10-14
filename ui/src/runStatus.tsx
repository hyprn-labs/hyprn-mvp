import type { ReactNode } from 'react';
import type { PublicRunDetail, RunHistoryItem } from './contract';
import { Ledger, StatusTag, type Tone } from './design';

export type OutcomeLabel = { label: string; tone: Tone };

/**
 * Run outcomes shown to readers.
 *
 * A run headline shows only the facets the runtime actually computes today:
 * Execution and Criteria. Current results omit unsupported scientific status
 * placeholders and aggregate output counts. Exact historical artifacts retain
 * their recorded fields; public historical views identify their source and view
 * separately. Execution and criteria are never merged into one badge. Missing
 * outputs keep an explicit reason and are never treated as zero.
 */
export type RunOutcomeFacets = { execution: OutcomeLabel; criteria: OutcomeLabel };

export function criterionStatus(criteria: Array<{ outcome: string }>): OutcomeLabel {
  if (!criteria.length) return { label: 'None defined', tone: 'inert' };
  const failed = criteria.filter(c => c.outcome === 'violated').length;
  const unresolved = criteria.filter(c => c.outcome !== 'met' && c.outcome !== 'violated').length;
  return failed ? { label: `${failed} of ${criteria.length} not met`, tone: 'alarm' } : unresolved ? { label: `${unresolved} of ${criteria.length} not evaluated`, tone: 'advisory' } : { label: `${criteria.length} of ${criteria.length} met`, tone: 'ok' };
}

/** Execution of a retained result. Only finished and failed exist; anything else is unknown, never success. */
export function executionResult(state: unknown): OutcomeLabel {
  return state === 'finished' ? { label: 'Completed', tone: 'ok' } : state === 'failed' ? { label: 'Failed', tone: 'alarm' } : { label: 'Unknown', tone: 'advisory' };
}

/** A stored request is never evidence of successful execution or scientific validity. */
export function executionStatus(run: RunHistoryItem | PublicRunDetail): OutcomeLabel {
  const result = 'history' in run ? run.history?.results?.execution : undefined;
  if (result) return executionResult(result.state);
  if ('process_state' in run) {
    if (run.process_state === 'excepted' || run.process_state === 'killed' || (run.exit_status != null && run.exit_status !== 0)) return { label: 'Failed', tone: 'alarm' };
    if (run.process_state === 'finished') return { label: 'Finished · results unavailable', tone: 'warning' };
    if (run.process_state === 'running') return { label: 'Running', tone: 'running' };
  }
  const stages: Record<RunHistoryItem['state'], OutcomeLabel> = {
    accepted_run: { label: 'Queued', tone: 'inert' }, prepared: { label: 'Ready to start', tone: 'inert' },
    dispatching: { label: 'Starting', tone: 'running' }, preparation_failed: { label: 'Preparation failed', tone: 'alarm' },
    recorded: { label: 'Results unavailable', tone: 'advisory' }, uncertain: { label: 'Needs review', tone: 'warning' },
  };
  return stages[run.state];
}

/**
 * Outcomes of one run detail read. `null` means the detail is not read: still
 * loading, or the read failed (`unavailable`). A run without results has
 * criteria "Not evaluated"; an unread run has criteria "Not available".
 */
export function runOutcomes(run: PublicRunDetail | null, unavailable = false): RunOutcomeFacets {
  if (!run) return { execution: { label: unavailable ? 'Status unavailable' : 'Loading status', tone: 'inert' }, criteria: { label: 'Not available', tone: 'advisory' } };
  const results = run.history?.results;
  return { execution: executionStatus(run), criteria: results ? criterionStatus(results.criteria) : { label: 'Not evaluated', tone: 'advisory' } };
}

/** Outcomes carried by a result-source inventory row (verified scalar of a finished or failed run). */
export function resultOutcomes(execution: { state: unknown }, criteria: Array<{ outcome: string }>): RunOutcomeFacets {
  return { execution: executionResult(execution.state), criteria: criterionStatus(criteria) };
}

/**
 * The one reader rendering of run outcomes. `summary` is the compact form used in
 * lists (Overview recent runs, Findings, result picker); `ledger` is the run
 * headline (Run › Results, Findings run details).
 */
export function RunOutcomes({ outcomes, variant = 'summary', executionDetail, children }: {
  outcomes: RunOutcomeFacets; variant?: 'summary' | 'inline' | 'ledger'; executionDetail?: string; children?: ReactNode;
}) {
  const { execution, criteria } = outcomes;
  if (variant === 'ledger') return <Ledger className="run-outcomes" label="Run status" facets={[
    { label: 'Execution', value: execution.label, tone: execution.tone, detail: executionDetail },
    { label: 'Criteria', value: criteria.label, tone: criteria.tone },
  ]} />;
  return <div className={variant === 'inline' ? 'run-outcomes-inline' : 'hf-run-summary'} aria-label="Run outcomes">
    <span>Execution <StatusTag tone={execution.tone}>{execution.label}</StatusTag></span>
    <span>Criteria <StatusTag tone={criteria.tone}>{criteria.label}</StatusTag></span>
    {children}
  </div>;
}
