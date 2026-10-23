import {mkdir, writeFile, readFile} from 'node:fs/promises';
import {join} from 'node:path';
import { test, expect, chromium, type Page } from 'playwright/test';
import { chromiumExecutable } from './support/browser';

async function model(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', {name:'Sign in',exact:true}).click();
  await page.getByRole('button', {name:'New study',exact:true}).click();
  await page.getByLabel('Study name',{exact:true}).fill('Unit authoring');
  await page.getByLabel('Study question', { exact: true })
    .fill('What must this engineering study establish?');
  await page.getByRole('button', {name:'Create study',exact:true}).click();
  await page.getByRole('button', {name:'Models',exact:true}).click();
  await page.getByRole('button', {name:'New model',exact:true}).click();
  await page.getByLabel('New model name').fill('Compound quantities');
}
test('@units-authoring negotiates explicit new-model protocol', async ({page})=>{
  await model(page);
  const request=page.waitForRequest(r=>r.method()==='POST' && /\/models$/.test(new URL(r.url()).pathname));
  await page.getByRole('button',{name:'Create model',exact:true}).click();
  expect((await request).postDataJSON().schema_version).toBe('3');
});

for (const response of ['success', 'refusal'] as const) {
  test('@units-authoring keeps component inputs through catalog ' + response, async ({page}) => {
    await model(page);
    await expect(page.getByRole('button', {name: 'Create model', exact: true})).toBeEnabled();
    let release!: () => void;
    const pending = new Promise<void>(resolve => release = resolve);
    let arrived = false;
    await page.route('**/unit-catalog', async route => {
      arrived = true;
      await pending;
      if (response === 'refusal') {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({error: {
            code: 'modeling_unavailable',
            message: 'Unit guidance is unavailable',
            fields: [],
            outcome: 'unchanged',
          }}),
        });
      } else {
        await route.continue();
      }
    }, {times: 1});
    try {
      await page.getByRole('button', {name: 'Create model', exact: true}).click();
      await expect.poll(() => arrived).toBe(true);
      await page.getByRole('button', {name: '＋ Component', exact: true}).click();
      const dialog = page.getByRole('dialog', {name: 'Add component', exact: true});
      await dialog.getByLabel('New component name').fill('Energy law');
      await dialog.getByLabel('Input symbols').fill('x');
      await dialog.getByLabel('Output symbols').fill('y');
      const add = dialog.getByRole('button', {name: 'Add component', exact: true});
      await expect(dialog.getByRole('status')).toHaveText('Loading unit guidance…');
      await expect(add).toBeDisabled();
      release();
      if (response === 'refusal') {
        await expect(dialog.getByRole('alert')).toContainText('Unit guidance is unavailable');
        await expect(add).toBeDisabled();
        await dialog.getByRole('button', {name: 'Retry unit guidance', exact: true}).click();
      }
      await expect(add).toBeEnabled();
      await expect(dialog.getByLabel('New component name')).toHaveValue('Energy law');
      await expect(dialog.getByLabel('Input symbols')).toHaveValue('x');
      await expect(dialog.getByLabel('Output symbols')).toHaveValue('y');
      await add.click();
      await page.getByRole('button', {name: 'Apply changes', exact: true}).click();
      await expect(page.getByText('Component added', {exact: true})).toBeVisible();
      const guidanceError = page.getByRole('alert').filter({
        hasText: 'Unit guidance is unavailable',
      });
      await expect(guidanceError).toHaveCount(0);
    } finally {
      release();
    }
  });
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
async function closePorts(page: Page) { await page.keyboard.press('Escape'); }
async function save(page: Page) {
  await page.getByRole('button',{name:'Save component',exact:true}).click();
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByText('Component saved',{exact:true})).toBeVisible();
}
const ids=(page:Page)=> {const hash=new URLSearchParams(new URL(page.url()).hash.slice(1));return {sid:hash.get('study')!,mid:hash.get('model')!};};
async function snapshot(page:Page) {const {sid,mid}=ids(page);return (await (await page.request.get('/api/1/studies/'+sid+'/models/'+mid)).json()).data;}
const activePorts=(m:any)=>m.definitions.find((d:any)=>d.definition_version_id===m.instances[1].definition_version_id).ports;

