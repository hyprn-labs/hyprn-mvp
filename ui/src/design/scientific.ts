import type { CriterionEvaluation1 } from '../contract';
import type { Tone } from './components';

/** Why a criterion reads as it does for a run, in the reader's words. */
export const evaluationReasons: Record<CriterionEvaluation1['reason'], string> = {
  threshold_comparison: 'Compared with the threshold',
  measured: 'Calculated',
  criterion_not_bound: 'Criterion not bound',
  run_not_recorded: 'No results yet',
  retained_record_invalid: 'Record could not be verified',
  convergence_unresolved: 'Convergence unresolved',
  required_output_unavailable: 'Output not computed',
  invalid_criterion_or_units: 'Value or units invalid',
};

/** Objective values are model calculations, not physical measurements. */
export function criterionStatus(outcome: CriterionEvaluation1['outcome']): [Tone, string] {
  switch (outcome) {
    case 'met':
      return ['ok', 'Met'];
    case 'not_met':
      return ['alarm', 'Not met'];
    case 'measured':
      return ['inert', 'Calculated'];
    default:
      return ['advisory', 'Not evaluated'];
  }
}
