import {test, expect, chromium, type Page} from 'playwright/test';
import {mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import { chromiumExecutable } from './support/browser';

test.beforeEach(async({request})=>{await request.post('/fixture/control',{data:{offline:true}});await request.post('/fixture/control',{data:{description:''}});});

async function openSource(page: Page) {
  const props=await(await page.request.get('/fixture')).json();
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:props.study.study_id,view:'runs',run:props.linked_run}));
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('button',{name:'Create modified run',exact:true})).toBeEnabled();
  return props;
}

test('@modified retained seed opens offline without current model or writes',async({page})=>{
  const writes:string[]=[],mutable:string[]=[];
  // The modified run works from its source's saved model version: it never reads the current
  // model or a model version. Only the calculation navigation lists retained version summaries.
  page.on('request',r=>{if(r.method()==='POST'&&/\/configurations$|\/runs$/.test(r.url()))writes.push(r.url());const path=new URL(r.url()).pathname;if(/\/models\//.test(path)&&!/\/models\/[^/]+\/revisions$/.test(path))mutable.push(r.url());});
  await openSource(page);
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Create modified run',exact:true})).toBeVisible();
  await expect(page.locator('input[data-input-key][readonly]')).toHaveValue('150');
  await page.getByLabel('Configuration name',{exact:true}).fill('Modified offline work');
  // The modeling outage is surfaced before a save attempt: unit guidance
  // (served by the private modeling service) is unavailable, so saving is not offered.
  const editor=page.getByRole('region',{name:'Configuration',exact:true});
  await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeDisabled();
  await expect(editor.getByRole('alert')).toContainText('unavailable');
  await expect(page.getByRole('radio',{name:/context/})).toHaveCount(0);
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Modified offline work');
  expect(writes).toEqual([]);expect(mutable).toEqual([]);
  await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/modified-outage.png`,fullPage:true});
});

test('@modified unchanged cancellation and review cancellation allocate no records',async({page})=>{
  const writes:string[]=[];page.on('request',r=>{if(r.method()==='POST'&&/\/configurations$|\/runs$/.test(r.url()))writes.push(r.url());});
  await openSource(page);await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await page.getByRole('button',{name:'Cancel modified run',exact:true}).click();
  await expect(page.getByRole('button',{name:'Create modified run',exact:true})).toBeEnabled();
  await page.request.post('/fixture/control',{data:{offline:false}});
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  const save=page.getByRole('button',{name:'Save configuration',exact:true});await save.click();
  await expect(page.getByRole('dialog',{name:'Review modified run',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');await expect(save).toBeFocused();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue(/modified/);expect(writes).toEqual([]);
});

test('@modified inherited context notes, stale review and exact origin save',async({page})=>{
  await page.request.post('/fixture/control',{data:{description:'Current study question'}});
  const props=await openSource(page);const sid=props.study.study_id;
  const before=await(await page.request.get(`/api/1/studies/${sid}/runs/${props.linked_run}`)).json();
  await page.request.post('/fixture/control',{data:{offline:false}});
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await expect(page.getByRole('radio',{name:/context/})).toHaveCount(0);
  // A configuration 6 owns its context: the source run's description starts the draft and
  // stays editable for the new configuration only; the source run is never changed.
  await page.getByRole('button',{name:'Input tools',exact:true}).click();
  const tools=page.getByRole('dialog',{name:'Input tools and model binding',exact:true});
  await expect(tools.getByLabel('Description',{exact:true})).toBeEnabled();
  await expect(tools.getByLabel('Description',{exact:true})).toHaveValue(props.saved.configuration.context_snapshot.description);
  // Configuration notes are not authored in the UI; inherited notes pass through unchanged.
  await expect(page.getByLabel('Configuration notes',{exact:true})).toHaveCount(0);
  await tools.getByRole('button',{name:'Done',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('My independent attempt');
  await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/modified-context-light.png`,fullPage:true});
  await page.request.post('/fixture/control',{data:{description:'Context changed again'}});
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await page.getByRole('button',{name:'Refresh study revision',exact:true}).click();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('My independent attempt');
  for(const note of props.saved.configuration.context_snapshot.notes)await expect(page.locator('#configuration .configuration-context').getByText(note,{exact:true})).toHaveCount(0);
  const literal=page.locator('input[data-input-key]:not([readonly])').first();await literal.fill('9.123456');
  await page.getByRole('button',{name:'View source result',exact:true}).click();
  await page.getByRole('button',{name:'Return to configuration',exact:true}).click();
  await expect(literal).toHaveValue('9.123456');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Review modified run',exact:true});await expect(dialog).toContainText('Provisional runtime');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.emulateMedia({reducedMotion:'reduce'});
  await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/modified-review-dark.png`,fullPage:true});
  const committed=page.waitForResponse(r=>r.request().method()==='POST'&&/\/configurations$/.test(r.url()));
  await page.getByRole('button',{name:'Save modified configuration',exact:true}).click();
  const response=await committed;expect(response.status()).toBe(201);const saved=(await response.json()).data;
  expect(saved.configuration.configuration_id).not.toBe(props.saved.configuration.configuration_id);
  expect(saved.configuration.model_revision_id).toBe(props.saved.configuration.model_revision_id);
  expect(saved.configuration.inputs[0].result_binding).toEqual(props.saved.configuration.inputs[0].result_binding);
  expect(saved.configuration.derivation.source_run_id).toBe(props.linked_run);
  expect(saved.configuration.evidence_snapshots).toEqual(props.saved.configuration.evidence_snapshots);
  expect(saved.configuration.evidence_snapshots).toHaveLength(1);
  expect(saved.configuration.context_snapshot.notes).toEqual(props.saved.configuration.context_snapshot.notes);
  expect(saved.configuration.inputs[1].value).toBe(9.123456);
  await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
  const after=await(await page.request.get(`/api/1/studies/${sid}/runs/${props.linked_run}`)).json();expect(after.data).toEqual(before.data);
});

test('@modified inherited context and lost submission preserve saved revision and command',async({page})=>{
  await page.request.post('/fixture/control',{data:{description:'Current investigation question'}});
  const props=await openSource(page);await page.request.post('/fixture/control',{data:{offline:false}});
  // Readiness only is a transport double. Save, queue admission and receipts use
  // the actual isolated API. No worker runs and no numerical success is claimed.
  await page.route('**/execution-readiness',route=>route.fulfill({json:{schema_version:'1',data:{readiness_schema_version:'1',capability:'flat_explicit_scalar',status:'ready',reasons:[],observed_at:new Date().toISOString(),expires_at:new Date(Date.now()+600000).toISOString()}}}));
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await expect(page.getByRole('radio',{name:/context/})).toHaveCount(0);
  await page.getByLabel('Configuration name',{exact:true}).fill('Current context attempt');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const commit=page.waitForResponse(r=>r.request().method()==='POST'&&/\/configurations$/.test(r.url()));
  await page.getByRole('button',{name:'Save modified configuration',exact:true}).click();
  const saved=(await(await commit).json()).data;expect(saved.configuration.context_snapshot.description).toBe(props.saved.configuration.context_snapshot.description);
  const commands:any[]=[];let accepted:any;
  await page.route('**/runs',async route=>{if(route.request().method()!=='POST')return route.continue();commands.push(route.request().postDataJSON());const result=await route.fetch();accepted=(await result.json()).data;await route.abort('failed');});
  await page.getByRole('button',{name:'Run this configuration',exact:true}).click();
  await expect(page.getByRole('button',{name:'Run this configuration',exact:true})).toBeDisabled();
  await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
  expect(commands).toHaveLength(1);expect(commands[0].configuration_revision_id).toBe(saved.configuration.configuration_revision_id);
  await page.getByRole('button',{name:'Check original command',exact:true}).click();
  await expect(page).toHaveURL(new RegExp('run='+accepted.run_id));expect(commands).toHaveLength(1);
  const receipt=(await(await page.request.get(`/api/1/studies/${props.study.study_id}/commands/${commands[0].command_id}?category=run`)).json()).data;
  expect(receipt.result.run_id).toBe(accepted.run_id);
  // Presentation-only prepared response; the native journeys prove real prepared bundles.
  const seed=(await(await page.request.get(`/api/1/studies/${props.study.study_id}/runs/${props.linked_run}/modified-run-seed`)).json()).data;
  await page.route(`**/runs/${accepted.run_id}`,async route=>{const response=await route.fetch();const body=await response.json();body.data.runtime_comparison={source:seed.source_runtime,current:{...seed.source_runtime,policy_digest:'f'.repeat(64)},state:'different',basis:'prepared_bundle',observed_at:null,expires_at:null};await route.fulfill({json:body});});
  await page.getByRole('button',{name:'Refresh run status',exact:true}).click();
  await expect(page.getByText('Prepared runtime · saved for this attempt',{exact:true})).toBeVisible();
  await expect(page.getByText('Provisional runtime · checked again during preparation',{exact:true})).not.toBeVisible();
  await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/modified-prepared-display.png`});
});

