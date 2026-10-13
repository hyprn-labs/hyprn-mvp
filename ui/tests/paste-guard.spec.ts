import { test, expect, Page } from 'playwright/test';
import { writeFileSync } from 'node:fs';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';

const dirty = (page: Page) => page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
async function fixture(page: Page) {
  await page.goto('/ui/'); await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const login = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click(); const csrf = (await (await login).json()).data.csrf_token;
  await page.getByLabel('New study name').fill('17-3 paste reviewfix ' + crypto.randomUUID()); await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page.getByLabel('New model name').fill('Paste scope'); await page.getByLabel('Starting model').selectOption('two_component_example'); await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select First', exact: true })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue(), mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue(), path = `/api/1/studies/${sid}/models/${mid}`;
  const read = async () => (await (await page.request.get(path)).json()).data;
  const edit = async (edits: unknown[]) => { const r = await page.request.post(path + '/edits', { headers: { 'X-CSRF-Token': csrf, Origin: servedOrigin() }, data: { command_id: crypto.randomUUID(), expected_revision: (await read()).draft_revision, edits } }); expect(r.ok()).toBeTruthy(); };
  const initial = await read(), first = initial.instances.find((i: any) => i.name === 'First');
  await edit([{ kind: 'instantiate', temp_key: 'repeat', version_ref: { definition_version_id: first.definition_version_id } }]);
  const before = await read(), repeated = before.instances.find((i: any) => i.instance_id !== first.instance_id && i.definition_version_id === first.definition_version_id);
  await edit([{ kind: 'rename_instance', instance_id: repeated.instance_id, name: 'Repeated' }]);
  await page.getByRole('button', { name: 'Reload model', exact: true }).click(); await expect(page.getByRole('button', { name: 'Select Repeated', exact: true })).toBeVisible();
  const port = before.definitions.find((d: any) => d.definition_version_id === first.definition_version_id).ports[0];
  const writes: unknown[] = []; page.on('request', r => { if (r.method() === 'POST' && (r.url().endsWith('/edits') || r.url().endsWith('/configurations'))) writes.push(r.postDataJSON()); });
  return { sid, path, read, edit, first, repeated, port, writes, configs: async () => (await (await page.request.get(`/api/1/studies/${sid}/configurations`)).json()).data };
}
async function table(page: Page) { await page.getByRole('button', { name: 'Select First', exact: true }).click(); await page.getByRole('tab', { name: 'Variables', exact: true }).click(); }
async function configuration(page: Page) {
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await expect(page.getByText('Model snapshot committed. Enter or review every input.', { exact: true })).toBeVisible();
  await page.getByText('Paste input assignments', { exact: true }).click();
  const refs = await page.locator('[data-input-key]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-input-key')!));
  return 'instance_id\tport_id\tvalue\tunits\tprovenance\n' + refs.map((ref, i) => `${ref.replace('/', '\t')}\t${i ? -3 : 0}\t\tExact provenance Ω  `).join('\n');
}
test('unpreviewed and rejected Variables paste guards repeated-instance selection and discards without writes', async ({ page }) => {
  const f = await fixture(page); await table(page); const before = await f.read();
  for (const text of [`port_id\tname\n${f.port.port_id}\tExact Ω  `, 'rejected\trows\nkeep exact  ']) {
    await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill(text);
    if (text.startsWith('rejected')) await page.getByRole('button', { name: 'Preview port metadata', exact: true }).click();
    await page.getByRole('table', { name: 'Global variables' }).getByRole('button', { name: 'Repeated', exact: true }).first().click(); await expect(dirty(page)).toBeVisible();
    await dirty(page).getByRole('button', { name: 'Keep editing', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Port metadata paste', exact: true })).toHaveValue(text);
    await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('First');
    if (text.startsWith('rejected')) {
      await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click();
      await expect(dirty(page)).not.toBeVisible(); await expect(page.getByRole('textbox', { name: 'Port metadata paste', exact: true })).toHaveValue(text); expect(f.writes).toHaveLength(0);
    }
    await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Discard changes', exact: true }).click();
    await page.getByRole('button', { name: 'Model', exact: true }).click(); await page.getByRole('tab', { name: 'Variables', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Port metadata paste', exact: true })).toHaveValue(''); expect(await f.read()).toEqual(before); expect(f.writes).toHaveLength(0);
  }
});
test('Variables navigation Save previews original instance once; cancellation and stale rejection preserve text', async ({ page }) => {
  const f = await fixture(page); await table(page); const before = await f.read(), text = `port_id\tname\n${f.port.port_id}\tReviewed Ω  `;
  await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill(text);
  await page.getByRole('table', { name: 'Global variables' }).getByRole('button', { name: 'Repeated', exact: true }).first().click(); await expect(dirty(page)).toBeVisible(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true }); await expect(preview).toContainText('2 edits'); expect(f.writes).toHaveLength(0);
  await preview.getByRole('button', { name: 'Keep editing', exact: true }).click(); await expect(page.getByRole('textbox', { name: 'Port metadata paste', exact: true })).toHaveValue(text);
  await page.getByRole('table', { name: 'Global variables' }).getByRole('button', { name: 'Repeated', exact: true }).first().click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(preview.getByRole('button', { name: 'Apply changes', exact: true })).toBeEnabled();
  await preview.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('Repeated');
  const after = await f.read(); expect(f.writes).toHaveLength(1); expect(after.instances.find((i: any) => i.instance_id === f.repeated.instance_id).definition_version_id).toBe(f.first.definition_version_id);
  expect(after.instances.find((i: any) => i.instance_id === f.first.instance_id).definition_version_id).not.toBe(f.first.definition_version_id); expect(after.source_files).toEqual(before.source_files);
  await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill(text); await f.edit([{ kind: 'rename_model', name: 'Concurrent model' }]); const concurrent = await f.read();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(preview.getByRole('alert')).toBeVisible();
  await preview.getByRole('button', { name: 'Keep editing', exact: true }).click(); await expect(page.getByRole('textbox', { name: 'Port metadata paste', exact: true })).toHaveValue(text); expect(await f.read()).toEqual(concurrent);
  writeFileSync(evidencePath('paste-original-instance.json'), JSON.stringify({ before, after, concurrent, writes: f.writes }, null, 2));
});
test('combined source and Variables navigation Save uses one command and rejects a subsequently stale local paste scope', async ({ page }) => {
  const f = await fixture(page); await table(page);
  const source = 'outputs["u"] = inputs["x"] + inputs["z"] + 8\n', text = `port_id\tname\n${f.port.port_id}\tCombined metadata`;
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill(source); await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill(text);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true }); await expect(preview.getByRole('button', { name: 'Apply changes', exact: true })).toBeEnabled(); expect(f.writes).toHaveLength(0);
  await preview.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(page.getByRole('button', { name: 'Configurations', exact: true })).toHaveAttribute('aria-current', 'page'); expect(f.writes).toHaveLength(1);
  const command = f.writes[0] as any; expect(command.edits).toHaveLength(2); expect(command.edits[0].changes.map((c: any) => c.kind)).toEqual(['set_source', 'update_port']);
  expect(Buffer.from(command.edits[0].changes[0].source.bytes, 'base64').toString()).toBe(source); expect(command.edits[1].instance_id).toBe(f.first.instance_id);
  await page.getByRole('button', { name: 'Model', exact: true }).click(); await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('First'); await page.getByRole('tab', { name: 'Variables', exact: true }).click();
  await page.getByRole('textbox', { name: 'Port metadata paste', exact: true }).fill(text);
  const origin = await page.getByText(/^Paste scope:/).textContent();
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill(source + '# Local revision advance\n'); await page.getByRole('button', { name: 'Save component', exact: true }).click(); await preview.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(preview).not.toBeVisible();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(dirty(page)).not.toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Port metadata paste', exact: true })).toHaveValue(text); await expect(page.getByText(/^Paste scope:/)).toHaveText(origin!); expect(f.writes).toHaveLength(2);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Discard changes', exact: true }).click(); expect(f.writes).toHaveLength(2);
  writeFileSync(evidencePath('paste-combined-command.json'), JSON.stringify({ command, original_paste_scope: origin, writes: f.writes }, null, 2));
});
test('configuration unpreviewed and rejected paste survives Keep and is fully discarded without writes', async ({ page }) => {
  const f = await fixture(page), valid = await configuration(page);
  for (const text of [valid, 'invalid\trows\nexact rejected Ω  ']) {
    await page.getByLabel('Input assignment rows').fill(text); if (text.startsWith('invalid')) await page.getByRole('button', { name: 'Preview input assignments', exact: true }).click();
    await page.getByRole('button', { name: 'Runs', exact: true }).click(); await expect(dirty(page)).toBeVisible(); await dirty(page).getByRole('button', { name: 'Keep editing', exact: true }).click(); await expect(page.getByLabel('Input assignment rows')).toHaveValue(text);
    await page.getByRole('button', { name: 'Runs', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Discard changes', exact: true }).click(); await page.getByRole('button', { name: 'Configurations', exact: true }).click();
    await expect(page.getByLabel('Input assignment rows')).toHaveValue(''); expect(f.writes).toHaveLength(0); expect(await f.configs()).toHaveLength(0);
  }
  await page.getByLabel('Input assignment rows').fill(valid); await page.getByRole('button', { name: 'Preview input assignments', exact: true }).click(); await page.getByRole('dialog', { name: 'Input assignment preview', exact: true }).getByRole('button', { name: 'Keep editing', exact: true }).click();
  await page.getByRole('button', { name: 'Discard configuration changes', exact: true }).click(); await expect(page.getByLabel('Input assignment rows')).toHaveValue(''); await expect(page.getByRole('dialog', { name: 'Input assignment preview', exact: true })).not.toBeVisible(); expect(f.writes).toHaveLength(0);
});
test('configuration navigation Save requires explicit paste review and preserves invalid or stale paste', async ({ page }) => {
  const f = await fixture(page), valid = await configuration(page); await page.getByLabel('Configuration name', { exact: true }).fill('Reviewed paste');
  await page.getByLabel('Input assignment rows').fill('invalid rows Ω  '); await page.getByRole('button', { name: 'Runs', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(dirty(page)).not.toBeVisible(); await expect(page.getByLabel('Input assignment rows')).toHaveValue('invalid rows Ω  '); expect(await f.configs()).toHaveLength(0);
  const incompatible = valid.replaceAll('\t\tExact provenance', '\tm\tExact provenance');
  await page.getByLabel('Input assignment rows').fill(incompatible); await page.getByRole('button', { name: 'Runs', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.getByRole('dialog', { name: 'Input assignment preview', exact: true }).getByRole('button', { name: 'Apply and save configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible(); await expect(page.getByLabel('Input assignment rows')).toHaveValue(incompatible); expect(await f.configs()).toHaveLength(0); expect(f.writes).toHaveLength(0);
  await page.getByLabel('Input assignment rows').fill(valid); await page.getByRole('button', { name: 'Runs', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Input assignment preview', exact: true }); await expect(preview).toBeVisible(); expect(f.writes).toHaveLength(0);
  await preview.getByRole('button', { name: 'Keep editing', exact: true }).click(); await expect(page.getByLabel('Input assignment rows')).toHaveValue(valid);
  await page.getByRole('button', { name: 'Runs', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await preview.getByRole('button', { name: 'Apply and save configuration', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Runs', exact: true })).toHaveAttribute('aria-current', 'page'); expect(f.writes).toHaveLength(1); const configs = await f.configs(); expect(configs).toHaveLength(1); expect(configs[0].configuration.inputs.map((i: any) => i.value)).toContain(0);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await expect(page.getByLabel('Input assignment rows')).toHaveValue('');
  await page.getByLabel('Input assignment rows').fill(valid); await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click(); await page.getByRole('button', { name: 'Use reviewed model revision', exact: true }).click();
  await page.getByRole('button', { name: 'Runs', exact: true }).click(); await dirty(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(page.getByRole('alert')).toContainText('paste'); await expect(page.getByLabel('Input assignment rows')).toHaveValue(valid); expect(await f.configs()).toEqual(configs);
  await page.screenshot({ path: evidencePath('paste-stale-retained.png'), fullPage: true });
});
