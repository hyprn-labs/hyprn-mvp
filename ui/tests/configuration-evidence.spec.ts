import { test, expect, Page } from 'playwright/test';
import { evidencePath } from './evidence';
import { ownerPassword } from './support/served';

async function setup(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('New study name').fill('Evidence ' + crypto.randomUUID());
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page.getByLabel('New model name').fill('Chain'); await page.getByLabel('Starting model').selectOption('two_component_example');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Refresh model', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByText('Model snapshot committed. Enter or review every input.', { exact: true })).toBeVisible();
  return page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
}
test('typed evidence freezes into explicit input and criterion provenance and survives reload', async ({ page }) => {
  const sid = await setup(page);
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await page.getByRole('combobox', { name: 'Evidence scope', exact: true }).selectOption({ label: 'Model revision' });
  await page.getByLabel('Evidence note', { exact: true }).fill('Signed input justification');
  await page.getByRole('button', { name: 'Create evidence note', exact: true }).click();
  await expect(page.getByText('Evidence note recorded.', { exact: true })).toBeVisible();
  const record = (await (await page.request.get(`/api/1/studies/${sid}/evidence`)).json()).data[0];
  expect(record.evidence_schema_version).toBe('2'); expect(record.resource_scope.kind).toBe('model_revision');
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Frozen evidence');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Enter an explicit value');
  for (const [symbol, value] of [['x', '0'], ['z', '-3']]) { await page.getByLabel(`First · ${symbol} value`, { exact: true }).fill(value); await page.getByLabel(`First · ${symbol} provenance`, { exact: true }).fill('Explicit signed value'); }
  await page.getByRole('listbox', { name: 'First · x evidence', exact: true }).selectOption([record.evidence_version_id]);
  await page.getByText('Criteria', { exact: true }).click(); await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await page.getByRole('combobox', { name: 'Criterion 1 output', exact: true }).selectOption({ label: 'Second · y' });
  await page.getByLabel('Criterion 1 threshold', { exact: true }).fill('100');
  await page.getByRole('listbox', { name: 'Criterion 1 evidence', exact: true }).selectOption([record.evidence_version_id]);
  await expect(page.getByRole('region', { name: 'Connected inputs' })).toContainText('Second · u');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const frozen = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data[0];
  expect(frozen.configuration.inputs.map((i: any) => i.value).sort()).toEqual([-3, 0]);
  expect(frozen.configuration.inputs.find((i: any) => i.value === 0).provenance.evidence_version_ids).toEqual([record.evidence_version_id]);
  expect(frozen.configuration.criteria[0].evidence_version_ids).toEqual([record.evidence_version_id]);
  expect(frozen.configuration.evidence_snapshots[0].resource_scope).toEqual(record.resource_scope);
  await page.getByRole('button', { name: 'Refresh execution readiness', exact: true }).click();
  const readiness = (await (await page.request.get(`/api/1/studies/${sid}/execution-readiness`)).json()).data;
  await expect(page.getByRole('region', { name: 'Execution readiness', exact: true })).toContainText(readiness.status);
  if (readiness.status !== 'ready') await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeDisabled();
  await page.screenshot({ path: evidencePath('configuration-evidence.png'), fullPage: true });
  await page.reload();
  const retained = (await (await page.request.get(`/api/1/studies/${sid}/configurations/${frozen.configuration.configuration_revision_id}`)).json()).data;
  expect(retained).toEqual(frozen);
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(0);
});

test('input paste previews locally and copied configuration requires explicit rebind review', async ({ page }) => {
  const sid = await setup(page);
  await page.getByLabel('Configuration name', { exact: true }).fill('Paste proposal');
  const refs = await page.locator('[data-input-key]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-input-key')!));
  await page.getByText('Paste input assignments', { exact: true }).click();
  const text = 'instance_id\tport_id\tvalue\tunits\tprovenance\n' + refs.map((ref, i) => `${ref.replace('/', '\t')}\t${i ? -2 : 0}\t\tMeasured value`).join('\n');
  await page.getByLabel('Input assignment rows').fill(text);
  await page.getByRole('button', { name: 'Preview input assignments', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Input assignment preview' })).toContainText('Measured value');
  expect((await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data).toHaveLength(0);
  await page.getByRole('button', { name: 'Apply input assignments', exact: true }).click();
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const frozen = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data[0];
  await page.getByText('Saved configurations', { exact: true }).click();
  await page.getByRole('button', { name: /^Copy Paste proposal/ }).click();
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review model binding' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep current binding' }).click();
  expect((await (await page.request.get(`/api/1/studies/${sid}/configurations/${frozen.configuration.configuration_revision_id}`)).json()).data).toEqual(frozen);
  expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(0);
});

