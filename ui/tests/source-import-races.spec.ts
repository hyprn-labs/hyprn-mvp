import { test, expect, Page } from 'playwright/test';
import { createHash } from 'node:crypto';
import { ownerPassword } from './support/served';
async function apply(page: Page) { const d=page.getByRole('dialog',{name:'Preview changes',exact:true}); await d.getByRole('button',{name:'Apply changes',exact:true}).click(); await expect(d).not.toBeVisible(); }
async function setup(page: Page) {
  await page.goto('/ui/'); await page.getByLabel('Username').fill('owner'); await page.getByLabel('Password',{exact:true}).fill(ownerPassword()); await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByLabel('New study name').fill(`Import race ${crypto.randomUUID()}`);await page.getByRole('button',{name:'Create study',exact:true}).click();
  await page.getByLabel('New model name').fill('Import ownership');await page.getByRole('button',{name:'Create model',exact:true}).click();
  await page.getByLabel('New component name').fill('Repeated');await page.getByLabel('Input symbols').fill('x');await page.getByLabel('Output symbols').fill('y');await page.getByRole('button',{name:'Add component',exact:true}).click();await apply(page);
  await page.getByRole('button',{name:'Add another instance',exact:true}).click();await apply(page);
  const sid=await page.getByRole('combobox',{name:'Study',exact:true}).inputValue(),mid=await page.getByRole('combobox',{name:'Model',exact:true}).inputValue();
  const read=async()=>(await(await page.request.get(`/api/1/studies/${sid}/models/${mid}`)).json()).data;
  const before=await read(),instances=before.instances.filter((i:any)=>i.instance_id!==before.root_instance_id);
  expect(instances[0].definition_version_id).toBe(instances[1].definition_version_id);
  await page.locator(`#panel-Graph [data-instance="${instances[0].instance_id}"]`).click();
  return {read,before,instances};
}
async function hold(page: Page, mode: 'read'|'hash') {
  await page.evaluate(mode=>{
    const w=window as any;w.importWaiting=false;w.releaseImport=undefined;
    const target=mode==='read'?File.prototype:crypto.subtle, key=mode==='read'?'arrayBuffer':'digest';
    const original=(target as any)[key];let once=true;
    (target as any)[key]=async function(...args:any[]){const value=await original.apply(this,args);if(once){once=false;w.importWaiting=true;await new Promise<void>((resolve,reject)=>{w.releaseImport=resolve;w.rejectImport=()=>reject(new Error('Delayed source read failed'));});}return value;};
  },mode);
}
const oldBytes=Buffer.from('\ufeff# delayed A\r\noutputs["y"] = 99\r\n');
for(const [view,mode] of [['Graph','read'],['XDSM','hash'],['Variables','read']] as const) test(`late ${mode} import cannot follow selection through ${view}`,async({page})=>{
  const f=await setup(page),source=page.getByRole('textbox',{name:'Python source',exact:true}),baseline=await source.inputValue();
  await hold(page,mode);await page.getByLabel('Load Python source file').setInputFiles({name:'a.py',mimeType:'text/x-python',buffer:oldBytes});await expect.poll(()=>page.evaluate(()=>(window as any).importWaiting)).toBe(true);
  await page.getByRole('tab',{name:view,exact:true}).click();
  if(view==='Variables')await page.locator(`[data-variable^="${f.instances[1].instance_id}/"]`).first().getByRole('button',{name:/^Inspect variable ·/}).click();
  else await page.locator(`#panel-${view} [data-instance="${f.instances[1].instance_id}"]`).click();
  await page.evaluate(()=>(window as any).releaseImport());await page.waitForTimeout(100);
  await expect(source).toHaveValue(baseline);await expect(page.getByRole('button',{name:'Save component',exact:true})).toBeDisabled();expect(await f.read()).toEqual(f.before);
  // A subsequent intentional import belongs to B, with exact original bytes and explicit preview.
  const raw=Buffer.from('\ufeff# correct B café\r\noutputs["y"] = inputs["x"]\r\n');
  await page.getByLabel('Load Python source file').setInputFiles({name:'b.py',mimeType:'text/x-python',buffer:raw});await expect(page.getByRole('button',{name:'Save component',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Save component',exact:true}).click();await expect(page.getByRole('dialog',{name:'Preview changes',exact:true})).toBeVisible();expect(await f.read()).toEqual(f.before);await apply(page);
  const after=await f.read(),a=after.instances.find((i:any)=>i.instance_id===f.instances[0].instance_id),b=after.instances.find((i:any)=>i.instance_id===f.instances[1].instance_id);
  expect(a.definition_version_id).toBe(f.instances[0].definition_version_id);expect(b.definition_version_id).not.toBe(a.definition_version_id);
  const sha=createHash('sha256').update(raw).digest('hex');expect(after.definitions.find((d:any)=>d.definition_version_id===b.definition_version_id).source_refs).toEqual([sha]);expect(after.source_files.find((s:any)=>s.sha256===sha).bytes).toBe(raw.toString('base64'));
});
test('discard and a newer import invalidate a delayed earlier import',async({page})=>{
  const f=await setup(page);await page.getByRole('textbox',{name:'Python source',exact:true}).fill('# local change');
  await hold(page,'read');await page.getByLabel('Load Python source file').setInputFiles({name:'a.py',mimeType:'text/x-python',buffer:oldBytes});await expect.poll(()=>page.evaluate(()=>(window as any).importWaiting)).toBe(true);
  await page.locator(`#panel-Graph [data-instance="${f.instances[1].instance_id}"]`).click();await page.getByRole('button',{name:'Discard changes',exact:true}).click();
  const next=Buffer.from('# newer B\noutputs["y"] = 2\n');await page.getByLabel('Load Python source file').setInputFiles({name:'b.py',mimeType:'text/x-python',buffer:next});
  await expect(page.getByRole('textbox',{name:'Python source',exact:true})).toHaveValue(next.toString());await page.evaluate(()=>(window as any).releaseImport());await page.waitForTimeout(100);
  await expect(page.getByRole('textbox',{name:'Python source',exact:true})).toHaveValue(next.toString());expect(await f.read()).toEqual(f.before);
});
test('a failed obsolete read leaves the new instance editable and error-free',async({page})=>{
  const f=await setup(page),source=page.getByRole('textbox',{name:'Python source',exact:true}),baseline=await source.inputValue();
  await hold(page,'read');await page.getByLabel('Load Python source file').setInputFiles({name:'a.py',mimeType:'text/x-python',buffer:oldBytes});await expect.poll(()=>page.evaluate(()=>(window as any).importWaiting)).toBe(true);
  await page.locator(`#panel-Graph [data-instance="${f.instances[1].instance_id}"]`).click();await page.evaluate(()=>(window as any).rejectImport());await page.waitForTimeout(100);
  await expect(source).toHaveValue(baseline);await expect(source).toBeEnabled();await expect(page.getByRole('alert')).toHaveCount(0);expect(await f.read()).toEqual(f.before);
});
test('unmounted source import cannot affect a reloaded draft',async({page})=>{
  const f=await setup(page);await hold(page,'hash');await page.getByLabel('Load Python source file').setInputFiles({name:'a.py',mimeType:'text/x-python',buffer:oldBytes});await expect.poll(()=>page.evaluate(()=>(window as any).importWaiting)).toBe(true);
  const link=page.url();await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByLabel('Username')).toBeVisible();await page.evaluate(()=>(window as any).releaseImport());await page.waitForTimeout(100);await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByLabel('Username').fill('owner');await page.getByLabel('Password',{exact:true}).fill(ownerPassword());await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.goto(link);
  await expect(page.locator(`#panel-Graph [data-instance="${f.instances[0].instance_id}"]`)).toBeVisible();expect(await f.read()).toEqual(f.before);
});
