import { test, expect, chromium, type Page } from 'playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromiumExecutable } from './support/browser';

async function openRetained(page: Page, caller: 'saved' | 'run') {
  const props = await (await page.request.get('/fixture')).json();
  const query=new URLSearchParams({v:'1',study:props.study.study_id,view:caller==='saved'?'configurations':'runs',...(caller==='saved'?{configuration:props.saved.configuration.configuration_revision_id}:{run:props.linked_run})});
  await page.goto('/ui/?retained='+caller+'#'+query);
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  if(caller==='run')await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  await expect(page.getByRole('button',{name:'View source result',exact:true})).toBeVisible();
  return props;
}

test('@retained source inspection keeps unsaved form and exact binding',async({page})=>{
  const props=await openRetained(page,'saved');
  // Copy's current-model prerequisite is an explicit transport double here;
  // the two retained-view cases run with the model service fully unavailable.
  await page.route(`**/models/${props.model.model_id}`,route=>route.fulfill({json:{schema_version:'1',data:props.model}}));
  await page.route('**/configurations/preview',route=>route.fulfill({status:503,json:{error:{code:'backend_unavailable',message:'Modeling unavailable; edits are kept.',fields:[],outcome:'unchanged'}}}));
  await page.getByRole('button',{name:'Copy configuration to draft',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Unsaved engineer notes');
  const literal=page.locator('input[data-input-key]:not([readonly])').first();await literal.fill('9.123456');
  await page.getByRole('button',{name:'View source result',exact:true}).click();
  await expect(page.locator(`[data-source-output="${props.source.source_output.instance_id}/${props.source.source_output.port_id}"]`)).toBeFocused();
  await page.getByRole('button',{name:'Return to configuration',exact:true}).click();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Unsaved engineer notes');
  await expect(literal).toHaveValue('9.123456');
  await expect(page.locator('input[data-input-key][readonly]')).toHaveValue('150');
});

test('@retained genuine 200 percent shared records and source focus',async({baseURL})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const extension=join(root,'artifacts/retained-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Retained view zoom',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/retained-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');let tabId:number|undefined;
  try {
    const page=context.pages()[0]??await context.newPage();await openRetained(page,'saved');
    const cdp=await context.newCDPSession(page);const info=await cdp.send('Browser.getWindowForTarget');
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});
    // Native content geometry, with no viewport emulation.
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    tabId=await worker.evaluate(async(url)=>{const tabs=await (globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tabId);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId)).toBe(2);
    expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    for(const caller of ['saved','run'] as const){
      if(caller==='run')await openRetained(page,'run');
      await page.evaluate(()=>document.documentElement.dataset.theme='dark');
      const action=page.getByRole('button',{name:'View source result',exact:true});await action.focus();
      await expect(action).toBeFocused();await action.scrollIntoViewIfNeeded();
      await page.evaluate(()=>new Promise<void>(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r()))));
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
      await writeFile(join(root,`evidence/${caller}-binding-200.png`),Buffer.from(shot.data,'base64'));
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
      await page.keyboard.press('Enter');
      await expect(page.locator('[data-source-output]:focus')).toHaveCount(1);
    }
    await writeFile(join(root,'evidence/retained-zoom.json'),JSON.stringify({factor:2,viewport:page.viewportSize(),geometry:await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio}))}));
  } finally {if(tabId!==undefined)await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tabId);await context.close();}
});

for (const caller of ['saved', 'run'] as const) {
  test(`@retained ${caller} shared binding navigates exact source and returns offline`, async ({ page }) => {
    const props = await (await page.request.get('/fixture')).json();
    const query = new URLSearchParams({v:'1',study:props.study.study_id,view:caller==='saved'?'configurations':'runs',
      ...(caller==='saved'?{configuration:props.saved.configuration.configuration_revision_id}:{run:props.linked_run})});
    await page.goto('/ui/#'+query);
    await page.getByLabel('Username', {exact:true}).fill('owner');
    await page.getByLabel('Password', {exact:true}).fill('correct horse battery staple');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    if(caller==='run') await page.getByRole('tab',{name:'Configuration',exact:true}).click();
    const source=page.getByRole('button',{name:'View source result',exact:true});
    await expect(source).toBeVisible();
    await expect(page.getByText('Uses result from', {exact:false})).toContainText(props.source.labels.run_name);
    await expect(page.getByText('Unnamed model', {exact:false})).toBeVisible();
    await source.focus();await page.keyboard.press('Enter');
    const output=page.locator(`[data-source-output="${props.source.source_output.instance_id}/${props.source.source_output.port_id}"]`);
    await expect(output).toBeFocused();
    await expect(page).toHaveURL(new RegExp('run='+props.source.source_run_id));
    await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/${caller}-source-light.png`,fullPage:true});
    await page.getByRole('button',{name:caller==='saved'?'Return to configuration':'Return to run',exact:true}).click();
    if(caller==='run') await page.getByRole('tab',{name:'Configuration',exact:true}).click();
    await expect(source).toBeVisible();
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');
    await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/${caller}-binding-dark.png`,fullPage:true});
  });
}