test('context evidence can be selected and removed without altering the saved version', async ({ page }) => {
  const sid = await setup(page);
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await page.getByRole('textbox', { name: 'Evidence note', exact: true }).fill('Context-only boundary evidence');
  await page.getByRole('button', { name: 'Create evidence note', exact: true }).click();
  await expect(page.getByText('Evidence note recorded.', { exact: true })).toBeVisible();
  const record = (await (await page.request.get(`/api/1/studies/${sid}/evidence`)).json()).data[0];
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('textbox', { name: 'Configuration name', exact: true }).fill('Context evidence');
  for (const symbol of ['x', 'z']) { await page.getByLabel(`First · ${symbol} value`, { exact: true }).fill('0'); await page.getByRole('textbox', { name: `First · ${symbol} provenance`, exact: true }).fill('Explicit zero'); }
  await page.getByRole('listbox', { name: 'Context evidence', exact: true }).selectOption(record.evidence_version_id);
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const frozen = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data[0];
  expect(frozen.configuration.evidence_snapshots.map((e: any) => e.evidence_version_id)).toEqual([record.evidence_version_id]);
  await page.getByRole('listbox', { name: 'Context evidence', exact: true }).selectOption([]);
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect.poll(async () => (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data.length).toBe(2);
  const records = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data;
  expect(records[1].configuration.evidence_snapshots).toEqual([]);
  expect((await (await page.request.get(`/api/1/studies/${sid}/configurations/${frozen.configuration.configuration_revision_id}`)).json()).data).toEqual(frozen);
});

test('deep-linked retained run copies to its matching model configuration without a write', async ({ page }) => {
  const sid = await setup(page);
  await page.getByRole('textbox', { name: 'Configuration name', exact: true }).fill('Deep copy');
  for (const symbol of ['x', 'z']) { await page.getByLabel(`First · ${symbol} value`, { exact: true }).fill('2'); await page.getByRole('textbox', { name: `First · ${symbol} provenance`, exact: true }).fill('Copied exact provenance'); }
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const frozen = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data[0], rid = crypto.randomUUID();
  // Scoped navigation fixture only; no scientific execution claim.
  const run = { run_id: rid, state: 'recorded', history: { configuration: frozen.configuration, model_snapshot: frozen.model_snapshot, results: null, assessment: null, artifacts: [], errors: [] } };
  await page.route(`**/api/1/studies/${sid}/runs/${rid}`, route => route.fulfill({ json: { schema_version: '1', data: run } }));
  await page.route(`**/api/1/studies/${sid}/runs`, route => route.fulfill({ json: { schema_version: '1', data: [{ run_id: rid, state: 'recorded', configuration_revision_id: frozen.configuration.configuration_revision_id }] } }));
  const { workspaceHash } = await import('../src/workspaceModel');
  await page.evaluate(hash => { location.hash = hash; }, workspaceHash({ study: sid, view: 'runs', run: rid }));
  await expect(page.getByRole('button', { name: 'Create new version', exact: true })).toBeVisible();
  let writes = 0; page.on('request', r => { if (['POST', 'PATCH'].includes(r.method())) writes++; });
  await page.getByRole('button', { name: 'Create new version', exact: true }).click();
  await expect(page.getByText('Configuration copied to an unsaved draft. No run submitted.', { exact: true })).toBeVisible();
  await expect(page.getByLabel('First · x value', { exact: true })).toHaveValue('2');
  await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeDisabled();
  expect(writes).toBe(0);
});

test('changed model binding requires explicit new input and preserves its earlier configuration', async ({ page }) => {
  const sid = await setup(page);
  await page.getByRole('textbox', { name: 'Configuration name', exact: true }).fill('Before changed contract');
  for (const symbol of ['x', 'z']) { await page.getByLabel(`First · ${symbol} value`, { exact: true }).fill('2'); await page.getByRole('textbox', { name: `First · ${symbol} provenance`, exact: true }).fill('Original explicit input'); }
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
  const frozen = (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data[0];
  await page.getByRole('button', { name: 'Model', exact: true }).click();
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["u"] = inputs["x"] + inputs["z"] + inputs["extra"]\n');
  await page.getByText('Inputs/outputs', { exact: true }).click();
  const count = await page.getByRole('button', { name: /^Remove port / }).count();
  await page.getByRole('button', { name: 'Add input port', exact: true }).click();
  await page.getByLabel(`Port ${count + 1} name`, { exact: true }).fill('Extra');
  await page.getByLabel(`Port ${count + 1} symbol`, { exact: true }).fill('extra');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await page.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Preview changes' })).not.toBeVisible();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review model binding' })).toContainText('Extra');
  await page.getByRole('button', { name: 'Use reviewed model revision', exact: true }).click();
  await expect(page.getByLabel('First · Extra value', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Enter an explicit value');
  await page.getByLabel('First · Extra value', { exact: true }).fill('-1');
  await page.getByRole('textbox', { name: 'First · Extra provenance', exact: true }).fill('Reviewed new contract');
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect.poll(async () => (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data.length).toBe(2);
  expect((await (await page.request.get(`/api/1/studies/${sid}/configurations/${frozen.configuration.configuration_revision_id}`)).json()).data).toEqual(frozen);
});

test('dirty exact-scope evidence note survives navigation and an uncertain response without duplication', async ({ page }) => {
  const sid = await setup(page);
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await page.getByRole('combobox', { name: 'Evidence scope', exact: true }).selectOption({ label: 'Model revision' });
  await page.getByRole('textbox', { name: 'Evidence note', exact: true }).fill('Preserve this scoped note');
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Evidence note', exact: true })).toHaveValue('Preserve this scoped note');
  let posts = 0;
  await page.route(`**/api/1/studies/${sid}/evidence`, async route => { if (route.request().method() === 'POST') { posts++; await route.fetch(); await route.abort('failed'); } else await route.continue(); });
  await page.getByRole('button', { name: 'Create evidence note', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Check original command', exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Evidence note', exact: true })).toHaveValue('Preserve this scoped note');
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh evidence', exact: true }).click();
  const records = (await (await page.request.get(`/api/1/studies/${sid}/evidence`)).json()).data;
  expect(records).toHaveLength(1); expect(records[0].resource_scope.kind).toBe('model_revision'); expect(posts).toBe(1);
  await page.getByRole('button', { name: 'Runs', exact: true }).click(); await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Refresh run history', exact: true })).toBeVisible();
});
