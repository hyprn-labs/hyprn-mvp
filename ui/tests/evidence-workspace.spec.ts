import { test, expect, type Page } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { criterionStatus, executionResult, resultOutcomes, runOutcomes } from '../src/runStatus';
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
  latch,
} from './foundry-fixtures';
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture);
test.beforeEach(async ({ page }) => {
  await guardOrigin(page);
});
test.afterAll(stopFixture);
/** The component's draft source stays mounted in its Python reading pane. */
async function openSource(page: Page) {
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
}
async function capture(page: Page, name: string) {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.screenshot({
      path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/opk-${name}-${colorScheme}.png`,
      animations: 'disabled',
    });
  }
}
test('criterion counts use the same denominator for single, multiple and unresolved assessments', () => {
  expect(criterionStatus([{ outcome: 'violated' }]).label).toBe('1 of 1 not met');
  expect(
    criterionStatus([{ outcome: 'violated' }, { outcome: 'met' }, { outcome: 'unresolved' }]).label,
  ).toBe('1 of 3 not met');
  expect(criterionStatus([{ outcome: 'unresolved' }, { outcome: 'met' }]).label).toBe(
    '1 of 2 not evaluated',
  );
  expect(criterionStatus([{ outcome: 'met' }]).label).toBe('1 of 1 met');
  expect(criterionStatus([]).label).toBe('None defined');
});
test('run outcomes are Execution and Criteria only; unread, unresulted and unknown states are never success', () => {
  // Only facets the runtime computes today. Constant facets are not projected.
  const finished = {
    run_id: 'r',
    state: 'recorded',
    process_state: 'finished',
    exit_status: 0,
    history: {
      results: {
        execution: { state: 'finished', exit_code: 0, message: 'completed' },
        criteria: [{ criterion_id: 'c', outcome: 'violated', reason: 'threshold_comparison' }],
        convergence: { state: 'not_applicable' },
        optimization: { termination: 'not_applicable', feasibility: 'not_applicable' },
        applicability: { state: 'unassessed', evidence_refs: [] },
      },
    },
  } as any;
  expect(Object.keys(runOutcomes(finished))).toEqual(['execution', 'criteria']);
  expect(runOutcomes(finished)).toEqual({
    execution: { label: 'Completed', tone: 'ok' },
    criteria: { label: '1 of 1 not met', tone: 'alarm' },
  });
  const failed = structuredClone(finished);
  failed.history.results.execution.state = 'failed';
  failed.history.results.criteria = [];
  expect(runOutcomes(failed)).toEqual({
    execution: { label: 'Failed', tone: 'alarm' },
    criteria: { label: 'None defined', tone: 'inert' },
  });
  expect(
    runOutcomes({ run_id: 'r', state: 'accepted_run', history: null } as any).criteria,
  ).toEqual({ label: 'Not evaluated', tone: 'advisory' });
  expect(runOutcomes(null)).toEqual({
    execution: { label: 'Loading status', tone: 'inert' },
    criteria: { label: 'Not available', tone: 'advisory' },
  });
  expect(runOutcomes(null, true).execution).toEqual({ label: 'Status unavailable', tone: 'inert' });
  expect(executionResult('finished')).toEqual({ label: 'Completed', tone: 'ok' });
  expect(executionResult('failed')).toEqual({ label: 'Failed', tone: 'alarm' });
  expect(executionResult('unrecognized')).toEqual({ label: 'Unknown', tone: 'advisory' });
  expect(
    resultOutcomes({ state: 'finished' }, [{ outcome: 'met' }, { outcome: 'unresolved' }]),
  ).toEqual({
    execution: { label: 'Completed', tone: 'ok' },
    criteria: { label: '1 of 2 not evaluated', tone: 'advisory' },
  });
});
test('model header groups secondary actions and connections occur in Ports only', async ({
  page,
}) => {
  const state = await harness(page);
  referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  const header = page.locator('.model-header');
  await expect(
    header.getByRole('button', { name: 'Save model version', exact: true }),
  ).toBeVisible();
  await expect(
    header.getByRole('button', { name: 'Create configuration', exact: true }),
  ).toBeVisible();
  await expect(
    header.getByRole('button', { name: 'Export model', exact: true }),
  ).toHaveCount(0);
  expect(
    await page.getByLabel('Model version', { exact: true }).locator('option').allTextContents(),
  ).toEqual(['Draft', 'Version 1']);
  await header.getByRole('button', { name: 'Model actions', exact: true }).click();
  const menu = page.getByRole('dialog', { name: 'Model actions', exact: true });
  for (const name of ['Rename model', 'Refresh model', 'Import model', 'Export model'])
    await expect(menu.getByRole('button', { name, exact: true })).toBeVisible();
  await capture(page, 'model-actions');
  await page.keyboard.press('Escape');
  // The selected name appears once; quantities remain in the table below.
  await page.locator('.connected-graph [data-instance="a"]').click();
  await expect(
    details(page).getByRole('heading', { name: 'Linear response', exact: true }),
  ).toBeVisible();
  await openSource(page);
  await expect(details(page).getByRole('group', { name: 'Source actions' })).toHaveCount(0);
  const bytes = await page.getByLabel('Python source', { exact: true }).inputValue();
  await page.getByRole('tab', { name: 'Component', exact: true }).click();
  await page.getByRole('tab', { name: 'Python', exact: true }).click();
  expect(await page.getByLabel('Python source', { exact: true }).inputValue()).toBe(bytes);
  await capture(page, 'source');
  const controls = page.getByRole('group', { name: 'Graph view controls' });
  const heights = await controls
    .getByRole('button')
    .evaluateAll((es) => es.map((e) => e.getBoundingClientRect().height));
  expect(new Set(heights).size).toBe(1);
  await page.getByLabel('Model version', { exact: true }).selectOption(version);
  await header.getByRole('button', { name: 'Model actions', exact: true }).click();
  await expect(menu.getByRole('button', { name: 'Rename model', exact: true })).toHaveCount(0);
  await page.keyboard.press('Escape');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});
test('retained model and configuration stay exact during modeling outage, without run actions', async ({
  page,
}) => {
  const state = await harness(page);
  const d = runFixture(state);
  state.outage = true;
  d.history.configuration.criteria = [
    {
      criterion_id: 'c',
      target: { instance_id: 'a', port_id: 'u' },
      operator: 'le',
      threshold: 10,
      units: '',
      evidence_version_ids: ['retained-note'],
    },
  ];
  d.history.results.criteria = [
    { criterion_id: 'c', outcome: 'violated', reason: 'threshold_comparison' },
  ];
  d.history.configuration.evidence_snapshots = d.history.evidence;
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Refresh run status', exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByText('Criterion outcomes', { exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
  const config = page.getByRole('tabpanel', { name: 'Configuration', exact: true });
  await expect(
    config.locator('.configuration-criterion .hf-criterion__requirement span'),
  ).toHaveText(['at most', '10', 'dimensionless']);
  await expect(config.getByText('Not met', { exact: true })).toBeVisible();
  await expect(
    config.getByRole('button', { name: 'Run this configuration', exact: true }),
  ).toHaveCount(0);
  await expect(config.locator('.configuration-inputs .hf-field__ro')).toHaveText('0');
  await config
    .locator('.configuration-criterion')
    .getByRole('button', { name: 'View evidence (1)', exact: true })
    .click();
  await expect(page.getByRole('region', { name: 'Evidence details', exact: true })).toContainText(
    'Exact retained note <script>inert</script>',
  );
  await page.keyboard.press('Escape');
  await capture(page, 'retained-configuration');
  await page.getByRole('tab', { name: 'Model', exact: true }).click();
  await page.locator('.connected-graph [data-instance="a"]').click();
  await page.getByRole('tab', { name: 'Quantities', exact: true }).click();
  await expect(
    page
      .getByRole('region', { name: 'Quantities table', exact: true })
      .getByRole('columnheader', { name: 'Value', exact: true }),
  ).toBeVisible();
  await openSource(page);
  expect(
    await page
      .getByRole('region', { name: 'Selection inspector', exact: true })
      .getByLabel('Read-only authored source')
      .textContent(),
  ).toBe(Buffer.from(d.history.model_snapshot.source_files[0].bytes, 'base64').toString('utf8'));
  await expect(details(page).locator('.quantity-endpoints:visible')).toHaveCount(0);
  await capture(page, 'retained-model');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});
test('retained file preview verifies hashes, preserves download bytes, and drops late responses', async ({
  page,
}) => {
  const { createHash } = await import('node:crypto');
  const { source, latch } = await import('./foundry-fixtures');
  const state = await harness(page);
  const d = runFixture(state),
    bytes = Buffer.from(source),
    sha256 = createHash('sha256').update(bytes).digest('hex');
  state.outage = true;
  d.history.artifacts = [
    { artifact_id: 'source', name: 'sources/exact.py', role: 'source', size: bytes.length, sha256 },
  ];
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/source`, (r) =>
    r.fulfill({ body: bytes, contentType: 'application/octet-stream' }),
  );
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await page.locator('details.run-files > summary').click();
  const row = page
    .getByRole('region', { name: 'Run files table', exact: true })
    .locator('tbody tr');
  await row.getByRole('button', { name: 'Preview', exact: true }).click();
  const preview = page.getByLabel('Read-only run file', { exact: true });
  await expect(preview).toBeFocused();
  expect(await preview.textContent()).toBe(source);
  await page.getByRole('button', { name: 'Close preview', exact: true }).click();
  const download = page.waitForEvent('download');
  await row.getByRole('button', { name: 'Download', exact: true }).click();
  expect(await readFile((await (await download).path())!)).toEqual(bytes);
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/source`, (r) =>
    r.fulfill({ body: Buffer.alloc(bytes.length, 120), contentType: 'application/octet-stream' }),
  );
  await row.getByRole('button', { name: 'Preview', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText(
    'This file could not be verified. It was not downloaded.',
  );
  await expect(preview).toHaveCount(0);
  const held = latch(),
    requested = latch();
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/source`, async (r) => {
    requested.release();
    await held.promise;
    await r.fulfill({ body: bytes, contentType: 'application/octet-stream' });
  });
  try {
    await row.getByRole('button', { name: 'Preview', exact: true }).click();
    await requested.promise;
    await page.getByRole('button', { name: 'Return to run history', exact: true }).click();
    const response = page.waitForResponse((r) => r.url().endsWith('/artifacts/source'));
    held.release();
    await response;
    await expect(preview).toHaveCount(0);
  } finally {
    held.release();
  }
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('One evidence action groups exact sources, counts unavailable versions and clears on navigation', async ({
  page,
}) => {
  const state = await harness(page);
  const run = runFixture(state);
  const saved = run.history.evidence[0];
  const second = {
    ...saved,
    evidence_version_id: 'second-source',
    content: 'Second saved passage',
    source_refs: ['Second report, page 8'],
  };
  run.history.configuration.inputs[0].provenance.evidence_version_ids = [
    saved.evidence_version_id,
    second.evidence_version_id,
    saved.evidence_version_id,
    'unavailable-source',
  ];
  run.history.configuration.evidence_snapshots = [saved, second];
  await login(page, `#v=1&study=${sid}&view=runs`);
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
  const row = page
    .getByRole('region', { name: 'Saved configuration inputs', exact: true })
    .getByRole('row')
    .last();
  const action = row.getByRole('button', { name: 'View evidence (3)', exact: true });
  await expect(row.getByRole('button', { name: /View evidence/ })).toHaveCount(1);
  await expect(row).not.toContainText(saved.content);
  await action.click();
  const panel = page.getByRole('region', { name: 'Evidence details', exact: true });
  await expect(panel).toContainText(saved.content);
  await expect(panel).toContainText('Second saved passage');
  await expect(panel).toContainText('Second report, page 8');
  await expect(panel.getByText('Evidence unavailable', { exact: true })).toHaveCount(1);
  await expect(panel.getByRole('button', { name: /View evidence/ })).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: 'Evidence detail', exact: true })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await expect(action).toBeFocused();
  await action.click();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(panel).toHaveCount(0);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Evidence library shows cited versions directly, preserves source attribution and reports partial reads', async ({page}) => {
  const state = await harness(page);
  const original = {evidence_id:'family', evidence_version_id:'original', study_id:sid,
    title:'Reference condition', content:'HYPRN evidence/1\n'+JSON.stringify({source_reference:'Engineering report — A. Author, 2026', location:'p. 7, Table 2', excerpt:'The reference temperature is 293.15 K.', explanation:'This supports the reference condition, not the operating temperature.'}), source_refs:['Engineering report — A. Author, 2026'], resource_scope:{scope_version:'1',kind:'study',study_id:sid}};
  let failing = true;
  await page.route(`**/api/1/studies/${sid}/brief`, route => route.fulfill({json:{schema_version:'1',data:{draft:{content:{assumptions:[{evidence_links:[{evidence_version_id:'original',relation:'supports'},{evidence_version_id:'original',relation:'supports'},{evidence_version_id:'missing',relation:'context'}]}]}},latest_version:null}}}));
  await page.route(`**/api/1/studies/${sid}/evidence/original`, route => route.fulfill({json:{schema_version:'1',data:original}}));
  await page.route(`**/api/1/studies/${sid}/evidence/missing`, route => route.fulfill({status:404,json:{error:{code:'resource_not_found',message:'Missing cited version',fields:[],outcome:'unchanged'}}}));
  await page.route(`**/api/1/studies/${sid}/configurations`, route => failing ? route.fulfill({status:503,json:{error:{code:'backend_unavailable',message:'Unavailable configuration list',fields:[],outcome:'unchanged'}}}) : route.fallback());
  await page.route(`**/api/1/studies/${sid}/agent/attribution*`, route => route.fulfill({json:{schema_version:'1',data:{items:[{record_kind:'evidence_version',record_id:'original',version_id:'original',agent:{display_name:'Study assistant'},delegator:{display_name:'Engineer'}}],next_cursor:null}}}));
  await login(page, `#v=1&study=${sid}&view=evidence`);
  const library = page.getByRole('region',{name:'Evidence library',exact:true});
  await expect(library.getByRole('heading',{name:original.title,exact:true})).toHaveCount(1);
  await expect(library.getByRole('button',{name:/View evidence/})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Assumptions by owner',exact:true})).toHaveCount(0);
  await expect(library.getByRole('region',{name:'Source',exact:true})).toHaveText('SourceEngineering report — A. Author, 2026');
  await expect(library.locator('blockquote')).toHaveText('The reference temperature is 293.15 K.');
  await expect(library.getByRole('region',{name:'Source excerpt',exact:true})).toContainText('p. 7, Table 2');
  await expect(library.getByRole('region',{name:'Assistant explanation',exact:true})).toContainText('This supports the reference condition');
  await expect(library.getByText('Evidence unavailable',{exact:true})).toHaveCount(1);
  await expect(library.getByRole('alert')).toContainText('may be incomplete');
  await library.getByRole('button',{name:'Evidence record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Evidence record',exact:true})).toContainText('original');
  await page.keyboard.press('Escape');
  failing = false;
  await library.getByRole('button',{name:'Retry loading evidence',exact:true}).click();
  await expect(page.getByRole('button',{name:'Refresh evidence',exact:true})).toBeEnabled();
  await expect(library.locator('blockquote')).toHaveText('The reference temperature is 293.15 K.');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('A deep-linked finished run returns to a freshly readable history', async ({ page }) => {
  const state = await harness(page);
  const detail = runFixture(state);
  const run = '90000000-0000-0000-0000-000000000001';
  detail.run_id = run;
  state.runs[0].run_id = run;
  await page.route(`**/api/1/studies/${sid}/runs/${run}`, (route) =>
    route.fulfill({ json: { schema_version: '1', data: detail } }),
  );
  await login(page, `#v=1&study=${sid}&view=runs&run=${run}`);
  await page.getByRole('button', { name: 'Return to run history', exact: true }).click();
  await expect(page.getByRole('button', { name: `Inspect run ${run}`, exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Refresh runs', exact: true })).toBeEnabled();
  await expect(page.getByText('1 run', { exact: true })).toBeVisible();
  expect(state.unknown).toEqual([]);
});

test('Run-result and evidence pickers use the same filtered coverage and page retry', async ({
  page,
}) => {
  const state = await harness(page);
  referenceModel(state);
  const requestCursors: (string | null)[] = [];
  let fail = true;
  const result = (n: number) => ({
    source_run_id: 'source-run-' + n,
    source_output: { instance_id: 'a', port_id: 'u' },
    value: n,
    units: '',
    labels: {
      run_name: 'Source run ' + n,
      model_name: 'Response',
      instance_name: 'Linear',
      output_name: n === 2 ? 'Late output' : 'First output',
    },
    outcomes: { execution: { state: 'succeeded' } },
  });
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/result-sources`,
    (route) => {
      const cursor = new URL(route.request().url()).searchParams.get('cursor');
      requestCursors.push(cursor);
      if (cursor && fail) {
        fail = false;
        return route.fulfill({
          status: 503,
          json: {
            error: {
              code: 'internal_error',
              message: 'Temporary results failure',
              fields: [],
              outcome: 'unchanged',
            },
          },
        });
      }
      return route.fulfill({
        json: {
          schema_version: '1',
          data: {
            schema_version: '3',
            items: [result(cursor ? 2 : 1)],
            next_cursor: cursor ? null : 'result-next',
          },
        },
      });
    },
  );
  const evidence = (id: string) => ({
    evidence_version_id: id,
    evidence_id: id,
    study_id: sid,
    title: 'Evidence ' + id,
    content: 'Available source',
    source_refs: [],
    resource_scope: { scope_version: '1', kind: 'study', study_id: sid },
  });
  const evidenceRequests: (string | null)[] = [];
  await page.route(
    (url) => url.pathname === `/api/1/studies/${sid}/evidence`,
    (route) => {
      const cursor = new URL(route.request().url()).searchParams.get('cursor');
      evidenceRequests.push(cursor);
      return route.fulfill({
        json: {
          schema_version: '1',
          data: [evidence(cursor ? 'second' : 'first')],
          next_cursor: cursor ? null : 'evidence-next',
        },
      });
    },
  );
  await login(page, `#v=1&study=${sid}&model=${mid}&revision=${version}&view=model`);
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  await page.getByRole('button', { name: 'New configuration', exact: true }).click();
  await page.getByRole('button', { name: 'Use a run result', exact: true }).first().click();
  const picker = page.getByRole('dialog', { name: /Use a run result for/ });
  await expect(picker.getByText('1 result shown · More available', { exact: true })).toBeVisible();
  await picker.getByLabel('Filter results', { exact: true }).fill('Late output');
  await picker.getByRole('button', { name: 'Load more results', exact: true }).click();
  await picker.getByRole('button', { name: 'Retry loading more results', exact: true }).click();
  await expect(picker.getByText('1 match in 2 results', { exact: true })).toBeVisible();
  await picker.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Add evidence', exact: true }).first().click();
  const sources = page.getByRole('dialog', { name: /Add evidence to/ });
  await expect(
    sources.getByText('1 evidence record shown · More available', { exact: true }),
  ).toBeVisible();
  await sources.getByRole('button', { name: 'Load more evidence records', exact: true }).click();
  await expect(sources.getByText('2 evidence records', { exact: true })).toBeVisible();
  expect(requestCursors).toEqual([null, 'result-next', 'result-next']);
  expect(evidenceRequests.slice(-2)).toEqual([null, 'evidence-next']);
  await page.route(`**/api/1/studies/${sid}/evidence/second`, (route) =>
    route.fulfill({
      status: 403,
      json: {
        error: {
          code: 'forbidden',
          message: 'Evidence access lost',
          fields: [],
          outcome: 'unchanged',
        },
      },
    }),
  );
  await sources.getByRole('button', { name: 'Choose Evidence second', exact: true }).click();
  await sources.getByRole('button', { name: 'Attach evidence', exact: true }).click();
  await expect(
    sources.getByRole('button', { name: 'Choose Evidence first', exact: true }),
  ).toHaveCount(0);
  await expect(sources.getByRole('button', { name: 'Create new', exact: true })).toBeDisabled();
  await sources
    .getByRole('button', { name: 'Retry loading evidence records', exact: true })
    .click();
  await expect(
    sources.getByText('1 evidence record shown · More available', { exact: true }),
  ).toBeVisible();
  await expect(
    sources.getByRole('button', { name: 'Choose Evidence first', exact: true }),
  ).toBeEnabled();
  await expect(sources.getByRole('button', { name: 'Create new', exact: true })).toBeEnabled();
  expect(evidenceRequests.at(-1)).toBe(null);

  expect(state.unknown).toEqual([]);
});

test('New evidence stays out of the library until explicitly cited', async ({page}) => {
  const state = await harness(page);
  const record = {evidence_id:'new', evidence_version_id:'new-version', study_id:sid, title:'Unattached source', content:'A note, not a source quotation.', source_refs:[], resource_scope:{scope_version:'1',kind:'study',study_id:sid}};
  let attached = false;
  await page.route(`**/api/1/studies/${sid}/brief`, route => route.fulfill({json:{schema_version:'1',data:{draft:attached?{content:{assumptions:[{evidence_links:[{evidence_version_id:'new-version',relation:'supports'}]}]}}:null,latest_version:null}}}));
  await page.route(`**/api/1/studies/${sid}/evidence`, route => route.request().method() === 'POST' ? route.fulfill({json:{schema_version:'1',data:record}}) : route.fallback());
  await page.route(`**/api/1/studies/${sid}/evidence/new-version`, route => route.fulfill({json:{schema_version:'1',data:record}}));
  await login(page, `#v=1&study=${sid}&view=evidence`);
  await page.getByRole('button',{name:'New evidence',exact:true}).click();
  await page.getByLabel('Title',{exact:true}).fill(record.title);
  await page.getByLabel('Evidence note',{exact:true}).fill(record.content);
  await page.getByRole('button',{name:'Create evidence',exact:true}).click();
  const library = page.getByRole('region',{name:'Evidence library',exact:true});
  await expect(library).toContainText('Evidence saved.');
  await expect(library.getByRole('heading',{name:record.title,exact:true})).toHaveCount(0);
  attached = true;
  await expect(page.getByRole('button',{name:'Refresh evidence',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Refresh evidence',exact:true}).click();
  await expect(library.getByRole('heading',{name:record.title,exact:true})).toBeVisible();
  await expect(library.getByRole('region',{name:'Evidence note',exact:true})).toContainText(record.content);
  await expect(library.locator('blockquote')).toHaveCount(0);
  expect(state.unknown).toEqual([]);
});
