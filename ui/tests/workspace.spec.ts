import { test, expect, Page } from 'playwright/test';
import { evidencePath } from './evidence';
import { HyprnMvpApi } from '../src/api';
import { ownerPassword, servedOrigin } from './support/served';

async function login(page: Page, hash = '') {
  await page.goto('about:blank');
  await page.goto('/ui/' + hash);
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const response = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
  return (await (await response).json()).data.csrf_token as string;
}
async function create(page: Page) {
  const name = 'Workspace ' + crypto.randomUUID();
  await page.getByLabel('New study name').fill(name);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  return name;
}
test('empty study, loaded filtering, navigation and logout clear scoped data', async ({ page }) => {
  await login(page); const name = await create(page);
  await page.getByLabel('Filter loaded studies').fill(name);
  await expect(page.getByText(/1 of \d+ loaded studies/)).toBeVisible();
  const width = page.getByRole('slider', { name: 'Navigation width', exact: true });
  const initialWidth = Number(await width.inputValue()); await width.focus(); await width.press('ArrowRight');
  await expect(width).toHaveValue(String(initialWidth + 16));
  await page.getByLabel('Filter loaded studies').focus();
  await page.setViewportSize({ width: 1024, height: 900 });
  const show = page.getByRole('button', { name: 'Show study navigation', exact: true });
  await expect(show).toHaveAttribute('aria-expanded', 'false'); await expect(show).toBeFocused();
  await show.click(); await expect(page.getByLabel('Filter loaded studies')).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.setViewportSize({ width: 1440, height: 1000 });
  for (const view of ['Overview', 'Model', 'Configurations', 'Runs', 'Evidence']) {
    await page.getByRole('button', { name: view, exact: true }).click();
    await expect(page.getByRole('button', { name: view, exact: true })).toHaveAttribute('aria-current', 'page');
  }
  await expect(page.getByText('No evidence notes yet. Add a note or select a scope.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to HYPRN MVP' })).toBeVisible();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
});
test('exact committed revision remains read-only after draft changes and missing links never fall back', async ({ page }) => {
  const csrf = await login(page); await create(page);
  await page.getByLabel('New model name').fill('Revision fixture');
  await page.getByLabel('Starting model').selectOption('two_component_example');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Refresh model' })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const base = `/api/1/studies/${sid}/models/${mid}`;
  const draft = (await (await page.request.get(base)).json()).data;
  const commit = await page.request.post(base + '/commits', { headers: { 'X-CSRF-Token': csrf, Origin: servedOrigin() }, data: { command_id: crypto.randomUUID(), expected_revision: draft.draft_revision } });
  expect(commit.ok()).toBeTruthy(); const revision = (await commit.json()).data;
  expect(revision.model_revision_id).toMatch(/^[0-9a-f-]{36}$/);
  const rename = await page.request.post(base + '/edits', { headers: { 'X-CSRF-Token': csrf, Origin: servedOrigin() }, data: { command_id: crypto.randomUUID(), expected_revision: draft.draft_revision, edits: [{ kind: 'rename_model', name: 'Changed draft name' }] } });
  expect(rename.ok()).toBeTruthy();
  await page.getByRole('button', { name: 'Refresh model' }).click();
  await page.getByRole('combobox', { name: 'Model revision', exact: true }).selectOption(revision.model_revision_id);
  await expect(page.getByText('Read-only model revision', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Exact revision source').first()).toHaveText(Buffer.from(revision.source_files[0].bytes, 'base64').toString('utf8'));
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp('revision=' + revision.model_revision_id));
  await login(page, `#v=1&study=${sid}&model=${mid}&revision=${crypto.randomUUID()}&view=model`);
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveCount(0);
  await expect(page.getByText('Saved mutable draft', { exact: true })).toHaveCount(0);
});
test('dirty navigation retains proposal and safe choice restores focus', async ({ page }) => {
  await login(page); await create(page);
  await page.getByLabel('New model name').fill('Dirty fixture');
  await page.getByLabel('Starting model').selectOption('two_component_example');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await page.getByRole('button', { name: /^Select / }).first().click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: evidencePath('connected-shell.png'), fullPage: true });
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('# local proposal\n');
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveValue('# local proposal\n');
  await expect(page.getByRole('button', { name: 'Runs', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Run history', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('# saved proposal\n');
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true });
  await expect(preview.getByRole('button', { name: 'Apply changes', exact: true })).toBeEnabled();
  await preview.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(preview).not.toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Unsaved changes', exact: true })).not.toBeVisible();
  await expect(page.getByRole('heading', { name: 'Run history', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveValue('# saved proposal\n');
});
test('late authenticated responses cannot restore another session; original command stays actor-scoped', async () => {
  const api = new HyprnMvpApi(); api.actor = 'actor-a';
  const originalFetch = globalThis.fetch;
  let finish!: (response: Response) => void;
  globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
  try {
    const command = { command_id: crypto.randomUUID() };
    const pending = api.mutate('/studies', command, 'study_create');
    api.actor = 'actor-b';
    finish(new Response(JSON.stringify({ schema_version: '1', data: { state: 'committed' } }), { status: 200 }));
    await expect(pending).rejects.toThrow('session changed');
    expect(api.pending).toBeNull();
    globalThis.fetch = async () => new Response(JSON.stringify({ data: { actor_id: 'actor-a', csrf_token: 'synthetic', expires_at: 0 } }), { status: 200 });
    await api.login('actor-a', 'synthetic');
    expect(api.pending?.body.command_id).toEqual(command.command_id);
    expect(api.retryReady).toBe(false);
  } finally { globalThis.fetch = originalFetch; }
});
test('run deep link reads retained history without a modeling request', async ({ page }) => {
  await login(page);
  const studies = (await (await page.request.get('/api/1/studies')).json()).data;
  let target: { sid: string; rid: string } | undefined;
  for (const study of studies) {
    const runs = (await (await page.request.get(`/api/1/studies/${study.study_id}/runs`)).json()).data;
    const recorded = runs.find((r: { state: string }) => r.state === 'recorded');
    if (recorded) { target = { sid: study.study_id, rid: recorded.run_id }; break; }
  }
  expect(target, 'Retained baseline run fixture must exist').toBeTruthy();
  const requests: string[] = [];
  await page.route('**/api/1/studies/*/models/**', route => { requests.push(route.request().url()); return route.abort(); });
  await login(page, `#v=1&study=${target!.sid}&run=${target!.rid}&view=runs`);
  await expect(page.getByRole('heading', { name: `Run ${target!.rid}`, exact: true })).toBeVisible();
  await expect(page.getByText('Read-only retained record', { exact: true })).toBeVisible();
  expect(requests).toEqual([]);
});
test('late study response cannot restore old context and authorization loss clears it', async ({ page }) => {
  await login(page); const first = await create(page);
  const firstId = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const second = await create(page);
  const secondId = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  let release!: () => void; const held = new Promise<void>(resolve => { release = resolve; });
  let arrived!: () => void; const ready = new Promise<void>(resolve => { arrived = resolve; });
  await page.route(`**/api/1/studies/${firstId}`, async route => { const response = await route.fetch(); arrived(); await held; await route.fulfill({ response }); });
  await page.getByRole('combobox', { name: 'Study', exact: true }).selectOption(firstId);
  await ready;
  await page.getByRole('combobox', { name: 'Study', exact: true }).selectOption(secondId);
  await expect(page.getByRole('heading', { name: second, exact: true })).toBeVisible();
  release();
  await page.unrouteAll({ behavior: 'wait' });
  await expect(page.getByRole('heading', { name: first, exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: second, exact: true })).toBeVisible();
  await page.route(`**/api/1/studies/${firstId}`, route => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: { code: 'unauthenticated', message: 'Session expired', fields: [], outcome: 'unchanged' } }) }));
  await page.getByRole('combobox', { name: 'Study', exact: true }).selectOption(firstId);
  await expect(page.getByRole('heading', { name: 'Sign in to HYPRN MVP' })).toBeVisible();
  await expect(page.getByText(second, { exact: true })).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Workspace sections' })).toHaveCount(0);
});
