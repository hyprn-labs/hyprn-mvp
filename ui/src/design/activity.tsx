import type { ReactNode } from 'react';
import { Panel } from './components';
import { SectionHeader } from './primitives';

/** One display for stored instants, never a replacement for a missing timestamp. */
export function RecordTimestamp({ at, label }: { at?: string | number | null; label: string }) {
  if (at == null) return null;
  const date = new Date(typeof at === 'number' ? at * 1000 : at);
  if (!Number.isFinite(date.getTime())) return null;
  return (
    <time
      className="hf-record-time"
      dateTime={date.toISOString()}
      title={date.toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'long' })}
    >
      {label}{' '}
      {date.toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })}
    </time>
  );
}

/** Operational progress is distinct from the saved scientific answer. */
export function StudyActivityPanel({ children }: { children: ReactNode }) {
  return (
    <Panel label="Study activity" bodyClassName="hf-flow">
      <SectionHeader title="Study activity" level={2} help="studyActivity" />
      {children}
    </Panel>
  );
}
