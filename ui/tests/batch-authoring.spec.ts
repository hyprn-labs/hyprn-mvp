import { test, expect, Page } from 'playwright/test';
import { writeFileSync } from 'node:fs';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';
async function openModelTools(page: Page) { const tools = page.locator('details.model-tools'); if (await tools.count() && await tools.getAttribute('open') === null) await tools.locator(':scope > summary').click(); }

async function fixture(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const session = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const csrf = (await (await session).json()).data.csrf_token;
  await page.getByLabel('New study name').fill(`Batch ${crypto.randomUUID()}`);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page.getByLabel('New model name').fill('Batch model');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByText('Add a component to start.', { exact: true })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const path = `/api/1/studies/${sid}/models/${mid}`;
  return { path, csrf, read: async () => (await (await page.request.get(path)).json()).data,
    edit: async (snapshot: any, edits: any[]) => page.request.post(path + '/edits', { headers: { 'X-CSRF-Token': csrf, Origin: servedOrigin() }, data: { command_id: crypto.randomUUID(), expected_revision: snapshot.draft_revision, edits } }) };
}
async function apply(page: Page, label = 'Apply changes') {
  const dialog = page.getByRole('dialog', { name: 'Preview changes', exact: true });
  await expect(dialog.getByRole('button', { name: label, exact: true })).toBeEnabled();
  await dialog.getByRole('button', { name: label, exact: true }).click();
  await expect(dialog).not.toBeVisible();
}
async function add(page: Page, name: string, inputs: string, outputs: string) {
  await openModelTools(page);
  await page.getByLabel('New component name').fill(name);
  await page.getByLabel('Input symbols').fill(inputs);
  await page.getByLabel('Output symbols').fill(outputs);
  await page.getByRole('button', { name: 'Add component', exact: true }).click();
  await apply(page);
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue(name);
}

