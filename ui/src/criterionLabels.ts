import type { Criterion } from './contract';

export const criterionOperators: Record<Criterion['operator'], string> = {
  lt: 'less than', le: 'at most', eq: 'equal to', ge: 'at least', gt: 'greater than',
};
