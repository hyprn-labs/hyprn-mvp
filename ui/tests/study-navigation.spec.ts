import { test, expect, type Page } from 'playwright/test';
import { createServer, type Server } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import type { ModelDraft, Study } from '../src/contract';
import { unitCatalog } from './foundry-fixtures';

// Isolated shell/state regression only. Every API request is a controlled fixture;
// this must never contact the live application or claim real API acceptance.
// The build location is refused unless it is a fresh isolated build: foundry-fixtures (imported
// above) applies that guard when it loads, before any test runs.
const build = process.env.HYPRN_MVP_NAV_BUILD;
test.skip(!build, 'Isolated fixture suite requires HYPRN_MVP_NAV_BUILD; real served acceptance uses the other suites.');
let server: Server, origin: string;
test.beforeAll(async () => {
  server = createServer(async (request, response) => {
    response.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'");
    const path = new URL(request.url!, 'http://localhost').pathname;
    const file = resolve(build!, path === '/ui/' ? 'index.html' : path.replace(/^\/ui\//, ''));
    if (!path.startsWith('/ui/') || !file.startsWith(resolve(build!) + sep)) { response.writeHead(404).end(); return; }
    try {
      const bytes = await readFile(file);
      const mime = file.endsWith('.js') ? 'text/javascript'
        : file.endsWith('.css') ? 'text/css' : file.endsWith('.ttf') ? 'font/ttf' : 'text/html';
      response.setHeader('Content-Type', mime);
      response.end(bytes);
    }
    catch { response.writeHead(404).end(); }
  });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address(); if (!address || typeof address === 'string') throw new Error('Isolated server unavailable');
  origin = `http://127.0.0.1:${address.port}`;
});
test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort('blockedbyclient'));
});
test.afterAll(async () => { if (server?.listening) await new Promise<void>((done, reject) => server.close(error => error ? reject(error) : done())); });

const sid = '10000000-0000-4000-8000-000000000001';
const sid2 = '10000000-0000-4000-8000-000000000002';
const mid = '20000000-0000-4000-8000-000000000001';
const version = '30000000-0000-4000-8000-000000000001';
function latch() { let release!: () => void; const promise = new Promise<void>(resolve => { release = resolve; }); return { promise, release }; }
async function harness(page: Page) {
  const state = {
    studies: [{ study_id: sid, revision: 'study-r1', name: 'Thermal study', description: 'A retained description', boundary: 'Retained boundary must survive' }] as Study[],
    model: null as ModelDraft | null,
    writes: [] as Array<{ path: string; method: string; body: any }>,
    unknown: [] as string[],
    delayStudy: null as ReturnType<typeof latch> | null,
    uncertainCreate: false,
    expire: false,
    actor: 'owner',
  };
  await page.route('**/api/1/**', async route => {
    if (new URL(route.request().url()).origin !== origin) return route.abort('blockedbyclient');
    const request = route.request(), path = new URL(request.url()).pathname.slice('/api/1'.length), method = request.method();
    const body = method === 'GET' ? undefined : request.postDataJSON();
    const ok = (data: unknown) => route.fulfill({ json: { schema_version: '1', data, next_cursor: null } });
    if (path === '/session') { if (method === 'POST') state.actor = body.username; return ok({ actor_id: state.actor, csrf_token: 'isolated-fixture-token' }); }
    // The study shell's attribution reads: no record in these studies was written by an agent.
    // Answered before the expiry switch, which belongs to the request each test exercises.
    const attribution =
      path === '/agent/attribution/studies' || /^\/studies\/[^/]+\/agent\/attribution$/.test(path);
    if (attribution && method === 'GET') return ok({ items: [], next_cursor: null });
    if (state.expire) { state.expire = false; return route.fulfill({ status: 401, json: { error: { code: 'unauthenticated', message: 'Session expired', fields: [], outcome: 'unchanged' } } }); }
    if (method !== 'GET') state.writes.push({ path, method, body });
    if (path === '/studies') {
      if (method === 'GET') return ok(state.actor === 'owner' && new URL(request.url()).searchParams.get('archived') !== 'true' ? state.studies : []); // this double has no archived studies
      if (state.uncertainCreate) return route.abort('failed');
      const study = { study_id: sid2, revision: 'new-study-r1', name: body.name, description: '', boundary: '' };
      state.studies.push(study); return ok(study);
    }
    if (path.startsWith('/commands/')) {
      return ok({ state: 'rejected', result: null, recovery: 'refused' });
    }
    const id = path.split('/')[2], study = state.studies.find(s => s.study_id === id);
    if (path === `/studies/${id}` && study) {
      if (method === 'PATCH') Object.assign(study, { name: body.name, description: body.description, boundary: body.boundary, revision: 'study-r2' });
      if (state.delayStudy) await state.delayStudy.promise;
      return ok(study);
    }
    if (path === `/studies/${id}/models`) {
      if (method === 'GET') return ok(state.model ? [{ model_id: mid }] : []);
      state.model = { schema_version: '1', model_id: mid, study_id: id, name: body.name, root_instance_id: 'root', draft_revision: 'draft-r1', definitions: [], instances: [], ports: [], connections: [], boundary_mappings: [], annotations: [], source_files: [], required_capabilities: [] };
      return ok(state.model);
    }
    if (path === `/studies/${id}/models/${mid}`) return ok(state.model);
    if (path === `/studies/${id}/models/${mid}/revisions`) return ok([{ model_revision_id: version, parent_model_revision_id: null, originating_draft_revision: 'draft-r1', digest: 'digest-fixture' }]);
    if (path === `/studies/${id}/models/${mid}/revisions/${version}`) return ok({ ...state.model, model_revision_id: version, parent_model_revision_id: null, originating_draft_revision: 'draft-r1', digest: 'digest-fixture' });
    if (/\/(runs|configurations|evidence)$/.test(path)) return ok([]);
    // Declared doubles, as in foundry-fixtures.ts: the model editor reads the pinned unit catalog
    // (creation stays disabled without it), and the study shell reads the latest saved
    // approach. These presentation studies have no approach.
    if (path === `/studies/${id}/unit-catalog` && study && method === 'GET') return ok(unitCatalog);
    if (path === `/studies/${id}/approach` && study && method === 'GET') return ok({ draft: null, latest_version: null });
    // As foundry-fixtures.ts: this legacy presentation model has no assumption closure; the read is
    // explicitly unavailable (honest recovery, never fabricated evidence).
    if (path === `/studies/${id}/models/${mid}/assumption-evidence` && study && method === 'GET') return route.fulfill({ status: 409, json: { error: { code: 'source_result_unavailable', message: 'Unavailable in this legacy presentation fixture', fields: [], outcome: 'unchanged' } } });
    if (path.endsWith('/execution-readiness')) return ok({ readiness_schema_version: '1', capability: 'flat_explicit_scalar', status: 'unavailable', reasons: ['executor_unavailable'], observed_at: null, expires_at: null });
    state.unknown.push(method + ' ' + path);
    return route.fulfill({ status: 500, json: { error: { message: 'Unexpected isolated request', code: 'internal_error', fields: [], outcome: 'unchanged' } } });
  });
  return state;
}
async function login(page: Page, hash = '', name = 'owner') {
  await page.goto(origin + '/ui/' + hash);
  await page.getByLabel('Username', { exact: true }).fill(name);
  await page.getByLabel('Password', { exact: true }).fill('isolated-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Profile', exact: true })).toBeVisible();
}
async function openStudy(page: Page) { await page.getByRole('button', { name: 'Open study Thermal study' }).click(); await expect(page.getByRole('heading', { name: 'About this study' })).toBeVisible(); }

