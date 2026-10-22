import { DataTable, StatusTag } from './components';
import { ErrorAllowance } from './errorAllowance';
import { MetricGrid } from './workspace';
import { formatNumber } from './numbers';
import { displayUnit } from '../unitLabels';

export type ValidationRow = {
  name: string;
  units?: string;
  method?: string | null;
  reason?: string | null;
  tolerance?: { absolute: number; relative: number };
  metrics?: {
    assessed_count: number;
    failed_count: number;
    max_absolute_error: number | null;
    rmse: number | null;
    target_met: boolean;
  } | null;
};
function errorValue(value: number | null | undefined, units?: string) {
  if (value == null) return 'Not computed';
  const unit = units === undefined ? '' : displayUnit(units);
  return (
    <span title={`${value} ${unit}`}>
      {value > 0 && value < 0.001 ? '< 0.001' : formatNumber(value)} {unit}
    </span>
  );
}
/** The same saved validation facts in a collection table or a single-result reader. */
export function SurrogateValidation({
  rows,
  summary = false,
}: {
  rows: ValidationRow[];
  summary?: boolean;
}) {
  const columns = [
    { key: 'output', label: 'Output', presentation: 'label' as const },
    { key: 'method', label: 'Method', presentation: 'compact' as const },
    { key: 'points', label: 'Points', numeric: true },
    { key: 'max', label: 'Max. error', numeric: true },
    { key: 'rmse', label: 'RMSE', numeric: true },
    { key: 'allowance', label: 'Allowed error', presentation: 'formula' as const },
    { key: 'result', label: 'Result', presentation: 'compact' as const },
  ];
  const values = rows.map((row) => ({
    output: row.name,
    method:
      row.method === 'response_surface'
        ? 'Response surface'
        : row.method === 'kriging'
          ? 'Kriging'
          : 'Not fitted',
    points: row.metrics
      ? row.metrics.failed_count
        ? `${row.metrics.assessed_count} assessed; ${row.metrics.failed_count} unavailable`
        : row.metrics.assessed_count
      : 'Not assessed',
    max: errorValue(row.metrics?.max_absolute_error, row.units),
    rmse: errorValue(row.metrics?.rmse, row.units),
    allowance: row.tolerance ? (
      <ErrorAllowance {...row.tolerance} units={row.units} reference="calculated output" compact />
    ) : (
      'Not recorded'
    ),
    result:
      row.reason === null && row.metrics?.target_met ? (
        <StatusTag tone="ok">Passed</StatusTag>
      ) : (
        <span className="hf-result-cell">
          <StatusTag tone="advisory">Not usable</StatusTag>
          {row.reason?.replace(/_/g, ' ')}
        </span>
      ),
  }));
  if (summary)
    return (
      <>
        {values.map((row, index) => (
          <MetricGrid
            key={index}
            label={`${rows[index].name} validation`}
            items={columns.slice(1).map((column) => ({
              label: column.key === 'points' ? 'Validation points' : column.label,
              value: row[column.key as keyof typeof row],
            }))}
          />
        ))}
      </>
    );
  return (
    <DataTable
      regionLabel="Surrogate validation"
      className="hf-table--comparison"
      columns={columns}
      rows={values}
    />
  );
}
