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
test('@units-reading preview distinguishes unspecified declarations',async({page})=>{
  await create(page);
  await page.getByRole('button',{name:'＋ Component',exact:true}).click();
  const add=page.getByRole('dialog',{name:'Add component',exact:true});
  await add.getByLabel('New component name').fill('Energy law');
  await add.getByLabel('Input symbols').fill('x');
  await add.getByLabel('Output symbols').fill('y');
  await add.getByRole('button',{name:'Add component',exact:true}).click();
  const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});
  await expect(preview.getByText('input: x · Not specified\noutput: y · Not specified',{exact:true})).toBeVisible();
});

type ReaderFixture = {study_id:string;model_id:string;producer_id:string;receiver_id:string;before:any;after:any};
async function seeded(page:Page,schema='3'):Promise<ReaderFixture> {
  await create(page);
  const hash=new URLSearchParams(new URL(page.url()).hash.slice(1));
  const response=await page.request.post('/fixture/read-model',{data:{study_id:hash.get('study'),model_id:hash.get('model'),schema}});
  expect(response.ok(),await response.text()).toBe(true);
  const fixture=await response.json();await openRevision(page,fixture);return fixture;
}
async function openRevision(page:Page,f:ReaderFixture) {
  await page.goto('/ui/#v=1&view=model&study='+f.study_id+'&model='+f.model_id+'&revision='+f.before.model_revision_id);
  await expect(page.getByText('Read-only model version',{exact:true}).first()).toBeVisible();
}
async function inspectXdsm(page:Page,symbol:string,label:string) {
  await page.getByRole('tab',{name:'XDSM',exact:true}).click();
  const select=page.getByRole('button',{name:symbol+' · free input',exact:true});
  const inspector=page.getByRole('region',{name:'Selection inspector',exact:true});
  await page.locator('#panel-XDSM').getByRole('button',{name:'Receiver',exact:true}).click();
  await expect(inspector.getByRole('heading',{name:'Receiver',exact:true})).toBeVisible();
  await select.focus();await expect(select).toBeFocused();await page.keyboard.press('Enter');
  await expect(inspector.getByRole('heading',{name:'Energy law',exact:true})).toBeVisible();
  // The Details panel has no ports table; the selected component's quantities are the
  // highlighted rows of the one quantities table below the canvas.
  await expect(inspector.locator('table')).toHaveCount(0);
  await expect(page.getByRole('table',{name:'Quantities',exact:true}).getByRole('row').filter({has:page.locator('code').filter({hasText:new RegExp('^'+symbol+'$')})})).toContainText(label);
}
for(const schema of ['1','2','3']) test('@units-reading exact schema '+schema+' tables graph XDSM and connection inspector',async({page})=>{
  const f=await seeded(page,schema),unknown=schema==='3'?'Not specified':'Dimensionless';
  await expect(page.getByRole('tab',{name:'Variables',exact:true})).toHaveCount(0);
  if(await page.getByRole('button',{name:'Show all quantities',exact:true}).isVisible())await page.getByRole('button',{name:'Show all quantities',exact:true}).click();
  const table=page.getByRole('table',{name:'Quantities',exact:true});
  for(const [symbol,label] of [['unknown',unknown],['ratio','Dimensionless'],['legacy','Dimensionless'],['speed','m/s'],['flow','m/s']]) {
    const row=table.getByRole('row').filter({has:page.locator('code').filter({hasText:new RegExp('^'+symbol+'$')})});
    await expect(row).toContainText(label);
  }
  await expect(table).not.toContainText('old_');await expect(table).not.toContainText('[object Object]');
  await page.getByRole('tab',{name:'Graph',exact:true}).click();
  for(const [symbol,label] of [['unknown',unknown],['ratio','Dimensionless'],['speed','m/s']]) {
    const port=page.locator('#panel-Graph .hf-node__port[title^="'+symbol+' · "]');
    await expect(port).toHaveAttribute('title',new RegExp(symbol+' · '+symbol+' · '+label.replace('/','\\/')));
  }
  await inspectXdsm(page,'unknown',unknown);await inspectXdsm(page,'ratio','Dimensionless');await inspectXdsm(page,'speed','m/s');
  await page.locator('#panel-XDSM').getByRole('button',{name:'1 connection flow → incoming',exact:true}).click();
  const inspector=page.getByRole('region',{name:'Selection inspector',exact:true});
  await expect(inspector.getByRole('button',{name:'Energy law · flow · m/s',exact:true})).toBeVisible();
  await expect(inspector.getByRole('button',{name:'Receiver · incoming · m/s',exact:true})).toBeVisible();
  expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('revision')).toBe(f.before.model_revision_id);
});
// This legacy fixture has no quantity definitions. Keep the honest notice and readable units.
async function portTableReadable(page: Page) {
  const table = page.getByRole('table', { name: 'Quantities', exact: true });
  const inspector = page.getByRole('region', { name: 'Selection inspector', exact: true });
  await expect(inspector.locator('table')).toHaveCount(0);
  await expect(table.getByRole('columnheader', { name: 'Definition', exact: true })).toHaveCount(0);
  await expect(page.getByText('No quantity definitions provided.', { exact: true })).toBeVisible();
  await expect(table.getByRole('columnheader', { name: 'Unit', exact: true })).toBeVisible();
  const rows = await table.locator('tbody td.unit').evaluateAll(cells => cells.map(cell => {
    const range = document.createRange();
    range.selectNodeContents(cell);
    return {
      text: cell.textContent,
      lines: range.getClientRects().length,
      fits: cell.scrollWidth <= cell.clientWidth,
      textRight: range.getBoundingClientRect().right,
      cellRight: cell.getBoundingClientRect().right,
    };
  }));
  expect(rows.length).toBe(4);
  expect(rows.map(row => row.text).sort()).toEqual([
    'Dimensionless', 'Not specified', 'm/s', 'm/s',
  ]);
  for (const row of rows) {
    expect(row.lines, JSON.stringify(row)).toBe(1);
    expect(row.fits, JSON.stringify(row)).toBe(true);
    expect(row.textRight, JSON.stringify(row)).toBeLessThanOrEqual(row.cellRight + 1);
  }
  return rows;
}
async function approachPicker(page:Page,f:ReaderFixture) {
  await page.goto('/ui/#v=1&view=approach&study='+f.study_id);
  await page.getByRole('button',{name:'Create modeling approach',exact:true}).click();
  await page.getByRole('button',{name:'Add method step',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Method step',exact:true});
  await dialog.getByLabel('Step title',{exact:true}).fill('Read exact unit intent');
  await dialog.getByLabel('Implementation status',{exact:true}).selectOption('linked');
  await dialog.getByLabel('Implementation model',{exact:true}).selectOption(f.model_id);
  await dialog.getByLabel('Implementation model version',{exact:true}).selectOption(f.before.model_revision_id);
  return dialog;
}
test('@units-reading approach references resolve occurrence through exact definition version',async({page})=>{
  const f=await seeded(page),dialog=await approachPicker(page,f);
  const labels=['Energy law · unknown · input · Not specified','Energy law · ratio · input · Dimensionless','Energy law · speed · input · m/s','Energy law · flow · m/s → Receiver · incoming · m/s'];
  for(const label of labels) await dialog.getByRole('checkbox',{name:label,exact:true}).check();
  await expect(dialog).not.toContainText('old_flow');await expect(dialog).not.toContainText('[object Object]');
  await dialog.getByRole('button',{name:'Apply step',exact:true}).click();
  // The linked model dialog identifies its exact saved version and preserves quantity units.
  const detail=page.getByRole('region',{name:'Selected method step',exact:true});
  await detail.getByRole('button', { name: 'View model details', exact: true }).click();
  const inspector = page.getByRole('dialog', {
    name: 'Model version ' + f.before.model_revision_id.slice(0, 8), exact: true,
  });
  await expect(inspector).toContainText(
    'version ' + f.before.model_revision_id.slice(0, 8) + ' · read-only · linked to this approach',
  );
  await expect(inspector).toContainText('Not specified');await expect(inspector).toContainText('Dimensionless');await expect(inspector).toContainText('m/s');
  await page.keyboard.press('Escape');
});
for(const schema of ['3','2','1']) test('@units-reading exact schema '+schema+' assumption changes',async({page})=>{
  const f=await seeded(page,schema);
  // Actual consumer component with schema-validated exact public snapshots.
  // ConfigurationPanel binding workflow remains a separate integration.
  const before=(await(await page.request.get('/api/1/studies/'+f.study_id+'/models/'+f.model_id+'/revisions/'+f.before.model_revision_id)).json()).data;
  const after=(await(await page.request.get('/api/1/studies/'+f.study_id+'/models/'+f.model_id+'/revisions/'+f.after.model_revision_id)).json()).data;
  expect(before).toEqual(f.before);expect(after).toEqual(f.after);
  await page.evaluate(({before,after})=>(window as any).showAssumptionChanges(before,after),{before,after});
  const region=page.getByRole('region',{name:'Model assumption changes',exact:true}).first();
  if(schema==='1')await expect(region).toContainText('No model assumption changes.');
  else {await expect(region).toContainText('Original bounded assumption');await expect(region).toContainText('Revised bounded assumption');await expect(region).not.toContainText('No model assumption changes.');}
});

test('@units-reading light dark narrow and genuine 200 percent keyboard evidence',async({baseURL})=>{
  test.setTimeout(180000);
  const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/units-reading-zoom-extension');
  await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Units reader zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/units-reading-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try {
    const page=context.pages()[0]??await context.newPage();page.on('pageerror',e=>pageErrors.push(e.message));const f=await seeded(page);
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
      const labels=await page.locator('.change-table th .exact-proposal').evaluateAll(items=>items.map(item=>({width:item.clientWidth,scrollWidth:item.scrollWidth})));
      for(const label of labels)expect(label.scrollWidth).toBeLessThanOrEqual(label.width+1);geometry.push({name,buttons,...size,labels});
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));
    }
    await resize(1440,1000);
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    async function mode(size:string) {
      await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tab);await expect.poll(()=>page.evaluate(()=>devicePixelRatio)).toBe(1);
      await resize(size==='narrow'?600:1440,size==='narrow'?900:1000);
      if(size==='200'){
        await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);
        expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
      }
    }
    for(const size of ['desktop','narrow','200']) {
      await mode(size);
      for(const theme of ['light','dark']) {
        await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
        await page.getByRole('tab',{name:'Graph',exact:true}).click();
        const port = page.locator('#panel-Graph .hf-node__port[title^="unknown · "]');
        await port.focus();
        await page.keyboard.press('Enter');
        await expect(port).toHaveAttribute('aria-pressed', 'true');
        await expect(page.locator('#panel-Graph .hf-node__port[aria-pressed="true"]'))
          .toHaveCount(1);
        await expect(page.locator('#panel-Graph [data-instance="' + f.producer_id + '"]'))
          .toHaveAttribute('aria-pressed', 'false');
        await page.getByRole('tab',{name:'Graph',exact:true}).scrollIntoViewIfNeeded();await capture('reader-graph-'+size+'-'+theme);
        await inspectXdsm(page,'unknown','Not specified');await capture('reader-xdsm-'+size+'-'+theme);
        await page.getByRole('region',{name:'Selection inspector',exact:true}).scrollIntoViewIfNeeded();geometry.push({name:'port-table-'+size+'-'+theme,rows:await portTableReadable(page)});await capture('reader-inspector-'+size+'-'+theme);
        const scroll=page.getByRole('region',{name:'Quantities table',exact:true});await scroll.focus();await expect(scroll).toBeFocused();await capture('reader-variables-'+size+'-'+theme);
      }
    }
    await mode('desktop');const dialog=await approachPicker(page,f);
    await expect(dialog.getByRole('checkbox',{name:'Energy law · flow · m/s → Receiver · incoming · m/s',exact:true})).toBeVisible();
    for(const size of ['desktop','narrow','200']) {
      await mode(size);
      for(const theme of ['light','dark']) {
        await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
        const choice=dialog.getByRole('checkbox',{name:'Energy law · unknown · input · Not specified',exact:true});
        await choice.focus();await expect(choice).toBeFocused();await choice.scrollIntoViewIfNeeded();await capture('reader-references-'+size+'-'+theme);
        const action=dialog.getByRole('button',{name:'Apply step',exact:true});await action.focus();await expect(action).toBeFocused();await action.scrollIntoViewIfNeeded();await capture('reader-reference-actions-'+size+'-'+theme);
      }
    }
    await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Add method step',exact:true})).toBeFocused();
    await mode('desktop');
    // Cancel restored the prior empty approach; use existing version navigation.
    await page.getByRole('button',{name:'Back to overview',exact:true}).click();
    await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toBeVisible();
    await openRevision(page,f);await page.getByLabel('Model version',{exact:true}).selectOption('draft');
    await page.getByRole('button',{name:'＋ Component',exact:true}).click();
    const add=page.getByRole('dialog',{name:'Add component',exact:true});await add.getByLabel('New component name').fill('New unresolved component');await add.getByLabel('Input symbols').fill('x');await add.getByLabel('Output symbols').fill('y');await add.getByRole('button',{name:'Add component',exact:true}).click();
    const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});await expect(preview).toContainText('Not specified');
    for(const size of ['desktop','narrow','200']) {
      await mode(size);
      for(const theme of ['light','dark']) {await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await preview.getByRole('button',{name:'Keep editing',exact:true}).focus();await capture('reader-preview-'+size+'-'+theme);}
    }
    await writeFile(join(root,'evidence/reader-native-zoom.json'),JSON.stringify({zoom:2,viewport:null,geometry},null,2));
  } finally {await context.close();}
});

test('@units-reading preview preserves before and after unit meanings',async({page})=>{
  await seeded(page);
  await page.getByLabel('Model version',{exact:true}).selectOption('draft');
  await page.getByRole('button',{name:'Edit quantities',exact:true}).click();
  const ports=page.getByRole('dialog',{name:'Edit quantities',exact:true});
  await ports.getByLabel('Quantity 1 units',{exact:true}).selectOption('dimensionless');
  await ports.getByLabel('Quantity 2 units',{exact:true}).selectOption('physical');
  await ports.getByLabel('Quantity 2 units spelling',{exact:true}).fill('J/kg');
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Save component',exact:true}).click();
  const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});
  const row=preview.getByRole('row').filter({hasText:'Energy law · ports'});
  await expect(row.getByRole('cell').nth(0)).toContainText('unknown · Not specified');
  await expect(row.getByRole('cell').nth(0)).toContainText('ratio · Dimensionless');
  await expect(row.getByRole('cell').nth(1)).toContainText('unknown · Dimensionless');
  await expect(row.getByRole('cell').nth(1)).toContainText('ratio · J/kg');
  await expect(row.getByRole('cell').nth(1)).toContainText('speed · m/s');
  await expect(preview).not.toContainText('[object Object]');
});
