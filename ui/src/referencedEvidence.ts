import { useEffect, useState } from 'react';
import { accessLostText, message, type HyprnMvpApi, type EvidenceSnapshot } from './api';
import { useAccessLoss } from './accessLoss';

/** Only explicit attachments count. Source text and the library are never searched for IDs. */
export function evidenceIds(value: unknown): string[] {
  const ids = new Set<string>();
  function visit(node: unknown) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    const object = node as Record<string, unknown>;
    // A resolved evidence body is not an attachment in its own right.
    if ('content' in object && 'source_refs' in object) return;
    for (const [key, child] of Object.entries(object)) {
      if (key === 'evidence_version_id' && typeof child === 'string') ids.add(child);
      else if (
        (key === 'evidence_version_ids' ||
          key === 'general_context_evidence_version_ids' ||
          key === 'evidence_refs') &&
        Array.isArray(child)
      )
        child.forEach((id) => {
          if (typeof id === 'string') ids.add(id);
        });
      else if (key !== 'evidence_snapshots' && key !== 'evidence') visit(child);
    }
  }
  visit(value);
  return [...ids];
}

/** Library membership follows the same exact attachments as the claim readers, including history.
 * All reads use the public API. Two owner reads at a time, with visible partial failures. */
export function useReferencedEvidence(api: HyprnMvpApi, study: string) {
  const [attempt, retry] = useState(0);
  const key = JSON.stringify([study, api.actor, attempt]);
  type State = {
    key: string;
    records: EvidenceSnapshot[];
    missing: string[];
    issues: string[];
    loading: boolean;
    unavailable?: boolean;
  };
  const empty = (): State => ({ key, records: [], missing: [], issues: [], loading: true });
  const [state, setState] = useState<State>(empty);
  useAccessLoss(api, study, () =>
    setState({ ...empty(), loading: false, issues: [accessLostText], unavailable: true }),
  );
  useEffect(() => {
    const fence = api.fence({ studyId: study });
    const ids = new Set<string>(),
      records = new Map<string, EvidenceSnapshot>(),
      issues: string[] = [];
    const queue: Array<{ label: string; read: () => Promise<unknown> }> = [];
    const add = (label: string, read: () => Promise<unknown>) => queue.push({ label, read });
    const collect = (value: unknown) => {
      evidenceIds(value).forEach((id) => ids.add(id));
      // Retained bodies supply exactly what the historical owner read; never replace with a head.
      const snapshots = (node: unknown) => {
        if (!node || typeof node !== 'object') return;
        if (Array.isArray(node)) {
          node.forEach(snapshots);
          return;
        }
        const body = node as Record<string, unknown>;
        if (
          typeof body.evidence_version_id === 'string' &&
          typeof body.content === 'string' &&
          Array.isArray(body.source_refs)
        )
          records.set(body.evidence_version_id, body as EvidenceSnapshot);
        else Object.values(body).forEach(snapshots);
      };
      snapshots(value);
    };
    add('Study brief', () => api.brief(study, fence.signal));
    add('Study brief versions', async () => {
      let cursor: number | undefined;
      do {
        const page = await api.briefVersions(study, cursor, fence.signal);
        collect(page.items);
        cursor = page.next_cursor ?? undefined;
      } while (cursor !== undefined && fence.valid());
    });
    add('Study answer', () => api.studyAnswer(study, fence.signal));
    add('Study answer versions', async () => {
      let cursor: number | undefined;
      do {
        const page = await api.studyAnswerVersions(study, cursor, fence.signal);
        collect(page.items);
        cursor = page.next_cursor ?? undefined;
      } while (cursor !== undefined && fence.valid());
    });
    add('Configurations', async () => {
      const retained = new Set<string>();
      try {
        const configurations = await api.configurations(study, fence.signal);
        for (const frozen of configurations)
          retained.add(frozen.configuration.configuration_revision_id);
        collect(configurations);
      } finally {
        // A run reads the same frozen configuration/model/approach closure. Reading
        // every numerical result duplicates that evidence and scales with sample count.
        // Recover a retained closure from one run only when its owner is unavailable.
        add('Retained configurations', async () => {
          for (const run of await api.runs(study, fence.signal)) {
            if (retained.has(run.configuration_revision_id)) continue;
            retained.add(run.configuration_revision_id);
            add('Retained configuration', () => api.run(study, run.run_id, fence.signal));
          }
        });
      }
    });
    add('Component evidence attachments', async () => {
      const scopes = new Set(['model_revision', 'definition_version', 'instance', 'port', 'connection']);
      for (const record of await api.evidence(study, fence.signal)) {
        // The selection inspector already exposes these explicit resource bindings.
        if ('resource_scope' in record && scopes.has(record.resource_scope.kind)) {
          ids.add(record.evidence_version_id);
          records.set(record.evidence_version_id, record);
        }
      }
    });
    add('Models', async () => {
      for (const model of await api.models(study, fence.signal)) {
        add('Model draft', () => api.model(study, model.model_id, fence.signal));
        add('Model explanation', () => api.modelExplanation(study, model.model_id, fence.signal));
        add('Model versions', async () => {
          for (const version of await api.revisions(study, model.model_id, fence.signal)) {
            add('Saved model', () =>
              api.revision(study, model.model_id, version.model_revision_id, fence.signal),
            );
            add('Saved model explanation', () =>
              api.modelVersionExplanation(
                study,
                model.model_id,
                version.model_revision_id,
                fence.signal,
              ),
            );
          }
        });
      }
    });
    setState(empty());
    async function run() {
      const worker = async () => {
        while (queue.length && fence.valid()) {
          const task = queue.shift()!;
          try {
            collect(await task.read());
          } catch (error) {
            await api.readFailed(error, fence);
            if (fence.valid()) issues.push(task.label + ': ' + message(error));
          }
        }
      };
      await Promise.all([worker(), worker()]);
      if (!fence.valid()) return;
      // Resolve only attached versions not already supplied by a historical snapshot.
      for (const id of ids)
        if (!records.has(id))
          add('Attached evidence', async () => {
            const record = await api.evidenceVersion(study, id, fence.signal);
            if (record.evidence_version_id !== id)
              throw new Error('The requested evidence version was not returned.');
            records.set(id, record);
          });
      await Promise.all([worker(), worker()]);
      if (fence.valid())
        setState({
          key,
          records: [...ids].flatMap((id) => (records.has(id) ? [records.get(id)!] : [])),
          missing: [...ids].filter((id) => !records.has(id)),
          issues,
          loading: false,
        });
      fence.done();
    }
    void run();
    return () => {
      fence.abort();
      fence.done();
    };
  }, [api, key, study]);
  return { ...(state.key === key ? state : empty()), refresh: () => retry((n) => n + 1) };
}