// @editor uses the real client/editor/public API and fresh retained records.
// The fixture explicitly doubles private compatibility; it never claims execution.
async function openEditor(page: Page) {
  await page.goto('/ui/');
  await expect(page.getByLabel('Configuration name', { exact: true })).toBeVisible();
  await page.getByLabel('Configuration name', { exact: true }).fill('Result comparison');
  for (const input of await page.locator('input[data-input-key]').all()) await input.fill('3');
  for (const input of await page.locator('input[aria-label$=" provenance"]').all()) await input.fill('Reviewed laboratory input');
  // Units are explicit (authoritative catalog; no implicit physical default).
  // The retained chain model ports declare no units, so Dimensionless is the explicit choice.
  for (const units of await page.locator('select[aria-label$=" units"]').all()) await units.selectOption('dimensionless');
}
async function choose(page: Page) {
  await page.getByRole('button', { name: 'Use a run result', exact: true }).first().click();
  await expect(page.getByRole('dialog', { name: /Use a run result/ })).toBeVisible();
  await page.getByRole('button', { name: /^Use this result/ }).first().click();
  await expect(page.getByText('In model units', { exact: false })).toBeVisible();
}

test('@editor exact source, nullable labels, conversion and explicit replacement', async ({ page }) => {
  await openEditor(page);
  await page.getByRole('button', { name: 'Use a run result', exact: true }).first().click();
  const dialog = page.getByRole('dialog', { name: /Use a run result/ });
  await expect(dialog.getByText('Unnamed model', { exact: false }).first()).toBeVisible();
  // The shared run outcomes (Execution and Criteria only); applicability is never computed, so not shown.
  const outcomes = dialog.getByLabel('Run outcomes', { exact: true }).first();
  await expect(outcomes).toContainText('Execution Completed'); await expect(outcomes.locator('.hf-tag')).toHaveCount(2);
  await expect(dialog).not.toContainText('Applicability');
  await expect(dialog).toContainText('Criteria are fixed-threshold checks, not a scientific assessment.');
  await page.screenshot({ path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/picker-light.png`, fullPage: true });
  await dialog.getByRole('button', { name: /^Use this result/ }).first().click();
  const input = page.locator('input[data-input-key]').first();
  await expect(input).toHaveAttribute('readonly', '');
  // A bound input's units are the recorded source units, rendered as text (not an editable control).
  const boundUnits = page.locator('[aria-label$=" units"]').first();
  await expect(boundUnits).toBeVisible();
  expect(await boundUnits.evaluate(el => el.tagName)).toBe('P');
  await expect(page.getByText('In model units', { exact: false })).toContainText('150');
  await page.screenshot({ path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/selected-light.png`, fullPage: true });
  await page.getByRole('button', { name: 'View source result', exact: true }).click();
  const props = await (await page.request.get('/fixture')).json();
  await expect(page.getByTestId('source-reference')).toHaveText(JSON.stringify({ runId: props.source.source_run_id, output: props.source.source_output }));
  await page.getByRole('button', { name: 'Enter a value instead', exact: true }).click();
  await expect(input).not.toHaveAttribute('readonly', '');
  await expect(input).toHaveValue('150');
  await expect(page.locator('input[aria-label$=" provenance"]').first()).toHaveValue('Reviewed laboratory input');
  await input.fill('7');
  await expect(page.getByTestId('dirty')).toHaveText('dirty');
});

// New (non-seed) configurations are Request3 since 02-13; Request2 remains only for legacy Seed1.
test('@editor request3 preview digest and saved copy preserve binding', async ({ page }) => {
  await openEditor(page); await choose(page);
  const commandPromise = page.waitForRequest(r => r.method() === 'POST' && /\/configurations$/.test(r.url()));
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  const command = (await commandPromise).postDataJSON();
  expect(command.configuration.schema_version).toBe('3');
  expect(command.configuration.inputs[0].kind).toBe('run_result');
  expect(command.configuration.inputs[0]).not.toHaveProperty('value');
  expect(command.expected_preview_digest).toMatch(/^[a-f0-9]{64}$/);
  await expect(page.getByRole('button', { name: /Copy.*configuration/i }).first()).toBeVisible();
  await page.getByRole('button', { name: /Copy.*configuration/i }).first().click();
  await expect(page.locator('input[data-input-key]').first()).toHaveAttribute('readonly', '');
  await expect(page.getByRole('button', { name: 'View source result', exact: true })).toBeVisible();
});

