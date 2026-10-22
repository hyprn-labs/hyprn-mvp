import type { HyprnMvpApi, RevisionSummary } from './api';
export type CalculationScope = { model?: string; revision?: string };

/** Navigation metadata never loads full configurations or run history. */
export async function calculationCatalogue(
  api: HyprnMvpApi,
  study: string,
  preferred: CalculationScope,
  knownModels: Array<{ model_id: string; name: string }>,
  cached?: { model?: string; revisions: RevisionSummary[] },
) {
  const associations = cached && knownModels.length ? knownModels : await api.models(study);
  const models = associations.map((a) => ({
    model_id: a.model_id,
    name: a.name ?? 'Model name unavailable',
  }));
  const model = preferred.model ?? models[0]?.model_id;
  if (!model) return { models, revisions: [] as RevisionSummary[], scope: {}, warning: '' };
  if (!models.some((m) => m.model_id === model)) models.push({ model_id: model, name: 'Model name unavailable' });
  let revisions: RevisionSummary[];
  let warning = '';
  try {
    revisions = cached?.model === model ? [...cached.revisions] : await api.revisions(study, model);
  } catch {
    // Offline fallback is explicit and rare; retained records remain authoritative.
    const summaries = await api.configurationSummaries(study, { model_id: model });
    const versions = [...new Set(summaries.data.map((c) => c.model_revision_id))];
    revisions = await Promise.all(
      versions.map(async (version) => {
        const c = summaries.data.find((c) => c.model_revision_id === version)!;
        return (await api.configuration(study, c.configuration_revision_id)).model_snapshot;
      }),
    );
    warning =
      'Model version list unavailable. Showing versions from the first page of retained configurations.';
  }
  if (preferred.revision && !revisions.some((r) => r.model_revision_id === preferred.revision))
    revisions.push(await api.revision(study, model, preferred.revision));
  const parents = new Set(revisions.map((r) => r.parent_model_revision_id));
  const latest = revisions.filter((r) => !parents.has(r.model_revision_id)).at(-1);
  return {
    models,
    revisions,
    scope: { model, revision: preferred.revision ?? latest?.model_revision_id },
    warning,
  };
}
