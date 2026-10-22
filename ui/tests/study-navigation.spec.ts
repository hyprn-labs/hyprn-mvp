import { test, expect, type Page } from 'playwright/test';
import { createServer, type Server } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import type { ModelDraft, Study } from '../src/contract';
import { unitCatalog, modelFixture, source } from './foundry-fixtures';

// Isolated shell/state regression only. Every API request is a controlled fixture;
// this must never contact the live application or claim real API acceptance.
// The build location is refused unless it is a fresh isolated build: foundry-fixtures (imported
// above) applies that guard when it loads, before any test runs.
const build = process.env.HYPRN_MVP_NAV_BUILD;
test.skip(
  !build,
  'Isolated fixture suite requires HYPRN_MVP_NAV_BUILD; real served acceptance uses the other suites.',
);
let server: Server, origin: string;
test.beforeAll(async () => {
  server = createServer(async (request, response) => {
    response.setHeader(
      'Content-Security-Policy',
      "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
    );
    const path = new URL(request.url!, 'http://localhost').pathname;
    const file = resolve(build!, path === '/ui/' ? 'index.html' : path.replace(/^\/ui\//, ''));
    if (!path.startsWith('/ui/') || !file.startsWith(resolve(build!) + sep)) {
      response.writeHead(404).end();
      return;
    }
    try {
      const bytes = await readFile(file);
      const mime = file.endsWith('.js')
        ? 'text/javascript'
        : file.endsWith('.css')
          ? 'text/css'
          : file.endsWith('.ttf')
            ? 'font/ttf'
            : 'text/html';
      response.setHeader('Content-Type', mime);
      response.end(bytes);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise<void>((done) => server.listen(0, '127.0.0.1', done));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Isolated server unavailable');
  origin = `http://127.0.0.1:${address.port}`;
});
test.beforeEach(async ({ page }) => {
  await page.route('**/*', (route) =>
    new URL(route.request().url()).origin === origin
      ? route.continue()
      : route.abort('blockedbyclient'),
  );
});
test.afterAll(async () => {
  if (server?.listening)
    await new Promise<void>((done, reject) =>
      server.close((error) => (error ? reject(error) : done())),
    );
});

const sid = '10000000-0000-4000-8000-000000000001';
const sid2 = '10000000-0000-4000-8000-000000000002';
const mid = '20000000-0000-4000-8000-000000000001';
const version = '30000000-0000-4000-8000-000000000001';
function latch() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}
async function harness(page: Page) {
  const state = {
    studies: [
      {
        study_id: sid,
        revision: 'study-r1',
        name: 'Thermal study',
        description: 'A retained description',
        boundary: 'Retained boundary must survive',
      },
    ] as Study[],
    model: null as ModelDraft | null,
    versions: [version],
    configurations: [] as any[],
    brief: null as any,
    runs: [] as any[],
    failRunPage: false,
    failConfigurationPage: false,
    reads: [] as string[],
    writes: [] as Array<{ path: string; method: string; body: any }>,
    unknown: [] as string[],
    delayStudy: null as ReturnType<typeof latch> | null,
    uncertainCreate: false,
    expire: false,
    actor: 'owner',
    alias: null as string | null,
    profileRevision: 0,
    profileFailure: false,
    profileLostResponse: false,
    messages: [] as Array<Record<string, unknown>>,
    assistantStage: 'idle',
    assistantFailure: 'budget' as 'budget' | 'unknown' | 'none',
    assistantSends: [] as Array<{command_id: string; text: string}>,
  };
  await page.route('**/api/1/**', async (route) => {
    if (new URL(route.request().url()).origin !== origin) return route.abort('blockedbyclient');
    const request = route.request(),
      path = new URL(request.url()).pathname.slice('/api/1'.length),
      method = request.method();
    if (method === 'GET') state.reads.push(request.url());
    const body = method === 'GET' ? undefined : request.postDataJSON();
    const ok = (data: unknown) =>
      route.fulfill({ json: { schema_version: '1', data, next_cursor: null } });
    const profile = () => ({
      actor_id: state.actor, account_name: state.actor, display_alias: state.alias,
      display_name: state.alias || state.actor, revision: state.profileRevision,
    });
    if (path === '/session/mode') return ok({ mode: 'local' });
    if (path === '/session') {
      if (method === 'POST') state.actor = body.username;
      return ok({ actor_id: state.actor, csrf_token: 'isolated-fixture-token', profile: profile() });
    }
    if (path === '/profile') {
      if (method === 'PUT') {
        if (state.profileFailure) return route.fulfill({ status: 409, json: { error: {
          code: 'stale_revision', message: 'Profile changed', fields: [], outcome: 'unchanged',
        } } });
        state.alias = body.display_alias?.trim() || null;
        state.profileRevision++;
        if (state.profileLostResponse) return route.abort('failed');
      }
      return ok(profile());
    }
    if (path === '/assistant/budget' || /^\/studies\/[^/]+\/assistant\/budget$/.test(path))
      return ok({ configured: true, currency: 'USD', limit_cents: 10000,
        reserved_cents: 500, unallocated_cents: 9500, spent_cents: 125,
        remaining_cents: 9875, prior_cents: 0, new_study_limit_cents: 500,
        study_limit_cents: 500, study_spent_cents: 125, study_remaining_cents: 375,
        checked_at: 1792490000, usage_current: true, approved: null });
    if (/^\/studies\/[^/]+\/assistant\/messages$/.test(path) && method === 'POST') {
      state.assistantSends.push(body);
      if (state.assistantFailure === 'unknown') return route.abort('failed');
      if (state.assistantFailure === 'none') return ok({ state: 'running', error: null,
        can_send: false, can_stop: true, has_earlier_messages: false, messages: [] });
      return route.fulfill({ status: 429, json: { error: {
        code: 'limit_exceeded', message: 'limit exceeded', outcome: 'unchanged',
        fields: [{ path: '/assistant/budget', code: 'assistant_budget_reserved',
          message: 'The installation’s Assistant budget is fully reserved by existing conversations. No message was sent. Ask the administrator to review the budget.',
          element_ref: null }],
      } } });
    }
    if (/^\/studies\/[^/]+\/assistant$/.test(path) && method === 'GET')
      return ok({
        state: state.assistantStage, error: null,
        can_send: state.assistantStage === 'idle', can_stop: state.assistantStage !== 'idle',
        messages: state.messages, has_earlier_messages: false,
      });
    // The model editor negotiates its edit format: this service accepts model format 4 edits.
    if (path === '/capabilities' && method === 'GET')
      return ok({
        model_formats: { create_request: ['3'], edit_request: ['4'], saved_record: ['4'] },
      });
    // The study shell's attribution reads: no record in these studies was written by an agent.
    // Answered before the expiry switch, which belongs to the request each test exercises.
    const attribution =
      path === '/agent/attribution/studies' || /^\/studies\/[^/]+\/agent\/attribution$/.test(path);
    if (attribution && method === 'GET') return ok({ items: [], next_cursor: null });
    if (state.expire) {
      state.expire = false;
      return route.fulfill({
        status: 401,
        json: {
          error: {
            code: 'unauthenticated',
            message: 'Session expired',
            fields: [],
            outcome: 'unchanged',
          },
        },
      });
    }
    if (method !== 'GET') state.writes.push({ path, method, body });
    if (path === '/studies') {
      if (method === 'GET')
        return ok(
          state.actor === 'owner' && new URL(request.url()).searchParams.get('archived') !== 'true'
            ? state.studies
            : [],
        ); // this double has no archived studies
      if (state.uncertainCreate) return route.abort('failed');
      const study = {
        study_id: sid2,
        revision: 'new-study-r1',
        name: body.name,
        description: '',
        boundary: '',
      };
      state.studies.push(study);
      return ok(study);
    }
    if (path.startsWith('/commands/')) {
      return ok({ state: 'rejected', result: null, recovery: 'refused' });
    }
    const id = path.split('/')[2],
      study = state.studies.find((s) => s.study_id === id);
    if (path === `/studies/${id}` && study) {
      if (method === 'PATCH')
        Object.assign(study, {
          name: body.name,
          description: body.description,
          boundary: body.boundary,
          revision: 'study-r2',
        });
      if (state.delayStudy) await state.delayStudy.promise;
      return ok(study);
    }
    if (path === `/studies/${id}/models`) {
      if (method === 'GET')
        return ok(state.model ? [{ model_id: mid, name: state.model.name }] : []);
      state.model = {
        schema_version: '1',
        model_id: mid,
        study_id: id,
        name: body.name,
        root_instance_id: 'root',
        draft_revision: 'draft-r1',
        definitions: [],
        instances: [],
        ports: [],
        connections: [],
        boundary_mappings: [],
        annotations: [],
        source_files: [],
        required_capabilities: [],
      };
      return ok(state.model);
    }
    if (path === `/studies/${id}/models/${mid}`) return ok(state.model);
    if (path === `/studies/${id}/models/${mid}/revisions`)
      return ok(
        state.versions.map((v, i) => ({
          model_revision_id: v,
          parent_model_revision_id: state.versions[i - 1] ?? null,
          originating_draft_revision: 'draft-r1',
          digest: 'digest-fixture',
        })),
      );
    if (path.startsWith(`/studies/${id}/models/${mid}/revisions/`) && path.endsWith('/explanation'))
      return ok({ explanation: null });
    if (path.startsWith(`/studies/${id}/models/${mid}/revisions/`))
      return ok({
        ...state.model,
        model_revision_id: path.split('/').at(-1),
        parent_model_revision_id: null,
        originating_draft_revision: 'draft-r1',
        digest: 'digest-fixture',
      });
    if (path === `/studies/${id}/configurations`) return ok(state.configurations);
    if (path === `/studies/${id}/configuration-summaries`) {
      const q = new URL(route.request().url()).searchParams;
      const selected = state.configurations.filter(
        (c) =>
          (!q.get('model_id') || c.configuration.model_id === q.get('model_id')) &&
          (!q.get('model_revision_id') ||
            c.configuration.model_revision_id === q.get('model_revision_id')),
      );
      const start = q.get('cursor')
        ? selected.findIndex((c) => c.configuration.configuration_revision_id === q.get('cursor')) +
          1
        : 0;
      if (start && state.failConfigurationPage) {
        state.failConfigurationPage = false;
        return route.fulfill({
          status: 503,
          json: {
            error: {
              code: 'internal_error',
              message: 'Temporary configuration failure',
              fields: [],
              outcome: 'unchanged',
            },
          },
        });
      }

      const limit = Number(q.get('limit') ?? 50),
        rows = selected.slice(start, start + limit);
      return route.fulfill({
        json: {
          schema_version: '1',
          data: rows.map((c) => ({
            ...c.configuration,
            input_count: c.configuration.inputs.length,
          })),
          next_cursor:
            selected.length > start + limit
              ? rows.at(-1)!.configuration.configuration_revision_id
              : null,
        },
      });
    }
    if (path === `/studies/${id}/runs`) {
      const q = new URL(route.request().url()).searchParams;
      const selected = state.runs.filter(
        (r) =>
          !q.get('model_revision_id') ||
          state.configurations.some(
            (c) =>
              c.configuration.configuration_revision_id === r.configuration_revision_id &&
              c.configuration.model_revision_id === q.get('model_revision_id'),
          ),
      );
      const start = q.has('cursor')
        ? selected.findIndex((r) => r.run_id === q.get('cursor')) + 1
        : 0;
      if (start && state.failRunPage) {
        state.failRunPage = false;
        return route.fulfill({
          status: 503,
          json: {
            error: {
              code: 'internal_error',
              message: 'Temporary page failure',
              fields: [],
              outcome: 'unchanged',
            },
          },
        });
      }
      const rows = selected.slice(start, start + 20);
      return route.fulfill({
        json: {
          schema_version: '1',
          data: rows,
          next_cursor: start + 20 < selected.length ? rows.at(-1)!.run_id : null,
        },
      });
    }
    if (path === `/studies/${id}/evidence`) return ok([]);
    // Declared doubles, as in foundry-fixtures.ts: the model editor reads the pinned unit catalog
    // (creation stays disabled without it), and the study shell reads the latest saved
    // approach. These presentation studies have no approach.
    if (path === `/studies/${id}/unit-catalog` && study && method === 'GET') return ok(unitCatalog);
    if (path === `/studies/${id}/approach` && study && method === 'GET')
      return ok({ draft: null, latest_version: null });
    // These studies have no study brief and no saved brief versions; Overview reads both.
    if (path === `/studies/${id}/brief` && study && method === 'GET')
      return ok({ draft: state.brief, latest_version: null });
    if (path === `/studies/${id}/brief/draft` && method === 'POST') {
      state.brief = { schema_version: '1', revision: 'brief-r2', content: body.content };
      return ok(state.brief);
    }
    if (path === `/studies/${id}/brief/versions` && study && method === 'GET')
      return ok({ items: [], next_cursor: null });
    if (path === `/studies/${id}/answer` && study && method === 'GET')
      return ok({ draft: null, latest_version: null });
    if (path === `/studies/${id}/answer/versions` && study && method === 'GET')
      return ok({ items: [], next_cursor: null });
    if (path === `/studies/${id}/models/${mid}/explanation` && study && method === 'GET')
      return ok({ draft: null, latest_version: null });
    // These studies have no calculations and no reference marks; the Calculations area reads both.
    if (path === `/studies/${id}/analyses` && study && method === 'GET')
      return ok({ items: [], next_cursor: null });
    if (path === `/studies/${id}/reference-marks` && study && method === 'GET')
      return ok({ items: [] });
    // As foundry-fixtures.ts: this legacy presentation model has no assumption closure; the read is
    // explicitly unavailable (honest recovery, never fabricated evidence).
    if (path === `/studies/${id}/models/${mid}/assumption-evidence` && study && method === 'GET')
      return route.fulfill({
        status: 409,
        json: {
          error: {
            code: 'source_result_unavailable',
            message: 'Unavailable in this legacy presentation fixture',
            fields: [],
            outcome: 'unchanged',
          },
        },
      });
    if (path.endsWith('/execution-readiness'))
      return ok({
        readiness_schema_version: '1',
        capability: 'flat_explicit_scalar',
        status: 'unavailable',
        reasons: ['executor_unavailable'],
        observed_at: null,
        expires_at: null,
      });
    state.unknown.push(method + ' ' + path);
    return route.fulfill({
      status: 500,
      json: {
        error: {
          message: 'Unexpected isolated request',
          code: 'internal_error',
          fields: [],
          outcome: 'unchanged',
        },
      },
    });
  });
  return state;
}
async function login(page: Page, hash = '', name = 'owner') {
  await page.goto(origin + '/ui/' + hash);
  await page.getByLabel('Username', { exact: true }).fill(name);
  await page.getByLabel('Password', { exact: true }).fill('isolated-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
}
async function openStudy(page: Page) {
  await page.getByRole('button', { name: 'Open study Thermal study' }).click();
  await expect(page.getByRole('region', { name: 'Study brief', exact: true })).toBeVisible();
}

test('Home, separate study creation, three study sections and minimal Profile', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page);
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
  await expect(page.getByLabel('New study name')).toHaveCount(0);
  // Active | Archived switch, a bordered Archive per row and one notices link.
  await expect(
    page.getByRole('tablist', { name: 'Study list', exact: true }).getByRole('tab'),
  ).toHaveText(['Active1', 'Trash0']);
  await expect(
    page.getByRole('button', { name: 'Delete study Thermal study', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Third-party software notices' })).toHaveCount(0);
  await page.getByLabel('Filter studies').fill('missing');
  await expect(page.getByText('No studies match these filters.')).toBeVisible();
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('New study name').fill('New investigation');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'New investigation', exact: true })).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Workspace sections' }).getByRole('button'),
  ).toHaveText(['Overview', 'Models', 'Experiments', 'Evidence', 'Documents']);
  await expect(page.getByRole('slider')).toHaveCount(0);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true }).locator('dd')).toHaveText('owner');
  await expect(page.getByRole('combobox', { name: 'Appearance', exact: true })).toHaveValue(
    'dark',
  );
  await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await login(page, '', 'other-user');
  await expect(page.getByText('No studies yet.', { exact: false })).toBeVisible();
  await expect(page.getByText('New investigation', { exact: true })).toHaveCount(0);
  expect(state.unknown).toEqual([]);
});