test('pure preview, safe dismissal and explicit selected version replacement', async ({ page }) => {
  const f = await fixture(page); const initial = await f.read();
  await openModelTools(page);
  await page.getByLabel('New component name').fill('Scale');
  await page.getByLabel('Input symbols').fill('x'); await page.getByLabel('Output symbols').fill('y');
  await page.getByRole('button', { name: 'Add component', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Preview changes', exact: true });
  await expect(dialog).toBeVisible(); await expect(dialog.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
  expect(await f.read()).toEqual(initial);
  await page.screenshot({ path: evidencePath("batch-preview.png"), fullPage: true });
  await dialog.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Add component', exact: true })).toBeFocused();
  await expect(page.getByLabel('New component name')).toHaveValue('Scale');
  await page.getByRole('button', { name: 'Add component', exact: true }).click(); await apply(page);
  await page.getByRole('button', { name: 'Add another instance', exact: true }).click(); await apply(page);
  const before = await f.read(); const instances = before.instances.filter((i: any) => i.instance_id !== before.root_instance_id);
  expect(instances).toHaveLength(2); expect(instances[0].definition_version_id).toBe(instances[1].definition_version_id);
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["y"] = inputs["x"] * 3\n');
  const commands: any[] = []; page.on('request', r => { if (r.url().endsWith('/edits') && r.method() === 'POST') commands.push(r.postDataJSON()); });
  await page.getByRole('button', { name: 'Save component', exact: true }).click(); await apply(page);
  const after = await f.read(); expect(commands).toHaveLength(1);
  expect(commands[0].edits.filter((e: any) => e.kind === 'replace_local_instance_version')).toHaveLength(1);
  expect(after.instances.filter((i: any) => i.definition_version_id === instances[0].definition_version_id)).toHaveLength(1);
  const replay = await page.request.post(f.path + '/edits', { headers: { 'X-CSRF-Token': f.csrf, Origin: servedOrigin() }, data: commands[0] });
  expect(replay.ok()).toBeTruthy(); expect(await f.read()).toEqual(after);
  writeFileSync(evidencePath('batch-version-records.json'), JSON.stringify({ before, after, command: commands[0] }, null, 2));
});

test('multi-connect, per-row reconnect, incident removal and one-member disconnect', async ({ page }) => {
  const f = await fixture(page); await add(page, 'Producer', '', 'a,b'); await add(page, 'Consumer', 'x,y', 'z');
  const before = await f.read(); const producer = before.instances.find((i: any) => i.name === 'Producer'), consumer = before.instances.find((i: any) => i.name === 'Consumer');
  const ports = (i: any) => before.definitions.find((d: any) => d.definition_version_id === i.definition_version_id).ports;
  for (const [out, input] of [['a','x'], ['b','y']]) {
    await openModelTools(page);
    await page.getByRole('combobox', { name: 'Connection output', exact: true }).selectOption(`${producer.instance_id}/${ports(producer).find((p: any) => p.name === out).port_id}`);
    await page.getByRole('combobox', { name: 'Connection input', exact: true }).selectOption(`${consumer.instance_id}/${ports(consumer).find((p: any) => p.name === input).port_id}`);
    await page.getByRole('button', { name: 'Queue connection', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Preview queued connections', exact: true }).click(); expect(await f.read()).toEqual(before); await apply(page);
  const connected = await f.read(); expect(connected.connections).toHaveLength(2);
  await page.getByLabel(`Select connection ${connected.connections[0].connection_id}`, { exact: true }).check();
  await page.getByRole('button', { name: 'Disconnect selected connections', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep connections', exact: true })).toBeFocused(); await apply(page, 'Disconnect connections');
  const remaining = await f.read(); expect(remaining.connections).toEqual([connected.connections[1]]);
  await openModelTools(page);
  await page.getByRole('combobox', { name: 'Connection output', exact: true }).selectOption(`${producer.instance_id}/${ports(producer).find((p: any) => p.name === 'a').port_id}`);
  await page.getByRole('combobox', { name: 'Connection input', exact: true }).selectOption(`${consumer.instance_id}/${ports(consumer).find((p: any) => p.name === 'y').port_id}`);
  await page.getByRole('button', { name: `Reconnect ${remaining.connections[0].connection_id}`, exact: true }).click(); await apply(page);
  expect((await f.read()).connections).toHaveLength(1);
  await openModelTools(page);
  await page.getByLabel(`Select component ${producer.instance_id}`, { exact: true }).check();
  await page.getByRole('button', { name: 'Remove selected components', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep components', exact: true })).toBeFocused(); await apply(page, 'Remove components');
  const removed = await f.read(); expect(removed.connections).toHaveLength(0); expect(removed.instances.some((i: any) => i.instance_id === producer.instance_id)).toBeFalsy();
});

test('stale proposal remains reviewable until deliberate re-preview and rename', async ({ page }) => {
  const f = await fixture(page); await add(page, 'Scale', 'x', 'y');
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["y"] = inputs["x"] + 8\n');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Apply changes', exact: true })).toBeEnabled();
  const before = await f.read(); expect((await f.edit(before, [{ kind: 'rename_model', name: 'Concurrent name' }])).ok()).toBeTruthy();
  await page.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('changed');
  await page.getByRole('button', { name: 'Review current revision', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Current revision differences' })).toContainText('Concurrent name');
  await page.getByRole('button', { name: 'Re-preview preserved proposal', exact: true }).click(); await apply(page);
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveValue('outputs["y"] = inputs["x"] + 8\n');
  await openModelTools(page);
  await page.getByText('Model name', { exact: true }).click();
  await page.getByLabel('Rename model', { exact: true }).fill('Reviewed name'); await page.getByRole('button', { name: 'Preview model rename', exact: true }).click(); await apply(page);
  expect((await f.read()).name).toBe('Reviewed name');
  await page.screenshot({ path: evidencePath('batch-authoring.png'), fullPage: true });
});

test('global metadata paste rejects indexed invalid rows and applies one selected instance', async ({ page }) => {
  const f = await fixture(page); await add(page, 'Scale', 'x', 'y'); const before = await f.read();
  const instance = before.instances.find((i: any) => i.name === 'Scale'); const definition = before.definitions.find((d: any) => d.definition_version_id === instance.definition_version_id);
  await page.getByRole('tab', { name: 'Variables', exact: true }).click();
  await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill('port_id\tvalue\n' + definition.ports[0].port_id + '\t0');
  await page.getByRole('button', { name: 'Preview port metadata', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Variables view' }).getByRole('alert')).toContainText('Row 1'); expect(await f.read()).toEqual(before);
  await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill('port_id\tname\n' + definition.ports[0].port_id + '\tReadable input');
  await page.getByRole('button', { name: 'Preview port metadata', exact: true }).click(); await apply(page);
  const after = await f.read(); const updated = after.instances.find((i: any) => i.instance_id === instance.instance_id);
  expect(after.definitions.find((d: any) => d.definition_version_id === updated.definition_version_id).ports[0].name).toBe('Readable input');
  await page.screenshot({ path: evidencePath('batch-variables-paste.png'), fullPage: true });
});

test('invalid batch has no partial effect and advertised limits reject before a request', async ({ page }) => {
  const f = await fixture(page); await add(page, 'Scale', 'x', 'y'); const before = await f.read();
  const invalid = await f.edit(before, [{ kind: 'rename_model', name: 'Must roll back' }, { kind: 'remove_instance', instance_id: crypto.randomUUID() }]);
  expect(invalid.ok()).toBeFalsy(); expect(await f.read()).toEqual(before);
  const { HyprnMvpApi, validateEditCommand } = await import('../src/api');
  const base = { command_id: crypto.randomUUID(), expected_revision: before.draft_revision, edits: [{ kind: 'rename_model' as const, name: 'Valid' }] };
  expect(() => validateEditCommand({ ...base, edits: Array.from({ length: 257 }, () => base.edits[0]) })).toThrow('256');
  expect(() => validateEditCommand({ ...base, edits: [{ kind: 'set_annotation', element_ref: before.root_instance_id, text: 'x'.repeat(2 * 1024 * 1024) }] })).toThrow('2 MiB');
  expect(() => validateEditCommand({ ...base, edits: [{ kind: 'create_definition', temp_key: 'large', definition_kind: 'explicit_component', name: 'Large', ports: [], source: { encoding: 'base64', media_type: 'text/x-python', bytes: Buffer.alloc(256 * 1024 + 1).toString('base64'), sha256: '0'.repeat(64) } }] })).toThrow('256 KiB');
  expect(() => validateEditCommand(base, { ...before, instances: Array.from({ length: 1001 }, () => before.instances[0]) })).toThrow('1000');
  const api = new HyprnMvpApi(); let requests = 0;
  api.request = async () => { requests++; throw new Error('Unexpected request'); };
  await expect(api.previewEdits(before, { ...base, edits: Array.from({ length: 257 }, () => base.edits[0]) })).rejects.toThrow('256');
  expect(requests).toBe(0);
});

test('frozen configuration survives a guarded source save and table paste preserves dirty text', async ({ page }) => {
  const f = await fixture(page); await add(page, 'Scale', 'x', 'y');
  const model = await f.read(), sid = model.study_id;
  const headers = { 'X-CSRF-Token': f.csrf, Origin: servedOrigin() };
  const committed = await page.request.post(f.path + '/commits', { headers, data: { command_id: crypto.randomUUID(), expected_revision: model.draft_revision } });
  expect(committed.ok(), await committed.text()).toBeTruthy(); const revision = (await committed.json()).data;
  const instance = model.instances.find((i: any) => i.name === 'Scale'); const definition = model.definitions.find((d: any) => d.definition_version_id === instance.definition_version_id);
  const input = definition.ports.find((p: any) => p.direction === 'input');
  const study = (await (await page.request.get(`/api/1/studies/${sid}`)).json()).data;
  const response = await page.request.post(`/api/1/studies/${sid}/configurations`, { headers, data: { command_id: crypto.randomUUID(), expected_revision: null, configuration: {
    schema_version: '1', study_id: sid, model_id: model.model_id, model_revision_id: revision.model_revision_id, name: 'Immutable batch evidence',
    inputs: [{ target: { instance_id: instance.instance_id, port_id: input.port_id }, value: 0, units: '', provenance: { kind: 'manual', statement: 'Explicit zero retention fixture', evidence_version_ids: [] } }], criteria: [],
    numerical: { mode: 'deterministic', initialization: [], solvers: [], derivatives: { method: 'none', form: null, check: null }, design_variables: [], objectives: [], constraints: [], optimizer: null, uncertainty: null },
    context_snapshot: { description: study.description, boundary: study.boundary, notes: [] }, evidence_snapshots: [], required_capabilities: []
  } } });
  expect(response.ok(), await response.text()).toBeTruthy(); const frozen = (await response.json()).data;
  const path = `/api/1/studies/${sid}/configurations/${frozen.configuration.configuration_revision_id}`;
  const original = JSON.stringify((await (await page.request.get(path)).json()).data);
  const source = 'outputs["y"] = inputs["x"] + 19\n';
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill(source);
  await page.getByRole('tab', { name: 'Variables', exact: true }).click();
  await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill(`port_id\tname\n${input.port_id}\tMust stay local`);
  await page.getByRole('button', { name: 'Preview port metadata', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Variables view' }).getByRole('alert')).toContainText('Save or discard');
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveValue(source);
  await page.getByRole('button', { name: 'Reload model', exact: true }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await apply(page);
  await expect(page.getByRole('dialog')).not.toBeVisible();
  expect(JSON.stringify((await (await page.request.get(path)).json()).data)).toBe(original);
  writeFileSync(evidencePath('batch-frozen-configuration.json'), original);
  writeFileSync(evidencePath('batch-retention-proof.json'), JSON.stringify({ configuration_revision_id: frozen.configuration.configuration_revision_id, exact_public_record_unchanged: true, submitted_runs: 0 }, null, 2));
});
