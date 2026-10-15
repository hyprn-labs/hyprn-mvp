import { test, expect, type Page } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { formatNumber } from '../src/design/numbers';
import { startFixture, stopFixture, guardOrigin, harness, login, sid, mid, referenceModel, runFixture, details, version } from './foundry-fixtures';
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture); test.beforeEach(async ({ page }) => { await guardOrigin(page); }); test.afterAll(stopFixture);
/** The component's draft source is in the Selection inspector's "Edit source" disclosure. */
async function openSource(page: Page) { const source = details(page).locator('details.component-source'); if (!await source.evaluate(e => (e as HTMLDetailsElement).open)) await source.locator('summary').click(); }
async function capture(page: Page, name: string) { for (const colorScheme of ['light', 'dark'] as const) { await page.emulateMedia({colorScheme}); await page.screenshot({path:`${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/nx7-${name}-${colorScheme}.png`,animations:'disabled'}); } }
test('display precision never turns small nonzero values into zero', () => {
  for (const [value, expected] of [[8381.7034110152,'8381.703'],[3127.9887138077,'3127.989'],[1e-10,'1e-10'],[-0.000004321987,'-4.322e-6'],[0,'0'],[1,'1'],[-1.23456,'-1.235'],[1e20,'1e+20']] as const) expect(formatNumber(value)).toBe(expected);
  expect(formatNumber(NaN)).toBe('not computed');
});
test('model controls and source have direct actions; quantity cells align and search reveals distant targets', async ({page}) => {
 const state=await harness(page); referenceModel(state);
 for(let i=0;i<16;i++)state.model.instances.push({...state.model.instances[0],instance_id:'remote-'+i,name:'Remote component '+i});
 await login(page,`#v=1&study=${sid}&model=${mid}&view=model`);
 await expect(page.getByText('View controls',{exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Help?',exact:true}).click(); await expect(page.getByRole('dialog',{name:'How to read the graph'})).toContainText('arrow keys'); await page.keyboard.press('Escape');
 const search=page.getByRole('searchbox',{name:'Search loaded model',exact:true}); await search.fill('Remote component 15');
 await page.getByRole('region',{name:'Loaded model search results'}).getByRole('button',{name:'Remote component 15',exact:true}).click();
 const target=page.locator('.connected-graph [data-instance="remote-15"]'); await expect(target).toBeFocused();
 const bounds=await target.boundingBox(), viewport=await page.locator('.graph-viewport').boundingBox(); expect(bounds!.y).toBeGreaterThanOrEqual(viewport!.y); expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(viewport!.y+viewport!.height);
 await expect(details(page).getByRole('heading',{name:'Remote component 15',exact:true})).toBeVisible();
 await openSource(page);
 await expect(details(page).getByText('Source tools',{exact:true})).toHaveCount(0); await expect(details(page).getByText(/^Declared symbols:/)).toHaveCount(0);
 await expect(details(page).getByRole('button',{name:'Indent selection',exact:true})).toHaveCount(0);
 await expect(details(page).getByRole('button',{name:'Code reference',exact:true})).toHaveCount(0); await expect(details(page).locator('.quantity-endpoints:visible')).toHaveCount(0);
 await capture(page,'source');
 // Quantities are listed once, below the projections, scoped to the selected component; a quantity
 // revealed by the model search is scrolled into view inside the table's own region.
 const quantities=page.getByRole('region',{name:'Quantities table',exact:true});
 await expect(quantities.locator('[data-variable^="remote-15/"]').first()).toBeVisible();
 expect(await page.locator('[data-variable="remote-15/x"] td').evaluateAll(es=>es.every(e=>getComputedStyle(e).verticalAlign==='middle'))).toBeTruthy();
 await search.fill('x'); await page.getByRole('region',{name:'Loaded model search results'}).getByRole('button',{name:'Remote component 15 · x (x)',exact:true}).click(); const row=quantities.locator('[data-variable="remote-15/x"]'); await expect(row).toHaveAttribute('aria-selected','true');
 await expect.poll(async()=>{const r=await row.boundingBox(),q=await quantities.boundingBox();return !!r&&!!q&&r.y>=q.y-1&&r.y+r.height<=q.y+q.height+1;}).toBe(true);
 await capture(page,'variables');
 await page.getByRole('tab',{name:'XDSM',exact:true}).click(); await search.fill('Remote component 15'); await page.getByRole('region',{name:'Loaded model search results'}).getByRole('button',{name:'Remote component 15',exact:true}).click();
 await expect(page.locator('.xdsm [data-instance="remote-15"]')).toBeFocused();
 await capture(page,'xdsm');
 expect(state.writes).toEqual([]);expect(state.unknown).toEqual([]);
});
test('search respects unsaved source and read-only model versions never borrow a draft name',async({page})=>{
 const state=await harness(page); referenceModel(state);
 await login(page,`#v=1&study=${sid}&model=${mid}&view=model`);
 await page.locator('.connected-graph [data-instance="a"]').click(); await openSource(page);
 await page.getByLabel('Python source',{exact:true}).fill("outputs['u'] = 7\n");
 await page.getByRole('searchbox',{name:'Search loaded model'}).fill('Squared response'); await page.getByRole('region',{name:'Loaded model search results'}).getByRole('button',{name:'Squared response',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Unsaved changes'})).toBeVisible();
 await page.getByRole('button',{name:'Keep editing',exact:true}).click();
 await expect(details(page).getByRole('heading',{name:'Linear response',exact:true})).toBeVisible(); await expect(page.getByLabel('Python source',{exact:true})).toHaveValue("outputs['u'] = 7\n");
 await page.getByRole('combobox',{name:'Model version',exact:true}).selectOption(version); await page.getByRole('dialog',{name:'Unsaved changes'}).getByRole('button',{name:'Discard changes',exact:true}).click();
 await expect(page.locator('.model-heading > div > h2')).toHaveText('Model version 30000000');
 expect(state.writes).toEqual([]);
});
test('run criterion aligns with seven outcomes; rounded outputs retain exact values and diagnostics', async({page})=>{
 const state=await harness(page); const d=runFixture(state); d.history.results.execution={state:'finished',exit_code:0,message:'completed'}; d.history.results.outputs[0].value=8381.7034110152;
 d.history.configuration.criteria=[{criterion_id:'criterion-1',target:{instance_id:'a',port_id:'u'},operator:'lt',threshold:1,units:''}]; d.history.results.criteria=[{criterion_id:'criterion-1',outcome:'violated',reason:'threshold_comparison'}];
 await login(page,`#v=1&study=${sid}&view=runs`); await page.getByRole('button',{name:'Inspect run run-fixture',exact:true}).click();
 const ledger=page.getByRole('list',{name:'Run status',exact:true}); await expect(ledger.locator('.hf-facet__k')).toHaveText(['Execution','Criteria']); await expect(ledger.getByRole('listitem').filter({hasText:'Criteria'}).locator('.hf-facet__v')).toHaveText('1 of 1 not met');
 const tops=await ledger.locator('.hf-facet__v').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().top)); expect(Math.max(...tops)-Math.min(...tops)).toBeLessThan(2);
 await expect(page.getByText('Run status and diagnostics',{exact:true})).toHaveCount(0);
 await expect(page.getByRole('region',{name:'Output values',exact:true})).toContainText('8381.703'); await expect(page.getByRole('region',{name:'Output values',exact:true})).not.toContainText('8381.703411');
 await expect(
   page
     .getByRole('region', { name: 'Output values', exact: true })
     .locator('[title*="8381.7034110152"]'),
 ).toBeVisible();
 await capture(page,'run');
 await page.locator('details.run-files > summary').click();
 await page.getByRole('button', { name: 'Diagnostics', exact: true }).click();
 await expect(page.getByLabel('Execution diagnostics', { exact: true })).toContainText('exit_code');
 expect(d.history.results.outputs[0].value).toBe(8381.7034110152);expect(state.writes).toEqual([]);
});
test(
  'Overview separates metadata and distinguishes criteria from execution',
  async ({
  page,
}) => {
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
test('evidence has one details action, readable references and an exact download without invented legacy scope',async({page})=>{
 const state=await harness(page); const record={evidence_id:'legacy',evidence_version_id:'legacy-v1',study_id:sid,kind:'note',content:'A note\n\nWith a paragraph.',source_refs:['Report A, page 5','https://example.invalid/not-a-verified-link']};
 await page.route(url=>url.pathname===`/api/1/studies/${sid}/evidence`,r=>r.fulfill({json:{schema_version:'1',data:[record],next_cursor:null}}));
 await login(page,`#v=1&study=${sid}&view=evidence`); const note=page.locator('.evidence-record');
 await expect(note.getByRole('button',{name:'View evidence',exact:true})).toBeVisible();await expect(note.getByText('Legacy scope: not inferred')).toHaveCount(0);await expect(note.getByRole('button',{name:/Source reference/})).toHaveCount(0);
 await note.getByRole('button',{name:'View evidence',exact:true}).click();const detail=page.getByRole('dialog',{name:'Evidence detail',exact:true});await expect(detail).toContainText('Report A, page 5');await expect(detail).not.toContainText('Study evidence');
 await detail.getByRole('button', { name: 'Evidence record details', exact: true }).click();
 await expect(page.getByRole('dialog', { name: 'Evidence record', exact: true })).toContainText(
   'No scope.',
 );
 await page.getByRole('button', { name: 'Close Evidence record', exact: true }).click();
 await expect(note.locator('a')).toHaveCount(0);
 const downloading=page.waitForEvent('download');await detail.getByRole('button',{name:'Download evidence record',exact:true}).click();expect(JSON.parse(await readFile((await (await downloading).path())!,'utf8'))).toEqual(record);
 await capture(page,'evidence');await page.getByRole('button',{name:'Close Evidence detail',exact:true}).click();await expect(note.getByText('Report A, page 5',{exact:true})).toBeHidden();expect(state.writes).toEqual([]);
});

test('Overview does not infer outcomes when a recorded run detail is unavailable',async({page})=>{
 const state=await harness(page);runFixture(state);
 await page.route(`**/api/1/studies/${sid}/runs/run-fixture`,r=>r.fulfill({status:503,json:{error:{code:'unavailable',message:'Unavailable',fields:[],outcome:'unchanged'}}}));
 await login(page,`#v=1&study=${sid}&view=overview`);
 await page.getByRole('button', { name: 'Runs', exact: true }).click();
 await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
 await expect(page.getByRole('alert').filter({ hasText: 'Unavailable' })).toBeVisible();
 await expect(page.getByRole('list', { name: 'Run status', exact: true })).toHaveCount(0);
 await expect(page.locator('.hf-tag--ok')).toHaveCount(0);
 expect(state.writes).toEqual([]);
});

test('Statement sets preserve shared sources and reader focus', async ({
  page,
}) => {
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

test('Limit context preserves native modality and return focus', async ({
  page,
}) => {
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
