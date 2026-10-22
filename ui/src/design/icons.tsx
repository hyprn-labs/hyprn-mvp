import type { ReactElement } from 'react';

export type ActionIconName =
  | 'close'
  | 'back'
  | 'add'
  | 'import'
  | 'export'
  | 'open-record'
  | 'chevron-left'
  | 'chevron-right'
  | 'chevron-up'
  | 'chevron-down'
  | 'search'
  | 'expand'
  | 'contract';

// Independently drawn on a 24-unit grid; no icon library or font assets.
const paths: Record<Exclude<ActionIconName, 'search'>, string> = {
  'open-record': 'M6 18 18 6M6 6h12v12',
  expand: 'M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5',
  contract: 'M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5',
  close: 'M6 6l12 12M18 6L6 18',
  back: 'M20 12H4m7-7-7 7 7 7',
  add: 'M12 4v16M4 12h16',
  import: 'M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6',
  export: 'M12 16V4m-5 5 5-5 5 5M4 15v6h16v-6',
  'chevron-left': 'm15 5-7 7 7 7',
  'chevron-right': 'm9 5 7 7-7 7',
  'chevron-up': 'm5 15 7-7 7 7',
  'chevron-down': 'm5 9 7 7 7-7',
};

/** Decorative only. Give the containing Button visible text or an aria-label. */
export function ActionIcon({ name }: { name: ActionIconName }): ReactElement {
  return (
    <svg
      className="hf-glyph"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="square"
      strokeLinejoin="miter"
    >
      {name === 'search' ? (
        <>
          <circle cx="10" cy="10" r="6" />
          <path d="m15 15 6 6" />
        </>
      ) : (
        <path d={paths[name]} />
      )}
    </svg>
  );
}
