import { test, expect, type Page, type Locator } from 'playwright/test';
import { startFixture, stopFixture, guardOrigin, harness, login, sid, mid, referenceModel, runFixture, details } from './foundry-fixtures';

test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture);
test.beforeEach(async ({ page }) => { await guardOrigin(page); });
test.afterAll(stopFixture);
async function capture(page: Page, name: string) {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.evaluate(theme => document.documentElement.dataset.theme = theme, colorScheme);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ animations: 'disabled', path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/n47-${name}-${colorScheme}.png` });
  }
}
/** New configurations need the current model format: a Model4 version with typed units. */
function currentModelFormat(state: Awaited<ReturnType<typeof harness>>) {
  const model = state.model as any;
  model.schema_version = '4'; model.assumptions = [];
  model.required_capabilities = ['unit_declarations/1', 'quantity_definitions/1'];
  for (const definition of model.definitions) {
    definition.quantity_definitions = [];
    for (const port of definition.ports) port.units = { kind: 'dimensionless' };
  }
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
  await expect(page.getByRole('button', { name: 'Refresh model', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByText('Source and composition', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Show Variables below diagram')).toHaveCount(0);
  await capture(page, 'model');
  // Component scope does not imply every quantity is individually selected.
  await expect(page.getByRole('tab', { name: 'Variables', exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await expect(
    page.getByRole('table', { name: 'Quantities', exact: true }).getByRole('columnheader'),
  ).toHaveText(['Quantity', 'Direction', 'Unit', 'Actions']);
  await expect(page.locator('[data-variable]')).toHaveCount(3);
  await expect(page.locator('[data-variable][aria-selected="true"]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Clear selection', exact: true }).click();
  await page.getByRole('tab', { name: 'Component', exact: true }).click();
  await expect(
    details(page).getByRole('heading', { name: 'Model', exact: true }).last(),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await expect(page.locator('[data-variable][aria-selected]')).toHaveCount(0);
  await expect(page.locator('[data-variable]')).toHaveCount(5);
  await expect(page.getByText('from Linear response · u', { exact: true })).toBeVisible();
  await capture(page, 'variables');
  if (!(await page.getByRole('dialog', { name: 'Model actions', exact: true }).isVisible()))
    await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
  const downloading = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Quantities CSV', exact: true }).click();
  const download = await downloading;
  const content = await (
    await import('node:fs/promises')
  ).readFile((await download.path())!, 'utf8');
  expect(content).toContain('Connections');
  expect(content).toContain('a/u');
  await page.getByRole('button', { name: 'Close Export model', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: 'XDSM', exact: true }).click();
  await expect(page.locator('.xdsm-exchange button')).toHaveText('1 connectionu → u');
  expect(
    await page.locator('.xdsm-exchange button').evaluate((e) => getComputedStyle(e).flexDirection),
  ).toBe('column');
  await capture(page, 'xdsm');
  if (!(await page.getByRole('dialog', { name: 'Model actions', exact: true }).isVisible()))
    await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Import model', exact: true }).click();
  await expect(
    page
      .getByRole('dialog', { name: 'Import model', exact: true })
      .getByRole('button', { name: 'Choose file' }),
  ).toBeVisible();
  await capture(page, 'import');
  await page.getByRole('button', { name: 'Close Import model', exact: true }).click();
  if (!(await page.getByRole('dialog', { name: 'Model actions', exact: true }).isVisible()))
    await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download portable model record' })).toBeDisabled();
  const exportDialog = page.getByRole('dialog', { name: 'Export model', exact: true });
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
      expect(await exportDialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
      await expect(exportDialog.getByRole('region', { name: 'Reusable model' })).toBeVisible();
      await expect(exportDialog.getByRole('region', { name: 'Current view' })).toBeVisible();
    }
  }
  await capture(page, 'export');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('configuration fields align; criteria stay in the study brief; saved layout survives navigation', async ({ page }) => {
  const state = await harness(page); referenceModel(state); currentModelFormat(state); state.ready = true;
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
  // A new configuration authors no criteria: the study brief owns them.
  const draftCriteria = page.locator('.configuration-criterion');
  await expect(draftCriteria).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Add criterion', exact: true })).toHaveCount(0);
  await capture(page, 'configuration-draft');
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  const saved = page.getByRole('region', { name: 'Saved configuration', exact: true });
  await expect(saved).toBeVisible();
  await expect(saved.getByRole('button', { name: 'Run this configuration', exact: true })).toBeEnabled();
  await expect(saved.locator('.configuration-criterion')).toHaveCount(0);
  await expect(saved.getByRole('article', { name: 'Criterion 1', exact: true })).toHaveCount(0);
  const headings = await saved.getByRole('heading', { level: 3 }).allTextContents();
  // Model assumptions are one line with View model assumptions, not a repeated section.
  expect(headings).toEqual(['Inputs and provenance']);
  await saved.getByRole('button', { name: 'Configuration record details', exact: true }).click();
  const record = page.getByLabel('Saved configuration JSON', { exact: true });
  const content = JSON.parse((await record.textContent())!);
  expect(content.context_snapshot).toEqual(state.configurations[0].configuration.context_snapshot);
  expect(content.schema_version).toBe('6');
  expect(content).not.toHaveProperty('criteria');
  expect(content.assumptions).toEqual([]);
  await page.getByRole('button', { name: 'Close Configuration record', exact: true }).click();
  await capture(page, 'configuration-saved');
  await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
  await expect(saved).toBeVisible();
  expect(await saved.getByRole('heading', { level: 3 }).allTextContents()).toEqual(headings);
  await expect(saved.getByRole('button', { name: 'Run this configuration', exact: true })).toBeEnabled();
  const requests = state.writes.filter(w => /\/configurations(\/preview)?$/.test(w.path));
  expect(requests.length).toBeGreaterThan(0);
  for (const { body } of requests) {
    const candidate = body.configuration ?? body;
    expect(candidate.schema_version).toBe('6');
    expect(candidate).not.toHaveProperty('criteria');
    expect(candidate).not.toHaveProperty('approach_selection');
  }
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
  await expect(progress).toHaveAttribute('aria-label', 'Analysis running');
  await capture(page, 'run-running');
  state.detail = finished;
  await expect(progress).toHaveCount(0);
  await expect(
    page.getByLabel('Execution summary', { exact: true }).locator('dt'),
  ).toHaveText(['Status', 'Operation']);
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
  await expect(page.getByLabel('Execution summary', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
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
  (state.model.definitions[0] as any).quantity_definitions = [{ port_id: state.model.definitions[0].ports[0].port_id, statement: 'Projected delivered hydrogen price for the long-term operating horizon, including transport and storage' }];
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  // The 350px inspector ports table is gone by construction; the quantities table keeps units readable.
  await expect(details(page).locator('table')).toHaveCount(0);
  await page.getByRole('tab', {name: 'Quantities', exact: true}).click();
  const table = page.getByRole('table', { name: 'Quantities', exact: true });
  await expect(table.locator('thead th')).toHaveText([
    'Quantity', 'Direction', 'Definition', 'Unit', 'Actions',
  ]);
  await expect(table.getByText('No definition', { exact: true })).toHaveCount(2);
  await expect(page.getByText('No quantity definitions provided.', { exact: true })).toHaveCount(0);
  for (const width of [1440, 720, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    // Units stay on one line inside their own cell; they are never overlapped.
    const cells = await table.locator('tbody td.unit').evaluateAll(es => es.map(e => {
      const r = document.createRange();
      r.selectNodeContents(e);
      return { text: e.textContent, lines: r.getClientRects().length,
        fits: e.scrollWidth <= e.clientWidth };
    }));
    expect(cells.length).toBeGreaterThan(0);
    expect(cells.every(c => c.lines === 1 && c.fits), JSON.stringify(cells)).toBe(true);
    // Definitions wrap inside their own cells instead of overflowing onto Unit.
    const definitions = await table.locator('tbody td.quantity-definition')
      .evaluateAll(es => es.map(e => {
        const r = document.createRange();
        r.selectNodeContents(e);
        const text = r.getBoundingClientRect(), cell = e.getBoundingClientRect();
        return { fits: e.scrollWidth <= e.clientWidth, inside: text.right <= cell.right + 1,
          lines: r.getClientRects().length };
      }));
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
    await page.evaluate(theme => document.documentElement.dataset.theme = theme, colorScheme);
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
  await view.getByRole('tab', {name: 'Quantities', exact: true}).click();
  await expect(table.getByRole('columnheader')).toHaveText([
    'Quantity', 'Component', 'Direction', 'Unit', 'Value', 'Provenance',
  ]);
  await expect(view.getByRole('tab', { name: 'Graph', exact: true })).toBeVisible(); await expect(view.getByRole('tab', { name: 'XDSM', exact: true })).toBeVisible();
  await view.getByRole('tab', {name: 'Component', exact: true}).click();
  await expect(inspector.getByRole('heading', { name: 'Model', exact: true }).last()).toBeVisible();
  await expect(inspector).toContainText('Model versions saved in this older format have no assumptions.');
  await view.getByRole('tab', {name: 'Quantities', exact: true}).click();
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
  await view.getByRole('tab', {name: 'Quantities', exact: true}).click();
  await expect(table.locator('[data-variable]')).toHaveCount(5);
  await s4Shot(page, 'run-model', view);
  await table.getByRole('button', { name: 'Inspect component Squared response', exact: true }).first().click();
  await view.getByRole('tab', {name: 'Component', exact: true}).click();
  await expect(inspector.getByRole('heading', { name: 'Squared response', exact: true })).toBeVisible();
  await expect(inspector.getByRole('heading', { name: 'Method context', exact: true })).toHaveCount(
    0,
  );
  await expect(
    inspector.getByRole('heading', { name: 'Why this method', exact: true }),
  ).toHaveCount(0);
  await view.getByRole('tab', {name: 'Python', exact: true}).click();
  await expect(inspector.getByLabel('Read-only authored source')).toBeVisible();
  await view.getByRole('tab', {name: 'Quantities', exact: true}).click();
  await expect(inspector.locator('table')).toHaveCount(0);
  await expect(table.locator('[data-variable]')).toHaveCount(2);
  await expect(view.getByRole('button', { name: 'Show all quantities', exact: true })).toBeVisible();
  await s4Shot(page, 'run-model-component', view);
  await view.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await view.getByRole('tab', {name: 'Quantities', exact: true}).click();
  await expect(table.locator('[data-variable]')).toHaveCount(5);
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
  await expect(page.getByText('Inspect recorded model', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'View model version', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Configuration model', exact: true });
  const configured = dialog.getByRole('region', { name: 'Model view', exact: true }).getByRole('table', { name: 'Quantities', exact: true });
  await dialog.getByRole('tab', {name: 'Quantities', exact: true}).click();
  await expect(configured.getByRole('columnheader')).toHaveText([
    'Quantity', 'Component', 'Direction', 'Unit', 'Value', 'Provenance',
  ]);
  if (await dialog.getByRole('button', { name: 'Show all quantities', exact: true }).isVisible()) await dialog.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await expect(configured.locator('[data-variable="a/x"] .numeric-value')).toHaveText('0');
  await expect(configured.locator('[data-variable="b/y"] td.missing')).toHaveText('computed when run');
  await s4Shot(page, 'configuration-model-version', dialog);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'View model version', exact: true })).toBeFocused();
  expect(state.unknown).toEqual([]); expect(state.writes).toEqual([]);
});

test('long configuration headers leave back navigation reachable and preserve saved formatting', async ({ page }) => {
  const state = await harness(page);
  const { history } = runFixture(state);
  history.configuration.name = 'Kerosene — common 574 tonne screen · 100 passengers · exploration support 21';
  history.configuration.inputs[0] = {
    ...history.configuration.inputs[0], value: 12345.6789, units: 'kg/m**3',
    provenance: { kind: 'manual', statement: 'Explicit saved density for formatting coverage' },
  };
  history.model_snapshot.definitions[0].ports.find((p: { port_id: string }) => p.port_id === 'x')!.units = 'kg/m**3';
  state.configurations.push({ configuration: history.configuration, model_snapshot: history.model_snapshot });
  await login(page, `#v=1&study=${sid}&view=configurations&configuration=${history.configuration.configuration_revision_id}`);
  const saved = page.getByRole('region', { name: 'Saved configuration', exact: true });
  const back = page.getByRole('button', { name: 'Return to all configurations', exact: true });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await back.scrollIntoViewIfNeeded();
    const backBox = (await back.boundingBox())!;
    const headerBox = (await saved.locator('.configuration-header').boundingBox())!;
    expect(headerBox.y).toBeGreaterThanOrEqual(backBox.y + backBox.height);
    await back.click({ trial: true });
    const record = saved.getByRole('button', { name: 'Configuration record details', exact: true });
    await expect(record).toHaveText('Record details');
    const titleBox = (await saved.getByRole('heading', { level: 2 }).boundingBox())!;
    const recordBox = (await record.boundingBox())!;
    expect(recordBox.y).toBeGreaterThanOrEqual(titleBox.y + titleBox.height);
    expect(recordBox.x).toBeLessThan(titleBox.x + titleBox.width);
    await record.click();
    await expect(page.getByRole('dialog', { name: 'Configuration record', exact: true })).toContainText(history.configuration.configuration_revision_id);
    await page.keyboard.press('Escape');
    await expect(record).toBeFocused();

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await expect(saved.getByRole('cell', { name: 'kg/m³', exact: true })).toBeVisible();
  await expect(saved.locator('[title="Full precision: 12345.6789"] .hf-field__ro')).toHaveText('12345.679');
  expect(await saved.locator('.hf-field__ro').first().evaluate(el => getComputedStyle(el).justifyContent)).toBe('flex-end');
  expect(history.configuration.inputs[0].value).toBe(12345.6789);
  expect(history.configuration.inputs[0].units).toBe('kg/m**3');
  await back.click();
  await expect(page.getByRole('button', { name: 'Open configuration', exact: true })).toBeVisible();
  expect(state.writes).toEqual([]);
});