test('Display alias saves, survives sign-in, guards edits and recovers a stale profile', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true }).locator('dd')).toHaveText('owner');
  const alias = page.getByRole('textbox', { name: 'Display alias', exact: true });
  await alias.fill('Guérric <engineer>');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).not.toBeVisible();
  expect(state.alias).toBe('Guérric <engineer>');
  await expect(page.locator('engineer')).toHaveCount(0);
  await expect(page.getByRole('img', { name: 'Signed in as Guérric <engineer>', exact: true })).toBeVisible();
  for (const appearance of ['light', 'dark']) {
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption(appearance);
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.screenshot({ path: resolve(process.env.HYPRN_MVP_UI_EVIDENCE_ROOT!, 'display-alias-' + appearance + '.png') });
  }
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await alias.fill('Unsaved alias');
  await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(alias).toHaveValue('Guérric <engineer>');
  state.profileFailure = true;
  await alias.fill('Another alias');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Your edits are kept');
  await expect(alias).toHaveValue('Another alias');
  state.profileFailure = false;
  await page.getByRole('button', { name: 'Load latest profile', exact: true }).click();
  await expect(alias).toHaveValue('Guérric <engineer>');
  state.profileLostResponse = true;
  await alias.fill('Accepted but disconnected');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('could not be confirmed');
  state.profileLostResponse = false;
  await page.getByRole('button', { name: 'Load latest profile', exact: true }).click();
  await expect(alias).toHaveValue('Accepted but disconnected');
  await alias.fill('Guérric <engineer>');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).not.toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await login(page);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(alias).toHaveValue('Guérric <engineer>');
  await alias.fill('');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('img', { name: 'Signed in as owner', exact: true })).toBeVisible();
  state.messages = [
    { message_id: 'human', role: 'user', text: 'Read the study.', actor_id: 'owner',
      author_display_name: 'Guérric <engineer>', created_at: 1 },
    { message_id: 'assistant', role: 'assistant', text: 'Study read.', actor_id: null,
      author_display_name: null, created_at: 2 },
  ];
  await openStudy(page);
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  await expect(page.locator('[data-role="user"] > strong')).toHaveText('Guérric <engineer>');
  await expect(page.locator('[data-role="assistant"] > strong')).toHaveText('Assistant');
  await expect(page.locator('engineer')).toHaveCount(0);
  const humanBubble = (await page.locator('[data-role="user"]').boundingBox())!;
  const assistant = (await page.locator('[data-role="assistant"]').boundingBox())!;
  const log = (await page.getByRole('log', { name: 'Study conversation' }).boundingBox())!;
  expect(humanBubble.width).toBeLessThan(log.width - 40);
  expect(humanBubble.height).toBeLessThan(100);
  expect(humanBubble.x).toBeGreaterThan(assistant.x + 40);
  expect(state.unknown).toEqual([]);
});