test('Home, separate study creation, five study sections and minimal Profile', async ({ page }) => {
  const state = await harness(page); await login(page);
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
  await expect(page.getByLabel('New study name')).toHaveCount(0);
  // Studies | Archived switch, a quiet Archive per row and one notices link.
  await expect(page.getByRole('tablist', { name: 'Study list', exact: true }).getByRole('tab')).toHaveText(['Studies1', 'Archived0']);
  await expect(page.getByRole('button', { name: 'Archive study Thermal study', exact: true })).toBeVisible();
  await expect(page.locator('main>footer')).toHaveText('Third-party software notices');
  await page.getByLabel('Filter loaded studies').fill('missing');
  await expect(page.getByText('No studies match this filter.')).toBeVisible();
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('New study name').fill('New investigation');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'New investigation', exact: true })).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Workspace sections' }).getByRole('button'),
  ).toHaveText(['Overview', 'Models', 'Configurations', 'Runs', 'Cases']);
  await expect(page.getByRole('slider')).toHaveCount(0);
  await page.getByRole('button', { name: 'Profile', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Profile', exact: true })).toBeVisible();
  await expect(page.locator('.profile-page dd')).toHaveText('owner');
  await expect(page.getByRole('combobox', { name: 'Appearance', exact: true })).toHaveValue(
    'system',
  );
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await login(page, '', 'other-user');
  await expect(page.getByText('No studies yet.', { exact: false })).toBeVisible();
  await expect(page.getByText('New investigation', { exact: true })).toHaveCount(0);
  expect(state.unknown).toEqual([]);
});