test('@units-authoring new ports remain unspecified in saved drafts and read-only versions; configurations blocked',async({page})=>{
  await component(page);
  const draft=await snapshot(page);expect(activePorts(draft).map((p:any)=>p.units)).toEqual([{kind:'unspecified'},{kind:'unspecified'}]);
  const edit=await ports(page);await expect(edit.getByLabel('Quantity 1 units',{exact:true})).toHaveValue('unspecified');await closePorts(page);
  await page.getByRole('button',{name:'Save model version',exact:true}).click();
  await expect(page.getByText('Model version saved · units incomplete. Resolve units in the listed active components before creating a configuration.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'units are not specified'})).toBeVisible();
  const version=await page.getByLabel('Model version',{exact:true}).locator('option').nth(1).getAttribute('value');
  let release!:()=>void,arrived=false;
  const held=new Promise<void>(resolve=>release=resolve);
  await page.route(/\/models\/[^/]+\/revisions(?:\?.*)?$/,async route=>{
    arrived=true;await held;await route.continue();
  },{times:1});
  try {
    await page.getByLabel('Model version',{exact:true}).selectOption(version!);
    await expect.poll(()=>arrived).toBe(true);
    await expect(page.getByText('Read-only',{exact:true}).first()).toBeVisible();
    await expect(page.getByText('Loading study/model…',{exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Create configuration',exact:true})).toBeDisabled();
    await expect(page.getByLabel('Model version',{exact:true})).toBeDisabled();
  } finally {release();}
  await expect(page.getByLabel('Model version',{exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'units are not specified'})).toBeVisible();
  await expect(page.getByLabel('Model version',{exact:true})).toBeEnabled();
  await expect(page.getByText('Loading study/model…',{exact:true})).toHaveCount(0);
  const {sid,mid}=ids(page);
  const retained=(await(await page.request.get('/api/1/studies/'+sid+'/models/'+mid+'/revisions/'+version)).json()).data;
  expect(activePorts(retained).map((p:any)=>p.units)).toEqual([{kind:'unspecified'},{kind:'unspecified'}]);
  await page.getByLabel('Model version',{exact:true}).selectOption('draft');
  await expect.poll(async()=>activePorts(await snapshot(page)).map((p:any)=>p.units)).toEqual([{kind:'unspecified'},{kind:'unspecified'}]);
});

test('@units-authoring catalog choices save explicit dimensionless and compound spelling; invalid text and dirty navigation survive',async({page})=>{
  await component(page);const edit=await ports(page);
  await edit.getByLabel('Quantity 1 units',{exact:true}).selectOption('dimensionless');
  await edit.getByLabel('Quantity 2 units',{exact:true}).selectOption('physical');
  const spelling=edit.getByLabel('Quantity 2 units spelling',{exact:true});
  await spelling.fill('EUR');
  await expect(edit.getByRole('alert')).toContainText('This unit spelling is not supported');
  await closePorts(page);await page.getByRole('button',{name:'Save component',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'This unit spelling is not supported'})).toBeVisible();
  await page.getByRole('button',{name:'Return to all models',exact:true}).click();
  await page.getByRole('dialog',{name:'Unsaved changes',exact:true}).getByRole('button',{name:'Keep editing',exact:true}).click();
  const again=await ports(page);await expect(again.getByLabel('Quantity 2 units spelling',{exact:true})).toHaveValue('EUR');
  await again.getByLabel('Quantity 2 units spelling',{exact:true}).fill('MJ/kg');await closePorts(page);await save(page);
  expect(activePorts(await snapshot(page)).map((p:any)=>p.units)).toEqual([{kind:'dimensionless'},{kind:'physical',expression:'MJ/kg'}]);
  const reopened=await ports(page);await expect(reopened.getByLabel('Quantity 2 units spelling',{exact:true})).toHaveValue('MJ/kg');
});

test('@units-authoring unavailable negotiation never downgrades and retry keeps model name',async({page})=>{
  await page.route('**/unit-catalog',route=>route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({error:{code:'unsupported_capability',message:'Typed units unavailable',fields:[],outcome:'unchanged'}})}));
  await model(page);await expect(page.getByRole('button',{name:'Create model',exact:true})).toBeDisabled();
  await expect(page.getByText(/Unit guidance is unavailable/)).toBeVisible();await expect(page.getByLabel('New model name')).toHaveValue('Compound quantities');
  await page.unroute('**/unit-catalog');await page.getByRole('button',{name:'Retry unit guidance',exact:true}).click();
  await expect(page.getByRole('button',{name:'Create model',exact:true})).toBeEnabled();
});

test('@units-authoring preview refusal and stale revision preserve source and unit text',async({page})=>{
  await component(page);const edit=await ports(page);await edit.getByLabel('Quantity 1 units',{exact:true}).selectOption('physical');await edit.getByLabel('Quantity 1 units spelling',{exact:true}).fill('m');await closePorts(page);
  await page.route('**/models/*/preview',route=>route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({error:{code:'incompatible_units',message:'Connected quantities have incompatible units. Your edits are kept.',fields:[],outcome:'unchanged'}})}),{times:1});
  await page.getByRole('button',{name:'Save component',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'incompatible units'})).toBeVisible();
  await page.getByRole('button',{name:'Keep editing',exact:true}).click();
  const again=await ports(page);await expect(again.getByLabel('Quantity 1 units spelling',{exact:true})).toHaveValue('m');await closePorts(page);
  await page.route('**/models/*/preview',route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:{code:'stale_revision',message:'Draft changed',fields:[],outcome:'unchanged'}})}),{times:1});
  await page.getByRole('button',{name:'Save component',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Your edits are preserved'})).toBeVisible();
  await page.getByRole('button',{name:'Keep editing',exact:true}).click();await ports(page);await expect(page.getByLabel('Quantity 1 units spelling',{exact:true})).toHaveValue('m');
});

