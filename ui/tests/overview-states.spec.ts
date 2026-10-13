import { test, expect, Page } from 'playwright/test';
import { ownerPassword } from './support/served';

const sid = 'dec4f9d0-e125-4f9a-8908-8dbc22cd105a';
const cid = '98d6bf68-42e2-4be7-8668-17b0d967c8f2';
const rid = '6e80a9ea-5f6a-4edf-a2fa-95826ab3733f';
const configurations = (page: Page) => page.getByRole('region', { name: 'Recent configurations', exact: true });
const runs = (page: Page) => page.getByRole('region', { name: 'Recent runs', exact: true });
async function login(page: Page) {
  await page.goto('/ui/#v=1&study=' + sid + '&view=overview');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
}
const failure = (code = 'internal_error') => ({ error: { code, message: 'Controlled collection read failure', fields: [], outcome: 'unchanged' } });
function latch() { let release!: () => void; const pending = new Promise<void>(resolve => { release = resolve; }); return { pending, release }; }

for (const collection of ['configurations', 'runs'] as const) test(`${collection} read failure has independent retry and no writes`, async ({ page }) => {
  let fail = true;
  const mutations: string[] = [];
  page.on('request', request => { if (request.method() !== 'GET' && !request.url().endsWith('/session')) mutations.push(request.method() + ' ' + request.url()); });
  await page.route(`**/api/1/studies/${sid}/${collection}`, route => fail ? route.fulfill({ status: 500, json: failure() }) : route.continue());
  await login(page);
  const failed = collection === 'configurations' ? configurations(page) : runs(page);
  const healthy = collection === 'configurations' ? runs(page) : configurations(page);
  await expect(failed.getByRole('alert')).toContainText('Could not load recent ' + collection);
  await expect(healthy.getByRole('button').first()).toBeVisible();
  await expect(failed).not.toContainText('no runs yet');
  await expect(failed).not.toContainText('No saved configurations');
  fail = false;
  await failed.getByRole('button', { name: 'Retry recent ' + collection }).click();
  await expect(failed.getByRole('alert')).toHaveCount(0);
  await expect(failed.getByRole('button').first()).toBeVisible();
  expect(mutations).toEqual([]);
});

test('pending records show loading and late completions cannot populate another empty study', async ({ page }) => {
  const held = latch();
  await page.route(`**/api/1/studies/${sid}/configurations`, async route => { const response = await route.fetch(); await held.pending; await route.fulfill({ response }); });
  await page.route(`**/api/1/studies/${sid}/runs`, async route => { const response = await route.fetch(); await held.pending; await route.fulfill({ response }); });
  try {
    await login(page);
    await expect(configurations(page).getByRole('status')).toHaveText('Loading recent configurations…');
    await expect(runs(page).getByRole('status')).toHaveText('Loading recent runs…');
    await page.getByLabel('New study name').fill('Empty Overview ' + crypto.randomUUID());
    await page.getByRole('button', { name: 'Create study', exact: true }).click();
    await expect(configurations(page)).toContainText('No saved configurations in this study.');
    await expect(runs(page)).toContainText('This study has no runs yet.');
    held.release();
    await page.unrouteAll({ behavior: 'wait' });
    await expect(configurations(page)).not.toContainText(sid);
    await expect(runs(page)).not.toContainText(sid);
    await expect(configurations(page).getByRole('button')).toHaveCount(0);
    await expect(runs(page).getByRole('button')).toHaveCount(0);
  } finally { held.release(); }
});

test('authorization loss clears Overview and late successful records cannot restore it', async ({ page }) => {
  const auth = latch(), held = latch();
  await page.route(`**/api/1/studies/${sid}/configurations`, async route => { await auth.pending; await route.fulfill({ status: 401, json: failure('unauthenticated') }); });
  await page.route(`**/api/1/studies/${sid}/runs`, async route => { const response = await route.fetch(); await held.pending; await route.fulfill({ response }); });
  try {
    await login(page);
    await expect(configurations(page).getByRole('status')).toBeVisible();
    auth.release();
    await expect(page.getByRole('heading', { name: 'Sign in to HYPRN MVP' })).toBeVisible();
    held.release();
    await page.unrouteAll({ behavior: 'wait' });
    await expect(configurations(page)).toHaveCount(0);
    await expect(runs(page)).toHaveCount(0);
    await expect(page.getByText(sid, { exact: false })).toHaveCount(0);
  } finally { auth.release(); held.release(); }
});

test('bounded summary takes the latest five across public pages without sorting UUIDs', async ({ page }) => {
  // Fault/collection-shape fixture only; actual retained-record checks are in overview.spec.ts.
  const ids = ['ffffffff', 'dddddddd', 'bbbbbbbb', '99999999', '77777777', '55555555', '33333333'].map(prefix => prefix + '-0000-4000-8000-000000000000');
  const observed: string[] = [];
  await page.route(`**/api/1/studies/${sid}/configurations*`, async route => {
    const url = new URL(route.request().url());
    if (url.pathname !== `/api/1/studies/${sid}/configurations`) return route.continue();
    const response = await page.request.get(`/api/1/studies/${sid}/configurations/${cid}`);
    const frozen = (await response.json()).data;
    const start = url.searchParams.get('cursor') ? 4 : 0;
    observed.push(url.searchParams.get('cursor') ?? 'first');
    const data = ids.slice(start, start + 4).map((id, i) => ({ ...frozen, configuration: { ...frozen.configuration, configuration_revision_id: id, name: 'Collection fixture ' + (start + i) } }));
    await route.fulfill({ json: { schema_version: '1', data, next_cursor: start === 0 ? 'page-two' : null } });
  });
  await login(page);
  await expect(configurations(page).getByRole('button')).toHaveCount(5);
  await expect(configurations(page)).toContainText('5 of 7 loaded configurations');
  await expect(configurations(page).getByRole('button')).toHaveText(['Collection fixture 6', 'Collection fixture 5', 'Collection fixture 4', 'Collection fixture 3', 'Collection fixture 2']);
  expect(observed).toContain('page-two');
  await expect(runs(page).getByRole('button', { name: 'Open run ' + rid, exact: true })).toBeVisible();
});
