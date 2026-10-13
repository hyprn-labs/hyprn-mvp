/** Display precision only; never used for storage, comparisons, input editing or exports. */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return 'not computed';
  if (value === 0) return '0';
  const magnitude = Math.abs(value);
  if (magnitude < .001 || magnitude >= 1e9) return value.toExponential(3).replace(/\.?0+e/, 'e');
  return Number(value.toFixed(3)).toString();
}