test('@units-authoring lost acknowledgement keeps exact typed receipt and reloads committed result',async({page})=>{
  await component(page);const edit=await ports(page);await edit.getByLabel('Quantity 1 units',{exact:true}).selectOption('dimensionless');await closePorts(page);
  let original:any;await page.route('**/models/*/edits',async route=>{original=route.request().postDataJSON();await route.fetch();await route.abort();},{times:1});
  await page.getByRole('button',{name:'Save component',exact:true}).click();await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByText(/Command outcome is uncertain/).first()).toBeVisible();expect(original.schema_version).toBe('5');
  await page.getByRole('button',{name:'Keep editing',exact:true}).click();
  await page.getByRole('button',{name:'Check original command',exact:true}).click();
  await expect.poll(async()=>activePorts(await snapshot(page))[0].units).toEqual({kind:'dimensionless'});
  const {sid}=ids(page),receipt=(await(await page.request.get('/api/1/studies/'+sid+'/commands/'+original.command_id+'?category=model')).json()).data;
  expect(receipt.state).toBe('committed');expect(receipt.command_id).toBe(original.command_id);
});

test('@units-authoring light dark narrow and genuine 200 percent zoom preserve keyboard editing',async({baseURL})=>{
  test.setTimeout(120000);
  const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/units-zoom-extension');
  await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Units zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/units-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try {
    const page=context.pages()[0]??await context.newPage();await component(page);
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
      expect(size.scrollWidth).toBeLessThanOrEqual(size.width+1);geometry.push({name,buttons,...size});
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));
    }
    await resize(1440,1000);
    for(const theme of ['light','dark']) {
      await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await capture('units-workbench-'+theme);
      const edit=await ports(page);await edit.getByLabel('Quantity 1 units',{exact:true}).selectOption('dimensionless');await edit.getByLabel('Quantity 2 units',{exact:true}).selectOption('physical');await edit.getByLabel('Quantity 2 units spelling',{exact:true}).fill('kg/m**3');await capture('units-editor-'+theme);await closePorts(page);
    }
    await resize(600,900);await ports(page);await capture('units-editor-narrow');await closePorts(page);await resize(1440,1000);
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    for(const theme of ['light','dark']) {
      await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
      const button=page.getByRole('button',{name:'Component actions',exact:true}).first();await button.focus();await button.press('Enter');
      const manage=page.getByRole('button',{name:'Manage quantities',exact:true});await manage.focus();await manage.press('Enter');
      const edit=page.getByRole('dialog',{name:'Manage quantities',exact:true}),intent=edit.getByLabel('Quantity 1 units',{exact:true});
      await intent.focus();await page.keyboard.press('Tab');await expect(edit.getByRole('button',{name:'Remove quantity 1',exact:true})).toBeFocused();
      await edit.getByLabel('Quantity 2 units spelling',{exact:true}).fill('unsupported long unit spelling');
      await edit.getByRole('alert').scrollIntoViewIfNeeded();await capture('units-editor-error-200-'+theme);
      await edit.getByLabel('Quantity 2 units spelling',{exact:true}).fill('kg/m**3');
      await edit.getByRole('button',{name:'Remove quantity 2',exact:true}).scrollIntoViewIfNeeded();await capture('units-editor-200-'+theme);await page.keyboard.press('Escape');await expect(button).toBeFocused();
    }
    await writeFile(join(root,'evidence/units-native-zoom.json'),JSON.stringify({zoom:2,viewport:null,geometry},null,2));
  } finally {await context.close();}
});

