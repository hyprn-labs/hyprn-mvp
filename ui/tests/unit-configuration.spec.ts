import {mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import { test, expect, chromium, type Page } from 'playwright/test';
import { chromiumExecutable } from './support/browser';
let pageErrors:string[]=[];
test.beforeEach(async({page})=>{pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));});
test.afterEach(()=>expect(pageErrors).toEqual([]));

async function model(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', {name:'Sign in',exact:true}).click();
  await page.getByRole('button', {name:'New study',exact:true}).click();
  await page.getByLabel('New study name',{exact:true}).fill('Unit authoring');
  await page.getByRole('button', {name:'Create study',exact:true}).click();
  await page.getByRole('button', {name:'Models',exact:true}).click();
  await page.getByRole('button', {name:'New model',exact:true}).click();
  await page.getByLabel('New model name').fill('Compound quantities');
}
async function create(page: Page) {
  await model(page);
  await page.getByRole('button',{name:'Create model',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Compound quantities',exact:true})).toBeVisible();
}
async function component(page: Page) {
  await create(page);
  await page.getByRole('button',{name:'＋ Component',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Add component',exact:true});
  await dialog.getByLabel('New component name').fill('Energy law');
  await dialog.getByLabel('Input symbols').fill('x');
  await dialog.getByLabel('Output symbols').fill('y');
  await dialog.getByRole('button',{name:'Add component',exact:true}).click();
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByText('Component added',{exact:true})).toBeVisible();
}
async function ports(page: Page) {
  await page.getByRole('button',{name:'Component actions',exact:true}).first().click();
  await page.getByRole('button',{name:'Manage quantities',exact:true}).click();
  return page.getByRole('dialog',{name:'Manage quantities',exact:true});
}
/** A quantity definition saves the model in the current format (Model4), which new
 * configurations require. */
async function defineQuantity(edit: ReturnType<Page['getByRole']>) {
  await edit.getByLabel('Quantity 1 definition',{exact:true}).fill('Specific energy supplied to the law');
}
async function closePorts(page: Page) { await page.keyboard.press('Escape'); }
async function save(page: Page) {
  await page.getByRole('button',{name:'Save component',exact:true}).click();
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByText('Component saved',{exact:true})).toBeVisible();
}
const ids=(page:Page)=> {const hash=new URLSearchParams(new URL(page.url()).hash.slice(1));return {sid:hash.get('study')!,mid:hash.get('model')!};};
async function snapshot(page:Page) {const {sid,mid}=ids(page);return (await (await page.request.get('/api/1/studies/'+sid+'/models/'+mid)).json()).data;}
const activePorts=(m:any)=>m.definitions.find((d:any)=>d.definition_version_id===m.instances[1].definition_version_id).ports;


async function configuration(page: Page,outputUnits = 'J/kg',beforeConfiguration?:()=>Promise<void>) {
  await component(page); const edit=await ports(page);
  for(const n of [1,2]) {await edit.getByLabel(`Quantity ${n} units`,{exact:true}).selectOption('physical');await edit.getByLabel(`Quantity ${n} units spelling`,{exact:true}).fill(n===2 ? outputUnits : 'J/kg');}
  await defineQuantity(edit);await closePorts(page);await save(page);await beforeConfiguration?.();
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Unit configuration');
  await page.getByLabel('Energy law · x value',{exact:true}).fill('2');
  await page.getByLabel('Energy law · x provenance',{exact:true}).fill('Explicit engineering input');
}
async function physical(page: Page,label:string,value:string) {
  await page.getByLabel(label,{exact:true}).selectOption('physical');
  await page.getByLabel(label+' spelling',{exact:true}).fill(value);
}
test('@units-configuration explicit input units use the public catalog; configuration 6 carries no criteria',async({page})=>{
  await configuration(page);
  await expect(page.getByLabel('Energy law · x units',{exact:true})).toHaveValue('unspecified');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'Choose Dimensionless or physical units'})).toBeVisible();
  await physical(page,'Energy law · x units','MJ/kg');
  // Criteria belong to the study brief; the configuration editor authors none.
  await expect(page.locator('.configuration-criterion')).toHaveCount(0);
  await expect(page.locator('.configuration-criterion').getByRole('button')).toHaveCount(0);
  const request=page.waitForRequest(r=>r.method()==='POST' && /configurations\/preview$/.test(new URL(r.url()).pathname));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const body=(await request).postDataJSON();expect(body.schema_version).toBe('6');
  expect(body.inputs[0].units).toBe('MJ/kg');expect(body.inputs[0].value).toBe(2);
  expect(body).not.toHaveProperty('criteria');expect(body).not.toHaveProperty('approach_selection');
  await expect(page.getByRole('button',{name:'Create new version',exact:true})).toBeVisible();
});

