import { test, expect } from 'playwright/test';
import { ApiError, HyprnMvpApi } from '../src/api';

// The client follows the owner's recovery and keeps no table of receipt states or categories:
// adopt and refused settle the command, resend_same_command resends the exact original body
// once, wait and uncertain never resend, and an answer without recovery never resends.

type Call = { path: string; method: string; body?: unknown };
type Answer = () => unknown;

const receipt =
  (state: string, recovery?: string, extra: object = {}) =>
  () => ({
    schema_version: '1',
    data: {
      command_id: 'original',
      state,
      result: null,
      error: null,
      ...extra,
      ...(recovery ? { recovery } : {}),
    },
  });
const missing = (recovery?: string, retry?: number) => () => {
  const detail = {
    code: 'resource_not_found',
    message: 'resource not found',
    outcome: 'unchanged',
    fields: [],
  };
  const members = recovery ? { recovery, ...(retry ? { retry_after_s: retry } : {}) } : {};
  throw new ApiError({ ...detail, ...members } as never);
};

function lostReply(answer: Answer) {
  const api = new HyprnMvpApi();
  const calls: Call[] = [];
  let mutation = 0;
  api.request = async (path, payload, method = payload === undefined ? 'GET' : 'POST') => {
    calls.push({ path, method, body: structuredClone(payload) });
    if (method !== 'GET') {
      mutation++;
      if (mutation === 1) throw new TypeError('Response lost');
      return { schema_version: '1', data: { saved: true } } as never;
    }
    return answer() as never;
  };
  const mutations = () => calls.filter((call) => call.method !== 'GET');
  return { api, calls, mutations };
}

async function send(api: HyprnMvpApi, category: string) {
  const body = {
    command_id: 'original',
    expected_revision: 'r1',
    edits: [{ text: 'exact original' }],
  };
  const original = structuredClone(body);
  const path = category === 'run' ? '/studies/s/runs' : '/studies/s/models/m/edits';
  await expect(api.mutate(path, body, category, 's')).rejects.toThrow();
  body.edits[0].text = 'later local edit';
  return { path, original };
}

for (const [name, answer] of [
  ['adopt', receipt('committed', 'adopt')],
  ['refused', receipt('rejected', 'refused')],
] as const) {
  test(`${name} settles the original command without a resend`, async () => {
    const { api, mutations } = lostReply(answer);
    await send(api, 'model');
    await api.reconcile();
    expect(api.pending).toBeNull();
    expect(api.retryReady).toBe(false);
    expect(mutations()).toHaveLength(1);
  });
}

for (const [name, answer] of [
  ['a pending remote model receipt', receipt('pending_remote', 'resend_same_command')],
  ['a missing receipt', missing('resend_same_command')],
] as const) {
  test(`resend_same_command after ${name} resends the exact original body once`, async () => {
    const { api, calls, mutations } = lostReply(answer);
    const { path, original } = await send(api, 'model');
    await api.reconcile();
    expect(api.retryReady).toBe(true);
    expect(mutations()).toHaveLength(1);
    await api.retryOriginal();
    expect(calls.map((call) => call.method)).toEqual(['POST', 'GET', 'GET', 'POST']);
    expect(calls[3]).toEqual({ path, method: 'POST', body: original });
    expect(api.pending).toBeNull();
  });
}

for (const [name, answer, rejects] of [
  ['wait on a pending receipt', receipt('pending_remote', 'wait', { retry_after_s: 2 }), false],
  ['wait on a missing run receipt', missing('wait', 2), true],
  ['uncertain', receipt('uncertain', 'uncertain'), false],
  ['a missing receipt without recovery', missing(), true],
  ['a receipt without recovery', receipt('pending_remote'), false],
] as const) {
  test(`${name} keeps the command pending and never resends it`, async () => {
    const { api, mutations } = lostReply(answer);
    await send(api, 'model');
    if (rejects) await expect(api.reconcile()).rejects.toThrow();
    else await api.reconcile();
    expect(api.pending?.body.command_id).toBe('original');
    expect(api.retryReady).toBe(false);
    await expect(api.retryOriginal()).rejects.toThrow();
    expect(mutations()).toHaveLength(1);
  });
}

for (const [name, answer] of [
  ['accepted', receipt('accepted_run', 'adopt', { result: { run_id: 'run' } })],
  ['dispatching', receipt('dispatching', 'adopt', { result: { run_id: 'run' } })],
  ['uncertain', receipt('uncertain', 'uncertain')],
  ['missing', missing('wait', 2)],
] as const) {
  test(`a run whose receipt is ${name} is never resent`, async () => {
    const { api, mutations } = lostReply(answer);
    await send(api, 'run');
    await api.reconcile().catch(() => undefined);
    await expect(api.retryOriginal()).rejects.toThrow();
    expect(mutations()).toHaveLength(1);
  });
}
