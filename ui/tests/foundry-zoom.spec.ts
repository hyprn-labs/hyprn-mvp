import { test, expect, chromium, type Page, type Locator } from 'playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { startFixture, stopFixture, guardOrigin, harness, login, runFixture, sid, mid, details } from './foundry-fixtures';
import { chromiumExecutable } from './support/browser';

test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Fixture build required');
test('genuine 200 percent browser zoom keeps every Foundry route and dialog reachable', async () => {
  test.setTimeout(120000);
  const evidence = process.env.HYPRN_MVP_UI_EVIDENCE_ROOT!;
  const extension = join(evidence, 'zoom-extension');
  await mkdir(extension, { recursive: true });
  await writeFile(join(extension, 'manifest.json'), JSON.stringify({
    manifest_version: 3, name: 'HYPRN MVP local fixture zoom', version: '1.0',
    permissions: ['tabs'], background: { service_worker: 'worker.js' },
  }));
  await writeFile(join(extension, 'worker.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
  const origin = await startFixture();
  const context = await chromium.launchPersistentContext(join(evidence, 'zoom-profile'), {
    executablePath: chromiumExecutable(),
    headless: true, viewport: null,
    args: ['--disable-extensions-except=' + extension, '--load-extension=' + extension,
      '--window-size=1440,1000', '--no-first-run'],
  });
  let worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker');
  let tabId: number | undefined;
  const observations: unknown[] = [];
  let fixturePage: Page | undefined;
  try {
    const page = context.pages()[0] ?? await context.newPage(); fixturePage = page;
    await guardOrigin(page);
    const state = await harness(page); runFixture(state);
    for (const input of state.detail.history.configuration.inputs) input.provenance.evidence_version_ids = [];
    state.configurations = [{ configuration: state.detail.history.configuration, model_snapshot: state.detail.history.model_snapshot }];
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await login(page);
    const cdp = await context.newCDPSession(page);
    const window = await cdp.send('Browser.getWindowForTarget');
    // Native window resize compensates chrome decorations; viewport emulation stays disabled.
    for (let attempt = 0; attempt < 3; attempt++) {
      const css = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
      if (css.width === 1440 && css.height === 1000) break;
      const current = await cdp.send('Browser.getWindowBounds', { windowId: window.windowId });
      await cdp.send('Browser.setWindowBounds', { windowId: window.windowId, bounds: {
        width: current.bounds.width! + 1440 - css.width,
        height: current.bounds.height! + 1000 - css.height,
      } });
      await expect.poll(() => page.evaluate(() => ({ width: innerWidth, height: innerHeight }))).toEqual({ width: 1440, height: 1000 });
    }
    const before = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio }));
    expect(before.width).toBe(1440); expect(before.height).toBe(1000);
    tabId = await worker.evaluate(async (origin) => {
      const chrome = (globalThis as any).chrome;
      const tabs = await chrome.tabs.query({});
      const tab = tabs.find((tab: any) => tab.url?.startsWith(origin + '/ui/'));
      if (!tab?.id) throw new Error('Exact isolated fixture tab absent');
      await chrome.tabs.setZoomSettings(tab.id, { mode: 'automatic', scope: 'per-tab' });
      await chrome.tabs.setZoom(tab.id, 2);
      return tab.id;
    }, origin);
    const factor = await worker.evaluate(id => (globalThis as any).chrome.tabs.getZoom(id), tabId);
    expect(factor).toBe(2);
    await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);
    const after = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio }));
    expect(after.height).toBe(500);
    observations.push({ browser: context.browser()?.version(), zoom: factor, before, after, viewportEmulation: page.viewportSize() });
    expect(page.viewportSize()).toBeNull();

    async function check(name: string, target: Locator) {
      expect(
        await worker.evaluate(id => (globalThis as any).chrome.tabs.getZoom(id), tabId),
      ).toBe(2);
      await expect(target).toBeVisible();
      await target.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab');
      await expect(target).toBeFocused();
      const focus = await target.evaluate(el => ({ width: getComputedStyle(el).outlineWidth, style: getComputedStyle(el).outlineStyle }));
      expect(focus.width, name).toBe('2px'); expect(focus.style, name).not.toBe('none');
      await expect.poll(async () => { const box = await target.boundingBox(); return !!box && box.y >= 0 && box.y + box.height <= 501; }, { message: name + ' focused control visible vertically' }).toBe(true);
      const bounds = await target.boundingBox();
      expect(bounds!.x, name).toBeGreaterThanOrEqual(0);
      expect(bounds!.y, name).toBeGreaterThanOrEqual(0);
      expect(bounds!.y + bounds!.height, name).toBeLessThanOrEqual(501);
      const hit = await target.evaluate(el => { const box = el.getBoundingClientRect(); const at = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2); return { unobstructed: at === el || el.contains(at), target: el.tagName, hit: at?.tagName }; });
      expect(hit.unobstructed, name + ': ' + JSON.stringify(hit)).toBe(true);
      expect(bounds!.x + bounds!.width, name).toBeLessThanOrEqual(721);
      const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
      expect(layout.scroll, name).toBeLessThanOrEqual(layout.width + 1);
      observations.push({ name, focus, layout, bounds, hit });
      await page.screenshot({ path: join(evidence, name + '-200.png'), fullPage: true });
    }
    const button = (name: string) => page.getByRole('button', { name, exact: true });
    for (const theme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme: theme });
      await button('Home').click();
      await check('home-' + theme, button('New study'));
      await page.keyboard.press('Enter'); await check('new-study-' + theme, page.getByLabel('New study name'));
      await button('Cancel').click(); await button('Profile').click();
      await check('profile-' + theme, button('Sign out'));
      await button('Home').click(); await button('Open study Scalar model study').click();
      await check('overview-approach-' + theme, button('View modeling approach'));
      await check('overview-' + theme, button('Edit study'));
      await page.keyboard.press('Enter');
      await check(
        'study-dialog-' + theme,
        page.getByLabel('Study list description', { exact: true }),
      );
      await page.keyboard.press('Escape');
      await button('Models').click(); await check('models-' + theme, button('New model'));
      await page.goto(origin + '/ui/#v=1&study=' + sid + '&model=' + mid + '&view=model');
      await expect(page.getByRole('heading', { name: 'Response chain', exact: true })).toBeVisible();
      // Graph | XDSM on top; the quantities table is always below in its own scroll region.
      await expect(page.getByRole('tab', { name: 'Variables', exact: true })).toHaveCount(0);
      for (const view of ['Graph', 'XDSM', 'Quantities']) {
        const tab = view === 'Quantities' ? page.getByRole('region', { name: 'Quantities table', exact: true }) : page.getByRole('tab', { name: view, exact: true });
        if (view !== 'Quantities') { await tab.focus(); await page.keyboard.press('Enter'); await check('model-' + view.toLowerCase() + '-' + theme, tab); }
        if (view === 'Quantities') {
          const table = page.locator('.quantities-scroll').first();
          const dimensions = await table.evaluate(el => ({ width: el.clientWidth, scroll: el.scrollWidth, overflow: getComputedStyle(el).overflowX, tabindex: el.getAttribute('tabindex') }));
          expect(dimensions.overflow).toBe('auto');
          if (dimensions.scroll > dimensions.width) {
            await table.focus(); await page.keyboard.press('ArrowRight');
            await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0);
          } else {
            // The five-column quantities table can fit at 200% zoom.
            await expect(table.getByRole('columnheader', { name: 'Unit', exact: true })).toBeVisible();
            expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width);
          }
          observations.push({ name: 'local-table-scroll-' + theme, dimensions });
        }
      }
      await page.getByRole('tab', { name: 'Graph', exact: true }).click();
      await page.locator('.connected-graph [data-instance="a"]').click();
      // Details stack What it computes · Why · Assumptions with Edit and Edit ports; no tabs, no ports table.
      await expect(details(page).getByRole('tab')).toHaveCount(0); await expect(details(page).locator('table')).toHaveCount(0);
      for (const name of ['Edit quantities', 'Add assumption']) {
        const control = details(page).getByRole('button', { name, exact: true });
        await control.scrollIntoViewIfNeeded();
        await check('details-' + name.toLowerCase().replace(' ', '-') + '-' + theme, control);
        if (name === 'Edit quantities') {
          // Quantities table at genuine 200%: Unit (column 5) stays on one readable line;
          // the definition (column 4) wraps inside its own cell.
          const ports = page.getByRole('table', { name: 'Quantities', exact: true });
          await expect(ports.locator('thead th')).toHaveText([
            'Quantity',
            'Component',
            'Direction',
            'Definition',
            'Unit',
          ]);
          const rows = await ports.evaluate((t) =>
            [...t.querySelectorAll('tbody tr')].map((tr) => {
              const cell = (n: number) => {
                const e = tr.children[n] as HTMLElement,
                  r = document.createRange();
                r.selectNodeContents(e);
                return {
                  text: e.textContent,
                  lines: r.getClientRects().length,
                  fits: e.scrollWidth <= e.clientWidth,
                  textRight: r.getBoundingClientRect().right,
                  cellRight: e.getBoundingClientRect().right,
                };
              };
              return { definition: cell(3), units: cell(4) };
            }),
          );
          expect(rows.length).toBeGreaterThan(0);
          for (const row of rows) {
            expect(row.units.lines, JSON.stringify(row)).toBe(1);
            expect(row.units.fits, JSON.stringify(row)).toBe(true);
            expect(row.definition.fits, JSON.stringify(row)).toBe(true);
            expect(row.definition.textRight, JSON.stringify(row)).toBeLessThanOrEqual(
              row.definition.cellRight + 1,
            );
          }
          observations.push({ name: 'port-table-' + theme, rows });
          await ports.scrollIntoViewIfNeeded();
          const shot = await cdp.send('Page.captureScreenshot', {
            format: 'png',
            fromSurface: true,
            captureBeyondViewport: false,
          });
          await writeFile(
            join(evidence, 'details-port-table-' + theme + '-200.png'),
            Buffer.from(shot.data, 'base64'),
          );
        }
      }
      await button('Configurations').click(); await check('configurations-' + theme, button('New configuration'));
      await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
      await check('configuration-saved-' + theme, button('Copy configuration to draft'));
      await button('Copy configuration to draft').click();
      await check('configuration-new-' + theme, page.getByLabel('Configuration name', { exact: true }));
      await button('Input tools').click();
      await button('Add evidence').first().click(); await expect(page.getByRole('dialog').locator('.evidence-record')).toHaveCount(1); await check('evidence-picker-' + theme, page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }));
      await page.keyboard.press('Escape');
      await button('Close Input tools and model binding').click();
      await button('Runs').click();
      if (await page.getByRole('dialog', { name: 'Unsaved changes' }).isVisible()) await button('Discard changes').click();
      await check('runs-' + theme, button('Inspect run run-fixture'));
      await button('Inspect run run-fixture').click();
      for (const name of ['Results', 'Model', 'Configuration']) {
        const tab = page.getByRole('tab', { name, exact: true });
        await tab.focus();
        await page.keyboard.press('Enter');
        await check('run-' + name.split(' ')[0].toLowerCase() + '-' + theme, tab);
      }
      await page.goto(origin + '/ui/#v=1&study=' + sid + '&view=evidence');
      await check('evidence-' + theme, page.getByLabel('Filter evidence', { exact: true }));
      await page.goto(origin + '/ui/?specimen');
      await worker.evaluate(id => (globalThis as any).chrome.tabs.setZoom(id, 2), tabId);
      await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);
      expect(
        await worker.evaluate((id) => (globalThis as any).chrome.tabs.getZoom(id), tabId),
      ).toBe(2);
      await check(
        'specimen-claims-' + theme,
        page.getByRole('button', { name: '2 statements · Complete set', exact: true }),
      );
      await check(
        'specimen-context-' + theme,
        page.getByRole('button', { name: 'Close Specimen context', exact: true }),
      );
      await check(
        'specimen-assistant-' + theme,
        page.getByRole('button', { name: 'Close Assistant', exact: true }),
      );
      await page.getByRole('button', { name: 'Open recipe dialog', exact: true }).click();
      await check(
        'specimen-dialog-' + theme,
        page
          .getByRole('dialog', { name: 'Recipe dialog', exact: true })
          .getByRole('button', { name: 'Done', exact: true }),
      );
      await page.keyboard.press('Escape');
      await login(page);
      await worker.evaluate(id => (globalThis as any).chrome.tabs.setZoom(id, 2), tabId);
      await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);

    }
    expect(state.unknown).toEqual([]);
    expect(state.writes).toEqual([]);
  } catch (error) {
    await fixturePage?.screenshot({ path: join(evidence, 'zoom-failure.png') });
    throw error;
  } finally {
    if (tabId !== undefined) {
      await worker.evaluate(id => (globalThis as any).chrome.tabs.setZoom(id, 1), tabId);
      observations.push({ restoredZoom: await worker.evaluate(id => (globalThis as any).chrome.tabs.getZoom(id), tabId) });
    }
    await writeFile(join(evidence, 'zoom.json'), JSON.stringify(observations, null, 2));
    await context.close(); await stopFixture();
  }
});
