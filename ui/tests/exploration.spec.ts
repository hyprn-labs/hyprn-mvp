import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test, expect } from 'playwright/test';

async function openExplorer(page: any, f: any, study: string) {
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(f.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
  await page.goto('/ui/#' + new URLSearchParams({ v: '1', study, view: 'overview' }));
  const explorer = page.getByRole('region', { name: 'Explore the answer', exact: true });
  await expect(explorer.getByLabel('Directed component diagram')).toBeVisible({ timeout: 60000 });
  return explorer;
}

test('all free inputs use declared controls and the complete vector fences every curve', async ({
  page,
}) => {
  test.setTimeout(240000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const f = JSON.parse(
    await readFile(join(root, 'artifacts/exploration-browser-input.json'), 'utf8'),
  );
  const explorer = await openExplorer(page, f, f.study_id);
  const dims = f.controls.fuel_design.request.combinations[0].dimensions;
  await expect(explorer.getByRole('slider')).toHaveCount(14, { timeout: 60000 });
  await expect(explorer.getByText('Connected ·', { exact: false })).toHaveCount(5);
  await expect(explorer.getByText(f.initial_state ?? 'Calculated', { exact: true })).toHaveCount(
    11,
  );
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/1/') && r.method() !== 'GET') writes.push(r.url());
  });
  const port = (id: string) => explorer.locator('[data-port="' + id + '"]').locator('..');
  const baseline = new Map(
    f.fit.basis.inputs
      .filter((p: any) => p.binding.kind === 'free')
      .map((p: any) => [p.target.port_id, p.binding.assignment.value]),
  );
  for (const d of dims) {
    const row = port(d.target.port_id),
      slider = row.getByRole('slider'),
      entry = row.getByRole('spinbutton');
    await expect(slider).toHaveAttribute('min', String(d.lower));
    await expect(slider).toHaveAttribute('max', String(d.upper));
    await expect(slider).toHaveAttribute('step', d.step === null ? 'any' : String(d.step));
    await slider.scrollIntoViewIfNeeded();
    await slider.focus();
    await slider.press('Home');
    await expect(slider).toBeFocused();
    await expect(entry).toHaveValue(String(d.lower));
    // Pointer interaction is on the native control, never a canvas drag.
    const box = await slider.boundingBox();
    if (!box) throw Error('Missing native range');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.7, box.y + box.height / 2);
    await page.mouse.up();
    await expect(slider).toBeFocused();
    await entry.fill(String(baseline.get(d.target.port_id)));
  }
  const axis = port(f.fit.request.axis.port_id);
  await axis.getByRole('spinbutton').fill('6.1');
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(11);
  const second = dims.find(
    (d: any) => d.target.port_id !== f.fit.request.axis.port_id && !d.covary_group,
  );
  await port(second.target.port_id).getByRole('spinbutton').fill(String(second.upper));
  await expect(explorer.getByText('Not computed', { exact: true })).toHaveCount(11);
  await axis.getByRole('slider').focus();
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(0);
  await expect(explorer.locator('.hf-response-curve__estimate')).toHaveCount(0);
  await port(second.target.port_id)
    .getByRole('spinbutton')
    .fill(String(baseline.get(second.target.port_id)));
  await axis.getByRole('slider').focus();
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(11);
  const integer = dims.find((d: any) => d.step === 1);
  await port(integer.target.port_id).getByRole('spinbutton').fill('100.5');
  await expect(explorer.getByText('Not computed', { exact: true })).toHaveCount(11);
  await port(integer.target.port_id).getByRole('spinbutton').fill('100');
  for (const group of ['mass', 'volume']) {
    const linked = dims.filter((d: any) => d.covary_group === group);
    await port(linked[0].target.port_id).getByRole('spinbutton').fill(String(linked[0].lower));
    await expect(port(linked[1].target.port_id).getByRole('spinbutton')).toHaveValue(
      String(linked[0].lower),
    );
    await port(linked[0].target.port_id)
      .getByRole('spinbutton')
      .fill(String(baseline.get(linked[0].target.port_id)));
  }
  await axis.getByRole('spinbutton').fill('7');
  await expect(axis).toContainText('Outside the declared range.');
  await expect(axis.getByRole('spinbutton')).toHaveValue('7');
  await axis.getByRole('spinbutton').fill('');
  await expect(explorer.getByText('Not computed', { exact: true })).toHaveCount(11);
  await axis.getByRole('spinbutton').fill('6.1');
  expect(writes).toEqual([]);
  await expect(
    explorer.getByRole('button', { name: 'Calculate selected point', exact: true }),
  ).toHaveCount(0);
  await explorer.getByRole('button', { name: 'Sample settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Sample settings', exact: true });
  expect(await dialog.locator('.hf-btn--primary').count()).toBeLessThanOrEqual(1);
  await expect(
    dialog.getByRole('button', { name: 'Calculate selected point', exact: true }),
  ).toBeEnabled();
  await expect(
    dialog.getByRole('button', { name: 'Save input design', exact: true }),
  ).toBeVisible();
  if (!f.selected_run_id) {
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
  }
  await page.keyboard.press('Escape');
  await explorer.locator('.hf-node').first().scrollIntoViewIfNeeded();
  await page.screenshot({
    path: join(root, 'evidence/exploration-all-inputs-day.png'),
    fullPage: true,
  });
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
  await page.screenshot({
    path: join(root, 'evidence/exploration-all-inputs-dark.png'),
    fullPage: true,
  });
  await explorer.getByRole('button', { name: 'Open model', exact: true }).click();
  expect(page.url()).toContain(f.fit.basis.model_revision_id);
});