test('run and embedded configuration record controls stay below their own titles', async ({ page }) => {
  const state = await harness(page);
  const run = runFixture(state);
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const heading = page.locator('.run-heading');
  await expect(heading.getByRole('heading', {level:2})).toHaveText(run.history.configuration.name);
  const control = heading.getByRole('button', { name: 'Run record details', exact: true });
  await expect(control).toHaveText('Record details');
  const titleBox = (await heading.getByRole('heading', { level: 2 }).boundingBox())!;
  const controlBox = (await control.boundingBox())!;
  expect(controlBox.y).toBeGreaterThanOrEqual(titleBox.y + titleBox.height);
  await expect(heading.locator('.section-actions').getByRole('button', { name: 'Run record details', exact: true })).toHaveCount(0);
  await control.click();
  await expect(page.getByRole('dialog', { name: 'Run record', exact: true })).toContainText(run.history.configuration.configuration_revision_id);
  await page.keyboard.press('Escape');
  await expect(control).toBeFocused();
  await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
  const child = page.getByRole('tabpanel', { name: 'Configuration', exact: true });
  const childControl = child.getByRole('button', { name: 'Configuration record details', exact: true });
  await expect(childControl).toHaveText('Record details');
  await childControl.click();
  await expect(page.getByRole('dialog', { name: 'Configuration record', exact: true })).toContainText(run.history.configuration.configuration_revision_id);
  await page.keyboard.press('Escape');
  await expect(childControl).toBeFocused();
  expect(state.writes).toEqual([]);
});


