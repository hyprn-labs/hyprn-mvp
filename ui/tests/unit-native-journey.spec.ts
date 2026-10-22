import {createHash} from 'node:crypto';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {test,expect,chromium,type Page} from 'playwright/test';
import { chromiumExecutable } from './support/browser';
const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
async function fixture(){return JSON.parse(await readFile(join(root,'artifacts/native-browser-input.json'),'utf8'));}
async function login(page:Page,f:any){
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');await page.getByLabel('Password').fill(f.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('button',{name:'New study',exact:true})).toBeVisible();
}
// Composition: the selected step names its exact model version in one implementation line
// and opens it in the canonical model view. A version selector exists only when the step links
// several exact model versions; otherwise the single linked version is shown by its short id.
async function expectStepModel(
  approach: any,
  approachVersion: any,
  stepIndex: number,
  unitText: string,
) {
  const stepButton = approach.getByRole('button', {
    name: 'Select step ' + (stepIndex + 1),
    exact: true,
  });
  if ((await stepButton.getAttribute('aria-expanded')) !== 'true') await stepButton.click();
  const content = approachVersion.version.content,
    step = content.steps[stepIndex];
  const linked = [...new Set(step.implementation_refs.map((r: any) => r.binding_id))];
  expect(linked).toContain(content.model_bindings[1].binding_id);
  const selector = approach.getByLabel('Approach model version', { exact: true }),
    id8 = content.model_bindings[1].model_revision_id.slice(0, 8);
  if (linked.length > 1) {
    await expect(selector).toHaveValue(content.model_bindings[1].binding_id);
  } else {
    expect(linked).toEqual([content.model_bindings[1].binding_id]);
    await expect(selector).toHaveCount(0);
  }
  await expect(
    approach.getByRole('region', { name: 'Selected method step', exact: true }),
  ).toContainText('Implemented in Model version ' + id8);
  await approach.getByRole('button', { name: 'Open model version', exact: true }).click();
  const open = approach.page().getByRole('dialog', { name: 'Model version ' + id8, exact: true });
  await expect(open.getByRole('table', { name: 'Quantities', exact: true })).toContainText(
    unitText,
  );
  await approach.page().keyboard.press('Escape');
  await expect(open).toBeHidden();
}
async function openRun(page:Page,f:any,row:any){
  await page.goto('/ui/#v=1&view=runs&study='+f.study_id+'&run='+row.run_id);
  await expect(page.getByRole('button',{name:'Full-precision values',exact:true})).toBeVisible();
}

