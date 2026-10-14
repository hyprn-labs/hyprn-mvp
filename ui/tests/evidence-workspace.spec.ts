import { test, expect, type Page } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { criterionStatus, executionResult, resultOutcomes, runOutcomes } from '../src/runStatus';
import { startFixture, stopFixture, guardOrigin, harness, login, sid, mid, referenceModel, runFixture, details, version } from './foundry-fixtures';
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture); test.beforeEach(async ({page}) => { await guardOrigin(page); }); test.afterAll(stopFixture);
/** The component's draft source is in the Selection inspector's "Edit source" disclosure. */
async function openSource(page: Page) { const source = details(page).locator('details.component-source'); if (!await source.evaluate(e => (e as HTMLDetailsElement).open)) await source.locator('summary').click(); }
async function capture(page: Page, name: string) { for (const colorScheme of ['light','dark'] as const) { await page.emulateMedia({colorScheme}); await page.screenshot({path:`${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/opk-${name}-${colorScheme}.png`,animations:'disabled'}); } }
test('criterion counts use the same denominator for single, multiple and unresolved assessments',()=>{
 expect(criterionStatus([{outcome:'violated'}]).label).toBe('1 of 1 not met');
 expect(criterionStatus([{outcome:'violated'},{outcome:'met'},{outcome:'unresolved'}]).label).toBe('1 of 3 not met');
 expect(criterionStatus([{outcome:'unresolved'},{outcome:'met'}]).label).toBe('1 of 2 not evaluated');
 expect(criterionStatus([{outcome:'met'}]).label).toBe('1 of 1 met');
 expect(criterionStatus([]).label).toBe('None defined');
});
test('run outcomes are Execution and Criteria only; unread, unresulted and unknown states are never success',()=>{
 // Only facets the runtime computes today. Constant facets are not projected.
 const finished={run_id:'r',state:'recorded',process_state:'finished',exit_status:0,history:{results:{execution:{state:'finished',exit_code:0,message:'completed'},criteria:[{criterion_id:'c',outcome:'violated',reason:'threshold_comparison'}],convergence:{state:'not_applicable'},optimization:{termination:'not_applicable',feasibility:'not_applicable'},applicability:{state:'unassessed',evidence_refs:[]}}}} as any;
 expect(Object.keys(runOutcomes(finished))).toEqual(['execution','criteria']);
 expect(runOutcomes(finished)).toEqual({execution:{label:'Completed',tone:'ok'},criteria:{label:'1 of 1 not met',tone:'alarm'}});
 const failed=structuredClone(finished);failed.history.results.execution.state='failed';failed.history.results.criteria=[];
 expect(runOutcomes(failed)).toEqual({execution:{label:'Failed',tone:'alarm'},criteria:{label:'None defined',tone:'inert'}});
 expect(runOutcomes({run_id:'r',state:'accepted_run',history:null} as any).criteria).toEqual({label:'Not evaluated',tone:'advisory'});
 expect(runOutcomes(null)).toEqual({execution:{label:'Loading status',tone:'inert'},criteria:{label:'Not available',tone:'advisory'}});
 expect(runOutcomes(null,true).execution).toEqual({label:'Status unavailable',tone:'inert'});
 expect(executionResult('finished')).toEqual({label:'Completed',tone:'ok'});
 expect(executionResult('failed')).toEqual({label:'Failed',tone:'alarm'});
 expect(executionResult('unrecognized')).toEqual({label:'Unknown',tone:'advisory'});
 expect(resultOutcomes({state:'finished'},[{outcome:'met'},{outcome:'unresolved'}])).toEqual({execution:{label:'Completed',tone:'ok'},criteria:{label:'1 of 2 not evaluated',tone:'advisory'}});
});
test('model header groups secondary actions and connections occur in Ports only',async({page})=>{
  const state = await harness(page);
  referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  const header = page.locator('.model-heading');
  await expect(
    header.getByRole('button', { name: 'Save model version', exact: true }),
  ).toBeVisible();
  await expect(
    header.getByRole('button', { name: 'Create configuration', exact: true }),
  ).toBeVisible();
  await expect(
    header.getByRole('button', { name: 'Export model and data', exact: true }),
  ).toHaveCount(0);
  expect(
    await page.getByLabel('Model version', { exact: true }).locator('option').allTextContents(),
  ).toEqual(['draft-r1 (draft)', '30000000 (read-only)']);
  await header.getByRole('button', { name: 'Model actions', exact: true }).click();
  const menu = page.getByRole('dialog', { name: 'Model actions', exact: true });
  for (const name of ['Rename model', 'Reload model', 'Import', 'Export model and data'])
    await expect(menu.getByRole('button', { name, exact: true })).toBeVisible();
  await capture(page, 'model-actions');
  await page.keyboard.press('Escape');
  // Quantities and connections appear once below the inspector, which summarizes them.
  await page.locator('.connected-graph [data-instance="a"]').click();
  await expect(
    details(page).getByText('Affine · 3 quantities · shown below', { exact: true }),
  ).toBeVisible();
  await openSource(page);
  await expect(
    details(page).getByRole('group', { name: 'Source actions' }).getByRole('button'),
  ).toHaveCount(1);
  const bytes = await page.getByLabel('Python source', { exact: true }).inputValue();
  await details(page).getByRole('button', { name: 'Expand source', exact: true }).click();
  await details(page).getByRole('button', { name: 'Collapse source', exact: true }).click();
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
test('retained model and configuration stay exact during modeling outage, without run actions',async({page})=>{
 const state=await harness(page);const d=runFixture(state);state.outage=true;
 d.history.configuration.criteria=[{criterion_id:'c',target:{instance_id:'a',port_id:'u'},operator:'le',threshold:10,units:'',evidence_version_ids:['retained-note']}];d.history.results.criteria=[{criterion_id:'c',outcome:'violated',reason:'threshold_comparison'}];d.history.configuration.evidence_snapshots=d.history.evidence;
 await login(page,`#v=1&study=${sid}&view=runs`);await page.getByRole('button',{name:'Inspect run run-fixture',exact:true}).click();await expect(page.getByRole('button',{name:'Refresh run status',exact:true})).toHaveCount(0);await expect(page.getByText('Criterion outcomes',{exact:true})).toHaveCount(0);
 await page.getByRole('tab',{name:'Configuration',exact:true}).click();const config=page.getByRole('tabpanel',{name:'Configuration',exact:true});await expect(config.locator('.configuration-criterion .hf-criterion__requirement span')).toHaveText(['at most','10','dimensionless']);await expect(config.getByText('Not met',{exact:true})).toBeVisible();await expect(config.getByRole('button',{name:'Run this configuration',exact:true})).toHaveCount(0);await expect(config.locator('.configuration-inputs .hf-field__ro')).toHaveText('0');
 await config.locator('.configuration-criterion').getByRole('button',{name:'View evidence',exact:true}).click();await expect(page.getByRole('dialog',{name:'Evidence detail',exact:true})).toContainText('Exact retained note <script>inert</script>');await page.keyboard.press('Escape');await capture(page,'retained-configuration');
 await page.getByRole('tab',{name:'Model',exact:true}).click();await page.locator('.connected-graph [data-instance="a"]').click();await expect(page.getByRole('region',{name:'Quantities table',exact:true}).getByRole('columnheader',{name:'Value',exact:true})).toBeVisible();await details(page).getByRole('button',{name:'View source',exact:true}).click();expect(await page.getByRole('dialog',{name:'Source · Linear response',exact:true}).getByLabel('Read-only authored source').textContent()).toBe(Buffer.from(d.history.model_snapshot.source_files[0].bytes,'base64').toString('utf8'));await expect(details(page).locator('.quantity-endpoints:visible')).toHaveCount(0);await capture(page,'retained-model');expect(state.writes).toEqual([]);expect(state.unknown).toEqual([]);
});
test('retained file preview verifies hashes, preserves download bytes, and drops late responses',async({page})=>{
 const {createHash}=await import('node:crypto'); const {source,latch}=await import('./foundry-fixtures');
 const state=await harness(page); const d=runFixture(state),bytes=Buffer.from(source),sha256=createHash('sha256').update(bytes).digest('hex');state.outage=true;
 d.history.artifacts=[{artifact_id:'source',name:'sources/exact.py',role:'source',size:bytes.length,sha256}];
 await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/source`,r=>r.fulfill({body:bytes,contentType:'application/octet-stream'}));
 await login(page,`#v=1&study=${sid}&view=runs`);await page.getByRole('button',{name:'Inspect run run-fixture',exact:true}).click();await page.getByRole('tab',{name:'Evidence',exact:true}).click();
 const row=page.getByRole('region',{name:'Run files table',exact:true}).locator('tbody tr');await row.getByRole('button',{name:'Preview',exact:true}).click();const preview=page.getByLabel('Read-only run file',{exact:true});await expect(preview).toBeFocused();expect(await preview.textContent()).toBe(source);
 await page.getByRole('button',{name:'Close preview',exact:true}).click();const download=page.waitForEvent('download');await row.getByRole('button',{name:'Download',exact:true}).click();expect(await readFile((await (await download).path())!)).toEqual(bytes);
 await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/source`,r=>r.fulfill({body:Buffer.alloc(bytes.length,120),contentType:'application/octet-stream'}));await row.getByRole('button',{name:'Preview',exact:true}).click();await expect(page.getByRole('alert')).toContainText('This file could not be verified. It was not downloaded.');await expect(preview).toHaveCount(0);
 const held=latch(),requested=latch();await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/source`,async r=>{requested.release();await held.promise;await r.fulfill({body:bytes,contentType:'application/octet-stream'});});
 try{await row.getByRole('button',{name:'Preview',exact:true}).click();await requested.promise;await page.getByRole('button',{name:'Back to run history',exact:true}).click();const response=page.waitForResponse(r=>r.url().endsWith('/artifacts/source'));held.release();await response;await expect(preview).toHaveCount(0);}finally{held.release();}
 expect(state.writes).toEqual([]);expect(state.unknown).toEqual([]);
});
