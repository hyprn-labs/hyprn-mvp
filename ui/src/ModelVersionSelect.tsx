import { lineageVersions, VersionSelect } from './design';
import type { RevisionSummary } from './api';

/** Same version vocabulary for model authoring and saved calculation contexts. */
export function ModelVersionSelect({
  value,
  revisions,
  draft = false,
  showLabel = true,
  disabled,
  onChange,
}: {
  value: string;
  revisions: RevisionSummary[];
  draft?: boolean;
  showLabel?: boolean;
  disabled?: boolean;
  onChange: (version: string) => void;
}) {
  return (
    <VersionSelect
      label="Model version"
      showLabel={showLabel}
      value={value}
      draft={draft}
      versions={lineageVersions(
        revisions.map((r) => ({ id: r.model_revision_id, parent: r.parent_model_revision_id })),
      )}
      disabled={disabled}
      onChange={onChange}
    />
  );
}
