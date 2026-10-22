import { test, expect, type Page } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { formatNumber } from '../src/design/numbers';
import {
  startFixture,
  stopFixture,
  guardOrigin,
  harness,
  login,
  sid,
  mid,
  referenceModel,
  runFixture,
  details,
  version,
} from './foundry-fixtures';
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture);
test.beforeEach(async ({ page }) => {
  await guardOrigin(page);
});
test.afterAll(stopFixture);
test('Individual connections lead to full-width component readers and quantity editing', async ({
  page,
}) => {
  await harness(page);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  const graph = page.getByRole('region', { name: 'Directed component diagram' });
  const connection = graph.locator('[data-connection]').first();
  await expect(connection).toBeVisible();
  await connection.focus();
  await page.keyboard.press('Enter');
  await expect(connection).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('tab', { name: 'Model explanation', exact: true }).click();
  const modelReader = page.getByRole('region', { name: 'Model explanation reader', exact: true });
  await expect(modelReader.getByRole('region', { name: 'Selection inspector' })).toHaveCount(0);
  await expect(modelReader.getByRole('heading', { name: 'Model', exact: true })).toHaveCount(0);
  await expect(modelReader).toContainText('3 components');
  await page.getByRole('tab', { name: 'Diagram', exact: true }).click();
  await graph.locator('[data-instance="a"]').click();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  await expect(page.getByLabel('Python source', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  const row = page.locator('.quantities-table tbody tr').first();
  const portId = (await row.getAttribute('data-variable'))!.split('/')[1];
  await row.getByRole('button', { name: 'Edit quantity', exact: true }).click();
  await expect(
    page
      .getByRole('dialog', { name: 'Edit quantity' })
      .locator(`[data-port-definition="${portId}"]`),
  ).toBeFocused();
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Edit quantity', exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    const region = page.getByRole('region', { name: 'Quantities table', exact: true });
    const action = region.getByRole('button', { name: 'Edit quantity' }).last();
    await action.focus();
    await expect(action).toBeFocused();
    const surface = await region.evaluate((el) => {
      const row = el.querySelector('tbody tr')!;
      const cells = [...row.children].map((cell) => getComputedStyle(cell).backgroundColor);
      const wrapper = el.parentElement!;
      return {
        cells,
        overflow: getComputedStyle(wrapper).overflowX,
        pageFits: document.documentElement.scrollWidth <= innerWidth + 1,
      };
    });
    expect(new Set(surface.cells).size).toBe(1);
    expect(surface.overflow).toBe('visible');
    expect(surface.pageFits).toBe(true);
    await action.click();
    await expect(page.getByRole('dialog', { name: 'Edit quantity' })).toBeVisible();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Edit quantity', exact: true })).toHaveCount(0);
  }
});
test('Reversed endpoint rows keep separate outer lanes in a five-link gutter', async ({ page }) => {
  const state = await harness(page);
  const definition = state.model.definitions[0];
  state.model.instances = state.model.instances.slice(0, 2);
  state.model.definitions = state.model.instances.map((instance, n) => {
    instance.definition_version_id = `reversed-${n}`;
    return {
      ...definition,
      definition_version_id: instance.definition_version_id,
      ports: Array.from({ length: 5 }, (_, i) => ({
        ...definition.ports[0],
        port_id: `port-${i}`,
        code_symbol: `port_${i}`,
        direction: n === 0 ? ('output' as const) : ('input' as const),
      })),
    };
  });
  state.model.connections = [4, 1, 2, 3, 0].map((target, i) => ({
    connection_id: `reversed-${i}`,
    source_ref: { instance_id: 'a', port_id: `port-${i}` },
    target_ref: { instance_id: 'b', port_id: `port-${target}` },
  }));
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  const graph = page.getByRole('region', { name: 'Directed component diagram' });
  await expect(graph.locator('[data-connection]')).toHaveCount(5);
  const card = (await graph.locator('.hf-node').first().boundingBox())!;
  const outer = [];
  for (const index of [0, 4]) {
    const route = graph.locator(`[data-connection="reversed-${index}"] path:not(.exchange-hit)`);
    const box = (await route.boundingBox())!;
    expect(box.y).toBeLessThan(card.y);
    outer.push(box.y);
  }
  expect(Math.abs(outer[0] - outer[1])).toBeGreaterThan(1);
  const straight = graph.locator('[data-connection="reversed-2"] path:not(.exchange-hit)');
  expect(
    await straight.evaluate((element) => (element as SVGPathElement).getBBox().height),
  ).toBeLessThan(1);
});
test('Source stays mounted with caret and local scroll across component tabs', async ({ page }) => {
  await harness(page);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.locator('.connected-graph [data-instance="a"]').click();
  const inspector = page.getByRole('region', { name: 'Selection inspector' });
  await expect(inspector.getByRole('heading', { name: 'Component', exact: true })).toHaveCount(0);
  const title = (await inspector.getByRole('heading', { level: 3 }).first().boundingBox())!;
  for (const name of ['Edit component']) {
    const action = (await inspector.getByRole('button', { name, exact: true }).boundingBox())!;
    expect(Math.abs(title.y + title.height / 2 - action.y - action.height / 2)).toBeLessThan(2);
  }
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  const source = page.getByLabel('Python source', { exact: true });
  const text =
    '# <script>globalThis.componentSourceRan = true</script>\n' +
    '# long_identifier '.repeat(80) +
    '\n' +
    '# retained line\n'.repeat(60);
  await source.fill(text);
  await source.evaluate((el: HTMLTextAreaElement) => {
    el.setSelectionRange(2, 17);
    el.scrollLeft = 120;
    el.scrollTop = 96;
    el.dispatchEvent(new Event('scroll'));
  });
  await page.getByRole('tab', { name: 'Component', exact: true }).click();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  await expect(source).toHaveValue(text);
  expect(
    await source.evaluate((el: HTMLTextAreaElement) => [
      el.selectionStart,
      el.selectionEnd,
      el.scrollLeft,
      el.scrollTop,
    ]),
  ).toEqual([2, 17, 120, 96]);
  expect(await page.evaluate(() => Reflect.get(window, 'componentSourceRan'))).toBeUndefined();
  await expect(page.getByRole('button', { name: /Expand source|Collapse source/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Edit component', exact: true })).toBeHidden();
  await expect(page.getByRole('button', { name: 'Edit quantities', exact: true })).toBeHidden();
  await source.focus();
  await source.press('Tab');
  await expect(source).not.toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  await source.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  );
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  const guard = page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
  await guard.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(source).toHaveValue(text);
});
test('Quantity row requests respect pending removal and cancelled owner guards', async ({
  page,
}) => {
  const state = await harness(page);
  referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.locator('.connected-graph [data-instance="a"]').click();
  await page.getByRole('button', { name: 'Component actions', exact: true }).click();
  await page.getByRole('button', { name: 'Manage quantities', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Manage quantities', exact: true });
  await dialog.getByRole('button', { name: 'Remove quantity 1', exact: true }).click();
  await dialog.getByRole('button', { name: 'Done', exact: true }).click();
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await page
    .locator('[data-variable="a/x"]')
    .getByRole('button', { name: 'Edit quantity', exact: true })
    .click();
  const removed = page.getByRole('dialog', { name: 'Edit quantity', exact: true });
  await expect(removed).toContainText('pending removal');
  await expect(removed.locator('[data-port-definition]')).toHaveCount(0);
  await removed.getByRole('button', { name: 'Manage quantities', exact: true }).click();
  await expect(dialog.getByLabel('Quantity 1 symbol', { exact: true })).toHaveValue('z');
  await dialog.getByRole('button', { name: 'Done', exact: true }).click();
  await page.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await page
    .locator('[data-variable="b/u"]')
    .getByRole('button', { name: 'Edit quantity', exact: true })
    .click();
  const guard = page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
  await expect(guard).toBeVisible();
  await guard.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(removed).not.toBeVisible();
  await page.locator('.connected-graph [data-instance="b"]').click();
  await guard.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(removed).not.toBeVisible();
  expect(state.writes).toEqual([]);
});
/** Reading tabs retain the component's draft source. */
async function openSource(page: Page) {
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
}
async function capture(page: Page, name: string) {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.screenshot({
      path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/nx7-${name}-${colorScheme}.png`,
      animations: 'disabled',
    });
  }
}
test('display precision never turns small nonzero values into zero', () => {
  for (const [value, expected] of [
    [8381.7034110152, '8381.703'],
    [3127.9887138077, '3127.989'],
    [1e-10, '1e-10'],
    [-0.000004321987, '-4.322e-6'],
    [0, '0'],
    [1, '1'],
    [-1.23456, '-1.235'],
    [1e20, '1e+20'],
  ] as const)
    expect(formatNumber(value)).toBe(expected);
  expect(formatNumber(NaN)).toBe('not computed');
});
test('Fit model contains complete readable nodes and wheel input scrolls the page', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 878 });
  const state = await harness(page);
  state.model.name = 'Hydrogen storage mass and tank volume feasibility';
  const definition = state.model.definitions[0];
  state.model.definitions = [14, 9, 7].map((count, n) => ({
    ...definition,
    definition_version_id: `many-${n}`,
    ports: Array.from({ length: count }, (_, i) => ({
      ...definition.ports[0],
      port_id: `quantity-${i}`,
      code_symbol: i === 0 ? 'propulsion_adjustment' : `quantity_${i}`,
      direction: i >= count - 2 ? ('output' as const) : ('input' as const),
    })),
  }));
  state.model.instances.forEach((instance, n) => {
    instance.definition_version_id = `many-${n}`;
    instance.name = [
      'Cruise propulsion adjustment',
      'Aircraft mission fuel requirement',
      'Tank and storage feasibility',
    ][n];
  });
  state.model.connections = [0, 1].map((n) => ({
    connection_id: `flow-${n}`,
    source_ref: {
      instance_id: state.model.instances[n].instance_id,
      port_id: `quantity-${[13, 8][n]}`,
    },
    target_ref: { instance_id: state.model.instances[n + 1].instance_id, port_id: 'quantity-0' },
  }));
  state.model.connections.push({
    connection_id: 'bypass',
    source_ref: { instance_id: 'a', port_id: 'quantity-13' },
    target_ref: { instance_id: 'c', port_id: 'quantity-1' },
  });
  state.model.connections.push(
    {
      connection_id: 'parallel',
      source_ref: { instance_id: 'a', port_id: 'quantity-12' },
      target_ref: { instance_id: 'b', port_id: 'quantity-1' },
    },
    {
      connection_id: 'feedback',
      source_ref: { instance_id: 'c', port_id: 'quantity-6' },
      target_ref: { instance_id: 'a', port_id: 'quantity-0' },
    },
  );
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  const viewport = page.getByRole('region', { name: 'Directed component diagram' });
  const fit = page.getByRole('button', { name: 'Fit model', exact: true });
  await expect
    .poll(async () => {
      const bounds = await viewport.locator('.hf-node').evaluateAll((nodes) =>
        nodes.map((node) => {
          const box = node.getBoundingClientRect();
          return { top: box.top, bottom: box.bottom };
        }),
      );
      return bounds.length === 3 && bounds.every((box) => box.top >= 0 && box.bottom <= 878);
    })
    .toBe(true);
  const footer = (await page.locator('.canvas-footer').boundingBox())!;
  expect(footer.y + footer.height).toBeLessThanOrEqual(878);
  await fit.click();
  async function contained() {
    const frame = (await viewport.boundingBox())!;
    for (const node of await viewport
      .locator('.hf-node, .graph-exchange path:not(.exchange-hit), .graph-exchange text')
      .all()) {
      const box = (await node.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(frame.x);
      expect(box.y).toBeGreaterThanOrEqual(frame.y);
      expect(box.x + box.width).toBeLessThanOrEqual(frame.x + frame.width);
      expect(box.y + box.height).toBeLessThanOrEqual(frame.y + frame.height);
    }
  }
  await contained();
  await expect(viewport.locator('[data-connection]')).toHaveCount(5);
  for (const link of state.model.connections) {
    const route = viewport.locator(`[data-connection="${link.connection_id}"]`);
    const geometry = await route.locator('path:not(.exchange-hit)').evaluate((element, link) => {
      const path = element as SVGPathElement,
        matrix = path.getScreenCTM()!;
      const endpoint = (ref: { instance_id: string; port_id: string }) => {
        const card = document
          .querySelector(`.connected-graph [data-instance="${ref.instance_id}"]`)!
          .closest('.hf-node')!;
        const bounds = card.getBoundingClientRect();
        const port = card.querySelector(`[data-port="${ref.port_id}"]`)!.getBoundingClientRect();
        return { left: bounds.left, right: bounds.right, y: port.y + port.height / 2 };
      };
      const first = path.getPointAtLength(0).matrixTransform(matrix),
        last = path.getPointAtLength(path.getTotalLength()).matrixTransform(matrix);
      const cards = [...document.querySelectorAll('.connected-graph .hf-node')].map((card) =>
        card.getBoundingClientRect(),
      );
      let clear = true;
      for (let i = 1; i < 500; i++) {
        const point = path
          .getPointAtLength((path.getTotalLength() * i) / 500)
          .matrixTransform(matrix);
        if (
          cards.some(
            (card) =>
              point.x > card.left + 1 &&
              point.x < card.right - 1 &&
              point.y > card.top + 1 &&
              point.y < card.bottom - 1,
          )
        )
          clear = false;
      }
      return {
        first: { x: first.x, y: first.y },
        last: { x: last.x, y: last.y },
        top: path.getBoundingClientRect().top,
        source: endpoint(link.source_ref),
        target: endpoint(link.target_ref),
        clear,
      };
    }, link);
    expect(geometry.first.x).toBeCloseTo(geometry.source.right, 0);
    expect(geometry.first.y).toBeCloseTo(geometry.source.y, 0);
    expect(geometry.last.x).toBeCloseTo(geometry.target.left, 0);
    expect(geometry.last.y).toBeCloseTo(geometry.target.y, 0);
    expect(geometry.clear).toBe(true);
    if (link.connection_id === 'flow-0' || link.connection_id === 'parallel') {
      expect(geometry.top).toBeGreaterThanOrEqual(Math.min(geometry.first.y, geometry.last.y) - 1);
    }
    const before = await route.locator('path:not(.exchange-hit)').getAttribute('d');
    await route.focus();
    await page.keyboard.press('Enter');
    await expect(route).toHaveAttribute('aria-pressed', 'true');
    await expect(viewport.locator('[data-highlighted]')).toHaveCount(2);
    expect(await route.locator('path:not(.exchange-hit)').getAttribute('d')).toBe(before);
  }
  while (await page.getByRole('button', { name: 'Zoom out', exact: true }).isEnabled())
    await page.getByRole('button', { name: 'Zoom out', exact: true }).click();
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect(page.getByLabel('Graph zoom', { exact: true })).toHaveText('50%');
  for (const link of state.model.connections) {
    const route = viewport.locator(`[data-connection="${link.connection_id}"]`);
    const point = await route.locator('path:not(.exchange-hit)').evaluate((element) => {
      const path = element as SVGPathElement,
        point = path
          .getPointAtLength(path.getTotalLength() / 2)
          .matrixTransform(path.getScreenCTM()!);
      return { x: point.x, y: point.y };
    });
    await page.mouse.move(point.x, point.y);
    await page.mouse.click(point.x, point.y);
    await expect(route).toHaveAttribute('aria-pressed', 'true');
  }
  await fit.click();
  expect(
    await viewport
      .locator('[data-connection="bypass"] path:not(.exchange-hit)')
      .evaluate((path) => {
        const curve = path as SVGPathElement;
        const middle = document
          .querySelector('.connected-graph [data-instance="b"]')!
          .closest('.hf-node')!
          .getBoundingClientRect();
        const matrix = curve.getScreenCTM()!;
        for (let i = 0; i <= 100; i++) {
          const point = curve
            .getPointAtLength((curve.getTotalLength() * i) / 100)
            .matrixTransform(matrix);
          if (
            point.x > middle.left &&
            point.x < middle.right &&
            point.y > middle.top &&
            point.y < middle.bottom
          )
            return false;
        }
        return true;
      }),
  ).toBe(true);
  expect(
    await viewport
      .locator('.hf-node__name,.hf-node__port code')
      .evaluateAll((elements) =>
        elements.every(
          (e) =>
            e.scrollWidth <= e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis',
        ),
      ),
  ).toBe(true);
  expect(
    Number((await page.getByLabel('Graph zoom', { exact: true }).textContent())!.replace('%', '')),
  ).toBeGreaterThanOrEqual(70);
  await viewport.locator('[data-instance="a"]').click();
  await expect(page.locator('.canvas-footer')).toContainText('Cruise propulsion adjustment');
  await expect(page.locator('.quantities-table [aria-selected="true"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await viewport.focus();
  await page.keyboard.press('ArrowRight');
  await page.getByRole('button', { name: 'Focus selection', exact: true }).click();
  await expect(viewport.locator('[data-instance="a"]')).toHaveAttribute('aria-pressed', 'true');
  await fit.click();
  await contained();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await fit.click();
  await contained();
  expect(
    Number((await page.getByLabel('Graph zoom', { exact: true }).textContent())!.replace('%', '')),
  ).toBeGreaterThanOrEqual(60);
  await capture(page, 'model-fit');
  await fit.click();
  await contained();
  await viewport.hover();
  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, 500);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(before);
  expect(await viewport.evaluate((e) => e.scrollTop)).toBe(0);
  await expect(page.getByRole('button', { name: 'Jump to Quantities' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Read component' })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Quantities', exact: true })).toBeVisible();
  expect(state.writes).toEqual([]);
});
for (const count of [0, 1])
  test(`A model with ${count} components has finite graph geometry`, async ({ page }) => {
    const state = await harness(page);
    state.model.instances = state.model.instances.slice(0, count);
    state.model.connections = [];
    await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
    await page.getByRole('button', { name: 'Fit model', exact: true }).click();
    if (!count)
      await expect(
        page
          .getByRole('tabpanel', { name: 'Graph', exact: true })
          .getByText('No components in this model.', { exact: true }),
      ).toBeVisible();
    else {
      const node = page.locator('.connected-graph .hf-node');
      await expect(node).toBeVisible();
      const box = (await node.boundingBox())!;
      expect(Object.values(box).every(Number.isFinite)).toBe(true);
      expect(box.width).toBeGreaterThan(200);
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByRole('button', { name: 'Fit model', exact: true }).click();
      const addComponent = page.getByRole('button', { name: '＋ Component', exact: true });
      expect(
        await addComponent.evaluate((button) => {
          const range = document.createRange();
          range.selectNodeContents(button);
          return (
            range.getBoundingClientRect().height <=
            parseFloat(getComputedStyle(button).lineHeight) + 1
          );
        }),
      ).toBe(true);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
    }
    expect(state.writes).toEqual([]);
  });
test('Quantity columns omit repeated owners and empty definitions', async ({ page }) => {
  const state = await harness(page);
  referenceModel(state);
  state.model.definitions.forEach((definition) => {
    (definition as any).quantity_definitions = [];
  });
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  const table = page.getByRole('table', { name: 'Quantities', exact: true });
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await page.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await expect(table.getByRole('columnheader')).toHaveText([
    'Quantity',
    'Component',
    'Direction',
    'Unit',
    'Actions',
  ]);
  await expect(page.getByText('No quantity definitions provided.', { exact: true })).toHaveCount(0);
  await page.getByLabel('Component filter', { exact: true }).selectOption('a');
  await expect(table.getByRole('columnheader')).toHaveText([
    'Quantity',
    'Direction',
    'Unit',
    'Actions',
  ]);
  await expect(
    page.getByRole('button', { name: 'Inspect component Linear response', exact: true }),
  ).toHaveCount(0);
  await page.locator('.connected-graph [data-instance="a"]').click();
  await page.getByRole('tab', { name: 'Component', exact: true }).click();
  await expect(
    details(page).getByRole('heading', { name: 'Linear response', exact: true }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await page.getByRole('button', { name: 'Show all quantities', exact: true }).click();
  await expect(table.getByRole('columnheader', { name: 'Component', exact: true })).toBeVisible();
  await page.getByLabel('Find a quantity', { exact: true }).fill('does_not_exist');
  await expect(
    table.getByText('No quantities match these filters.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('No quantity definitions provided.', { exact: true })).toHaveCount(0);
  expect(state.writes).toEqual([]);
});
test('Model actions stay direct and quantity search reveals distant targets', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 934 });
  const state = await harness(page);
  referenceModel(state);
  for (let i = 0; i < 16; i++)
    state.model.instances.push({
      ...state.model.instances[0],
      instance_id: 'remote-' + i,
      name: 'Remote component ' + i,
    });
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await expect(page.getByText('View controls', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Help?', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'How to read the graph' })).toContainText(
    'arrow keys',
  );
  await page.keyboard.press('Escape');
  const search = page.getByRole('searchbox', { name: 'Search loaded model', exact: true });
  await search.fill('Remote component 15');
  await page
    .getByRole('region', { name: 'Loaded model search results' })
    .getByRole('button', { name: 'Remote component 15', exact: true })
    .click();
  const target = page.locator('.connected-graph [data-instance="remote-15"]');
  await expect(target).toBeFocused();
  const bounds = await target.boundingBox(),
    viewport = await page.locator('.graph-viewport').boundingBox();
  expect(bounds!.y).toBeGreaterThanOrEqual(viewport!.y);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport!.y + viewport!.height);
  await expect(
    details(page).getByRole('heading', { name: 'Remote component 15', exact: true }),
  ).toBeVisible();
  await openSource(page);
  await expect(details(page).getByText('Source tools', { exact: true })).toHaveCount(0);
  await expect(details(page).getByText(/^Declared symbols:/)).toHaveCount(0);
  await expect(
    details(page).getByRole('button', { name: 'Indent selection', exact: true }),
  ).toHaveCount(0);
  await expect(
    details(page).getByRole('button', { name: 'Code reference', exact: true }),
  ).toHaveCount(0);
  await expect(details(page).locator('.quantity-endpoints:visible')).toHaveCount(0);
  await capture(page, 'source');
  // Quantities are listed once, below the projections, scoped to the selected component; a quantity
  // revealed by the model search is scrolled into view inside the table's own region.
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  const quantities = page.getByRole('region', { name: 'Quantities table', exact: true });
  await expect(quantities.locator('[data-variable^="remote-15/"]').first()).toBeVisible();
  expect(
    await page
      .locator('[data-variable="remote-15/x"] td')
      .evaluateAll((es) => es.every((e) => getComputedStyle(e).verticalAlign === 'middle')),
  ).toBeTruthy();
  await search.fill('x');
  await page
    .getByRole('region', { name: 'Loaded model search results' })
    .getByRole('button', { name: 'Remote component 15 · x (x)', exact: true })
    .click();
  const row = quantities.locator('[data-variable="remote-15/x"]');
  await expect(row).toHaveAttribute('aria-selected', 'true');
  await expect
    .poll(async () => {
      const r = await row.boundingBox(),
        q = await quantities.boundingBox();
      return !!r && !!q && r.y >= q.y - 1 && r.y + r.height <= q.y + q.height + 1;
    })
    .toBe(true);
  await capture(page, 'variables');
  await page.getByRole('tab', { name: 'XDSM', exact: true }).click();
  await search.fill('Remote component 15');
  await page
    .getByRole('region', { name: 'Loaded model search results' })
    .getByRole('button', { name: 'Remote component 15', exact: true })
    .click();
  await expect(page.locator('.xdsm [data-instance="remote-15"]')).toBeFocused();
  await capture(page, 'xdsm');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});
test('Search preserves drafts and saved model identity', async ({ page }) => {
  const state = await harness(page);
  referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.locator('.connected-graph [data-instance="a"]').click();
  await openSource(page);
  await page.getByLabel('Python source', { exact: true }).fill("outputs['u'] = 7\n");
  await page.getByRole('searchbox', { name: 'Search loaded model' }).fill('x');
  await page
    .getByRole('region', { name: 'Loaded model search results' })
    .getByRole('button', { name: 'Linear response · x (x)', exact: true })
    .click();
  await expect(page.getByRole('dialog', { name: 'Unsaved changes' })).not.toBeVisible();
  await expect(page.locator('[data-variable="a/x"]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByLabel('Python source', { exact: true })).toHaveValue("outputs['u'] = 7\n");
  await page.getByRole('searchbox', { name: 'Search loaded model' }).fill('Squared response');
  await page
    .getByRole('region', { name: 'Loaded model search results' })
    .getByRole('button', { name: 'Squared response', exact: true })
    .click();
  await expect(page.getByRole('dialog', { name: 'Unsaved changes' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Python', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByRole('tab', { name: 'Component', exact: true }).click();
  await expect(
    details(page).getByRole('heading', { name: 'Linear response', exact: true }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  await expect(page.getByLabel('Python source', { exact: true })).toHaveValue("outputs['u'] = 7\n");
  await page.getByRole('combobox', { name: 'Model version', exact: true }).selectOption(version);
  await page
    .getByRole('dialog', { name: 'Unsaved changes' })
    .getByRole('button', { name: 'Discard changes', exact: true })
    .click();
  await expect(page.locator('.model-header .page-heading > div > h2')).toHaveText(state.model!.name);
  await expect(page.getByRole('button', { name: 'Save model version', exact: true })).toHaveCount(
    0,
  );
  expect(state.writes).toEqual([]);
});
test('Run outcomes retain exact values and diagnostics', async ({ page }) => {
  const state = await harness(page);
  const d = runFixture(state);
  d.history.results.execution = { state: 'finished', exit_code: 0, message: 'completed' };
  d.history.results.outputs[0].value = 8381.7034110152;
  d.history.configuration.criteria = [
    {
      criterion_id: 'criterion-1',
      target: { instance_id: 'a', port_id: 'u' },
      operator: 'lt',
      threshold: 1,
      units: '',
    },
  ];
  d.history.results.criteria = [
    { criterion_id: 'criterion-1', outcome: 'violated', reason: 'threshold_comparison' },
  ];
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const ledger = page.getByRole('list', { name: 'Run status', exact: true });
  await expect(ledger.locator('.hf-facet__k')).toHaveText(['Execution', 'Criteria']);
  await expect(
    ledger.getByRole('listitem').filter({ hasText: 'Criteria' }).locator('.hf-facet__v'),
  ).toHaveText('1 of 1 not met');
  const tops = await ledger
    .locator('.hf-facet__v')
    .evaluateAll((es) => es.map((e) => e.getBoundingClientRect().top));
  expect(Math.max(...tops) - Math.min(...tops)).toBeLessThan(2);
  await expect(page.getByText('Run status and diagnostics', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Output values', exact: true })).toContainText(
    '8381.703',
  );
  await expect(page.getByRole('region', { name: 'Output values', exact: true })).not.toContainText(
    '8381.703411',
  );
  await expect(
    page
      .getByRole('region', { name: 'Output values', exact: true })
      .locator('[title*="8381.7034110152"]'),
  ).toBeVisible();
  await capture(page, 'run');
  await page.locator('details.run-files > summary').click();
  await page.getByRole('button', { name: 'Diagnostics', exact: true }).click();
  await expect(page.getByLabel('Execution diagnostics', { exact: true })).toContainText(
    'exit_code',
  );
  expect(d.history.results.outputs[0].value).toBe(8381.7034110152);
  expect(state.writes).toEqual([]);
});
test('Overview separates metadata and distinguishes criteria from execution', async ({ page }) => {
  const state = await harness(page);
  const d = runFixture(state);
  state.studies[0].description = 'First line\nSecond line\n\nAnother paragraph.';
  d.history.results.execution.state = 'finished';
  d.history.results.criteria = [
    { criterion_id: 'c', outcome: 'violated', reason: 'threshold_comparison' },
  ];
  await login(page, `#v=1&study=${sid}&view=overview`);
  const about = page.getByRole('region', { name: 'About this study', exact: true });
  await expect(about).toContainText('No study question yet');
  await expect(about).not.toContainText(state.studies[0].description, { useInnerText: true });
  await about.getByRole('button', { name: 'Edit study', exact: true }).click();
  await expect(page.getByLabel('Study list description', { exact: true })).toHaveValue(
    state.studies[0].description,
  );
  await page.getByRole('button', { name: 'Close Edit study', exact: true }).click();
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const summary = page.getByRole('list', { name: 'Run status', exact: true });
  await expect(summary).toContainText('ExecutionCompleted');
  await expect(summary).toContainText('Criteria1 of 1 not met');
  await expect(summary).not.toContainText('recorded');
  await capture(page, 'overview');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});
test('Evidence retains direct details, references and exact download', async ({ page }) => {
  const state = await harness(page);
  const record = {
    evidence_id: 'legacy',
    evidence_version_id: 'legacy-v1',
    study_id: sid,
    kind: 'note',
    content: 'A note\n\nWith a paragraph.',
    source_refs: ['Report A, page 5', 'https://example.invalid/not-a-verified-link'],
  };
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/evidence`,
    (r) => r.fulfill({ json: { schema_version: '1', data: [record], next_cursor: null } }),
  );
  await page.route(`**/api/1/studies/${sid}/brief`, route => route.fulfill({json:{schema_version:'1',data:{draft:{content:{assumptions:[{evidence_links:[{evidence_version_id:record.evidence_version_id,relation:'supports'}]}]}},latest_version:null}}}));
  await page.route(`**/api/1/studies/${sid}/evidence/${record.evidence_version_id}`, route => route.fulfill({json:{schema_version:'1',data:record}}));
  await login(page, `#v=1&study=${sid}&view=evidence`);
  const note = page.locator('.evidence-record');
  await expect(note.getByRole('heading',{name:'Evidence note',exact:true})).toBeVisible();
  await expect(note.getByRole('button', { name: 'View evidence (1)', exact: true })).toHaveCount(0);
  await expect(note.getByText('Legacy scope: not inferred')).toHaveCount(0);
  await expect(note.getByRole('button', { name: /Source reference/ })).toHaveCount(0);
  const detail = note;
  await expect(detail).toContainText('Report A, page 5');
  await expect(detail).not.toContainText('Study evidence');
  await detail.getByRole('button', { name: 'Evidence record details', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Evidence record', exact: true })).toContainText(
    'No scope.',
  );
  await page.getByRole('button', { name: 'Close Evidence record', exact: true }).click();
  await expect(note.locator('a')).toHaveCount(0);
  const downloading = page.waitForEvent('download');
  await detail.getByRole('button', { name: 'Evidence record details', exact: true }).click();
  await page.getByRole('dialog', { name: 'Evidence record', exact: true }).getByRole('button', { name: 'Download evidence record', exact: true }).click();
  expect(JSON.parse(await readFile((await (await downloading).path())!, 'utf8'))).toEqual(record);
  await page.getByRole('button', { name: 'Close Evidence record', exact: true }).click();
  await capture(page, 'evidence');
  await expect(note.getByText('Report A, page 5', { exact: true })).toBeVisible();
  expect(state.writes).toEqual([]);
});

test('Overview does not infer outcomes when a recorded run detail is unavailable', async ({
  page,
}) => {
  const state = await harness(page);
  runFixture(state);
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture`, (r) =>
    r.fulfill({
      status: 503,
      json: {
        error: { code: 'unavailable', message: 'Unavailable', fields: [], outcome: 'unchanged' },
      },
    }),
  );
  await login(page, `#v=1&study=${sid}&view=overview`);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await page.getByRole('tab', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Unavailable' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Run status', exact: true })).toHaveCount(0);
  await expect(page.locator('.hf-tag--ok')).toHaveCount(0);
  expect(state.writes).toEqual([]);
});

test('Statement sets preserve shared sources and reader focus', async ({ page }) => {
  const state = await harness(page);
  const run = runFixture(state);
  const source = {
    evidence_version_id: 'retained-note',
    content: 'Exact retained note <script>inert</script>',
    source_refs: ['Exact retained reference'],
  };
  run.history.configuration.schema_version = '3';
  run.history.configuration.derivation = null;
  run.history.configuration.general_context_evidence_version_ids = [];
  run.history.configuration.assumptions = ['first', 'second'].map((assumption_id) => ({
    assumption_id,
    statement: 'Identical statement text under distinct identities.',
    evidence_links: [{ evidence_version_id: source.evidence_version_id, relation: 'supports' }],
  }));
  run.history.configuration.evidence_snapshots = [source];
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
  await expect(page.getByRole('button', {name:'Statement details', exact:true})).toHaveCount(0);
  const assertions = page.locator('.assumption-item').filter({hasText:'Identical statement text under distinct identities.'});
  await expect(assertions).toHaveCount(2);
  const evidence = assertions.nth(1).getByRole('button', {name:'View evidence (1)', exact:true});
  await evidence.click();
  const evidencePanel = page.getByRole('region', {name:'Evidence details', exact:true});
  await expect(evidencePanel).toContainText(source.content);
  await expect(evidencePanel).toContainText('Exact retained reference');
  await expect(evidencePanel.getByRole('button', {name:/View evidence|Statement details|Back to statements/})).toHaveCount(0);
  await capture(page, 'contour-source');
  await page.getByRole('button', {name:'Open assistant', exact:true}).click();
  await capture(page, 'contour-context');
  await page.getByRole('region', {name:'Assistant', exact:true}).getByRole('button', {name:'Hide assistant', exact:true}).click();
  await evidencePanel.getByRole('button', {name:'Close Evidence', exact:true}).click();
  await expect(evidence).toBeFocused();
  await evidence.click();
  await page.getByRole('button', {name:'Home', exact:true}).click();
  await expect(evidencePanel).toHaveCount(0);
  expect(state.writes).toEqual([]);
});

test('Limit context preserves native modality and return focus', async ({ page }) => {
  await harness(page);
  const evidence = {
    evidence_version_id: 'limit-source',
    content: 'Measured range only.',
    source_refs: ['Laboratory notebook, range measurements'],
  };
  const content = {
    schema_version: '2',
    question: 'What is supported within the measured range?',
    scope: 'Measured range',
    limitations: '',
    open_questions: '',
    model_bindings: [],
    steps: [],
    assumptions: [],
    basis_refs: [],
    original_question: null,
    elaboration: null,
    limit_items: [
      {
        limit_id: 'limit-one',
        statement: 'Do not extrapolate.',
        evidence_links: [
          { evidence_version_id: evidence.evidence_version_id, relation: 'supports' },
        ],
      },
    ],
  };
  const saved = {
    version: {
      schema_version: '2',
      approach_version_id: 'approach-v1',
      version_number: 1,
      content,
      digest: 'fixture-approach',
    },
    closure: {
      schema_version: '4',
      models: [],
      configurations: [],
      approach_versions: [],
      run_contexts: [],
      evidence: [evidence],
      root_approach_version_id: 'approach-v1',
      root_approach_digest: 'fixture-approach',
      digest: 'fixture-closure',
    },
  };
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/approach`,
    (route) =>
      route.fulfill({
        json: { schema_version: '1', data: { draft: null, latest_version: saved.version } },
      }),
  );
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/approach/versions/approach-v1`,
    (route) => route.fulfill({ json: { schema_version: '1', data: saved } }),
  );
  await page.route(
    (url) => url.pathname.includes('/approach/versions/approach-v1/'),
    (route) =>
      route.fulfill({ json: { schema_version: '1', data: { items: [], next_cursor: null } } }),
  );
  await login(page, `#v=1&study=${sid}&view=overview`);
  await page.getByRole('button', { name: 'See more details', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Study details', exact: true });
  await expect(dialog.getByRole('button', {name:'Statement details',exact:true})).toHaveCount(0);
  const opener = dialog.getByRole('button', {name:'View evidence (1)',exact:true});
  await opener.click();
  const context = dialog.getByRole('region', {name:'Evidence details',exact:true});
  await expect(context.getByRole('heading',{name:'Evidence',exact:true})).toBeFocused();
  await expect(context).toContainText(evidence.content);
  await capture(page, 'contour-modal-source');
  await expect(context.getByRole('button',{name:/View evidence|Back to statements/})).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(context).toHaveCount(0);
  await expect(dialog).toBeVisible();
  await expect(opener).toBeFocused();
});

test('Unavailable saved evidence never substitutes an unrelated source', async ({page}) => {
  const state=await harness(page), run=runFixture(state);
  run.history.configuration.schema_version='3';
  run.history.configuration.derivation=null;
  run.history.configuration.general_context_evidence_version_ids=[];
  run.history.configuration.assumptions=[{assumption_id:'missing',statement:'Protected statement',evidence_links:[{evidence_version_id:'missing-source',relation:'challenges'}]}];
  run.history.configuration.evidence_snapshots=[{evidence_version_id:'unrelated',content:'Unrelated source content',source_refs:[]}];
  await login(page,`#v=1&study=${sid}&view=runs`);
  await page.getByRole('button',{name:'Inspect run run-fixture',exact:true}).click();
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  await page.locator('.assumption-item').getByRole('button',{name:'View evidence (1)',exact:true}).click();
  const detail=page.getByRole('region',{name:'Evidence details',exact:true});
  await expect(detail).toContainText('Evidence unavailable');
  await expect(detail).not.toContainText('Unrelated source content');
  await page.getByRole('button',{name:'Home',exact:true}).click();
  await expect(detail).toHaveCount(0);
  expect(state.writes).toEqual([]);
});

test('Shared specimens preserve component recipes and scientific states', async ({
  page,
  browser,
}) => {
  const state = await harness(page);
  await login(page);
  const origin = new URL(page.url()).origin;
  const requests: string[] = [],
    violations: string[] = [];
  page.on('request', (request) => requests.push(request.url()));
  await page.addInitScript(() => {
    (window as any).__csp = [];
    document.addEventListener('securitypolicyviolation', (event) =>
      (window as any).__csp.push(event.violatedDirective),
    );
  });
  await page.goto(origin + '/ui/?specimen');
  const material = page.getByRole('group', {name:'Material', exact:true});
  await expect(material.getByRole('button', {name:'Alloy A', exact:true})).toHaveAttribute('aria-pressed', 'true');
  await expect(material.getByRole('button', {name:'Ceramic', exact:true})).toBeDisabled();
  await material.getByRole('button', {name:'Alloy B', exact:true}).focus();
  await page.keyboard.press('Space');
  await expect(material.getByRole('button', {name:'Alloy B', exact:true})).toHaveAttribute('aria-pressed', 'true');
  await expect(material.getByRole('button', {name:'Alloy A', exact:true})).toHaveAttribute('aria-pressed', 'false');
  const preset = page.getByRole('combobox', {name:'Operating preset', exact:true});
  await preset.selectOption('High');
  await expect(preset).toHaveValue('High');
  await expect(preset.locator('option[value="Unsupported"]')).toHaveJSProperty('disabled', true);
  const response = page.getByRole('img', {name: 'Illustrative response response to Input (m)', exact: true});
  await expect(response.getByLabel('Limit: 1.5 m', {exact:true})).toHaveCount(1);
  const referenceGeometry = await response.evaluate(svg => {
    const line = svg.querySelector('.hf-response-curve__reference')!.getBoundingClientRect();
    const plot = svg.getBoundingClientRect();
    return {inside:line.top >= plot.top && line.bottom <= plot.bottom};
  });
  expect(referenceGeometry.inside).toBe(true);
  const barrel = await readFile(new URL('../src/design/index.ts', import.meta.url), 'utf8');
  const exports = [...barrel.matchAll(/export \{([\s\S]*?)\} from/g)]
    .flatMap((match) =>
      match[1]
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean),
    )
    .filter((name) => name !== 'formatNumber')
    .sort();
  const represented = await page
    .locator('[data-components]')
    .evaluateAll((nodes) =>
      [
        ...new Set(nodes.flatMap((node) => node.getAttribute('data-components')!.split(' '))),
      ].sort(),
    );
  expect(represented).toEqual(exports);
  await expect(page.getByRole('list', { name: 'Independent facets' })).toContainText(
    'ExecutionCompleted',
  );
  await expect(page.getByRole('list', { name: 'Independent facets' })).toContainText(
    'Criteria1 of 1 not met',
  );
  await expect(page.getByLabel('Specimen exact source', { exact: true })).toHaveValue(
    "# Exact source <tag>\noutputs['value'] = inputs['value'] ** 2\n",
  );
  const measurements: unknown[] = [];
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
    for (const viewport of [
      { width: 1440, height: 1000 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      for (const size of ['sm', 'desk', 'floor']) {
        const values = await page
          .locator('[data-recipe="' + size + '"]:visible')
          .evaluateAll((nodes) =>
            nodes.map((node) => {
              const s = getComputedStyle(node);
              return {
                font: s.fontFamily,
                size: s.fontSize,
                line: s.lineHeight,
                padding: s.padding,
                gap: s.gap,
                min: s.minHeight,
                height: node.getBoundingClientRect().height,
              };
            }),
          );
        expect(values.length).toBeGreaterThanOrEqual(6);
        for (const value of values) expect(value).toEqual(values[0]);
        expect(values[0].height).toBe(size === 'sm' ? 28 : size === 'desk' ? 36 : 48);
        measurements.push({ theme, viewport, size, values });
      }
      const rhythm = await page.getByRole('region', { name: 'Assertion rhythm' }).evaluate((el) => {
        const items = [...el.querySelectorAll('.hf-assertion')];
        return items.map((item) => {
          const s = item.querySelector('.hf-assertion__statement')!;
          const evidence = item.querySelector('.hf-evidence-stack')!;
          const style = getComputedStyle(item);
          return {
            gap: evidence.getBoundingClientRect().height
              ? evidence.getBoundingClientRect().top - s.getBoundingClientRect().bottom
              : null,
            sourceGap: getComputedStyle(evidence).rowGap,
            padding: style.paddingTop,
          };
        });
      });
      expect(rhythm.map((item) => item.gap)).toEqual([null, 12, 12]);
      expect(rhythm.map((item) => item.padding)).toEqual(['0px', '16px', '16px']);
      expect(rhythm.every((item) => item.sourceGap === '8px')).toBe(true);
      const sections = await page
        .locator('.hf-reading-stack > .hf-reading-section')
        .evaluateAll((nodes) =>
          nodes
            .slice(1, -1)
            .map((node) => [
              getComputedStyle(node).paddingTop,
              getComputedStyle(node).paddingBottom,
            ]),
        );
      expect(sections.every((pair) => pair[0] === '24px' && pair[1] === '24px')).toBe(true);
      const claim = page.locator('.hf-claim');
      const margins = await claim.evaluate((el) =>
        [...el.children].map((child) => getComputedStyle(child).marginTop),
      );
      expect(margins.every((value) => value === '0px')).toBe(true);
      const overflow = await page.evaluate(() => ({
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
        offenders: [...document.querySelectorAll('body *')]
          .filter((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1);
          })
          .slice(0, 15)
          .map((el) => ({
            class: el.className,
            tag: el.tagName,
            right: el.getBoundingClientRect().right,
          })),
      }));
      expect(overflow.scroll, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width + 1);
      const text = page.getByRole('button', {
        name:
          'An unusually long action label that must remain fully readable ' +
          'when the screen is narrow',
      });
      expect(
        await text.evaluate(
          (el) => el.scrollHeight <= el.clientHeight && el.scrollWidth <= el.clientWidth,
        ),
      ).toBe(true);
      await page.getByRole('region', { name: 'Workspace recipes' }).screenshot({
        path:
          process.env.HYPRN_MVP_UI_EVIDENCE_ROOT +
          '/contour-specimen-' +
          theme +
          '-' +
          viewport.width +
          '.png',
      });
      await page.getByRole('region', { name: 'Scientific records' }).screenshot({
        path:
          process.env.HYPRN_MVP_UI_EVIDENCE_ROOT +
          '/contour-scientific-' +
          theme +
          '-' +
          viewport.width +
          '.png',
      });
    }
  }
  const font = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts].some(
      (face) => face.family.includes('Manrope') && face.status === 'loaded',
    );
  });
  expect(font).toBe(true);
  const fonts = requests.filter((url) => /\.(ttf|woff2?)(\?|$)/.test(url));
  expect(fonts.length).toBeGreaterThan(0);
  expect(requests.every((url) => new URL(url).origin === origin)).toBe(true);
  violations.push(...(await page.evaluate(() => (window as any).__csp)));
  expect(violations).toEqual([]);
  const tab = page.getByRole('tablist', { name: 'Specimen views' }).getByRole('tab').first();
  await tab.focus();
  await page.keyboard.press('ArrowRight');
  await expect(
    page.getByRole('tablist', { name: 'Specimen views' }).getByRole('tab').nth(1),
  ).toBeFocused();
  await page.keyboard.press('Home');
  await expect(tab).toBeFocused();
  const opener = page.getByRole('button', { name: 'Open recipe dialog', exact: true });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'Recipe dialog', exact: true });
  await expect(dialog).toBeVisible();
  for (const size of ['sm', 'desk', 'floor']) {
    const geometry = (locator: import('playwright/test').Locator) =>
      locator.evaluate((el) => {
        const s = getComputedStyle(el);
        return [s.fontSize, s.lineHeight, s.padding, s.gap, s.minHeight];
      });
    expect(await geometry(dialog.locator('[data-recipe="' + size + '"]'))).toEqual(
      await geometry(page.locator('[data-recipe="' + size + '"]').first()),
    );
  }
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();

  const controls = page.locator('[aria-label="desk controls"]');
  const enabled = controls.getByRole('button', { name: 'secondary', exact: true });
  const disabled = controls.getByRole('button', { name: 'Unavailable', exact: true });
  const paint = (locator: import('playwright/test').Locator) =>
    locator.evaluate((el) => {
      const s = getComputedStyle(el);
      return [s.backgroundColor, s.borderColor, s.color];
    });
  await page.mouse.move(0, 0);
  const resting = await paint(enabled),
    disabledResting = await paint(disabled);
  await enabled.hover();
  expect(await paint(enabled)).not.toEqual(resting);
  await disabled.hover();
  expect(await paint(disabled)).toEqual(disabledResting);
  await expect(disabled).toBeDisabled();
  await enabled.focus();
  expect(await enabled.evaluate((el) => getComputedStyle(el).outlineWidth)).toBe('2px');
  expect(await enabled.evaluate((el) => getComputedStyle(el).transitionDuration)).toBe('0s');
  expect(
    await page
      .locator('.hf-mark--running')
      .evaluateAll((nodes) => nodes.every((el) => getComputedStyle(el).animationName === 'none')),
  ).toBe(true);
  await page.getByLabel('Example file', { exact: true }).setInputFiles({
    name: 'explicit-model-source.py',
    mimeType: 'text/plain',
    buffer: Buffer.from('# inert fixture bytes\n'),
  });
  await expect(page.getByText('explicit-model-source.py', { exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Loading evidence' })).not.toHaveAttribute(
    'value',
  );

  const touch = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true });
  try {
    const screen = await touch.newPage();
    await guardOrigin(screen);
    await screen.goto(origin + '/ui/?specimen');
    const heights = await screen
      .locator('button:visible')
      .evaluateAll((nodes) => nodes.map((node) => ({label: node.textContent, height: node.getBoundingClientRect().height})));
    expect(heights.filter(({height}) => height < 48)).toEqual([]);
  } finally {
    await touch.close();
  }
  await import('node:fs/promises').then((fs) =>
    fs.writeFile(
      process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/contour-measurements.json',
      JSON.stringify(measurements, null, 2),
    ),
  );
  expect(state.writes).toEqual([]);
});

test('Component reading tabs preserve prose and source without duplicate contents', async ({
  page,
}) => {
  const state = await harness(page);
  referenceModel(state);
  const content = {
    schema_version: '2',
    question: 'Explain the analysis',
    scope: 'Illustrative model',
    limitations: '',
    open_questions: '',
    assumptions: [],
    basis_refs: [],
    model_bindings: [{ binding_id: 'model-binding', model_id: mid, model_revision_id: version }],
    steps: [
      {
        step_id: 'method-one',
        title: 'Full method',
        purpose: 'Purpose '.repeat(80),
        rationale: 'Measured assumptions only.',
        intent: { transformation: 'Compute the explicit response.' },
        implementation_refs: [{ kind: 'instance', binding_id: 'model-binding', instance_id: 'a' }],
        assumptions: [],
        basis_refs: [],
        depends_on: [],
      },
    ],
  };
  content.steps.push({
    ...content.steps[0],
    step_id: 'shared-method',
    title: 'Shared balance',
    purpose: 'One shared scientific rationale.',
    implementation_refs: ['a', 'b'].map((instance_id) => ({
      kind: 'instance',
      binding_id: 'model-binding',
      instance_id,
    })),
  });
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/approach`,
    (route) =>
      route.fulfill({
        json: {
          schema_version: '1',
          data: { draft: { content, revision: 'draft-method' }, latest_version: null },
        },
      }),
  );
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await page.locator('.connected-graph [data-instance="a"]').click();
  const reader = details(page);
  await expect(reader).not.toContainText('One shared scientific rationale.');
  await expect(reader.getByRole('navigation', { name: 'In this explanation' })).toHaveCount(0);
  await expect(
    reader.getByRole('heading', { name: 'Calculation logic', exact: true }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  await expect(page.getByLabel('Python source', { exact: true })).toBeVisible();
  await page.getByLabel('Python source', { exact: true }).fill('# preserved across readers\n');
  await page.getByRole('tab', { name: 'Model explanation', exact: true }).click();
  const modelReader = page.getByRole('region', { name: 'Model explanation reader', exact: true });
  await expect(
    modelReader.getByText('One shared scientific rationale.', { exact: true }),
  ).toHaveCount(1);
  await expect(modelReader).not.toContainText('Purpose '.repeat(80));
  await page.getByRole('tab', { name: 'Diagram', exact: true }).click();
  await page.getByRole('tab', { name: 'Component', exact: true }).click();
  await expect(
    reader.getByRole('heading', { name: 'Calculation logic', exact: true }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  await expect(page.getByLabel('Python source', { exact: true })).toHaveValue(
    '# preserved across readers\n',
  );
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Rendered shell chrome retains text and control contrast in both themes', async ({ page }) => {
  await harness(page);
  await login(page);
  const origin = new URL(page.url()).origin;
  await page.goto(origin + '/ui/?specimen');
  const samples: unknown[] = [];
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await page.setViewportSize({ width: 1440, height: 1000 });
    const rail = page.getByRole('complementary', { name: 'Workspace navigation' });
    await rail.scrollIntoViewIfNeeded();
    const probes = await rail.evaluate((el) => {
      const targets = [
        el.querySelector('.hf-navigation__study')!,
        el.querySelector('.hf-navigation__eyebrow')!,
        el.querySelector('.hf-navigation__item')!,
      ];
      return targets.map((target) => {
        const r = target.getBoundingClientRect(),
          s = getComputedStyle(target);
        return {
          label: target.textContent,
          color: s.color,
          x: r.x + 2,
          y: r.y + 2,
          image: getComputedStyle(el).backgroundImage,
        };
      });
    });
    const bytes = await page.screenshot();
    const measured = await page.evaluate(
      async ({ bytes, probes }) => {
        const bitmap = await createImageBitmap(
          new Blob([new Uint8Array(bytes)], { type: 'image/png' }),
        );
        const canvas = new OffscreenCanvas(bitmap.width, bitmap.height),
          ctx = canvas.getContext('2d')!;
        ctx.drawImage(bitmap, 0, 0);
        const luminance = (rgb: number[]) =>
          rgb
            .map((x) => x / 255)
            .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
            .reduce((sum, x, i) => sum + x * [0.2126, 0.7152, 0.0722][i], 0);
        return probes.map((probe) => {
          const ground = [
            ...ctx.getImageData(Math.floor(probe.x), Math.floor(probe.y), 1, 1).data,
          ].slice(0, 3);
          const ink = probe.color
            .match(/[\d.]+/g)!
            .slice(0, 3)
            .map(Number);
          const a = luminance(ink),
            b = luminance(ground);
          return { ...probe, ground, contrast: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) };
        });
      },
      { bytes: [...bytes], probes },
    );
    for (const sample of measured) {
      expect(sample.image).toContain('linear-gradient');
      expect(sample.contrast, JSON.stringify(sample)).toBeGreaterThanOrEqual(4.5);
    }
    const texture = await page.locator('.hf-workspace').evaluate((el) => ({
      image: getComputedStyle(el).backgroundImage,
      ground: getComputedStyle(el).backgroundColor,
      readingGround: getComputedStyle(el.querySelector('.hf-workspace__canvas')!).backgroundImage,
    }));
    expect(texture.image).toContain('radial-gradient');
    expect(texture.readingGround).toBe('none');
    samples.push({ theme, measured, texture });
  }
  await import('node:fs/promises').then((fs) =>
    fs.writeFile(
      process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/contour-rendered-contrast.json',
      JSON.stringify(samples, null, 2),
    ),
  );
});

test('exploration cards fit unequal quantities without internal scroll at 25–100 percent', async ({
  page,
}) => {
  await harness(page);
  await login(page);
  await page.goto(new URL('/ui/?specimen', page.url()).href);
  const graph = page.getByRole('region', { name: 'Unequal exploration columns', exact: true });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });
      for (const zoom of [100, 75, 50, 25]) {
        await expect(graph.getByLabel('Graph zoom', { exact: true })).toHaveText(zoom + '%');
        await expect
          .poll(() =>
            graph.locator('.hf-node--explorer').evaluateAll((nodes) =>
              nodes.every((node) => {
                const columns = [...node.querySelectorAll<HTMLElement>('.hf-node__port-column')];
                return (
                  columns[0].clientHeight === columns[1].clientHeight &&
                  columns.every(
                    (c) =>
                      c.scrollHeight <= c.clientHeight + 1 && c.scrollWidth <= c.clientWidth + 1,
                  ) &&
                  Math.abs(
                    Number(node.parentElement!.getAttribute('height')) -
                      (node as HTMLElement).offsetHeight,
                  ) <= 1
                );
              }),
            ),
          )
          .toBe(true);
        const rows = await graph
          .locator('.hf-node__port-column:first-child')
          .evaluateAll((cols) =>
            cols.map((c) => [...c.children].map((row) => row.getBoundingClientRect().height)),
          );
        for (const heights of rows)
          expect(Math.max(...heights) - Math.min(...heights)).toBeLessThanOrEqual(1);
        await expect(graph.locator('.hf-response-curve')).toHaveCount(5);
        const outputComposition = await graph.locator('.hf-node__exploration-port[data-direction="out"]').evaluateAll(rows => rows.every(row => {
          const value = row.querySelector('.hf-quantity-result')!.getBoundingClientRect();
          const plot = row.querySelector('.hf-response-curve')!.getBoundingClientRect();
          const box = row.getBoundingClientRect();
          return plot.top >= value.bottom && plot.width > box.width * .8;
        }));
        expect(outputComposition).toBe(true);
        await expect(graph.locator('summary')).toHaveCount(0);
        const palette = await graph.evaluate((el) => ({
          stop: getComputedStyle(el.querySelector('.hf-slider-stop--estimated')!).borderColor,
          line: getComputedStyle(el.querySelector('.hf-response-curve__estimate')!).stroke,
          calculatedStop: getComputedStyle(el.querySelector('.hf-slider-stop--calculated')!)
            .backgroundColor,
          calculatedPoint: getComputedStyle(el.querySelector('.hf-response-curve__calculated')!)
            .fill,
        }));
        expect(palette.stop).toBe(palette.line);
        expect(palette.calculatedStop).toBe(palette.calculatedPoint);
        if (zoom !== 25) await graph.getByRole('button', { name: 'Zoom out', exact: true }).click();
      }
      await expect(graph.getByRole('button', { name: 'Zoom out', exact: true })).toBeDisabled();
      const slider = graph.getByRole('slider').first();
      await slider.press('Home');
      await expect(slider).toHaveAttribute('aria-valuetext', '0 m');
      await slider.press('ArrowRight');
      await expect(slider).toHaveAttribute('aria-valuetext', '1 m');
      const stops = await graph
        .locator('.hf-discrete-track')
        .first()
        .evaluate((el) => {
          const range = el.querySelector('input')!.getBoundingClientRect();
          const dots = [...el.querySelectorAll('.hf-slider-stops span')].map((d) =>
            d.getBoundingClientRect(),
          );
          return {
            start: dots[0].x + dots[0].width / 2 - range.x,
            end: range.right - dots.at(-1)!.x - dots.at(-1)!.width / 2,
          };
        });
      expect(Math.abs(stops.start - stops.end)).toBeLessThan(1);
      for (let i = 0; i < 3; i++)
        await graph.getByRole('button', { name: 'Zoom in', exact: true }).click();
    }
  }
});

test('Disclosure labels and arrows stay vertically centred through expansion', async ({page}) => {
  await harness(page); await login(page);
  await page.goto(new URL('/ui/?specimen',page.url()).href);
  const summary=page.getByText('Additional explanation',{exact:true});
  for (const theme of ['light','dark']) {
    await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    for (const width of [1440,390]) {
      await page.setViewportSize({width,height:1000});
      for (const open of [true,false]) {
        await summary.click();
        expect(await summary.evaluate(el=>el.parentElement!.hasAttribute('open'))).toBe(open);
        const geometry=await summary.evaluate(el=>{const r=document.createRange();r.selectNodeContents(el);const a=el.getBoundingClientRect(),b=r.getBoundingClientRect();return {offset:Math.abs((a.top+a.bottom-b.top-b.bottom)/2),display:getComputedStyle(el).display,align:getComputedStyle(el).alignItems}});
        expect(geometry.display).toBe('flex');expect(geometry.align).toBe('center');expect(geometry.offset).toBeLessThanOrEqual(3);
      }
    }
  }
});


test('Record metadata starts with details and dropdown arrows have a shared inset',async({page})=>{
  const state=await harness(page);referenceModel(state);
  await login(page,`#v=1&study=${sid}&view=model&model=${mid}&revision=${version}`);
  const row=page.locator('[data-record-kind="Model"]');
  await expect(row.locator(':scope > :first-child')).toHaveAttribute('aria-label','Model record details');
  await expect(row.locator('.hf-record-identity')).toHaveText('Version ID '+version.slice(0,8));
  const select=page.getByRole('combobox',{name:'Model version',exact:true});
  const geometry=await select.evaluate(el=>{const a=el.getBoundingClientRect(),arrow=el.parentElement!.querySelector('svg')!.getBoundingClientRect();return {inset:a.right-arrow.right,center:Math.abs((a.top+a.bottom-arrow.top-arrow.bottom)/2),padding:parseFloat(getComputedStyle(el).paddingRight)}});
  expect(geometry.inset).toBe(12);expect(geometry.center).toBeLessThanOrEqual(1);expect(geometry.padding).toBeGreaterThanOrEqual(geometry.inset+16);
  await row.getByRole('button',{name:'Model record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Model version record',exact:true})).toContainText(version);
});
