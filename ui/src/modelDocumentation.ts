import { useEffect, useState } from 'react';
import { message, type HyprnMvpApi } from './api';
import type {
  ModelExplanationContent1,
  ModelExplanationContent2,
  ModelExplanationContent3,
  ModelExplanationDraftRead3,
} from './contract';
import type { Snapshot } from './GraphView';

const changes = new EventTarget();
export function documentationChanged(api: HyprnMvpApi, modelId: string) {
  changes.dispatchEvent(new CustomEvent('changed', { detail: { api, modelId } }));
}
export function onDocumentationChange(api: HyprnMvpApi, modelId: string, refresh: () => void) {
  const listener = (event: Event) => {
    const detail = (event as CustomEvent).detail;
    if (detail.api === api && detail.modelId === modelId) refresh();
  };
  changes.addEventListener('changed', listener);
  return () => changes.removeEventListener('changed', listener);
}
export function currentDocumentation(
  content?: ModelExplanationContent1 | ModelExplanationContent2 | ModelExplanationContent3 | null,
): ModelExplanationContent3 {
  if (content?.schema_version === '3') return content;
  if (content?.schema_version === '2')
    return { ...content, schema_version: '3', monetary_quantities: [] };
  return {
    represents: '',
    basis: '',
    calculation_logic: '',
    components: [],
    evidence_links: [],
    ...content,
    schema_version: '3',
    monetary_quantities: [],
    limits: '',
    component_details: [],
  };
}

/** Read the exact saved explanation, or the draft explicitly. No latest-version substitution. */
export function useModelDocumentation(
  api: HyprnMvpApi | undefined,
  snapshot: Snapshot,
  studyId?: string,
) {
  const [draft, setDraft] = useState<ModelExplanationDraftRead3 | null>(null);
  const [content, setContent] = useState<ModelExplanationContent3 | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const revision = 'model_revision_id' in snapshot ? snapshot.model_revision_id : null;
  const sid = studyId ?? ('study_id' in snapshot ? snapshot.study_id : ''),
    mid = snapshot.model_id;
  const identity = `${api?.actor}/${sid}/${mid}/${revision ?? 'draft'}`;
  const [loaded, setLoaded] = useState('');
  useEffect(
    () =>
      api?.onSessionChange((change) => {
        if (
          change.kind === 'signed-out' ||
          (change.kind === 'access-lost' && change.studyId === sid)
        ) {
          setContent(null);
          setDraft(null);
          setError('Access to this model is no longer available.');
        }
      }),
    [api, sid],
  );
  useEffect(
    () => (api ? onDocumentationChange(api, mid, () => setAttempt((n) => n + 1)) : undefined),
    [api, mid],
  );
  useEffect(() => {
    if (!api) {
      setLoading(false);
      return;
    }
    const fence = api.fence({ studyId: sid });
    setLoading(true);
    setError('');
    void (async () => {
      try {
        const value = revision
          ? (await api.modelVersionExplanation(sid, mid, revision, fence.signal)).explanation
          : (await api.modelExplanation(sid, mid, fence.signal)).draft;
        if (!fence.valid()) return;
        setDraft(value && 'revision' in value ? value : null);
        setContent(value ? currentDocumentation(value.content) : null);
        setLoaded(identity);
      } catch (failure) {
        await api.readFailed(failure, fence);
        if (fence.valid()) {
          setError(message(failure));
          setLoaded(identity);
        }
      } finally {
        if (fence.valid()) setLoading(false);
        fence.done();
      }
    })();
    return () => {
      fence.abort();
      fence.done();
    };
  }, [api, identity, attempt]);
  return {
    content: loaded === identity ? content : null,
    revision: loaded === identity ? (draft?.revision ?? null) : null,
    loading: !!api && (loading || loaded !== identity),
    error: loaded === identity ? error : '',
    retry: () => setAttempt((n) => n + 1),
    save: async (next: ModelExplanationContent3, expectedRevision: string | null) => {
      if (!api || revision || loaded !== identity || loading || error)
        throw new Error('Read the current model documentation before editing it.');
      const saved = await api.saveModelExplanationDraft(sid, mid, {
        command_id: crypto.randomUUID(),
        expected_revision: expectedRevision,
        content: next,
      });
      setDraft(saved);
      setContent(currentDocumentation(saved.content));
      documentationChanged(api, mid);
    },
  };
}
