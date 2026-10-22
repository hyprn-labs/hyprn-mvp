import {mkdir, writeFile, readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {test,expect,chromium,type Page,type Locator} from 'playwright/test';
import { chromiumExecutable } from './support/browser';
let pageErrors:string[]=[];
test.beforeEach(async({page})=>{pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));});
test.afterEach(()=>expect(pageErrors).toEqual([]));
async function model(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password').fill('correct horse battery staple');
  const login=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/1/session' && r.request().method()==='POST');
  await page.getByRole('button', {name:'Sign in',exact:true}).click();
  const session=(await(await login).json()).data;
  await page.evaluate(session=>{(window as any).unitsApi.csrf=session.csrf_token;(window as any).unitsApi.actor=session.actor_id;},session);
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
type ReaderFixture = {study_id:string;model_id:string;producer_id:string;receiver_id:string;before:any;after:any;package:any;evidence:any};
async function seeded(page:Page,schema='3'):Promise<ReaderFixture> {
  await create(page);
  const hash=new URLSearchParams(new URL(page.url()).hash.slice(1));
  const response=await page.request.post('/fixture/read-model',{data:{study_id:hash.get('study'),model_id:hash.get('model'),schema}});
  expect(response.ok(),await response.text()).toBe(true);
  const fixture=await response.json();await openRevision(page,fixture);return fixture;
}
async function openRevision(page:Page,f:ReaderFixture) {
  await page.goto('/ui/#v=1&view=model&study='+f.study_id+'&model='+f.model_id+'&revision='+f.before.model_revision_id);
  await expect(page.getByText('Read-only',{exact:true}).first()).toBeVisible();
}

test('@units-history downloaded CSV distinguishes declarations and absent value units',async({page})=>{
  await seeded(page);
  // The Variables tab is gone; the Quantities table is always below the canvas and the
  // Quantities CSV exports its displayed rows.
  await expect(page.getByRole('tab', { name: 'Variables', exact: true })).toHaveCount(0);
  await expect(page.getByRole('table', { name: 'Quantities', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Quantities CSV', exact: true }).click();
  const csv = await readFile((await (await download).path())!, 'utf8');
  expect(csv).toContain('"Not specified"');
  expect(csv).toContain('"Dimensionless"');
  expect(csv).toContain('"m/s"');
  expect(csv).toContain('"Not recorded"');
  expect(csv).not.toContain('[object Object]');
  // The CSV exports exactly the displayed columns, including Definition.
  const header = csv.split('\r\n').find((r) => r.startsWith('"Variable",'))!;
  expect(header.split(',').slice(0, 5)).toEqual([
    '"Variable"',
    '"Component"',
    '"Direction"',
    '"Definition"',
    '"Units"',
  ]);
  await expect(
    page.getByRole('alert').filter({ hasText: 'Unsupported displayed column' }),
  ).toHaveCount(0);
});

async function portability(page: Page, f: ReaderFixture) {
  const study = (await (await page.request.get('/api/1/studies/' + f.study_id)).json()).data;
  await page.evaluate(({ study, snapshot }) => (window as any).showPortability(study, snapshot), {
    study,
    snapshot: f.before,
  });
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
}
for(const schema of ['1','2','3'])test('@units-history exact schema '+schema+' model package download and import inspection',async({page})=>{
  const f=await seeded(page,schema);await portability(page,f);
  expect(await page.evaluate(()=>(window as any).unitSourceExecuted)).toBeUndefined();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download portable model record',exact:true}).click();
  const text=await readFile((await(await download).path())!,'utf8'),pkg=JSON.parse(text);
  expect(pkg.schema_version).toBe(schema);expect(pkg.revisions[0]).toEqual(f.before);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Import model',exact:true}).click();
  await page.getByLabel('Portable model record file',{exact:true}).setInputFiles({name:'model.json',mimeType:'application/json',buffer:Buffer.from(text)});
  await page.getByRole('button',{name:'Preview model import',exact:true}).click();
  await expect(page.getByRole('region',{name:'Model import preview',exact:true})).toContainText('This model already exists in this study.');
  await expect(page.getByRole('button',{name:'Import model',exact:true})).toBeDisabled();
});

async function packageImport(page:Page,f:ReaderFixture,pkg:any) {
  const study=await page.evaluate(()=>(window as any).unitsApi.createStudy('Imported units'));
  await page.evaluate(({study,snapshot})=>(window as any).showPortability(study,snapshot),{study,snapshot:f.before});
  await page.getByRole('button',{name:'Import model',exact:true}).click();
  await page.getByLabel('Portable model record file',{exact:true}).setInputFiles({name:'model.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(pkg))});
  await page.getByRole('button',{name:'Preview model import',exact:true}).click();return study;
}
test('@units-history package3 actual import preserves mixed ancestor bytes and declarations',async({page})=>{
  const f=await seeded(page);
  const study=await packageImport(page,f,f.package);
  await expect(page.getByRole('button',{name:'Import model',exact:true})).toBeEnabled();
  const response=page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname.endsWith('/model-imports'));
  await page.getByRole('button',{name:'Import model',exact:true}).click();
  expect((await response).status()).toBe(200);
  const selected=(await(await page.request.get('/api/1/studies/'+study.study_id+'/models/'+f.model_id+'/revisions/'+f.before.model_revision_id)).json()).data;
  expect(selected).toEqual(f.before);
  const after=(await(await page.request.get('/api/1/studies/'+study.study_id+'/models/'+f.model_id+'/revisions/'+f.after.model_revision_id)).json()).data;
  expect(after).toEqual(f.after);
  await expect(page.getByRole('status').filter({hasText:'Model imported'}).first()).toBeVisible();
});
async function reseal(page:Page,pkg:any) {
  return page.evaluate(async pkg=>{const {digest,...body}=pkg;pkg.digest=await(window as any).exportHelpers.sha256(new TextEncoder().encode((window as any).exportHelpers.canonical(body)));return pkg;},pkg);
}
test('@units-history package inspector rejects tamper unsupported versions missing capabilities and unsafe inventory',async({page})=>{
  const f=await seeded(page);
  const cases:Array<[string,(p:any)=>void,boolean]>=[
    ['does not match its SHA-256',p=>p.source_service='tampered',false],
    // 43.1 made ModelPackage4 a supported reader version; '5' is the next unsupported one.
    ['Unsupported or invalid',p=>p.schema_version='5',true],
    ['Record format 4 requires quantity_definitions/1',p=>p.schema_version='4',true],
    ['requires unit_declarations/1',p=>p.required_capabilities=[],true],
    ['Model version record formats do not match',p=>p.schema_version='2',true],
    ['Source hash mismatch',p=>p.revisions[0].source_files[0].sha256='0'.repeat(64),true],
    ['Invalid file list in the portable model record',p=>p.files[0].path='../escape',true],
    ['file list does not match',p=>p.files[0].size+=1,true],
  ];
  // Every negative is inspected by the real file-picker/preview action.
  await packageImport(page,f,{...f.package,schema_version:'4'});
  let submissions=0;page.on('request',r=>{if(r.method()==='POST' && new URL(r.url()).pathname.endsWith('/model-imports'))submissions++;});
  for(const [message,mutate,recompute]of cases) {
    let pkg=structuredClone(f.package);mutate(pkg);
    if(message==='Source hash mismatch') {pkg.revisions[0]=await reseal(page,pkg.revisions[0]);}
    if(recompute)pkg=await reseal(page,pkg);
    await page.getByLabel('Portable model record file',{exact:true}).setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(pkg))});
    await page.getByRole('button',{name:'Preview model import',exact:true}).click();
    await expect(page.getByRole('alert').filter({hasText:message}).first()).toBeVisible();
    await expect(page.getByRole('button',{name:'Import model',exact:true})).toHaveCount(0);
  }
  expect(submissions).toBe(0);
});

async function savedHistory(page:Page) {
  const f=await seeded(page);
  const frozen=await page.evaluate(async f=>{
    const api=(window as any).unitsApi,study=await api.study(f.study_id),m=f.after;
    const incoming=new Set(m.connections.map((c:any)=>c.target_ref.instance_id+'/'+c.target_ref.port_id));
    const inputs=m.instances.flatMap((i:any)=>m.definitions.find((d:any)=>d.definition_version_id===i.definition_version_id).ports.filter((p:any)=>p.direction==='input'&&!incoming.has(i.instance_id+'/'+p.port_id)).map((p:any)=>({kind:'literal',target:{instance_id:i.instance_id,port_id:p.port_id},value:0,units:typeof p.units==='string'?p.units:p.units.kind==='physical'?p.units.expression:'',provenance:{kind:'manual',statement:'Original exact zero',evidence_version_ids:[]}})));
    const request={schema_version:'4',study_id:f.study_id,model_id:f.model_id,model_revision_id:m.model_revision_id,name:'Retained unit scenario',inputs,criteria:[],numerical:{mode:'deterministic',initialization:[],solvers:[],derivatives:{method:'none',form:null,check:null},design_variables:[],objectives:[],constraints:[],optimizer:null,uncertainty:null},context_source:{kind:'current_study',expected_study_revision:study.revision},context_override:{schema_version:'1',description:'Original retained scenario',boundary:'Exact original boundary'},notes:['Original note'],derivation:null,assumptions:[],general_context_evidence_version_ids:[],approach_selection:null};
    const preview=await api.previewConfiguration4(request);
    return await api.commitConfiguration4({command_id:crypto.randomUUID(),configuration_id:null,expected_revision:null,configuration:request,expected_preview_digest:preview.candidate_digest});
  },f);
  const response=await page.request.post('/fixture/retain',{data:{study_id:f.study_id,configuration_revision_id:frozen.configuration.configuration_revision_id}});expect(response.ok(),await response.text()).toBe(true);
  return {...f,frozen,run_id:(await response.json()).run_id};
}
async function outage(page:Page) {
  const reads:string[]=[];
  await page.route('**/api/1/studies/*/models/**',route=>{reads.push(route.request().url());return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'backend_unavailable',message:'Modeling unavailable',fields:[],outcome:'unchanged'}})});});
  return reads;
}
/** A configuration does not repeat its model's assumptions. One line states how many
 * the exact retained model version records; View model assumptions opens that version read-only in
 * the canonical model view, whose Details list the model's own and each component's assumptions. */