async function retainedScientificAnswers(page: Page, f: any) {
  const answers = f.scientific_answers;
  if (!answers) return;
  await page.goto(
    '/ui/#v=1&view=approach&study=' + f.study_id +
      '&approach=' + answers.approach_version_id,
  );
  const study = page.getByRole('region', {
    name: 'Answer to the study question', exact: true,
  });
  await expect(study).toContainText(answers.study_answer.interpretation);
  const comparison = page.getByRole('article', {
    name: 'Direct and retained-result comparison', exact: true,
  });
  await comparison.locator('summary').first().click();
  await expect(comparison).toContainText(answers.revised_case_answer.qualifications[1]);
  await study.getByText('Answer basis and record details', { exact: true }).click();
  await study.getByRole('button', {
    name: 'View case answer version ' + answers.case_answer.answer_version_id.slice(0, 8),
    exact: true,
  }).click();
  await expect(study).toContainText(answers.case_answer.interpretation);
  await expect(study).not.toContainText(answers.revised_case_answer.qualifications[1]);
  const basis = study.getByRole('button', {
    name: 'Run ' + answers.case_answer.basis.run_ids[0].slice(0, 8), exact: true,
  });
  await expect(basis.first()).toBeVisible();
  await page.screenshot({
    path: join(root, 'evidence/native-persistent-scientific-answers.png'), fullPage: true,
  });
  await basis.first().click();
  await expect(page.getByRole('button', {
    name: 'Full-precision values', exact: true,
  })).toBeVisible();
  expect(page.url()).toContain('run=' + answers.case_answer.basis.run_ids[0]);
}
test('@units-producer browser author commit and configuration use the real private producer without execution',async({page})=>{
  test.setTimeout(90000);const f=await fixture(),calls:any[]=[],errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{const path=new URL(r.url()).pathname;if(path.startsWith('/api/'))calls.push({method:r.request().method(),path,status:r.status()});});
  await login(page,f);
  await page.goto('/ui/#v=1&view=model&study='+f.study_id);
  await page.getByRole('button',{name:'New model',exact:true}).click();
  await page.getByLabel('New model name').fill('Browser native unit declaration');
  await page.getByRole('button',{name:'Create model',exact:true}).click();
  await page.getByRole('button',{name:'＋ Component',exact:true}).click();
  const add=page.getByRole('dialog',{name:'Add component',exact:true});
  await add.getByLabel('New component name').fill('Energy law');
  await add.getByLabel('Input symbols').fill('x');await add.getByLabel('Output symbols').fill('y');
  await add.getByRole('button',{name:'Add component',exact:true}).click();
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByText('Component added',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save model version',exact:true}).click();
  await expect(page.getByText('Model version saved · units incomplete. Resolve units in the listed active components before creating a configuration.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'units are not specified'})).toBeVisible();
  await page.getByRole('button',{name:'Edit ports',exact:true}).click();
  for(const n of [1,2]){await page.getByLabel(`Port ${n} units`,{exact:true}).selectOption('physical');await page.getByLabel(`Port ${n} units spelling`,{exact:true}).fill('J/kg');}
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Save component',exact:true}).click();
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Browser compound configuration');
  await page.getByLabel('Energy law · x value',{exact:true}).fill('2');
  await page.getByLabel('Energy law · x provenance',{exact:true}).fill('Explicit browser input, no analysis requested');
  await page.getByLabel('Energy law · x units',{exact:true}).selectOption('physical');
  await page.getByLabel('Energy law · x units spelling',{exact:true}).fill('MJ/kg');
  const preview=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/configurations/preview'));
  const committed=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/configurations'));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const checked=await preview;expect(checked.status()).toBe(200);expect((await checked.json()).data.compatibility.compatible).toBe(true);
  const saved=await committed;expect(saved.status()).toBe(201);const retained=(await saved.json()).data;
  expect(retained.model_snapshot.schema_version).toBe('4');
  expect(retained.configuration.inputs[0].units).toBe('MJ/kg');expect(retained.configuration.inputs[0].value).toBe(2);
  await expect(page.getByRole('button',{name:'Create new version',exact:true})).toBeVisible();
  expect(calls.some(c=>c.path.endsWith('/unit-catalog')&&c.status===200)).toBe(true);
  for(const ending of ['/models','/preview','/edits','/commits','/configurations'])expect(calls.some(c=>c.method==='POST'&&c.path.endsWith(ending)&&[200,201].includes(c.status))).toBe(true);
  expect(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/runs'))).toEqual([]);expect(errors).toEqual([]);
  await writeFile(join(root,'evidence/native-browser-authoring.json'),JSON.stringify({calls,retained},null,2));
});

test('@units-native @units-mixed-retained actual seven native records retain exact values and modified seeds during real outage (one retained record with fixed mixed selector)',async({page})=>{
  test.setTimeout(120000);const f=await fixture(),errors:string[]=[],calls:any[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))calls.push({method:r.method(),path:new URL(r.url()).pathname});});
  expect(f.process_count).toBe(f.mixed?1:f.records.length);await login(page,f);
  await retainedScientificAnswers(page, f);
  for(const row of f.records){
    await openRun(page,f,row);
    const response=await page.request.get('/api/1/studies/'+f.study_id+'/runs/'+row.run_id);
    expect(response.ok()).toBe(true);expect((await response.json()).data.history).toEqual(row.detail.history);
    await page.getByRole('button',{name:'Full-precision values',exact:true}).focus();await page.keyboard.press('Enter');
    const table=page.getByRole('region',{name:'Full-precision output values',exact:true});
    for(const [index,output]of row.detail.history.results.outputs.entries()){
      const cells=table.locator('tbody tr').nth(index).locator('td');
      await expect(cells.nth(0)).toHaveText(String(output.value));
      await expect(cells.nth(1)).toHaveText(output.units||'dimensionless');
    }
    await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Full-precision values',exact:true})).toBeFocused();
    await page.getByRole('tab',{name:'Model',exact:true}).click();
    await expect(page.locator('#run-panel-1')).not.toContainText('[object Object]');
    await page.getByRole('tab',{name:'Configuration',exact:true}).click();
    await expect(page.locator('#run-panel-2').getByRole('heading',{name:'Context',exact:true})).toBeVisible();
    await expect(page.locator('#run-panel-2').getByRole('region',{name:'Saved configuration inputs',exact:true}).locator('tbody tr')).toHaveCount(row.configuration.configuration.inputs.length);
    if(f.mixed){
      await page.locator('#run-panel-2').getByRole('button',{name:'View modeling approach',exact:true}).click();
      const approach=page.getByRole('dialog',{name:'Linked modeling approach',exact:true});
      await expectStepModel(approach,f.mixed.variants[1].approach,1,'Not specified');
      await page.keyboard.press('Escape');
      const downloaded=await page.request.get('/api/1/studies/'+f.study_id+'/computational-records/'+f.mixed.archive_id+'/download');
      expect(downloaded.status()).toBe(200);
      const bytes=await downloaded.body();expect(createHash('sha256').update(bytes).digest('hex')).toBe(f.mixed.archive_sha256);
      await writeFile(join(root,'evidence/mixed-browser-download.zip'),bytes);
    }

    const seedResponse=await page.request.get('/api/1/studies/'+f.study_id+'/runs/'+row.run_id+'/modified-run-seed');
    expect(seedResponse.ok()).toBe(true);const seed=(await seedResponse.json()).data;
    expect(seed.model_snapshot).toEqual(row.detail.history.model_snapshot);
    if(f.mixed){expect(seed.approach_closure).toEqual(f.mixed.seed.approach_closure);expect(seed.source_configuration).toEqual(row.configuration.configuration);}
    expect(seed.schema_version).toBe({'8':'8','4':'4'}[row.detail.history.history_schema_version as string]??'3');
    await page.getByRole('button',{name:'Create modified run',exact:true}).click();
    await expect(page.getByLabel('Configuration name',{exact:true})).toBeVisible();
    await expect(page.locator('body')).not.toContainText('[object Object]');
  }
  if(f.mixed){
    for(const variant of f.mixed.variants){
      const c=variant.configuration;
      await page.goto('/ui/#v=1&view=configurations&study='+f.study_id+'&configuration='+c.configuration.configuration_revision_id);
      await expect(page.getByRole('button',{name:'Create new version',exact:true})).toBeVisible();
      const response=await page.request.get('/api/1/studies/'+f.study_id+'/configurations/'+c.configuration.configuration_revision_id);
      expect((await response.json()).data).toEqual(c);
      await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
      const approach=page.getByRole('dialog',{name:'Linked modeling approach',exact:true});
      await expectStepModel(approach,variant.approach,1,variant.kind==='unspecified'?'Not specified':'N');
      expect(c.model_snapshot).toEqual(f.records[0].configuration.model_snapshot);
      await page.screenshot({path:join(root,'evidence/mixed-configuration-'+variant.kind+'.png')});
      await page.keyboard.press('Escape');
    }
    await openRun(page,f,f.records[0]);
    await page.getByRole('button',{name:'Export computational record',exact:true}).click();
    const exported=page.getByRole('dialog',{name:'Export computational record',exact:true});
    await expect(exported).toContainText('Review the computation');
    await exported.getByText('Details',{exact:true}).click();
    await expect(exported).toContainText(f.records[0].run_id);
    await expect(exported.getByRole('button',{name:'Check contents',exact:true})).toBeVisible();
    await page.screenshot({path:join(root,'evidence/mixed-export-existing-entry.png')});
    await page.keyboard.press('Escape');
  }
  expect(calls.filter(c=>c.path.includes('/models/'))).toEqual([]);
  expect(calls.filter(c=>c.method!=='GET'&&c.path!=='/api/1/session')).toEqual([]);
  expect(errors).toEqual([]);
  await writeFile(join(root,'evidence/native-browser-api-calls.json'),JSON.stringify(calls,null,2));
});

