import { test, expect, Page } from 'playwright/test';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';

async function fixture(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const session = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const csrf = (await (await session).json()).data.csrf_token;
  async function post(path: string, data: unknown) { const response = await page.request.post('/api/1' + path, { headers: { Origin: servedOrigin(), 'X-CSRF-Token': csrf }, data }); expect(response.ok(), await response.text()).toBeTruthy(); return (await response.json()).data; }
  const study = await post('/studies', { command_id: crypto.randomUUID(), name: 'Variables ' + crypto.randomUUID() });
  const model = await post(`/studies/${study.study_id}/models`, { command_id: crypto.randomUUID(), expected_revision: study.revision, name: 'Inspection fixture', template: 'two_component_example' });
  await page.evaluate(hash => { window.location.hash = hash; }, `v=1&study=${study.study_id}&model=${model.model_id}&view=model`);
  await expect(page.getByRole('button', { name: 'Refresh model', exact: true })).toBeVisible();
  return { study, model, post };
}

test('Variables shares exact graph/XDSM/editor selection, truthful draft state and filters', async ({ page }) => {
  const { study, model } = await fixture(page);
  await expect(page.getByRole('combobox', { name: 'Study', exact: true })).toHaveValue(study.study_id);
  const views = page.getByRole('region', { name: 'Connected model views', exact: true });
  await views.getByRole('tab', { name: 'Variables', exact: true }).click();
  const table = views.getByRole('table', { name: 'Global variables', exact: true });
  const first = model.instances.find((i: any) => i.name === 'First');
  const port = model.definitions.find((d: any) => d.definition_version_id === first.definition_version_id).ports.find((p: any) => p.direction === 'output');
  const row = table.locator(`[data-variable="${first.instance_id}/${port.port_id}"]`);
  await expect(row).toContainText('Declared · not computed');
  await row.getByRole('button', { name: /^Inspect variable ·/ }).click();
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('First');
  await expect(page.getByRole('region', { name: 'Selection inspector' })).toContainText(first.definition_version_id);
  await views.getByRole('tab', { name: 'Graph', exact: true }).click();
  await expect(views.locator(`[data-instance="${first.instance_id}"]`).first().locator('..').locator('..').getByRole('button', { name: /← u/ })).toHaveAttribute('aria-pressed', 'true');
  await views.getByRole('tab', { name: 'Variables', exact: true }).click();
  await views.getByLabel('Filter variables').fill('no-such-variable');
  await expect(views.getByText(/0 of \d+ loaded variables/)).toBeVisible();
  await views.getByRole('button', { name: 'Clear variable filters' }).click();
  await views.getByLabel('Direction filter').selectOption('output');
  expect(await table.locator('tbody tr').count()).toBe(2);
  await views.getByRole('button', { name: 'Clear variable filters' }).click();
  for (const width of [1440, 1920, 1024]) { await page.setViewportSize({ width, height: 1000 }); await views.scrollIntoViewIfNeeded(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy(); await page.screenshot({ path: evidencePath(`variables-${width}.png`) }); }
});

test('configuration draft and frozen assignments use their exact snapshot and values', async ({ page }) => {
  await fixture(page);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Explicit inputs');
  const valueFields = page.locator('[data-input-key]');
  for (let i = 0; i < await valueFields.count(); i++) { await valueFields.nth(i).fill(String(i + 2)); await page.locator('.input-row textarea').nth(i).fill('Manual inspection fixture'); }
  const views = page.getByRole('region', { name: 'Connected model views', exact: true });
  await views.getByRole('tab', { name: 'Variables', exact: true }).click();
  await expect(views.getByText('Configuration draft · explicit inputs', { exact: true })).toBeVisible();
  await expect(views.getByRole('table', { name: 'Global variables' })).toContainText('Manual inspection fixture');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(views.getByText('Committed configuration · read-only assignments', { exact: true })).toBeVisible();
  await expect(views.getByRole('table', { name: 'Global variables' })).toContainText('Not computed');
});

test('repeated definitions keep distinct rows and grouped exchanges trace every consumer', async ({ page }) => {
  const { study, model, post } = await fixture(page);
  const base = `/studies/${study.study_id}/models/${model.model_id}`;
  const first = model.instances.find((i: any) => i.name === 'First');
  const definition = model.definitions.find((d: any) => d.definition_version_id === first.definition_version_id);
  let next = await post(base + '/edits', { command_id: crypto.randomUUID(), expected_revision: model.draft_revision, edits: ['repeat_a', 'repeat_b'].map(temp_key => ({ kind: 'instantiate', temp_key, version_ref: { definition_version_id: first.definition_version_id } })) });
  const added = next.instances.filter((i: any) => !model.instances.some((old: any) => old.instance_id === i.instance_id));
  const output = definition.ports.find((p: any) => p.direction === 'output'), inputs = definition.ports.filter((p: any) => p.direction === 'input');
  next = await post(base + '/edits', { command_id: crypto.randomUUID(), expected_revision: next.draft_revision, edits: [...added.map((i: any) => ({ kind: 'rename_instance', instance_id: i.instance_id, name: 'Repeated instance' })), ...[[added[0], inputs[0]], [added[0], inputs[1]], [added[1], inputs[0]]].map(([i, p], index) => ({ kind: 'connect', temp_key: 'link' + index, source_ref: { instance_id: first.instance_id, port_id: output.port_id }, target_ref: { instance_id: i.instance_id, port_id: p.port_id } }))] });
  await page.getByRole('button', { name: 'Refresh model' }).click();
  const views = page.getByRole('region', { name: 'Connected model views', exact: true });
  const exchange = views.locator(`[data-group="${first.instance_id}:${added[0].instance_id}"]`).first(); await exchange.focus(); await exchange.press('Enter');
  await expect(views.locator('[data-selected-link]')).toHaveCount(2);
  await expect(page.getByRole('region', { name: 'Selection inspector' })).toContainText('dimensionless');
  await views.getByRole('tab', { name: 'Variables', exact: true }).click();
  for (const instance of added) await expect(views.locator(`[data-variable="${instance.instance_id}/${inputs[0].port_id}"]`)).toHaveCount(1);
  const producer = views.locator(`[data-variable="${first.instance_id}/${output.port_id}"]`);
  await expect(producer.getByRole('button', { name: /^Consumer:/ })).toHaveCount(4);
  await producer.getByRole('button', { name: /^Consumer:/ }).last().click();
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('Repeated instance');
  await expect(page.getByRole('region', { name: 'Selection inspector' })).toContainText(added[1].instance_id);
});

test('ordinary run selection uses retained values without substituting a current draft', async ({ page }) => {
  await fixture(page);
  const studies = (await (await page.request.get('/api/1/studies?limit=100')).json()).data;
  let retained: { study: string; run: any } | undefined;
  for (const study of studies) {
    const runs = (await (await page.request.get(`/api/1/studies/${study.study_id}/runs`)).json()).data;
    for (const run of runs.filter((r: any) => r.state === 'recorded')) {
      const detail = (await (await page.request.get(`/api/1/studies/${study.study_id}/runs/${run.run_id}`)).json()).data;
      if (detail.history?.model_snapshot && detail.history?.results) { retained = { study: study.study_id, run: detail }; break; }
    }
    if (retained) break;
  }
  expect(retained).toBeTruthy();
  await page.evaluate(hash => { window.location.hash = hash; }, `v=1&view=runs&study=${retained!.study}`);
  await page.getByRole('button', { name: `Inspect run ${retained!.run.run_id}`, exact: true }).click();
  await page.getByRole('tab', { name: 'Model and inputs', exact: true }).click();
  const views = page.getByRole('region', { name: 'Connected model views', exact: true });
  await views.getByRole('tab', { name: 'Variables', exact: true }).click();
  await expect(views.getByText('Retained run · verified values and availability', { exact: true })).toBeVisible();
  for (const output of retained!.run.history.results.outputs) {
    const row = views.locator(`[data-variable="${output.target.instance_id}/${output.target.port_id}"]`);
    await expect(row).toContainText(output.availability === 'available' && output.value !== null ? String(output.value) : '—');
  }
  await expect(page).toHaveURL(new RegExp('run=' + retained!.run.run_id));
});

test('missing and failed outputs never become zero; explicit zero remains a real input', async () => {
  const { variableRows } = await import('../src/VariablesTable'); const { project } = await import('../src/GraphView');
  const input = { port_id: 'in', name: 'x', code_symbol: 'x', direction: 'input', units: 'm', value_type: 'real_scalar' }, output = { ...input, port_id: 'out', name: 'y', code_symbol: 'y', direction: 'output' };
  const snapshot = { root_instance_id: 'root', instances: [{ instance_id: 'a', definition_version_id: 'v', name: 'A' }], definitions: [{ definition_version_id: 'v', ports: [input, output], source_refs: ['source'] }], connections: [] } as any;
  const projection = project(snapshot);
  const draft = variableRows(snapshot, projection, { kind: 'configuration_draft', inputs: [{ target: { instance_id: 'a', port_id: 'in' }, value: '0', units: 'm', statement: 'Measured zero' }] });
  expect(draft[0].value).toBe('0'); expect(draft[1].value).toBe('Not computed');
  const rows = variableRows(snapshot, projection, { kind: 'run', history: { configuration: null, results: { outputs: [{ target: { instance_id: 'a', port_id: 'out' }, value: 0, units: 'm', availability: 'unavailable', reason: 'producer_failed' }] } } as any });
  expect(rows[1].value).toBe('not computed'); expect(rows[1].availability).toBe('unavailable');
  expect(rows[1].provenance).toBe('Retained run output · Producer failed');
});
