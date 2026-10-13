import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {test,expect,chromium,type Page} from 'playwright/test';
import { chromiumExecutable } from './support/browser';
const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
async function fixture(){return JSON.parse(await readFile(join(root,'artifacts/findings-input.json'),'utf8'));}
async function login(page:Page,f:any){
  await page.goto('/ui/');
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill(f.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('button',{name:'New study',exact:true})).toBeVisible();
}
async function inspect(page:Page,f:any,label:string,capture:(part:string)=>Promise<void>){
  const writes:string[]=[],calls:any[]=[],responses:any[]=[];
  page.on('request',r=>{if(r.url().includes('/api/1/')){calls.push({method:r.method(),url:r.url()});if(r.method()!=='GET')writes.push(r.url());}});
  const pending:Promise<void>[]=[];
  page.on('response',r=>{if(r.url().includes('/api/1/')&&r.request().method()==='GET')pending.push(r.json().then(body=>{responses.push({url:r.url(),status:r.status(),body});}).catch(()=>{}));});
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:f.study_id,view:'approach',approach:f.approach_version_id}));
  // Usage and recorded runs live under the "Cases & results" section tab
  // (results first; one card per case holds its runs); keyboard activation keeps the 200% keyboard journey honest.
  const cases=page.getByRole('tab',{name:'Cases & results',exact:true});
  await cases.focus();await cases.press('Enter');
  await expect(cases).toHaveAttribute('aria-selected','true');
  await expect(page.getByRole('tabpanel',{name:'Cases & results',exact:true}).getByRole('heading',{name:'No study answer has been assessed.',exact:true})).toBeVisible();
  const usage=page.getByRole('region',{name:'Approach usage',exact:true});
  await expect(usage).toContainText(f.configuration_name);
  await usage.getByLabel('Findings case',{exact:true}).selectOption(f.case_id);
  await expect(usage).toContainText('2 usage rows loaded');
  await expect(usage.getByRole('button',{name:'View run',exact:true})).toHaveCount(1);
  const run=usage.getByRole('button',{name:'Run details',exact:true});
  await run.focus();await run.press('Enter');
  await expect(usage).toContainText('Completed');
  // Applicability is never computed today, so it is not shown.
  await expect(usage).not.toContainText('Not assessed');
  await expect(usage).toContainText('1000000');
  const runRow=usage.getByRole('article',{name:'run '+f.run_id,exact:true});
  await runRow.evaluate(e=>e.scrollIntoView({block:'start'}));await capture('downstream');
  await runRow.getByRole('button',{name:'Review source-linked inputs',exact:true}).press('Enter');
  const load=usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).first();await load.focus();await load.press('Enter');
  await expect(usage).toContainText('Verified source identity');
  await expect(usage).toContainText('Upstream criterion not met');
  await expect(usage).toContainText('Original 1 MJ/kg');
  await expect(usage).toContainText('factor 1000000 · received 1000000 J/kg');
  await runRow.getByRole('button',{name:'Review source-linked inputs',exact:true}).focus();
  await runRow.getByText('Original 1 MJ/kg',{exact:true}).evaluate(e=>e.scrollIntoView({block:'center'}));await capture('source');
  const exact=usage.getByRole('button',{name:'Full-precision values',exact:true});await exact.focus();await exact.press('Enter');
  await expect(page.getByRole('dialog')).toContainText('1000000');await capture('downstream-exact');await page.keyboard.press('Escape');await expect(exact).toBeFocused();
  await usage.getByRole('button',{name:'View upstream run',exact:true}).first().press('Enter');
  await expect(page.getByRole('tab',{name:'Results',exact:true})).toBeVisible();
  expect(new URL(page.url()).hash).toContain(f.source_id);
  await page.getByRole('button',{name:'Full-precision values',exact:true}).press('Enter');
  await expect(page.getByRole('dialog')).toContainText('MJ/kg');await capture('source-exact');await page.keyboard.press('Escape');
  await Promise.all(pending);
  const usages=responses.filter(r=>r.url.includes('/usage')&&r.status===200);
  expect(usages.length).toBeGreaterThan(0);expect(JSON.stringify(usages)).toContain(f.run_id);
  const actual=responses.find(r=>new URL(r.url).pathname.endsWith('/runs/'+f.run_id));
  expect(actual.body.data.history).toEqual(f.downstream.history);
  const source=responses.find(r=>new URL(r.url).pathname.endsWith('/runs/'+f.source_id));
  expect(source.body.data.retained_integrity).toEqual(f.source.retained_integrity);
  expect(writes).toEqual([]);
  await writeFile(join(root,'evidence/'+label+'-http.json'),JSON.stringify({calls,responses,writes},null,2));
}
async function settled(page:Page){
  await expect.poll(()=>page.locator('.hf-btn:visible').evaluateAll(items=>items.every(item=>{getComputedStyle(item).backgroundColor;return item.getAnimations().every(a=>a.playState!=='running');}))).toBe(true);
}
test('@findings-online actual pinned downstream and source qualifications',async({page})=>{
  const f=await fixture();expect(f.mode).toBe('online');await login(page,f);
  await inspect(page,f,'online',async(part)=>{
    for(const theme of ['light','dark']){
      await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await settled(page);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
      await page.screenshot({path:join(root,'evidence/findings-online-'+part+'-'+theme+'.png'),fullPage:false});
    }
  });
});
test('@findings-offline actual outage restarted app with genuine 200 percent keyboard',async({baseURL})=>{
  test.setTimeout(120000);const f=await fixture();expect(f.mode).toBe('offline');
  const extension=join(root,'artifacts/findings-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Findings zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(await mkdtemp(join(root,'artifacts/findings-zoom-profile-')),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  try{
    const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),page=context.pages()[0]??await context.newPage();
    await login(page,f);const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');
    const before=await page.evaluate(()=>({width:innerWidth,height:innerHeight})),bounds=(await cdp.send('Browser.getWindowBounds',{windowId:info.windowId})).bounds;
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:bounds.width!+1440-before.width,height:bounds.height!+1000-before.height}});
    const tab=await worker.evaluate(async url=>(await(globalThis as any).chrome.tabs.query({})).find((t:any)=>t.url.startsWith(url)).id,baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);
    expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    await inspect(page,f,'offline',async(part)=>{
      for(const theme of ['light','dark']){
        await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await settled(page);
        const geometry=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));
        expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width+1);expect(geometry.dpr).toBe(2);
        const focused=page.locator(':focus');expect(await focused.count()).toBe(1);
        const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
        await writeFile(join(root,'evidence/findings-offline-200-'+part+'-'+theme+'.png'),Buffer.from(shot.data,'base64'));
        await writeFile(join(root,'evidence/findings-offline-200-'+part+'-'+theme+'.json'),JSON.stringify({zoom:2,geometry,focus:await focused.evaluate(e=>e===document.activeElement)}));
      }
    });
  }finally{await context.close();}
});
