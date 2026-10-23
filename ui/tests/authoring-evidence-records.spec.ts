import { test, expect, Page } from 'playwright/test';
import { writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';

// Actual public API only: isolated new authoring records, no candidate execution.
async function login(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
}
async function data(page: Page, path: string) { const r = await page.request.get(path); expect(r.ok()).toBeTruthy(); return (await r.json()).data; }
async function apply(page: Page) { const d = page.getByRole('dialog', { name: 'Preview changes', exact: true }); await d.getByRole('button', { name: 'Apply changes', exact: true }).click(); await expect(d).toHaveCount(0); }
async function disclose(page: Page, name: string) { const s = page.locator('summary').filter({ hasText: new RegExp(`^${name}$`) }); const d = s.locator('..'); if (await d.getAttribute('open') === null) await s.click(); }
const retain = (name: string, value: unknown) => writeFileSync(evidencePath(name), JSON.stringify(value, null, 2));

test('real simplified authoring and evidence configuration retain exact records without running', async ({ page }) => {
  test.setTimeout(120000);
  const traffic: { method: string; url: string }[] = [];
  page.on('request', r => { if (['fetch', 'xhr'].includes(r.resourceType())) traffic.push({ method: r.method(), url: r.url() }); });
  await login(page);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.locator('.profile-page dd')).toHaveText('owner');
  await page.getByRole('button', { name: 'Home', exact: true }).focus(); await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('Study name').fill('Simple UI18 ' + crypto.randomUUID());
  const studyResponse = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/1/studies'));
  await page.getByLabel('Study question', { exact: true })
    .fill('What must this engineering study establish?');
  await page.getByRole('button', { name: 'Create study', exact: true }).click(); const study = (await (await studyResponse).json()).data;
  retain('new-study.json', study);
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await page.getByRole('button', { name: 'New model', exact: true }).click();
  await page.getByLabel('New model name').fill('Explicit unexecuted scalar');
  const modelResponse = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/models'));
  await page.getByRole('button', { name: 'Create model', exact: true }).click(); const model = (await (await modelResponse).json()).data;
  const base = `/api/1/studies/${study.study_id}`, path = `${base}/models/${model.model_id}`;
  retain('scope.json', { study_id: study.study_id, model_id: model.model_id });
  await disclose(page, 'Add component'); await page.getByLabel('New component name').fill('Scalar');
  await page.getByLabel('Input symbols', { exact: true }).fill('x'); await page.getByLabel('Output symbols', { exact: true }).fill('y');
  await page.getByRole('button', { name: 'Add component', exact: true }).click(); await apply(page);
  await disclose(page, 'Source');
  const source = '# exact source: café\noutputs["y"] = 2 * inputs["x"]\n';
  await page.getByLabel('Python source', { exact: true }).fill(source);
  await disclose(page, 'Ports'); await page.getByLabel('Port 1 units', { exact: true }).fill('m'); await page.getByLabel('Port 2 units', { exact: true }).fill('m');
  await page.getByRole('button', { name: 'Save component', exact: true }).click(); await apply(page);
  await page.getByRole('button', { name: 'Add another instance', exact: true }).click(); await apply(page);
  await page.getByLabel('Component name', { exact: true }).fill('Repeated');
  await page.getByRole('button', { name: 'Save component', exact: true }).click(); await apply(page);
  const draft = await data(page, path); retain('authored-draft.json', draft);
  expect(draft.instances.filter((i: any) => i.name === 'Scalar' || i.name === 'Repeated')).toHaveLength(2);
  expect(draft.source_files.some((f: any) => f.sha256 === createHash('sha256').update(source).digest('hex'))).toBeTruthy();
  await page.getByRole('tab', { name: 'XDSM', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('tab', { name: 'XDSM', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: 'Variables', exact: true }).click();
  await page.getByRole('tab', { name: 'Graph', exact: true }).click();
  await page.screenshot({ path: evidencePath('model-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: evidencePath('model-compact.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'Save model version', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill('Saved zero inputs; no execution');
  for (const name of ['Scalar', 'Repeated']) { await page.getByLabel(`${name} · x value`, { exact: true }).fill('0'); await page.getByLabel(`${name} · x provenance`, { exact: true }).fill('Explicit synthetic zero, not a default'); }
  const attachment = page.getByRole('region', { name: 'Scalar · x evidence', exact: true });
  await attachment.getByRole('button', { name: 'Add evidence', exact: true }).click();
  const dialog = page.getByRole('dialog'); await dialog.getByRole('button', { name: 'Create new', exact: true }).click();
  await dialog.getByLabel('Evidence note', { exact: true }).fill('Real API note with inert <script>text</script>');
  await dialog.getByLabel('Source references', { exact: true }).fill('Plan18 isolated UI verification');
  await dialog.getByRole('button', { name: 'Create and attach note', exact: true }).click(); await expect(dialog).toHaveCount(0);
  const notes = await data(page, `${base}/evidence`); expect(notes).toHaveLength(1); const note = notes[0]; retain('evidence.json', note);
  expect(note.resource_scope.kind).toBe('port');
  await page.getByRole('region', { name: 'Context evidence notes', exact: true }).getByRole('button', { name: 'Add evidence', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /^Attach note / }).click();
  const savedResponse = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/configurations'));
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  const saved = (await (await savedResponse).json()).data; retain('configuration.json', saved);
  await expect(page.getByText('Configuration saved. Run is a separate action.', { exact: true })).toBeVisible();
  expect(saved.configuration.inputs.map((i: any) => i.value)).toEqual([0, 0]);
  expect(saved.configuration.inputs.find((i: any) => i.target.instance_id === note.resource_scope.instance_id).provenance.evidence_version_ids).toEqual([note.evidence_version_id]);
  const { evidence_id, study_id, ...snapshot } = note; expect(saved.configuration.evidence_snapshots).toEqual([snapshot]);
  expect(saved.configuration.model_revision_id).toBe(note.resource_scope.model_revision_id);
  expect((await data(page, `${base}/configurations/${saved.configuration.configuration_revision_id}`)).configuration).toEqual(saved.configuration);
  await page.screenshot({ path: evidencePath('configuration-desktop.png'), fullPage: true });
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Evidence library' })).toContainText(note.content);
  expect(await data(page, `${base}/runs`)).toEqual([]);
  expect(traffic.some(r => r.method === 'POST' && r.url.endsWith('/runs'))).toBe(false);
  expect(traffic.every(r => r.url.startsWith(servedOrigin() + '/api/1/'))).toBeTruthy(); retain('public-traffic.json', traffic);
});
