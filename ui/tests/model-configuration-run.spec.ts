import { test, expect, type Page, type Locator } from 'playwright/test';
import { startFixture, stopFixture, guardOrigin, harness, login, sid, mid, referenceModel, runFixture, details } from './foundry-fixtures';

test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture);
test.beforeEach(async ({ page }) => { await guardOrigin(page); });
test.afterAll(stopFixture);
async function capture(page: Page, name: string) {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ animations: 'disabled', path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/n47-${name}-${colorScheme}.png` });
  }
}
// Criteria render as numbered records since 261010-kpx-03 (formerly one .criterion-summary line).
async function expectAtMostTen(scope: Locator) {
  const record = scope.getByRole('article', { name: 'Criterion 1', exact: true });
  await expect(record.locator('.hf-criterion__target')).toHaveText('Squared response · y');
  await expect(record.locator('.hf-criterion__requirement')).toContainText('at most');
  await expect(record.locator('.hf-criterion__number')).toHaveText('10');
  await expect(record.locator('.hf-criterion__requirement .hf-criterion__unit')).toHaveText(/^dimensionless$/i);
}
test('model quantities inspect their component; tables, XDSM and portability stay concise', async ({ page }) => {
  const state = await harness(page);
  referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.locator('.hf-node__port').first().click();
  // Details explain the component (What it computes · Why · Assumptions); no ports table or tabs.
  await expect(
    details(page).getByRole('heading', { name: 'Method context', exact: true }),
  ).toHaveCount(0);
  await expect(
    details(page).getByRole('heading', { name: 'Why this method', exact: true }),
  ).toHaveCount(0);
  await expect(details(page).locator('[data-selected-variable]')).toHaveCount(0);
  await expect(details(page).locator('table')).toHaveCount(0);
  await expect(details(page).getByRole('tab')).toHaveCount(0);
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Reload model', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByText('Source and composition', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Show Variables below diagram')).toHaveCount(0);
  await capture(page, 'model');
  // Component scope does not imply every quantity is individually selected.
  await expect(page.getByRole('tab', { name: 'Variables', exact: true })).toHaveCount(0);
  await expect(
    page.getByRole('table', { name: 'Quantities', exact: true }).getByRole('columnheader'),
  ).toHaveText(['Quantity', 'Component', 'Direction', 'Definition', 'Unit']);
  await expect(page.locator('[data-variable]')).toHaveCount(3);
  await expect(page.locator('[data-variable][aria-selected="true"]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Clear selection', exact: true }).click();
  await expect(details(page).getByRole('heading', { name: 'Model', exact: true })).toBeVisible();
  await expect(page.locator('[data-variable][aria-selected]')).toHaveCount(0);
  await expect(page.locator('[data-variable]')).toHaveCount(5);
  await expect(page.getByText('from Linear response · u', { exact: true })).toBeVisible();
  await capture(page, 'variables');
  if (!(await page.getByRole('dialog', { name: 'Model actions', exact: true }).isVisible()))
    await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  const downloading = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Quantities CSV', exact: true }).click();
  const download = await downloading;
  const content = await (
    await import('node:fs/promises')
  ).readFile((await download.path())!, 'utf8');
  expect(content).toContain('Connections');
  expect(content).toContain('a/u');
  await page.getByRole('button', { name: 'Close Export model and data', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: 'XDSM', exact: true }).click();
  await expect(page.locator('.xdsm-exchange button')).toHaveText('1 connectionu → u');
  expect(
    await page.locator('.xdsm-exchange button').evaluate((e) => getComputedStyle(e).flexDirection),
  ).toBe('column');
  await capture(page, 'xdsm');
  if (!(await page.getByRole('dialog', { name: 'Model actions', exact: true }).isVisible()))
    await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Import', exact: true }).click();
  await expect(
    page
      .getByRole('dialog', { name: 'Import', exact: true })
      .getByRole('button', { name: 'Choose file' }),
  ).toBeVisible();
  await capture(page, 'import');
  await page.getByRole('button', { name: 'Close Import', exact: true }).click();
  if (!(await page.getByRole('dialog', { name: 'Model actions', exact: true }).isVisible()))
    await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download portable model record' })).toBeDisabled();
  await capture(page, 'export');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('configuration fields align; one criterion persists visibly; saved layout survives navigation', async ({ page }) => {
  const state = await harness(page); referenceModel(state); state.ready = true;
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.getByRole('button', { name: 'Create configuration', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Engineering baseline');
  for (const [symbol, value] of [['x', '0'], ['z', '3']]) {
    await page.getByLabel(`Linear response · ${symbol} value`, { exact: true }).fill(value);
    await page.getByLabel(`Linear response · ${symbol} provenance`, { exact: true }).fill('Analytical reference');
    // Input units are an explicit choice; the model quantity is Dimensionless.
    await page.getByLabel(`Linear response · ${symbol} units`, { exact: true }).selectOption('dimensionless');
  }
  const tops = await page.locator('.configuration-inputs tbody tr').first().locator('input').evaluateAll(es => es.map(e => e.getBoundingClientRect().top));
  expect(Math.max(...tops) - Math.min(...tops)).toBeLessThan(2);
  await expect(page.locator('.configuration-inputs .hf-field__tag')).toHaveCount(0);
  const criteria = page.locator('.configuration-criterion');
  await criteria.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await expect(page.locator('.criterion-row')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Add another criterion', exact: true })).toBeDisabled();
  await page.getByLabel('Criterion 1 output', { exact: true }).selectOption('b/y');
  await page.getByLabel('Criterion 1 operator', { exact: true }).selectOption({ label: 'at most' });
  await page.getByLabel('Criterion 1 threshold', { exact: true }).fill('10');
  // Criterion units are an explicit choice.
  await page.getByLabel('Criterion 1 units', { exact: true }).selectOption('dimensionless');
  await page.getByRole('dialog', { name: 'Edit criteria', exact: true }).getByRole('button', { name: 'Done', exact: true }).click();
  await expectAtMostTen(criteria);
  await criteria.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.locator('.criterion-row')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await capture(page, 'configuration-draft');
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  const saved = page.getByRole('region', { name: 'Saved configuration', exact: true });
  await expect(saved).toBeVisible();
  await expect(saved.getByRole('button', { name: 'Run this configuration', exact: true })).toBeEnabled();
  await expectAtMostTen(saved);
  const headings = await saved.getByRole('heading', { level: 3 }).allTextContents();
  // Current saved composition: context first (261010-kpx-03), approach (02-20), assumptions (02-13).
  // Model assumptions are one line with View model assumptions, not a repeated section.
  expect(headings).toEqual(['Inputs and provenance', 'Criteria']);
  await saved.getByRole('button', { name: 'Configuration record details', exact: true }).click();
  const record = page.getByLabel('Saved configuration JSON', { exact: true });
  const content = JSON.parse((await record.textContent())!);
  expect(content.context_snapshot).toEqual(state.configurations[0].configuration.context_snapshot);
  expect(content.schema_version).toBe('3');
  expect(content.assumptions).toEqual([]);
  await page.getByRole('button', { name: 'Close Configuration record', exact: true }).click();
  await capture(page, 'configuration-saved');
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
  await expect(saved).toBeVisible();
  expect(await saved.getByRole('heading', { level: 3 }).allTextContents()).toEqual(headings);
  await expect(saved.getByRole('button', { name: 'Run this configuration', exact: true })).toBeEnabled();
  expect(state.configurations[0].configuration.criteria).toHaveLength(1);
  expect(state.writes.filter(w => w.path.endsWith('/runs'))).toHaveLength(0);
  expect(state.unknown).toEqual([]);
});

test('run progress updates automatically, recovers a failed read, and never resubmits', async ({ page }) => {
  const state = await harness(page);
  const finished = structuredClone(runFixture(state));
  state.detail = { ...finished, state: 'accepted_run', history: null, process_state: undefined };
  let reads = 0;
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture`, (route) => {
    reads++;
    if (reads === 2)
      return route.fulfill({
        status: 503,
        json: {
          error: {
            code: 'backend_unavailable',
            message: 'Temporary read failure',
            fields: [],
            outcome: 'unchanged',
          },
        },
      });
    return route.fulfill({ json: { schema_version: '1', data: state.detail } });
  });
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const progress = page.getByRole('progressbar');
  await expect(progress).toHaveAttribute('aria-label', 'Queued for preparation');
  await expect(progress).not.toHaveAttribute('value');
  await capture(page, 'run-queued');
  await expect(
    page.getByText('Connection interrupted. Retrying status updates automatically.'),
  ).toBeVisible();
  state.detail = { ...state.detail, state: 'recorded', process_state: 'running' };
  await expect(progress).toHaveAttribute('aria-label', 'Calculation running');
  await capture(page, 'run-running');
  state.detail = finished;
  await expect(progress).toHaveCount(0);
  await expect(
    page.getByRole('list', { name: 'Run status', exact: true }).locator('.hf-facet__k'),
  ).toHaveText(['Execution', 'Criteria']);
  const outputs = page.getByRole('region', { name: 'Output values', exact: true });
  await expect(outputs.getByRole('columnheader')).toHaveText(['Output', 'Value', 'Units']);
  await expect(outputs).toContainText('not computed: Producer failed');
  await expect(page.locator('.run-panel .run-key-outputs')).toHaveCount(0);
  await expect(outputs.locator('tbody tr')).toHaveCount(finished.history.results.outputs.length);
  await capture(page, 'run-partial');
  const completedReads = reads;
  await page.waitForTimeout(1800);
  expect(reads).toBe(completedReads);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('component and connection dialogs close only after successful atomic apply', async ({ page }) => {
  const state = await harness(page); referenceModel(state);
  const commands: any[] = [];
  await page.route(`**/api/1/studies/${sid}/models/${mid}/{preview,edits}`, async route => {
    const body = route.request().postDataJSON(); const next = structuredClone(state.model);
    for (const edit of body.edits) {
      if (edit.kind === 'create_definition') {
        next.definitions.push({ definition_id: 'new-definition', definition_version_id: 'new-version', definition_kind: edit.definition_kind, name: edit.name, ports: edit.ports.map((p: any) => ({ ...p, port_id: p.code_symbol })), source_refs: [edit.source.sha256], annotations: [] });
        next.source_files.push(edit.source);
      }
      if (edit.kind === 'instantiate') next.instances.push({ instance_id: 'new-instance', definition_version_id: 'new-version', name: next.definitions.at(-1)!.name });
      if (edit.kind === 'connect') next.connections.push({ connection_id: 'new-connection', source_ref: edit.source_ref, target_ref: edit.target_ref });
    }
    if (route.request().url().endsWith('/edits')) { commands.push(body); next.draft_revision = 'draft-' + commands.length; state.model = next; }
    await route.fulfill({ json: { schema_version: '1', data: next } });
  });
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.getByRole('button', { name: '＋ Component', exact: true }).click();
  await page.getByLabel('New component name').fill('Independent component');
  await page.getByLabel('Input symbols', { exact: true }).fill('v');
  await page.getByLabel('Output symbols', { exact: true }).fill('w');
  await page.getByRole('button', { name: 'Add component', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true });
  await expect(preview).toContainText('Independent component');
  await expect(preview).not.toContainText('expected draft');
  await capture(page, 'component-preview');
  await preview.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Add component', exact: true })).toBeHidden();
  await expect(page.locator('.connected-graph [data-instance="new-instance"]')).toBeVisible();
  await page.getByRole('button', { name: 'Connect quantities', exact: true }).click();
  await page.getByLabel('Connection output', { exact: true }).selectOption('b/y');
  await page.getByLabel('Connection input', { exact: true }).selectOption('new-instance/v');
  await expect(page.getByRole('button', { name: 'Queue connection', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Review connection', exact: true }).click();
  await expect(preview).toContainText('Squared response · y → Independent component · v');
  await preview.getByRole('button', { name: 'Connect quantities', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Connections', exact: true })).toBeHidden();
  expect(commands).toHaveLength(2);
  expect(commands[0].edits.map((e: any) => e.kind)).toEqual(['create_definition', 'instantiate']);
  expect(commands[1].edits.map((e: any) => e.kind)).toEqual(['connect']);
});

test('saved configuration remains identical after a run and permits another explicit run', async ({ page }) => {
  const state = await harness(page); const run = runFixture(state);
  run.history.configuration.inputs[0].provenance.evidence_version_ids = [];
  const saved = { configuration: run.history.configuration, model_snapshot: run.history.model_snapshot };
  state.configurations = [saved]; state.ready = true;
  await login(page, `#v=1&study=${sid}&view=configurations&configuration=${saved.configuration.configuration_revision_id}`);
  const panel = page.getByRole('region', { name: 'Saved configuration', exact: true });
  await expect(panel).toBeVisible();
  const before = await panel.getByRole('heading').allTextContents();
  await page.getByRole('button', { name: 'Run this configuration', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Run status', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
  await expect(panel).toBeVisible();
  expect(await panel.getByRole('heading').allTextContents()).toEqual(before);
  await expect(page.getByRole('button', { name: 'Run this configuration', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Run this configuration', exact: true }).click();
  await expect.poll(() => state.writes.filter(w => w.path.endsWith('/runs')).length).toBe(2);
  const submissions = state.writes.filter(w => w.path.endsWith('/runs'));
  expect(submissions[0].body.configuration_revision_id).toBe(submissions[1].body.configuration_revision_id);
  expect(submissions[0].body.command_id).not.toBe(submissions[1].body.command_id);
  expect(state.configurations[0]).toEqual(saved); expect(state.unknown).toEqual([]);
});

test('long source symbols preserve case and leave port units readable', async ({ page }) => {
  const state = await harness(page); referenceModel(state);
  state.model.definitions[0].ports[0].code_symbol = 'future_hydrogen_price';
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  (state.model.definitions[0] as any).quantity_definitions = [{ port_id: state.model.definitions[0].ports[0].port_id, statement: 'Projected delivered hydrogen price for the long-term operating horizon, including transport and storage' }];
  // The 350px inspector ports table is gone by construction; the quantities table keeps units readable.
  await expect(details(page).locator('table')).toHaveCount(0);
  const table = page.getByRole('table', { name: 'Quantities', exact: true });
  await expect(table.locator('thead th')).toHaveText(['Quantity', 'Component', 'Direction', 'Definition', 'Unit']);
  for (const width of [1440, 720, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    // Units (column 5) stay on one line inside their own cell; they are never overlapped.
    const cells = await table.locator('tbody td:nth-child(5)').evaluateAll(es => es.map(e => { const r = document.createRange(); r.selectNodeContents(e); return { text: e.textContent, lines: r.getClientRects().length, fits: e.scrollWidth <= e.clientWidth }; }));
    expect(cells.length).toBeGreaterThan(0);
    expect(cells.every(c => c.lines === 1 && c.fits), JSON.stringify(cells)).toBe(true);
    // The definition (column 4) wraps inside its own cell instead of overflowing onto Unit.
    const definitions = await table.locator('tbody td:nth-child(4)').evaluateAll(es => es.map(e => { const r = document.createRange(); r.selectNodeContents(e); const text = r.getBoundingClientRect(), cell = e.getBoundingClientRect(); return { fits: e.scrollWidth <= e.clientWidth, inside: text.right <= cell.right + 1, lines: r.getClientRects().length }; }));
    expect(definitions.every(c => c.fits && c.inside), JSON.stringify(definitions)).toBe(true);
    // In its fixed-width column the long definition must wrap rather than overflow.
    if (width === 1440) expect(definitions.some(c => c.lines > 1)).toBe(true);
    await table.scrollIntoViewIfNeeded(); await page.screenshot({ animations: 'disabled', path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/n47-port-table-${width}.png` });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(await page.locator('[data-variable="a/x"] code').evaluate(e => getComputedStyle(e).textTransform)).toBe('none');
  await capture(page, 'long-symbols');
});

// One canonical model view. Run › Model shows the run's values in the quantities table
// ("not computed" when missing, 0 as an explicit value); a saved configuration opens the same view.
async function s4Shot(page: Page, name: string, target: Locator) {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await target.evaluate(element => element.scrollIntoView({ block: 'start' }));
    await page.screenshot({ animations: 'disabled', path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/s4-${name}-${colorScheme}.png` });
  }
  await page.emulateMedia({ colorScheme: 'light' });
}
test('run Model tab and saved configuration View model version reuse the canonical model view with values', async ({ page }) => {
  const state = await harness(page); const run = runFixture(state);
  run.history.configuration.inputs[0].provenance.evidence_version_ids = [];
  state.configurations = [{ configuration: run.history.configuration, model_snapshot: run.history.model_snapshot }];
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Models', exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Model', exact: true }).click();
  const view = page.getByRole('tabpanel', { name: 'Model', exact: true }).getByRole('region', { name: 'Model view', exact: true });
  const table = view.getByRole('table', { name: 'Quantities', exact: true }), inspector = view.getByRole('region', { name: 'Selection inspector', exact: true });
  await expect(table.getByRole('columnheader')).toHaveText(['Quantity', 'Component', 'Direction', 'Definition', 'Unit', 'Value', 'Provenance']);
  await expect(view.getByRole('tab', { name: 'Graph', exact: true })).toBeVisible(); await expect(view.getByRole('tab', { name: 'XDSM', exact: true })).toBeVisible();
  await expect(inspector.getByRole('heading', { name: 'Model', exact: true })).toBeVisible();
  await expect(inspector).toContainText('Model versions saved in this older format have no assumptions.');
  await expect(table.locator('[data-variable]')).toHaveCount(5);
  await expect(table.locator('[data-variable="a/x"] .numeric-value')).toHaveText('0');
  await expect(table.locator('[data-variable="a/x"]')).toContainText('Explicit recorded zero');
  await expect(table.locator('[data-variable="a/z"] td.missing')).toHaveText('unassigned');
  await expect(table.locator('[data-variable="a/u"] .numeric-value')).toHaveText('0');
  await expect(table.locator('[data-variable="b/u"]')).toContainText('From Linear response · u');
  await expect(table.locator('[data-variable="b/y"] td.missing')).toHaveText('not computed');
  await expect(table.locator('[data-variable="b/y"]')).toContainText('Producer failed');
  await expect(
    view.getByRole('combobox', { name: 'Availability filter', exact: true }),
  ).toHaveCount(0);
  await expect(view.getByRole('button', { name: 'Components', exact: true })).toHaveCount(0);
  await expect(view.getByRole('region', { name: 'Model components', exact: true })).toHaveCount(0);
  await view
    .getByRole('combobox', { name: 'Direction filter', exact: true })
    .selectOption('output');
  await expect(table.locator('[data-variable]')).toHaveCount(2);
  await expect(table.locator('[data-variable="b/y"]')).toContainText('Producer failed');
  await view.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect(table.locator('[data-variable]')).toHaveCount(5);
  await s4Shot(page, 'run-model', view);
  await table.getByRole('button', { name: 'Inspect component Squared response', exact: true }).first().click();
  await expect(inspector.getByRole('heading', { name: 'Squared response', exact: true })).toBeVisible();
  await expect(inspector.getByRole('heading', { name: 'Method context', exact: true })).toHaveCount(
    0,
  );
  await expect(
    inspector.getByRole('heading', { name: 'Why this method', exact: true }),
  ).toHaveCount(0);
  await expect(inspector.locator('details.component-source > summary')).toHaveText(
    'Python function',
  );
  await expect(inspector.locator('table')).toHaveCount(0);
  await expect(table.locator('[data-variable]')).toHaveCount(2);
  await expect(view.getByRole('button', { name: 'Show all quantities', exact: true })).toBeVisible();
  await s4Shot(page, 'run-model-component', view);
  await view.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await expect(table.locator('[data-variable]')).toHaveCount(5);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
  await expect(page.getByText('Inspect recorded model', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'View model version', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Model version ' + run.history.configuration.model_revision_id.slice(0, 8), exact: true });
  const configured = dialog.getByRole('region', { name: 'Model view', exact: true }).getByRole('table', { name: 'Quantities', exact: true });
  await expect(configured.getByRole('columnheader')).toHaveText(['Quantity', 'Component', 'Direction', 'Definition', 'Unit', 'Value', 'Provenance']);
  if (await dialog.getByRole('button', { name: 'Show all quantities', exact: true }).isVisible()) await dialog.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await expect(configured.locator('[data-variable="a/x"] .numeric-value')).toHaveText('0');
  await expect(configured.locator('[data-variable="b/y"] td.missing')).toHaveText('computed when run');
  await s4Shot(page, 'configuration-model-version', dialog);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'View model version', exact: true })).toBeFocused();
  expect(state.unknown).toEqual([]); expect(state.writes).toEqual([]);
});
