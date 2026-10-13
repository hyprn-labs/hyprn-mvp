import { test, expect, Page } from 'playwright/test';
import { evidencePath } from './evidence';
import { ownerPassword, servedOrigin } from './support/served';

async function fixture(page: Page, empty = false) {
  await page.goto('/ui/');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  const response = page.waitForResponse(r => r.url().endsWith('/api/1/session') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const csrf = (await (await response).json()).data.csrf_token;
  async function post(path: string, data: unknown) {
    const r = await page.request.post('/api/1' + path, { headers: { Origin: servedOrigin(), 'X-CSRF-Token': csrf }, data });
    expect(r.ok(), await r.text()).toBeTruthy(); return r.json();
  }
  const s = (await post('/studies', { command_id: crypto.randomUUID(), name: 'Connected views ' + crypto.randomUUID() })).data;
  const base = `/studies/${s.study_id}/models`;
  let m = (await post(base, { command_id: crypto.randomUUID(), expected_revision: s.revision, name: 'Heat transfer model', template: 'empty' })).data;
  let ids: Record<string, any> = {};
  if (!empty) {
    const raw = Buffer.from("outputs['heat'] = inputs['temperature']\noutputs['flow'] = inputs['pressure']\n");
    const hash = await crypto.subtle.digest('SHA-256', raw);
    const ports = ['temperature', 'pressure', 'heat', 'flow'].map((name, i) => ({ temp_key: name, name, code_symbol: name, direction: i < 2 ? 'input' : 'output', value_type: 'real_scalar', units: '' }));
    const ref = (instance: string, port: string) => ({ instance_temp_key: instance, definition_temp_key: 'd', port_temp_key: port });
    const edits = [{ kind: 'create_definition', temp_key: 'd', definition_kind: 'explicit_component', name: 'Repeated thermal component with long descriptive engineering name', ports, source: { encoding: 'base64', media_type: 'text/x-python', bytes: raw.toString('base64'), sha256: Buffer.from(hash).toString('hex') } },
      ...['a', 'b', 'c', 'd1', 'e', 'f'].map(temp_key => ({ kind: 'instantiate', temp_key, version_ref: { temp_key: 'd' } })),
      ...[['ab1', 'a', 'heat', 'b', 'temperature'], ['ab2', 'a', 'flow', 'b', 'pressure'], ['bc', 'b', 'heat', 'c', 'temperature'], ['ad', 'a', 'heat', 'd1', 'temperature']].map(([temp_key, from, output, to, input]) => ({ kind: 'connect', temp_key, source_ref: ref(from, output), target_ref: ref(to, input) }))];
    const changed = await post(base + '/' + m.model_id + '/edits', { command_id: crypto.randomUUID(), expected_revision: m.draft_revision, edits });
    m = changed.data; ids = changed.created_ids;
    m = (await post(base + '/' + m.model_id + '/edits', { command_id: crypto.randomUUID(), expected_revision: m.draft_revision, edits: ['a', 'b'].map(key => ({ kind: 'rename_instance', instance_id: ids[key].instance_id, name: 'Repeated thermal component' })) })).data;
  }
  await page.evaluate(hash => { window.location.hash = hash; }, `v=1&study=${s.study_id}&model=${m.model_id}&view=model`);
  await expect(page.getByRole('button', { name: 'Reload model', exact: true })).toBeVisible();
  return { s, m, ids, base: '/api/1' + base + '/' + m.model_id };
}

test('grouped directed graph and XDSM share exact selections, cyclic traces and presentation ordering', async ({ page }) => {
  const { ids, base } = await fixture(page);
  const mutations: string[] = []; page.on('request', r => { if (r.url().includes('/api/1/') && r.method() !== 'GET') mutations.push(r.url()); });
  const region = page.getByRole('region', { name: 'Model view', exact: true });
  await expect(region).toBeVisible();
  const a = ids.a.instance_id, b = ids.b.instance_id;
  const edge = region.locator(`[data-group="${a}:${b}"]`).first();
  await edge.click(); await expect(edge).toHaveAttribute('aria-pressed', 'true');
  await expect(edge.getByText('heat, flow', { exact: true })).toBeVisible();
  await expect(region.locator('[data-selected-link]')).toHaveCount(2);
  expect(await region.locator('[data-selected-link]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-selected-link')).sort())).toEqual([ids.ab1.connection_id, ids.ab2.connection_id].sort());
  await region.getByRole('tab', { name: 'XDSM', exact: true }).click();
  await expect(region.getByText('Producer row → consumer column', { exact: true })).toBeVisible();
  await expect(region.locator(`[data-group="${a}:${b}"]`).first()).toHaveAttribute('aria-pressed', 'true');
  const diagonal = region.locator(`[data-instance="${a}"]:visible`).first(); await diagonal.click();
  await region.getByLabel('Trace relationships', { exact: true }).selectOption('downstream');
  await expect(region.getByText(/Downstream trace: 4 components/)).toBeVisible();
  await region.getByRole('tab', { name: 'Graph', exact: true }).click();
  await expect(region.locator(`[data-instance="${a}"]`).first()).toHaveAttribute('aria-pressed', 'true');
  await region.getByLabel('Search loaded model').fill('flow');
  await expect(region.getByRole('button', { name: /Find variable/ })).toHaveCount(6);
  await region.getByRole('button', { name: /Find variable/ }).nth(1).click();
  await expect(region.locator('[data-selected-variable]')).toHaveCount(1);
  await region.getByRole('button', { name: 'Clear search', exact: true }).click();
  await region.getByRole('button', { name: 'Clear trace', exact: true }).click();
  await region.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect(region.getByLabel('Graph zoom')).toHaveText('125%');
  await region.getByText('Pan and reset', { exact: true }).click();
  await region.getByRole('button', { name: 'Pan right', exact: true }).click();
  await region.getByRole('button', { name: 'Reset to 100%', exact: true }).click();
  await expect(region.getByLabel('Graph zoom')).toHaveText('100%');
  await region.getByText('Structure · presentation order', { exact: true }).click();
  await region.getByRole('button', { name: 'Move down', exact: true }).first().click();
  expect(await region.locator('[data-order-id]').first().getAttribute('data-order-id')).toBe(b);
  await region.getByRole('tab', { name: 'XDSM', exact: true }).click();
  await expect(region.locator('thead [data-column-id]').first()).toHaveAttribute('data-column-id', b);
  await expect(region.getByRole('rowheader', { name: 'Free inputs', exact: true })).toBeVisible();
  await expect(region.getByRole('columnheader', { name: 'Responses', exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
  const stored = (await (await page.request.get(base)).json()).data;expect(stored.connections).toHaveLength(4);
});

test('dense long labels remain usable at desktop widths and diagrams have keyboard equivalents', async ({ page }) => {
  await fixture(page);const region = page.getByRole('region', { name: 'Model view', exact: true });
  await expect(region).toBeVisible();
  for (const width of [1440, 1920, 1024]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const view of ['Graph', 'XDSM']) {
      await region.getByRole('tab', { name: view, exact: true }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
      await region.scrollIntoViewIfNeeded();
      await page.screenshot({ path: evidencePath(`connected-${view.toLowerCase()}-${width}.png`), fullPage: false });
    }
  }
  await region.getByRole('tab', { name: 'Graph', exact: true }).click();
  await region.getByText('Structure · presentation order', { exact: true }).click();
  const select = region.locator('[data-order-id] button').first();await select.focus();await select.press('Enter');await expect(select).toHaveAttribute('aria-pressed', 'true');
  await region.getByRole('button', { name: 'Focus selection', exact: true }).click();
  await expect(region.getByLabel('Graph zoom')).toHaveText('150%');
});

test('empty snapshot has explicit empty diagrams and no fabricated Driver', async ({ page }) => {
  await fixture(page, true);const region = page.getByRole('region', { name: 'Model view', exact: true });
  await expect(region.getByRole('tabpanel').getByText('No components in this model.', { exact: true })).toBeVisible();
  await region.getByRole('tab', { name: 'XDSM', exact: true }).click();
  await expect(region.getByRole('tabpanel').getByText('No components in this model.', { exact: true })).toBeVisible();
  await expect(region.getByText('Driver', { exact: true })).toHaveCount(0);
});

// Pure presentation algorithm: unsupported scientific cycles must still terminate when inspected.
test('cyclic, fan-out and malformed readable snapshots have bounded exact-ID projections', async () => {
  const { project, traceRelationships } = await import('../src/GraphView');
  const groups = [
    { key: 'a:b', source: 'a', target: 'b', links: [{ connection_id: 'ab', source_ref: { instance_id: 'a', port_id: 'x' }, target_ref: { instance_id: 'b', port_id: 'y' } }] },
    { key: 'b:a', source: 'b', target: 'a', links: [{ connection_id: 'ba', source_ref: { instance_id: 'b', port_id: 'x' }, target_ref: { instance_id: 'a', port_id: 'y' } }] },
    { key: 'a:c', source: 'a', target: 'c', links: [{ connection_id: 'ac', source_ref: { instance_id: 'a', port_id: 'z' }, target_ref: { instance_id: 'c', port_id: 'y' } }] },
  ];
  const trace = traceRelationships(groups, ['a'], 'downstream');expect([...trace.nodes].sort()).toEqual(['a','b','c']);expect([...trace.links].sort()).toEqual(['ab','ac','ba']);
  expect([...traceRelationships(groups, ['a'], 'outgoing', { kind: 'variable', instance_id: 'a', port_id: 'z' }).links]).toEqual(['ac']);
  const broken = project({ instances: [{ instance_id: 'a', definition_version_id: 'missing', name: 'Same name' }], root_instance_id: 'root', definitions: [], connections: groups[0].links } as any);
  expect(broken.nodes[0].incomplete).toBe(true);expect(broken.invalid).toHaveLength(1);expect(broken.groups).toEqual([]);
});
