import { test, expect, Page } from 'playwright/test';
import { writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { evidencePath } from './evidence';
import { ownerPassword } from './support/served';

async function setup(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('New study name').fill(`Source ${crypto.randomUUID()}`);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page.getByLabel('New model name').fill('Source workspace');
  await page.getByRole('button', { name: 'Create model', exact: true }).click();
  await page.getByLabel('New component name').fill('Unicode source');
  await page.getByLabel('Input symbols').fill('x');await page.getByLabel('Output symbols').fill('y');
  await page.getByRole('button', { name: 'Add component', exact: true }).click();await apply(page);
  const sid=await page.getByRole('combobox',{name:'Study',exact:true}).inputValue();
  const mid=await page.getByRole('combobox',{name:'Model',exact:true}).inputValue();
  const path=`/api/1/studies/${sid}/models/${mid}`;
  return { read:async()=>(await(await page.request.get(path)).json()).data, path };
}
async function apply(page:Page) {
  const dialog=page.getByRole('dialog',{name:'Preview changes',exact:true});
  await expect(dialog.getByRole('button',{name:'Apply changes',exact:true})).toBeEnabled();
  await dialog.getByRole('button',{name:'Apply changes',exact:true}).click();await expect(dialog).not.toBeVisible();
}
test('source tools preserve raw bytes until a deliberate edit and save only through preview',async({page})=>{
  const f=await setup(page);const source=page.getByRole('textbox',{name:'Python source',exact:true});
  const raw=Buffer.from('\ufeff# café <script>window.sourceExecuted=true</script>\r\noutputs["y"] = inputs["x"]\r\n\r\n');
  await page.getByLabel('Load Python source file').setInputFiles({name:'unicode.py',mimeType:'text/x-python',buffer:raw});
  await expect(page.getByRole('toolbar',{name:'Source actions'})).toHaveCount(0);
  await expect(page.getByText('Declared symbols: x → y',{exact:true})).toBeVisible();
  await expect(page.locator('.source-highlight')).toContainText('<script>window.sourceExecuted=true</script>');
  expect(await page.evaluate(()=>Reflect.get(window,'sourceExecuted'))).toBeUndefined();
  await source.focus();await source.press('Escape');await expect(source).toBeFocused();
  await page.getByLabel('Find in source',{exact:true}).fill('outputs');await page.getByRole('button',{name:'Find next',exact:true}).click();
  expect(await source.evaluate((e:HTMLTextAreaElement)=>e.value.slice(e.selectionStart,e.selectionEnd))).toBe('outputs');
  await source.press('Tab');await expect(source).not.toBeFocused();
  const before=await f.read();await page.getByRole('button',{name:'Save component',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes',exact:true})).toBeVisible();expect(await f.read()).toEqual(before);await apply(page);
  const first=await f.read();const expected=createHash('sha256').update(raw).digest('hex');
  const instance=first.instances.find((i:any)=>i.name==='Unicode source');
  const definition=(m:any)=>m.definitions.find((d:any)=>d.definition_version_id===m.instances.find((i:any)=>i.instance_id===instance.instance_id).definition_version_id);
  expect(definition(first).source_refs).toEqual([expected]);
  expect(first.source_files.find((s:any)=>s.sha256===expected)?.bytes).toBe(raw.toString('base64'));
  await page.getByText('Assumptions',{exact:true}).click();await page.getByLabel('Component assumptions').fill('Only metadata changes.');
  await page.getByRole('button',{name:'Save component',exact:true}).click();await apply(page);
  const notes=await f.read();expect(definition(notes).source_refs).toEqual([expected]);
  expect(definition(notes).definition_version_id).toBe(definition(first).definition_version_id);
  expect(notes.source_files.find((s:any)=>s.sha256===expected)?.bytes).toBe(raw.toString('base64'));
  await source.fill('# intentional UTF-8 edit\noutputs["y"] = inputs["x"] + 2\n');
  await source.evaluate((e:HTMLTextAreaElement)=>e.setSelectionRange(0,e.value.length));
  await page.getByRole('button',{name:'Indent selection',exact:true}).click();await expect(source).toHaveValue('    # intentional UTF-8 edit\n    outputs["y"] = inputs["x"] + 2\n');
  await page.getByRole('button',{name:'Outdent selection',exact:true}).click();
  await expect(source).toHaveValue('# intentional UTF-8 edit\noutputs["y"] = inputs["x"] + 2\n');
  await page.getByRole('button',{name:'Save component',exact:true}).click();await apply(page);
  const changed=await f.read();expect(changed.draft_revision).not.toBe(first.draft_revision);
  const editedHash=createHash('sha256').update('# intentional UTF-8 edit\noutputs["y"] = inputs["x"] + 2\n').digest('hex');
  expect(definition(changed).source_refs).toEqual([editedHash]);
  expect(definition(changed).definition_version_id).not.toBe(definition(first).definition_version_id);
  expect(changed.source_files.some((s:any)=>Buffer.from(s.bytes,'base64').toString().includes('+ 2'))).toBeTruthy();
  writeFileSync(evidencePath('source-byte-proof.json'),JSON.stringify({original:raw.toString('base64'),sha256:expected,editedHash,first,notes,changed,candidate_executions:0},null,2));
});

test('source preserves caret and scrolling across widths',async({page})=>{
  await setup(page);const source=page.getByRole('textbox',{name:'Python source',exact:true});
  const text='# '+ 'long_identifier '.repeat(100)+'\n'+Array.from({length:40},(_,i)=>`# line ${i+2}`).join('\n');
  await source.fill(text);await source.evaluate((e:HTMLTextAreaElement)=>e.setSelectionRange(2,17));
  await page.getByRole('tab',{name:'Component',exact:true}).click();
  await page.getByRole('tab',{name:'Python',exact:true}).click();
  await expect(source).toHaveValue(text);
  expect(await source.evaluate((e:HTMLTextAreaElement)=>[e.selectionStart,e.selectionEnd])).toEqual([2,17]);
  await expect(page.locator('.source-line-numbers')).toContainText('41');
  expect(await source.evaluate((e:HTMLTextAreaElement)=>e.scrollWidth>e.clientWidth)).toBeTruthy();
  await source.evaluate((e:HTMLTextAreaElement)=>{e.scrollLeft=200;e.scrollTop=96;e.dispatchEvent(new Event('scroll'));});
  await expect(page.locator('.source-highlight')).toHaveCSS('transform','matrix(1, 0, 0, 1, -200, -96)');
  await source.evaluate((e:HTMLTextAreaElement)=>{e.scrollLeft=0;e.scrollTop=0;e.dispatchEvent(new Event('scroll'));});
  for(const width of [1440,720]){
    await page.setViewportSize({width,height:1000});await source.scrollIntoViewIfNeeded();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:evidencePath(`source-editor-${width}.png`),fullPage:true});
  }
  await source.focus();await source.press('Tab');await expect(source).not.toBeFocused();
  await expect(source).toHaveValue(text);
  await expect(page.getByText('Unsaved changes',{exact:true}).first()).toBeVisible();
});
