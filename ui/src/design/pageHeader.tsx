import type { ReactNode } from 'react';
import { OpenLink } from './navigation';
import { Button, type ButtonProps } from './components';
import { Select } from './select';
import { SectionHelp, type SectionHelpTopic } from './primitives';

/** A return names its destination; screens never draw "Back" or bare arrows. */
export type ReturnTarget = {
  label: `Return to ${string}`;
  onClick: () => void;
  disabled?: boolean;
};

export function ReturnLink({ label, onClick, disabled }: ReturnTarget) {
  return (
    <OpenLink
      direction="back"
      size="sm"
      className="hf-return-link"
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </OpenLink>
  );
}

/**
 * One header for every record and collection page: return and related links in normal
 * flow above, then the title with its record details and state, and on the right the
 * version choice followed by commands. Long titles wrap; commands start on the title row.
 */
export function PageHeader({
  title,
  level = 2,
  id,
  returnTo,
  links,
  titleEditor,
  help,
  details,
  controls,
  actions,
  className = '',
}: {
  title: ReactNode;
  help?: SectionHelpTopic;
  /** An editable name shown in place of the title; the heading stays for assistive technology. */
  titleEditor?: ReactNode;
  level?: 1 | 2 | 3;
  id?: string;
  returnTo?: ReturnTarget;
  links?: ReactNode;
  details?: ReactNode;
  controls?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  const Heading = level === 1 ? 'h1' : level === 3 ? 'h3' : 'h2';
  return (
    <header className={('hf-page-header ' + className).trim()}>
      {(returnTo || links) && (
        <nav className="hf-page-header__links" aria-label="Page links">
          {returnTo && <ReturnLink {...returnTo} />}
          {links}
        </nav>
      )}
      <div className="page-heading">
        <div>
          <div className="hf-heading-group">
            <Heading id={id} tabIndex={-1} className={titleEditor ? 'sr-only' : undefined}>
              {title}
            </Heading>
            {titleEditor}
            {help && <SectionHelp topic={help} />}
          </div>
          {details && <div className="hf-page-header__details">{details}</div>}
        </div>
        {(controls || actions) && (
          <div className="section-actions">
            {controls}
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}

/** Begin an editable successor without changing the saved record being inspected. */
export function CreateVersionAction({
  onClick,
  disabled,
  title,
}: Pick<ButtonProps, 'onClick' | 'disabled' | 'title'>) {
  return (
    <Button onClick={onClick} disabled={disabled} title={title}>
      Create new version
    </Button>
  );
}

/** Numbers come from recorded metadata, never collection position or a truncated UUID. */
export type VersionChoice = string | { id: string; number?: number };
export function versionLabel(version: VersionChoice): string {
  if (typeof version !== 'string' && version.number !== undefined)
    return 'Version ' + version.number;
  const id = typeof version === 'string' ? version : version.id;
  return 'Saved · ' + id.slice(0, 8);
}

/** A complete, unbranched ancestry establishes a model's ordinal independently of list order.
 * Missing ancestors or branches retain exact identifiers rather than inventing a sequence. */
export function lineageVersions(rows: readonly { id: string; parent: string | null }[]) {
  const byId = new Map(rows.map((row) => [row.id, row]));
  const branched = rows.some(
    (row) => rows.filter((other) => other.parent === row.parent).length > 1,
  );
  return rows.map((row) => {
    let cursor = row,
      number = 1;
    const seen = new Set([row.id]);
    while (!branched && cursor.parent !== null) {
      const parent = byId.get(cursor.parent);
      if (!parent || seen.has(parent.id)) return { id: row.id };
      seen.add(parent.id);
      cursor = parent;
      number++;
    }
    return branched ? { id: row.id } : { id: row.id, number };
  });
}

export function VersionSelect({
  label,
  value,
  versions,
  draft = false,
  disabled,
  placeholder,
  showLabel = true,
  onChange,
}: {
  label: string;
  value: string;
  versions: readonly VersionChoice[];
  showLabel?: boolean;
  placeholder?: string;
  draft?: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  const select = (
    <Select
      aria-label={label}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {draft && <option value="draft">Draft</option>}
      {!draft && !versions.length && <option value="">No saved versions</option>}
      {versions.map((version) => {
        const id = typeof version === 'string' ? version : version.id;
        return (
          <option key={id} value={id} title={id}>
            {versionLabel(version)}
          </option>
        );
      })}
    </Select>
  );
  return showLabel ? (
    <div className="hf-version-select">
      <div className="hf-control-caption">
        <span>{label}</span>
      </div>
      {select}
    </div>
  ) : (
    select
  );
}

/** The widths a page's content column may take, each a layout token. */
export type ColumnWidth = 'reading' | 'form' | 'login' | 'full';

/**
 * The page's content column. Its width comes from a layout token (reading: home-max, form:
 * form-max, login: login-max, full: the canvas); every section inside spans the column and
 * sections are spaced evenly. Screens never set a page or section width themselves.
 */
export function ContentColumn({
  width,
  className = '',
  children,
}: {
  width: ColumnWidth;
  className?: string;
  children: ReactNode;
}) {
  return <div className={`hf-column hf-column--${width} ${className}`.trim()}>{children}</div>;
}

/** Saved values are readable text, never disabled editing affordances. */
export function SavedField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="hf-form-field">
      <span className="context-line">{label}</span>
      <p className="hf-saved-value">{children}</p>
    </div>
  );
}