test('@units-native @units-mixed-retained retained compound results light dark narrow and actual 200 percent keyboard evidence',async({baseURL})=>{
  test.setTimeout(120000);const f=await fixture(),errors:string[]=[],geometry:any[]=[];
  const extension=join(root,'artifacts/native-zoom-extension');await mkdir(extension,{recursive:true});
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Native units zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(await mkdtemp(join(root,'artifacts/native-zoom-profile-')),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  try{
    const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),page=context.pages()[0]??await context.newPage();
    page.on('pageerror',e=>errors.push(e.message));await login(page,f);await openRun(page,f,f.records[0]);
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');
    async function resize(width:number,height:number){const before=await page.evaluate(()=>({width:innerWidth,height:innerHeight})),actual=(await cdp.send('Browser.getWindowBounds',{windowId:info.windowId})).bounds;await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:actual.width!+width-before.width,height:actual.height!+height-before.height}});await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(width);}
    const tab=await worker.evaluate(async url=>(await(globalThis as any).chrome.tabs.query({})).find((t:any)=>t.url.startsWith(url)).id,baseURL!);
    for(const size of ['desktop','narrow','200']){
      await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tab);await expect.poll(()=>page.evaluate(()=>devicePixelRatio)).toBe(1);
      await resize(size==='narrow'?600:1440,size==='narrow'?900:1000);
      if(size==='200'){await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);}
      for(const theme of ['light','dark']){
        await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
        await page.getByRole('button',{name:'Full-precision values',exact:true}).focus();await page.keyboard.press('Enter');
        await expect(page.getByRole('dialog')).toBeVisible();
        await expect.poll(()=>page.locator('.hf-btn:visible').evaluateAll(items=>items.every(item=>{getComputedStyle(item).backgroundColor;return item.getAnimations().every(a=>a.playState!=='running');}))).toBe(true);
        const bounds=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width+1);
        geometry.push({size,theme,...bounds});const image=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
        await writeFile(join(root,'evidence/native-exact-'+size+'-'+theme+'.png'),Buffer.from(image.data,'base64'));
        if(size==='narrow'){
          const table=page.getByRole('region',{name:'Full-precision output values',exact:true});
          await table.evaluate(e=>e.scrollLeft=e.scrollWidth);
          const cells=table.locator('tbody tr').first().locator('td');
          const expectedUnit=f.records[0].detail.history.results.outputs[0].units||'dimensionless';
          await expect(cells.nth(1)).toHaveText(expectedUnit);
          const unitBounds=await cells.nth(1).boundingBox();expect(unitBounds!.x+unitBounds!.width).toBeLessThanOrEqual(600);
          const scrolled=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
          await writeFile(join(root,'evidence/native-exact-narrow-'+theme+'-units.png'),Buffer.from(scrolled.data,'base64'));
        }
        await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Full-precision values',exact:true})).toBeFocused();
      }
    }
    expect(errors).toEqual([]);await writeFile(join(root,'evidence/native-browser-geometry.json'),JSON.stringify(geometry,null,2));
  }finally{await context.close();}
});