const modelAssumptionsLine=(f:any)=>'Model assumptions: '+f.after.assumptions.length+' in the model';
async function retainedModelAssumptions(page:Page,f:any,scope:Locator) {
  await expect(scope.getByText(modelAssumptionsLine(f),{exact:true})).toBeVisible();
  await scope.getByRole('button',{name:'View model assumptions',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Model assumptions',exact:true});
  const details=dialog.getByRole('region',{name:'Selection inspector',exact:true});
  await expect(details.getByRole('region',{name:'Model assumptions',exact:true}).getByText('Revised bounded assumption',{exact:true})).toBeVisible();
  await dialog.getByRole('button',{name:'Inspect component Energy law',exact:true}).first().click();
  await expect(details.getByRole('region',{name:'Component · Energy law assumptions',exact:true}).getByText('Original component assumption',{exact:true})).toBeVisible();
  await page.keyboard.press('Escape');await expect(dialog).toBeHidden();
}
test('@units-history saved run and modified configuration retain exact model3 assumptions during modeling outage',async({page})=>{
  const f=await savedHistory(page),before=JSON.stringify(f.frozen),reads=await outage(page);
  await page.goto('/ui/#v=1&view=configurations&study='+f.study_id+'&configuration='+f.frozen.configuration.configuration_revision_id);
  await retainedModelAssumptions(page,f,page.getByRole('region',{name:'Saved configuration',exact:true}));
  await page.goto('/ui/#v=1&view=runs&study='+f.study_id+'&run='+f.run_id);
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  await retainedModelAssumptions(page,f,page.locator('#run-panel-2'));
  await page.getByRole('tab',{name:'Evidence',exact:true}).click();
  // Run › Evidence lists the run's assumptions by owner, built only from its retained versions.
  await expect(page.locator('#run-panel-3').getByText('Revised bounded assumption',{exact:true})).toBeVisible();
  await expect(page.locator('#run-panel-3').getByText('Original component assumption',{exact:true})).toBeVisible();
  await page.locator('#run-panel-3').getByRole('button',{name:'View evidence (1)',exact:true}).first().click();
  await expect(page.getByRole('region',{name:'Evidence details',exact:true}).getByText('Retained unit evidence',{exact:true})).toBeVisible();await page.keyboard.press('Escape');
  const seed=(await(await page.request.get('/api/1/studies/'+f.study_id+'/runs/'+f.run_id+'/modified-run-seed')).json()).data;
  expect(seed.schema_version).toBe('4');expect(seed.model_snapshot).toEqual(f.after);
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await retainedModelAssumptions(page,f,page.getByRole('region',{name:'Configuration assumption owners',exact:true}).filter({visible:true}));
  await expect(page.locator('.configuration-context:visible p').filter({hasText:/^Original retained scenario$/})).toBeVisible();
  expect(reads).toEqual([]);
  const retained=(await(await page.request.get('/api/1/studies/'+f.study_id+'/configurations/'+f.frozen.configuration.configuration_revision_id)).json()).data;
  expect(JSON.stringify(retained)).toBe(before);
});

async function rebuildPackage(page:Page,pkg:any) {
  return page.evaluate(async pkg=>{
    const {canonical,sha256}= (window as any).exportHelpers,bytes=(x:any)=>new TextEncoder().encode(canonical(x)),inventory=new Map();
    async function add(path:string,raw:Uint8Array,media_type:string,role:string) {
      const key=(await sha256(new TextEncoder().encode('model-package-v1:'+path))).slice(0,32),file_id=[key.slice(0,8),key.slice(8,12),key.slice(12,16),key.slice(16,20),key.slice(20)].join('-');
      inventory.set(path,{file_id,path,size:raw.length,sha256:await sha256(raw),media_type,role});
    }
    for(const r of pkg.revisions) {
      delete r.digest;r.digest=await sha256(bytes(r));await add('revisions/'+r.model_revision_id+'.json',bytes(r),'application/json','model');
      for(const source of r.source_files)await add('sources/'+source.sha256+'.py',Uint8Array.from(atob(source.bytes),c=>c.charCodeAt(0)),'text/x-python','source');
    }
    pkg.files=[...inventory.values()].sort((a:any,b:any)=>a.path.localeCompare(b.path));delete pkg.digest;pkg.digest=await sha256(bytes(pkg));return pkg;
  },pkg);
}
test('@units-history model package3 admits exact model1 and model2 ancestors',async({page})=>{
  const f=await seeded(page,'1'),one=structuredClone(f.before),two={...structuredClone(one),schema_version:'2',model_revision_id:crypto.randomUUID(),parent_model_revision_id:one.model_revision_id,assumptions:[],required_capabilities:['model_assumptions/1']};
  const three={...structuredClone(two),schema_version:'3',model_revision_id:crypto.randomUUID(),parent_model_revision_id:two.model_revision_id,required_capabilities:['model_assumptions/1','unit_declarations/1']};
  const pkg=await rebuildPackage(page,{...f.package,schema_version:'3',model_revision_id:three.model_revision_id,revisions:[one,two,three],required_capabilities:three.required_capabilities});
  const study=await packageImport(page,f,pkg);
  const submitted=page.waitForRequest(r=>r.method()==='POST'&&new URL(r.url()).pathname.endsWith('/model-imports'));
  await page.getByRole('button',{name:'Import model',exact:true}).click();
  expect((await submitted).postDataJSON().package).toEqual(pkg);
  await expect(page.getByRole('status').filter({hasText:'Model imported'}).first()).toBeVisible();
  for(const r of pkg.revisions)expect((await(await page.request.get('/api/1/studies/'+study.study_id+'/models/'+f.model_id+'/revisions/'+r.model_revision_id)).json()).data).toEqual(r);
  expect(pkg.revisions[0]).toEqual(f.before);
});
test('@units-history unknown capabilities block and server retains closed schema authority',async({page})=>{
  const f=await seeded(page);const unsupported=await reseal(page,{...f.package,required_capabilities:[...f.package.required_capabilities,'future_units/99']});
  await packageImport(page,f,unsupported);
  await expect(page.getByRole('alert').filter({hasText:'Unsupported capabilities: future_units/99'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Import model',exact:true})).toBeDisabled();
  // Correctly resealed bytes/inventory cannot turn malformed declarations into
  // valid input. Frontend inspection is deliberately not server authority.
  const malformed=structuredClone(f.package);malformed.revisions.at(-1).ports[0].units={kind:'currency'};
  const pkg=await rebuildPackage(page,malformed);
  await page.getByLabel('Portable model record file',{exact:true}).setInputFiles({name:'invalid-units.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(pkg))});
  await page.getByRole('button',{name:'Preview model import',exact:true}).click();
  await expect(page.getByRole('button',{name:'Import model',exact:true})).toBeEnabled();
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/model-imports'));
  await page.getByRole('button',{name:'Import model',exact:true}).click();expect((await response).status()).toBe(400);
  await expect(page.getByRole('alert').first()).toBeVisible();
});

async function runModels(page:Page,f:any) {
  await page.goto('/ui/#v=1&view=runs&study='+f.study_id+'&run='+f.run_id);
  // The run's Model tab (formerly Models) shows the canonical model view; its Quantities
  // table is always below the canvas (no Variables tab).
  await page.getByRole('tab',{name:'Model',exact:true}).click();
  await expect(page.locator('#run-panel-1').getByRole('table',{name:'Quantities',exact:true})).toBeVisible();
}
async function csvDownload(page: Page) {
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Quantities CSV', exact: true }).click();
  const csv = await readFile((await (await pending).path())!, 'utf8');
  await page.keyboard.press('Escape');
  return csv;
}
test('@units-history run CSV retains dimensionless zero physical output and absent records',async({page})=>{
  const f=await savedHistory(page);await outage(page);await runModels(page,f);
  const csv=await csvDownload(page),rows=csv.split('\r\n');
  expect(rows.find(r=>r.startsWith('"ratio",'))).toContain('"0"');
  expect(rows.find(r=>r.startsWith('"ratio",'))).toContain('"Dimensionless"');
  expect(rows.find(r=>r.startsWith('"flow",'))).toContain('"7"');
  expect(rows.find(r=>r.startsWith('"flow",'))).toContain('"m/s"');
  expect(rows.find(r=>r.startsWith('"incoming",'))).toContain('"Not recorded"');
  // Declared presentation overlay of a partial verified history, not corruption
  // validation. The backend's corrupt-record admission is proven by the history tests.
  const url='/api/1/studies/'+f.study_id+'/runs/'+f.run_id;
  const detail=await(await page.request.get(url)).json();detail.data.history.results.outputs=[];
  await page.route('**'+url,route=>route.fulfill({json:detail}));
  await page.getByRole('button',{name:'Return to run history',exact:true}).click();
  await page.getByRole('button',{name:'Inspect run '+f.run_id,exact:true}).click();
  await page.getByRole('tab',{name:'Model',exact:true}).click();await expect(page.locator('#run-panel-1').getByRole('table',{name:'Quantities',exact:true})).toBeVisible();
  const absent=(await csvDownload(page)).split('\r\n').find(r=>r.startsWith('"flow",'))!;
  expect(absent).toContain('"not computed"');expect(absent).toContain('"Not recorded"');expect(absent).not.toContain('"0"');
});
for(const code of ['missing_results','corrupt_retained_record','unsupported_record_version'])test('@units-history '+code+' keeps unavailable retained context truthful',async({page})=>{
  const f=await savedHistory(page),reads=await outage(page),url='/api/1/studies/'+f.study_id+'/runs/'+f.run_id;
  const detail=await(await page.request.get(url)).json();
  detail.data.history.model_snapshot=null;detail.data.history.results=null;detail.data.history.errors=[{code,message:'Declared isolated presentation fixture'}];
  await page.route('**'+url,route=>route.fulfill({json:detail}));
  await page.goto('/ui/#v=1&view=runs&study='+f.study_id+'&run='+f.run_id);
  const text=code==='missing_results'?'Some results are missing. What is available is shown below.':code==='corrupt_retained_record'?'Part of this run\'s record could not be verified. Verified sections remain visible.':'This run uses a record format this application cannot display.';
  await expect(page.getByRole('alert').filter({hasText:text})).toBeVisible();
  await expect(page.getByText('No results for this run. Missing values are never shown as zero.',{exact:true})).toBeVisible();
  await page.getByRole('tab',{name:'Model',exact:true}).click();
  await expect(page.locator('#run-panel-1').getByText('This run\'s model version can\'t be shown. The current model is not shown in its place.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Create modified run',exact:true})).toHaveCount(0);expect(reads).toEqual([]);
});
test('@units-history light dark narrow and genuine 200 percent keyboard evidence',async({baseURL})=>{
  test.setTimeout(180000);
  const root = process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,
    extension = join(root, 'artifacts/units-history-zoom-extension');
  await mkdir(extension);
  await writeFile(
    join(extension, 'manifest.json'),
    JSON.stringify({
      manifest_version: 3,
      name: 'Units historical zoom verification',
      version: '1.0',
      permissions: ['tabs'],
      background: { service_worker: 'worker.js' },
    }),
  );
  await writeFile(join(extension, 'worker.js'), 'chrome.runtime.onInstalled.addListener(()=>{});');
  const context = await chromium.launchPersistentContext(
    join(root, 'artifacts/units-history-zoom-profile'),
    {
      executablePath: chromiumExecutable(),
      headless: true,
      viewport: null,
      baseURL,
      args: [
        '--disable-extensions-except=' + extension,
        '--load-extension=' + extension,
        '--window-size=1440,1000',
        '--no-first-run',
      ],
    },
  );
  const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker')),
    geometry: any[] = [];
  try {
    const page = context.pages()[0] ?? (await context.newPage());
    page.on('pageerror', (e) => pageErrors.push(e.message));
    const f = await savedHistory(page);
    await outage(page);
    const cdp = await context.newCDPSession(page),
      info = await cdp.send('Browser.getWindowForTarget');
    async function resize(width: number, height: number) {
      const before = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
      const actual = (await cdp.send('Browser.getWindowBounds', { windowId: info.windowId }))
        .bounds;
      await cdp.send('Browser.setWindowBounds', {
        windowId: info.windowId,
        bounds: {
          width: actual.width! + width - before.width,
          height: actual.height! + height - before.height,
        },
      });
      await expect.poll(() => page.evaluate(() => innerWidth)).toBe(width);
    }
    async function capture(name: string) {
      await page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
          ),
      );
      // Flush computed styles and use a bounded wait for Foundry's theme
      // transitions before capturing their final colors.
      await expect
        .poll(() =>
          page.locator('.hf-btn:visible').evaluateAll((items) =>
            items.every((item) => {
              getComputedStyle(item).backgroundColor;
              return item.getAnimations().every((a) => a.playState !== 'running');
            }),
          ),
        )
        .toBe(true);
      const size = await page.evaluate(() => ({
        width: innerWidth,
        height: innerHeight,
        scrollWidth: document.documentElement.scrollWidth,
        dpr: devicePixelRatio,
      }));
      expect(size.scrollWidth).toBeLessThanOrEqual(size.width + 1);
      const labels = await page
        .locator('.change-table th .exact-proposal')
        .evaluateAll((items) =>
          items.map((item) => ({ width: item.clientWidth, scrollWidth: item.scrollWidth })),
        );
      for (const label of labels) expect(label.scrollWidth).toBeLessThanOrEqual(label.width + 1);
      const buttons = await page.locator('.hf-btn:visible').evaluateAll((items) =>
        items.map((item) => {
          const style = getComputedStyle(item);
          return {
            text: item.textContent,
            className: item.className,
            background: style.backgroundColor,
            color: style.color,
            border: style.borderColor,
            surface: style.getPropertyValue('--surface').trim(),
            hover: item.matches(':hover'),
            transition: style.transitionDuration,
            animations: item.getAnimations().map((a) => a.playState),
          };
        }),
      );
      for (const button of buttons) expect(button.animations).not.toContain('running');
      geometry.push({ name, ...size, labels, buttons });
      const shot = await cdp.send('Page.captureScreenshot', {
        format: 'png',
        fromSurface: true,
        captureBeyondViewport: false,
      });
      await writeFile(join(root, 'evidence/' + name + '.png'), Buffer.from(shot.data, 'base64'));
    }
    await resize(1440, 1000);
    const tab = await worker.evaluate(async (url) => {
      const tabs = await (globalThis as any).chrome.tabs.query({});
      return tabs.find((t: any) => t.url.startsWith(url)).id;
    }, baseURL!);
    async function mode(size: string) {
      await worker.evaluate((id) => (globalThis as any).chrome.tabs.setZoom(id, 1), tab);
      await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBe(1);
      await resize(size === 'narrow' ? 600 : 1440, size === 'narrow' ? 900 : 1000);
      if (size === '200') {
        await worker.evaluate((id) => (globalThis as any).chrome.tabs.setZoom(id, 2), tab);
        expect(
          await worker.evaluate((id) => (globalThis as any).chrome.tabs.getZoom(id), tab),
        ).toBe(2);
        expect(page.viewportSize()).toBeNull();
        await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);
      }
    }

    await page.goto(
      '/ui/#v=1&view=configurations&study=' +
        f.study_id +
        '&configuration=' +
        f.frozen.configuration.configuration_revision_id,
    );
    const saved = page.getByRole('region', { name: 'Saved configuration', exact: true });
    for (const size of ['desktop', 'narrow', '200']) {
      await mode(size);
      for (const theme of ['light', 'dark']) {
        await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
        await saved.getByRole('button', { name: 'Record details', exact: true }).focus();
        await capture('history-saved-context-' + size + '-' + theme);
        // One model-assumptions line; the retained model version opens read-only
        // in the canonical model view, where the model's assumptions carry their evidence.
        const assumption = saved.getByText(modelAssumptionsLine(f), { exact: true });
        await assumption.scrollIntoViewIfNeeded();
        await capture('history-saved-assumptions-' + size + '-' + theme);
        const open = saved.getByRole('button', { name: 'View model assumptions', exact: true });
        await open.focus();
        await page.keyboard.press('Enter');
        const modelDialog = page.getByRole('dialog', {
          name: 'Model assumptions',
          exact: true,
        });
        const evidence = modelDialog
          .getByRole('region', { name: 'Model assumptions', exact: true })
          .getByRole('button', { name: 'View evidence (1)', exact: true })
          .first();
        await evidence.focus();
        await page.keyboard.press('Enter');
        const dialog = page.getByRole('region', {name:'Evidence details',exact:true});
        await expect(dialog).toBeVisible();
        await capture('history-retained-evidence-' + size + '-' + theme);
        await page.keyboard.press('Escape');
        await expect(evidence).toBeFocused();
        await page.keyboard.press('Escape');
        await expect(modelDialog).toBeHidden();
        await expect(open).toBeFocused();
      }
    }
    await mode('desktop');
    await page.goto('/ui/#v=1&view=runs&study=' + f.study_id + '&run=' + f.run_id);
    for (const size of ['desktop', 'narrow', '200']) {
      await mode(size);
      for (const theme of ['light', 'dark']) {
        await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
        await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
        await page
          .locator('#run-panel-2')
          .getByText(modelAssumptionsLine(f), { exact: true })
          .scrollIntoViewIfNeeded();
        await capture('history-run-configuration-' + size + '-' + theme);
        await page.getByRole('tab', { name: 'Evidence', exact: true }).focus();
        await page.keyboard.press('Enter');
        await expect(page.getByRole('tab', { name: 'Evidence', exact: true })).toBeFocused();
        await page
          .locator('#run-panel-3')
          .getByText('Revised bounded assumption', { exact: true })
          .scrollIntoViewIfNeeded();
        await capture('history-run-evidence-' + size + '-' + theme);
      }
    }
    await mode('desktop');
    await page.getByRole('button', { name: 'Create modified run', exact: true }).click();
    await expect(page.getByLabel('Configuration name', { exact: true })).toBeVisible();
    for (const size of ['desktop', 'narrow', '200']) {
      await mode(size);
      for (const theme of ['light', 'dark']) {
        await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
        await page
          .getByRole('region', { name: 'Configuration assumption owners', exact: true })
          .filter({ visible: true })
          .getByText(modelAssumptionsLine(f), { exact: true })
          .scrollIntoViewIfNeeded();
        await capture('history-modified-assumptions-' + size + '-' + theme);
      }
    }
    // Comparison remains an isolated actual component consumer; owner-hidden
    // comparison navigation is not exposed by this test harness.
    await page.unroute('**/api/1/studies/*/models/**');
    await mode('desktop');
    await comparison(page, f);
    const unitGroup = page
      .getByRole('region', { name: 'Comparison', exact: true })
      .locator('details')
      .filter({ has: page.locator('summary').filter({ hasText: /^Ports and units/ }) });
    if ((await unitGroup.getAttribute('open')) === null)
      await unitGroup.locator('summary').first().click();
    for (const size of ['desktop', 'narrow', '200']) {
      await mode(size);
      for (const theme of ['light', 'dark']) {
        await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
        const labels = unitGroup.getByText(/Left: Energy law · unknown/);
        await labels.scrollIntoViewIfNeeded();
        await capture('history-comparison-' + size + '-' + theme);
      }
    }
    await page.keyboard.press('Escape');
    await expect(
      page.getByRole('button', { name: 'Export model', exact: true }),
    ).toBeFocused();
    await page.getByRole('button', { name: 'Import model', exact: true }).click();
    await page
      .getByLabel('Portable model record file', { exact: true })
      .setInputFiles({
        name: 'model.json',
        mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify(f.package)),
      });
    await page.getByRole('button', { name: 'Preview model import', exact: true }).click();
    for (const size of ['desktop', 'narrow', '200']) {
      await mode(size);
      for (const theme of ['light', 'dark']) {
        await page.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
        await page.getByRole('button', { name: 'Cancel', exact: true }).focus();
        await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
        await capture('history-package-inspector-' + size + '-' + theme);
      }
    }
    await writeFile(
      join(root, 'evidence/history-native-zoom.json'),
      JSON.stringify({ zoom: 2, viewport: null, geometry }, null, 2),
    );
  } finally {
    await context.close();
  }
});