test('@editor paging, empty filter, read failure and keyboard close preserve edits', async ({ page }) => {
  await openEditor(page);
  const props = await (await page.request.get('/fixture')).json(); let calls = 0;
  // Explicit transport fault/pagination double; actual-source/save tests above use API.
  await page.route('**/result-sources?*', async route => {
    calls++;
    if (calls === 1) return route.fulfill({ status: 503, json: { error: { code: 'backend_unavailable', message: 'Unavailable', fields: [], outcome: 'unchanged' } } });
    return route.fulfill({ json: { schema_version: '1', data: { items: calls === 2 ? [props.source] : [], next_cursor: calls === 2 ? 'page-two' : null } } });
  });
  const invoking = page.getByRole('button', { name: 'Use a run result', exact: true }).first();
  await invoking.click();
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
  await page.screenshot({ path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/picker-error.png`, fullPage: true });
  await page.getByRole('button', { name: 'Retry results', exact: true }).click();
  await page.getByRole('button', { name: 'Load more', exact: true }).click();
  expect(calls).toBe(3);
  await page.getByLabel('Filter loaded results', { exact: true }).fill('not-a-match');
  await expect(page.getByText('No matching results in the loaded page.')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(invoking).toBeFocused();
  await expect(page.getByLabel('Configuration name', { exact: true })).toHaveValue('Result comparison');
  await expect(page.locator('input[data-input-key]').first()).toHaveValue('3');
});

test('@editor uncertain save recovers original committed command without duplicate', async ({ page }) => {
  await openEditor(page); await choose(page);
  const bodies: unknown[] = [];
  await page.route('**/configurations', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    bodies.push(route.request().postDataJSON()); await route.fetch(); await route.abort('failed');
  });
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Check original configuration command', exact: true })).toBeVisible();
  await expect(page.getByLabel('Configuration name', { exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Check original configuration command', exact: true }).click();
  await expect(page.getByRole('button', { name: /Copy.*configuration/i }).first()).toBeVisible();
  expect(bodies).toHaveLength(1);
});

test('@editor dark selected state and keyboard operation', async ({ page }) => {
  await openEditor(page);
  await page.evaluate(() => document.documentElement.dataset.theme = 'dark');
  const trigger = page.getByRole('button', { name: 'Use a run result', exact: true }).first();
  await trigger.focus(); await page.keyboard.press('Enter');
  await page.getByRole('button', { name: /^Use this result/ }).first().focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('In model units', { exact: false })).toBeVisible();
  await page.screenshot({ path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/selected-dark.png`, fullPage: true });
});

test('@editor literal inputs use Request3 and a reviewed finite value', async ({ page }) => {
  await openEditor(page);
  const sent = page.waitForRequest(r => r.method() === 'POST' && /\/configurations$/.test(r.url()));
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  const body = (await sent).postDataJSON();
  expect(body.configuration.schema_version).toBe('3');
  expect(body.configuration.inputs.every((i: { kind: string; value: number; units: string }) => i.kind === 'literal' && i.value === 3 && i.units === '')).toBe(true);
  await expect(page.getByRole('button', { name: /Copy.*configuration/i }).first()).toBeVisible();
});

