import { test, expect } from 'playwright/test';
import { HyprnMvpApi } from '../src/api';

for (const outcome of ['absent', 'pending_remote', 'committed']) {
  test(`original model command recovery after ${outcome}`, async () => {
    const api = new HyprnMvpApi(); const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const body = { command_id: crypto.randomUUID(), expected_revision: 'original', edits: [{ text: 'exact original' }] };
    const original = structuredClone(body);
    let mutation = 0;
    api.request = async (path, payload, method = payload === undefined ? 'GET' : 'POST') => {
      calls.push({ path, method, body: payload });
      if (method !== 'GET') {
        mutation++;
        if (mutation === 1) throw new TypeError('Response lost');
        return { schema_version: '1', data: { saved: true } } as never;
      }
      if (outcome === 'absent') {
        const { ApiError } = await import('../src/api');
        throw new ApiError({ code: 'resource_not_found', message: 'Not found', outcome: 'unchanged', fields: [] } as never);
      }
      return { schema_version: '1', data: { command_id: original.command_id, state: outcome, result: null, error: null } } as never;
    };
    await expect(api.mutate('/studies/s/models/m/edits', body, 'model', 's', 'PATCH')).rejects.toThrow();
    body.edits[0].text = 'later local edit';
    await api.reconcile();
    expect(calls.filter(c => c.method !== 'GET')).toHaveLength(1);
    if (outcome === 'committed') { expect(api.pending).toBeNull(); return; }
    expect(api.retryReady).toBe(true);
    await api.retryOriginal();
    expect(calls.map(c => c.method)).toEqual(['PATCH', 'GET', 'GET', 'PATCH']);
    expect(calls[3]).toEqual({ path: '/studies/s/models/m/edits', method: 'PATCH', body: original });
    expect(api.pending).toBeNull();
  });
}

for (const state of ['dispatching', 'uncertain']) {
  test(`native ${state} command cannot be retried`, async () => {
    const api = new HyprnMvpApi(); let mutations = 0;
    api.request = async (_path, payload) => {
      if (payload !== undefined) { mutations++; throw new TypeError('Response lost'); }
      return { schema_version: '1', data: { state, result: null } } as never;
    };
    await expect(api.mutate('/studies/s/runs', { command_id: 'original' }, 'run', 's')).rejects.toThrow();
    await api.reconcile();
    await expect(api.retryOriginal()).rejects.toThrow();
    expect(mutations).toBe(1);
  });
}
