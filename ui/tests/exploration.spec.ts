import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test, expect } from 'playwright/test';

test('canonical graph keeps calculations in settings and predictions on selection', async ({
  page,
}) => {
  test.setTimeout(240000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const f = JSON.parse(
    await readFile(join(root, 'artifacts/exploration-browser-input.json'), 'utf8'),
  );
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(f.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
  await page.goto('/ui/#' + new URLSearchParams({ v: '1', study: f.study_id, view: 'overview' }));
  const explorer = page.getByRole('region', { name: 'Explore the answer', exact: true });
  page.on('response', (response) => {
    if (response.url().includes('/api/1/'))
      console.log('API read', response.status(), new URL(response.url()).pathname);
  });
  page.on('pageerror', (error) => console.log('Page error', error.message));
  page.on('requestfailed', (request) =>
    console.log('Request failed', new URL(request.url()).pathname, request.failure()),
  );
  await expect(explorer.getByLabel('Directed component diagram')).toBeVisible({ timeout: 60000 });
  await expect(explorer.locator('.hf-node')).toHaveCount(3);
  await expect(explorer.getByText('Calculated', { exact: true })).toHaveCount(11);
  await expect(
    explorer.getByRole('button', { name: 'Calculate selected point', exact: true }),
  ).toHaveCount(0);
  const axis = f.fit.basis.inputs.find(
    (p: any) => JSON.stringify(p.target) === JSON.stringify(f.fit.request.axis),
  );
  const slider = explorer.getByRole('slider', { name: axis.name + ' prepared points' });
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/1/') && r.method() !== 'GET') writes.push(r.url());
  });
  await slider.focus();
  await slider.press('End');
  await expect(slider).toBeFocused();
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(11);
  expect(writes).toEqual([]);
  const entry = explorer.getByRole('spinbutton', { name: axis.name + ' · Dimensionless' });
  await entry.fill('');
  await expect(explorer.getByText('Not computed', { exact: true })).toHaveCount(11);
  await entry.fill('6.05');
  await expect(explorer.getByText('Not computed', { exact: true })).toHaveCount(11);
  await expect(explorer).toContainText('No prepared estimate at this value.');
  await entry.fill('6.1');
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(11);
  expect(writes).toEqual([]);
  const readouts = explorer.locator('.hf-quantity-result');
  for (const output of f.fit.request.tolerances) {
    const index = f.fit.request.tolerances.indexOf(output);
    const numeric = f.fit.numerical.result.outputs[index].values[2];
    expect(numeric).not.toBeNull();
    const port = explorer.locator('[data-port="' + output.target.port_id + '"]').locator('..');
    await expect(port.locator('.hf-quantity-result')).toContainText('Estimated');
    await expect(port.locator('.hf-quantity-result')).toHaveAttribute('title', String(numeric));
    await expect(port.locator('svg title')).toContainText('6.1');
  }
  expect(await readouts.count()).toBe(11);
  await readouts.first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(root, 'evidence/exploration-day.png'), fullPage: true });
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
  await page.screenshot({ path: join(root, 'evidence/exploration-dark.png'), fullPage: true });
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  await explorer.getByRole('button', { name: 'Sample settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Sample settings', exact: true });
  const response = page.waitForResponse(
    (r) => r.url().endsWith('/runs') && r.request().method() === 'POST',
    { timeout: 60000 },
  );
  await dialog.getByRole('button', { name: 'Calculate selected point', exact: true }).click();
  const run = (await (await response).json()).data;
  await writeFile(
    join(root, 'artifacts/exploration-submitted.json'),
    JSON.stringify({ run_id: run.run_id }),
  );
  await expect(dialog).toContainText('Calculation submitted.');
  await expect
    .poll(
      async () => {
        await dialog
          .getByRole('button', { name: 'Read selected calculation', exact: true })
          .click();
        return explorer.getByText('Calculated', { exact: true }).count();
      },
      { timeout: 160000, intervals: [1000] },
    )
    .toBe(11);
  await page.keyboard.press('Escape');
  await expect(slider).toHaveValue('2');
  await expect(explorer.locator('.hf-response-curve__calculated')).toHaveCount(22);
  await expect(explorer.locator('.hf-response-curve__cursor')).toHaveCount(0);
  await slider.focus();
  await slider.press('Home');
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(11);
  const after = writes.length;
  await slider.press('ArrowRight');
  await expect(explorer.getByText('Calculated', { exact: true })).toHaveCount(11);
  expect(writes.length).toBe(after);
  await explorer.getByRole('button', { name: 'Open model', exact: true }).click();
  expect(page.url()).toContain(f.fit.basis.model_revision_id);
});

test('retained graph exposes real response curves without another calculation', async ({
  page,
}) => {
  test.setTimeout(120000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const f = JSON.parse(
    await readFile(join(root, 'artifacts/exploration-browser-input.json'), 'utf8'),
  );
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(f.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
  await page.goto('/ui/#' + new URLSearchParams({ v: '1', study: f.study_id, view: 'overview' }));
  const explorer = page.getByRole('region', { name: 'Explore the answer', exact: true });
  await expect(explorer.getByText('Calculated', { exact: true })).toHaveCount(11, {
    timeout: 60000,
  });
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/1/') && r.method() !== 'GET') writes.push(r.url());
  });
  await explorer.getByRole('slider').press('End');
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(11);
  const firstOutput = explorer.locator('.hf-response-curve').first();
  await firstOutput.scrollIntoViewIfNeeded();
  await expect(firstOutput).toBeVisible();
  await page.screenshot({
    path: join(root, 'evidence/exploration-outputs-day.png'),
    fullPage: true,
  });
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
  await page.screenshot({
    path: join(root, 'evidence/exploration-outputs-dark.png'),
    fullPage: true,
  });
  await explorer.getByRole('button', { name: 'Result basis', exact: true }).first().click();
  await expect(page.getByRole('dialog')).toContainText(f.fit.numerical.result_sha256);
  await page.keyboard.press('Escape');
  expect(writes).toEqual([]);
  const selected = await page.request.get(
    '/api/1/studies/' + f.study_id + '/runs/' + f.selected_run_id,
    { timeout: 60000 },
  );
  expect(selected.status()).toBe(200);
  expect((await selected.json()).data.history.results.execution.state).toBe('finished');
});