test('run commands align with long titles, values align and routine diagnostics stay secondary', async ({ page }) => {
  const state = await harness(page);
  const run = runFixture(state);
  run.history.configuration.name = 'Methane — common 574 tonne screen · 100 passengers · recorded comparison';
  run.execution_diagnostic = { state: 'completed', message: 'Worker exited normally.', elapsed_seconds: 4.9, wall_seconds: 45, artifact_id: null };
  run.history.results.outputs[0].units = 'm**2';
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const heading = page.locator('.run-heading');
  await expect(heading.getByRole('heading', {level:2})).toHaveText(run.history.configuration.name);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const title = (await heading.getByRole('heading', { level: 2 }).boundingBox())!;
    const actions = (await heading.locator('.page-heading > .section-actions').boundingBox())!;
    if (width === 1440) expect(Math.abs(actions.y - title.y)).toBeLessThanOrEqual(1);
    else {
      expect(actions.y).toBeGreaterThan(title.y + title.height);
      expect(Math.abs(actions.x - title.x)).toBeLessThanOrEqual(1);
      const exportAction = (await heading.getByRole('button', { name: 'Export model', exact: true }).boundingBox())!;
      expect(Math.abs(exportAction.x - title.x)).toBeLessThanOrEqual(1);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  const outputs = page.getByRole('region', { name: 'Output values', exact: true });
  expect(await outputs.getByRole('columnheader', { name: 'Value', exact: true }).evaluate(el => getComputedStyle(el).textAlign)).toBe('right');
  await expect(outputs.getByRole('cell', { name: 'm²', exact: true })).toBeVisible();
  await expect(outputs.getByRole('cell', { name: '0', exact: true })).toBeVisible();
  await expect(outputs.getByText('not computed: Producer failed', { exact: true })).toBeVisible();
  await expect(page.getByText('Worker exited normally.', { exact: false })).not.toBeVisible();
  const execution = page.getByRole('region', { name: 'Execution', exact: true });
  await expect(execution).toContainText('4.9 s');
  await expect(execution).toContainText('45 s');
  await expect(execution).not.toContainText('Criteria');
  await expect(execution).not.toContainText('Converged');
  await expect(page.getByText('Run files and diagnostics', { exact: true })).toHaveCount(0);
  await execution.getByRole('button', { name: 'Execution details', exact: true }).click();
  await expect(page.getByText('Worker exited normally.', { exact: false })).toBeVisible();
  await page.getByText('Raw execution record and source mapping', { exact: true }).click();
  await expect(page.getByText('Fixture producer failed', { exact: false }).first()).toBeVisible();
  expect(run.history.results.outputs[0].units).toBe('m**2');
  expect(state.writes).toEqual([]);
});

// Parent-owned spacing must survive real content and responsive reflow, not only empty specimens.
test('shared flow separates cards, execution tabs, narrative and model search controls', async ({ page }) => {
  const state = await harness(page); const run = runFixture(state);
  state.runs.push({ ...state.runs[0], run_id: 'run-second' });
  state.configurations = [1, 2].map((n) => ({
    configuration: { ...run.history.configuration, configuration_revision_id: `configuration-${n}`, name: `Configuration ${n}` },
    model_snapshot: run.history.model_snapshot,
  }));
  const brief = {
    schema_version: '1', study_id: sid, brief_version_id: 'brief-spacing', version_number: 1,
    predecessor_version_id: null, created_by: 'owner', created_at: '2026-10-19T10:00:00Z', digest: 'fixture',
    content: {
      schema_version: '1', question: 'Compare alternatives under the declared operating conditions.',
      original_question: null, elaboration: null, scope: 'Keep the full scientific scope readable.',
      alternatives: [1, 2].map(n => ({ alternative_id: `alternative-${n}`, name: `Alternative ${n}`, description: 'A complete description that remains visible.', reason: 'An explicit comparison in the brief.' })),
      criteria: [{ criterion_id: 'limit', kind: 'constraint', name: 'Response', statement: 'Response must remain bounded.', operator: 'le', threshold: 10, units: '', evidence_links: [] }],
      assumptions: [{ assumption_id: 'assumption', statement: 'The conditions are illustrative.', evidence_links: [] }], limits: [], open_questions: [],
    },
  };
  await page.route(`**/api/1/studies/${sid}/brief`, route => route.fulfill({ json: { schema_version: '1', data: { draft: null, latest_version: brief } } }));
  await page.route(url => url.pathname === `/api/1/studies/${sid}/brief/versions`, route => route.fulfill({ json: { schema_version: '1', data: { items: [brief], next_cursor: null } } }));
  await login(page, `#v=1&study=${sid}&view=runs`);
  const separated = async (items: Locator, minimum: number) => {
    const bounds = await items.evaluateAll(elements => elements.map(e => {
      const r = e.getBoundingClientRect(); return { top: r.top, bottom: r.bottom };
    }));
    expect(bounds.length).toBeGreaterThan(1);
    for (let i = 1; i < bounds.length; i++) expect(bounds[i].top - bounds[i - 1].bottom).toBeGreaterThanOrEqual(minimum);
  };
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.locator('.run-panel .hf-resource-card')).toHaveCount(2);
    await separated(page.locator('.run-panel .hf-resource-card'), 16);
    await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Configurations', exact: true }).locator('.hf-resource-card')).toHaveCount(2);
    await separated(page.getByRole('region', { name: 'Configurations', exact: true }).locator('.hf-resource-card'), 16);
    await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const execution = page.getByRole('region', { name: 'Execution', exact: true });
  await expect(execution).toBeVisible();
  const box = (await execution.boundingBox())!;
  const tabs = (await page.getByRole('tablist', { name: 'Run detail sections' }).boundingBox())!;
  expect(tabs.y - box.y - box.height).toBeGreaterThanOrEqual(24);
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  const reader = page.getByRole('region', { name: 'Study brief', exact: true });
  await expect(reader.getByRole('heading', { name: 'Alternative 1' })).toBeVisible();
  for (const width of [728, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const heading = (await reader.getByRole('heading', { name: 'Study brief', exact: true }).boundingBox())!;
    expect(heading.width).toBeGreaterThan(120);
    expect(heading.height).toBeLessThanOrEqual(48);
  }
  await separated(reader.locator('.hf-option-list > li'), 12);
  const criteria = reader.getByRole('region', { name: 'Study criteria', exact: true });
  const title = (await criteria.getByRole('heading').boundingBox())!;
  const table = (await criteria.locator('.hf-table-wrap').boundingBox())!;
  expect(table.y - title.y - title.height).toBeGreaterThanOrEqual(16);
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  const openModel = page.getByRole('button', { name: /Open model / });
  await openModel.first().click();
  await expect(page.getByRole('searchbox', { name: 'Search loaded model' })).toBeVisible();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const search = (await page.getByRole('searchbox', { name: 'Search loaded model' }).boundingBox())!;
    const toolbar = (await page.locator('.canvas-toolbar').boundingBox())!;
    expect(search.x - toolbar.x).toBeGreaterThanOrEqual(16);
    expect(search.y - toolbar.y).toBeGreaterThanOrEqual(16);
    expect(toolbar.x + toolbar.width - search.x - search.width).toBeGreaterThanOrEqual(16);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});


test('appearance defaults to dark and preserves an explicit light preference', async ({ page }) => {
  await harness(page);
  await login(page, `#v=1&study=${sid}&view=overview`);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Appearance', exact: true })).toHaveValue('dark');
  await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption('light');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});
