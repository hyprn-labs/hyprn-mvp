import { test, expect, Page } from 'playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';
async function openModelTools(page: Page) { const tools = page.locator('details.model-tools'); if (await tools.count() && await tools.getAttribute('open') === null) await tools.locator(':scope > summary').click(); }

async function login(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Create study', exact: true })).toBeVisible();
}
async function setup(page: Page) {
  await login(page);
  await page.getByLabel('Study name').fill(`Run UI ${crypto.randomUUID()}`);
  await page.getByLabel('Study question', { exact: true })
    .fill('What must this engineering study establish?');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page.getByLabel('New model name').fill('Chain');
  await page.getByLabel('Starting model').selectOption('two_component_example');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select First', exact: true })).toBeVisible();
}

async function configurationView(page: Page) { await page.getByRole('button', { name: 'Configurations', exact: true }).click(); }
async function applyChanges(page: Page) { await page.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(page.getByRole('dialog', { name: 'Preview changes', exact: true })).not.toBeVisible(); }
async function readyToRun(page: Page) {
  await page.getByRole('button', { name: 'Refresh execution readiness', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeEnabled({ timeout: 15000 });
}

test('discard before inspect and copy restores every component field without saving', async ({ page }) => {
  await setup(page);
  await configurationView(page);
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Discard fixture');
  for (const [symbol, value] of [['x', '2'], ['z', '3']]) {
    await page.getByLabel(`First · ${symbol} value`, { exact: true }).fill(value);
    await page.getByLabel(`First · ${symbol} provenance`, { exact: true }).fill('Explicit discard fixture');
  }
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const frozen = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data[0];
  // Isolated navigation fixture: no scientific execution or retained-result claim.
  const rid = crypto.randomUUID();
  await page.route(`**/api/1/studies/${sid}/runs`, route => route.fulfill({ json: { schema_version: '1', data: [{ run_id: rid, state: 'recorded', configuration_revision_id: frozen.configuration.configuration_revision_id }] } }));
  await page.route(`**/api/1/studies/${sid}/runs/${rid}`, route => route.fulfill({ json: { schema_version: '1', data: { run_id: rid, state: 'recorded', process_state: 'finished', exit_status: 0,
    history: { configuration: frozen.configuration, model_snapshot: frozen.model_snapshot, results: null, assessment: null, artifacts: [], errors: [] } } } }));
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh run history', exact: true }).click();
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  const source = page.getByRole('textbox', { name: 'Python source', exact: true });
  const original = await source.inputValue();
  await page.getByText('Inputs/outputs', { exact: true }).click();
  await page.getByText('Assumptions', { exact: true }).click();
  const portName = await page.getByLabel('Port 1 name', { exact: true }).inputValue();
  const portSymbol = await page.getByLabel('Port 1 symbol', { exact: true }).inputValue();
  const portCount = await page.getByRole('button', { name: /^Remove port / }).count();
  let writes = 0; page.on('request', r => { if (['POST', 'PATCH'].includes(r.method())) writes++; });
  for (const action of [`Inspect run ${rid}`, 'Create new version']) {
    await page.getByLabel('Component name', { exact: true }).fill('Discard me');
    await page.getByLabel('Load Python source file').setInputFiles({ name: 'discard.py', mimeType: 'text/x-python', buffer: Buffer.from('outputs["u"] = 99\n') });
    await expect(page.getByRole('status')).toContainText('Source file loaded locally');
    await page.getByLabel('Port 1 name', { exact: true }).fill('discarded');
    await page.getByLabel('Port 1 symbol', { exact: true }).fill('discarded_symbol');
    await page.getByLabel('Port 1 units', { exact: true }).fill('m');
    await page.getByRole('button', { name: 'Add input port', exact: true }).click();
    await page.getByLabel('Component assumptions').fill('Discard these notes');
    await page.getByRole('button', { name: 'Runs', exact: true }).click();
    await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
    await page.getByRole('button', { name: action, exact: true }).click();
    await page.getByRole('button', { name: 'Model', exact: true }).click();
    if (action === 'Create new version') await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
    await openModelTools(page);
    await page.getByRole('button', { name: 'Select First', exact: true }).click();
    const portDetails = page.getByText('Inputs/outputs', { exact: true }); if (!await page.getByLabel('Port 1 name', { exact: true }).isVisible()) await portDetails.click();
    if (!await page.getByLabel('Component assumptions').isVisible()) await page.getByText('Assumptions', { exact: true }).click();
    await expect(source).toHaveValue(original);
    await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('First');
    await expect(page.getByLabel('Port 1 name', { exact: true })).toHaveValue(portName);
    await expect(page.getByLabel('Port 1 symbol', { exact: true })).toHaveValue(portSymbol);
    await expect(page.getByLabel('Port 1 units', { exact: true })).toHaveValue('');
    await expect(page.getByRole('button', { name: /^Remove port / })).toHaveCount(portCount);
    await expect(page.getByLabel('Component assumptions')).toHaveValue('');
    await expect(page.getByRole('button', { name: 'Save component', exact: true })).toBeDisabled();
  }
  expect(writes).toBe(0);
});

for (const state of ['prepared', 'preparation_failed']) {
  test(`history renders the public ${state} state`, async ({ page }) => {
    await setup(page);
    const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
    const run = { run_id: crypto.randomUUID(), configuration_revision_id: crypto.randomUUID(), state };
    await page.route(`**/api/1/studies/${sid}/runs`, route => route.fulfill({ json: { schema_version: '1', data: [run] } }));
    await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh run history', exact: true }).click();
    await expect(page.getByText(`${state} · configuration ${run.configuration_revision_id}`, { exact: true })).toBeVisible();
  });
}

test('explicit configuration runs once and retained history copies only into a draft', async ({ page }) => {
  test.setTimeout(180000);
  const traffic: string[] = [];
  page.on('request', r => { if (['fetch', 'xhr'].includes(r.resourceType())) traffic.push(`${r.method()} ${r.url()}`); });
  await setup(page);
  await configurationView(page);
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Configuration', exact: true })).toBeVisible();
  await page.getByLabel('Configuration name', { exact: true }).fill('Explicit inputs');
  await page.getByLabel('First · x value', { exact: true }).fill('2');
  await page.getByLabel('First · x provenance', { exact: true }).fill('Manually specified for this rehearsal.');
  await page.getByLabel('First · z value', { exact: true }).fill('3');
  await page.getByLabel('First · z provenance', { exact: true }).fill('Second explicit rehearsal input.');
  await page.getByText('Criteria', { exact: true }).click();
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await page.getByRole('combobox', { name: 'Criterion 1 output', exact: true }).selectOption({ label: 'Second · y' });
  await page.getByLabel('Criterion 1 threshold', { exact: true }).fill('30');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  await readyToRun(page);
  await page.getByRole('button', { name: 'Run model', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible({ timeout: 120000 });
  await expect(page.getByRole('region', { name: 'Run details' })).toContainText('Execution: finished');
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const list = (await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data;
  expect(list).toHaveLength(1);
  const first = (await (await page.request.get(`/api/1/studies/${sid}/runs/${list[0].run_id}`)).json()).data;
  expect(first.history.results.outputs.every((o: { availability: string }) => o.availability === 'available')).toBeTruthy();
  expect(first.history.results.outputs.map((o: { value: number }) => o.value).sort((a: number, b: number) => a - b)).toEqual([5, 25]);
  expect(first.history.results.criteria[0].outcome).toBe('met');
  await page.getByRole('button', { name: 'Create new version', exact: true }).click();
  await expect(page.getByText('Configuration copied to an unsaved draft. No run submitted.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeDisabled();
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(1);
  await page.getByLabel('First · x value', { exact: true }).fill('4');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  await readyToRun(page);
  await page.getByRole('button', { name: 'Run model', exact: true }).click();
  await expect.poll(async () => {
    const rows = (await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data;
    if (rows.length < 2) return false;
    const run = (await (await page.request.get(`/api/1/studies/${sid}/runs/${rows[1].run_id}`)).json()).data;
    return run.history?.results?.outputs.some((o: { value: number }) => o.value === 49) ?? false;
  }, { timeout: 120000 }).toBeTruthy();
  await page.getByRole('button', { name: `Inspect run ${list[0].run_id}`, exact: true }).click();
  await expect(page.getByRole('region', { name: 'Run details' })).toContainText('Execution: finished');
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs/${list[0].run_id}`)).json()).data).toEqual(first);
  await page.getByText('Run status and diagnostics', { exact: true }).click();
  await page.screenshot({ path: evidencePath('run-history-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 720, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: evidencePath('run-history-reflow.png'), fullPage: true });
  writeFileSync(evidencePath('run-history-public-requests.json'), JSON.stringify(traffic, null, 2));
  writeFileSync(evidencePath('run-history-record.json'), JSON.stringify(first, null, 2));
  expect(traffic.every(r => r.split(' ')[1].startsWith(servedOrigin() + '/api/1/'))).toBeTruthy();
});

test('retained history keyboard controls and stable desktop/narrow captures use read-only requests', async ({ page }) => {
  const retained = JSON.parse(readFileSync(evidencePath('run-history-record.json'), 'utf8'));
  const sid = retained.history.configuration.study_id;
  await login(page);
  let posts = 0; page.on('request', r => { if (r.method() === 'POST') posts++; });
  await page.getByRole('combobox', { name: 'Study', exact: true }).selectOption(sid);
  await page.getByRole('combobox', { name: 'Model', exact: true }).selectOption(retained.history.configuration.model_id);
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  const inspect = page.getByRole('button', { name: `Inspect run ${retained.run_id}`, exact: true });
  await inspect.focus(); await inspect.press('Enter');
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible();
  const outcomes = page.getByText('Run status and diagnostics', { exact: true });
  await outcomes.focus(); await outcomes.press('Enter');
  await expect(page.getByText('Optimization termination', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Run details' })).toContainText('Second · y ≤ 30 dimensionless: Met');
  await page.getByRole('region', { name: 'Run details' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: evidencePath('history-desktop-viewport.png') });
  await page.setViewportSize({ width: 720, height: 900 });
  await page.waitForTimeout(300);
  await page.getByRole('heading', { name: 'Outputs', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: evidencePath('history-narrow-viewport.png') });
  await page.getByRole('button', { name: 'Create new version', exact: true }).click();
  await expect(page.getByText('Configuration copied to an unsaved draft. No run submitted.', { exact: true })).toBeVisible();
  await page.getByLabel('First · x value', { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: evidencePath('configuration-narrow-viewport.png') });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(posts).toBe(0);
});

test('missing, zero, negative and incompatible units retain drafts and guard navigation', async ({ page }) => {
  await setup(page);
  await configurationView(page);
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Zero and negative');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Enter an explicit value.');
  await page.getByLabel('First · x value', { exact: true }).fill('0');
  await page.getByLabel('First · z value', { exact: true }).fill('-3');
  for (const name of ['x', 'z']) await page.getByLabel(`First · ${name} provenance`, { exact: true }).fill('Explicit signed input.');
  await page.getByLabel('First · x units', { exact: true }).fill('m');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('First · x value', { exact: true })).toHaveValue('0');
  await expect(page.getByLabel('First · z value', { exact: true })).toHaveValue('-3');
  await page.getByLabel('First · x units', { exact: true }).fill('');
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Unsaved changes' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Model', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const configs = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data;
  expect(configs[0].configuration.inputs.map((i: { value: number }) => i.value).sort()).toEqual([-3, 0]);
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(0);
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["u"] = inputs["x"] + inputs["z"] + 1\n');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await applyChanges(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await configurationView(page);
  await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeDisabled();
  await expect(page.getByText('The model draft changed. Commit its current snapshot and review compatibility.', { exact: true })).toBeVisible();
  await page.getByLabel('Configuration name', { exact: true }).fill('Unsaved config');
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await page.getByText('Study context', { exact: true }).click();
  await page.getByLabel('Description', { exact: true }).fill('Unsaved study');
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await expect(page.getByLabel('Description', { exact: true })).toHaveValue('');
});

test('no-free-input model runs and a lost submission response reconciles the same command', async ({ page }) => {
  test.setTimeout(180000); await setup(page);
  await page.getByLabel('New model name').fill('Constant');
  await page.getByLabel('Starting model').selectOption('empty');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByText('Add a component to start.', { exact: true })).toBeVisible();
  await openModelTools(page);
  await page.getByLabel('New component name').fill('Constant');
  await page.getByLabel('Input symbols').fill(''); await page.getByLabel('Output symbols').fill('y');
  await page.getByRole('button', { name: 'Add component', exact: true }).click();
  await applyChanges(page);
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["y"] = 0\n');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await applyChanges(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await configurationView(page);
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByText('No inputs required.', { exact: true })).toBeVisible();
  await page.getByLabel('Configuration name', { exact: true }).fill('Declared constant equation');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  let submissions = 0;
  await page.route(`**/api/1/studies/${sid}/runs`, async route => { if (route.request().method() === 'POST') { submissions++; await route.fetch(); await route.abort('failed'); } else await route.continue(); });
  await readyToRun(page);
  await page.getByRole('button', { name: 'Run model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Check original command', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible({ timeout: 120000 });
  expect(submissions).toBe(1);
  await expect(page.getByRole('region', { name: 'Output values' })).toContainText('0');
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(1);
});

test('downstream failure keeps upstream evidence, unresolved criteria and model-independent history', async ({ page }) => {
  test.setTimeout(180000); await setup(page);
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select Second', exact: true }).click();
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('raise RuntimeError("deliberate downstream failure")\n');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await applyChanges(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await configurationView(page);
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Partial result');
  for (const name of ['x', 'z']) {
    await page.getByLabel(`First · ${name} value`, { exact: true }).fill(name === 'x' ? '2' : '3');
    await page.getByLabel(`First · ${name} provenance`, { exact: true }).fill('Explicit partial-result rehearsal.');
  }
  await page.getByText('Criteria', { exact: true }).click();
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await page.getByRole('combobox', { name: 'Criterion 1 output', exact: true }).selectOption({ label: 'Second · y' });
  await page.getByLabel('Criterion 1 threshold', { exact: true }).fill('30');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  await readyToRun(page);
  await page.getByRole('button', { name: 'Run model', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible({ timeout: 120000 });
  const details = page.getByRole('region', { name: 'Run details' });
  await expect(details).toContainText('Execution: failed'); await expect(details).toContainText('Unresolved');
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const rows = (await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data;
  const original = (await (await page.request.get(`/api/1/studies/${sid}/runs/${rows[0].run_id}`)).json()).data;
  expect(original.history.results.outputs.some((o: { value: number | null; availability: string }) => o.value === null && o.availability === 'unavailable')).toBeTruthy();
  expect(original.history.results.outputs.some((o: { value: number }) => o.value === 5)).toBeTruthy();
  await page.route(`**/api/1/studies/${sid}/models/**`, route => route.abort('failed'));
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh model', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: `Inspect run ${rows[0].run_id}`, exact: true }).click();
  await page.getByRole('button', { name: 'Refresh run status', exact: true }).click();
  await expect(details).toContainText('Execution: failed');
  await page.getByRole('tab', { name: 'Model and inputs', exact: true }).click();
  await page.getByText('Exact snapshots, source, context and dependencies', { exact: true }).click();
  await expect(details).toContainText('deliberate downstream failure');
  const artifact = original.history.artifacts.find((a: { name: string }) => a.name.startsWith('sources/'));
  await page.getByRole('tab', { name: 'Artifacts', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: `Download ${artifact.name}`, exact: true }).click();
  expect(readFileSync((await (await download).path())!).length).toBe(artifact.size);
  // Rendering-only fault overlays use an actual retained record; they do not alter retained storage.
  for (const [code, copy] of [['missing_results', 'Some results were not retained.'], ['missing_artifacts', 'This run file is unavailable.'], ['corrupt_retained_record', 'Some retained evidence could not be verified.'], ['unsupported_record_version', 'This retained record uses a version']]) {
    await page.route(`**/api/1/studies/${sid}/runs/${rows[0].run_id}`, async route => { await route.fulfill({ json: { schema_version: '1', data: { ...original, history: { ...original.history, errors: [{ code, partial: true }], results: code === 'missing_results' ? null : original.history.results } } } }); });
    await page.getByRole('button', { name: 'Refresh run status', exact: true }).click();
    await expect(details).toContainText(copy);
    await page.unroute(`**/api/1/studies/${sid}/runs/${rows[0].run_id}`);
  }
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(1);
});