test('Brief edits preserve the study boundary through keep, discard and save navigation', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page);
  await openStudy(page);
  await page.getByRole('button', { name: 'Edit brief', exact: true }).click();
  await page.getByLabel('Study question', { exact: true }).fill('Local question');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByLabel('Study question', { exact: true })).toHaveValue('Local question');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await openStudy(page);
  await page.getByRole('button', { name: 'Edit brief', exact: true }).click();
  await expect(page.getByLabel('Study question', { exact: true })).toHaveValue('');
  await page.getByLabel('Study question', { exact: true }).fill('Saved question');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByLabel('Study question', { exact: true })).toHaveValue('Saved question');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  expect(state.writes).toHaveLength(1);
  expect(state.writes[0].path).toBe(`/studies/${sid}/brief/draft`);
  expect(state.writes[0].body.content.question).toBe('Saved question');
  expect(state.studies[0].boundary).toBe('Retained boundary must survive');
  expect(state.unknown).toEqual([]);
});

test('Models list, separate creation and exact read-only version navigation', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await openStudy(page);
  await expect(page.getByLabel('New model name')).toHaveCount(0);
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await page.getByRole('button', { name: 'New model', exact: true }).click();
  await page.getByLabel('New model name').fill('Scalar model');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Scalar model', exact: true })).toBeVisible();
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue('draft');
  await page.getByLabel('Model version', { exact: true }).selectOption(version);
  await expect(page).toHaveURL(new RegExp('revision=' + version));
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue(version);
  await expect(page.getByRole('heading', { name: 'Scalar model', exact: true })).toBeVisible();
  // Complete parent ancestry establishes the ordinal independently of list order.
  await expect(page.getByLabel('Model version').locator('option:checked')).toHaveText(
    'Version 1',
  );
  // Export lives under Model actions (resource header actions); the exact read-only version
  // offers its package download ("Download portable model record", formerly "Export exact model package").
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Download portable model record', exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel('Comparison target')).toHaveCount(0);
  await page
    .getByRole('dialog', { name: 'Export model', exact: true })
    .getByRole('button', { name: 'Close', exact: true })
    .click();
  await page.getByRole('button', { name: 'Close Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Return to all models', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Open model Scalar model', exact: true }),
  ).toBeVisible();
  expect(state.writes.map((write) => write.path)).toEqual([`/studies/${sid}/models`]);
  expect(state.unknown).toEqual([]);
});

test('Home invalidates a late study read and authorization loss clears the shell', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page);
  const held = latch();
  state.delayStudy = held;
  await page.getByRole('button', { name: 'Open study Thermal study' }).click();
  await expect(page.getByText('Loading study/model…')).toBeVisible();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  held.release();
  state.delayStudy = null;
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Study brief', exact: true })).toHaveCount(0);
  state.expire = true;
  await page.getByRole('button', { name: 'Open study Thermal study', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Settings', exact: true })).toHaveCount(0);
  expect(state.unknown).toEqual([]);
});

test('Uncertain creation remains recoverable from Home and Profile without duplicate writes', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page);
  state.uncertainCreate = true;
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('New study name').fill('Unknown outcome');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Check original command', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeDisabled();
  await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeEnabled();
  expect(state.writes).toHaveLength(1);
  expect(state.writes[0].body.name).toBe('Unknown outcome');
  expect(state.unknown).toEqual([]);
});

test('Study deep link and compact shell keep records reachable without page overflow', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page, `#v=1&view=overview&study=${sid}`);
  await expect(page.getByRole('region', { name: 'Study brief', exact: true })).toBeVisible();
  const navigation = page.getByRole('navigation', { name: 'Workspace sections' });
  await expect(navigation.getByRole('button', { name: 'Experiments', exact: true })).toBeVisible();
  await expect(navigation.getByRole('button', { name: 'Models', exact: true })).toBeVisible();
  await page.screenshot({
    path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/navigation-desktop.png',
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Home', exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.screenshot({
    path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/navigation-compact.png',
    fullPage: true,
  });
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

for (const theme of ['light', 'dark'] as const) {
  test(`Shared shell preserves navigation, local font and responsive surfaces in ${theme}`, async ({
    page,
  }, testInfo) => {
    const state = await harness(page);
    const remote: string[] = [];
    page.on('request', (request) => {
      if (!request.url().startsWith(origin)) remote.push(request.url());
    });
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
    await login(page);
    await expect(page.getByRole('complementary', { name: 'Workspace navigation' })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
    await expect(page.getByLabel('Home', { exact: true })).toHaveAttribute('aria-current', 'page');
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.fonts.check('400 14px Manrope'))).toBe(true);
    const surfaces = await page.locator('.hf-workspace__canvas').evaluate((canvas) => {
      const panel = document.querySelector('.study-list')!;
      return {
        canvas: getComputedStyle(canvas).backgroundColor,
        panel: getComputedStyle(panel).backgroundColor,
        shadow: getComputedStyle(panel).boxShadow,
      };
    });
    expect(surfaces.canvas).not.toBe(surfaces.panel);
    expect(surfaces.shadow).not.toBe('none');
    await page.screenshot({
      path: testInfo.outputPath(`contour-home-${theme}.png`),
      fullPage: true,
    });
    await openStudy(page);
    const sections = page.getByRole('navigation', { name: 'Workspace sections' });
    await expect(sections.getByRole('button')).toHaveText([
      'Overview',
      'Models',
      'Experiments',
      'Evidence',
      'Documents',
    ]);
    for (const name of ['Models', 'Experiments', 'Overview']) {
      await sections.getByRole('button', { name, exact: true }).click();
      await expect(sections.getByRole('button', { name, exact: true })).toHaveAttribute(
        'aria-current',
        'page',
      );
    }
    await expect(page.getByRole('region', { name: 'Study brief', exact: true })).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`contour-study-${theme}.png`),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(sections.getByRole('button', { name: 'Overview', exact: true })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await sections.getByRole('button', { name: 'Models', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Models', exact: true })).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`contour-narrow-${theme}.png`),
      fullPage: true,
    });
    expect(remote).toEqual([]);
    expect(state.unknown).toEqual([]);
  });
}

