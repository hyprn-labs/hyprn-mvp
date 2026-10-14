import {test, expect, chromium, type Page} from 'playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import { chromiumExecutable } from './support/browser';

test.beforeEach(async({request})=>{expect((await request.post('/fixture/export-control',{data:{action:'reset'}})).ok()).toBe(true);});
const panel=(page:Page)=>page.getByRole('dialog',{name:'Export computational record',exact:true});
const action=(page:Page,name:string)=>panel(page).getByRole('button',{name,exact:true});
const control=(page:Page,action:string)=>page.request.post('/fixture/export-control',{data:{action}});
async function review(page:Page){await action(page,'Review record').click();await expect(panel(page)).toContainText('Queued');await control(page,'process');await expect(action(page,'Create record export')).toBeEnabled();}
async function ready(page:Page){await review(page);await action(page,'Create record export').click();await expect(panel(page)).toContainText('Queued');await control(page,'process');await expect(action(page,'Download record export')).toBeEnabled();}
async function capture(page:Page,name:string){await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(250);await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/${name}.png`});}

async function openRecord(page: Page) {
  const props=await(await page.request.get('/fixture')).json();
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:props.sid,view:'runs',run:props.rid}));
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  const exports = page.getByRole('group', { name: 'Run exports', exact: true });
  await expect(exports.getByRole('button')).toHaveText([
    'Export model and data',
    'Export computational record',
  ]);
  const boxes = await exports.getByRole('button').evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, right: rect.right };
    }),
  );
  expect(boxes[1].x).toBeGreaterThan(boxes[0].right);
  expect(boxes[1].y).toBe(boxes[0].y);
  await exports.getByRole('button', { name: 'Export computational record', exact: true }).click();
  return props;
}

test('@export actual preview, explicit package and verified binary download',async({page})=>{
  const props=await openRecord(page);
  const dialog=page.getByRole('dialog',{name:'Export computational record',exact:true});
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:'Review record',exact:true}).click();
  await expect(dialog).toContainText('Queued');
  await page.request.post('/fixture/export-control',{data:{action:'process'}});
  await expect(dialog.getByRole('button',{name:'Create record export',exact:true})).toBeEnabled();
  await expect(dialog).toContainText('Computational ancestors');
  await expect(dialog).toContainText('Inspection only');
  await expect(dialog).toContainText('Runtime portability is unverified');
  await expect(dialog.getByRole('region',{name:'Selected runs',exact:true})).toContainText('Modified comparison');
  await expect(dialog.getByRole('region',{name:'Computational ancestors',exact:true})).toContainText('Sizing result');
  await expect(dialog.getByRole('region',{name:'Configuration origins',exact:true})).toContainText('Configuration origin');
  await expect(dialog.getByText(props.rid,{exact:true})).not.toBeVisible();
  await capture(page,'export-review-light');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');await capture(page,'export-review-dark');
  await dialog.getByRole('button',{name:'Create record export',exact:true}).click();
  await expect(dialog).toContainText('Queued');
  await page.request.post('/fixture/export-control',{data:{action:'process'}});
  await expect(dialog.getByRole('button',{name:'Download record export',exact:true})).toBeEnabled();
  const downloaded=page.waitForEvent('download');
  await dialog.getByRole('button',{name:'Download record export',exact:true}).click();
  const download=await downloaded;expect(download.suggestedFilename()).toBe('hyprn-mvp-computational-record.zip');
  const file=`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/downloaded-computational-record.zip`;await download.saveAs(file);
  const evidence=await(await control(page,'evidence')).json();expect(evidence.scientific_unchanged).toBe(true);expect(evidence.requests).toHaveLength(2);
  const created=evidence.requests.find((row:any)=>row.kind==='create');
  const status=(await(await page.request.get(`/api/1/studies/${props.sid}/computational-records/${created.request_id}`)).json()).data;
  const bytes=await readFile(file);expect(bytes.length).toBe(status.download.size);expect(createHash('sha256').update(bytes).digest('hex')).toBe(status.download.sha256);
  expect(bytes.subarray(0,2).toString()).toBe('PK');await capture(page,'export-ready-dark');
});

test('@export queued close restores focus, stops reads and preserves accepted request',async({page})=>{
  await openRecord(page);let polls=0;
  page.on('request',request=>{if(request.method()==='GET'&&/\/computational-records\/[^/]+$/.test(new URL(request.url()).pathname))polls++;});
  await action(page,'Review record').click();await expect(panel(page)).toContainText('Queued');
  await expect(panel(page).getByRole('progressbar')).not.toHaveAttribute('value');
  await control(page,'building');await expect(panel(page)).toContainText('Building record');
  await page.keyboard.press('Escape');await expect(panel(page)).not.toBeVisible();
  await expect(page.getByRole('button',{name:'Export computational record',exact:true})).toBeFocused();
  await page.waitForTimeout(250);const stopped=polls;await page.waitForTimeout(1300);expect(polls).toBe(stopped);
  await page.keyboard.press('Enter');await expect(panel(page)).toContainText('Building record');await action(page,'Close').focus();await control(page,'process');await expect(action(page,'Create record export')).toBeEnabled();await expect(action(page,'Close')).toBeFocused();
  const terminal=polls;await page.waitForTimeout(1300);expect(polls).toBe(terminal);
  expect((await(await control(page,'evidence')).json()).requests).toHaveLength(1);
});

test('@export lost preview and create acknowledgements recover their original receipts',async({page})=>{
  await openRecord(page);const sent:any[]=[];
  await page.route('**/computational-record-previews',async route=>{sent.push(route.request().postDataJSON());await route.fetch();await route.abort('failed');});
  await action(page,'Review record').click();await expect(action(page,'Check original export command')).toBeVisible();
  await action(page,'Check original export command').click();await expect(panel(page)).toContainText('Queued');
  await control(page,'process');await expect(action(page,'Create record export')).toBeEnabled();
  await page.route('**/computational-records',async route=>{sent.push(route.request().postDataJSON());await route.fetch();await route.abort('failed');});
  await action(page,'Create record export').click();await expect(action(page,'Check original export command')).toBeVisible();await action(page,'Check original export command').click();
  await control(page,'process');await expect(action(page,'Download record export')).toBeEnabled();
  const rows=(await(await control(page,'evidence')).json()).requests;expect(rows).toHaveLength(2);expect(sent).toHaveLength(2);
  expect(rows.map((row:any)=>row.command_id).sort()).toEqual(sent.map(body=>body.command_id).sort());expect(sent[1].preview_id).toBe(rows.find((row:any)=>row.kind==='preview').request_id);
});

test('@export never-received command retries the exact original body after receipt check',async({page})=>{
  await openRecord(page);const bodies:any[]=[];
  await page.route('**/computational-record-previews',async route=>{bodies.push(route.request().postDataJSON());if(bodies.length===1)await route.abort('failed');else await route.continue();});
  await action(page,'Review record').click();await action(page,'Check original export command').click();await expect(action(page,'Retry original export command')).toBeEnabled();
  await action(page,'Retry original export command').click();await expect(panel(page)).toContainText('Queued');expect(bodies).toHaveLength(2);expect(bodies[0]).toEqual(bodies[1]);
  expect((await(await control(page,'evidence')).json()).requests).toHaveLength(1);
});

test('@export stale create fails honestly and requires explicit new review',async({page})=>{
  await openRecord(page);await review(page);await action(page,'Create record export').click();await expect(panel(page)).toContainText('Queued');await control(page,'fail');
  await expect(panel(page)).toContainText('The record changed since review');await expect(action(page,'Review again')).toBeEnabled();
  await capture(page,'export-stale-light');const before=(await(await control(page,'evidence')).json()).requests;expect(before).toHaveLength(2);
  await action(page,'Review again').click();await expect(panel(page)).toContainText('Queued');await control(page,'process');await expect(action(page,'Create record export')).toBeEnabled();
  const after=(await(await control(page,'evidence')).json()).requests;expect(after).toHaveLength(3);expect(new Set(after.map((row:any)=>row.command_id)).size).toBe(3);
});

const downloadPath=(response:{url():string})=>/\/computational-records\/[^/]+\/download$/.test(new URL(response.url()).pathname);
test('@export current authorization is checked again before any download',async({page})=>{
  const props=await openRecord(page);await ready(page);let downloads=0;page.on('download',()=>downloads++);await control(page,'revoke');
  // The server re-authorizes the package read itself; the revoked member gets no bytes.
  const refused=page.waitForResponse(downloadPath);
  await action(page,'Download record export').click();expect([403,404]).toContain((await refused).status());
  // The refusal is classified like every other read of this run. The study probe
  // confirms the access loss, so the run record and its reviewed export are cleared, not kept on screen.
  await expect(page.getByText('Access to this resource is no longer available.',{exact:true}).first()).toBeVisible();
  await expect(panel(page)).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Download record export',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Export computational record',exact:true})).toHaveCount(0);
  await expect(page.getByText(props.rid)).toHaveCount(0);
  expect(downloads).toBe(0);await capture(page,'export-revoked-light');
});

test('@export a refused package read with study access intact keeps the request checkable',async({page})=>{
  const props=await openRecord(page);await ready(page);let downloads=0;page.on('download',()=>downloads++);
  // Declared transport overlay: only the package read is refused; membership is unchanged.
  await page.route('**/computational-records/*/download',route=>route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({error:{code:'resource_not_found',message:'resource_not_found',request_id:crypto.randomUUID(),command_id:null,resource_id:null,current_revision:null,outcome:'unchanged',fields:[]}})}));
  const probe=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/1/studies/'+props.sid&&response.request().method()==='GET');
  await action(page,'Download record export').click();expect((await probe).status()).toBe(200);
  await expect(panel(page)).toContainText('This record is no longer available to you');expect(downloads).toBe(0);await expect(action(page,'Download record export')).toBeDisabled();await expect(panel(page)).toContainText('Status needs checking');await expect(action(page,'Check request status')).toBeEnabled();await capture(page,'export-refused-light');
  await page.unroute('**/computational-records/*/download');
  await action(page,'Check request status').click();await expect(action(page,'Download record export')).toBeEnabled();expect(downloads).toBe(0);
});

test('@export corrupt transport bytes are rejected before browser download',async({page})=>{
  await openRecord(page);await ready(page);let downloads=0;page.on('download',()=>downloads++);
  await page.route('**/computational-records/*/download',async route=>{const response=await route.fetch();const body=await response.body();body[body.length-1]^=1;await route.fulfill({response,body});});
  await action(page,'Download record export').click();await expect(panel(page)).toContainText('Record export verification failed');expect(downloads).toBe(0);
});

test('@export genuine 200 percent zoom, bounded dialog and keyboard focus',async({baseURL})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const extension=join(root,'artifacts/export-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Export zoom',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/export-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');let tabId:number|undefined;
  try{
    const page=context.pages()[0]??await context.newPage();await openRecord(page);await review(page);
    const cdp=await context.newCDPSession(page);const info=await cdp.send('Browser.getWindowForTarget');await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    tabId=await worker.evaluate(async(url)=>{const tabs=await (globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tabId);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId)).toBe(2);
    expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function shot(name:string){await page.waitForTimeout(250);const value=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,`evidence/${name}.png`),Buffer.from(value.data,'base64'));expect(await panel(page).evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);}
    await panel(page).evaluate(e=>e.scrollTop=0);await shot('export-review-200-light');
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.emulateMedia({reducedMotion:'reduce'});await action(page,'Create record export').focus();await action(page,'Create record export').scrollIntoViewIfNeeded();
    expect(await action(page,'Create record export').evaluate(button=>{const r=button.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===button;})).toBe(true);
    await panel(page).locator('.dialog-body').evaluate(e=>e.scrollTop=e.scrollHeight);await shot('export-actions-200-dark');await page.keyboard.press('Tab');await expect(panel(page).getByText('Details',{exact:true})).toBeFocused();
    await page.keyboard.press('Enter');await shot('export-details-200-dark');await page.keyboard.press('Shift+Tab');await expect(action(page,'Create record export')).toBeFocused();
    await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Export computational record',exact:true})).toBeFocused();
    await writeFile(join(root,'evidence/export-zoom.json'),JSON.stringify({factor:2,viewport:page.viewportSize(),geometry:await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio}))}));
  }finally{if(tabId!==undefined)await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tabId);await context.close();}
});


test('@export actionable admission limits retain selection and distinguish size from queue pressure',async({page})=>{
  const props=await openRecord(page);
  const messages=[
    'Selected runs and their required records exceed the 32 MiB expanded export limit. Export fewer runs. If one run still exceeds the limit, its complete record cannot currently be exported; required computational ancestors cannot be omitted.',
    'Too many export requests are pending. Wait for an existing request to finish before creating another.'
  ];
  let calls=0;
  await page.route('**/computational-record-previews',async route=>{
    const body=route.request().postDataJSON();expect(body.selected_run_ids).toEqual([props.rid]);
    const text=messages[calls++];
    await route.fulfill({status:413,contentType:'application/json',body:JSON.stringify({error:{code:'limit_exceeded',message:'limit_exceeded',request_id:crypto.randomUUID(),command_id:body.command_id,resource_id:null,current_revision:null,outcome:'unchanged',fields:[{path:'/selected_run_ids',code:calls===1?'expanded_bytes_limit':'pending_requests_limit',message:text,element_ref:null}]}})});
  });
  await action(page,'Review record').click();await expect(panel(page).getByRole('alert')).toContainText(messages[0]);
  await expect(action(page,'Check original export command')).toHaveCount(0);await expect(action(page,'Review again')).toBeEnabled();
  await capture(page,'export-size-limit-light');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  await action(page,'Review again').click();await expect(panel(page).getByRole('alert')).toContainText(messages[1]);
  await expect(panel(page).getByRole('alert')).not.toContainText('32 MiB');
  await capture(page,'export-queue-limit-dark');
  expect((await(await control(page,'evidence')).json()).requests).toHaveLength(0);expect(calls).toBe(2);
});


test('@export failed queued request retains actionable limit diagnosis',async({page})=>{
  await openRecord(page);await action(page,'Review record').click();await expect(panel(page)).toContainText('Queued');
  await page.route('**/computational-records/*',async route=>{
    const response=await route.fetch();const body=await response.json();
    body.data.state='failed';body.data.error={code:'limit_exceeded',status:413,current_revision:null,outcome:'unchanged',fields:[{path:'/selected_run_ids',code:'expanded_bytes_limit',message:'Selected runs and their required records exceed the 32 MiB expanded export limit. Export fewer runs. If one run still exceeds the limit, its complete record cannot currently be exported; required computational ancestors cannot be omitted.',element_ref:null}]};
    await route.fulfill({response,json:body});
  });
  await expect(panel(page).getByRole('alert')).toContainText('32 MiB expanded export limit');
  await expect(panel(page).getByRole('status')).toContainText('Export failed');await expect(action(page,'Review again')).toBeEnabled();
  await expect(action(page,'Create record export')).toHaveCount(0);await expect(action(page,'Download record export')).toHaveCount(0);
  expect((await(await control(page,'evidence')).json()).requests).toHaveLength(1);
});
