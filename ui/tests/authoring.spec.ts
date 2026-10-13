import { test, expect, Page } from 'playwright/test';
import { writeFileSync } from 'node:fs';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';
async function openModelTools(page: Page) { const tools = page.locator('details.model-tools'); if (await tools.count() && await tools.getAttribute('open') === null) await tools.locator(':scope > summary').click(); }

async function login(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const session = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Create study', exact: true })).toBeVisible();
  return (await (await session).json()).data.csrf_token as string;
}
async function createStudy(page: Page) {
  const name = `Authoring ${crypto.randomUUID()}`;
  await page.getByLabel('New study name').fill(name);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.getByLabel('New model name').fill('Scalar chain');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByText('Add a component to start.', { exact: true })).toBeVisible();
  return name;
}
async function apply(page: Page, pending = false) {
  const dialog = page.getByRole("dialog", { name: "Preview changes", exact: true });
  await expect(dialog.getByRole("button", { name: "Apply changes", exact: true })).toBeEnabled();
  await dialog.getByRole("button", { name: "Apply changes", exact: true }).click();
  if (!pending) await expect(dialog).not.toBeVisible();
}
async function component(page: Page, name: string, input: string, output: string) {
  await openModelTools(page);
  await page.getByLabel('New component name').fill(name);
  await page.getByLabel('Input symbols').fill(input);
  await page.getByLabel('Output symbols').fill(output);
  await page.getByRole('button', { name: 'Add component', exact: true }).click();
  await apply(page);
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue(name);
}
test('author, connect, save and reload exact scalar source through the public API', async ({ page }) => {
  const traffic: Array<{ method: string; url: string }> = [];
  page.on('request', r => { if (['fetch', 'xhr'].includes(r.resourceType())) traffic.push({ method: r.method(), url: r.url() }); });
  await login(page);
  const name = await createStudy(page);
  await component(page, 'Scale', 'x, k', 'u');
  const source = '# café — source remains exact\noutputs["u"] = inputs["k"] * inputs["x"] + 1\n\n';
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill(source);
  await page.getByText('Assumptions', { exact: true }).click();
  await page.getByLabel('Component assumptions').fill('Real scalar, explicit inputs.');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await component(page, 'Square', 'u', 'y');
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["y"] = inputs["u"] ** 2\n');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await openModelTools(page);
  await page.getByLabel('Connection output').selectOption({ label: 'Scale · u (dimensionless)' });
  await page.getByLabel('Connection input').selectOption({ label: 'Square · u (dimensionless)' });
  await page.getByRole('button', { name: 'Connect ports', exact: true }).click();
  await apply(page);
  await expect(page.getByText('Scale · u → Square · u', { exact: true })).toBeVisible();
  await page.reload();
  await login(page);
  await page.getByRole('combobox', { name: 'Study', exact: true }).selectOption({ label: name });
  await page.getByRole('combobox', { name: 'Model', exact: true }).selectOption({ label: 'Scalar chain' });
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select Scale', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveValue(source);
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const snapshot = await page.request.get(`/api/1/studies/${sid}/models/${mid}`);
  const model = (await snapshot.json()).data;
  expect(model.source_files.some((s: { bytes: string }) => Buffer.from(s.bytes, 'base64').toString('utf8') === source)).toBeTruthy();
  expect(model.connections).toHaveLength(1);
  expect(traffic.length).toBeGreaterThan(5);
  expect(traffic.every(r => r.url.startsWith(servedOrigin() + '/api/1/'))).toBeTruthy();
  writeFileSync(evidencePath('browser-public-requests.json'), JSON.stringify(traffic, null, 2));
  writeFileSync(evidencePath('authoring-model.json'), JSON.stringify(model, null, 2));
  await page.screenshot({ path: evidencePath('authoring.png'), fullPage: true });
});

