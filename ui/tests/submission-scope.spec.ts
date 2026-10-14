import { test, expect, Page, Route } from 'playwright/test';
import { ownerPassword } from './support/served';

// The owner's receipt answer for the original run command: the run is the outcome (adopt).
const adopt = (f: { command: string; run: unknown }) => (route: Route) =>
  route.fulfill({
    json: {
      schema_version: '1',
      data: { command_id: f.command, state: 'committed', result: f.run, recovery: 'adopt' },
    },
  });

async function fixture(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const names = ['Destination ', 'Origin '].map(x => x + crypto.randomUUID()), ids: string[] = [];
  for (const name of names) {
    await page.getByLabel('New study name').fill(name); await page.getByRole('button', { name: 'Create study', exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    ids.push(await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue());
  }
  const [destination, origin] = ids;
  // Readiness and submission responses are navigation fixtures only; the stopped executor is unchanged.
  await page.route(`**/api/1/studies/${origin}/execution-readiness`, route => route.fulfill({ json: { schema_version: '1', data: { status: 'ready', capability: 'flat_explicit_scalar', reasons: [], observed_at: new Date().toISOString(), expires_at: new Date(Date.now() + 600000).toISOString() } } }));
  await page.getByLabel('New model name').fill('Submission scope'); await page.getByLabel('Starting model').selectOption('two_component_example');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Reload model', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByText('Model snapshot committed. Enter or review every input.', { exact: true })).toBeVisible();
  await page.getByLabel('Configuration name', { exact: true }).fill('Scope fixture');
  for (const symbol of ['x', 'z']) { await page.getByLabel(`First · ${symbol} value`, { exact: true }).fill('0'); await page.getByLabel(`First · ${symbol} provenance`, { exact: true }).fill('Explicit fixture'); }
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const cid = (await (await page.request.get(`/api/1/studies/${origin}/configurations`)).json()).data[0].configuration.configuration_revision_id;
  const run = { run_id: crypto.randomUUID(), state: 'accepted_run', configuration_revision_id: cid, history: null };
  let posts = 0, command = '', delayed: Route | undefined; const wrongReads: string[] = [];
  page.on('request', r => { if (r.url().includes(`/studies/${destination}/runs/${run.run_id}`)) wrongReads.push(r.url()); });
  await page.route(`**/api/1/studies/${origin}/runs`, route => { if (route.request().method() === 'POST') { posts++; command = route.request().postDataJSON().command_id; delayed = route; } else void route.continue(); });
  await page.route(`**/api/1/studies/${origin}/runs/${run.run_id}`, route => route.fulfill({ json: { schema_version: '1', data: run } }));
  return { origin, destination, names, run, get posts() { return posts; }, get command() { return command; }, get delayed() { return delayed; }, wrongReads };
}

for (const outcome of ['acknowledgement', 'recovery'] as const) test(`${outcome} retains original run without contaminating another study`, async ({ page }) => {
  const f = await fixture(page);
  await page.getByRole('button', { name: 'Run model', exact: true }).click();
  await expect.poll(() => !!f.delayed).toBe(true);
  if (outcome === 'recovery') { await f.delayed!.abort('failed'); await expect(page.getByRole('button', { name: 'Check original command', exact: true })).toBeVisible(); }
  await page.getByRole('combobox', { name: 'Study', exact: true }).selectOption(f.destination);
  await expect(page.getByRole('heading', { name: f.names[0], exact: true })).toBeVisible();
  if (outcome === 'acknowledgement') await f.delayed!.fulfill({ json: { schema_version: '1', data: f.run } });
  else {
    await page.route(`**/api/1/studies/${f.origin}/commands/${f.command}?category=run`, adopt(f));
    await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  }
  await expect(page.getByRole('button', { name: 'Open original run', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: f.names[0], exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Overview', exact: true })).toHaveAttribute('aria-current', 'page');
  expect(new URL(page.url()).hash).toContain(f.destination); expect(new URL(page.url()).hash).not.toContain(f.run.run_id);
  expect(f.posts).toBe(1); expect(f.wrongReads).toEqual([]);
  await page.getByRole('button', { name: 'Open original run', exact: true }).click();
  await expect(page.getByRole('heading', { name: f.names[1], exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Run details', exact: true })).toContainText(f.run.run_id);
  expect(new URL(page.url()).hash).toContain(f.origin); expect(f.posts).toBe(1);
  expect((await (await page.request.get(`/api/1/studies/${f.origin}/runs`)).json()).data).toHaveLength(0);
});
test('original-context recovery still selects its run without resubmission', async ({ page }) => {
  const f = await fixture(page); await page.getByRole('button', { name: 'Run model', exact: true }).click(); await expect.poll(() => !!f.delayed).toBe(true);
  await f.delayed!.abort('failed'); await expect(page.getByRole('button', { name: 'Check original command', exact: true })).toBeVisible();
  await page.route(`**/api/1/studies/${f.origin}/commands/${f.command}?category=run`, adopt(f));
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Run details', exact: true })).toContainText(f.run.run_id); expect(f.posts).toBe(1);
  await expect(page.getByRole('button', { name: 'Open original run', exact: true })).toHaveCount(0);
});
