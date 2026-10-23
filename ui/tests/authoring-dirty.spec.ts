import { test, expect, Page } from 'playwright/test';
import { createHash } from 'node:crypto';
import { ownerPassword, servedOrigin } from './support/served';
async function tools(page: Page) { const el = page.locator('details.model-tools'); if (await el.getAttribute('open') === null) await el.locator(':scope > summary').click(); }
async function fixture(page: Page) {
  await page.goto('/ui/'); await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const session = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click(); const csrf = (await (await session).json()).data.csrf_token;
  await page.getByLabel('Study name').fill('Dirty guard ' + crypto.randomUUID()); await page.getByLabel('Study question', { exact: true }).fill('What must this engineering study establish?');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page.getByLabel('New model name').fill('Pending authoring'); await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByText('Add a component to start.', { exact: true })).toBeVisible();
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue(), mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const path = `/api/1/studies/${sid}/models/${mid}`, read = async () => (await (await page.request.get(path)).json()).data;
  const source = Buffer.from('# Authored fixture; never executed.\n'), hash = createHash('sha256').update(source).digest('hex');
  const edits = [['Producer', '', 'a,b'], ['Consumer', 'x,y', 'z']].flatMap(([name, ins, outs], i) => [{ kind: 'create_definition', temp_key: `d${i}`, definition_kind: 'explicit_component', name,
    ports: [...ins.split(',').filter(Boolean).map(s => ({ s, direction: 'input' })), ...outs.split(',').map(s => ({ s, direction: 'output' }))].map((p, n) => ({ temp_key: `p${n}`, name: p.s, code_symbol: p.s, direction: p.direction, value_type: 'real_scalar', units: '' })),
    source: { encoding: 'base64', media_type: 'text/x-python', bytes: source.toString('base64'), sha256: hash } }, { kind: 'instantiate', temp_key: `i${i}`, version_ref: { temp_key: `d${i}` } }]);
  const response = await page.request.post(path + '/edits', { headers: { 'X-CSRF-Token': csrf, Origin: servedOrigin() }, data: { command_id: crypto.randomUUID(), expected_revision: (await read()).draft_revision, edits } }); expect(response.ok()).toBeTruthy();
  await page.getByRole('button', { name: 'Refresh model', exact: true }).click(); await expect(page.getByRole('button', { name: 'Select Producer', exact: true })).toBeVisible();
  let writes = 0; page.on('request', r => { if (r.url().endsWith(path + '/edits') && r.method() === 'POST') writes++; });
  return { read, path, get writes() { return writes; } };
}
async function queue(page: Page) {
  for (const [out, input] of [['a', 'x'], ['b', 'y']]) {
    await page.getByRole('combobox', { name: 'Connection output', exact: true }).selectOption({ label: `Producer · ${out} (dimensionless)` });
    await page.getByRole('combobox', { name: 'Connection input', exact: true }).selectOption({ label: `Consumer · ${input} (dimensionless)` });
    await page.getByRole('button', { name: 'Queue connection', exact: true }).click();
  }
}
test('queued connections survive preview dismissal and navigation cancellation, then discard or save atomically', async ({ page }) => {
  const f = await fixture(page), before = await f.read(); await queue(page);
  await page.getByRole('button', { name: 'Preview queued connections', exact: true }).click();
  await page.getByRole('dialog', { name: 'Preview changes' }).getByRole('button', { name: 'Keep editing', exact: true }).click();
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  const dirty = page.getByRole('dialog', { name: 'Unsaved changes', exact: true }); await expect(dirty).toBeVisible();
  await dirty.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Remove queued row/ })).toHaveCount(2); expect(await f.read()).toEqual(before); expect(f.writes).toBe(0);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await page.getByRole('button', { name: 'Model', exact: true }).click(); await tools(page); await expect(page.getByRole('button', { name: /^Remove queued row/ })).toHaveCount(0); expect(await f.read()).toEqual(before);
  await queue(page); await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty.getByRole('button', { name: 'Save changes', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true }); await expect(preview).toContainText('2 edits'); expect(f.writes).toBe(0);
  await preview.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(page.getByRole('button', { name: 'Configurations', exact: true })).toHaveAttribute('aria-current', 'page');
  expect((await f.read()).connections).toHaveLength(2); expect(f.writes).toBe(1);
});
test('rename and add-component drafts are guarded, retained and saved in one preview; filters stay local', async ({ page }) => {
  const f = await fixture(page); await page.getByText('Model name', { exact: true }).click(); await page.getByLabel('Rename model', { exact: true }).fill('Reviewed model');
  await page.getByLabel('New component name').fill('Third'); await page.getByLabel('Output symbols').fill('result');
  await page.getByRole('button', { name: 'Refresh model', exact: true }).click();
  const dirty = page.getByRole('dialog', { name: 'Unsaved changes', exact: true }); await expect(dirty).toBeVisible(); await dirty.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByLabel('Rename model', { exact: true })).toHaveValue('Reviewed model'); await expect(page.getByLabel('New component name')).toHaveValue('Third');
  await page.getByRole('button', { name: 'Configurations', exact: true }).click(); await dirty.getByRole('button', { name: 'Save changes', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true }); await expect(preview).toContainText('3 edits'); expect(f.writes).toBe(0);
  await preview.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(page.getByRole('button', { name: 'Configurations', exact: true })).toHaveAttribute('aria-current', 'page');
  const after = await f.read(); expect(after.name).toBe('Reviewed model'); expect(after.instances.some((i: any) => i.name === 'Third')).toBeTruthy(); expect(f.writes).toBe(1);
  await page.getByRole('button', { name: 'Model', exact: true }).click(); await page.getByLabel('Filter loaded studies').fill('not a match');
  await page.getByRole('button', { name: 'Runs', exact: true }).click(); await expect(dirty).not.toBeVisible();
});
test('lost batch acknowledgement retains queued edits and reconciles one original command', async ({ page }) => {
  const f = await fixture(page); await queue(page); let command = '';
  await page.route(`**${f.path}/edits`, async route => { command = route.request().postDataJSON().command_id; await route.fetch(); await route.abort('failed'); });
  await page.getByRole('button', { name: 'Preview queued connections', exact: true }).click();
  const preview = page.getByRole('dialog', { name: 'Preview changes', exact: true }); await preview.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(preview).toContainText('This proposal cannot submit a second command');
  await preview.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Remove queued row/ })).toHaveCount(2);
  const receipt = page.waitForRequest(r => r.url().includes(`/commands/${command}?category=model`));
  await page.getByRole('button', { name: 'Check original command', exact: true }).click(); await receipt;
  await expect(page.getByText(/Original command: committed/)).toBeVisible(); expect(f.writes).toBe(1); expect((await f.read()).connections).toHaveLength(2);
  await page.getByRole('button', { name: 'Refresh model', exact: true }).click(); await page.getByRole('dialog', { name: 'Unsaved changes', exact: true }).getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Remove queued row/ })).toHaveCount(0); expect(f.writes).toBe(1);
});