test('Appearance is browser-local and Home requires an attached study before chatting', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(
    page.getByRole('combobox', { name: 'Appearance', exact: true }).locator('option'),
  ).toHaveText(['Light', 'Dark']);
  await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption('light');
  await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption('dark');
  const settingsSave = page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Save', exact: true });
  if (await settingsSave.isEnabled()) await settingsSave.click();
  else await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await login(page);
  const opener = page.getByRole('button', { name: 'Open assistant', exact: true });
  await expect(opener).toBeVisible();
  await expect(opener).toHaveText('Assistant');
  const launcherSize = (await opener.boundingBox())!;
  expect(launcherSize.width).toBeGreaterThan(launcherSize.height);
  const canvas = page.locator('.hf-workspace__canvas');
  const expandedCanvas = (await canvas.boundingBox())!;
  await opener.click();
  const assistant = page.getByRole('region', { name: 'Assistant', exact: true });
  const compressedCanvas = (await canvas.boundingBox())!,
    dock = (await assistant.boundingBox())!;
  expect(compressedCanvas.width).toBeLessThan(expandedCanvas.width - 300);
  expect(compressedCanvas.x + compressedCanvas.width).toBeLessThanOrEqual(dock.x);
  await page.getByRole('button', { name: 'Hide assistant', exact: true }).click();
  expect(Math.abs((await canvas.boundingBox())!.width - expandedCanvas.width)).toBeLessThan(1);
  await opener.click();
  await expect(assistant.getByRole('button', { name: 'Start a new study', exact: true })).toBeVisible();
  await expect(assistant.getByRole('button', { name: 'Switch study', exact: true })).toBeVisible();
  await expect(assistant.getByRole('button', { name: 'Send', exact: true })).toHaveCount(0);
  await expect(assistant.getByRole('textbox', { name: 'Message assistant' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(assistant).toBeVisible();
  await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await openStudy(page);
  await expect(assistant).toContainText('Thermal study');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(opener).toHaveCount(0);
  expect(
    await assistant.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return box.left >= 0 && box.right <= innerWidth;
    }),
  ).toBe(true);
  const narrowCanvas = (await canvas.boundingBox())!,
    narrowDock = (await assistant.boundingBox())!;
  expect(narrowDock.y + narrowDock.height).toBeLessThanOrEqual(narrowCanvas.y);
  await assistant.getByRole('button', { name: 'Hide assistant', exact: true }).focus();
  await page.keyboard.press('Escape');
  await expect(assistant).toHaveCount(0);
  await expect(opener).toBeFocused();
  expect(state.writes).toEqual([]);
});

test('Analysis tabs and reload preserve a saved model pin and exclude other versions', async ({
  page,
}) => {
  const state = await harness(page);
  const newer = '30000000-0000-4000-8000-000000000002';
  state.versions.push(newer);
  state.model = {
    schema_version: '1',
    model_id: mid,
    study_id: sid,
    name: 'Cooling model',
    root_instance_id: 'root',
    draft_revision: 'draft-r1',
    definitions: [],
    instances: [],
    ports: [],
    connections: [],
    boundary_mappings: [],
    annotations: [],
    source_files: [],
    required_capabilities: [],
  };
  state.configurations = state.versions.map((v, i) => ({
    configuration: {
      schema_version: '1',
      configuration_revision_id: `40000000-0000-4000-8000-00000000000${i + 1}`,
      model_revision_id: v,
      model_id: mid,
      study_id: sid,
      name: i ? 'Newer inputs' : 'Earlier inputs',
      inputs: [],
      criteria: [],
    },
    model_snapshot: {
      ...state.model,
      model_revision_id: v,
      parent_model_revision_id: null,
      originating_draft_revision: 'draft-r1',
      digest: 'fixture',
    },
  }));
  state.runs = state.configurations.map((c, i) => ({
    run_id: `50000000-0000-4000-8000-00000000000${i + 1}`,
    configuration_revision_id: c.configuration.configuration_revision_id,
    configuration_name: i ? 'Newer run' : 'Earlier run',
    state: 'recorded',
  }));
  await login(page, `#v=1&view=model&study=${sid}&model=${mid}&revision=${version}`);
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue(version);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue(version);
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue(version);
  await expect(page.getByRole('heading', { name: 'Earlier inputs', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Newer inputs', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Model version').locator('option[value="draft"]')).toHaveCount(0);
  await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Inspect run ' + state.runs[0].run_id, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Inspect run ' + state.runs[1].run_id, exact: true }),
  ).toHaveCount(0);
  await page.getByLabel('Model version', { exact: true }).selectOption(newer);
  await expect(
    page.getByRole('button', { name: 'Inspect run ' + state.runs[1].run_id, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Inspect run ' + state.runs[0].run_id, exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill('isolated-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue(newer);
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Newer inputs', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue(newer);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('A draft without a saved version cannot create analyses', async ({ page }) => {
  const state = await harness(page);
  state.versions = [];
  state.model = {
    schema_version: '1',
    model_id: mid,
    study_id: sid,
    name: 'New model',
    root_instance_id: 'root',
    draft_revision: 'draft-r1',
    definitions: [],
    instances: [],
    ports: [],
    connections: [],
    boundary_mappings: [],
    annotations: [],
    source_files: [],
    required_capabilities: [],
  };
  await login(page, `#v=1&view=model&study=${sid}&model=${mid}`);
  await expect(page.getByLabel('Model version', { exact: true })).toHaveValue('draft');
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await expect(
    page.getByText('Save a model version to prepare analyses.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'New analysis', exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New configuration', exact: true })).toBeDisabled();
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Analysis lists load bounded pages and overview never fetches run history', async ({
  page,
}) => {
  const state = await harness(page);
  state.model = {
    schema_version: '1',
    model_id: mid,
    study_id: sid,
    name: 'Cooling model',
    root_instance_id: 'root',
    draft_revision: 'draft-r1',
    definitions: [],
    instances: [],
    ports: [],
    connections: [],
    boundary_mappings: [],
    annotations: [],
    source_files: [],
    required_capabilities: [],
  };
  state.configurations = Array.from({ length: 51 }, (_, i) => ({
    configuration: {
      configuration_revision_id: `40000000-0000-4000-8000-${String(i).padStart(12, '0')}`,
      configuration_id: `60000000-0000-4000-8000-${String(i).padStart(12, '0')}`,
      model_id: mid,
      model_revision_id: version,
      name: `Inputs ${i}`,
      inputs: [],
    },
  }));
  await login(page);
  await openStudy(page);
  expect(state.reads.some((url) => new URL(url).pathname.endsWith('/runs'))).toBe(false);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  // The area opens on its calculations; configurations are one tab away.
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inputs 49', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Configurations', exact: true })).toHaveCount(0);
  const scope = page.getByRole('region', { name: 'Experiments navigation', exact: true });
  await expect(scope.getByText('Model', { exact: true })).toBeVisible();
  await expect(scope.getByText('Model version', { exact: true })).toBeVisible();
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const tabs = (await page
      .getByRole('tablist', { name: 'Experiments', exact: true })
      .boundingBox())!;
    const create = (await page
      .getByRole('button', { name: 'New configuration', exact: true })
      .boundingBox())!;
    expect(create.y).toBeGreaterThan(tabs.y + tabs.height + 8);
    expect(create.x).toBeGreaterThanOrEqual(0);
    expect(create.x + create.width).toBeLessThanOrEqual(width);
  }

  await expect(page.getByRole('heading', { name: 'Inputs 50', exact: true })).toHaveCount(0);
  expect(
    state.reads.filter((url) => new URL(url).pathname.endsWith('/configuration-summaries')),
  ).toHaveLength(1);
  expect(state.reads.some((url) => new URL(url).pathname.endsWith('/configurations'))).toBe(false);
  expect(state.reads.some((url) => new URL(url).pathname.endsWith('/runs'))).toBe(false);
  await expect(
    page.getByText('50 configuration versions shown · More available', { exact: true }),
  ).toBeVisible();
  state.failConfigurationPage = true;
  await page.getByRole('button', { name: 'Load more configuration versions', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inputs 49', exact: true })).toBeVisible();
  await page
    .getByRole('button', { name: 'Retry loading more configuration versions', exact: true })
    .click();
  await expect(page.getByText('51 configuration versions', { exact: true })).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Inputs 50', exact: true })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Load more configuration versions', exact: true }),
  ).toHaveCount(0);
  expect(
    state.reads.filter((url) => new URL(url).pathname.endsWith('/configuration-summaries')),
  ).toHaveLength(3);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