test('@units-authoring revoked catalog clears protected state; stale catalog failures cannot clear a later view',async({page})=>{
  let release!:()=>void;const wait=new Promise<void>(resolve=>release=resolve);let arrived=false;
  await page.route('**/unit-catalog',async route=>{arrived=true;await wait;await route.continue();},{times:1});
  await model(page);await expect.poll(()=>arrived).toBe(true);
  const sid=ids(page).sid;expect((await page.request.post('/fixture/revoke',{data:{study_id:sid}})).ok()).toBe(true);release();
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
  await expect(page.getByText('Compound quantities',{exact:true})).toHaveCount(0);
  let releaseStale!:()=>void;const stale=new Promise<void>(resolve=>releaseStale=resolve);
  await page.route('**/unit-catalog',async route=>{await stale;await route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({error:{code:'resource_not_found',message:'Unavailable',fields:[],outcome:'unchanged'}})});},{times:1});
  await model(page);await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByRole('button',{name:'Home',exact:true}).click();releaseStale();
  await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toHaveCount(0);
});

test('@units-authoring shared labels preserve old strings and resolve only exact active versions',async({page})=>{
  await page.goto('/ui/');
  const result=await page.evaluate(()=>{
    const h=(window as any).unitLabels;
    return {
      labels:['','m',{kind:'unspecified'},{kind:'dimensionless'},{kind:'physical',expression:'g/cm**3'}].map(h.unitLabel),
      resolved:[h.resolvedUnit(''),h.resolvedUnit({kind:'unspecified'})??null,h.resolvedUnit({kind:'physical',expression:'MJ/kg'})],
      issues:h.unresolvedModelUnits({instances:[{instance_id:'one',definition_version_id:'v1',name:'First'},{instance_id:'two',definition_version_id:'v2',name:'Second'}],definitions:[{definition_version_id:'v0',ports:[{port_id:'unused',name:'Unused',units:{kind:'unspecified'}}]},{definition_version_id:'v1',ports:[{port_id:'same',name:'Input',units:''}]},{definition_version_id:'v2',ports:[{port_id:'same',name:'Input',units:{kind:'unspecified'}}]}]})
    };
  });
  expect(result.labels).toEqual(['Dimensionless','m','Not specified','Dimensionless','g/cm**3']);
  expect(result.resolved).toEqual(['',null,'MJ/kg']);
  expect(result.issues).toEqual([{instance_id:'two',definition_version_id:'v2',port_id:'same',component:'Second',quantity:'Input'}]);
});