test('About edits preserve the hidden boundary through keep, discard and save navigation', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await openStudy(page);
  await page
    .locator('.study-about')
    .getByRole('button', { name: 'Edit study', exact: true })
    .click();
  await expect(page.getByLabel('Boundary', { exact: true })).toHaveCount(0);
  await page.getByLabel('Study list description', { exact: true }).fill('Local edit');
  await page
    .getByRole('dialog', { name: 'Edit study', exact: true })
    .getByRole('button', { name: 'Done', exact: true })
    .click();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.locator('textarea[aria-label="Study list description"]')).toHaveValue(
    'Local edit',
  );
  await expect(page.getByRole('button', { name: 'Home', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await openStudy(page);
  await page
    .locator('.study-about')
    .getByRole('button', { name: 'Edit study', exact: true })
    .click();
  await expect(page.getByLabel('Study list description', { exact: true })).toHaveValue(
    'A retained description',
  );
  await page.getByLabel('Study list description', { exact: true }).fill('Saved description');
  await page
    .getByRole('dialog', { name: 'Edit study', exact: true })
    .getByRole('button', { name: 'Done', exact: true })
    .click();
  await page.getByRole('button', { name: 'Profile', exact: true }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Profile', exact: true })).toBeVisible();
  expect(state.writes).toHaveLength(1);
  expect(state.writes[0].body).toMatchObject({
    expected_revision: 'study-r1',
    description: 'Saved description',
    boundary: 'Retained boundary must survive',
  });
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
  // Naming since fce14ed (as pinned in evidence-workspace.spec.ts): "<id8> (read-only)".
  await expect(page.getByLabel('Model version').locator('option:checked')).toHaveText(
    '30000000 (read-only)',
  );
  // Export lives under Model actions (resource header actions); the exact read-only version
  // offers its package download ("Download portable model record", formerly "Export exact model package").
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Download portable model record', exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel('Comparison target')).toHaveCount(0);
  await page
    .getByRole('dialog', { name: 'Export model and data', exact: true })
    .getByRole('button', { name: 'Done', exact: true })
    .click();
  await page.getByRole('button', { name: 'Close Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'All models', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Open model Scalar model', exact: true }),
  ).toBeVisible();
  expect(state.writes.map((write) => write.path)).toEqual([`/studies/${sid}/models`]);
  expect(state.unknown).toEqual([]);
});

test('Home invalidates a late study read and authorization loss clears the shell', async ({ page }) => {
  const state = await harness(page); await login(page);
  const held = latch(); state.delayStudy = held;
  await page.getByRole('button', { name: 'Open study Thermal study' }).click();
  await expect(page.getByText('Loading study/model…')).toBeVisible();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  held.release(); state.delayStudy = null;
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'About this study' })).toHaveCount(0);
  state.expire = true;
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Profile', exact: true })).toHaveCount(0);
  expect(state.unknown).toEqual([]);
});

test('Uncertain creation remains recoverable from Home and Profile without duplicate writes', async ({ page }) => {
  const state = await harness(page); await login(page); state.uncertainCreate = true;
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('New study name').fill('Unknown outcome');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Check original command', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Profile', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeEnabled();
  expect(state.writes).toHaveLength(1);
  expect(state.writes[0].body.name).toBe('Unknown outcome');
  expect(state.unknown).toEqual([]);
});

test('Study deep link and compact shell keep records reachable without page overflow', async ({ page }) => {
  const state = await harness(page); await login(page, `#v=1&view=overview&study=${sid}`);
  await expect(page.getByRole('heading', { name: 'About this study' })).toBeVisible();
  const navigation = page.getByRole('navigation', { name: 'Workspace sections' });
  await expect(navigation.getByRole('button', { name: 'Runs', exact: true })).toBeVisible();
  await expect(
    navigation.getByRole('button', { name: 'Configurations', exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/navigation-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Home', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/navigation-compact.png', fullPage: true });
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
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
    await expect(page.getByRole('button', { name: 'Home', exact: true })).toHaveAttribute(
      'aria-current',
      'page',
    );
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
      'Configurations',
      'Runs',
      'Cases',
    ]);
    for (const name of ['Models', 'Configurations', 'Runs', 'Cases', 'Overview']) {
      await sections.getByRole('button', { name, exact: true }).click();
      await expect(sections.getByRole('button', { name, exact: true })).toHaveAttribute(
        'aria-current',
        'page',
      );
    }
    await expect(page.getByRole('heading', { name: 'About this study' })).toBeVisible();
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

test('Appearance is browser-local and the unavailable assistant cannot send', async ({ page }) => {
  const state = await harness(page);
  await login(page);
  await page.getByRole('button', { name: 'Profile', exact: true }).click();
  await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await login(page);
  await openStudy(page);
  const opener = page.getByRole('button', { name: 'Open assistant', exact: true });
  await opener.click();
  const assistant = page.getByRole('region', { name: 'Assistant', exact: true });
  await expect(assistant).toContainText('Not connected');
  await expect(assistant.getByRole('button', { name: 'Send', exact: true })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(assistant).toHaveCount(0);
  await expect(opener).toBeFocused();
  expect(state.writes).toEqual([]);
});
