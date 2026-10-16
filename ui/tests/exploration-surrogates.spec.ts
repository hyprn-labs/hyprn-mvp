import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { test, expect, chromium } from 'playwright/test';

import { chromiumExecutable } from './support/browser';

test('warm full-vector predictions render within the interaction budget', async ({ baseURL }) => {
  test.setTimeout(180000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const refining = process.env.HYPRN_MVP_TEST_REFINEMENT_ID;
  const extension = join(root, 'evidence/explorer-zoom-extension');
  await mkdir(extension, { recursive: true });
  await writeFile(
    join(extension, 'manifest.json'),
    JSON.stringify({
      manifest_version: 3,
      name: 'Scoped explorer zoom',
      version: '1.0',
      permissions: ['tabs'],
      background: { service_worker: 'worker.js' },
    }),
  );
  await writeFile(
    join(extension, 'worker.js'),
    'chrome.runtime.onInstalled.addListener(() => {});',
  );
  const context = await chromium.launchPersistentContext(
    join(root, 'evidence/explorer-profile-' + Date.now()),
    {
      executablePath: chromiumExecutable(),
      headless: true,
      viewport: null,
      baseURL,
      args: [
        '--disable-extensions-except=' + extension,
        '--load-extension=' + extension,
        '--window-size=1440,1100',
      ],
    },
  );
  const page = context.pages()[0];
  const cdp = await context.newCDPSession(page);
  const nativeWindow = await cdp.send('Browser.getWindowForTarget');
  const css = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
  const bounds = await cdp.send('Browser.getWindowBounds', { windowId: nativeWindow.windowId });
  await cdp.send('Browser.setWindowBounds', {
    windowId: nativeWindow.windowId,
    bounds: {
      width: bounds.bounds.width! + 1440 - css.width,
      height: bounds.bounds.height! + 1000 - css.height,
    },
  });
  await expect.poll(() => page.evaluate(() => innerHeight)).toBe(1000);
  try {
    const f = JSON.parse(
      await readFile(join(root, 'artifacts/surrogate-native-input.json'), 'utf8'),
    );
    const network: unknown[] = [];
    page.on('requestfinished', async (request) => {
      if (request.url().includes('/api/1/'))
        network.push({
          method: request.method(),
          path: new URL(request.url()).pathname,
          timing: request.timing(),
        });
    });
    await page.goto('/ui/');
    await page.getByLabel('Username', { exact: true }).fill('owner');
    await page.getByLabel('Password', { exact: true }).fill(f.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
    await page.goto('/ui/#' + new URLSearchParams({ v: '1', study: f.study_id, view: 'overview' }));
    const explorer = page.getByRole('region', { name: 'Explore the answer', exact: true });
    await expect(explorer.getByRole('slider')).toHaveCount(2, { timeout: 60000 });
    await expect(explorer.getByText(/^(Estimated|Calculated)$/, { exact: true })).toHaveCount(1);
    const selectedPath = join(root, 'artifacts/surrogate-selected-ui-point.json');
    let selected: { run_id: string } | null = null;
    try {
      selected = JSON.parse(await readFile(selectedPath, 'utf8'));
    } catch (error: any) {
      if (error.code !== 'ENOENT') throw error;
    }
    let inFlight = false;
    let submittedHere = false;
    if (!selected) {
      await explorer.getByRole('slider').evaluateAll((sliders) => {
        const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
        for (const slider of sliders) {
          set.call(slider, '1.05');
          slider.dispatchEvent(new Event('input', { bubbles: true }));
          slider.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
      await expect(explorer.getByText('Estimated', { exact: true })).toHaveCount(1);
      await explorer.getByRole('button', { name: 'Sample settings', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: 'Sample settings', exact: true });
      const submission = page.waitForResponse(
        (r) => r.url().endsWith('/runs') && r.request().method() === 'POST',
      );
      await dialog.getByRole('button', { name: 'Calculate selected point', exact: true }).click();
      selected = { run_id: (await (await submission).json()).data.run_id };
      await writeFile(selectedPath, JSON.stringify(selected));
      await page.keyboard.press('Escape');
      inFlight = true;
      submittedHere = true;
    }
    const originalBefore = (
      await (
        await page.request.get('/api/1/studies/' + f.study_id + '/runs/' + selected!.run_id)
      ).json()
    ).data.state;
    inFlight = originalBefore !== 'recorded';
    const refinementState = async () =>
      refining
        ? (
            await (
              await page.request.get(
                '/api/1/studies/' + f.study_id + '/exploration-surrogates/' + refining,
              )
            ).json()
          ).data.state
        : null;
    const refinementBefore = await refinementState();
    if (refining) expect(['pending', 'building']).toContain(refinementBefore);
    const writes: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('/api/1/') && r.method() !== 'GET') writes.push(r.url());
    });
    // Observe actual fetch responses and committed DOM; no intercepts or fake replies.
    await page.evaluate(() => {
      const w = window as any;
      w.explorationTiming = { last: null };
      const original = window.fetch;
      window.fetch = async (...args) => {
        const started = performance.now();
        const response = await original(...args);
        const headersAt = performance.now();
        if (String(args[0]).endsWith('/predictions') && response.ok) {
          const body = await response.clone().json();
          w.explorationTiming.last = {
            request: JSON.parse(String(args[1]?.body)),
            result: body.data,
            at: performance.now(),
            started,
            headersAt,
            server: response.headers.get('Server-Timing'),
            resource: performance.getEntriesByName(response.url).at(-1)?.toJSON(),
          };
        }
        return response;
      };
    });
    await explorer.locator('.hf-node').first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(root, 'evidence/explorer-layout-initial.png') });
    const latencies: number[] = [],
      thumbs: number[] = [];
    const requests: unknown[] = [];
    const stages: unknown[] = [];
    for (let i = 0; i < 50; i++) {
      const result = await page.evaluate(
        async ({ x, y, reverse }) => {
          const region = document.querySelector('[aria-label="Explore the answer"]')!;
          const inputs = [...region.querySelectorAll<HTMLInputElement>('input[type="range"]')];
          const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
          const w = window as any;
          w.explorationTiming.last = null;
          const start = performance.now();
          const values = [x, y];
          const order = reverse ? [1, 0] : [0, 1];
          for (const index of order) {
            set.call(inputs[index], String(values[index]));
            inputs[index].dispatchEvent(new Event('input', { bubbles: true }));
            inputs[index].dispatchEvent(new Event('change', { bubbles: true }));
          }
          await new Promise(requestAnimationFrame);
          const thumb = performance.now() - start;
          const immediate = inputs.map((n) => Number(n.value));
          if (immediate[0] !== x || immediate[1] !== y) throw Error('Thumb update was deferred');
          return await new Promise<any>((resolve, reject) => {
            const timeout = setTimeout(() => {
              observer.disconnect();
              reject(Error('No rendered prediction'));
            }, 3000);
            const check = () => {
              const latest = w.explorationTiming.last;
              const value = latest?.result.outputs[0].values[0];
              if (!value || value.kind !== 'estimated') return;
              const element = region.querySelector('.hf-quantity-result');
              if (element?.getAttribute('title') !== String(value.value)) return;
              requestAnimationFrame(() => {
                const visible = [
                  inputs[0],
                  inputs[1],
                  element,
                  region.querySelector('.hf-response-curve'),
                ].every((node) => {
                  if (!node) return false;
                  const box = node.getBoundingClientRect();
                  if (
                    box.top < 0 ||
                    box.bottom > innerHeight ||
                    box.left < 0 ||
                    box.right > innerWidth
                  )
                    return false;
                  for (let parent = node.parentElement; parent; parent = parent.parentElement) {
                    if (['auto', 'hidden', 'scroll'].includes(getComputedStyle(parent).overflowY)) {
                      const clip = parent.getBoundingClientRect();
                      if (box.top < clip.top || box.bottom > clip.bottom) return false;
                    }
                  }
                  return true;
                });
                if (!visible) {
                  clearTimeout(timeout);
                  observer.disconnect();
                  reject(
                    Error(
                      'Active controls and returned curve are clipped: ' +
                        JSON.stringify(
                          [
                            inputs[0],
                            inputs[1],
                            element,
                            region.querySelector('.hf-response-curve'),
                          ].map((n) => n?.getBoundingClientRect().toJSON()),
                        ),
                    ),
                  );
                  return;
                }
                clearTimeout(timeout);
                observer.disconnect();
                resolve({
                  elapsed: performance.now() - start,
                  thumb,
                  request: latest.request,
                  value: value.value,
                  curves: region.querySelectorAll('.hf-response-curve__estimate').length,
                  dispatch_ms: latest.started - start,
                  fetch_ms: latest.at - latest.started,
                  render_ms: performance.now() - latest.at,
                  headers_ms: latest.headersAt - latest.started,
                  body_ms: latest.at - latest.headersAt,
                  server: latest.server,
                  resource: latest.resource,
                });
              });
            };
            const observer = new MutationObserver(check);
            observer.observe(region, {
              subtree: true,
              childList: true,
              attributes: true,
              characterData: true,
            });
            check();
          });
        },
        { x: (90 + (i % 20)) / 100, y: (1100 + 2 * i) / 1000, reverse: i % 2 === 0 },
      );
      latencies.push(result.elapsed);
      thumbs.push(result.thumb);
      requests.push(result.request);
      stages.push({
        dispatch_ms: result.dispatch_ms,
        fetch_ms: result.fetch_ms,
        render_ms: result.render_ms,
        headers_ms: result.headers_ms,
        body_ms: result.body_ms,
        server: result.server,
        resource: result.resource,
      });
      if (i % 10 === 0)
        await writeFile(
          join(root, 'evidence/surrogate-browser-progress.json'),
          JSON.stringify({ completed: i + 1, stages, latencies }),
        );
      expect(result.curves).toBeGreaterThan(0);
      const vector = (result.request as any).inputs;
      expect(vector.map((v: any) => v.value)).toEqual([
        (90 + (i % 20)) / 100,
        (1100 + 2 * i) / 1000,
      ]);
      expect(Math.abs(result.value - vector[0].value * vector[1].value)).toBeLessThan(1e-6);
    }
    const p95 = [...latencies].sort((a, b) => a - b)[47];
    const originalAfter = (
      await (
        await page.request.get('/api/1/studies/' + f.study_id + '/runs/' + selected!.run_id)
      ).json()
    ).data.state;
    const proof = {
      latencies_ms: latencies,
      p95_ms: p95,
      thumb_ms: thumbs,
      requests,
      stages,
      network,
      human_acceptance: false,
      writes,
      original_in_flight_at_start: inFlight,
      original_state_before_interactions: originalBefore,
      selected_run_id: selected!.run_id,
      refinement_before: refinementBefore,
      refinement_after: await refinementState(),
      original_state_after_interactions: originalAfter,
    };
    await writeFile(
      join(root, 'evidence/surrogate-browser' + (refining ? '-refinement' : '') + '-latency.json'),
      JSON.stringify(proof, null, 2),
    );
    expect(new Set(requests.map((r: any) => JSON.stringify(r.inputs))).size).toBe(50);
    expect(new Set(requests.map((r: any) => r.axis.port_id)).size).toBe(2);
    expect(writes.every((url) => url.endsWith('/predictions'))).toBe(true);
    // This answer cites no original runs: overview must not hydrate the entire
    // sampling campaign while the engineer explores its prepared response.
    expect(network.filter((r: any) => /\/runs\/[^/]+$/.test(r.path))).toHaveLength(0);
    expect(p95).toBeLessThanOrEqual(250);
    await expect(explorer.locator('.hf-response-curve__cursor')).toHaveCount(1);
    expect(await explorer.locator('.hf-response-curve text').count()).toBeGreaterThanOrEqual(4);
    if (inFlight) expect(['accepted_run', 'prepared', 'dispatching']).toContain(originalAfter);
    expect(Math.max(...thumbs)).toBeLessThanOrEqual(100);
    if (submittedHere) {
      await explorer.getByRole('button', { name: 'Sample settings', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: 'Sample settings', exact: true });
      // Read the same accepted original; the UI enriches the retained sampling basis.
      await expect
        .poll(
          async () => {
            const adoption = page
              .waitForResponse((r) => r.url().endsWith('/points'), { timeout: 5000 })
              .catch(() => null);
            await dialog
              .getByRole('button', { name: 'Read selected calculation', exact: true })
              .click();
            const response = await adoption;
            return response?.status();
          },
          { timeout: 120000, intervals: [1000] },
        )
        .toBe(201);
      await page.keyboard.press('Escape');
    }
    const views: unknown[] = [];
    const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker'));
    for (const zoom of [1, 2]) {
      const factor = await worker.evaluate(
        async ({ origin, zoom }) => {
          const chrome = (globalThis as any).chrome;
          const tab = (await chrome.tabs.query({})).find((t: any) => t.url?.startsWith(origin));
          if (!tab) throw Error('Scoped tab missing');
          await chrome.tabs.setZoomSettings(tab.id, { mode: 'automatic', scope: 'per-tab' });
          await chrome.tabs.setZoom(tab.id, zoom);
          return chrome.tabs.getZoom(tab.id);
        },
        { origin: baseURL!, zoom },
      );
      expect(factor).toBe(zoom);
      await expect.poll(() => page.evaluate(() => innerWidth)).toBe(1440 / zoom);
      for (const theme of ['light', 'dark'] as const) {
        await page.emulateMedia({ colorScheme: theme });
        const slider = explorer.getByRole('slider').first();
        await slider.press('Tab');
        await page.keyboard.press('Shift+Tab');
        await page.keyboard.press('ArrowRight');
        await expect(slider).toBeFocused();
        await expect(explorer.locator('.hf-quantity-result')).toHaveAttribute('title', /[0-9]/);
        const geometry = await page.evaluate(() => ({
          width: innerWidth,
          height: innerHeight,
          dpr: devicePixelRatio,
          pageWidth: document.documentElement.scrollWidth,
        }));
        expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.width);
        expect(page.viewportSize()).toBeNull();
        const control = await slider.boundingBox(),
          result = await explorer.locator('.hf-response-curve').boundingBox();
        expect(control!.y).toBeGreaterThanOrEqual(0);
        expect(control!.y + control!.height).toBeLessThanOrEqual(geometry.height);
        expect(result!.y).toBeGreaterThanOrEqual(0);
        expect(result!.y + result!.height).toBeLessThanOrEqual(geometry.height);
        views.push({ zoom, theme, geometry, control, result });
        const screenshot = await cdp.send('Page.captureScreenshot', {
          format: 'png',
          fromSurface: true,
          captureBeyondViewport: false,
        });
        await writeFile(
          join(root, 'evidence/explorer-visible-' + theme + '-' + zoom + '.png'),
          Buffer.from(screenshot.data, 'base64'),
        );
      }
    }
    await writeFile(
      join(root, 'evidence/explorer-visible-proof.json'),
      JSON.stringify({ views, human_acceptance: false }, null, 2),
    );
    const pinned = f.samples.combinations[0];
    const answer = await page.request.get(
      '/api/1/studies/' + f.study_id + '/answers/' + pinned.answer_version_id,
    );
    expect(answer.ok()).toBe(true);
    const approach = (await answer.json()).data.approach_version_id;
    await explorer.getByRole('button', { name: 'Open model', exact: true }).click();
    await expect
      .poll(() => new URLSearchParams(new URL(page.url()).hash.slice(1)).get('revision'))
      .toBe(pinned.model_revision_id);
    const route = new URLSearchParams(new URL(page.url()).hash.slice(1));
    expect(route.get('model')).toBe(pinned.model_id);
    expect(route.get('approach')).toBe(approach);
    await page.getByRole('button', { name: 'View modeling approach', exact: true }).click();
    await expect
      .poll(() => new URLSearchParams(new URL(page.url()).hash.slice(1)).get('approach'))
      .toBe(approach);
  } finally {
    await context.close();
  }
});