test('@editor empty inventory is explicit and selection survives preview rejection', async ({ page }) => {
  await openEditor(page);
  await page.route('**/result-sources?*', route => route.fulfill({ json: { schema_version: '1', data: { items: [], next_cursor: null } } }));
  await page.getByRole('button', { name: 'Use a run result', exact: true }).first().click();
  await expect(page.getByText('No available run results in the loaded page.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.unroute('**/result-sources?*');
  await page.route('**/configurations/preview', route => route.fulfill({ status: 409, json: { error: { code: 'reference_conflict', message: 'Source result changed. Choose the source again.', fields: [], outcome: 'unchanged' } } }));
  await page.getByRole('button', { name: 'Use a run result', exact: true }).first().click();
  await page.getByRole('button', { name: /^Use this result/ }).first().click();
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Source result changed');
  await expect(page.locator('input[data-input-key]').first()).toHaveValue('150');
  await expect(page.locator('input[data-input-key]').first()).toHaveAttribute('readonly', '');
  await expect(page.getByLabel('Configuration name', { exact: true })).toHaveValue('Result comparison');
  await expect(page.getByTestId('dirty')).toHaveText('dirty');
});

test('@editor an absent original command retries its identical body', async ({ page }) => {
  await openEditor(page); await choose(page);
  const bodies: unknown[] = [];
  await page.route('**/configurations', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    bodies.push(route.request().postDataJSON());
    if (bodies.length === 1) return route.abort('failed');
    await route.continue();
  });
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  await page.getByRole('button', { name: 'Check original configuration command', exact: true }).click();
  await page.getByRole('button', { name: 'Retry original configuration command', exact: true }).click();
  await expect(page.getByRole('button', { name: /Copy.*configuration/i }).first()).toBeVisible();
  expect(bodies).toHaveLength(2); expect(bodies[1]).toEqual(bodies[0]);
});

test('@editor genuine 200 percent browser zoom preserves picker and selected actions', async ({ baseURL }) => {
  test.setTimeout(120000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const extension = join(root, 'artifacts/zoom-extension');
  await mkdir(extension);
  await writeFile(join(extension, 'manifest.json'), JSON.stringify({ manifest_version: 3, name: 'Isolated editor zoom', version: '1.0', permissions: ['tabs'], background: { service_worker: 'worker.js' } }));
  await writeFile(join(extension, 'worker.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
  const context = await chromium.launchPersistentContext(join(root, 'artifacts/zoom-profile'), {
    executablePath: chromiumExecutable(),
    headless: true, viewport: null, baseURL,
    args: ['--disable-extensions-except=' + extension, '--load-extension=' + extension, '--window-size=1440,1000', '--no-first-run'],
  });
  const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker');
  let tabId: number | undefined;
  try {
    const page = context.pages()[0] ?? await context.newPage();
    await page.route('**/*', route => new URL(route.request().url()).origin === baseURL ? route.continue() : route.abort());
    await openEditor(page);
    const cdp = await context.newCDPSession(page), window = await cdp.send('Browser.getWindowForTarget');
    for (let attempt = 0; attempt < 3; attempt++) {
      const size = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
      if (size.width === 1440 && size.height === 1000) break;
      const current = await cdp.send('Browser.getWindowBounds', { windowId: window.windowId });
      await cdp.send('Browser.setWindowBounds', { windowId: window.windowId, bounds: { width: current.bounds.width! + 1440 - size.width, height: current.bounds.height! + 1000 - size.height } });
      await expect.poll(() => page.evaluate(() => ({ width: innerWidth, height: innerHeight }))).toEqual({ width: 1440, height: 1000 });
    }
    const before = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio }));
    expect(before.width).toBe(1440); expect(before.height).toBe(1000);
    tabId = await worker.evaluate(async origin => {
      const chrome = (globalThis as any).chrome;
      const tab = (await chrome.tabs.query({})).find((t: any) => t.url?.startsWith(origin + '/ui/'));
      if (!tab?.id) throw new Error('Isolated fixture tab missing');
      await chrome.tabs.setZoomSettings(tab.id, { mode: 'automatic', scope: 'per-tab' });
      await chrome.tabs.setZoom(tab.id, 2); return tab.id;
    }, baseURL);
    async function capture(name: string) {
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
      const shot = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
      await writeFile(join(root, 'evidence/' + name), Buffer.from(shot.data, 'base64'));
    }
    const factor = await worker.evaluate(id => (globalThis as any).chrome.tabs.getZoom(id), tabId);
    expect(factor).toBe(2);
    await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);
    const after = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio }));
    expect(after.height).toBe(500); expect(page.viewportSize()).toBeNull();
    const trigger = page.getByRole('button', { name: 'Use a run result', exact: true }).first();
    await trigger.focus(); await page.keyboard.press('Enter');
    const pick = page.getByRole('button', { name: /^Use this result/ }).first();
    await pick.focus();
    await expect(pick).toBeFocused();
    await capture('picker-200.png');
    await page.keyboard.press('Enter');
    await expect(page.getByText('In model units', { exact: false })).toBeVisible();
    const replace = page.getByRole('button', { name: 'Enter a value instead', exact: true });
    await replace.focus(); await expect(replace).toBeFocused();
    const hit = await replace.evaluate(el => { const b = el.getBoundingClientRect(); const at = document.elementFromPoint(b.x+b.width/2, b.y+b.height/2); return { unobstructed: at === el || el.contains(at), width: innerWidth, scrollWidth: document.documentElement.scrollWidth, outline: getComputedStyle(el).outlineWidth }; });
    expect(await replace.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    expect(hit.unobstructed).toBe(true); expect(hit.scrollWidth).toBeLessThanOrEqual(hit.width + 1); expect(hit.outline).toBe('2px');
    await capture('selected-200.png');
    await page.evaluate(() => document.documentElement.dataset.theme = 'dark');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await capture('selected-dark-200.png');
    await writeFile(join(root, 'evidence/zoom.json'), JSON.stringify({ factor, before, after, viewportEmulation: page.viewportSize(), hit }, null, 2));
    await page.keyboard.press('Enter');
    await expect(page.locator('input[data-input-key]').first()).not.toHaveAttribute('readonly', '');
  } finally {
    if (tabId !== undefined) await worker.evaluate(id => (globalThis as any).chrome.tabs.setZoom(id, 1), tabId);
    await context.close();
  }
});