test('dirty navigation keeps focus and text, then explicitly saves or discards', async ({ page }) => {
  await login(page); await createStudy(page);
  await component(page, 'First', 'x', 'y'); await component(page, 'Second', 'a', 'b');
  const source = page.getByRole('textbox', { name: 'Python source', exact: true });
  await source.fill('outputs["b"] = inputs["a"] + 2\n');
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(source).toHaveValue('outputs["b"] = inputs["a"] + 2\n');
  await expect(page.getByRole('button', { name: 'Select First', exact: true })).toBeFocused();
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await apply(page);
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue('First');
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select Second', exact: true }).click();
  await expect(source).toHaveValue('outputs["b"] = inputs["a"] + 2\n');
  await source.fill('discard this');
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select Second', exact: true }).click();
  await expect(source).toHaveValue('outputs["b"] = inputs["a"] + 2\n');
  await source.press('Tab'); await expect(source).not.toBeFocused();
});

test('rejected atomic save preserves edits; competing revision is reviewed without overwriting', async ({ page }) => {
  const csrf = await login(page); await createStudy(page); await component(page, 'Atomic', 'x', 'y');
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue(), mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const path = `/api/1/studies/${sid}/models/${mid}`;
  const before = (await (await page.request.get(path)).json()).data;
  const source = page.getByRole('textbox', { name: 'Python source', exact: true });
  await source.fill('outputs["y"] = inputs["x"] * 8\n');
  await page.getByText('Inputs/outputs', { exact: true }).click();
  await page.getByLabel('Port 1 units', { exact: true }).fill('invented_unit');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await page.getByRole('dialog', { name: 'Preview changes', exact: true }).getByRole('button', { name: 'Keep editing', exact: true }).click();
  await source.click();
  await expect(source).toHaveValue('outputs["y"] = inputs["x"] * 8\n');
  await expect(source).toBeFocused();
  expect((await (await page.request.get(path)).json()).data).toEqual(before);
  await page.getByLabel('Port 1 units', { exact: true }).fill('');
  const competing = await page.request.post(path + '/edits', { headers: { Origin: servedOrigin(), 'X-CSRF-Token': csrf }, data: { command_id: crypto.randomUUID(), expected_revision: before.draft_revision, edits: [{ kind: 'rename_instance', instance_id: before.instances[0].instance_id, name: 'Concurrent name' }] } });
  expect(competing.ok()).toBeTruthy();
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('This model changed. Your edits are preserved; review the current revision.');
  await expect(source).toHaveValue('outputs["y"] = inputs["x"] * 8\n');
  await page.getByRole('button', { name: 'Review current revision', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Current revision differences' })).toBeVisible();
  expect((await (await page.request.get(path)).json()).data).toEqual((await competing.json()).data);
});

test('BOM, CRLF and Unicode file bytes survive source save and a notes-only save', async ({ page }) => {
  await login(page); await createStudy(page); await component(page, 'Bytes', 'x', 'y');
  const raw = Buffer.from('\ufeff# café\r\noutputs["y"] = inputs["x"]\r\n\r\n', 'utf8');
  await page.getByLabel('Load Python source file').setInputFiles({ name: 'bytes.py', mimeType: 'text/x-python', buffer: raw });
  await expect(page.getByRole('status')).toContainText('Source file loaded locally');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await page.getByText('Assumptions', { exact: true }).click();
  await page.getByLabel('Component assumptions').fill('Preserve raw bytes.');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue(), mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const snapshot = (await (await page.request.get(`/api/1/studies/${sid}/models/${mid}`)).json()).data;
  expect(snapshot.source_files.some((s: { bytes: string }) => Buffer.from(s.bytes, 'base64').equals(raw))).toBeTruthy();
  await page.setViewportSize({ width: 720, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: evidencePath('reflow-720.png'), fullPage: true });
});

test('lost save response reconciles its original command and never issues another save', async ({ page }) => {
  await login(page); await createStudy(page); await component(page, 'Receipt', 'x', 'y');
  const path = `/api/1/studies/${await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue()}/models/${await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue()}/edits`;
  let saves = 0;
  await page.route('**' + path, async route => { saves++; await route.fetch(); await route.abort('failed'); });
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill('outputs["y"] = inputs["x"]\n');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page, true);
  await page.getByRole('dialog', { name: 'Preview changes', exact: true }).getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Check original command', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save component', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await expect(page.getByText(/Original command: committed/)).toBeVisible();
  expect(saves).toBe(1);
});

test('request lost before application receipt can explicitly retry the exact original save', async ({ page }) => {
  await login(page); await createStudy(page); await component(page, 'Retry', 'x', 'y');
  const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
  const mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  const path = `/api/1/studies/${sid}/models/${mid}/edits`;
  const saves: Array<{ method: string; body: string | null }> = [];
  await page.route('**' + path, async route => {
    saves.push({ method: route.request().method(), body: route.request().postData() });
    if (saves.length === 1) await route.abort('failed'); else await route.continue();
  });
  const text = 'outputs["y"] = inputs["x"] + 17\n';
  await page.getByRole('textbox', { name: 'Python source', exact: true }).fill(text);
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page, true);
  await page.getByRole('dialog', { name: 'Preview changes', exact: true }).getByRole('button', { name: 'Keep editing', exact: true }).click();
  await page.getByRole('button', { name: 'Check original command', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retry original command', exact: true })).toBeVisible();
  expect(saves).toHaveLength(1);
  await page.getByRole('button', { name: 'Retry original command', exact: true }).click();
  await expect(page.getByText('Original command resolved. Reload the study after reviewing unsaved edits.', { exact: true })).toBeVisible();
  expect(saves).toHaveLength(2); expect(saves[1]).toEqual(saves[0]);
  const model = (await (await page.request.get(`/api/1/studies/${sid}/models/${mid}`)).json()).data;
  expect(model.source_files.some((s: { bytes: string }) => Buffer.from(s.bytes, 'base64').toString('utf8') === text)).toBeTruthy();
});

test('model selection clears old details while loading; optional example and long names reflow', async ({ page }) => {
  await login(page); await createStudy(page); await component(page, 'Old component', 'x', 'y');
  const first = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
  await page.getByLabel('New model name').fill('Example model');
  await page.getByRole('combobox', { name: 'Starting model', exact: true }).selectOption('two_component_example');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select First', exact: true })).toBeVisible();
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select First', exact: true }).click();
  await page.route('**/models/' + first, async route => { await new Promise(resolve => setTimeout(resolve, 500)); await route.continue(); });
  await page.getByRole('combobox', { name: 'Model', exact: true }).selectOption(first);
  await expect(page.getByText('Loading study/model…')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Python source', exact: true })).toHaveCount(0);
  await openModelTools(page);
  await page.getByRole('button', { name: 'Select Old component', exact: true }).click();
  const longName = 'Long engineering component '.repeat(12);
  await page.getByLabel('Component name', { exact: true }).fill(longName);
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await apply(page);
  await expect(page.getByRole('status')).toContainText('Component saved');
  await page.setViewportSize({ width: 720, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  const selection = page.getByRole('button', { name: 'Select ' + longName.trim(), exact: true });
  await expect(selection).toBeVisible(); await selection.focus(); await selection.press('Enter');
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue(longName);
  await page.screenshot({ path: evidencePath('long-name-reflow.png'), fullPage: true });
});

test('invalid source bytes identify the line and preserve the unsaved text', async ({ page }) => {
  await login(page); await createStudy(page); await component(page, 'Invalid source', 'x', 'y');
  const raw = Buffer.from('# line one\noutputs["y"] = \0\n');
  await page.getByLabel('Load Python source file').setInputFiles({ name: 'invalid.py', mimeType: 'text/x-python', buffer: raw });
  await expect(page.getByRole('status')).toContainText('Source file loaded locally');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Python source, line 2: null characters are invalid. Your text is preserved.');
  const source = page.getByRole('textbox', { name: 'Python source', exact: true });
  await expect(source).toHaveValue(raw.toString()); await expect(source).toBeFocused();
});
