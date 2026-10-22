import type { ReactNode } from 'react';
import { ActionDialog } from './primitives';

type RecordKind = 'Analysis' | 'Model' | 'Configuration' | 'Run' | 'Approach' | 'Method'
  | 'Model explanation' | 'Study brief' | 'Study answer' | 'Evidence' | 'Prediction';

/** Record identity is secondary metadata, always directly below its owning title. */
export function RecordDetails({ kind, metadata, children }: {
  kind: RecordKind;
  metadata?: ReactNode;
  versionId?: string;
  recordId?: string;
  children: ReactNode;
}) {
  return (
    <div className="hf-record-metadata" data-record-kind={kind}>
      <ActionDialog
        title={kind === 'Model' ? 'Model version record' : `${kind} record`}
        label="Record details"
        triggerLabel={`${kind} record details`}
        size="sm"
        purpose="reader"
      >
        {children}
      </ActionDialog>
      {metadata}
    </div>
  );
}