test('@units-configuration invalid spelling, incompatible proof and catalog outage keep local edits',async({page})=>{
  await configuration(page);const {sid,mid}=ids(page);await physical(page,'Energy law · x units','USD');
  await expect(page.getByRole('alert').filter({hasText:'This unit spelling is not supported'})).toBeVisible();
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByLabel('Energy law · x units spelling',{exact:true})).toHaveValue('USD');
  await page.getByLabel('Energy law · x units spelling',{exact:true}).fill('m');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'incompatible'}).first()).toBeVisible();
  await page.getByLabel('Energy law · x units spelling',{exact:true}).fill('MJ/kg');
  await page.getByRole('button',{name:'Discard configuration changes',exact:true}).click();
  await page.getByRole('button',{name:'Return to all configurations',exact:true}).click();
  await page.evaluate(({sid,mid})=>{location.hash=new URLSearchParams({v:'1',study:sid,model:mid,view:'model'}).toString();},{sid,mid});
  await expect(page.getByRole('heading',{name:'Compound quantities',exact:true})).toBeVisible();
  await page.route('**/unit-catalog',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'backend_unavailable',message:'Unavailable',fields:[],outcome:'unchanged'}})}));
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Retained during outage');
  await expect(page.getByText(/Unit guidance is unavailable/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeDisabled();
  await page.unroute('**/unit-catalog');await page.getByRole('button',{name:'Retry unit guidance',exact:true}).click();
  await expect(page.getByLabel('Energy law · x units',{exact:true})).toBeEnabled();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Retained during outage');
});

test('@units-configuration incomplete immutable version identifies and opens exact active quantity',async({page})=>{
  await component(page);await page.getByRole('button',{name:'Save model version',exact:true}).click();
  const version=await page.getByLabel('Model version',{exact:true}).locator('option').nth(1).getAttribute('value');
  await page.getByLabel('Model version',{exact:true}).selectOption(version!);
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'units are not specified'})).toBeVisible();
  await page.getByText('Units incomplete',{exact:true}).click();await page.getByRole('button',{name:'View quantity',exact:true}).first().click();
  await expect(page.getByLabel('Model version',{exact:true})).toHaveValue(version!);
  // View quantity opens the exact read-only version with that quantity selected; the component's
  // quantities table shows its units, where every incomplete row reads Not specified.
  await expect(page.locator('.selection-inspector')).toContainText('Energy law');
  await page.getByRole('tab',{name:'Quantities',exact:true}).click();
  const table=page.getByRole('table',{name:'Quantities',exact:true});
  const row=(symbol:string)=>table.locator('tr[data-variable]').filter({has:page.locator('th code',{hasText:new RegExp('^'+symbol+'$')})});
  await expect(table.locator('tr[aria-selected="true"]')).toHaveCount(1);
  await expect(row('x')).toHaveAttribute('aria-selected','true');
  for(const symbol of ['x','y']){await expect(row(symbol)).toHaveCount(1);await expect(row(symbol).locator('td.unit')).toHaveText('Not specified');}
  await expect(page.getByRole('button',{name:'Save component',exact:true})).toHaveCount(0);
});

