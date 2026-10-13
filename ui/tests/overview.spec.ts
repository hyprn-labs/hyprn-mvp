import { test, expect, Page } from 'playwright/test';
import { evidencePath } from './evidence';
import { ownerPassword } from './support/served';

const sid = 'dec4f9d0-e125-4f9a-8908-8dbc22cd105a';
const rid = '6e80a9ea-5f6a-4edf-a2fa-95826ab3733f';
const cid = '98d6bf68-42e2-4be7-8668-17b0d967c8f2';
async function login(page: Page, study = sid) {
  await page.goto('/ui/#v=1&study=' + study + '&view=overview');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
}

test('saved description alone matches loaded study filter', async ({ page }) => {
  await login(page);
  const name = 'Overview search ' + crypto.randomUUID();
  const description = 'description-only-' + crypto.randomUUID();
  await page.getByLabel('New study name').fill(name);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.getByText('Study context', { exact: true }).click();
  await page.getByLabel('Description', { exact: true }).fill(description);
  await page.getByRole('button', { name: 'Save study context', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save study context', exact: true })).toBeDisabled();
  await page.getByLabel('Filter loaded studies').fill(description);
  await expect(page.getByText(/1 of \d+ loaded studies/)).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Study', exact: true }).locator('option:checked')).toHaveText(name);
});

test('Overview reads retained records and exact navigation preserves dirty context', async ({ page }) => {
  await login(page);
  const configs = page.getByRole('region', { name: 'Recent configurations', exact: true });
  const runs = page.getByRole('region', { name: 'Recent runs', exact: true });
  await expect(configs.getByRole('button', { name: 'Manual 7 and49 · Open configuration ' + cid, exact: true })).toBeVisible();
  const configButton = configs.getByRole('button', { name: 'Manual 7 and49 · Open configuration ' + cid, exact: true });
  await expect(configButton).toHaveText('Manual 7 and49');
  await expect(runs.getByRole('button', { name: 'Open run ' + rid, exact: true })).toBeVisible();
  // Full identities live in Record details, not in Overview disclosures.
  await expect(page.getByText(/^Exact (run|configuration) identities$/)).toHaveCount(0);
  await expect(configs).not.toContainText(cid);
  await expect(runs).not.toContainText(rid);
  await expect(runs.getByRole('button', { name: 'Open run ' + rid, exact: true })).toHaveText(new RegExp(' · ' + rid.slice(0, 8) + '$'));
  await page.screenshot({ path: evidencePath('overview-1440.png'), fullPage: true });
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.screenshot({ path: evidencePath('overview-1024.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByText('Study context', { exact: true }).click();
  const description = page.getByRole('textbox', { name: 'Description', exact: true });
  const original = await description.inputValue();
  await description.fill(original + '\nunsaved overview proposal');
  await configs.getByRole('button', { name: 'Manual 7 and49 · Open configuration ' + cid, exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Unsaved changes' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(description).toHaveValue(original + '\nunsaved overview proposal');
  await configs.getByRole('button', { name: 'Manual 7 and49 · Open configuration ' + cid, exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page).toHaveURL(new RegExp('configuration=' + cid));
  await expect(page.getByText('Read-only immutable configuration', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.getByText('Study context', { exact: true }).click();
  await description.fill('unsaved run navigation proposal');
  await runs.getByRole('button', { name: 'Open run ' + rid, exact: true }).click();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(description).toHaveValue('unsaved run navigation proposal');
  await runs.getByRole('button', { name: 'Open run ' + rid, exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page).toHaveURL(new RegExp('run=' + rid));
  await expect(page.getByRole('heading', { name: 'Run ' + rid, exact: true })).toBeVisible();
});
