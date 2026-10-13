import { test, expect, type Page, type Route } from 'playwright/test';
import { startFixture, stopFixture, guardOrigin, harness, login, runFixture, sid } from './foundry-fixtures';

// P2 port of the legacy live-app history-races.spec.ts (fbd0242) to the isolated Foundry
// harness: identical race choreography and assertions, with the declared in-browser API
// double and a fixture run record instead of the live app, its old credentials and a retained native file.
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture);
test.beforeEach(async ({ page }) => { await guardOrigin(page); });
test.afterAll(stopFixture);

// Deep links require a canonical run identity; the legacy spec used this same id.
const id = '41f66a9e-2509-40b7-87ae-04cfd5a69a04', url = `/api/1/studies/${sid}/runs/${id}`;
async function open(page: Page, before?: (state: Awaited<ReturnType<typeof harness>>) => Promise<void>) {
  const state = await harness(page); runFixture(state);
  state.detail.run_id = id; state.runs[0].run_id = id;
  const record = structuredClone(state.detail);
  await page.route(`**${url}`, route => route.fulfill({ json: { schema_version: '1', data: state.detail } }));
  if (before) await before(state);
  await login(page, `#v=1&view=runs&study=${sid}&run=${id}`);
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible();
  return { state, record, pending: { ...record, state: 'dispatching', process_state: 'running', history: null } };
}

for (const late of ['pending', 'error']) test(`newer terminal detail survives late ${late} poll`, async ({ page }) => {
  const { state, record, pending } = await open(page); let count = 0, delayed: Route | undefined;
  await page.route(`**${url}`, async route => {
    count++;
    if (count === 2) { delayed = route; return; }
    await route.fulfill({ json: { schema_version: '1', data: count === 1 ? pending : record } });
  });
  // Re-select so the first pending response starts the actual polling effect.
  await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
  await page.getByRole('button', { name: `Inspect run ${id}`, exact: true }).click();
  await expect.poll(() => !!delayed).toBe(true);
  await page.getByRole('button', { name: 'Refresh run status', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible();
  if (late === 'pending') await delayed!.fulfill({ json: { schema_version: '1', data: pending } });
  else await delayed!.abort('failed');
  await page.waitForTimeout(1800); // Beyond the polling interval: stale reads must not reschedule.
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Run details' }).getByRole('alert')).toHaveCount(0);
  expect(count).toBe(3);
  // Legacy asserted an enabled manual refresh. Since automatic progress (a1fd1d5) the action
  // exists only while a run is pending, so its absence proves the terminal detail was kept.
  await expect(page.getByRole('button', { name: 'Refresh run status', exact: true })).toHaveCount(0);
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});

test('newer history list survives the late initial response', async ({ page }) => {
  let first: Route | undefined, calls = 0;
  const { state } = await open(page, async fixture => {
    const item = { run_id: id, state: fixture.detail.state, process_state: fixture.detail.process_state, configuration_revision_id: fixture.detail.history.configuration.configuration_revision_id };
    await page.route(`**/api/1/studies/${sid}/runs`, async route => {
      if (++calls === 1) { first = route; return; }
      await route.fulfill({ json: { schema_version: '1', data: [item] } });
    });
  });
  // History list and run detail are separate views now; return to the list explicitly.
  await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
  await expect(page.getByRole('button', { name: `Inspect run ${id}`, exact: true })).toBeVisible();
  await expect.poll(() => !!first).toBe(true);
  await first!.fulfill({ json: { schema_version: '1', data: [] } });
  await page.waitForTimeout(100);
  await expect(page.getByRole('button', { name: `Inspect run ${id}`, exact: true })).toBeVisible();
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});

test('late detail failure cannot alter another selection or remounted history', async ({ page }) => {
  const { state, pending } = await open(page); let delayed: Route | undefined, count = 0;
  // A manual refresh exists only for pending runs (a1fd1d5): reopen the run while pending,
  // then hold its next detail read (automatic poll or explicit refresh).
  await page.route(`**${url}`, async route => {
    if (++count === 1) return route.fulfill({ json: { schema_version: '1', data: pending } });
    delayed = route;
  });
  await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
  await page.getByRole('button', { name: `Inspect run ${id}`, exact: true }).click();
  await page.getByRole('button', { name: 'Refresh run status', exact: true }).click();
  await expect.poll(() => !!delayed).toBe(true);
  await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
  await delayed!.abort('failed');
  await expect(page.getByRole('region', { name: 'Run details' })).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});
