import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test, expect } from 'playwright/test';

test('every declared input remains reachable beside a result on the canonical graph', async ({
  page,
}) => {
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const fixture = JSON.parse(
    await readFile(join(root, 'artifacts/fuel-surrogate-input.json'), 'utf8'),
  );
  const setup = JSON.parse(await readFile(join(root, 'artifacts/combined-setup.json'), 'utf8'));
  const combo = fixture.design.request.combinations[0];
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(setup.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New study', exact: true })).toBeVisible();
  await page.goto(
    '/ui/#' + new URLSearchParams({ v: '1', study: fixture.study_id, view: 'overview' }),
  );
  const explorer = page.getByRole('region', { name: 'Explore the answer', exact: true });
  await expect(explorer.getByRole('slider')).toHaveCount(combo.dimensions.length);
  await expect(explorer.locator('.hf-quantity-result')).toHaveCount(
    fixture.samples.combinations[0].tolerances.length,
  );
  await expect(
    page.getByRole('region', { name: 'Reasoning and methods', exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole('group', { name: 'Supporting results', exact: true })).toHaveCount(0);
  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/1/') && request.method() !== 'GET') writes.push(request.url());
  });
  const observations: unknown[] = [];
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (let index = 0; index < combo.dimensions.length; index++) {
      const dimension = combo.dimensions[index];
      const node = explorer
        .locator('.hf-node')
        .filter({ has: page.locator('[data-instance="' + dimension.target.instance_id + '"]') });
      const port = node
        .locator('.hf-node__exploration-port')
        .filter({ has: page.locator('[data-port="' + dimension.target.port_id + '"]') });
      const slider = port.getByRole('slider');
      await slider.scrollIntoViewIfNeeded();
      const response = page.waitForResponse(
        (r) =>
          r.url().endsWith('/predictions') &&
          r.request().postDataJSON().axis.port_id === dimension.target.port_id,
      );
      await slider.focus();
      await page.keyboard.press('ArrowRight');
      const reply = await response;
      expect(reply.ok()).toBe(true);
      const request = reply.request().postDataJSON();
      expect(request.inputs).toHaveLength(combo.dimensions.length);
      await expect(slider).toBeFocused();
      const output = node.locator('.hf-quantity-result').first();
      await expect(output).toBeVisible();
      const controlBox = await slider.boundingBox(),
        outputBox = await output.boundingBox();
      const height = await page.evaluate(() => innerHeight);
      expect(controlBox!.y).toBeGreaterThanOrEqual(0);
      expect(controlBox!.y + controlBox!.height).toBeLessThanOrEqual(height);
      // Independent input scrolling cannot displace the selected output column.
      expect(outputBox!.y).toBeGreaterThanOrEqual(0);
      expect(outputBox!.y + outputBox!.height).toBeLessThanOrEqual(height);
      observations.push({
        theme,
        target: dimension.target,
        input: controlBox,
        output: outputBox,
        request,
      });
    }
    await page.screenshot({ path: join(root, 'evidence/many-inputs-' + theme + '.png') });
  }
  expect(writes.every((url) => url.endsWith('/predictions'))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await writeFile(
    join(root, 'evidence/many-inputs-browser-proof.json'),
    JSON.stringify({ observations, writes, human_acceptance: false }, null, 2),
  );
});
