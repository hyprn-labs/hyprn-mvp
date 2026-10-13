import type { FrozenConfigurationRead7, RunHistoryItem } from './contract';

// Presentation only: IDs remain the navigation and grouping authority.
export function runLabel(run: RunHistoryItem): string {
  return run.configuration_name?.trim() ? run.configuration_name : 'Run';
}
export function configurationCounts(records: FrozenConfigurationRead7[]): string {
  const families = new Set(records.map(r => r.configuration.configuration_id).filter(Boolean));
  const unlinked = records.filter(r => !r.configuration.configuration_id).length;
  return `${families.size} configuration${families.size === 1 ? '' : 's'} · ${records.length} saved version${records.length === 1 ? '' : 's'}${unlinked ? ` · ${unlinked} not grouped with a configuration` : ''}`;
}
