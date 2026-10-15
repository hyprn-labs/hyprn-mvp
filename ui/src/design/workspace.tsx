import type { ReactNode } from 'react';
import { BrandLogo } from './BrandLogo';
import { Tabs, type TabItem } from './components';

/** Layout only: the application owns destinations, guards and record reads. */
export function WorkspaceShell({
  navigation,
  children,
}: {
  navigation: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="hf-workspace">
      {navigation}
      <div className="hf-workspace__canvas">
        <div className="hf-workspace__content">{children}</div>
      </div>
    </div>
  );
}

/** Real destinations supplied by the registry; no fabricated workflow progress. */
export function NavigationRail({
  primary,
  study,
  section,
  items,
  value,
  onChange,
}: {
  primary: ReactNode;
  study?: string;
  section?: string;
  items?: TabItem[];
  value?: string;
  onChange?: (id: string) => void;
}) {
  return (
    <aside className="hf-navigation" aria-label="Workspace navigation">
      <div className="hf-navigation__brand">
        <BrandLogo />
      </div>
      <nav className="hf-navigation__primary" aria-label="Main navigation">
        {primary}
        {study && (
          <div className="hf-navigation__location">
            <span className="hf-navigation__study">{study}</span>
            <span className="hf-navigation__section">{section}</span>
          </div>
        )}
      </nav>
      {items && value && (
        <Tabs
          navigation
          className="hf-navigation__sections"
          label="Workspace sections"
          items={items}
          value={value}
          onChange={onChange}
        />
      )}
    </aside>
  );
}