test('@units-mixed-producer browser saves the exact mixed modified configuration without dispatch',async({page})=>{
  test.setTimeout(90000);const f=await fixture(),calls:any[]=[],errors:string[]=[];
  expect(f.mixed).toBeTruthy();expect(f.process_count).toBe(1);
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))calls.push({method:r.method(),path:new URL(r.url()).pathname});});
  await login(page,f);await openRun(page,f,f.records[0]);
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Browser mixed retained copy');
  await page.locator('.configuration-criterion').getByRole('button',{name:'Edit',exact:true}).click();
  const criteria=page.getByRole('dialog',{name:'Edit criteria',exact:true});
  await criteria.getByLabel('Criterion 1 absolute tolerance',{exact:true}).fill('0');
  await criteria.getByLabel('Criterion 1 relative tolerance',{exact:true}).fill('0');
  await page.keyboard.press('Escape');
  const preview=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/configurations/preview'));
  const committed=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/configurations'));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const checked=await preview;expect(checked.status()).toBe(200);expect((await checked.json()).data.compatibility.compatible).toBe(true);
  await page.getByRole('dialog',{name:'Review modified run',exact:true}).getByRole('button',{name:'Save modified configuration',exact:true}).click();
  const saved=await committed;expect(saved.status()).toBe(201);const retained=(await saved.json()).data;
  expect(retained.schema_version).toBe('5');expect(retained.model_snapshot).toEqual(f.records[0].configuration.model_snapshot);
  expect(retained.approach_closure).toEqual(f.records[0].configuration.approach_closure);
  expect(retained.configuration.inputs[0].units).toBe('N');expect(retained.configuration.inputs[0].value).toBe(3);
  await expect(page.getByRole('button',{name:'Create new version',exact:true})).toBeVisible();
  expect(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/runs'))).toEqual([]);expect(errors).toEqual([]);
  await writeFile(join(root,'evidence/mixed-browser-authoring.json'),JSON.stringify({calls,retained},null,2));
});