test('@units-authoring editor guard refused editor save keeps unit text and focuses the source editor',async({page})=>{
  await component(page);const edit=await ports(page);
  await edit.getByLabel('Quantity 1 units',{exact:true}).selectOption('physical');await edit.getByLabel('Quantity 1 units spelling',{exact:true}).fill('EUR');await closePorts(page);
  // The source editor sits in the component's "Edit source" disclosure (no detail tabs);
  // a refused save opens it and focuses the editor.
  await expect(page.getByRole('tab',{name:'Source',exact:true})).toHaveCount(0);
  const dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true});
  await page.getByRole('button',{name:'Return to all models',exact:true}).click();await dirty.getByRole('button',{name:'Save changes',exact:true}).click();
  await expect(dirty).toBeHidden();await expect(page.locator('#python-source')).toBeFocused();
  await expect(page.getByRole('heading',{name:'Compound quantities',exact:true})).toBeVisible();
  const again=await ports(page);await expect(again.getByLabel('Quantity 1 units spelling',{exact:true})).toHaveValue('EUR');
});

test('@units-authoring editor guard Save applies a pending component edit once and skips the separate editor save',async({page})=>{
  await component(page);const {sid,mid}=ids(page),read=async()=>(await (await page.request.get('/api/1/studies/'+sid+'/models/'+mid)).json()).data;
  const quantities=await ports(page);
  await quantities.getByLabel('Quantity 1 name',{exact:true}).fill('Renamed input');
  await closePorts(page);
  const writes:unknown[]=[];page.on('request',r=>{if(r.method()==='POST'&&/\/models\/[^/]+\/edits$/.test(new URL(r.url()).pathname))writes.push(r.postDataJSON());});
  const dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true});
  await page.getByRole('button',{name:'Return to all models',exact:true}).click();await dirty.getByRole('button',{name:'Save changes',exact:true}).click();
  const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});await preview.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Models',exact:true})).toBeVisible();
  expect(writes).toHaveLength(1);
  expect(activePorts(await read())[0].name).toBe('Renamed input');
});

