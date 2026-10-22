import { test, expect } from 'playwright/test';
import { writeFileSync } from 'node:fs';
import { evidencePath } from './evidence';
import { ownerPassword } from './support/served';

test('served records are inspected through public reads only', async ({ page }) => {
  const faults: string[] = [], blockedWrites: string[] = [];
  page.on('pageerror', error => faults.push(error.message));
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
  await page.route('**/api/1/**', route => {
    if (route.request().method() !== 'GET') { blockedWrites.push(new URL(route.request().url()).pathname); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  const read = async (path: string) => { const response = await page.request.get('/api/1' + path); expect(response.ok()).toBeTruthy(); return (await response.json()).data; };
  const studies = await read('/studies');
  const observations: object[] = [];
  await page.screenshot({ path: evidencePath('home.png'), animations: 'disabled' });
  for (const study of studies.slice(0, 1)) {
    const models = await read(`/studies/${study.study_id}/models`);
    if (models.length) {
      await page.goto(`/ui/#v=1&study=${study.study_id}&model=${models[0].model_id}&view=model`);
      await expect(page.getByRole('button', { name: 'Refresh model', exact: true })).toBeVisible();
      for (const view of ['Graph', 'XDSM', 'Variables']) {
        await page.getByRole('tab', { name: view, exact: true }).click();
        await page.screenshot({ path: evidencePath('model-' + view.toLowerCase() + '.png'), animations: 'disabled' });
      }
      await page.getByRole('button', { name: 'Import model', exact: true }).click();
      await expect(page.getByRole('dialog', { name: 'Import model', exact: true }).getByRole('button', { name: 'Choose file' })).toBeVisible();
      await page.keyboard.press('Escape');
    }
    const configurations = await read(`/studies/${study.study_id}/configurations`);
    if (configurations.length) {
      await page.goto(`/ui/#v=1&study=${study.study_id}&view=configurations&configuration=${configurations[0].configuration.configuration_revision_id}`);
      const saved = page.getByRole('region', { name: 'Saved configuration', exact: true });
      await expect(saved).toBeVisible();
      await expect(saved.getByRole('heading', { level: 3 })).toHaveText(['Inputs and provenance', 'Criteria', 'Context & supporting evidence']);
      await page.screenshot({ path: evidencePath('configuration.png'), animations: 'disabled', fullPage: true });
    }
    const runs = await read(`/studies/${study.study_id}/runs`);
    if (runs.length) {
      await page.goto(`/ui/#v=1&study=${study.study_id}&view=runs&run=${runs.at(-1).run_id}`);
      await expect(page.getByRole('region', { name: 'Run details', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Refresh run status', exact: true })).toBeEnabled();
      await page.screenshot({ path: evidencePath('run.png'), animations: 'disabled', fullPage: true });
    }
    observations.push({ study_id: study.study_id, models: models.length, configurations: configurations.length, runs: runs.length });
  }
  expect(blockedWrites).toEqual([]); expect(faults).toEqual([]);
  writeFileSync(evidencePath('read-only-verification.json'), JSON.stringify({ observations, blockedWrites, faults }, null, 2));
});