test('@units-configuration explicit dimensionless retains historical empty strings on copied configurations',async({page})=>{
  await component(page);const edit=await ports(page);
  for(const n of [1,2])await edit.getByLabel(`Quantity ${n} units`,{exact:true}).selectOption('dimensionless');
  await defineQuantity(edit);await closePorts(page);await save(page);await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Dimensionless configuration');
  await page.getByLabel('Energy law · x value',{exact:true}).fill('0');await page.getByLabel('Energy law · x provenance',{exact:true}).fill('Explicit zero');
  await page.getByLabel('Energy law · x units',{exact:true}).selectOption('dimensionless');
  const response=page.waitForResponse(r=>r.request().method()==='POST' && /configurations$/.test(new URL(r.url()).pathname));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const frozen=(await (await response).json()).data;expect(frozen.configuration.inputs[0].units).toBe('');expect(frozen.configuration.inputs[0].value).toBe(0);
  await expect(page.getByLabel('Energy law · x value',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  await expect(page.getByLabel('Energy law · x units',{exact:true})).toHaveValue('dimensionless');
  await expect(page.getByLabel('Energy law · x value',{exact:true})).toHaveValue('0');
  await page.getByLabel('Energy law · x value',{exact:true}).fill('2');
  const revisedResponse=page.waitForResponse(r=>r.request().method()==='POST' && /configurations$/.test(new URL(r.url()).pathname));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const revised=(await (await revisedResponse).json()).data;
  expect(revised.configuration.configuration_revision_id).not.toBe(frozen.configuration.configuration_revision_id);
  expect(revised.configuration.inputs[0].value).toBe(2);
  const original=await page.request.get(`/api/1/studies/${frozen.configuration.study_id}/configurations/${frozen.configuration.configuration_revision_id}`);
  expect((await original.json()).data).toEqual(frozen);
});

test('@units-configuration source units, conversion proof and the modified-run seed retain exact saved strings',async({page})=>{
  await configuration(page,'MJ/kg');await physical(page,'Energy law · x units','MJ/kg');
  const saved=page.waitForResponse(r=>r.request().method()==='POST' && /configurations$/.test(new URL(r.url()).pathname));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const response=await saved;expect(response.status()).toBe(201);const frozen=(await response.json()).data;
  const sid=frozen.configuration.study_id;
  const retained=await page.request.post('/fixture/retain',{data:{study_id:sid,configuration_revision_id:frozen.configuration.configuration_revision_id}});
  expect(retained.ok()).toBe(true);const rid=(await retained.json()).run_id;
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  await expect(page.getByLabel('Energy law · x units spelling',{exact:true})).toHaveValue('MJ/kg');
  await page.getByRole('button',{name:'Use a run result',exact:true}).click();
  const picker=page.getByRole('dialog',{name:'Use a run result for Energy law · x',exact:true});
  await expect(picker.getByText('7 MJ/kg',{exact:true})).toBeVisible();
  const outcomes=picker.getByLabel('Run outcomes',{exact:true}).first();
  await expect(outcomes).toContainText('Execution Completed');await expect(outcomes.locator('.hf-tag')).toHaveCount(2);
  await expect(picker).not.toContainText('Applicability');
  await picker.getByRole('button',{name:'Use this result · Energy law · y',exact:true}).click();
  await expect(page.getByText('Original source: 7 MJ/kg',{exact:true})).toBeVisible();
  await expect(page.getByText('In model units: × 1000000 → 7000000 J/kg',{exact:true})).toBeVisible();
  await expect(page.getByLabel('Energy law · x value',{exact:true})).toHaveValue('7');
  await page.getByRole('button',{name:'Discard configuration changes',exact:true}).click();
  await page.goto(`/ui/#v=1&view=runs&study=${sid}&run=${rid}`);
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await expect(page.getByLabel('Energy law · x units spelling',{exact:true})).toHaveValue('MJ/kg');
  const request=page.waitForRequest(r=>r.method()==='POST' && /configurations\/preview$/.test(new URL(r.url()).pathname));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const candidate=(await request).postDataJSON();expect(candidate.schema_version).toBe('6');expect(candidate.inputs[0].units).toBe('MJ/kg');expect(candidate).not.toHaveProperty('criteria');
  await expect(page.getByRole('dialog',{name:'Review modified run',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save modified configuration',exact:true}).click();
  await expect(page.getByRole('button',{name:'Create new version',exact:true})).toBeVisible();
});

test('@units-configuration light dark narrow and actual 200 percent zoom preserve keyboard controls',async({baseURL})=>{
  test.setTimeout(120000);
  const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/units-zoom-extension');
  await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Units zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/units-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try {
    const page=context.pages()[0]??await context.newPage();page.on('pageerror',e=>pageErrors.push(e.message));await configuration(page);await physical(page,'Energy law · x units','MJ/kg');
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');
    async function resize(width:number,height:number) {const before=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));const actual=(await cdp.send('Browser.getWindowBounds',{windowId:info.windowId})).bounds;await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:actual.width!+width-before.width,height:actual.height!+height-before.height}});await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(width);}
    async function capture(name:string) {
      await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
      // Flush styles and bound the wait for visible Foundry transitions.
      await expect.poll(()=>page.locator('.hf-btn:visible').evaluateAll(items=>items.every(item=>{
        getComputedStyle(item).backgroundColor;
        return item.getAnimations().every(a=>a.playState!=='running');
      }))).toBe(true);
      const buttons=await page.locator('.hf-btn:visible').evaluateAll(items=>items.map(item=>{
        const style=getComputedStyle(item);return {text:item.textContent,background:style.backgroundColor,color:style.color,animations:item.getAnimations().map(a=>a.playState)};
      }));
      for(const button of buttons)expect(button.animations).not.toContain('running');
      const size=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));
      expect(size.scrollWidth).toBeLessThanOrEqual(size.width+1);
      const fields=await page.locator('td input').evaluateAll(inputs=>inputs.map(input=>{const a=input.getBoundingClientRect(),b=input.closest('td')!.getBoundingClientRect();return {label:input.getAttribute('aria-label'),left:a.left,right:a.right,cellLeft:b.left,cellRight:b.right};}));
      for(const field of fields){expect(field.left).toBeGreaterThanOrEqual(field.cellLeft);expect(field.right).toBeLessThanOrEqual(field.cellRight+1);}
      geometry.push({name,buttons,...size,fields});
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));
    }
    await resize(1440,1000);
    for(const theme of ['light','dark']) {
      await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.getByLabel('Energy law · x units spelling',{exact:true}).scrollIntoViewIfNeeded();await capture('units-configuration-'+theme);
    }
    await resize(600,900);await page.getByLabel('Energy law · x units spelling',{exact:true}).scrollIntoViewIfNeeded();await capture('units-configuration-narrow');await resize(1440,1000);
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    for(const theme of ['light','dark']) {
      await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
      const intent=page.getByLabel('Energy law · x units',{exact:true});await intent.focus();await page.keyboard.press('Tab');await expect(page.getByLabel('Energy law · x units spelling',{exact:true})).toBeFocused();await capture('units-configuration-200-'+theme);
      // An unsupported spelling stays readable and keyboard-correctable at 200 percent.
      const spelling=page.getByLabel('Energy law · x units spelling',{exact:true});await spelling.fill('USD');const unsupported=page.getByRole('alert').filter({hasText:'This unit spelling is not supported'});await unsupported.scrollIntoViewIfNeeded();await expect(unsupported).toBeVisible();await capture('units-configuration-error-200-'+theme);await spelling.fill('MJ/kg');await expect(unsupported).toHaveCount(0);await expect(spelling).toBeFocused();
      await page.getByRole('button',{name:'Save configuration',exact:true}).focus();await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeFocused();
    }
    await writeFile(join(root,'evidence/units-native-zoom.json'),JSON.stringify({zoom:2,viewport:null,geometry},null,2));
  } finally {await context.close();}
});


test('@units-configuration current catalog revocation clears protected configuration',async({page})=>{
  let release!:()=>void;const pending=new Promise<void>(resolve=>release=resolve);let arrived=false;
  await configuration(page,'J/kg',async()=>{await page.route('**/unit-catalog',async route=>{arrived=true;await pending;await route.continue();},{times:1});});
  await expect.poll(()=>arrived).toBe(true);const sid=ids(page).sid;
  expect((await page.request.post('/fixture/revoke',{data:{study_id:sid}})).ok()).toBe(true);release();
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveCount(0);
});
