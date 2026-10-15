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
/** The component's draft source is in the Selection inspector's "Edit source" disclosure. */
async function openSource(page: Page) {
  const source = details(page).locator('details.component-source');
  if (!(await source.evaluate((e) => (e as HTMLDetailsElement).open)))
    await source.locator('summary').click();
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
test('Model actions stay direct and quantity search reveals distant targets', async ({ page }) => {
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
  await page.getByRole('searchbox', { name: 'Search loaded model' }).fill('Squared response');
  await page
    .getByRole('region', { name: 'Loaded model search results' })
    .getByRole('button', { name: 'Squared response', exact: true })
    .click();
  await expect(page.getByRole('dialog', { name: 'Unsaved changes' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(
    details(page).getByRole('heading', { name: 'Linear response', exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel('Python source', { exact: true })).toHaveValue("outputs['u'] = 7\n");
  await page.getByRole('combobox', { name: 'Model version', exact: true }).selectOption(version);
  await page
    .getByRole('dialog', { name: 'Unsaved changes' })
    .getByRole('button', { name: 'Discard changes', exact: true })
    .click();
  await expect(page.locator('.model-heading > div > h2')).toHaveText('Model version 30000000');
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
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
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
  await login(page, `#v=1&study=${sid}&view=evidence`);
  const note = page.locator('.evidence-record');
  await expect(note.getByRole('button', { name: 'View evidence', exact: true })).toBeVisible();
  await expect(note.getByText('Legacy scope: not inferred')).toHaveCount(0);
  await expect(note.getByRole('button', { name: /Source reference/ })).toHaveCount(0);
  await note.getByRole('button', { name: 'View evidence', exact: true }).click();
  const detail = page.getByRole('dialog', { name: 'Evidence detail', exact: true });
  await expect(detail).toContainText('Report A, page 5');
  await expect(detail).not.toContainText('Study evidence');
  await detail.getByRole('button', { name: 'Evidence record details', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Evidence record', exact: true })).toContainText(
    'No scope.',
  );
  await page.getByRole('button', { name: 'Close Evidence record', exact: true }).click();
  await expect(note.locator('a')).toHaveCount(0);
  const downloading = page.waitForEvent('download');
  await detail.getByRole('button', { name: 'Download evidence record', exact: true }).click();
  expect(JSON.parse(await readFile((await (await downloading).path())!, 'utf8'))).toEqual(record);
  await capture(page, 'evidence');
  await page.getByRole('button', { name: 'Close Evidence detail', exact: true }).click();
  await expect(note.getByText('Report A, page 5', { exact: true })).toBeHidden();
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
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
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
  const opener = page.getByRole('button', {
    name: '2 statements · Configuration assumptions',
    exact: true,
  });
  await opener.click();
  const context = page.getByRole('region', { name: 'Scientific context', exact: true });
  await expect(context).toContainText('Identical statement text under distinct identities.');
  await expect(context.locator('.hf-claim__statement')).toHaveCount(2);
  for (const card of await context.locator('.hf-claim').all()) {
    await expect(card).toContainText('Identical statement text under distinct identities.');
    await expect(card).toBeVisible();
  }
  const evidence = context
    .locator('[data-statement="second"]')
    .getByRole('button', { name: 'View evidence', exact: true });
  await evidence.click();
  await expect(context).toContainText(source.content);
  await expect(context).toContainText('Exact retained reference');
  await expect(context).toContainText('Source passage unavailable. Showing evidence content.');
  await capture(page, 'contour-source');
  await context.getByRole('button', { name: 'Back to statements', exact: true }).click();
  await expect(context.locator('[data-statement="second"]')).toBeVisible();
  await expect(evidence).toBeFocused();
  await page.getByRole('button', { name: 'Open assistant', exact: true }).click();
  await capture(page, 'contour-context');
  await page
    .getByRole('region', { name: 'Assistant', exact: true })
    .getByRole('button', { name: 'Close Assistant', exact: true })
    .click();
  await context.getByRole('button', { name: 'Close Scientific context', exact: true }).click();
  await expect(opener).toBeFocused();
  await opener.click();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(context).toHaveCount(0);
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
    cases: [],
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
  const opener = dialog.getByRole('button', { name: 'Inspect statement', exact: true });
  await opener.click();
  const context = dialog.getByRole('region', { name: 'Scientific context', exact: true });
  await expect(context.locator('[data-statement="limit-one"]')).toBeFocused();
  await context.getByRole('button', { name: 'View evidence', exact: true }).click();
  await expect(
    context.getByRole('heading', { name: 'Evidence content', exact: true }),
  ).toBeFocused();
  await expect(context).toContainText(evidence.content);
  await capture(page, 'contour-modal-source');
  await context.getByRole('button', { name: 'Back to statements', exact: true }).click();
  await expect(context.getByRole('button', { name: 'View evidence', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(context).toHaveCount(0);
  await expect(dialog).toBeVisible();
  await expect(opener).toBeFocused();
});

for (const outcome of ['late', 'denied'] as const) {
  test(`Context source ${outcome} responses cannot retain protected content`, async ({ page }) => {
    const state = await harness(page);
    const run = runFixture(state);
    run.history.configuration.schema_version = '3';
    run.history.configuration.derivation = null;
    run.history.configuration.general_context_evidence_version_ids = [];
    run.history.configuration.assumptions = [
      {
        assumption_id: 'source-bound',
        statement: 'Protected statement',
        evidence_links: [{ evidence_version_id: 'unloaded-source', relation: 'challenges' }],
      },
    ];
    let requested!: () => void, release!: () => void;
    const started = new Promise<void>((resolve) => {
      requested = resolve;
    });
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(
      (url) => url.pathname === `/api/1/studies/${sid}/evidence/unloaded-source`,
      async (route) => {
        requested();
        await held;
        await route.fulfill(
          outcome === 'denied'
            ? {
                status: 403,
                json: {
                  error: {
                    code: 'forbidden',
                    message: 'Access lost',
                    fields: [],
                    outcome: 'unchanged',
                  },
                },
              }
            : {
                json: {
                  schema_version: '1',
                  data: {
                    evidence_version_id: 'unloaded-source',
                    content: 'Late protected source',
                    source_refs: [],
                  },
                },
              },
        );
      },
    );
    await login(page, `#v=1&study=${sid}&view=runs`);
    await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
    await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
    await page.getByRole('button', { name: 'Inspect statement', exact: true }).click();
    const context = page.getByRole('region', { name: 'Scientific context', exact: true });
    await context.getByRole('button', { name: 'View evidence', exact: true }).click();
    await started;
    if (outcome === 'late') await page.getByRole('button', { name: 'Home', exact: true }).click();
    release();
    await expect(context).toHaveCount(0);
    await expect(page.getByText('Late protected source', { exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });
}

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
  await expect(
    page.getByRole('button', { name: '2 statements · Complete set', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', {
      name: '1 loaded statement · partial set · Partial set',
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText('No linked statements · Empty set', { exact: true })).toBeVisible();
  await expect(
    page.getByText('Statements partially loaded · Loading set', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('Statements unavailable · Unavailable set', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: /0 statements/ })).toHaveCount(0);
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
      .evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
    expect(heights.every((height) => height >= 48)).toBe(true);
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

test('Method contents focus actual sections and open the existing source disclosure', async ({
  page,
}) => {
  const state = await harness(page);
  referenceModel(state);
  const content = {
    schema_version: '2',
    question: 'Explain the calculation',
    scope: 'Illustrative model',
    limitations: '',
    open_questions: '',
    assumptions: [],
    cases: [],
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
  const contents = reader.getByRole('navigation', { name: 'In this explanation', exact: true });
  await expect(contents).toBeVisible();
  await contents.getByRole('button', { name: 'Calculation logic', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(
    reader.getByRole('heading', { name: 'Calculation logic', exact: true }),
  ).toBeFocused();
  await contents.getByRole('button', { name: 'Python function', exact: true }).click();
  const disclosure = reader.locator('details.component-source');
  await expect(disclosure).toHaveAttribute('open', '');
  await expect(disclosure.locator('summary')).toBeFocused();
  await expect(disclosure).toContainText('outputs');
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
        el.querySelector('.hf-navigation__section')!,
        el.querySelector('.hf-tab')!,
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
