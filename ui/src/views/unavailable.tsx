import { FeatureUnavailable } from '../design';
import { resourceViewLink } from '../workspaceModel';
import type { ViewEntry } from './registry';

export const documentsView: ViewEntry<'documents'> = {
  name: 'documents', placement: {kind: 'tab', label: 'Documents', position: 5},
  parseLink: resourceViewLink, available: () => true,
  render: ({view}) => view === 'documents' ? <FeatureUnavailable name="Documents" /> : null,
};
export const helpView: ViewEntry<'help'> = {
  name: 'help', placement: {kind: 'link', tab: 'help', breadcrumb: 'Help'},
  parseLink: resourceViewLink, available: () => true,
  render: ({view}) => view === 'help' ? <FeatureUnavailable name="Help" /> : null,
};
