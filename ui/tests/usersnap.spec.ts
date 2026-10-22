import { test, expect, type Page } from 'playwright/test';

const widget = '9c4a930c-b62f-4b89-bca3-260ec022694a';
const loader = `https://widget.usersnap.com/global/load/${widget}*`;

test.beforeEach(async ({ page }) => {
  // No fixture can submit data or fetch follow-on provider code.
  await page.route('https://**/*', (route) => route.abort());
});

async function signIn(page: Page) {
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
}

test('unconfigured workspace makes no hosted feedback request', async ({ page }) => {
  const outbound: string[] = [];
  await page.route('https://**/*', (route) => {
    outbound.push(route.request().url());
    return route.abort();
  });
  const response = await page.goto('/disabled/');
  expect(response!.headers()['content-security-policy']).not.toContain('usersnap');
  await signIn(page);
  expect(outbound).toEqual([]);
  await expect(page.locator('meta[name="hyprn-usersnap"]')).toHaveCount(0);
});

test('nonce reaches one loader and inherited frames while unrelated code is refused', async ({
  page,
}) => {
  const loads: string[] = [];
  const faults: string[] = [];
  page.on('pageerror', (error) => faults.push(error.message));
  await page.route(loader, (route) => {
    loads.push(route.request().url());
    return route.fulfill({
      contentType: 'text/javascript',
      body: `
      const script = document.currentScript;
      window.vendorObservation = {nonce: script.nonce, calls: 0};
      const api = {init(options) {
        window.vendorObservation.options = options;
        window.vendorObservation.calls++;
        const frame = document.createElement('iframe');
        frame.title = 'Feedback fixture';
        frame.onload = () => {
          const style = frame.contentDocument.createElement('style');
          style.nonce = script.nonce;
          style.textContent = 'body { --feedback-nonce: accepted; }';
          frame.contentDocument.head.appendChild(style);
          window.vendorObservation.frameStyle =
            frame.contentWindow.getComputedStyle(frame.contentDocument.body)
              .getPropertyValue('--feedback-nonce').trim();
        };
        document.body.appendChild(frame);
        return Promise.resolve();
      }};
      window.onUsersnapLoad(api);
      window.onUsersnapLoad(api);
    `,
    });
  });
  await page.addInitScript(() => {
    (window as any).violations = [];
    document.addEventListener('securitypolicyviolation', (event) => {
      (window as any).violations.push({
        directive: event.effectiveDirective,
        blocked: event.blockedURI,
      });
    });
  });
  const response = await page.goto('/ui/');
  await expect
    .poll(() => page.evaluate(() => (window as any).vendorObservation?.frameStyle))
    .toBe('accepted');
  const configuration = await page
    .locator('meta[name="hyprn-usersnap"]')
    .getAttribute('data-nonce');
  expect(response!.headers()['content-security-policy']).toContain(`'nonce-${configuration}'`);
  expect(loads).toHaveLength(1);
  expect(new URL(loads[0]).searchParams.get('n')).toBe(configuration);
  expect(new URL(loads[0]).searchParams.get('onload')).toBe('onUsersnapLoad');
  expect(await page.evaluate(() => (window as any).vendorObservation)).toEqual({
    nonce: configuration,
    calls: 1,
    frameStyle: 'accepted',
    options: { useSystemFonts: true, collectGeoLocation: 'none', useLocalStorage: false },
  });
  expect(await page.evaluate(() => (window as any).violations)).toEqual([]);
  let unrelatedReached = false;
  await page.route('https://unrelated.invalid/**', (route) => {
    unrelatedReached = true;
    return route.abort();
  });
  await page.evaluate(() => {
    const inline = document.createElement('script');
    inline.textContent = 'window.untrustedExecuted = true';
    document.head.appendChild(inline);
    const remote = document.createElement('script');
    remote.src = 'https://unrelated.invalid/script.js';
    document.head.appendChild(remote);
  });
  await expect.poll(() => page.evaluate(() => (window as any).violations.length)).toBe(2);
  expect(await page.evaluate(() => (window as any).untrustedExecuted)).toBeUndefined();
  expect(unrelatedReached).toBe(false);
  await signIn(page);
  expect(loads).toHaveLength(1);
  await expect(page.locator(`script[src^="https://widget.usersnap.com/global/load/"]`)).toHaveCount(
    1,
  );
  expect(faults).toEqual([]);
});

for (const failure of ['network', 'rejection', 'throw'] as const) {
  test(`feedback ${failure} leaves the real workspace usable`, async ({ page }) => {
    const faults: string[] = [];
    page.on('pageerror', (error) => faults.push(error.message));
    await page.route(loader, (route) =>
      failure === 'network'
        ? route.abort()
        : route.fulfill({
            contentType: 'text/javascript',
            body: `window.onUsersnapLoad({init() { ${
              failure === 'rejection'
                ? 'return Promise.reject(new Error("Unavailable"));'
                : 'throw new Error("Unavailable");'
            } }});`,
          }),
    );
    await page.goto('/ui/');
    await signIn(page);
    expect(faults).toEqual([]);
  });
}