// Overview: recent runs read "name · id8" with Execution and Criteria only; full identities live in Record details;
// the study header names the study once; the footer is one notices link.
test('@retained Overview recent records show name and id8 with Execution and Criteria, no identity disclosures, the study name once and one notices link',async({page})=>{
  test.setTimeout(120000);
  const props=await (await page.request.get('/fixture')).json(),sid=props.study.study_id;
  await page.goto('/ui/?retained=overview#'+new URLSearchParams({v:'1',study:sid,view:'overview'}));
  await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  const runs=page.getByRole('region',{name:'Recent runs',exact:true}),configs=page.getByRole('region',{name:'Recent configurations',exact:true});
  const linked=runs.getByRole('button',{name:'Open run '+props.linked_run,exact:true});
  await expect(linked).toHaveText(new RegExp(' · '+props.linked_run.slice(0,8)+'$'));
  const outcomes=runs.getByLabel('Run outcomes',{exact:true});await expect(outcomes.first()).toBeVisible();await expect(runs).not.toContainText('Loading status');
  for(const summary of await outcomes.all()){await expect(summary.locator('.hf-tag')).toHaveCount(2);await expect(summary).toContainText('Execution');await expect(summary).toContainText('Criteria');}
  const revision=props.saved.configuration.configuration_revision_id;
  const config=configs.getByRole('button',{name:props.saved.configuration.name+' · Open configuration '+revision,exact:true});
  await expect(config).toHaveText(props.saved.configuration.name);await expect(configs).toContainText('Version '+revision.slice(0,8)+' · read-only');
  // Full identities are not shown on Overview (Record details owns them).
  for(const region of [runs,configs])await expect(region.locator('details')).toHaveCount(0);
  await expect(page.getByText(/^Exact (run|configuration) identities$/)).toHaveCount(0);
  await expect(runs).not.toContainText(props.linked_run);await expect(configs).not.toContainText(revision);
  await expect(configs).not.toContainText(props.saved.configuration.model_revision_id);
  // Section named once: no subtitle under the study name; the active tab names the section.
  await expect(page.locator('.study-heading')).toHaveText(props.study.name);
  await expect(page.getByRole('navigation',{name:'Workspace sections',exact:true}).getByRole('button',{name:'Overview',exact:true})).toHaveAttribute('aria-current','page');
  const footer=page.locator('main>footer');await expect(footer).toHaveText('Third-party software notices');
  await expect(footer.getByRole('link')).toHaveCount(1);await expect(footer.getByRole('link',{name:'Third-party software notices',exact:true})).toHaveAttribute('href','/ui/THIRD_PARTY_NOTICES.txt');
  const cdp=await page.context().newCDPSession(page),root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  try{
    for(const [size,metrics] of [['1440',{width:1440,height:1000,deviceScaleFactor:1,mobile:false}],['375',{width:375,height:812,deviceScaleFactor:1,mobile:false}],['200',{width:720,height:500,deviceScaleFactor:2,mobile:false}]] as const){
      await cdp.send('Emulation.setDeviceMetricsOverride',metrics);
      for(const theme of ['light','dark']){
        await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
        await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
        await expect.poll(()=>page.evaluate(()=>document.getAnimations().every(a=>a.playState!=='running'))).toBe(true);
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),size).toBe(true);
        for(const [part,target] of [['top',null],['records',runs]] as const){
          if(target)await target.evaluate(element=>element.scrollIntoView({block:'start'}));else await page.evaluate(()=>scrollTo(0,0));
          const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
          await writeFile(join(root,'evidence',`s6b-overview-${part}-${size}-${theme}.png`),Buffer.from(shot.data,'base64'));
        }
      }
    }
  }finally{await cdp.send('Emulation.clearDeviceMetricsOverride');await cdp.detach();}
});