// Transport fixtures isolate reading geometry; source validation has its own API suite.
test('Referenced evidence reads inline with bounded library and editor geometry', async ({
  page,
}) => {
  const state = await harness(page);
  const record = {
    schema_version: '1',
    study_id: sid,
    evidence_id: 'geometry-family',
    evidence_version_id: 'geometry-source',
    title: 'Measured range',
    content: 'Measured range only.',
    source_refs: ['Laboratory notebook, p. 7'],
    resource_scope: { scope_version: '1', study_id: sid, kind: 'study' },
  };
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/evidence`,
    (route) => route.fulfill({ json: { schema_version: '1', data: [record], next_cursor: null } }),
  );
  state.brief = { schema_version: '1', revision: 'brief-r1', content: {
    schema_version: '1', question: 'Is the measured range suitable?', original_question: null,
    elaboration: null, scope: '', alternatives: [], criteria: [], limits: [], open_questions: [],
    assumptions: [{ assumption_id: '40000000-0000-4000-8000-000000000001',
      statement: 'The measured range applies.', evidence_links: [
        { evidence_version_id: record.evidence_version_id, relation: 'supports' },
      ] }],
  } };
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/evidence/${record.evidence_version_id}`,
    (route) => route.fulfill({json: {schema_version: '1', data: record}}),
  );
  await login(page, `#v=1&study=${sid}&view=evidence`);
  for (const width of [1440, 720]) {
    await page.setViewportSize({ width, height: 1000 });
    const source = page.getByRole('region', { name: 'Evidence library', exact: true });
    const detail = source.locator('.evidence-record');
    await expect(detail.getByRole('heading', {name: record.title, exact: true})).toBeVisible();
    await expect(detail).toContainText(record.content);
    const before = (await detail.boundingBox())!;
    expect(before.height).toBeLessThanOrEqual(1000);
    expect(before.width).toBeGreaterThan(300);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    for (const theme of ['light', 'dark']) {
      await page.evaluate((value) => (document.documentElement.dataset.theme = value), theme);
      await page.screenshot({
        path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/source-${width}-${theme}.png`,
      });
    }
    await source.getByRole('button', { name: 'Edit', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Edit evidence', exact: true });
    await expect(dialog).toBeVisible();
    expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(width);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(source.getByRole('button', { name: 'Edit', exact: true })).toBeFocused();
  }
  expect(state.unknown).toEqual([]);
});

test('Grouped sidebar preserves routes and honest placeholders when collapsed', async ({
  page,
}) => {
  const state = await harness(page);
  state.studies[0].name = 'Hypersonic fuel comparison';
  await login(page, `#v=1&study=${sid}&view=overview`);
  const rail = page.getByRole('complementary', { name: 'Workspace navigation' });
  await expect(
    rail.getByRole('navigation', { name: 'Workspace sections', exact: true }),
  ).toBeVisible();
  await expect(rail.getByText('Library', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Edit brief', exact: true }).click();
  await page.getByLabel('Study question', { exact: true }).fill('Keep this local edit');
  await rail.getByRole('button', { name: 'Documents', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByLabel('Study question', { exact: true })).toHaveValue(
    'Keep this local edit',
  );
  await rail.getByRole('button', { name: 'Documents', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await rail.getByRole('button', { name: 'Overview', exact: true }).click();
  const before = await page.locator('.hf-workspace__canvas').boundingBox();
  await rail.getByRole('button', { name: 'Collapse menu', exact: true }).click();
  expect((await page.locator('.hf-workspace__canvas').boundingBox())!.width).toBeGreaterThan(
    before!.width,
  );
  await expect(rail).toHaveAttribute('data-collapsed', 'true');
  const placeholderReads = state.reads.length;
  await rail.getByRole('button', { name: 'Documents', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Documents', exact: true })).toContainText(
    'This functionality is not implemented yet.',
  );
  expect(
    state.reads.slice(placeholderReads).some((url) => /\/models|\/configurations|\/runs/.test(url)),
  ).toBe(false);
  await expect(rail.getByRole('button', { name: 'Documents', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await page.reload();
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill('isolated-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Documents', exact: true })).toBeVisible();
  await expect(rail).toHaveAttribute('data-collapsed', 'true');
  await rail.getByRole('button', { name: 'Help', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Help', exact: true })).toContainText(
    'This functionality is not implemented yet.',
  );
  await rail.getByRole('button', { name: 'Expand menu', exact: true }).click();
  await rail.getByRole('button', { name: 'Evidence', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible();
  await expect(rail.getByRole('button', { name: 'Evidence', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await page.setViewportSize({ width: 1440, height: 703 });
  expect(await rail.evaluate((el) => el.scrollHeight <= el.clientHeight)).toBe(true);
  for (const width of [1440, 720, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const mode of ['expanded', 'collapsed']) {
      if (mode === 'collapsed') {
        await rail.getByRole('button', { name: 'Collapse menu', exact: true }).click();
        expect(
          (await rail.locator('.hf-navigation__location').boundingBox())!.height,
        ).toBeLessThanOrEqual(48);
      }
      for (const theme of ['light', 'dark']) {
        await page.evaluate((theme) => (document.documentElement.dataset.theme = theme), theme);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        );
        await page.screenshot({
          path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/sidebar-${width}-${mode}-${theme}.png`,
        });
      }
    }
    await rail.getByRole('button', { name: 'Expand menu', exact: true }).click();
  }
  await rail.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toHaveCount(1);
  expect(state.writes).toEqual([]);
});

test('Home always returns to Studies from Settings and Help, with a distinct Overview icon', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page, `#v=1&study=${sid}&view=overview`);
  const home = page.getByRole('button', { name: 'Home', exact: true });
  const homePath = await home.locator('svg path').getAttribute('d');
  expect(
    await page
      .getByRole('button', { name: 'Overview', exact: true })
      .locator('svg path')
      .getAttribute('d'),
  ).not.toBe(homePath);
  for (const destination of ['Settings', 'Help']) {
    await page.getByRole('button', { name: destination, exact: true }).click();
    if (destination === 'Settings') {
      expect(new URL(page.url()).hash).toContain('study=' + sid);
      await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
    }
    await home.click();
    await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
    await expect(home).toHaveCount(0);
    await expect(page.getByLabel('Home', { exact: true })).toHaveAttribute('aria-current', 'page');
    expect(new URL(page.url()).hash).toBe('#home');
    await page.getByRole('button', { name: 'Open study Thermal study', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'Collapse menu', exact: true }).click();
  await expect(page.getByLabel('Home', { exact: true })).toHaveAttribute('aria-current', 'page');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(home).toHaveCount(0);
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  expect(await home.locator('svg path').getAttribute('d')).toBe(homePath);
  await home.click();
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Theme-aware brand and full-width verified Python preserve source and control geometry', async ({
  page,
}) => {
  const state = await harness(page);
  state.model = modelFixture();
  await login(page, `#v=1&study=${sid}&view=model&model=${mid}&revision=${version}`);
  await page
    .getByRole('region', { name: 'Directed component diagram', exact: true })
    .locator('[data-instance="a"]')
    .click();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  const code = page.getByLabel('Read-only authored source', { exact: true });
  await expect(code).toHaveText(source);
  const before = JSON.stringify(state.model.source_files);
  for (const width of [1440, 720]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['light', 'dark']) {
      await page.evaluate((theme) => (document.documentElement.dataset.theme = theme), theme);
      const bounds = await code.evaluate((el) => ({
        code: el.getBoundingClientRect().toJSON(),
        parent: el.parentElement!.getBoundingClientRect().toJSON(),
        text: getComputedStyle(el).textAlign,
      }));
      expect(bounds.code.x).toBe(bounds.parent.x);
      expect(bounds.code.width).toBe(bounds.parent.width);
      expect(bounds.text).toBe('start');
      const logo = page.getByRole('img', { name: 'HYPRN', exact: true });
      await expect(logo).toBeVisible();
      expect(await logo.evaluate((el) => getComputedStyle(el).color)).toBe(
        theme === 'light' ? 'rgb(17, 24, 32)' : 'rgb(232, 237, 242)',
      );
      expect(await logo.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(
        'rgba(0, 0, 0, 0)',
      );
      const control = page.getByRole('combobox', { name: 'Model version', exact: true });
      expect(
        await control.evaluate((el) => {
          const c = getComputedStyle(el);
          return (
            (parseFloat(c.lineHeight) || parseFloat(c.fontSize) * 1.2) +
              parseFloat(c.paddingTop) +
              parseFloat(c.paddingBottom) +
              2 <=
            el.getBoundingClientRect().height
          );
        }),
      ).toBe(true);
      await page.screenshot({
        path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/brand-python-${width}-${theme}.png`,
      });
    }
  }
  expect(JSON.stringify(state.model.source_files)).toBe(before);
  expect(state.writes).toEqual([]);
});

test('Study cards keep opening links and archive commands compact beside their content', async ({
  page,
}) => {
  const state = await harness(page);
  await login(page);
  const card = page.locator('.study-row').filter({ hasText: 'Thermal study' });
  const open = card.getByRole('button', { name: 'Open study Thermal study', exact: true });
  const archive = card.getByRole('button', { name: 'Delete study Thermal study', exact: true });
  for (const theme of ['light', 'dark']) {
    await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
    await page.setViewportSize({ width: 1440, height: 1000 });
    const title = (await card
      .getByRole('heading', { name: 'Thermal study', exact: true })
      .boundingBox())!;
    const a = (await open.boundingBox())!,
      b = (await archive.boundingBox())!;
    expect(a.x).toBeGreaterThan(title.x);
    const row = (await card.boundingBox())!;
    expect(Math.abs((a.y + b.y + b.height) / 2 - (row.y + row.height / 2))).toBeLessThanOrEqual(1);
    await expect(open).toHaveText('Open');
    await expect(open.locator('svg')).toHaveCount(1);
    expect(await open.locator('.hf-open-link__label').evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe('underline');
    await expect(archive).toHaveText('Delete');
    expect(Math.abs(b.y + b.height / 2 - a.y - a.height / 2)).toBeLessThanOrEqual(1);
    expect(b.x - a.x - a.width).toBeGreaterThanOrEqual(8);
    expect(await archive.evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe('none');
    await page.screenshot({
      path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/study-actions-${theme}.png`,
    });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await archive.click();
  await expect(page.getByRole('dialog', { name: 'Delete study', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close Delete study', exact: true }).click();
  expect(state.writes).toEqual([]);
});

test('Content navigation shares arrows while commands, sidebar and tabs retain their roles', async ({ page }) => {
  const state = await harness(page);
  state.model = modelFixture();
  await login(page, `#v=1&study=${sid}&view=model&model=${mid}&revision=${version}`);
  const details = page.getByRole('button', { name: 'Model record details', exact: true });
  const back = page.getByRole('button', { name: 'Return to all models', exact: true });
  for (const theme of ['light', 'dark']) {
    await page.evaluate((value) => (document.documentElement.dataset.theme = value), theme);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await expect(details.locator('svg path')).toHaveAttribute('d', 'M6 18 18 6M6 6h12v12');
      await expect(back.locator('svg path')).toHaveAttribute('d', 'M20 12H4m7-7-7 7 7 7');
      expect(await details.locator('.hf-open-link__label').evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe('underline');
      await expect(page.locator('.hf-navigation .hf-open-link, [role="tab"] .hf-open-link')).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await details.focus();
      await page.keyboard.press('Enter');
      const reader = page.getByRole('dialog', { name: 'Model version record', exact: true });
      await expect(reader).toBeVisible();
      await expect(reader).toContainText(version);
      const done = reader.getByRole('button', { name: 'Done', exact: true });
      expect(await done.evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe('none');
      await expect(done.locator('svg')).toHaveCount(0);
      await page.keyboard.press('Escape');
      await expect(reader).not.toBeVisible();
      await expect(details).toBeFocused();
      await page.screenshot({ path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/navigation-affordances-${theme}-${width}.png` });
    }
  }
  await back.click();
  const open = page.getByRole('button', { name: 'Open model Connected thermal model', exact: true });
  await expect(open.locator('svg')).toHaveCount(1);
  await open.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Connected thermal model', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Third-party software notices', exact: true })).toHaveCount(0);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Menu and right-side panels use the same reversible directional toggle', async ({ page }) => {
  await harness(page);
  await login(page, `#v=1&study=${sid}&view=overview`);
  const collapse = page.getByRole('button', { name: 'Collapse menu', exact: true });
  const left = await collapse.locator('svg path').getAttribute('d');
  await collapse.click();
  const expand = page.getByRole('button', { name: 'Expand menu', exact: true });
  const right = await expand.locator('svg path').getAttribute('d');
  expect(right).not.toBe(left);
  await expand.click();
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  const full = page.getByRole('button', { name: 'Expand to full width', exact: true });
  expect(await full.locator('svg path').getAttribute('d')).toBe(left);
  await full.click();
  const restore = page.getByRole('button', { name: 'Exit full screen', exact: true });
  expect(await restore.locator('svg path').getAttribute('d')).toBe(right);
  await restore.click();
  await page.getByRole('button', { name: 'Hide assistant', exact: true }).click();
});

test('Run pagination preserves prior rows and retries the exact cursor', async ({ page }) => {
  const state = await harness(page);
  state.model = { ...modelFixture(), model_id: mid, study_id: sid };
  const configurationId = '40000000-0000-4000-8000-000000000001';
  state.configurations = [
    {
      configuration: {
        configuration_revision_id: configurationId,
        model_id: mid,
        model_revision_id: version,
        inputs: [],
      },
    },
  ];
  state.runs = Array.from({ length: 23 }, (_, index) => ({
    run_id: '50000000-0000-4000-8000-' + String(index + 1).padStart(12, '0'),
    configuration_revision_id: configurationId,
    configuration_name: index === 22 ? 'Late match' : 'Cooling case ' + (index + 1),
    state: 'recorded',
  }));
  await login(page, `#v=1&view=model&study=${sid}&model=${mid}&revision=${version}`);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  const history = page.getByRole('region', { name: 'Run history', exact: true });
  await expect(history.getByText('20 runs shown · More available', { exact: true })).toBeVisible();
  for (const width of [1440, 390])
    for (const theme of ['light', 'dark']) {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate((value) => (document.documentElement.dataset.theme = value), theme);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await history.locator('.hf-collection-status').scrollIntoViewIfNeeded();
      await page.screenshot({
        path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/collection-partial-${width}-${theme}.png`,
      });
    }
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.getByLabel('Filter runs', { exact: true }).fill('Late match');
  await expect(
    history.getByText('No matches in the runs shown. Load more runs or clear the filters.', {
      exact: true,
    }),
  ).toBeVisible();
  state.failRunPage = true;
  await history.getByRole('button', { name: 'Load more runs', exact: true }).click();
  await expect(
    history.getByText('0 matches in 20 runs shown · More available', { exact: true }),
  ).toBeVisible();
  await history.getByRole('button', { name: 'Retry loading more runs', exact: true }).click();
  await expect(history.getByText('1 match in 23 runs', { exact: true })).toBeVisible();
  await expect(history.getByRole('button', { name: 'Load more runs', exact: true })).toHaveCount(0);
  await page.getByLabel('Filter runs', { exact: true }).fill('');
  await expect(history.getByRole('button', { name: /^Inspect run / })).toHaveCount(23);
  await page.evaluate(() => (document.documentElement.dataset.theme = 'light'));
  await history.locator('.hf-collection-status').scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/collection-complete-1440-light.png`,
  });

  const cursors = state.reads
    .filter((url) => new URL(url).pathname.endsWith('/runs'))
    .map((url) => new URL(url).searchParams.get('cursor'));
  expect(cursors).toEqual([null, state.runs[19].run_id, state.runs[19].run_id]);
  expect(state.unknown).toEqual([]);
});

test('Analysis collections follow version cursors and automatically load member run history', async ({ page }) => {
  const state = await harness(page);
  state.model = modelFixture();
  const configId = 'configuration-page-fixture',
    analysisId = 'analysis-page-fixture',
    versionId = 'analysis-version-new';
  const content = {
    schema_version: '2',
    name: 'Cooling cases',
    description: '',
    model_id: mid,
    model_revision_id: version,
    configuration_revision_ids: [configId],
    design: { kind: 'hand_picked' },
    brief_version_id: null,
    criterion_bindings: [],
  };
  const saved = {
    schema_version: '2',
    calculation_id: analysisId,
    calculation_version_id: versionId,
    version_number: 2,
    content,
  };
  const older = { ...saved, calculation_version_id: 'analysis-version-old', version_number: 1 };
  state.configurations = [
    {
      configuration: {
        configuration_revision_id: configId,
        model_id: mid,
        model_revision_id: version,
        name: 'Cooling inputs',
        inputs: [],
      },
      model_snapshot: { ...state.model, model_revision_id: version },
    },
  ];
  const requests: string[] = [];
  let fail = true;
  await page.route(
    (url) => url.pathname.startsWith(`/api/1/studies/${sid}/analys`),
    async (route) => {
      const url = new URL(route.request().url());
      requests.push(url.pathname + url.search);
      const ok = (data: unknown) => route.fulfill({ json: { schema_version: '1', data } });
      if (url.pathname.endsWith('/analyses'))
        return ok({
          items: url.searchParams.has('after')
            ? [
                {
                  calculation_id: 'second-analysis',
                  latest_version: { ...saved, content: { ...content, name: 'Second analysis' } },
                },
              ]
            : [{ calculation_id: analysisId, latest_version: saved }],
          next_cursor: url.searchParams.has('after') ? null : 0,
        });
      if (url.pathname.endsWith('/versions')) {
        if (url.searchParams.has('before') && fail) {
          fail = false;
          return route.fulfill({
            status: 503,
            json: {
              error: {
                code: 'internal_error',
                message: 'Temporary history failure',
                fields: [],
                outcome: 'unchanged',
              },
            },
          });
        }
        return ok({
          items: url.searchParams.has('before') ? [older] : [saved],
          next_cursor: url.searchParams.has('before') ? null : 0,
        });
      }
      if (url.pathname.endsWith('/estimates')) {
        const id = url.searchParams.has('cursor') ? 'estimate-two' : 'estimate-one';
        return ok({
          items: [
            {
              schema_version: '1',
              estimate_id: id,
              calculation_id: analysisId,
              calculation_version_id: versionId,
              state: 'failed',
              reason: 'Illustrative fixture',
              samples: [],
              groups: [],
              completed_groups: 0,
              total_groups: 0,
              request: { tolerances: [] },
            },
          ],
          next_cursor: url.searchParams.has('cursor') ? null : 'estimate-page-two',
        });
      }
      if (url.pathname.endsWith('/runs'))
        return ok({
          items: [
            {
              run_id: url.searchParams.has('after') ? 'run-two' : 'run-one',
              configuration_revision_id: configId,
              record_state: 'recorded',
              evaluations: [],
            },
          ],
          next_cursor: url.searchParams.has('after') ? null : 0,
        });
      if (url.pathname.endsWith('/' + versionId)) return ok(saved);
      if (url.pathname.endsWith('/' + older.calculation_version_id)) return ok(older);
      if (url.pathname.endsWith('/execution')) return ok(null);
      throw new Error('Unexpected analysis request ' + url);
    },
  );
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/configurations/${configId}`,
    (route) => route.fulfill({ json: { schema_version: '1', data: state.configurations[0] } }),
  );
  await page.route((url) => /\/runs\/run-(one|two)$/.test(url.pathname), (route) => route.fulfill({
    json: { schema_version: '1', data: {
      run_id: new URL(route.request().url()).pathname.split('/').pop(), command_id: 'command-fixture',
      state: 'accepted_run', receipt_url: '/receipt-fixture', process_state: 'running',
    } },
  }));
  await login(page, `#v=1&study=${sid}&view=model&model=${mid}&revision=${version}`);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await expect(page.getByText('1 analysis shown · More available', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Load more analyses', exact: true }).click();
  await expect(page.getByText('2 analyses', { exact: true })).toBeVisible();
  await page
    .getByRole('article')
    .filter({ has: page.getByRole('heading', { name: 'Cooling cases', exact: true }) })
    .getByRole('button', { name: 'Open analysis', exact: true })
    .click();
  await page.getByRole('button', { name: 'Load more analysis versions', exact: true }).click();
  await page
    .getByRole('button', { name: 'Retry loading more analysis versions', exact: true })
    .click();
  await expect(page.getByLabel('Analysis version', { exact: true }).locator('option')).toHaveCount(
    2,
  );
  await expect(page.getByLabel('Analysis version', { exact: true })).toHaveValue(versionId);
  await expect(page.getByRole('button', { name: 'Load more runs', exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Surrogate', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Cooling inputs displayed run').locator('option')).toHaveCount(2);
  const runLink = page.getByRole('button', { name: 'Open run · Cooling inputs · Running', exact: true });
  await expect(runLink.locator('svg')).toHaveCount(1);
  await expect(runLink.locator('.hf-tag')).toHaveCount(0);
  await expect(runLink.locator('..').getByText('Running', { exact: true })).toBeVisible();
  expect(requests.filter((url) => url.includes('before=0'))).toHaveLength(2);
  expect(requests.some((url) => url.includes('after=0'))).toBe(true);
  expect(state.unknown).toEqual([]);
});

test('Initial failure and stale model replies never claim a complete list', async ({ page }) => {
  const state = await harness(page);
  state.model = modelFixture();
  const newer = '30000000-0000-4000-8000-000000000002';
  state.versions.push(newer);
  let fail = true;
  const held = latch(),
    requested = latch(),
    completed = latch();
  const requests: string[] = [];
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/runs`,
    async (route) => {
      const url = new URL(route.request().url());
      const revision = url.searchParams.get('model_revision_id');
      requests.push(url.search);
      if (fail) {
        fail = false;
        return route.fulfill({
          status: 503,
          json: {
            error: {
              code: 'internal_error',
              message: 'Read interrupted',
              fields: [],
              outcome: 'unchanged',
            },
          },
        });
      }
      if (url.searchParams.has('cursor')) {
        requested.release();
        await held.promise;
      }
      const row = {
        run_id: revision === newer ? 'new-scope-run' : 'old-scope-run',
        configuration_revision_id: 'inputs',
        configuration_name: 'Scope case',
        state: 'recorded',
      };
      await route.fulfill({
        json: {
          schema_version: '1',
          data: [row],
          next_cursor: revision === newer ? null : 'old-page-two',
        },
      });
      if (url.searchParams.has('cursor')) completed.release();
    },
  );
  await login(page, `#v=1&study=${sid}&view=model&model=${mid}&revision=${version}`);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  await expect(page.getByText('Runs could not be loaded.', { exact: true })).toBeVisible();
  await expect(page.getByText('No runs yet.', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Retry loading runs', exact: true }).click();
  await expect(page.getByText('1 run shown · More available', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Load more runs', exact: true }).click();
  await requested.promise;
  await page.getByLabel('Model version', { exact: true }).selectOption(newer);
  await expect(
    page.getByRole('button', { name: 'Inspect run new-scope-run', exact: true }),
  ).toBeVisible();
  held.release();
  await completed.promise;
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())));
  await expect(
    page.getByRole('button', { name: 'Inspect run old-scope-run', exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText('1 run', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load more runs', exact: true })).toHaveCount(0);
  expect(requests).toHaveLength(4);
  expect(state.unknown).toEqual([]);
});


test('Assistant distinguishes a confirmed budget refusal from uncertain delivery', async ({page}) => {
  const state = await harness(page);
  await login(page);
  await openStudy(page);
  await page.getByRole('button', {name: 'Open assistant', exact: true}).click();
  const composer = page.getByRole('textbox', {name: 'Message assistant'});
  await composer.fill('Read my study.');
  await page.getByRole('button', {name: 'Send', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('budget is fully reserved');
  await expect(page.getByRole('alert')).toContainText('No message was sent');
  await expect(composer).toBeEnabled();
  await expect(composer).toHaveValue('Read my study.');
  await expect(page.getByRole('button', {name: 'Retry send', exact: true})).toHaveCount(0);
  state.assistantFailure = 'unknown';
  await composer.fill('Read the amended question.');
  await page.getByRole('button', {name: 'Send', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('Could not confirm delivery');
  await expect(composer).toBeDisabled();
  await page.getByRole('button', {name: 'Retry send', exact: true}).click();
  await expect.poll(() => state.assistantSends.length).toBe(3);
  expect(state.assistantSends[1]).toEqual(state.assistantSends[2]);
  expect(state.assistantSends[0].command_id).not.toBe(state.assistantSends[1].command_id);
  expect(state.unknown).toEqual([]);
});


test('Assistant Enter sends once, Shift Enter adds a line, and Home forms stay grouped', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await openStudy(page);
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Assistant', exact: true });
  const input = panel.getByRole('textbox', { name: 'Message assistant' });
  await expect(panel.getByText(/Spending ·/)).toHaveCount(0);
  await input.fill('Short message');
  await input.press('Shift+Enter');
  await expect(input).toHaveValue('Short message\n');
  expect(state.assistantSends).toHaveLength(0);
  await expect(panel.getByRole('button', { name: 'Send', exact: true })).toBeEnabled();
  await input.press('Enter');
  await expect.poll(() => state.assistantSends.length).toBe(1);
  await expect(panel.getByRole('alert')).toContainText('No message was sent');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await panel.getByRole('button', { name: 'Start a new study', exact: true }).click();
  await expect(panel.getByRole('textbox', { name: 'Study name', exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Switch study', exact: true })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Cancel', exact: true }).click();
  await panel.getByRole('button', { name: 'Switch study', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Open study', exact: true })).toBeDisabled();
  await panel.getByRole('combobox', { name: 'Study', exact: true }).selectOption(sid);
  await expect(panel.getByRole('button', { name: 'Open study', exact: true })).toBeEnabled();
  await panel.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect(state.unknown).toEqual([]);
});


test('Assistant forms replace history and save the question before autonomous work', async ({ page }) => {
  const state = await harness(page);
  state.messages = [{ message_id: 'old', role: 'assistant', text: 'Earlier conversation.', created_at: 1 }];
  await login(page); await openStudy(page);
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  await expect(page.getByRole('log')).toContainText('Earlier conversation.');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Assistant', exact: true });
  await panel.getByRole('button', { name: 'Switch study', exact: true }).click();
  await expect(panel.getByRole('log')).toHaveCount(0);
  await expect(panel.getByRole('textbox', { name: 'Message assistant' })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(panel.getByRole('log')).toContainText('Earlier conversation.');
  await panel.getByRole('button', { name: 'Start a new study', exact: true }).click();
  await expect(panel.getByRole('log')).toHaveCount(0);
  await panel.getByRole('textbox', { name: 'Study name', exact: true }).fill('New engineering question');
  await panel.getByRole('textbox', { name: 'Study question', exact: true }).fill('Can the proposed system meet its requirement?');
  const toggle = panel.getByRole('switch', { name: 'Autonomous agent', exact: true });
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
  state.assistantFailure = 'unknown';
  await panel.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('The study is saved.');
  expect(state.brief.content.original_question).toEqual({ text: 'Can the proposed system meet its requirement?', attribution: { kind: 'human', label: null } });
  expect(state.assistantSends).toHaveLength(1);
  const command = state.assistantSends[0];
  state.assistantFailure = 'none';
  await panel.getByRole('button', { name: 'Continue setup', exact: true }).click();
  await expect(panel.getByRole('textbox', { name: 'Study question', exact: true })).toHaveCount(0);
  expect(state.assistantSends).toEqual([command, command]);
  expect(state.studies.filter(s => s.name === 'New engineering question')).toHaveLength(1);
  expect(state.unknown).toEqual([]);
});

test('Assistant renders structured messages safely in light and narrow layouts', async ({ page }) => {
  const state = await harness(page);
  state.messages = [{ message_id: 'structured', role: 'assistant', created_at: 1,
    text: '## Findings\n\nThe **result** is conditional.\n\n1. Check inputs.\n2. Confirm limits.\n\n| Quantity | Result |\n| --- | --- |\n| Rise | 9.5 K |\n\n`safe_code` <script>alert(1)</script> [unsafe](javascript:alert)\n\n```python\ny = x + 1\n```' }];
  await login(page); await openStudy(page);
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  const log = page.getByRole('log');
  await expect(log.getByRole('heading', { name: 'Findings' })).toBeVisible();
  await expect(log.locator('strong').filter({ hasText: 'result' })).toBeVisible();
  await expect(log.getByRole('table')).toContainText('9.5 K');
  await expect(log.locator('ol > li')).toHaveCount(2);
  await expect(log.locator('script, a[href^="javascript:"]')).toHaveCount(0);
  await expect(log).toContainText('<script>alert(1)</script>');
  await page.evaluate(() => (document.documentElement.dataset.theme = 'light'));
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(log.getByRole('table')).toBeVisible();
  expect(await log.evaluate(e => e.getBoundingClientRect().right <= innerWidth)).toBe(true);
  expect(state.unknown).toEqual([]);
});

test('Manual study start saves the question without sending an Assistant message', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Assistant', exact: true });
  await panel.getByRole('button', { name: 'Start a new study', exact: true }).click();
  await panel.getByRole('textbox', { name: 'Study name', exact: true }).fill('Manual investigation');
  await panel.getByRole('textbox', { name: 'Study question', exact: true }).fill('Which assumptions need to be established?');
  await expect(panel.getByRole('switch', { name: 'Autonomous agent' })).toHaveAttribute('aria-checked', 'false');
  await panel.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(panel.getByRole('textbox', { name: 'Message assistant' })).toBeVisible();
  expect(state.brief.content.question).toBe('Which assumptions need to be established?');
  expect(state.brief.content.original_question.text).toBe(state.brief.content.question);
  await expect(page.getByRole('region', { name: 'Study brief', exact: true })
    .getByText(/Original wording/)).toHaveCount(0);
  expect(state.assistantSends).toEqual([]);
  expect(state.unknown).toEqual([]);
});


test('Assistant progress cards reflect the backend stages in light and narrow layouts', async ({ page }) => {
  const state = await harness(page);
  state.assistantStage = 'queued';
  await login(page);
  await openStudy(page);
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Assistant', exact: true });
  await expect(panel.getByRole('status')).toContainText('Queued');
  await expect(panel.getByRole('status')).not.toContainText('Working');
  for (const [stage, label] of [['starting', 'Starting'], ['running', 'Working'],
    ['waiting', 'Waiting for calculations'], ['stopping', 'Stopping']]) {
    state.assistantStage = stage;
    await expect(panel.getByRole('status')).toContainText(label);
  }
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  await page.setViewportSize({ width: 720, height: 900 });
  await expect(panel.getByRole('status')).toBeVisible();
  expect(await panel.getByRole('status').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  expect(state.unknown).toEqual([]);
});