test('@modified lost save receipt recovers one independent revision',async({page})=>{
  const props=await openSource(page);await page.request.post('/fixture/control',{data:{offline:false}});
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  const commands:any[]=[];
  await page.route('**/configurations',async route=>{if(route.request().method()!=='POST')return route.continue();commands.push(route.request().postDataJSON());await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await page.getByRole('button',{name:'Save modified configuration',exact:true}).click();
  await expect(page.getByRole('button',{name:'Check original configuration command',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Check original configuration command',exact:true}).click();
  await expect(page.getByText('Read-only',{exact:true})).toBeVisible();expect(commands).toHaveLength(1);
  const configurations=(await(await page.request.get(`/api/1/studies/${props.study.study_id}/configurations`)).json()).data;
  const receipt=(await(await page.request.get(`/api/1/studies/${props.study.study_id}/commands/${commands[0].command_id}?category=configuration`)).json()).data;
  expect(configurations.filter((c:any)=>c.configuration.configuration_revision_id===receipt.result.configuration.configuration_revision_id)).toHaveLength(1);
});

test('@modified genuine 200 percent context, binding and review keyboard flow',async({baseURL,request})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  await request.post('/fixture/control',{data:{description:'Changed investigation context with retained evidence and the original scientific model.'}});
  const extension=join(root,'artifacts/modified-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Modified run zoom',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/modified-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');let tabId:number|undefined;
  try {
    const page=context.pages()[0]??await context.newPage();await openSource(page);
    await page.getByRole('button',{name:'Create modified run',exact:true}).click();
    const cdp=await context.newCDPSession(page);const info=await cdp.send('Browser.getWindowForTarget');
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    tabId=await worker.evaluate(async(url)=>{const tabs=await (globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tabId);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId)).toBe(2);
    expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,`evidence/${name}.png`),Buffer.from(shot.data,'base64'));expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);}
    const edit=page.getByRole('button',{name:'Input tools',exact:true});await edit.focus();await page.keyboard.press('Enter');await expect(page.getByLabel('Description',{exact:true})).toBeVisible();await expect(page.getByLabel('Configuration notes',{exact:true})).toHaveCount(0);await page.keyboard.press('Escape');await expect(edit).toBeFocused();
    await capture('modified-context-200-light');
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(250);
    const replace=page.getByRole('button',{name:'Enter a value instead',exact:true});await replace.focus();await replace.scrollIntoViewIfNeeded();
    expect(await replace.evaluate(button=>{const r=button.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===button;})).toBe(true);
    await capture('modified-binding-200-dark');await page.keyboard.press('Enter');await expect(page.locator('input[data-input-key][readonly]')).toHaveCount(0);
    await page.request.post('/fixture/control',{data:{offline:false}});
    // Unit guidance failed while offline; recover it by keyboard before saving.
    const retry=page.getByRole('button',{name:'Retry unit guidance',exact:true});await retry.focus();await page.keyboard.press('Enter');
    const save=page.getByRole('button',{name:'Save configuration',exact:true});await expect(save).toBeEnabled();await save.focus();await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog',{name:'Review modified run',exact:true})).toBeVisible();await capture('modified-review-200-dark');
    await page.keyboard.press('Escape');await expect(save).toBeFocused();
    await writeFile(join(root,'evidence/modified-zoom.json'),JSON.stringify({factor:2,viewport:page.viewportSize(),geometry:await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio}))}));
  } finally {if(tabId!==undefined)await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tabId);await context.close();}
});