test('independent categories preserve common values and fence late loads', async ({ page }) => {
  test.setTimeout(180000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const f = JSON.parse(
    await readFile(join(root, 'artifacts/exploration-browser-input.json'), 'utf8'),
  );
  const explorer = await openExplorer(page, f, f.controls.generic_study_id);
  const material = explorer.getByRole('combobox', { name: 'material', exact: true }),
    regime = explorer.getByRole('combobox', { name: 'regime', exact: true });
  await expect(material).toBeVisible({ timeout: 60000 });
  await expect(explorer.getByRole('slider')).toHaveCount(4);
  const entry = (name: string) =>
    explorer.getByRole('spinbutton', { name: name + ' · Dimensionless', exact: true });
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/1/') && r.method() !== 'GET') writes.push(r.url());
  });
  for (const [m, r, mv, rv] of [
    ['a', 'low', '2', '3'],
    ['a', 'high', '2', '7'],
    ['b', 'low', '5', '3'],
    ['b', 'high', '5', '7'],
  ]) {
    await material.selectOption(m);
    await regime.selectOption(r);
    await expect(entry('material_factor')).toHaveValue(mv, { timeout: 60000 });
    await expect(entry('regime_factor')).toHaveValue(rv);
  }
  await entry('x').fill('2');
  await entry('y').fill('3');
  await entry('material_factor').fill('9');
  await material.selectOption('a');
  await expect(entry('material_factor')).toHaveValue('2', { timeout: 60000 });
  await expect(entry('x')).toHaveValue('2');
  await expect(entry('y')).toHaveValue('3');
  await expect(regime.locator('option[value="unsupported"]')).toHaveAttribute('disabled', '');
  // An older response is delayed at the real HTTP boundary; newer selection wins.
  let delayed = false;
  let finishDelayed!: () => void;
  const delayedFinished = new Promise<void>((resolve) => {
    finishDelayed = resolve;
  });
  await page.route('**/exploration-basis/**', async (route) => {
    if (!delayed) {
      delayed = true;
      const response = await route.fetch();
      await new Promise((r) => setTimeout(r, 900));
      await route.fulfill({ response });
      finishDelayed();
    } else await route.continue();
  });
  await regime.selectOption('low');
  await regime.selectOption('high');
  await expect(entry('regime_factor')).toHaveValue('7', { timeout: 60000 });
  await delayedFinished;
  await expect(regime).toHaveValue('high');
  await expect(entry('regime_factor')).toHaveValue('7');
  await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(0);
  expect(writes).toEqual([]);
  await page.unroute('**/exploration-basis/**');
  await explorer.getByRole('button', { name: 'Sample settings', exact: true }).click();
  const settings = page.getByRole('dialog', { name: 'Sample settings', exact: true });
  const savedDesign = page.waitForResponse(
    (r) => r.url().endsWith('/exploration-designs') && r.request().method() === 'POST',
    { timeout: 60000 },
  );
  const reloadedBasis = page.waitForResponse((r) => r.url().includes('/exploration-basis/'), {
    timeout: 60000,
  });
  await settings.getByRole('button', { name: 'Save input design', exact: true }).click();
  expect((await savedDesign).status()).toBe(201);
  expect((await reloadedBasis).status()).toBe(200);
  await expect(
    settings.getByRole('button', { name: 'Save input design', exact: true }),
  ).toBeEnabled({ timeout: 60000 });
  await expect(settings.getByText('Sampling scope:', { exact: false })).toBeVisible({
    timeout: 60000,
  });
  await settings.getByText('Sampling budget and error targets', { exact: true }).click();
  await settings
    .getByRole('spinbutton', { name: 'product absolute error', exact: true })
    .fill('0.1');
  await settings
    .getByRole('spinbutton', { name: 'product relative error', exact: true })
    .fill('0.01');
  await settings.getByRole('spinbutton', { name: 'Seed', exact: true }).fill('');
  await settings.getByRole('button', { name: 'Preview samples', exact: true }).click();
  await expect(settings.getByRole('alert')).toContainText('Enter a whole number');
  await settings.getByRole('spinbutton', { name: 'Seed', exact: true }).fill('17');
  const previewResponse = page.waitForResponse((r) =>
    r.url().endsWith('/exploration-samples/preview'),
  );
  await settings.getByRole('button', { name: 'Preview samples', exact: true }).click();
  const previewResult = await previewResponse;
  if (f.historical_executor_unavailable) {
    expect(previewResult.status(), await previewResult.text()).toBe(503);
    await expect(settings.getByRole('alert')).toContainText('unavailable');
    await expect(
      settings.getByRole('button', { name: 'Prepare samples', exact: true }),
    ).toHaveCount(0);
  } else {
    expect(previewResult.status(), await previewResult.text()).toBe(200);
    await expect(settings).toContainText('5 new calculations', { timeout: 60000 });
    await settings.getByRole('button', { name: 'Prepare samples', exact: true }).click();
    await expect(settings).toContainText('Samples: pending');
    await settings.getByRole('button', { name: 'Cancel sampling', exact: true }).click();
    await expect(settings).toContainText('Samples: cancelled');
    await settings.getByRole('button', { name: 'Read sampling progress', exact: true }).click();
    await settings.getByRole('button', { name: 'Resume sampling', exact: true }).click();
    await expect(settings).toContainText('Samples: pending');
    await settings.getByRole('button', { name: 'Cancel sampling', exact: true }).click();
    await expect(settings).toContainText('Samples: cancelled');
    await expect(
      settings.getByRole('button', { name: 'Reconcile sampling', exact: true }),
    ).toHaveCount(0);
    await expect(settings).toContainText('5 total');
    await expect(settings).not.toContainText('0 attempted');
  }
  await page.keyboard.press('Escape');
  await writeFile(
    join(root, 'evidence/exploration-controls-proof.json'),
    JSON.stringify({
      all_free_inputs: 14,
      connected: 5,
      outputs: 11,
      generic_inputs: 4,
      category_dimensions: 2,
      supported_tuples: 4,
      slider_writes: 0,
      late_response_fenced: true,
      historical_executor_unavailable: !!f.historical_executor_unavailable,
      human_acceptance: false,
    }),
  );
});

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