test('@units-authoring monetary basis follows an explicit USD to kUSD successor and preserves history',async({page})=>{
  await component(page);
  const {sid,mid}=ids(page),base=`/api/1/studies/${sid}/models/${mid}`;
  const seeded=await page.request.post('/fixture/price-evidence',{data:{study_id:sid}});
  expect(seeded.ok(),await seeded.text()).toBe(true);
  const evidence=await seeded.json();
  const edit=await ports(page);
  await edit.getByLabel('Quantity 1 units',{exact:true}).selectOption('dimensionless');
  await edit.getByLabel('Quantity 2 units',{exact:true}).selectOption('physical');
  await edit.getByLabel('Quantity 2 units spelling',{exact:true}).fill('USD');
  await edit.getByLabel('Quantity 2 definition',{exact:true}).fill('Quoted installed equipment cost');
  await closePorts(page);await save(page);
  const original=await snapshot(page);expect(original.schema_version).toBe('5');
  const target={instance_id:original.instances[1].instance_id,port_id:activePorts(original)[1].port_id};
  async function saveVersion() {
    const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===base+'/commits');
    await page.getByRole('button',{name:'Save model version',exact:true}).click();
    const result=await response;expect(result.ok(),await result.text()).toBe(true);
    return (await result.json()).data.model_revision_id as string;
  }
  async function publishBasis(version:string,year:string,basis:string,changed=false) {
    await page.getByRole('tab',{name:'Model explanation',exact:true}).click();
    await page.getByRole('button',{name:'Edit explanation',exact:true}).click();
    const region=page.getByRole('region',{name:'Price basis · y',exact:true});
    if(changed) {
      await expect(region).toContainText('The unit changed. Enter the price basis for kUSD.');
      await expect(region.getByLabel('Price year · y',{exact:true})).toHaveValue('');
      await expect(region.getByLabel('Cost basis · y',{exact:true})).toHaveValue('');
      await expect(region).not.toContainText('Explicit price basis report');
    }
    await region.getByLabel('Price year · y',{exact:true}).fill(year);
    await region.getByLabel('Cost basis · y',{exact:true}).fill(basis);
    await region.getByRole('button',{name:'Add price evidence',exact:true}).click();
    const picker=page.getByRole('dialog',{name:'Add evidence to Price basis · y',exact:true});
    await picker.getByLabel('Find evidence',{exact:true}).fill('Explicit price basis report');
    await picker.getByRole('button',{name:/^Choose Explicit price basis report/}).click();
    await picker.getByLabel('Relationship',{exact:true}).selectOption('supports');
    await picker.getByRole('button',{name:'Attach evidence',exact:true}).click();
    await page.getByRole('button',{name:'Save for model version',exact:true}).click();
    const publish=page.getByRole('dialog',{name:'Save explanation version',exact:true});
    await publish.getByLabel('Model version to explain',{exact:true}).selectOption(version);
    await publish.getByRole('button',{name:'Save explanation version',exact:true}).click();
    await expect(publish).toBeHidden();
    const response=await page.request.get(base+`/revisions/${version}/explanation`);
    expect(response.ok(),await response.text()).toBe(true);
    return (await response.json()).data.explanation;
  }
  const firstVersion=await saveVersion();
  const exported=await page.request.get(base+'/export?model_revision_id='+firstVersion);
  expect(exported.ok(),await exported.text()).toBe(true);
  const portable=(await exported.json()).data;
  expect(portable.schema_version).toBe('5');
  expect(portable.revisions[0].model_revision_id).toBe(firstVersion);
  expect(activePorts(portable.revisions[0])[1].units).toEqual({kind:'physical',expression:'USD'});
  await page.getByLabel('Model version',{exact:true}).selectOption(firstVersion);
  await page.getByRole('button',{name:'Model actions',exact:true}).click();
  await page.getByRole('button',{name:'Export model',exact:true}).click();
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download portable model record',exact:true}).click();
  const downloaded=await readFile((await(await download).path())!,'utf8');
  expect(JSON.parse(downloaded)).toEqual(portable);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Import model',exact:true}).click();
  const importing=page.getByRole('dialog',{name:'Import model',exact:true});
  await importing.getByLabel('Portable model record file',{exact:true}).setInputFiles({name:'monetary-model.json',mimeType:'application/json',buffer:Buffer.from(downloaded)});
  await importing.getByRole('button',{name:'Preview model import',exact:true}).click();
  await expect(importing.getByRole('region',{name:'Model import preview',exact:true})).toContainText('This model already exists in this study.');
  await expect(importing.getByRole('button',{name:'Import model',exact:true})).toBeDisabled();
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  await page.getByLabel('Model version',{exact:true}).selectOption('draft');
  const first=await publishBasis(firstVersion,'2025','Installed equipment, quoted in USD, excluding tax.');
  expect(first.content.monetary_quantities).toEqual([{...target,catalogue_expression:'USD',price_year:2025,economic_basis:'Installed equipment, quoted in USD, excluding tax.',evidence_links:[{evidence_version_id:evidence.evidence_version_id,relation:'supports'}]}]);
  await page.getByRole('tab',{name:'Diagram',exact:true}).click();
  const successor=await ports(page);
  await successor.getByLabel('Quantity 2 units spelling',{exact:true}).fill('kUSD');
  await closePorts(page);await save(page);
  const secondVersion=await saveVersion();expect(secondVersion).not.toBe(firstVersion);
  const second=await publishBasis(secondVersion,'2026','Installed equipment, explicitly quoted in thousands of USD, excluding tax.',true);
  expect(second.content.monetary_quantities).toEqual([{...target,catalogue_expression:'kUSD',price_year:2026,economic_basis:'Installed equipment, explicitly quoted in thousands of USD, excluding tax.',evidence_links:[{evidence_version_id:evidence.evidence_version_id,relation:'supports'}]}]);
  const retained=(await(await page.request.get(base+`/revisions/${firstVersion}/explanation`)).json()).data.explanation;
  expect(retained).toEqual(first);
  await page.getByLabel('Model version',{exact:true}).selectOption(firstVersion);
  await page.getByRole('tab',{name:'Model explanation',exact:true}).click();
  await expect(page.getByRole('region',{name:'Price basis',exact:true})).toContainText('y · USD');
  await expect(page.getByRole('region',{name:'Price basis',exact:true})).toContainText('2025 prices');
});
