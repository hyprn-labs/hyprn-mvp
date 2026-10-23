import { HelpCenter } from '../design';
import { resourceViewLink } from '../workspaceModel';
import type { ViewEntry } from './registry';

export const helpView: ViewEntry<'help'> = {
  name: 'help',
  placement: { kind: 'link', tab: 'help', breadcrumb: 'Help' },
  parseLink: resourceViewLink,
  available: () => true,
  render: ({ view }) => (view === 'help' ? <HelpCenter /> : null),
};
