import { createContext, createElement, Fragment, useContext } from 'react';
import type { ReactElement } from 'react';
import { attributionKey } from './api';
import type { AttributionEntry, AttributionIndex, AttributionKind } from './api';
import { AttributionChip } from './design';

/** Who wrote what in the open study, read once per open study by the study shell and cleared
 * when access to the study ends. Outside a study, and before the read answers, it is empty. */
export const emptyAttribution: AttributionIndex = new Map();
export const AttributionContext = createContext<AttributionIndex>(emptyAttribution);

/** The attribution entry of one record, or null when a person wrote it. Versioned records are
 * looked up by their exact version id (study revision, draft revision, model, evidence,
 * approach or configuration version id), so a historical view shows the entry stored with that
 * version and a later human version shows none; a study and a run by their own id. */
export function useAttribution(kind: AttributionKind, id: string | null | undefined) {
  const index = useContext(AttributionContext);
  return id ? (index.get(attributionKey(kind, id)) ?? null) : null;
}

/** "{agent} for {user}" as text, for Record details values. */
export const attributionText = (entry: AttributionEntry) => `${entry.agent} for ${entry.user}`;

type RecordProps = { kind: AttributionKind; id: string | null | undefined };

/** The attribution chip of one record when an agent wrote it; nothing for a person's record.
 * `line` places the chip on its own small metadata line; `inline` ends a metadata line with it,
 * after a space. */
export function RecordAttribution({
  kind,
  id,
  className,
  line = false,
  inline = false,
}: RecordProps & { className?: string; line?: boolean; inline?: boolean }): ReactElement | null {
  const entry = useAttribution(kind, id);
  if (!entry) return null;
  const chip = createElement(AttributionChip, { ...entry, className });
  if (line) return createElement('p', { className: 'context-line' }, chip);
  return inline ? createElement(Fragment, null, ' ', chip) : chip;
}

/** The Record details row ("Saved by", "Submitted by" or "Changed by") of one record when an
 * agent wrote it; nothing for a person's record. */
export function AttributionDetail({
  kind,
  id,
  label,
}: RecordProps & {
  label: 'Saved by' | 'Submitted by' | 'Changed by';
}): ReactElement | null {
  const entry = useAttribution(kind, id);
  return (
    entry &&
    createElement(
      Fragment,
      null,
      createElement('dt', null, label),
      createElement('dd', null, attributionText(entry)),
    )
  );
}
