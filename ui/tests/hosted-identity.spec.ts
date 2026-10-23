import { test, expect, chromium } from 'playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromiumExecutable } from './support/browser';

test('verified people have private workspaces and account switching clears private content', async ({ browser, baseURL }, info) => {
  const a = await browser.newContext({ baseURL, ignoreHTTPSErrors: true,
    extraHTTPHeaders: { 'Cf-Access-Jwt-Assertion': process.env.HYPRN_HOSTED_TEST_A! } });
  const b = await browser.newContext({ baseURL, ignoreHTTPSErrors: true,
    extraHTTPHeaders: { 'Cf-Access-Jwt-Assertion': process.env.HYPRN_HOSTED_TEST_B! } });
  try {
    const page = await a.newPage();
    await page.goto('/ui/');
    await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
    await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'New study', exact: true }).click();
    await page.getByLabel('Study name').fill('Alice private engineering');
    await page.getByLabel('Study question', { exact: true })
      .fill('What must this engineering study establish?');
    await page.getByRole('button', { name: 'Create study', exact: true }).click();
    await expect(page.getByText('Alice private engineering', { exact: true }).first()).toBeVisible();
    const other = await b.newPage();
    await other.goto('/ui/');
    await expect(other.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
    await expect(other.getByText('Loading studies…', { exact: true })).toHaveCount(0);
    await expect(other.getByText('Alice private engineering')).toHaveCount(0);
    for (const theme of ['light', 'dark']) {
      await other.evaluate(value => { localStorage.setItem('hyprn-appearance', value); }, theme);
      await other.reload();
      await expect(other.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
      await expect(other.getByText('Loading studies…', { exact: true })).toHaveCount(0);
      await other.screenshot({ path: info.outputPath(`hosted-${theme}.png`) });
    }
    await other.setViewportSize({ width: 720, height: 500 });
    await other.keyboard.press('Tab');
    await expect(other.locator(':focus')).toBeVisible();
    expect(await other.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    // Change the verified ingress identity while retaining A's cookie.
    await a.setExtraHTTPHeaders({ 'Cf-Access-Jwt-Assertion': process.env.HYPRN_HOSTED_TEST_B! });
    await page.getByRole('button', { name: 'Home', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Sign-in could not be completed' })).toBeVisible();
    await expect(page.getByText('Alice private engineering')).toHaveCount(0);
    expect(new URL(page.url()).hash).toBe('');
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
    await expect(page.getByText('Alice private engineering')).toHaveCount(0);
    await expect(page.getByText('Loading studies…', { exact: true })).toHaveCount(0);
    await a.setExtraHTTPHeaders({ 'Cf-Access-Jwt-Assertion': 'invalid' });
    await page.getByRole('button', { name: 'New study', exact: true }).click();
    await page.getByLabel('Study name').fill('denied');
    await page.getByLabel('Study question', { exact: true })
      .fill('What must this engineering study establish?');
    await page.getByRole('button', { name: 'Create study', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Sign-in could not be completed' })).toBeVisible();
    await expect(page.getByText('Alice private engineering')).toHaveCount(0);
    // The provider logout endpoint is outside this product fixture. Observe navigation.
    await other.route('**/cdn-cgi/access/logout', route => route.fulfill({
      status: 200, contentType: 'text/plain', body: 'External sign-out boundary' }));
    await other.getByRole('button', { name: 'Sign out', exact: true }).click();
    await expect(other).toHaveURL(/\/cdn-cgi\/access\/logout$/);
    expect((await b.cookies()).filter(cookie => cookie.name === 'hyprn_mvp_session')).toHaveLength(0);
  } finally { await a.close(); await b.close(); }
});

test('hosted sign-in and account controls remain reachable at genuine 200 percent zoom', async ({ baseURL }, info) => {
  const extension = info.outputPath('zoom-extension');
  await mkdir(extension, { recursive: true });
  await writeFile(join(extension, 'manifest.json'), JSON.stringify({
    manifest_version: 3, name: 'Isolated hosted zoom', version: '1.0',
    permissions: ['tabs'], background: { service_worker: 'worker.js' },
  }));
  await writeFile(join(extension, 'worker.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
  const context = await chromium.launchPersistentContext(info.outputPath('zoom-profile'), {
    executablePath: chromiumExecutable(), headless: true, viewport: null, ignoreHTTPSErrors: true,
    extraHTTPHeaders: { 'Cf-Access-Jwt-Assertion': process.env.HYPRN_HOSTED_TEST_B! },
    args: ['--disable-extensions-except=' + extension, '--load-extension=' + extension,
      '--window-size=1440,1000', '--no-first-run'],
  });
  try {
    const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker');
    const page = context.pages()[0] ?? await context.newPage();
    await page.goto(baseURL + '/ui/');
    await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
    const before = await page.evaluate(() => innerWidth);
    const tabId = await worker.evaluate(async origin => {
      const chrome = (globalThis as any).chrome;
      const tab = (await chrome.tabs.query({})).find((tab: any) => tab.url?.startsWith(origin + '/ui/'));
      if (!tab?.id) throw new Error('Isolated hosted tab absent');
      await chrome.tabs.setZoomSettings(tab.id, { mode: 'automatic', scope: 'per-tab' });
      await chrome.tabs.setZoom(tab.id, 2);
      return tab.id;
    }, baseURL);
    expect(await worker.evaluate(id => (globalThis as any).chrome.tabs.getZoom(id), tabId)).toBe(2);
    await expect.poll(() => page.evaluate(() => innerWidth)).toBe(Math.round(before / 2));
    expect(page.viewportSize()).toBeNull();
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => localStorage.setItem('hyprn-appearance', value), theme);
      await page.reload();
      const control = page.getByRole('button', { name: 'New study', exact: true });
      await expect(control).toBeVisible();
      await expect(page.getByText('Loading studies…', { exact: true })).toHaveCount(0);
      await control.focus();
      await page.keyboard.press('Tab');
      await page.keyboard.press('Shift+Tab');
      await expect(control).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
      await page.screenshot({ path: info.outputPath(`zoom-${theme}.png`) });
    }
  } finally { await context.close(); }
});

test('an Access redirect clears private content without following a cross-origin login request', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ baseURL, ignoreHTTPSErrors: true,
    extraHTTPHeaders: { 'Cf-Access-Jwt-Assertion': process.env.HYPRN_HOSTED_TEST_B! } });
  try {
    const page = await context.newPage();
    await page.goto('/ui/');
    await page.getByRole('button', { name: 'New study', exact: true }).click();
    await page.getByLabel('Study name').fill('Redirect private content');
    await page.getByLabel('Study question', { exact: true })
      .fill('What must this engineering study establish?');
    await page.getByRole('button', { name: 'Create study', exact: true }).click();
    await expect(page.getByText('Redirect private content', { exact: true }).first()).toBeVisible();
    let remoteRequests = 0;
    await page.route('https://login.example.invalid/**', route => { remoteRequests++; return route.abort(); });
    await page.route('**/api/1/studies?**', route => route.fulfill({ status: 302,
      headers: { Location: 'https://login.example.invalid/' } }));
    await page.getByRole('button', { name: 'Home', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Sign-in could not be completed' })).toBeVisible();
    await expect(page.getByText('Redirect private content')).toHaveCount(0);
    expect(remoteRequests).toBe(0);
  } finally { await context.close(); }
});