test('@units-mixed-inspection one real preview inspects retained mixed context without creating another package',async({page})=>{
  test.setTimeout(120000);const f=await fixture(),calls:any[]=[];
  expect(f.mixed).toBeTruthy();
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))calls.push({method:r.method(),path:new URL(r.url()).pathname});});
  await login(page,f);await openRun(page,f,f.records[0]);
  await page.getByRole('button',{name:'Export computational record',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Export computational record',exact:true});
  const requested=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/computational-record-previews'));
  await dialog.getByRole('button',{name:'Check contents',exact:true}).click();
  const response=await requested;expect(response.status()).toBe(202);
  const record=(await response.json()).data,body=response.request().postDataJSON();
  expect(body.selected_run_ids).toEqual([f.records[0].run_id]);
  await writeFile(join(root,'artifacts/mixed-preview-request.json'),JSON.stringify({request_id:record.request_id,body}));
  await expect(dialog.getByRole('button',{name:'Create export',exact:true})).toBeEnabled({timeout:90000});
  await expect(dialog).toContainText('For inspection. this archive does not guarantee that the calculation can run on another installation.');
  const included=dialog.getByRole('region',{name:'Included modeling approach',exact:true});
  await expect(included).toContainText('Saved approach versions');
  const returned=await page.request.get('/api/1/studies/'+f.study_id+'/computational-records/'+record.request_id);
  const ready=(await returned.json()).data;
  expect(ready.preview.approach_summary.model_count).toBe(2);
  expect(ready.preview.approach_summary.approach_version_ids).toEqual([f.mixed.variants[1].approach.version.approach_version_id]);
  expect(ready.preview.selected.map((r:any)=>r.run_id)).toEqual([f.records[0].run_id]);
  expect(ready.preview.selected[0].model_revision_id).toBe(f.records[0].configuration.model_snapshot.model_revision_id);
  await dialog.getByText('Details',{exact:true}).click();
  await expect(dialog).toContainText(f.records[0].run_id);
  await expect(dialog).toContainText(f.records[0].configuration.model_snapshot.model_revision_id);
  await page.screenshot({path:join(root,'evidence/mixed-real-preview-light.png')});
  expect(calls.filter(c=>c.method==='POST'&&(c.path.endsWith('/runs')||c.path.endsWith('/computational-records')))).toEqual([]);
  expect(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/computational-record-previews'))).toHaveLength(1);
  await writeFile(join(root,'evidence/mixed-real-preview.json'),JSON.stringify({calls,ready},null,2));
});
