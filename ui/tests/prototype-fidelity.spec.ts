import { test, expect, type Page } from 'playwright/test';
import { createServer, type Server } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { canonical } from '../src/exports';
import type { ModelDraft, Study } from '../src/contract';

import { startFixture, stopFixture, guardOrigin, sid, sid2, mid, version, source, components, details, mutations, latch, harness, login, openStudy, modelFixture, openModel, referenceModel, runFixture } from './foundry-fixtures';
const build = process.env.HYPRN_MVP_NAV_BUILD;
test.skip(!build, 'Isolated fixture suite requires HYPRN_MVP_NAV_BUILD');

// Details stack What it computes · Why · Assumptions (no tabs); the draft source editor
// is in the component's "Edit source" disclosure and the quantities table is always below.
async function openSource(page: Page) { const source = details(page).locator('details.component-source'); if (!await source.evaluate(e => (e as HTMLDetailsElement).open)) await source.locator('summary').click(); }
let origin: string;
test.beforeAll(async () => { origin = await startFixture(); });
test.beforeEach(async ({ page }) => { await guardOrigin(page); });
test.afterAll(stopFixture);

test('Foundry runs show Execution and Criteria as independent facets and explicit zero versus not computed in both themes', async ({ page }) => {
  const state = await harness(page);
  runFixture(state);
  await login(page);
  await page.getByRole('button', { name: 'Open study Scalar model study' }).click();
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  const capture = (name: string) =>
    page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/' + name + '.png' });
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await expect(page.locator('.run-list .hf-tag')).toHaveText(['Execution recorded']);
    await capture('foundry-runs-' + theme);
    await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Run history', exact: true })).toBeHidden();
    const ledger = page.getByRole('list', { name: 'Run status', exact: true });
    // Only computed facets; constant ones (convergence, termination, feasibility, completeness, applicability) are not shown.
    await expect(ledger.locator('.hf-facet__k')).toHaveText(['Execution', 'Criteria']);
    await expect(ledger).not.toContainText('Not converged');
    await expect(ledger).not.toContainText('Not applicable');
    await expect(
      page.getByRole('region', { name: 'Output values', exact: true }).locator('tbody tr').first(),
    ).toContainText('0dimensionless');
    await expect(page.getByRole('region', { name: 'Output values', exact: true })).toContainText(
      'not computed: Producer failed',
    );
    await expect(page.locator('.run-key-outputs .hf-readout__basis')).toHaveCount(0);
    const table = page.getByRole('region', { name: 'Output values', exact: true });
    await expect(table).toContainText('not computed');
    await expect(table).toContainText('Producer failed');
    await expect(page.locator('.run-panel .hf-record')).toContainText('Run record');
    await capture('foundry-run-partial-' + theme);
    await page.getByRole('tab', { name: 'Model & inputs', exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Run this configuration', exact: true }),
    ).toBeHidden();
    await capture('foundry-run-model-' + theme);
    await page.getByRole('tab', { name: 'Evidence & files', exact: true }).click();
    await expect(
      page.getByText('retained-note: Exact retained note <script>inert</script>', { exact: true }),
    ).toBeVisible();
    await capture('foundry-run-evidence-' + theme);
    await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
  }
  state.detail.history.results.optimization = {
    termination: 'unrecognized_fixture_state',
    feasibility: null,
  };
  state.detail.history.results.criteria = [
    { criterion_id: 'criterion-met', outcome: 'met', reason: 'threshold_comparison' },
    {
      criterion_id: 'criterion-unresolved',
      outcome: 'unresolved',
      reason: 'required_output_unavailable',
    },
  ];
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  const ledger = page.getByRole('list', { name: 'Run status', exact: true });
  await expect(ledger.locator('.hf-facet__k')).toHaveText(['Execution', 'Criteria']);
  await expect(ledger).not.toContainText('Termination');
  await expect(ledger).not.toContainText('Constraints');
  await expect(ledger.getByRole('listitem').filter({ hasText: 'Criteria' })).toContainText(
    '1 of 2 not evaluated',
  );
  await expect(page.getByText('criterion-met: Met', { exact: false })).toBeVisible();
  await expect(
    page.getByText('criterion-unresolved: Not evaluated', { exact: false }),
  ).toBeVisible();
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Foundry run missing uncertain and failed history stay truthful and late history cannot reopen detail', async ({ page }) => {
  const state = await harness(page); const retained = runFixture(state);
  await login(page); await page.getByRole('button', { name: 'Open study Scalar model study' }).click(); await page.getByRole('button', { name: 'Runs', exact: true }).click();
  for (const status of ['uncertain', 'preparation_failed']) {
    state.detail = { run_id: 'run-fixture', state: status, history: null };
    await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
    await expect(page.getByText('This run\'s record is not available yet.', { exact: true })).toBeVisible();
    await expect(page.getByText('No results for this run. Missing values are never shown as zero.', { exact: true })).toBeVisible();
    await expect(page.locator('.run-panel .hf-ledger')).toHaveCount(0);
    await page.getByRole('button', { name: 'Refresh run status', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Refresh run status', exact: true })).toBeEnabled();
    await page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/foundry-run-' + status + '.png' });
    await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
  }
  const held = latch(), requested = latch();
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture`, async route => { requested.release(); await held.promise; await route.fulfill({ json: { schema_version: '1', data: retained } }); });
  try {
    await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click(); await requested.promise;
    await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
    const response = page.waitForResponse(r => r.url().endsWith('/runs/run-fixture')); held.release(); await response;
    await expect(page.getByRole('heading', { name: 'Run history', exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Run details', exact: true })).toHaveCount(0);
  } finally { held.release(); }
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});

test('Foundry run retains exact source artifact bytes through outage and discards late artifact previews', async ({ page }) => {
  const state = await harness(page); const detail = runFixture(state), bytes = Buffer.from(source), sha256 = createHash('sha256').update(bytes).digest('hex');
  detail.history.artifacts = [{ artifact_id: 'retained-source', name: 'sources/exact.py', role: 'source', size: bytes.length, sha256 }, { artifact_id: 'large', name: 'large.txt', role: 'diagnostics', size: 65537, sha256 }];
  state.outage = true; state.model.source_files = [];
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/retained-source`, route => route.fulfill({ body: bytes, contentType: 'application/octet-stream' }));
  await login(page); await page.getByRole('button', { name: 'Open study Scalar model study' }).click(); await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await page.getByRole('tab', { name: 'Model & inputs', exact: true }).click();
  await page.getByText('Exact snapshots, source, context and dependencies', { exact: true }).click();
  const exact = page.getByRole('tabpanel', { name: 'Model & inputs', exact: true });
  expect(await exact.locator('pre').filter({ hasText: "outputs['heat']" }).first().textContent()).toBe(source);
  await expect(exact).toContainText('Explicit recorded zero');
  await page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/foundry-run-outage.png' });
  await page.getByRole('tab', { name: 'Evidence & files', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Preview large.txt', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Preview sources/exact.py', exact: true }).click();
  const preview = page.getByLabel('Read-only run file', { exact: true }); await expect(preview).toBeVisible(); expect(await preview.textContent()).toBe(source);
  await page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/foundry-run-artifact.png' });
  await page.getByRole('button', { name: 'Close artifact preview', exact: true }).click();
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download sources/exact.py', exact: true }).click(); const file = await download;
  expect(await readFile((await file.path())!)).toEqual(bytes);
  const held = latch(), requested = latch();
  await page.route(`**/api/1/studies/${sid}/runs/run-fixture/artifacts/retained-source`, async route => { requested.release(); await held.promise; await route.fulfill({ body: bytes, contentType: 'application/octet-stream' }); });
  try {
    await page.getByRole('button', { name: 'Preview sources/exact.py', exact: true }).click(); await requested.promise;
    await page.getByRole('button', { name: 'Back to run history', exact: true }).click();
    const response = page.waitForResponse(r => r.url().endsWith('/artifacts/retained-source')); held.release(); await response;
    await expect(preview).toHaveCount(0); await expect(page.getByRole('heading', { name: 'Run history', exact: true })).toBeVisible();
  } finally { held.release(); }
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});
async function shot(page: Page, name: string) {
  await expect(page.getByRole('button',{name:'Profile',exact:true})).toBeVisible();
  await expect(page.getByText('Loading study/model…',{exact:true})).toHaveCount(0);
  await page.evaluate(async()=>{ window.scrollTo(0,0); await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); });
  const original=page.viewportSize()!;
  for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
    await page.setViewportSize(viewport);await page.evaluate(async()=>{window.scrollTo(0,0);await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    for(const footer of await page.locator('dialog[open]>.dialog-footer').all()){const box=(await footer.boundingBox())!;expect(box.y+box.height).toBeLessThanOrEqual(viewport.height);}
    if(name==='ports-dialog') for(const label of await page.locator('dialog[open] .port>label').all()) {
      const aligned=await label.evaluate(el=>{const input=el.querySelector('input')!, range=document.createRange();range.selectNodeContents(el.firstChild!);return {label:range.getBoundingClientRect().x,input:input.getBoundingClientRect().x,margin:getComputedStyle(input).marginTop};});expect(Math.abs(aligned.label-aligned.input)).toBeLessThan(1);expect(aligned.margin).toBe('6px');
    }
    if(name==='configuration-saved') {
      const region=page.getByRole('region',{name:'Saved configuration inputs',exact:true});
      for(const cell of await region.locator('thead th,td:nth-child(3)').all()) expect(await cell.evaluate(el=>getComputedStyle(el).whiteSpace)).toBe('nowrap');
      if(viewport.width===390) expect(await region.evaluate(el=>el.scrollWidth>el.clientWidth)).toBeTruthy();
    }
    if(name==='runs' && viewport.width===1440) {
      const refresh=(await page.getByRole('button',{name:'Refresh run history',exact:true}).boundingBox())!;
      const filter=(await page.getByLabel('Filter loaded runs',{exact:true}).boundingBox())!;
      expect(filter.x-refresh.x-refresh.width).toBeGreaterThanOrEqual(16);
    }
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/'+name+(viewport.width===390?'-compact':'')+'.png',fullPage:viewport.width===390 && !await page.locator("dialog[open]").count()});
  }
  await page.setViewportSize(original);
}
test('approved composition: two complete nodes, contextual details and first-screen configuration inputs', async ({ page }) => {
  const state = await harness(page);
  referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  await expect(page.getByRole('heading', { name: 'Response chain', exact: true })).toBeVisible();
  await expect(components(page)).toBeHidden();
  await expect(details(page).getByRole('tab')).toHaveCount(0);
  await expect(
    details(page).getByRole('heading', { name: 'What it computes', exact: true }),
  ).toBeVisible();
  await expect(details(page).locator('table')).toHaveCount(0);
  const canvas = await page.locator('.graph-viewport').boundingBox();
  for (const item of await page.locator('.diagram-node').all()) {
    const box = await item.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(canvas!.x);
    expect(box!.x + box!.width).toBeLessThanOrEqual(canvas!.x + canvas!.width);
  }
  const panels = await page
    .locator('.connected-main,.connected-inspector')
    .evaluateAll((nodes) => nodes.map((el) => el.getBoundingClientRect().height));
  expect(Math.abs(panels[0] - panels[1])).toBeLessThan(2);
  for (const button of await page.locator('.connected-graph button').all())
    expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await shot(page, 'model');
  await page.getByRole('button', { name: '＋ Component', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Add component', exact: true })).toBeVisible();
  await shot(page, 'new-component-dialog');
  await page.keyboard.press('Escape');
  await openSource(page);
  await shot(page, 'model-source');
  await shot(page, 'model-assumptions');
  await page.getByRole('button', { name: 'Edit ports', exact: true }).click();
  await shot(page, 'ports-dialog');
  await page.keyboard.press('Escape');
  await details(page).getByRole('button', { name: 'Edit', exact: true }).click();
  await shot(page, 'component-version-dialog');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Import', exact: true }).click();
  await shot(page, 'import-dialog');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  await shot(page, 'export-dialog');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Create configuration', exact: true }).click();
  await expect(page.getByLabel('Configuration name', { exact: true })).toBeVisible();
  expect(await page.locator('.connected-views:visible').count()).toBe(0);
  await page.getByLabel('Configuration name', { exact: true }).fill('Baseline');
  await page.getByLabel('Linear response · x value', { exact: true }).fill('2');
  await page.getByLabel('Linear response · z value', { exact: true }).fill('3');
  await page
    .getByLabel('Linear response · x provenance', { exact: true })
    .fill('Manually specified analytical example');
  await page
    .getByLabel('Linear response · z provenance', { exact: true })
    .fill('Manually specified analytical example');
  expect(
    (await page.getByLabel('Linear response · z value', { exact: true }).boundingBox())!.y,
  ).toBeLessThan(800);
  await shot(page, 'configuration');
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  let exportDialog = page.getByRole('dialog', { name: 'Export model and data', exact: true });
  await exportDialog.getByText('Export scope', { exact: true }).click();
  await expect(exportDialog).toContainText(
    'Configuration unsaved explicit input proposal · Run none',
  );
  await expect(exportDialog).not.toContainText('Configuration 40000000');
  await shot(page, 'draft-export-scope');
  await page.keyboard.press('Escape');
  const criteria = page
    .locator('.section-header')
    .filter({ has: page.getByRole('heading', { name: 'Criteria', exact: true }) });
  await criteria.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await page.getByLabel('Criterion 1 operator', { exact: true }).selectOption('eq');
  await shot(page, 'criteria-dialog');
  await page.getByRole('button', { name: 'Remove criterion 1', exact: true }).click();
  await page.keyboard.press('Escape');
  await page
    .locator('.section-header')
    .filter({
      has: page.getByRole('heading', { name: 'Context & supporting evidence', exact: true }),
    })
    .getByRole('button', { name: 'Edit', exact: true })
    .click();
  await shot(page, 'configuration-context-dialog');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Input tools', exact: true }).click();
  await shot(page, 'input-tools-dialog');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  await expect(
    page.getByRole('region', { name: 'Saved configuration', exact: true }),
  ).toBeVisible();
  expect(state.configurations[0].configuration.inputs.map((i: any) => i.value)).toEqual([2, 3]);
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New configuration', exact: true })).toBeVisible();
  await shot(page, 'configuration-list');
  await page.getByRole('button', { name: 'Open configuration', exact: true }).click();
  await expect(
    page.getByRole('region', { name: 'Saved configuration', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.connected-views')).toBeHidden();
  await shot(page, 'configuration-saved');
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  exportDialog = page.getByRole('dialog', { name: 'Export model and data', exact: true });
  await exportDialog.getByText('Export scope', { exact: true }).click();
  await expect(exportDialog).toContainText(
    'Configuration 40000000-0000-4000-8000-000000000001 · Run none',
  );
  await page.keyboard.press('Escape');
  const cfg = state.configurations[0];
  state.runs = [
    {
      run_id: 'run-fixture',
      configuration_revision_id: cfg.configuration.configuration_revision_id,
      state: 'recorded',
    },
  ];
  state.detail = {
    run_id: 'run-fixture',
    state: 'recorded',
    process_state: 'finished',
    exit_status: 0,
    history: {
      errors: [],
      model_snapshot: cfg.model_snapshot,
      configuration: cfg.configuration,
      context: cfg.configuration.context_snapshot,
      evidence: [],
      artifacts: [],
      bundle: null,
      assessment: null,
      results: {
        outputs: [
          {
            target: { instance_id: 'a', port_id: 'u' },
            value: 7,
            units: '',
            availability: 'available',
            reason: null,
          },
          {
            target: { instance_id: 'b', port_id: 'y' },
            value: 49,
            units: '',
            availability: 'available',
            reason: null,
          },
        ],
        criteria: [],
        execution: { state: 'finished', exit_code: 0, message: 'Fixture only' },
        convergence: { state: 'not_applicable' },
        optimization: { termination: 'not_applicable', feasibility: 'not_applicable' },
        completeness: { available: 2, expected: 2, failed: 0, unavailable: 0 },
        applicability: { state: 'unassessed' },
      },
    },
  };
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await expect(
    page
      .getByRole('region', { name: 'Recent configurations', exact: true })
      .getByRole('button', { name: /Baseline/ }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Open run run-fixture', exact: true }),
  ).toBeVisible();
  await shot(page, 'overview');
  await page.getByRole('button', { name: 'Runs', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }),
  ).toBeVisible();
  await shot(page, 'runs');
  await page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Output values' })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Inspect run run-fixture', exact: true }),
  ).toBeHidden();
  await shot(page, 'run-results');
  await expect(
    page
      .locator('.run-heading')
      .getByRole('button', { name: 'Export model and data', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  exportDialog = page.getByRole('dialog', { name: 'Export model and data', exact: true });
  await exportDialog.getByText('Export scope', { exact: true }).click();
  await expect(exportDialog).toContainText(
    'Configuration 40000000-0000-4000-8000-000000000001 · Run run-fixture',
  );
  await shot(page, 'run-export-scope');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Evidence note', exact: true })).toBeVisible();
  await shot(page, 'evidence');
  await page.getByRole('button', { name: 'New note', exact: true }).click();
  await shot(page, 'evidence-dialog');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Open study Scalar model study', exact: true }),
  ).toBeVisible();
  await shot(page, 'home');
  await page.getByRole('button', { name: 'Profile', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Profile', exact: true })).toBeVisible();
  await shot(page, 'profile');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await expect(page.getByLabel('New study name')).toBeVisible();
  await shot(page, 'new-study');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Open study Scalar model study', exact: true }).click();
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Open model Response chain', exact: true }),
  ).toBeVisible();
  await shot(page, 'models-list');
  await page.getByRole('button', { name: 'New model', exact: true }).click();
  await expect(page.getByLabel('New model name')).toBeVisible();
  expect(
    await page
      .getByLabel('Starting model', { exact: true })
      .evaluate((el) => getComputedStyle(el).display),
  ).toBe('block');
  await shot(page, 'new-model');
  expect(state.unknown).toEqual([]);
});

test('tabbed source and dialog port edits retain one guarded atomic proposal', async ({page})=>{
 const state=await harness(page); referenceModel(state); await login(page,`#v=1&study=${sid}&model=${mid}&view=model`);
 await openSource(page);
 const raw=Buffer.from('# exact imported bytes\r\noutputs["u"] = 17\r\n'); await page.getByLabel('Load Python source file').setInputFiles({name:'affine.py',mimeType:'text/x-python',buffer:raw});
 await expect(page.getByText('Source file loaded locally; save to keep it')).toBeVisible();
 await page.getByRole('button',{name:'Details',exact:true}).click();await expect(details(page)).toBeHidden(); await page.getByRole('button',{name:'Details',exact:true}).click();
 await expect(page.getByLabel('Python source',{exact:true})).toHaveValue(raw.toString().replaceAll('\r\n','\n'));
  await page.getByRole('button',{name:'Edit ports',exact:true}).click();
 await page.getByLabel('Port 1 name',{exact:true}).fill('Inlet x'); await page.getByRole('button',{name:'Close Edit ports',exact:true}).click();
 // Component notes are no longer authored in the UI.
await expect(page.getByLabel('Component notes',{exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Home',exact:true}).click(); await page.getByRole('button',{name:'Keep editing',exact:true}).click();
 await expect(page.getByLabel('Python source',{exact:true})).toHaveValue(raw.toString().replaceAll('\r\n','\n'));
 await page.getByRole('button',{name:'Save component',exact:true}).click();await expect(page.getByRole('dialog',{name:'Preview changes'})).toBeVisible();
 const proposal=state.writes.find(w=>w.path.endsWith('/preview'))!.body; const change=proposal.edits.find((e:any)=>e.kind==='revise_definition');
 expect(Buffer.from(change.changes.find((c:any)=>c.kind==='set_source').source.bytes,'base64')).toEqual(raw);
 expect(change.changes).toContainEqual({kind:'update_port',port_id:'x',fields:{name:'Inlet x',code_symbol:'x',units:''}});
 expect(proposal.edits.some((e:any)=>e.kind==='set_annotation')).toBe(false);
 await page.getByRole('button',{name:'Keep editing',exact:true}).click();expect(mutations(state)).toEqual([]);expect(state.unknown).toEqual([]);
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await shot(page,'model-mobile');
});

test('saved configuration submits its exact identity once and uncertain outcome stays guarded', async ({page})=>{
 const state=await harness(page); referenceModel(state);
 const snapshot={...state.model,model_revision_id:version,originating_draft_revision:'draft-r1',digest:'fixture'};
 const c={schema_version:'1',study_id:sid,model_id:mid,configuration_revision_id:'40000000-0000-4000-8000-000000000001',name:'Baseline',model_revision_id:version,inputs:[],criteria:[],context_snapshot:{description:'Retained',boundary:'Original boundary',notes:[]},evidence_snapshots:[],numerical:{mode:'deterministic',derivatives:{method:'none'}},required_capabilities:[],digest:'config-fixture'};
 state.configurations=[{configuration:c,model_snapshot:snapshot}];state.outage=true;
 await login(page,`#v=1&study=${sid}&view=configurations&configuration=40000000-0000-4000-8000-000000000001`);
 const run=page.getByRole('button',{name:'Run this configuration',exact:true});await expect(run).toBeDisabled();
 state.ready=true;await page.getByRole('button',{name:'Check again',exact:true}).click();await expect(run).toBeEnabled();
 state.uncertain=true;await run.click();await expect(page.getByRole('button',{name:'Check original command',exact:true})).toBeVisible();await expect(run).toBeDisabled();
 const writes=state.writes.filter(w=>w.path.endsWith('/runs'));expect(writes).toHaveLength(1);expect(writes[0].body.configuration_revision_id).toBe('40000000-0000-4000-8000-000000000001');
 await page.getByRole('button',{name:'Check original command',exact:true}).click();await expect(run).toBeEnabled();expect(state.writes.filter(w=>w.path.endsWith('/runs'))).toHaveLength(1);expect(state.unknown).toEqual([]);
});

test('study header editing preserves drafts and boundary with equal overview cards', async ({page}) => {
 const state=await harness(page);await login(page);await openStudy(page);
 await expect(page.locator('.brand')).toHaveText('HYPRN MVP');await expect(page.getByRole('button',{name:'Browse models'})).toHaveCount(0);
 const about=page.locator('.study-about'),recent=page.getByRole('region',{name:'Recent runs',exact:true});
 await expect(about).toHaveClass(/hf-panel/);await expect(recent).toHaveClass(/hf-panel/);
 await expect(recent.getByText('This study has no runs yet. Save a configuration, then run the model.')).toBeVisible();
 const a=(await about.boundingBox())!,b=(await recent.boundingBox())!;
 expect(Math.abs(a.width-b.width)).toBeLessThan(2);expect(Math.abs(a.height-b.height)).toBeLessThan(2);expect(a.y).toBe(b.y);expect((await about.getByRole('heading').boundingBox())!.y).toBe((await recent.getByRole('heading').boundingBox())!.y);
 const edit=about.getByRole('button',{name:'Edit',exact:true});await edit.focus();await page.keyboard.press('Enter');
 const editor=page.getByRole('dialog',{name:'Edit study',exact:true});await expect(editor).toBeVisible();
 expect(await editor.getByLabel('Study name',{exact:true}).evaluate(el=>getComputedStyle(el).marginTop)).toBe('6px');expect(await editor.locator('.form-stack').evaluate(el=>getComputedStyle(el).rowGap)).toBe('16px');
 await editor.getByLabel('Description',{exact:true}).fill('Kept local description');await page.keyboard.press('Escape');await expect(edit).toBeFocused();
 await edit.click();await expect(editor.getByLabel('Description',{exact:true})).toHaveValue('Kept local description');await editor.getByRole('button',{name:'Done',exact:true}).click();
 await page.getByRole('button',{name:'Home',exact:true}).click();await expect(page.getByRole('dialog',{name:'Unsaved changes'})).toBeVisible();await page.getByRole('button',{name:'Keep editing',exact:true}).click();
 await edit.click();await shot(page,'study-edit');await page.emulateMedia({colorScheme:'dark'});await shot(page,'study-edit-dark');await page.emulateMedia({colorScheme:'light'});await editor.getByRole('button',{name:'Save study context',exact:true}).click();await expect(editor.getByText('Study saved',{exact:true})).toBeVisible();
 expect(state.writes.find(w=>w.method==='PATCH')!.body.boundary).toBe('Retained boundary must survive');await editor.getByRole('button',{name:'Done',exact:true}).click();
 await shot(page,'overview-equal');await page.emulateMedia({colorScheme:'dark'});await shot(page,'overview-equal-dark');await page.emulateMedia({colorScheme:'light'});await page.setViewportSize({width:390,height:844});
 expect((await recent.boundingBox())!.y).toBeGreaterThan((await about.boundingBox())!.y);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await shot(page,'overview-equal-mobile');
 await page.setViewportSize({width:1440,height:1000});await edit.click();await editor.getByLabel('Description',{exact:true}).fill('Unsaved for guarded View all');await editor.getByRole('button',{name:'Done',exact:true}).click();
 await recent.getByRole('button',{name:'View all runs',exact:true}).click();await expect(page.getByRole('dialog',{name:'Unsaved changes'})).toBeVisible();await page.getByRole('button',{name:'Keep editing',exact:true}).click();
 await recentCollection(page,'configurations').getByRole('button',{name:'View all configurations',exact:true}).click();await expect(page.getByRole('dialog',{name:'Unsaved changes'})).toBeVisible();await page.getByRole('button',{name:'Discard changes',exact:true}).click();await expect(page.getByRole('button',{name:'Configurations',exact:true})).toHaveAttribute('aria-current','page');
 expect(state.writes.filter(w=>w.method==='PATCH')).toHaveLength(1);expect(state.unknown).toEqual([]);
});

function modelPackage() {
 const digest=(value:unknown)=>createHash('sha256').update(canonical(value)).digest('hex');
 const record={...modelFixture(),model_id:'20000000-0000-4000-8000-000000000002',model_revision_id:version};
 const revision={...record,digest:digest(record)};
 const body={schema_version:'1',model_id:record.model_id,model_revision_id:version,revisions:[revision],files:[],required_capabilities:[]};
 return {...body,digest:digest(body)};
}

const recentCollection = (page: Page, collection: string) => page.getByRole('region', { name: 'Recent ' + collection, exact: true });
for (const collection of ['configurations', 'runs']) test(`Foundry Overview ${collection} failure retries independently without writes`, async ({ page }) => {
  const state = await harness(page); let fail = true;
  await page.route(`**/api/1/studies/${sid}/${collection}`, route => fail
    ? route.fulfill({ status: 500, json: { error: { code: 'internal_error', message: 'Controlled collection failure', fields: [], outcome: 'unchanged' } } })
    : route.fulfill({ json: { schema_version: '1', data: [], next_cursor: null } }));
  await login(page); await openStudy(page);
  const failed = recentCollection(page, collection), healthy = recentCollection(page, collection === 'runs' ? 'configurations' : 'runs');
  await expect(failed.getByRole('alert')).toContainText('Could not load recent ' + collection);
  await expect(healthy).toContainText(collection === 'runs' ? 'No saved configurations' : 'This study has no runs yet');
  await expect(failed).not.toContainText(collection === 'runs' ? 'This study has no runs yet' : 'No saved configurations');
  await shot(page, 'overview-' + collection + '-error');
  fail = false; await failed.getByRole('button', { name: 'Retry recent ' + collection }).click();
  await expect(failed.getByRole('alert')).toHaveCount(0);
  await expect(failed).toContainText(collection === 'runs' ? 'This study has no runs yet' : 'No saved configurations');
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});

test('Foundry Overview pending records cannot follow a study change', async ({ page }) => {
  const state = await harness(page), held = latch();
  state.studies.push({ ...state.studies[0], study_id: sid2, name: 'Empty second study' });
  await page.route(`**/api/1/studies/${sid}/runs`, async route => { await held.promise; await route.fulfill({ json: { schema_version: '1', data: [{ run_id: 'obsolete-run', configuration_revision_id: 'obsolete-config', state: 'recorded' }], next_cursor: null } }); });
  try {
    await login(page); await openStudy(page);
    await expect(recentCollection(page, 'runs').getByRole('status')).toHaveText('Loading recent runs…');
    await shot(page, 'overview-loading');
    await page.getByRole('button', { name: 'Home', exact: true }).click();
    await page.getByRole('button', { name: 'Open study Empty second study' }).click();
    await expect(recentCollection(page, 'runs')).toContainText('This study has no runs yet');
    held.release(); await page.unrouteAll({ behavior: 'wait' });
    await expect(recentCollection(page, 'runs')).not.toContainText('obsolete');
    await expect(recentCollection(page, 'configurations')).toContainText('No saved configurations');
    await shot(page, 'overview-empty'); expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
  } finally { held.release(); }
});

test('Foundry Overview authorization loss ignores a late successful collection', async ({ page }) => {
  const state = await harness(page), auth = latch(), held = latch();
  await page.route(`**/api/1/studies/${sid}/configurations`, async route => { await auth.promise; await route.fulfill({ status: 401, json: { error: { code: 'unauthenticated', message: 'Session expired', fields: [], outcome: 'unchanged' } } }); });
  await page.route(`**/api/1/studies/${sid}/runs`, async route => { await held.promise; await route.fulfill({ json: { schema_version: '1', data: [{ run_id: 'obsolete-run', state: 'recorded' }], next_cursor: null } }); });
  try {
    await login(page); await openStudy(page); await expect(recentCollection(page, 'runs').getByRole('status')).toBeVisible();
    auth.release(); await expect(page.getByRole('heading', { name: 'Sign in to HYPRN MVP' })).toBeVisible();
    held.release(); await page.unrouteAll({ behavior: 'wait' });
    await expect(recentCollection(page, 'runs')).toHaveCount(0); await expect(page.getByText('obsolete-run')).toHaveCount(0);
    expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
  } finally { auth.release(); held.release(); }
});

test('Foundry Overview latest five follow public pages and request states stay truthful', async ({ page }) => {
  const state = await harness(page); referenceModel(state);
  const ids = ['ffffffff', 'dddddddd', 'bbbbbbbb', '99999999', '77777777', '55555555', '33333333'];
  const observed: string[] = [];
  for (const collection of ['runs', 'configurations']) await page.route(`**/api/1/studies/${sid}/${collection}*`, async route => {
    const url = new URL(route.request().url()); if (url.pathname !== `/api/1/studies/${sid}/${collection}`) return route.fallback();
    const start = url.searchParams.has('cursor') ? 4 : 0; observed.push(collection + ':' + (url.searchParams.get('cursor') ?? 'first'));
    const data = ids.slice(start, start + 4).map((id, i) => collection === 'runs'
      ? { run_id: id, configuration_revision_id: 'config-' + id, state: ['accepted_run', 'prepared', 'preparation_failed', 'dispatching', 'uncertain', 'recorded', 'recorded'][start + i] }
      : { configuration: { configuration_revision_id: id, name: 'Collection fixture ' + (start + i), model_id: mid, model_revision_id: version } });
    await route.fulfill({ json: { schema_version: '1', data, next_cursor: start === 0 ? 'page-two' : null } });
  });
  await page.route(`**/api/1/studies/${sid}/runs/*`, route => { const id = new URL(route.request().url()).pathname.split('/').at(-1)!; const i = ids.indexOf(id); return route.fulfill({json:{schema_version:'1',data:{run_id:id, state:['accepted_run','prepared','preparation_failed','dispatching','uncertain','recorded','recorded'][i], history:null}}}); });
  await login(page, `#v=1&study=${sid}&view=overview`);
  await expect(recentCollection(page, 'configurations').locator('li button')).toHaveText(['Collection fixture 6', 'Collection fixture 5', 'Collection fixture 4', 'Collection fixture 3', 'Collection fixture 2']);
  await expect(recentCollection(page, 'runs').locator('li button')).toHaveText(ids.slice(-5).reverse().map(id => 'Run ' + id));
  for (const collection of ['runs', 'configurations']) { expect(observed).toContain(collection + ':page-two'); await expect(recentCollection(page, collection)).toContainText('5 of 7 ' + collection); }
  await expect(recentCollection(page, 'runs').locator('.hf-tag--ok')).toHaveCount(0);
  await expect(recentCollection(page, 'runs').locator('.hf-tag--warning')).toContainText('Needs review');
  await expect(recentCollection(page, 'runs').locator('.hf-tag--alarm')).toContainText('Preparation failed');
  await shot(page, 'overview-paged');
  await page.emulateMedia({ colorScheme: 'dark' }); await shot(page, 'overview-paged-dark');
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});
test('resource header import and export preserve scope, previews, exact bytes and errors',async({page})=>{
  const state = await harness(page);
  await openModel(page);
  const header = page.locator('.model-heading');
  await expect(header.getByRole('button', { name: 'Import', exact: true })).toBeVisible();
  await expect(
    header.getByRole('button', { name: 'Export model and data', exact: true }),
  ).toBeVisible();
  await expect(page.locator('summary').filter({ hasText: 'Import and export' })).toHaveCount(0);
  const launch = header.getByRole('button', { name: 'Export model and data', exact: true });
  await launch.focus();
  await page.keyboard.press('Enter');
  const exp = page.getByRole('dialog', { name: 'Export model and data', exact: true });
  await expect(
    exp.getByRole('button', { name: 'Download portable model record', exact: true }),
  ).toBeDisabled();
  await exp.getByText('Source files', { exact: true }).click();
  const download = page.waitForEvent('download');
  await exp.getByRole('button', { name: /Download source/ }).click();
  const bytes = await readFile((await (await download).path())!);
  expect(bytes).toEqual(Buffer.from(source));
  await page.keyboard.press('Escape');
  await expect(launch).toBeFocused();
  await header.getByRole('button', { name: 'Import', exact: true }).click();
  const imp = page.getByRole('dialog', { name: 'Import', exact: true });
  await imp
    .getByLabel('Portable model record file')
    .setInputFiles({
      name: 'package.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(modelPackage())),
    });
  await imp.getByRole('button', { name: 'Preview model import', exact: true }).click();
  await expect(imp.getByRole('region', { name: 'Model import preview' })).toBeVisible();
  await imp.getByRole('button', { name: 'Done', exact: true }).click();
  await header.getByRole('button', { name: 'Import', exact: true }).click();
  await expect(imp.getByRole('region', { name: 'Model import preview' })).toBeVisible();
  await imp.getByRole('button', { name: 'Import model', exact: true }).click();
  await expect(imp.getByRole('alert')).toContainText(
    'This model changed. Your edits are preserved',
  );
  await imp.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText(
    'This model changed. Your edits are preserved',
  );
  expect(state.writes.filter((w) => w.path.endsWith('/model-imports'))).toHaveLength(1);
  expect(
    state.writes.filter((w) => w.path.endsWith('/model-imports'))[0].body.expected_revision,
  ).toBe('study-r1');
  await page.getByLabel('Model version', { exact: true }).selectOption(version);
  await page.getByRole('button', { name: 'Import', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Model import preview' })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  await expect(
    exp.getByRole('button', { name: 'Download portable model record', exact: true }),
  ).toBeEnabled();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Configurations', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Import', exact: true })).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Export model and data', exact: true }),
  ).toHaveCount(0);
  expect(state.unknown).toEqual([]);
});

test('import confirmation participates in dirty navigation and replacing a package invalidates preview',async({page})=>{
 const state=await harness(page);await openModel(page);await page.getByLabel('Component assumptions',{exact:true}).fill('Keep this local draft');
 await page.getByRole('button',{name:'Import',exact:true}).click();const imp=page.getByRole('dialog',{name:'Import',exact:true});
 await imp.getByLabel('Portable model record file').setInputFiles({name:'package.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(modelPackage()))});await imp.getByRole('button',{name:'Preview model import',exact:true}).click();await expect(imp.getByRole('region',{name:'Model import preview'})).toBeVisible();
 await imp.getByRole('button',{name:'Import model',exact:true}).click();await page.getByRole('dialog',{name:'Unsaved changes',exact:true}).getByRole('button',{name:'Keep editing',exact:true}).click();expect(state.writes).toEqual([]);
 await imp.getByLabel('Portable model record file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('{}')});await expect(imp.getByRole('region',{name:'Model import preview'})).toHaveCount(0);await imp.getByRole('button',{name:'Preview model import',exact:true}).click();await expect(imp.getByRole('alert')).toContainText('Unsupported or invalid model package');await page.keyboard.press('Escape');await expect(page.getByLabel('Component assumptions',{exact:true})).toHaveValue('Keep this local draft');expect(state.writes).toEqual([]);expect(state.unknown).toEqual([]);
});

test('Foundry foundation: approved dimensions, Home surfaces and themed account controls', async ({page}) => {
  await harness(page); await login(page);
  await expect(page.locator('.home-page .hf-panel')).toBeVisible();
  const dimensions = await page.evaluate(() => {
    const css = getComputedStyle(document.documentElement);
    return ['appbar-height','page-gutter','panel-outline','panel-inspector'].map(key => css.getPropertyValue('--'+key).trim());
  });
  expect(dimensions).toEqual(['66px','28px','190px','350px']);
  await expect(page.getByRole('button',{name:'New study',exact:true})).toHaveClass(/hf-btn--primary/);
});

test('Foundry shell remains legible in both themes and dialogs restore focus with drafts mounted', async ({page}) => {
  const state = await harness(page); referenceModel(state);
  await page.emulateMedia({colorScheme:'light',reducedMotion:'reduce'});
  await page.goto(origin + '/ui/');
  await page.getByLabel('Username',{exact:true}).focus();
  await expect(page.getByLabel('Username',{exact:true})).toBeFocused();
  await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/login-light.png'});
  await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});
  await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/login-dark.png'});
  await login(page);
  for (const theme of ['light','dark'] as const) {
    await page.emulateMedia({colorScheme:theme,reducedMotion:'reduce'});
    await page.getByRole('button',{name:'Home',exact:true}).click();
    await expect(page.locator('.study-row')).toHaveCount(1);
    const contrast = await page.locator('.brand, .home-page h1, .study-row h2, .study-row p, .catalogue-toolbar p, .home-page .hf-btn--primary').evaluateAll(elements => elements.map(el => {
      const rgb = (color:string) => (color.match(/[0-9.]+/g) ?? []).slice(0,3).map(Number).map(v => {const c=v/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;});
      const luminance = (color:string) => {const c=rgb(color);return .2126*c[0]+.7152*c[1]+.0722*c[2];};
      let node:Element|null=el, background=''; while(node) {background=getComputedStyle(node).backgroundColor;if(background!=='rgba(0, 0, 0, 0)' && background!=='transparent')break;node=node.parentElement;}
      const a=luminance(getComputedStyle(el).color),b=luminance(background);
      return {text:el.textContent,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
    }));
    for(const item of contrast) expect(item.ratio,item.text ?? '').toBeGreaterThanOrEqual(4.5);
    const create=page.getByRole('button',{name:'New study',exact:true});
    await create.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab'); await expect(create).toBeFocused(); expect(await create.evaluate(el=>getComputedStyle(el).outlineWidth)).toBe('2px');
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/home-'+theme+'.png'});
    await create.click(); await expect(page.getByLabel('New study name')).toBeVisible();
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/new-study-'+theme+'.png'});
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await page.getByRole('button',{name:'Profile',exact:true}).click();
    await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/profile-'+theme+'.png'});
    await page.getByRole('button',{name:'Home',exact:true}).click();
    await page.getByRole('button',{name:'Open study Scalar model study'}).click();
    await page.getByRole('button',{name:'Models',exact:true}).click();
    await expect(page.getByRole('button',{name:'New model',exact:true})).toBeVisible();
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/models-list-'+theme+'.png'});
    await page.getByRole('button',{name:'New model',exact:true}).click();
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/new-model-'+theme+'.png'});
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await page.getByRole('button',{name:'Overview',exact:true}).click();
    const edit=page.getByRole('button',{name:'Edit',exact:true});
    await edit.click(); await page.getByLabel('Description',{exact:true}).fill('Preserved draft');
    await page.getByRole('button',{name:'Close Edit study',exact:true}).click();
    await expect(edit).toBeFocused();
    await edit.click(); await expect(page.getByLabel('Description',{exact:true})).toHaveValue('Preserved draft');
    await page.getByRole('button',{name:'Close Edit study',exact:true}).click();
    await page.getByRole('button',{name:'Home',exact:true}).click();
    await expect(page.getByRole('dialog',{name:'Unsaved changes'})).toBeVisible();
    await page.screenshot({path:process.env.HYPRN_MVP_UI_EVIDENCE_ROOT+'/dirty-dialog-'+theme+'.png'});
    await page.getByRole('button',{name:'Keep editing',exact:true}).click();
    await expect(page.getByRole('button',{name:'Home',exact:true})).toBeFocused();
    await page.getByRole('button',{name:'Home',exact:true}).click();
    await page.getByRole('button',{name:'Discard changes',exact:true}).click();
  }
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Foundry model light and dark projections, details and historical source are reviewable', async ({ page }) => {
  const state = await harness(page); referenceModel(state);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await login(page, '#v=1&study=' + sid + '&model=' + mid + '&view=model');
  for (const theme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: theme as 'light' | 'dark' });
    const capture = async (name: string) => page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/model-' + name + '-' + theme + '.png' });
    await page.getByRole('tab', { name: 'Graph', exact: true }).click();
    await capture('graph');
    await page.getByRole('button', { name: 'Components', exact: true }).click(); await capture('components');
    await page.getByRole('button', { name: 'Details', exact: true }).click(); await capture('without-details');
    await page.getByRole('button', { name: 'Details', exact: true }).click();
    await page.getByRole('button', { name: 'Components', exact: true }).click();
    for (const view of ['XDSM', 'Graph']) { await page.getByRole('tab', { name: view, exact: true }).click(); await capture(view.toLowerCase()); }
    for (const tab of ['Source', 'Assumptions']) { if (tab === 'Source') await openSource(page); await capture(tab.toLowerCase()); }
    await page.getByLabel('Component assumptions', { exact: true }).fill('Fixture assumption retained locally');
    await page.getByRole('button', { name: 'Save component', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Apply changes', exact: true })).toBeEnabled(); await capture('preview');
    await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
    await page.getByLabel('Component assumptions', { exact: true }).fill('');
    await page.getByLabel('Model version', { exact: true }).selectOption(version);
    await details(page).getByRole('button', { name: 'View source', exact: true }).click();
    await expect(page.getByLabel('Read-only authored source')).toBeVisible(); await capture('historical-source'); await page.keyboard.press('Escape');
    await page.getByLabel('Model version', { exact: true }).selectOption('draft');
  }
  expect(state.writes.filter(w => !w.path.endsWith('/preview'))).toEqual([]); expect(state.unknown).toEqual([]);
});

test('Foundry graph export retains every node and port as inert SVG slots', async ({ page }) => {
  const state = await harness(page);
  referenceModel(state);
  await login(page, '#v=1&study=' + sid + '&model=' + mid + '&view=model');
  await page.getByRole('button', { name: 'Export model and data', exact: true }).click();
  const downloading = page.waitForEvent('download');
  await page.getByRole('button', { name: /SVG/ }).click();
  const download = await downloading,
    path = await download.path();
  if (!path) throw new Error('Missing fixture download');
  const svg = await readFile(path, 'utf8');
  expect(svg).toContain('Linear response');
  expect(svg).toContain('Squared response');
  for (const port of ['→ x', '→ z', 'u →', '→ u', 'y →']) expect(svg).toContain(port);
  expect(svg).not.toContain('foreignObject');
  expect(svg).not.toContain('<button');
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Foundry configuration fields preserve blank zero negative and immutable saved inputs', async ({ page }) => {
 const state=await harness(page);referenceModel(state);await login(page,`#v=1&study=${sid}&model=${mid}&view=model`);
 await page.getByRole('button',{name:'Create configuration',exact:true}).click();
 const input=page.getByLabel('Linear response · x value',{exact:true}), other=page.getByLabel('Linear response · z value',{exact:true});
 await expect(page.locator('#configuration .hf-field--unassigned')).toHaveCount(2);
 await shot(page,'foundry-configuration-new');
 await page.getByLabel('Configuration name',{exact:true}).fill('Explicit inputs');
 await input.fill('0');await other.fill('-3');
 for (const key of ['x','z']) await page.getByLabel('Linear response · '+key+' provenance',{exact:true}).fill('Explicit fixture value');
 await expect(input).toHaveValue('0');await expect(page.getByText('Connected inputs are supplied by their producers. Blank values are missing; zero is an explicit value.',{exact:true})).toBeVisible();
 expect((await other.boundingBox())!.y).toBeLessThan(800);
 await page.getByRole('button',{name:'Save configuration',exact:true}).click();
 await expect(page.getByRole('region',{name:'Saved configuration',exact:true})).toBeVisible();
 expect(state.configurations[0].configuration.inputs.map((i:any)=>i.value)).toEqual([0,-3]);
 expect(state.writes.filter(w=>w.path.endsWith('/runs'))).toHaveLength(0);
 await page.getByRole('button',{name:'Configurations',exact:true}).click();
 await page.getByRole('button',{name:'Open configuration',exact:true}).click();
 const saved=page.getByRole('region',{name:'Saved configuration',exact:true});
 await expect(saved.locator('.hf-field--readonly')).toHaveCount(2);
 await expect(saved.locator('input')).toHaveCount(0);
 await expect(saved.getByText('Checks on calculated outputs.')).toHaveCount(0);
 for (const theme of ['light','dark']) {
  await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
  await shot(page,'foundry-configuration-saved-'+theme);
 }
 expect(state.unknown).toEqual([]);
});

test('Foundry configuration rejected paste and incompatible units preserve explicit proposal', async ({page})=>{
 const state=await harness(page);referenceModel(state);await login(page,`#v=1&study=${sid}&model=${mid}&view=model`);
 await page.getByRole('button',{name:'Create configuration',exact:true}).click();
 await page.getByLabel('Configuration name',{exact:true}).fill('Explicit proposal');
 await page.getByRole('button',{name:'Input tools',exact:true}).click();
 const paste='instance_id\tport_id\tvalue\tunits\tprovenance\na\tx\t0\t\tmanual\na\tx\t3\t\tduplicate';
 await page.getByRole('textbox',{name:'Input assignment rows',exact:true}).fill(paste);
 await page.getByRole('button',{name:'Preview input assignments',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'Input assignment rows',exact:true})).toHaveValue(paste);
 await expect(page.getByRole('dialog',{name:'Input assignment preview',exact:true})).toBeHidden();
 await shot(page,'foundry-configuration-rejected-paste');
 await page.getByRole('textbox',{name:'Input assignment rows',exact:true}).fill('');await page.keyboard.press('Escape');
 for(const [key,value] of [['x','0'],['z','-3']]) {
  await page.getByLabel('Linear response · '+key+' value',{exact:true}).fill(value);
  await page.getByLabel('Linear response · '+key+' provenance',{exact:true}).fill('Original provenance');
 }
 await page.getByLabel('Linear response · x units',{exact:true}).fill('kg');
 await page.route('**/configurations/preview',route=>route.fulfill({json:{schema_version:'1',data:{compatible:false,diagnostics:[{path:'inputs.0.units',message:'Incompatible kg; declared dimensionless. No conversion applied.'}]}}}));
 await page.getByRole('button',{name:'Save configuration',exact:true}).click();
 await expect(page.getByText('inputs.0.units: Incompatible kg; declared dimensionless. No conversion applied.',{exact:true}).first()).toBeVisible();
 await expect(page.getByLabel('Linear response · x units',{exact:true})).toHaveValue('kg');
 await expect(page.getByLabel('Linear response · x value',{exact:true})).toHaveValue('0');
 await shot(page,'foundry-configuration-invalid');
 await page.getByRole('region',{name:'Linear response · x evidence',exact:true}).getByRole('button',{name:'Add evidence',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Add evidence to Linear response · x evidence',exact:true})).toBeVisible();
 await shot(page,'foundry-configuration-evidence-open');
 expect(state.configurations).toEqual([]);expect(state.writes.filter(w=>w.path.endsWith('/runs'))).toEqual([]);expect(state.unknown).toEqual([]);
});

test('Foundry configuration stale preview retains pin and uncertain save reconciles original command',async({page})=>{
 const state=await harness(page);referenceModel(state);await login(page,`#v=1&study=${sid}&model=${mid}&view=model`);
 await page.getByRole('button',{name:'Create configuration',exact:true}).click();
 await page.getByLabel('Configuration name',{exact:true}).fill('Pinned proposal');
 for(const key of ['x','z']){
  await page.getByLabel('Linear response · '+key+' value',{exact:true}).fill('0');
  await page.getByLabel('Linear response · '+key+' provenance',{exact:true}).fill('Original provenance');
 }
 let stale=true, candidate:any;
 await page.route('**/configurations/preview',async route=>{
  candidate=route.request().postDataJSON();
  return stale?route.fulfill({status:409,json:{error:{code:'stale_revision',message:'Model pin changed; proposal retained',fields:[],outcome:'unchanged'}}}):route.fulfill({json:{schema_version:'1',data:{compatible:true,diagnostics:[]}}});
 });
 await page.getByRole('button',{name:'Save configuration',exact:true}).click();
 await expect(page.getByText('This model changed. Your edits are preserved; review the current revision.',{exact:true}).first()).toBeVisible();
 expect(candidate.model_revision_id).toBe(version);expect(state.configurations).toEqual([]);
 await expect(page.getByLabel('Linear response · x value',{exact:true})).toHaveValue('0');
 stale=false;let command:any,attempts=0;
 await page.route(`**/studies/${sid}/configurations`,route=>{
  if(route.request().method()!=='POST')return route.fallback();
  attempts++;command=route.request().postDataJSON();return route.abort('failed');
 });
 await page.getByRole('button',{name:'Save configuration',exact:true}).click();
 await expect(page.getByRole('button',{name:'Check original command',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeDisabled();
 const held=latch();let receiptPath='';
 await page.route('**/commands/**',async route=>{
  receiptPath=route.request().url();await held.promise;
  const data={state:'rejected',result:null,recovery:'refused'};
  return route.fulfill({json:{schema_version:'1',data}});
 });
 await page.getByRole('button',{name:'Check original command',exact:true}).click();
 await expect(page.getByRole('button',{name:'Check original command',exact:true})).toBeDisabled();
 await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Pinned proposal');
 held.release();await expect(page.getByRole('button',{name:'Check original command',exact:true})).toHaveCount(0);
 expect(receiptPath).toContain(command.command_id);expect(command.configuration.model_revision_id).toBe(version);expect(attempts).toBe(1);
 expect(state.writes.filter(w=>w.path.endsWith('/runs'))).toEqual([]);expect(state.unknown).toEqual([]);
});

/** Reference images of the design system (design-system/reference/), kept unchanged.
 * Real-screen snapshots are separate, off-cloud, and never overwrite these reference PNGs. */
const foundryReference = fileURLToPath(new URL('../../design-system/reference', import.meta.url));

test('reviewed Foundry real screens retain light and dark visual regressions and readable states', async ({ page }, testInfo) => {
  test.setTimeout(90000);
  // A visual comparison without its reference images fails; it is never skipped.
  expect(existsSync(foundryReference), 'reference absent: design-system/reference').toBe(true);
  const state = await harness(page); runFixture(state);
  for (const input of state.detail.history.configuration.inputs) input.provenance.evidence_version_ids = [];
    state.configurations = [{ configuration: state.detail.history.configuration, model_snapshot: state.detail.history.model_snapshot }];
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await login(page);
  const button = (name: string) => page.getByRole('button', { name, exact: true });
  const audit: unknown[] = [];
  async function capture(name: string, reference?: string) {
    if (reference) {
      const bytes = await readFile(resolve(foundryReference, reference));
      expect(bytes.subarray(1, 4).toString()).toBe('PNG');
      testInfo.annotations.push({ type: 'unchanged-reference', description: reference + ' SHA256 ' + createHash('sha256').update(bytes).digest('hex') });
    }
    const contrast = await page.locator('h1,h2,h3,p,td,label,.hf-tag,.hf-source-chip,.hf-btn:not(:disabled)').evaluateAll(elements => elements.filter(el => {
      const box = el.getBoundingClientRect();
      return box.width && box.height && box.bottom > 0 && box.top < innerHeight && getComputedStyle(el).visibility !== 'hidden' && el.textContent?.trim() && !el.closest('[inert]');
    }).map(el => {
      const rgb = (color: string) => (color.match(/[0-9.]+/g) ?? []).slice(0, 3).map(Number).map(v => { const c = v / 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; });
      const luminance = (color: string) => { const c = rgb(color); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; };
      let node: Element | null = el, background = ''; while (node) { background = getComputedStyle(node).backgroundColor; if (background !== 'rgba(0, 0, 0, 0)' && background !== 'transparent') break; node = node.parentElement; }
      const a = luminance(getComputedStyle(el).color), b = luminance(background);
      return { text: el.textContent?.trim().slice(0, 90), ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) };
    }));
    for (const item of contrast) expect(item.ratio, name + ': ' + item.text).toBeGreaterThanOrEqual(4.5);
    for (const tag of await page.locator('.hf-tag:visible').all()) {
      await expect(tag.locator('.hf-mark')).toHaveCount(1);
      expect((await tag.innerText()).trim()).not.toBe('');
    }
    audit.push({ name, contrast });
    await page.screenshot({ path: process.env.HYPRN_MVP_UI_EVIDENCE_ROOT + '/' + name + '.png' });
    await expect(page).toHaveScreenshot(name + '.png', { animations: 'disabled' });
  }
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await button('Home').click(); await expect(page.locator('.study-row')).toHaveCount(1);
    await capture('reviewed-home-' + theme, 'home.png');
    await button('Profile').click(); await capture('reviewed-profile-' + theme);
    await button('Home').click(); await button('Open study Scalar model study').click();
    await expect(page.getByRole('heading', { name: 'About this study' })).toBeVisible();
    await capture('reviewed-overview-' + theme, 'overview.png');
    await button('Edit').click(); await capture('reviewed-study-dialog-' + theme); await page.keyboard.press('Escape');
    await button('Models').click(); await capture('reviewed-model-list-' + theme);
    await page.goto(origin + '/ui/#v=1&study=' + sid + '&model=' + mid + '&view=model');
    await expect(page.getByRole('heading', { name: 'Response chain', exact: true })).toBeVisible();
    for (const view of ['Graph', 'XDSM']) {
      await page.getByRole('tab', { name: view, exact: true }).click();
      await capture('reviewed-model-' + view.toLowerCase() + '-' + theme, view === 'Graph' ? (theme === 'dark' ? 'model-dark.png' : 'model.png') : undefined);
    }
    for (const name of ['Source', 'Assumptions', 'Ports']) {
      if (name === 'Source') await openSource(page);
      await capture('reviewed-details-' + name.toLowerCase() + '-' + theme);
    }
    await button('Configurations').click(); await capture('reviewed-configurations-' + theme);
    await button('Open configuration').click();
    await expect(page.getByRole('region', { name: 'Saved configuration inputs' })).toBeVisible();
    await capture('reviewed-configuration-saved-' + theme, 'configuration.png');
    await button('Runs').click(); await capture('reviewed-runs-' + theme, 'runs.png');
    await button('Inspect run run-fixture').click();
    for (const name of ['Results', 'Model & inputs', 'Evidence & files']) {
      await page.getByRole('tab', { name, exact: true }).click();
      await capture('reviewed-run-' + name.split(' ')[0].toLowerCase() + '-' + theme);
    }
    await button('Evidence').click(); await expect(page.locator('.evidence-record')).toHaveCount(1);
    await capture('reviewed-evidence-' + theme);
  }
  await testInfo.attach('actual-state-contrast', { body: JSON.stringify(audit, null, 2), contentType: 'application/json' });
  expect(state.unknown).toEqual([]); expect(state.writes).toEqual([]);
});
