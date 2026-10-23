import {test, expect, chromium, type Page, type APIRequestContext, type Locator} from 'playwright/test';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import { chromiumExecutable } from './support/browser';

async function openModel(page: Page) {
  const props = await (await page.request.get('/fixture')).json();
  await page.goto('/ui/#' + new URLSearchParams({v: '1', study: props.sid, model: props.mid, view: 'model'}));
  await page.getByLabel('Username', {exact:true}).fill('owner');
  await page.getByLabel('Password', {exact:true}).fill('correct horse battery staple');
  await page.getByRole('button', {name:'Sign in',exact:true}).click();
  // Details stack What it computes · Why · Assumptions; there are no detail tabs.
  await expect(page.getByRole('region',{name:'Selection inspector',exact:true}).getByRole('heading',{name:'Assumptions',exact:true})).toBeVisible();
  await expect(page.getByRole('tab',{name:'Assumptions',exact:true})).toHaveCount(0);
  return props;
}
/** Model-level assumptions live in the model view's Details with nothing selected
 * (the former Model actions › Model assumptions dialog is removed). */
async function modelDetails(page: Page) {
  const clear=page.getByRole('button',{name:'Clear selection',exact:true});
  if(await clear.isVisible())await clear.click();
  const details=page.getByRole('region',{name:'Selection inspector',exact:true});
  await expect(details.getByRole('region',{name:'Model assumptions',exact:true})).toBeVisible();
  return details;
}

async function editComponent(page: Page) {
  const dialog = page.getByRole('dialog', {name:'Edit component', exact:true});
  if (!await dialog.isVisible()) await page.getByRole('button', {name:'Edit component', exact:true}).click();
  return dialog;
}
async function editModelDetails(page: Page) {
  await modelDetails(page);
  await page.getByRole('button', {name:'Model actions', exact:true}).click();
  await page.getByRole('button', {name:'Edit model', exact:true}).click();
  return page.getByRole('dialog', {name:'Edit model', exact:true});
}

test('@ae-model component assumptions apply locally, preview exact uses and preserve independent instances', async ({page,request}) => {
  const library=await writer(request), note=await library.create('Model source report');
  const props=await openModel(page);
  const draftPath=`/api/1/studies/${props.sid}/models/${props.mid}`;
  const before=(await (await page.request.get(draftPath)).json()).data;
  // A component's annotation is its explanation and is shown as such; definition notes are
  // not shown. The stored annotation stays in the record unchanged.
  expect(before.annotations.map((a:any)=>a.text)).toEqual(['Original component note.']);
  await expect(page.getByLabel('Component notes',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Original component note.',{exact:true}).first()).toBeVisible();
  await expect(page.getByText('Definition note stays separate.',{exact:true})).toHaveCount(0);
  await editComponent(page);
  await page.getByRole('button',{name:'Add assumption',exact:true}).click();
  const editorFooter = page.getByRole('dialog', {name:'Edit assumption', exact:true}).locator('.dialog-footer');
  await expect(editorFooter.getByRole('button')).toHaveText(['Cancel', 'Apply assumption']);
  await expect(editorFooter.getByRole('button', {name:'Apply assumption', exact:true})).toHaveClass(/hf-btn--primary/);
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await expect(page.getByRole('alert')).toHaveText('Enter an assumption statement.');
  await expect(page.getByLabel('Statement',{exact:true})).toBeFocused();
  await page.getByLabel('Statement',{exact:true}).fill('Steady flow in component A');
  await page.keyboard.press('Enter');
  await page.keyboard.type('Explicit local condition.');
  await page.keyboard.press('Escape');
  await expect(page.getByText('Discard unsaved assumption changes?',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Keep editing',exact:true}).click();
  await expect(page.getByLabel('Statement',{exact:true})).toBeFocused();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('dialog',{name:'Edit assumption',exact:true}).locator('.hf-btn--primary')).toHaveCount(1);
  await shots(page,'model-assumption-editor');
  await page.getByRole('button',{name:'Add evidence',exact:true}).click();
  await page.getByLabel('Find evidence',{exact:true}).fill('Model source report');
  await page.getByRole('button',{name:/^Choose Model source report/}).click();
  await page.getByLabel('Relationship',{exact:true}).selectOption('supports');
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await expect(page.getByText('Unsaved local edits. Save the model draft to keep these changes.',{exact:true}).last()).toBeVisible();
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(before);
  await shots(page,'model-component-local');
  await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toContainText('Steady flow in component A');
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toContainText('Supports · '+note.evidence_version_id);
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toHaveCount(0);
  const saved=(await (await page.request.get(draftPath)).json()).data;
  expect(saved.assumptions).toHaveLength(1);
  expect(saved.assumptions[0].owner).toEqual({kind:'instance',instance_id:props.instances[1].instance_id});
  expect(saved.assumptions[0].statement).toContain('\nExplicit local condition.');
  expect(saved.assumptions[0].evidence_links).toEqual([{evidence_version_id:note.evidence_version_id,relation:'supports'}]);
  expect(saved.annotations).toEqual(before.annotations);
  await editComponent(page);
  await page.getByRole('button',{name:'Edit assumption: '+saved.assumptions[0].statement,exact:true}).click();
  await page.getByLabel('Statement',{exact:true}).fill('Revised condition for A');
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toHaveCount(0);
  const preVersion=(await (await page.request.get(draftPath)).json()).data;
  expect(preVersion.assumptions[0].assumption_id).toBe(saved.assumptions[0].assumption_id);
  const nextNote=await library.revise(note,'Revised model source report');
  await editComponent(page);
  await page.getByRole('button',{name:'Edit assumption: Revised condition for A',exact:true}).click();
  const editing=page.getByRole('dialog',{name:'Edit assumption',exact:true});
  const replacement=page.getByRole('dialog',{name:'Change evidence version',exact:true});
  const chooseVersion=async()=>{
    // Attachment actions live with the evidence the assumption opens.
    if(!await page.getByRole('button',{name:'Change version',exact:true}).count())await editing.getByRole('button',{name:'View evidence (1)',exact:true}).click();
    await page.getByRole('button',{name:'Change version',exact:true}).click();
    await expect(replacement.getByRole('button',{name:'Apply version change',exact:true})).toBeDisabled();
    await replacement.getByRole('button',{name:/^Choose Revised model source report/}).click();
    await expect(replacement.getByRole('region',{name:'Proposed evidence replacement'})).toContainText(note.evidence_version_id.slice(0,8)+' → Revised model source report · Version '+nextNote.evidence_version_id.slice(0,8));
    await expect(replacement.getByRole('region',{name:'Proposed evidence replacement'})).toContainText('From evidence version '+note.evidence_version_id+' to evidence version '+nextNote.evidence_version_id+'.');
    await expect(replacement).toContainText('The existing Supports relationship is preserved. Other uses remain unchanged.');
  };
  await chooseVersion();
  const proposed=replacement.getByRole('region',{name:'Proposed evidence replacement'});
  await proposed.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  const proposedDetail=page.getByRole('region', { name: 'Evidence details', exact: true });
  await expect(proposedDetail).toContainText(nextNote.content);
  await page.keyboard.press('Escape');
  await expect(proposedDetail).not.toBeVisible();
  await expect(replacement).toBeVisible();
  await expect(proposed.getByRole('button',{name:'View evidence (1)',exact:true})).toBeFocused();
  await expect(replacement.getByRole('button',{name:/^Choose Revised model source report/})).toHaveAttribute('aria-pressed','true');
  await expect(proposed).toContainText('From evidence version '+note.evidence_version_id+' to evidence version '+nextNote.evidence_version_id+'.');
  await expect(editing.getByText('Discard unsaved assumption changes?',{exact:true})).toHaveCount(0);
  await shots(page,'model-evidence-version-change');
  await replacement.getByRole('button',{name:'Keep current version',exact:true}).click();
  // Cancelling returns focus to the assumption's evidence, which still cites the original version.
  await expect(editing.getByRole('button',{name:'View evidence (1)',exact:true})).toBeFocused();
  await editing.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Model source report',exact:true})).toBeVisible();
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(preVersion);
  await chooseVersion();
  await replacement.getByRole('button',{name:'Apply version change',exact:true}).click();
  await expect(replacement).toHaveCount(0);
  await expect(editing.getByLabel('Statement',{exact:true})).toBeFocused();
  await expect(page.getByRole('heading',{name:'Revised model source report',exact:true})).toBeVisible();
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(preVersion);
  await editing.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toContainText('Supports · '+note.evidence_version_id);
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toContainText('Supports · '+nextNote.evidence_version_id);
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toHaveCount(0);
  const revised=(await (await page.request.get(draftPath)).json()).data;
  expect(revised.assumptions[0]).toEqual({...preVersion.assumptions[0],evidence_links:[{evidence_version_id:nextNote.evidence_version_id,relation:'supports'}]});
  await editComponent(page);
  const remove=page.getByRole('button',{name:'Remove assumption: Revised condition for A',exact:true});
  await remove.click();
  const removal=page.getByRole('dialog',{name:'Remove assumption',exact:true});
  await expect(removal).toContainText('Remove this assumption from Component · Component A?');
  await expect(removal).toContainText('Revised condition for A');
  await expect(removal).toContainText('Its evidence records and saved versions will remain.');
  await expect(removal.getByRole('button',{name:'Keep assumption',exact:true})).toBeFocused();
  await shots(page,'model-assumption-removal');
  await removal.getByRole('button',{name:'Keep assumption',exact:true}).click();
  await expect(remove).toBeFocused();
  await remove.click();
  await page.keyboard.press('Escape');
  await expect(remove).toBeFocused();
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(revised);
  await remove.click();
  await removal.getByRole('button',{name:'Remove assumption',exact:true}).click();
  await expect(page.getByRole('button',{name:'Add assumption',exact:true})).toBeFocused();
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(revised);
  await (await editComponent(page)).getByRole('button',{name:'Cancel',exact:true}).click();
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(revised);
  await page.getByRole('button',{name:'2 Component B',exact:true}).click();
  // Explicit graph selection changes the instance, never the shared definition's ownership.
  await expect(
    page.getByRole('region', { name: 'Component · Component B assumptions' })
      .getByText('No assumptions', { exact: true }),
  ).toHaveCount(1);
  await expect(page.getByText('Revised condition for A',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Model actions',exact:true})).toBeVisible();
  const modelDialog=await editModelDetails(page);
  await modelDialog.getByRole('button',{name:'Add assumption',exact:true}).click();
  await page.getByLabel('Statement',{exact:true}).fill('Model boundary remains fixed');
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await modelDialog.getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toContainText('Model boundary remains fixed');
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toHaveCount(0);
  await shots(page,'model-wide-saved');
  const final=(await (await page.request.get(draftPath)).json()).data;
  expect(final.assumptions).toHaveLength(2);
  expect(final.assumptions.filter((a:any)=>a.owner.kind==='instance')).toEqual(revised.assumptions);
  expect(final.assumptions.find((a:any)=>a.owner.kind==='model').evidence_links).toEqual([]);
  await expect(modelDialog).toBeHidden();
  await page.getByRole('dialog',{name:'Model actions',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Save model version',exact:true}).click();
  await expect.poll(async()=> (await (await page.request.get(draftPath+'/revisions')).json()).data.length).toBe(2);
  expect((await (await page.request.get(draftPath+'/revisions/'+props.revision.model_revision_id)).json()).data).toEqual(props.revision);
  const revisions=(await (await page.request.get(draftPath+'/revisions')).json()).data;
  await page.getByLabel('Model version',{exact:true}).selectOption(revisions[0].model_revision_id);
  await expect(page.getByText('Revised condition for A',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Add assumption',exact:true})).toHaveCount(0);
  await expect(page.getByText('Original component note.',{exact:true}).first()).toBeVisible();
  await expect(page.getByText('Definition note stays separate.',{exact:true})).toHaveCount(0);
  await shots(page,'model-read-only');
  // The read-only version lists its model-wide assumptions in Details with nothing selected.
  await expect(page.getByRole('button',{name:'View model assumptions',exact:true})).toHaveCount(0);
  await expect(await modelDetails(page)).toContainText('Model boundary remains fixed');
  await shots(page,'model-read-only-wide');
  await page.getByLabel('Model version',{exact:true}).selectOption('draft');
  await editComponent(page);
  await page.getByRole('button',{name:'Remove assumption: Revised condition for A',exact:true}).click();
  await page.getByRole('dialog',{name:'Remove assumption',exact:true}).getByRole('button',{name:'Remove assumption',exact:true}).click();
  await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toContainText('Revised condition for A');
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toHaveCount(0);
  const removed=(await (await page.request.get(draftPath)).json()).data;
  expect(removed.assumptions).toEqual(final.assumptions.filter((a:any)=>a.owner.kind==='model'));
  expect(removed.annotations).toEqual(before.annotations);
  expect((await (await page.request.get(draftPath+'/revisions/'+revisions[0].model_revision_id)).json()).data.assumptions).toEqual(final.assumptions);
  expect((await (await page.request.get(`/api/1/studies/${props.sid}/evidence/${note.evidence_version_id}`)).json()).data).toEqual(note);
  expect((await (await page.request.get(`/api/1/studies/${props.sid}/evidence/${nextNote.evidence_version_id}`)).json()).data).toEqual(nextNote);
});

test('@ae-model component assumptions show statement and evidence rows with one empty state and no owner line or notes', async ({page,request}) => {
  const library=await writer(request), source=await library.create('S3 inlet calibration');
  const props=await openModel(page);
  const draftPath=`/api/1/studies/${props.sid}/models/${props.mid}`;
  const before=(await (await page.request.get(draftPath)).json()).data;
  await editComponent(page);
  const region=page.getByRole('region',{name:'Component · Component A assumptions',exact:true});
  // Empty authoring keeps its heading and action without filler or a repeated component name.
  await expect(region.getByRole('heading',{name:'Assumptions',exact:true})).toBeVisible();
  await expect(region.getByText('No assumptions', { exact: true })).toHaveCount(0);
  await expect(region.getByRole('button',{name:'Add assumption',exact:true})).toBeVisible();
  await expect(region.getByText('Component · Component A',{exact:true})).toHaveCount(0);
  await expect(region).not.toContainText('No assumptions recorded');
  for(const removed of ['Notes','Component notes','Definition notes'])await expect(page.getByRole('heading',{name:removed,exact:true})).toHaveCount(0);
  await expect(page.getByLabel('Component notes',{exact:true})).toHaveCount(0);
  await expect(page.getByText('No recorded notes for this selection.',{exact:true})).toHaveCount(0);
  await s3Shots(page,'s3-component-assumptions-empty',region);
  // Populated: statement, then one evidence row per link (relationship · title · View evidence).
  await region.getByRole('button',{name:'Add assumption',exact:true}).click();
  await page.getByLabel('Statement',{exact:true}).fill('Inlet temperature is held at the design point');
  await page.getByRole('dialog',{name:'Edit assumption',exact:true}).getByRole('button',{name:'Add evidence',exact:true}).click();
  await page.getByLabel('Find evidence',{exact:true}).fill(source.title);
  await page.getByRole('button',{name:/^Choose S3 inlet calibration/}).click();
  await page.getByLabel('Relationship',{exact:true}).selectOption('supports');
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  const item=region.getByRole('article').filter({hasText:'Inlet temperature is held at the design point'});
  await expect(item).toHaveCount(1);
  await expect(item.getByRole('button',{name:'View evidence (1)',exact:true})).toBeVisible();
  // The relationship and source title are read in the evidence reader, not repeated inline.
  await expectEvidence(page, item, source.title, 'Supports');
  await expect(region.getByText('No assumptions',{exact:true})).toHaveCount(0);
  await expect(region.getByText('Component · Component A',{exact:true})).toHaveCount(0);
  await s3Shots(page,'s3-component-assumptions-populated',region);
  await item.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await expect(page.getByRole('region', { name: 'Evidence details', exact: true })).toContainText(source.content);
  await page.keyboard.press('Escape');
  await expect(item.getByRole('button',{name:'View evidence (1)',exact:true})).toBeFocused();
  // Nothing was saved: the stored draft, including its notes, is unchanged.
  expect((await (await page.request.get(draftPath)).json()).data).toEqual(before);
});

test('@ae-model package admission preserves exact mixed ancestry and rejects corrupt pairing, identities and bytes',async({page})=>{
  const props=await openModel(page);
  const result=await page.evaluate(async revision=>{
    const hash=async(value:string|Uint8Array)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',typeof value==='string'?new TextEncoder().encode(value):value as Uint8Array<ArrayBuffer>)),b=>b.toString(16).padStart(2,'0')).join('');
    const canonical=(v:any):string=>v===null||typeof v!=='object'?JSON.stringify(v):Array.isArray(v)?'['+v.map(canonical).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
    const sign=async(v:any)=>{delete v.digest;v.digest=await hash(canonical(v));return v;};
    const older=structuredClone(revision);older.schema_version='1';delete older.assumptions;await sign(older);
    const root=structuredClone(revision);root.model_revision_id=crypto.randomUUID();root.parent_model_revision_id=older.model_revision_id;root.assumptions=[{assumption_id:crypto.randomUUID(),owner:{kind:'model'},statement:'Opaque import reference',evidence_links:[{evidence_version_id:crypto.randomUUID(),relation:'context'}]}];await sign(root);
    const files=new Map<string,any>();
    for(const pin of [older,root]) {
      const add=async(path:string,raw:Uint8Array,media_type:string,role:string)=>{
        const key=(await hash('model-package-v1:'+path)).slice(0,32);
        files.set(path,{file_id:[key.slice(0,8),key.slice(8,12),key.slice(12,16),key.slice(16,20),key.slice(20)].join('-'),path,size:raw.length,sha256:await hash(raw),media_type,role});
      };
      await add('revisions/'+pin.model_revision_id+'.json',new TextEncoder().encode(canonical(pin)),'application/json','model');
      for(const source of pin.source_files)await add('sources/'+source.sha256+'.py',Uint8Array.from(atob(source.bytes),c=>c.charCodeAt(0)),'text/x-python','source');
    }
    const pkg=await sign({schema_version:'2',source_service:'fixture',model_id:root.model_id,model_revision_id:root.model_revision_id,revisions:[older,root],files:[...files.values()].sort((a,b)=>a.path.localeCompare(b.path)),required_capabilities:[],license_notices:[]});
    const check=(window as any).checkModelPackage;
    const accepted=await check(JSON.stringify(pkg));
    const failures=[];
    for(const kind of ['pairing','selected','duplicate','parent','digest','source','oversize']){
      const bad=structuredClone(pkg);
      if(kind==='pairing')bad.schema_version='1';
      if(kind==='selected')bad.model_revision_id=older.model_revision_id;
      if(kind==='duplicate')bad.revisions[1].model_revision_id=older.model_revision_id;
      if(kind==='parent')bad.revisions[1].parent_model_revision_id=crypto.randomUUID();
      if(kind==='source')bad.revisions[1].source_files[0].bytes=btoa('corrupt exact source');
      if(kind==='oversize')bad.revisions[1].source_files[0].bytes='A'.repeat(350000);
      await sign(bad.revisions[1]);
      await sign(bad);if(kind==='digest')bad.digest='0'.repeat(64);
      try{await check(JSON.stringify(bad));failures.push(kind+' accepted');}catch{failures.push(kind+' rejected');}
    }
    return {accepted,original:pkg,failures};
  },props.revision);
  expect(result.accepted).toEqual(result.original);
  expect(result.failures).toEqual(['pairing','selected','duplicate','parent','digest','source','oversize'].map(k=>k+' rejected'));
});

// Behavioral expectations of the evidence reader. Never skip or mark expected-failure.
async function openEvidence(page: Page, title = 'Heat capacity report') {
  const props = await (await page.request.get('/fixture')).json();
  await page.goto('/ui/#' + new URLSearchParams({v: '1', study: props.sid, view: 'evidence'}));
  await page.getByLabel('Username', {exact: true}).fill('owner');
  await page.getByLabel('Password', {exact: true}).fill('correct horse battery staple');
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await page.getByRole('button', {name: 'New evidence', exact: true}).click();
  await page.getByLabel('Title', {exact: true}).fill(title);
  await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill('Reference observation; applicability remains unassessed.');
  return props;
}

// Fixture authoring through public HTTP: only explicitly cited versions enter the library.
async function pinLibraryEvidence(page: Page, request: APIRequestContext, title: string) {
  await expect(page.getByRole('dialog',{name:/^(New evidence|Edit evidence)$/})).toBeHidden();
  const api = await writer(request);
  const rows = (await (await request.get(`/api/1/studies/${api.sid}/evidence?view=versions`)).json()).data;
  const record = rows.find((row:any) => row.title === title);
  expect(record).toBeTruthy();
  const state = (await (await request.get(`/api/1/studies/${api.sid}/brief`)).json()).data;
  const content = state.draft?.content ?? {schema_version:'1', question:'Evidence reading fixture', original_question:null, elaboration:null, scope:'', alternatives:[], criteria:[], assumptions:[], limits:[], open_questions:[]};
  const saved = await request.post(`/api/1/studies/${api.sid}/brief/draft`, {headers:api.headers, data:{command_id:crypto.randomUUID(), expected_revision:state.draft?.revision ?? null, content:{...content, assumptions:[...content.assumptions, {assumption_id:crypto.randomUUID(), statement:'Claim supported by '+title, evidence_links:[{evidence_version_id:record.evidence_version_id, relation:'supports'}]}]}}});
  expect(saved.status()).toBe(200);
  const refresh = page.getByRole('button',{name:'Refresh evidence',exact:true});
  await expect(refresh).toBeEnabled(); await refresh.click();
  await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
  return record;
}

test('@ae-evidence titled evidence shows its pinned version and exact content', async ({page,request}) => {
  await openEvidence(page);
  await page.getByRole('button', {name: 'Create evidence', exact: true}).click();
  await pinLibraryEvidence(page, request, 'Heat capacity report');
  const title = page.getByRole('heading', {name: 'Heat capacity report', exact: true});
  await expect(title).toHaveCSS('font-size', '16px');
  await expect(title).toHaveCSS('font-weight', '600');
  await expect(title).toHaveCSS('line-height', '24px');
  const detail = page.getByRole('region', { name: 'Evidence library', exact: true });
  await expect(detail.getByRole('button', {name:/View evidence/})).toHaveCount(0);
  await expect(detail).toContainText('Reference observation; applicability remains unassessed.');
  const card = detail.locator('article').filter({has:title});
  await card.getByRole('button',{name:'Evidence record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Evidence record',exact:true})).toContainText('Evidence version ID');
  await page.keyboard.press('Escape');
  await page.screenshot({path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/ae-evidence-title.png`});
});

test('@ae-evidence edit creates an immutable version and dirty Escape keeps text', async ({page,request}) => {
  const props = await openEvidence(page, 'Original report');
  await page.getByRole('button', {name: 'Create evidence', exact: true}).click();
  const original = await pinLibraryEvidence(page, request, 'Original report');
  const card = page.locator('article').filter({has: page.getByText('Original report', {exact: true})});
  await card.getByRole('button', {name: 'Edit', exact: true}).click();
  await page.getByLabel('Title', {exact: true}).fill('Revised report');
  await page.keyboard.press('Escape');
  await expect(page.getByText('Discard unsaved evidence changes?', {exact: true})).toBeVisible();
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    for (const width of [720, 390]) {
      await page.setViewportSize({width, height:700});
      const keep = page.getByRole('button', {name:'Keep editing', exact:true});
      await keep.scrollIntoViewIfNeeded();
      const left = (await keep.boundingBox())!;
      const right = (await page.getByRole('button', {name:'Discard changes', exact:true}).boundingBox())!;
      expect(right.x-left.x-left.width).toBeGreaterThanOrEqual(8);
      expect(Math.abs(left.y-right.y)).toBeLessThanOrEqual(1);
      expect(await page.getByRole('dialog', {name:'Edit evidence', exact:true})
        .evaluate(dialog => dialog.scrollWidth-dialog.clientWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/evidence-discard-${theme}-${width}.png`});
    }
  }
  await page.getByRole('button', {name: 'Keep editing', exact: true}).click();
  await expect(page.getByLabel('Title', {exact: true})).toHaveValue('Revised report');
  await page.getByRole('button', {name: 'Save new version', exact: true}).click();
  // Existing claim still reads its original version; revision does not retarget it.
  await expect(card).toBeVisible();
  await expect(page.getByRole('heading',{name:'Revised report',exact:true})).toHaveCount(0);
  await pinLibraryEvidence(page, request, 'Revised report');
  await expect(card).toBeVisible();
  const records = await (await page.request.get(`/api/1/studies/${props.sid}/evidence?view=versions`)).json();
  const versions = records.data.filter((r: {title?: string}) => ['Original report','Revised report'].includes(r.title ?? ''));
  expect(versions).toHaveLength(2);
  expect(versions[0].parent_evidence_version_id).toBe(versions[1].evidence_version_id);
});

test('@ae-evidence attachments open exact records directly with meaningful context and secondary identities', async ({page,request}) => {
  const api = await writer(request);
  const records = [
    await api.create('Direct calibration report'),
    await api.create('Direct observation report'),
  ];
  await harness(page, true);
  for (const [index, record] of records.entries()) {
    if (index) await page.getByRole('button', { name: 'Add evidence', exact: true }).click();
    await page.getByLabel('Find evidence', { exact: true }).fill(record.title);
    await page.getByRole('button', { name: new RegExp('^Choose ' + record.title) }).click();
    await page.getByRole('button', { name: 'Attach evidence', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByRole('button', { name: `View evidence (${index + 1})`, exact: true })).toHaveCount(1);
  }
  const reads: string[] = [];
  page.on('request', request => { if (request.url().includes('/evidence')) reads.push(request.url()); });
  const action = page.getByRole('button', { name: 'View evidence (2)', exact: true });
  await action.focus();
  await page.keyboard.press('Enter');
  const detail = page.getByRole('region', { name: 'Evidence details', exact: true });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(detail.locator('article')).toHaveCount(2);
  for (const record of records) {
    const source = detail.locator('article').filter({ has: page.getByRole('heading', { name: record.title, exact: true }) });
    await expect(source).toContainText(record.content);
    await expect(source.locator('script')).toHaveCount(0);
    await expect(source).toContainText('<script>inert reference</script>');
    await source.getByRole('button', { name: 'Evidence record details', exact: true }).click();
    const identities = page.getByRole('dialog', { name: 'Evidence record', exact: true });
    await expect(identities).toContainText(record.evidence_version_id);
    await expect(identities).toContainText(record.evidence_id);
    await expect(identities).toContainText(api.sid);
    await page.keyboard.press('Escape');
    await expect(source.getByRole('button', { name: 'Evidence record details', exact: true })).toBeFocused();
    const downloaded = page.waitForEvent('download');
    await source.getByRole('button', { name: 'Evidence record details', exact: true }).click();
    await identities.getByRole('button', { name: 'Download evidence record', exact: true }).click();
    expect(JSON.parse(await readFile((await (await downloaded).path())!, 'utf8'))).toEqual(record);
    await page.keyboard.press('Escape');
  }
  await shots(page, 'grouped-evidence');
  await detail.getByRole('button', { name: 'Close Evidence', exact: true }).click();
  await expect(action).toBeFocused();
  expect(reads).toEqual([]);
});

test('@ae-evidence uncertain create reconciles the original command once', async ({page,request}) => {
  await openEvidence(page, 'Recovered heat capacity report');
  let writes = 0;
  await page.route('**/api/1/studies/*/evidence', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    writes += 1;
    const saved = await route.fetch();
    expect(saved.status()).toBe(201);
    await route.abort('failed'); // Actual save succeeds; only the response is lost.
  });
  await page.getByRole('button', {name: 'Create evidence', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('The evidence may already be saved. Check the original command before trying again.');
  await page.getByRole('dialog').getByRole('button', {name: 'Check original command', exact: true}).click();
  await pinLibraryEvidence(page, request, 'Recovered heat capacity report');
  expect(writes).toBe(1);
  await page.screenshot({path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/ae-evidence-recovered.png`});
});
async function shots(page: Page, name: string) {
  for (const theme of ['light','dark']) {
    await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
    await page.screenshot({animations:'disabled',path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/${name}-${theme}.png`});
  }
}
async function expectEvidence(page: Page, owner: Locator, title: string, relation?: string) {
  await owner.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  const reader=page.getByRole('region',{name:'Evidence details',exact:true});
  await expect(reader).toContainText(title);
  if(relation)await expect(reader).toContainText(relation);
  await expect(reader.getByRole('button',{name:/^View evidence/})).toHaveCount(0);
  await reader.getByRole('button',{name:'Close Evidence',exact:true}).click();
}
// A configuration shows one line for its model's assumptions; the list opens from it.
async function viewModelAssumptions(page: Page, scope: Locator) {
  await scope.getByRole('button',{name:'View model assumptions',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Model assumptions',exact:true});
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('region',{name:'Model view',exact:true})).toBeVisible();
  await dialog.getByRole('tab',{name:'Model explanation',exact:true}).click();
  return dialog;
}
// 1440 x 1000 light/dark and 200 percent (720 CSS px at device scale 2) light/dark, without horizontal overflow.
async function s3Shots(page: Page, name: string, target?: Locator) {
  const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const cdp=await page.context().newCDPSession(page);
  const capture=async(file:string)=>{
    await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
    const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
    await writeFile(join(root,'evidence',file+'.png'),Buffer.from(shot.data,'base64'));
  };
  try {
    for(const [size,metrics] of [['1440',{width:1440,height:1000,deviceScaleFactor:1,mobile:false}],['200',{width:720,height:500,deviceScaleFactor:2,mobile:false}]] as const){
      await cdp.send('Emulation.setDeviceMetricsOverride',metrics);
      for(const theme of ['light','dark']){
        await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
        if(target)await target.evaluate(element=>element.scrollIntoView({block:'start'}));
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
        await capture(name+'-'+size+'-'+theme);
      }
    }
  } finally {
    await cdp.send('Emulation.clearDeviceMetricsOverride');await cdp.detach();
    await page.evaluate(()=>document.documentElement.dataset.theme='light');
  }
}
async function harness(page: Page, general = false) {
  await page.goto('/ui/?harness' + (general ? '&general' : ''));
  await page.getByRole('button', {name: 'Fixture sign in'}).click();
  await page.getByRole('button', {name: 'Add evidence', exact: true}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
}
async function writer(request: APIRequestContext) {
  const {sid} = await (await request.get('/fixture')).json();
  const login = await request.post('/api/1/session', {headers:{Origin:process.env.HYPRN_MVP_TEST_SCOPE_URL!},data:{username:'owner',password:'correct horse battery staple'}});
  expect(login.status()).toBe(200);
  const session = await login.json();
  const headers = {'X-CSRF-Token':session.data.csrf_token, Origin: process.env.HYPRN_MVP_TEST_SCOPE_URL!};
  const create = async (title: string) => {
    const response = await request.post(`/api/1/studies/${sid}/evidence`, {headers, data:{command_id:crypto.randomUUID(),evidence_schema_version:'3',title,kind:'note',content:'Exact note for '+title,source_refs:['<script>inert reference</script>'],resource_scope:{scope_version:'1',kind:'study',study_id:sid}}});
    expect(response.status()).toBe(201); return (await response.json()).data;
  };
  const revise = async (record: any, title: string) => {
    const response = await request.post(`/api/1/studies/${sid}/evidence-families/${record.evidence_id}/versions`, {headers,data:{command_id:crypto.randomUUID(),evidence_schema_version:'3',expected_revision:record.evidence_version_id,title,kind:record.kind,content:record.content,source_refs:record.source_refs,resource_scope:record.resource_scope}});
    expect(response.status()).toBe(201); return (await response.json()).data;
  };
  return {sid,create,revise,headers};
}

test('@ae-model concurrent add and revision survive clean version refresh and an unrelated save', async ({page,request,browser,baseURL}) => {
  const library=await writer(request), props=await (await request.get('/fixture')).json();
  const path=`/api/1/studies/${props.sid}/models/${props.mid}`;
  const original=(await (await request.get(path)).json()).data;
  const seeded=await request.post(path+'/edits',{headers:library.headers,data:{schema_version:'2',command_id:crypto.randomUUID(),expected_revision:original.draft_revision,edits:[{kind:'add_assumption',temp_key:'initial',owner:{kind:'model'},statement:'Initial remote condition',evidence_links:[]}]}});
  expect(seeded.status()).toBe(200);
  await openModel(page);
  const other=await browser.newContext({baseURL}), remote=await other.newPage();
  try {
    await openModel(remote);
    const owner=await editModelDetails(remote);
    await owner.getByRole('button',{name:'Edit assumption: Initial remote condition',exact:true}).click();
    await remote.getByLabel('Statement',{exact:true}).fill('Updated by the other authorized tab');
    await remote.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await owner.getByRole('button',{name:'Add assumption',exact:true}).click();
    await remote.getByLabel('Statement',{exact:true}).fill('Added by the other authorized tab');
    await remote.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await owner.getByRole('button',{name:'Save draft',exact:true}).click();
    await remote.getByRole('dialog',{name:'Preview changes',exact:true}).getByRole('button',{name:'Apply changes',exact:true}).click();
    await expect(remote.getByRole('dialog',{name:'Preview changes',exact:true})).toHaveCount(0);
    const authoritative=(await (await request.get(path)).json()).data;
    const commands:any[]=[];
    page.on('request',r=>{if(r.method()==='POST' && r.url().endsWith(path+'/preview'))commands.push(r.postDataJSON());});
    await page.getByRole('button',{name:'Save model version',exact:true}).click();
    await expect(page.getByText(/Model version [a-f0-9]+ saved\./)).toBeVisible();
    const local=await modelDetails(page);
    await expect(local).toContainText('Updated by the other authorized tab');
    await expect(local).toContainText('Added by the other authorized tab');
    await expect(local.getByRole('button',{name:'Add assumption',exact:true})).toHaveCount(0);
    await shots(page,'editor-clean-refreshed');
    await page.getByRole('button',{name:'1 Component A',exact:true}).click();
    // Component notes are no longer authored in the UI; the unrelated local save is a component assumption.
    await expect(page.getByLabel('Component notes',{exact:true})).toHaveCount(0);
    await editComponent(page);
    await page.getByRole('button',{name:'Add assumption',exact:true}).click();
    await page.getByLabel('Statement',{exact:true}).fill('Benign local assumption after clean refresh');
    await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
    const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});
    await expect(preview).toContainText('Benign local assumption after clean refresh');
    expect(commands).toHaveLength(1);
    expect(commands[0].expected_revision).toBe(authoritative.draft_revision);
    expect(commands[0].edits).toHaveLength(1);
    expect(commands[0].edits[0]).toMatchObject({kind:'add_assumption',owner:{kind:'instance',instance_id:props.instances[1].instance_id},statement:'Benign local assumption after clean refresh',evidence_links:[]});
    await preview.getByRole('button',{name:'Apply changes',exact:true}).click();
    await expect(preview).toHaveCount(0);
    const final=(await (await request.get(path)).json()).data;
    expect(final.assumptions.filter((a:any)=>a.statement!=='Benign local assumption after clean refresh')).toEqual(authoritative.assumptions);
    expect(final.assumptions.filter((a:any)=>a.statement==='Benign local assumption after clean refresh')).toHaveLength(1);
    expect(final.annotations).toEqual(authoritative.annotations);
    expect(final.source_files).toEqual(authoritative.source_files);
    await shots(page,'editor-clean-benign-saved');
    // A second local assumption beside a stored one on the same component previews one add only;
    // the stored assumption is unchanged and must not be sent as an update.
    await editComponent(page);
    await page.getByRole('button',{name:'Add assumption',exact:true}).click();
    await page.getByLabel('Statement',{exact:true}).fill('Second local assumption beside a stored one');
    await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
    await expect(preview).toContainText('Second local assumption beside a stored one');
    expect(commands).toHaveLength(2);
    expect(commands[1].edits.map((e:any)=>e.kind)).toEqual(['add_assumption']);
    await preview.getByRole('button',{name:'Keep editing',exact:true}).click();
    expect((await (await request.get(path)).json()).data).toEqual(final);
    await writeFile(join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/editor-clean-concurrency.json'),JSON.stringify({original,authoritative,commands,final},null,2));
  } finally {await other.close();}
});

test('@ae-model in-flight clean refresh preserves dirty local owner and original CAS until explicit reconciliation', async ({page,request,browser,baseURL}) => {
  const library=await writer(request), props=await openModel(page),path=`/api/1/studies/${props.sid}/models/${props.mid}`;
  const original=(await (await request.get(path)).json()).data;
  const other=await browser.newContext({baseURL}),remote=await other.newPage();
  let release!:()=>void; const held=new Promise<void>(resolve=>release=resolve);
  let received!:()=>void; const started=new Promise<void>(resolve=>received=resolve);
  try {
    await openModel(remote);
    await editComponent(remote);
    await remote.getByRole('button',{name:'Add assumption',exact:true}).click();
    await remote.getByLabel('Statement',{exact:true}).fill('Remote component condition stays');
    await remote.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await (await editComponent(remote)).getByRole('button',{name:'Save draft',exact:true}).click();
    await remote.getByRole('dialog',{name:'Preview changes',exact:true}).getByRole('button',{name:'Apply changes',exact:true}).click();
    await expect(remote.getByRole('dialog',{name:'Preview changes',exact:true})).toHaveCount(0);
    const authoritative=(await (await request.get(path)).json()).data;
    // Delay a real public GET response. Local editing remains available while
    // Workspace saves a version; no synthetic props or alternate writer seam.
    await page.route('**'+path,async route=>{
      if(route.request().method()!=='GET')return route.continue();
      const response=await route.fetch();received();await held;await route.fulfill({response});
    });
    const commands:any[]=[];
    page.on('request',r=>{if(r.method()==='POST' && r.url().endsWith(path+'/preview'))commands.push(r.postDataJSON());});
    await page.getByRole('button',{name:'Save model version',exact:true}).click();await started;
    // Notes are not authored in the UI; an applied local component assumption is the dirty local owner.
    await editComponent(page);
    await page.getByRole('button',{name:'Add assumption',exact:true}).click();
    await page.getByLabel('Statement',{exact:true}).fill('Local applied assumption survives refresh');
    await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await editComponent(page);
    await page.getByRole('button',{name:'Add assumption',exact:true}).click();
    await page.getByLabel('Statement',{exact:true}).fill('Local open assumption survives refresh');
    release();
    await expect(page.getByText(/Model version [a-f0-9]+ saved\./)).toBeVisible();
    await expect(page.getByLabel('Statement',{exact:true})).toHaveValue('Local open assumption survives refresh');
    await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
    await expect(page.getByText('Local applied assumption survives refresh',{exact:true}).filter({visible:true})).toBeVisible();
    await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
    const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});
    await expect(preview.getByRole('alert')).toContainText('changed');
    expect(commands[0].expected_revision).toBe(original.draft_revision);
    expect(commands[0].edits.map((e:any)=>e.kind)).toEqual(['add_assumption','add_assumption']);
    await preview.getByRole('button',{name:'Review current revision',exact:true}).click();
    await expect(preview.getByRole('region',{name:'Current revision differences'})).toContainText('Remote component condition stays');
    await shots(page,'editor-refresh-stale-review');
    await preview.getByRole('button',{name:'Keep editing',exact:true}).click();
    await expect(page.getByText('Local open assumption survives refresh',{exact:true}).filter({visible:true})).toBeVisible();
    await expect(page.getByText('Local applied assumption survives refresh',{exact:true}).filter({visible:true})).toBeVisible();
    expect((await (await request.get(path)).json()).data).toEqual(authoritative);
    await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
    await expect(preview.getByRole('alert')).toContainText('changed');
    expect(commands[1].expected_revision).toBe(original.draft_revision);
    await preview.getByRole('button',{name:'Review current revision',exact:true}).click();
    await preview.getByRole('button',{name:'Re-preview preserved proposal',exact:true}).click();
    await expect(preview.getByRole('button',{name:'Apply changes',exact:true})).toBeEnabled();
    expect(commands[2].expected_revision).toBe(authoritative.draft_revision);
    expect(commands[2].edits).toEqual(commands[1].edits);
    await preview.getByRole('button',{name:'Apply changes',exact:true}).click();
    await expect(preview).toHaveCount(0);
    const final=(await (await request.get(path)).json()).data;
    const local=['Local open assumption survives refresh','Local applied assumption survives refresh'];
    expect(final.assumptions.filter((a:any)=>!local.includes(a.statement))).toEqual(authoritative.assumptions);
    for(const statement of local)expect(final.assumptions.filter((a:any)=>a.statement===statement)).toHaveLength(1);
    expect(final.annotations).toEqual(original.annotations);
    expect(final.source_files).toEqual(original.source_files);
    await expect(page.getByText('Local applied assumption survives refresh',{exact:true}).filter({visible:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Save component',exact:true})).toBeHidden();
    await shots(page,'editor-explicit-reconciliation');
    await writeFile(join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/editor-dirty-concurrency.json'),JSON.stringify({original,authoritative,commands,final},null,2));
  } finally {release();await other.close();}
});

test('@ae-evidence picker separates create/attach, requires authored relationship and retains exact history', async ({page,request}) => {
  await harness(page);
  await page.getByRole('button', {name:'Create new',exact:true}).click();
  await page.getByLabel('Title',{exact:true}).fill('Picker source');
  await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill('Full exact content\nSecond line');
  await page.getByLabel('Source references',{exact:true}).fill('<script>inert source</script>');
  await page.getByRole('button',{name:'Create evidence',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Evidence saved to the library.');
  await expect(page.getByText('Attached versions: 0; relationship:',{exact:true})).toBeAttached();
  await expect(page.getByLabel('Relationship',{exact:true})).toHaveValue('');
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await expect(page.getByRole('alert')).toHaveText('Choose a relationship.');
  await expect(page.getByLabel('Relationship',{exact:true})).toBeFocused();
  await shots(page,'picker-saved-relationship-error');
  await page.getByLabel('Relationship',{exact:true}).selectOption('challenges');
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await expect(page.getByText('Attached versions: 1; relationship: challenges',{exact:true})).toBeVisible();
  const api = await writer(request), rows = await (await request.get(`/api/1/studies/${api.sid}/evidence`)).json();
  const original=rows.data.find((r:any)=>r.title==='Picker source');
  await api.revise(original,'Newer picker source');
  const evidenceReads: string[]=[];
  page.on('request',req=>{if(req.url().includes('/evidence'))evidenceReads.push(req.url());});
  await expect(page.getByRole('button',{name:/^Evidence \(/})).toHaveCount(0);
  await page.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  const detail=page.getByRole('region',{name:'Evidence details',exact:true});
  await detail.getByRole('button',{name:'Evidence record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Evidence record',exact:true})).toContainText(original.evidence_version_id);
  await page.keyboard.press('Escape');
  await expect(detail).toContainText('Picker source');
  await expect(detail).not.toContainText('Newer picker source');
  await expect(detail.getByRole('button',{name:'Versions',exact:true})).toHaveCount(0);
  await expect(detail).toContainText('<script>inert source</script>');
  await shots(page,'pinned-detail');
  expect(evidenceReads).toEqual([]);
});

test('@ae-evidence pending picker survives unmount, keeps original command and never follows another owner', async ({page}) => {
  await harness(page);
  await page.getByRole('button',{name:'Create new',exact:true}).click();
  await page.getByLabel('Title',{exact:true}).fill('Uncertain picker source');
  await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill('Draft belongs only to component A.');
  let writes=0;
  await page.route('**/api/1/studies/*/evidence',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    writes++;expect((await route.fetch()).status()).toBe(201);await route.abort('failed');
  });
  await page.getByRole('button',{name:'Create evidence',exact:true}).click();
  await expect(page.getByText('Outcome uncertain',{exact:true})).toBeVisible();
  await expect(page.getByRole('dialog').getByText('The evidence may already be saved. Check the original command before trying again.',{exact:true})).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeVisible();
  await shots(page,'picker-uncertain');
  await page.evaluate(()=>{(window as any).aeHarness.owner('Component B assumption');});
  await page.getByRole('button',{name:'Create new',exact:true}).click();
  await expect(page.getByLabel('Title',{exact:true})).toHaveValue('');
  await expect(page.getByRole('button',{name:'Check original command',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Create evidence',exact:true})).toBeDisabled();
  await page.evaluate(()=>{(window as any).aeHarness.owner('Component A assumption');(window as any).aeHarness.close();});
  await page.getByRole('button',{name:'Add evidence',exact:true}).click();
  await page.getByRole('button',{name:'Create new',exact:true}).click();
  await expect(page.getByLabel('Title',{exact:true})).toHaveValue('Uncertain picker source');
  await page.getByRole('button',{name:'Check original command',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Evidence saved to the library.');
  await expect(page.getByText('Attached versions: 0; relationship:',{exact:true})).toBeAttached();
  expect(writes).toBe(1);
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(page.getByRole('button',{name:'Add evidence',exact:true})).toBeFocused();
});

test('@ae-evidence stale head preserves edits and requires explicit reapplication', async ({page,request}) => {
  const api = await writer(request), original=await api.create('Stale report');
  await openEvidence(page,'unused');
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByRole('button',{name:'Discard changes',exact:true}).click();
  await pinLibraryEvidence(page, request, 'Stale report');
  await page.locator('article').filter({has:page.getByRole('heading',{name:'Stale report',exact:true})}).getByRole('button',{name:'Edit',exact:true}).click();
  await page.getByLabel('Title',{exact:true}).fill('My preserved report');
  await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill('My precise preserved note');
  const concurrent = await (await writer(request)).revise(original,'Concurrent report');
  await page.getByRole('button',{name:'Save new version',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('A newer evidence version was saved.');
  await expect(page.getByLabel('Title',{exact:true})).toHaveValue('My preserved report');
  await page.getByRole('button',{name:'Review latest version',exact:true}).click();
  await expect(page.getByRole('region',{name:'Latest evidence version'})).toContainText('Concurrent report');
  await shots(page,'stale-edit');
  await page.getByRole('button',{name:'Reapply edits to this version',exact:true}).click();
  await page.getByRole('button',{name:'Save new version',exact:true}).click();
  await pinLibraryEvidence(page, request, 'My preserved report');
  const rows=await (await request.get(`/api/1/studies/${api.sid}/evidence`)).json(), saved=rows.data.find((r:any)=>r.title==='My preserved report');
  expect(saved.parent_evidence_version_id).toBe(concurrent.evidence_version_id);
  expect(saved.content).toBe('My precise preserved note');
  await shots(page,'library');
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByRole('button',{name:'New evidence',exact:true})).toBeInViewport();
  await shots(page,'library-top');
});

test('@ae-evidence exact older selection has no relation control for general attachments', async ({page,request})=>{
  const api=await writer(request), original=await api.create('Version choice original');
  await api.revise(original,'Version choice current');
  await harness(page,true);
  await expect(page.getByLabel('Relationship',{exact:true})).toHaveCount(0);
  await page.getByLabel('Find evidence',{exact:true}).fill('Version choice current');
  await page.locator('article').filter({hasText:'Version choice current'}).getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await page.getByRole('button',{name:'Versions',exact:true}).click();
  await page.getByRole('button',{name:/^Inspect Version choice original/}).click();
  await page.getByRole('button',{name:'Choose this version',exact:true}).click();
  await page.getByRole('button',{name:'Close Evidence',exact:true}).click();
  await expect(page.getByRole('region',{name:'Selected evidence'})).toContainText(original.title);
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await page.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await expect(page.getByRole('region',{name:'Evidence details',exact:true})).toContainText('Version choice original');
});

test('@ae-evidence revoked current membership clears selected content and prevents attachment',async({page,request})=>{
  const api=await writer(request); await api.create('Private revoked note');
  await harness(page,true);
  await page.getByLabel('Find evidence',{exact:true}).fill('Private revoked note');
  await page.getByRole('button',{name:/^Choose Private revoked note/}).click();
  try {
    expect((await request.post('/fixture/membership',{data:{enabled:false}})).status()).toBe(200);
    await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
    await expect(page.getByRole('alert').filter({hasText: 'Access to this evidence is no longer available.'})).toHaveCount(1);
    await expect(page.getByRole('dialog').getByText(/Access to this evidence is no longer available\./)).toHaveCount(1);
    await expect(page.getByRole('heading',{name:'Private revoked note',exact:true})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'Attach evidence',exact:true})).toHaveCount(0);
    await shots(page,'revoked-picker');
  } finally {expect((await request.post('/fixture/membership',{data:{enabled:true}})).status()).toBe(200);}
});
test('@ae-evidence current library and immutable version lists load bounded pages',async({page,request})=>{
  const api=await writer(request);
  let version=await api.create('Paged family 0');
  const original=version;
  for(let i=1;i<=21;i++)version=await api.revise(version,'Paged family '+i);
  for(let i=0;i<22;i++)await api.create('Paged extra '+i);
  await harness(page,true);
  await expect(page.getByRole('dialog').locator('article')).toHaveCount(20);
  await page.getByRole('button',{name:'Load more evidence records',exact:true}).click();
  await page.getByLabel('Find evidence',{exact:true}).fill('Paged extra 21');
  await expect(page.getByRole('heading',{name:'Paged extra 21',exact:true})).toBeVisible();
  await page.getByLabel('Find evidence',{exact:true}).fill('Paged family');
  await page.getByRole('dialog').getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await page.getByRole('button',{name:'Versions',exact:true}).click();
  await expect(page.getByRole('region',{name:'Evidence versions'}).getByRole('button',{name:/^Inspect /})).toHaveCount(20);
  await page.getByRole('button',{name:'Load more evidence versions',exact:true}).click();
  await page.getByRole('button',{name:/^Inspect Paged family 0 ·/}).click();
  await page.getByRole('region',{name:'Evidence details',exact:true}).getByRole('button',{name:'Evidence record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Evidence record',exact:true})).toContainText(original.evidence_version_id);
  await shots(page,'version-pages');
});

test('@ae-configuration current copies retain explicit assumption and general uses', async ({page,request}) => {
  const library=await writer(request), note=await library.create('Configuration source report');
  await openModel(page);
  await page.getByRole('button',{name:'Create configuration',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Exact configuration');
  for (const name of ['Component A','Component B']) {
    await page.getByLabel(name+' · x value',{exact:true}).fill('2');
    await page.getByLabel(name+' · x provenance',{exact:true}).fill('Explicit measured input');
    // Units are an explicit choice; the model quantity is Dimensionless.
    await page.getByLabel(name+' · x units',{exact:true}).selectOption('dimensionless');
  }
  const assumptions=page.getByRole('region',{name:'Configuration assumptions',exact:true});
  await assumptions.getByRole('button',{name:'Add assumption',exact:true}).click();
  await page.getByLabel('Statement',{exact:true}).fill('Constant operating condition');
  await page.getByRole('dialog',{name:'Edit assumption',exact:true}).getByRole('button',{name:'Add evidence',exact:true}).click();
  await page.getByLabel('Find evidence',{exact:true}).fill(note.title);
  await chooseLoadedEvidence(page,'Configuration source report');
  await page.getByLabel('Relationship',{exact:true}).selectOption('challenges');
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await shots(page,'configuration-current');
  await page.getByRole('button',{name:'Input tools',exact:true}).click();
  const context=page.getByRole('dialog',{name:'Input tools and model binding',exact:true});
  await context.getByRole('button',{name:'Add evidence',exact:true}).click();
  await page.getByLabel('Find evidence',{exact:true}).fill(note.title);
  await chooseLoadedEvidence(page,'Configuration source report');
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await context.getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
  await expect(assumptions).toContainText('Constant operating condition');
  await shots(page,'configuration-saved');
  const props=await (await page.request.get('/fixture')).json();
  const all=(await (await page.request.get('/api/1/studies/'+props.sid+'/configurations')).json()).data;
  const original=all.find((v:any)=>v.configuration.name==='Exact configuration');
  // A new configuration is version 6: no criteria and no approach binding.
  expect(original.configuration.schema_version).toBe('6');expect(original.configuration).not.toHaveProperty('criteria');
  expect(original.configuration).not.toHaveProperty('approach_binding');expect(original).not.toHaveProperty('approach_closure');
  expect(original.configuration.general_context_evidence_version_ids).toEqual([note.evidence_version_id]);
  expect(original.configuration.assumptions[0].evidence_links).toEqual([{evidence_version_id:note.evidence_version_id,relation:'challenges'}]);
  expect(original.configuration.evidence_snapshots).toHaveLength(1);
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Independent copy');
  await page.getByRole('button',{name:'Input tools',exact:true}).click();
  await context.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await page.getByRole('button',{name:'Remove attachment',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Attached evidence',exact:true})).toHaveCount(0);
  await context.getByRole('button',{name:'Done',exact:true}).click();
  await expectEvidence(page, assumptions, 'Configuration source report', 'Challenges');
  await page.getByRole('tab',{name:'Runs',exact:true}).click();
  const navigation=page.getByRole('dialog',{name:'Unsaved changes',exact:true});
  await expect(navigation).toBeVisible();
  await navigation.getByRole('button',{name:'Keep editing',exact:true}).click();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Independent copy');
  await expect(assumptions).toContainText('Constant operating condition');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
  const copies=(await (await page.request.get('/api/1/studies/'+props.sid+'/configurations')).json()).data;
  const copy=copies.find((v:any)=>v.configuration.name==='Independent copy');
  expect(copy.configuration.general_context_evidence_version_ids).toEqual([]);
  expect(copy.configuration.assumptions).toEqual(original.configuration.assumptions);
  expect(copy.configuration.evidence_snapshots).toEqual(original.configuration.evidence_snapshots);
  expect(copies.find((v:any)=>v.configuration.configuration_revision_id===original.configuration.configuration_revision_id)).toEqual(original);
  await shots(page,'configuration-copy');
});

const studyCriteria='Criteria are defined in the study brief and evaluated in analyses.';
/** Attachment actions live with the evidence an assumption opens. */
async function changeVersion(page: Page) {
  const change=page.getByRole('button',{name:'Change version',exact:true});
  if(!await change.count())await page.getByRole('dialog',{name:'Edit assumption',exact:true}).getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await change.click();
}
async function configurationCase(request: APIRequestContext, kind='current') {
  const response=await request.post('/fixture/configuration-case',{data:{kind}});
  expect(response.status()).toBe(200); return response.json();
}
async function openConfigurationLink(page: Page, data: any, run=false) {
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:data.sid,view:run?'runs':'configurations',...(run?{run:data.rid}:{configuration:data.saved.configuration.configuration_revision_id})}));
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
}
async function configurationCounts(request: APIRequestContext) {return (await request.get('/fixture/configuration-counts')).json();}


async function chooseLoadedEvidence(page: Page,title: string,keyboard=false) {
  const choice=page.getByRole('button',{name:new RegExp('^Choose '+title)}).first();
  for(let pageNumber=0;pageNumber<20;pageNumber++){
    await expect(page.getByText('Loading evidence…',{exact:true})).toHaveCount(0);
    if(await choice.isVisible()){if(keyboard){await choice.focus();await page.keyboard.press('Enter');}else await choice.click();return;}
    const more=page.getByRole('dialog').last().getByRole('button',{name:'Load more evidence records',exact:true});
    await expect(more).toBeEnabled();await more.click();
  }
  throw Error('Evidence not found within bounded pages: '+title);
}

async function replaceAttachment(page: Page, region: ReturnType<Page['getByRole']>, title: string) {
  await region.getByRole('button',{name:'View evidence (1)',exact:true}).click();
  await page.getByRole('button',{name:'Remove attachment',exact:true}).click();
  await region.getByRole('button',{name:'Add evidence',exact:true}).click();
  await page.getByLabel('Find evidence',{exact:true}).fill(title);
  await chooseLoadedEvidence(page,title);
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
}

test('@ae-configuration Seed2 keeps retained owners and titles; a seed that carries criteria is refused before any save',async({page,request})=>{
  const data=await configurationCase(request), library=await writer(request);
  const newer=await library.revise(data.evidence,'New calibration E2');
  const historyPath=`/api/1/studies/${data.sid}/runs/${data.rid}`;
  const readOriginalHistory=async()=>{
    const response=await request.get(historyPath);
    expect(response.status()).toBe(200);
    const envelope=await response.json();
    expect(envelope).toHaveProperty('data');
    const run=envelope.data;
    expect(run).toMatchObject({run_id:data.rid,state:'recorded'});
    expect(run).toHaveProperty('history');
    const history=run.history;
    expect(history).toMatchObject({history_schema_version:'2',errors:[],bundle:{schema_version:'4'},results:{run_id:data.rid}});
    expect(history.configuration).toEqual(data.saved.configuration);
    expect(history.configuration.schema_version).toBe('3');
    expect(history.configuration.configuration_revision_id).toBe(data.saved.configuration.configuration_revision_id);
    expect(history.configuration.assumptions).toHaveLength(1);
    expect(history.configuration.assumptions[0].statement).toBe('Retained configuration condition');
    expect(history.model_snapshot).toEqual(data.saved.model_snapshot);
    expect(history.model_snapshot.schema_version).toBe('2');
    expect(history.model_snapshot.assumptions).toHaveLength(2);
    expect(history.evidence).toEqual([data.evidence]);
    expect(history.evidence[0]).toMatchObject({title:'Retained calibration E1',content:'Exact retained calibration observation'});
    expect(history.bundle.bundle_digest).toMatch(/^[a-f0-9]{64}$/);
    expect(history.results.bundle_digest).toBe(history.bundle.bundle_digest);
    expect(history.artifacts.length).toBeGreaterThan(0);
    return history;
  };
  const original=await readOriginalHistory();
  await openConfigurationLink(page,data,true);
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  const seed=(await (await page.request.get(`/api/1/studies/${data.sid}/runs/${data.rid}/modified-run-seed`)).json()).data;
  expect(seed.schema_version).toBe('2');expect(seed.model_snapshot).toEqual(data.saved.model_snapshot);
  await expect(page.getByRole('radio',{name:/context/})).toHaveCount(0);
  const contextSection=page.locator('#configuration .configuration-context');
  await expect(page.getByRole('heading',{name:'Inputs and provenance',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Input tools',exact:true}).click();
  await expect(page.getByLabel('Configuration notes',{exact:true})).toHaveCount(0);
  await page.getByLabel('Description',{exact:true}).fill('Independent operating question\n\nWith retained source context.');
  await page.getByRole('dialog',{name:'Input tools and model binding',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  // The editor authors no criteria: they belong to the study brief.
  await expect(page.locator('#configuration .configuration-criterion')).toContainText('Criteria are defined in the study brief and evaluated in analyses.');
  const assumptions=page.getByRole('region',{name:'Configuration assumptions',exact:true});
  await expectEvidence(page, assumptions, 'Retained calibration E1');
  await expect(page.locator('#configuration').getByText('Model assumptions: '+data.saved.model_snapshot.assumptions.length+' in the model',{exact:true})).toBeVisible();
  await expect(page.locator('#configuration').getByText('Retained model condition',{exact:true})).toBeHidden();
  const seededModel=await viewModelAssumptions(page,page.locator('#configuration'));
  await expect(seededModel.getByText('Retained model condition',{exact:true}).filter({visible:true})).toBeVisible();
  // The link opens the model view; a component's own assumptions show when it is selected.
  const owned=data.saved.model_snapshot.assumptions.find((a:any)=>a.owner.kind==='instance').owner.instance_id;
  await seededModel.getByRole('tab',{name:'Diagram',exact:true}).click();
  await seededModel.locator('[data-instance="'+owned+'"]').first().click();
  await expect(seededModel.getByText('Retained component condition',{exact:true}).filter({visible:true})).toBeVisible();
  await seededModel.getByRole('button',{name:'Done',exact:true}).click();
  await expect(assumptions).not.toContainText('New calibration E2');
  await assumptions.getByRole('button',{name:'Edit assumption: Retained configuration condition',exact:true}).click();
  await changeVersion(page);
  await page.getByRole('button',{name:/^Choose New calibration E2/}).click();
  const replacement=page.getByRole('dialog',{name:'Change evidence version',exact:true});
  await expect(replacement.getByRole('button',{name:'Apply version change',exact:true})).toBeEnabled();
  await expect(replacement.getByRole('region',{name:'Proposed evidence replacement'})).toContainText('New calibration E2');
  await expect(replacement).not.toContainText('Checking evidence version');
  await shots(page,'configuration-version-replacement');
  await page.getByRole('button',{name:'Keep current version',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Edit assumption',exact:true})).toContainText('Retained calibration E1');
  await changeVersion(page);
  await page.getByRole('button',{name:/^Choose New calibration E2/}).click();
  await page.getByRole('button',{name:'Apply version change',exact:true}).click();
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await expectEvidence(page, assumptions, 'New calibration E2', 'Challenges');
  const firstInput=page.locator('#configuration .configuration-inputs tbody tr').first();
  await replaceAttachment(page,firstInput,newer.title);
  // The retained run's configuration carries criteria; saving its seed is refused before any
  // preview or allocation, and the local edits stay in place.
  const before=await configurationCounts(request);
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'This run was configured before criteria moved to the study brief. Create a new configuration from its inputs instead.'})).toBeVisible();
  await expect(page.getByRole('dialog',{name:'Review modified run',exact:true})).toHaveCount(0);
  await expectEvidence(page, assumptions, 'New calibration E2', 'Challenges');
  expect(await configurationCounts(request)).toEqual(before);
  await shots(page,'configuration-modified-refused');
  expect(await readOriginalHistory()).toEqual(original);
  const all=(await (await page.request.get(`/api/1/studies/${data.sid}/configurations`)).json()).data;
  expect(all.some((c:any)=>c.configuration.derivation?.source_run_id===data.rid)).toBe(false);
  expect(all.find((c:any)=>c.configuration.configuration_revision_id===data.saved.configuration.configuration_revision_id)).toEqual(data.saved);
});

test('@ae-configuration configuration lists its own assumptions and links once to the model assumptions',async({page,request})=>{
  const data=await configurationCase(request);
  const id8=data.saved.model_snapshot.model_revision_id.slice(0,8), count=data.saved.model_snapshot.assumptions.length;
  const component=data.saved.model_snapshot.instances.find((i:any)=>i.instance_id===data.saved.model_snapshot.assumptions[1].owner.instance_id).name;
  expect(count).toBeGreaterThan(1);
  await openConfigurationLink(page,data);
  const saved=page.getByRole('region',{name:'Saved configuration',exact:true});
  const own=saved.getByRole('region',{name:'Configuration assumptions',exact:true});
  await expect(own.getByRole('heading',{name:'Assumptions',exact:true})).toBeVisible();
  const item=own.getByRole('article').filter({hasText:'Retained configuration condition'});
  await expect(item.getByText('Conflicting evidence',{exact:true})).toBeVisible();
  await expect(item.getByRole('heading',{name:'Retained calibration E1',exact:true})).toHaveCount(0);
  await expect(item.getByRole('button',{name:'View evidence (1)',exact:true})).toBeVisible();
  await expect(own.getByText('Configuration',{exact:true}).filter({visible:true})).toHaveCount(0);
  // One line for the model's assumptions; they are not repeated in the configuration.
  const line=saved.getByText('Model assumptions: '+count+' in the model',{exact:true});
  await expect(line).toBeVisible();
  await expect(saved.getByRole('heading',{name:'Model assumptions · read-only',exact:true})).toHaveCount(0);
  for(const statement of ['Retained model condition','Retained component condition'])await expect(saved.getByText(statement,{exact:true}).filter({visible:true})).toHaveCount(0);
  // Configuration notes stay in the record (Record details, exports) but are not shown to readers.
  expect(data.saved.configuration.context_snapshot.notes).toEqual(['Retained note with\nits own line break','Separate retained note']);
  await expect(saved.getByText('Separate retained note',{exact:true})).toHaveCount(0);
  await saved.getByRole('button',{name:'Configuration record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Configuration record',exact:true})).toContainText('Separate retained note');
  await page.keyboard.press('Escape');
  await s3Shots(page,'s3-configuration-assumptions',own);
  const dialog=await viewModelAssumptions(page,saved);
  // The model explanation shows the model's own assumptions; a selected component shows its own.
  const modelOwned=dialog.getByRole('region',{name:'Model details',exact:true}).getByRole('region',{name:'Model assumptions',exact:true});
  await expect(modelOwned).toContainText('Retained model condition');
  await expectEvidence(page, modelOwned, 'Retained calibration E1', 'Supports');
  const details=dialog.getByRole('region',{name:'Selection inspector',exact:true}).filter({visible:true});
  await dialog.getByRole('tab',{name:'Diagram',exact:true}).click();
  await dialog.locator('[data-instance="'+data.saved.model_snapshot.assumptions[1].owner.instance_id+'"]').first().click();
  await expect(details.getByRole('heading',{name:component,exact:true})).toBeVisible();
  await expect(details.getByRole('region',{name:'Component · '+component+' assumptions',exact:true})).toContainText('Retained component condition');
  await expect(details.getByRole('heading', { name: 'Method context', exact: true })).toHaveCount(0);
  await expect(details.getByRole('heading', { name: 'Why this method', exact: true })).toHaveCount(
    0,
  );
  await expect(dialog.getByRole('table',{name:'Ports'})).toHaveCount(0);
  await expect(dialog.getByRole('button',{name:'Add assumption',exact:true})).toHaveCount(0);
  await s3Shots(page,'s3-configuration-model-assumptions-dialog');
  await page.keyboard.press('Escape');
  await expect(saved.getByRole('button',{name:'View model assumptions',exact:true})).toBeFocused();
  // The run's Configuration tab shows the same line; its Evidence tab keeps the full list it used.
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:data.sid,view:'runs',run:data.rid}));
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  const retained=page.getByRole('tabpanel',{name:'Configuration',exact:true});
  await expect(retained.getByText('Model assumptions: '+count+' in the model',{exact:true})).toBeVisible();
  await expect(retained.getByText('Retained model condition',{exact:true})).toBeHidden();
  await expect(retained.getByText('Separate retained note',{exact:true})).toHaveCount(0);
  await page.getByRole('tab',{name:'Model',exact:true}).click();
  await page.getByRole('tabpanel',{name:'Model',exact:true}).getByRole('tab',{name:'Model explanation',exact:true}).click();
  await expect(page.getByRole('tabpanel',{name:'Model',exact:true}).getByRole('region',{name:'Model assumptions',exact:true}).filter({visible:true})).toContainText('Retained model condition');
});

// Retained configurations that carry criteria stay readable; new configurations are version 6
// on a Model4 revision, so neither a copy onto their earlier model format nor their Seed1 saves.
for(const kind of ['legacy','legacy-residual'])test('@ae-configuration '+kind+' ordinary copy ownership stays explicit; copy and Seed1 are refused before any save',async({page,request})=>{
  const data=await configurationCase(request,kind);await writer(request);
  const before=await configurationCounts(request);
  await openConfigurationLink(page,data);
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  if(kind==='legacy-residual'){
    await expect(page.getByRole('alert')).toContainText('older configuration has evidence without explicit attachment ownership');
    await shots(page,'configuration-legacy-refusal');
  }else{
    await page.getByLabel('Configuration name',{exact:true}).fill('Explicit legacy copy');
    await page.getByRole('button',{name:'Save configuration',exact:true}).click();
    await expect(page.getByRole('alert').filter({hasText:'This model version uses an earlier format. Save a new version of the model to configure it.'})).toBeVisible();
    await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Explicit legacy copy');
    await page.getByRole('button',{name:'Discard configuration changes',exact:true}).click();
  }
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:data.sid,view:'runs',run:data.rid}));
  await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  const seed=(await (await page.request.get(`/api/1/studies/${data.sid}/runs/${data.rid}/modified-run-seed`)).json()).data;
  expect(seed.schema_version).toBe('1');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:/earlier format|configured before criteria moved to the study brief/})).toBeVisible();
  await expect(page.getByRole('dialog',{name:'Review modified run',exact:true})).toHaveCount(0);
  expect(await configurationCounts(request)).toEqual(before);
  const all=(await (await page.request.get(`/api/1/studies/${data.sid}/configurations`)).json()).data;
  expect(all.find((c:any)=>c.configuration.configuration_revision_id===data.saved.configuration.configuration_revision_id)).toEqual(data.saved);
});

for(const unresolved of [false,true])test('@ae-configuration ordinary rebind '+(unresolved?'blocks unresolved closure without allocation':'reviews exact assumption changes'),async({page,request})=>{
  const data=await configurationCase(request,unresolved?'criteria-free-unresolved':'criteria-free'), library=await writer(request);
  if(!unresolved){
    const newer=await library.revise(data.evidence,'Rebound calibration E2');
    const draftPath=`/api/1/studies/${data.sid}/models/${data.mid}`;
    const draft=(await (await request.get(draftPath)).json()).data;
    const response=await request.post(draftPath+'/edits',{headers:library.headers,data:{schema_version:'4',command_id:crypto.randomUUID(),expected_revision:draft.draft_revision,edits:[{kind:'update_assumption',assumption_id:draft.assumptions[0].assumption_id,statement:'Revised model condition',evidence_links:[{evidence_version_id:newer.evidence_version_id,relation:'context'}]}]}});
    expect(response.status()).toBe(200);
  }
  await openConfigurationLink(page,data);
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Preserved rebind draft');
  await page.getByRole('button',{name:'Save model version',exact:true}).click();
  const review=page.getByRole('dialog',{name:'Review model binding',exact:true});
  const diff=review.getByRole('region',{name:'Model assumption changes',exact:true}).first();
  await expect(diff).toContainText('Retained calibration E1');
  await expect(diff).toContainText(unresolved?'Evidence unavailable':'Rebound calibration E2');
  if(!unresolved)await expect(diff).toContainText('Revised model condition');
  await shots(page,unresolved?'configuration-rebind-unresolved':'configuration-rebind');
  await review.getByRole('button',{name:'Keep current binding',exact:true}).click();
  const kept=await viewModelAssumptions(page,page.locator('#configuration'));
  await expect(kept.getByText('Retained model condition',{exact:true}).filter({visible:true})).toBeVisible();
  await kept.getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Save model version',exact:true}).click();
  await review.getByRole('button',{name:'Use reviewed model version',exact:true}).click();
  if(unresolved){
    const before=await configurationCounts(request);
    await expect(page.getByRole('alert')).toContainText('This evidence reference could not be resolved.');
    await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeDisabled();
    await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Preserved rebind draft');
    // A caller bypassing disabled UI still cannot allocate a configuration.
    const snapshot=(await (await request.get(`/api/1/studies/${data.sid}/models/${data.mid}/revisions`)).json()).data[0];
    const original=data.saved.configuration;
    const candidate={schema_version:'6',study_id:data.sid,model_id:data.mid,model_revision_id:snapshot.model_revision_id,name:'Unresolved attempt',inputs:original.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),numerical:original.numerical,context_source:{kind:'current_study',expected_study_revision:(await (await request.get(`/api/1/studies/${data.sid}`)).json()).data.revision},notes:[],assumptions:original.assumptions,general_context_evidence_version_ids:original.general_context_evidence_version_ids,derivation:null};
    for(const commit of [false,true]){
      const response=await request.post(`/api/1/studies/${data.sid}/configurations`+(commit?'':'/preview'),{headers:library.headers,data:commit?{command_id:crypto.randomUUID(),configuration_id:null,expected_revision:null,configuration:candidate,expected_preview_digest:'0'.repeat(64)}:candidate});
      expect(response.status()).toBe(422);expect((await response.json()).error.fields.some((f:any)=>f.code==='unresolved_evidence')).toBe(true);
    }
    expect(await configurationCounts(request)).toEqual(before);
    await shots(page,'configuration-unresolved-preserved');
  }else{
    await page.getByRole('button',{name:'Save configuration',exact:true}).click();
    await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
    const rebound=await viewModelAssumptions(page,page.getByRole('region',{name:'Saved configuration',exact:true}));
    await expect(rebound.getByText('Revised model condition',{exact:true}).filter({visible:true})).toBeVisible();
  }
  expect((await (await request.get(`/api/1/studies/${data.sid}/configurations/${data.saved.configuration.configuration_revision_id}`)).json()).data).toEqual(data.saved);
});

test('@ae-configuration outage stale context and revoked replacement preserve copied fields and clear evidence',async({page,request})=>{
  const data=await configurationCase(request,'criteria-free'),library=await writer(request);
  await library.revise(data.evidence,'Revocation target E2');
  await openConfigurationLink(page,data);
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill('Preserved modified fields');
  await page.getByRole('button',{name:'Input tools',exact:true}).click();
  await page.getByLabel('Description',{exact:true}).fill('Local context survives refresh');
  await page.getByRole('dialog',{name:'Input tools and model binding',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  await page.getByLabel('linear · x value',{exact:true}).fill('7');
  const before=await configurationCounts(request);
  await request.post('/fixture/configuration-control',{data:{offline:true}});
  const failedPreview=page.waitForResponse(response=>response.url().endsWith(`/studies/${data.sid}/configurations/preview`)&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const unavailable=await failedPreview;
  expect(unavailable.status()).toBe(503);
  expect((await unavailable.json()).error.code).toBe('backend_unavailable');
  await expect(page.getByRole('alert')).toHaveText('Modeling is unavailable. Your edits are preserved. Retry the read when it is available.');
  await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeEnabled();
  await page.getByRole('alert').scrollIntoViewIfNeeded();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Preserved modified fields');
  await expect(page.getByLabel('linear · x value',{exact:true})).toHaveValue('7');
  expect(await configurationCounts(request)).toEqual(before);
  await shots(page,'configuration-outage-preserved');
  await request.post('/fixture/configuration-control',{data:{offline:false}});
  await request.post('/fixture/configuration-control',{data:{stale_study:true}});
  // A stale study revision refuses the save without allocation and keeps every local field.
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Your edits are preserved');
  await page.getByRole('alert').scrollIntoViewIfNeeded();
  await shots(page,'configuration-stale-preserved');
  expect(await configurationCounts(request)).toEqual(before);
  await page.getByRole('button',{name:'Input tools',exact:true}).click();
  await expect(page.getByLabel('Description',{exact:true})).toHaveValue('Local context survives refresh');
  await page.getByRole('dialog',{name:'Input tools and model binding',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Preserved modified fields');
  await expect(page.getByLabel('linear · x value',{exact:true})).toHaveValue('7');
  const assumptions=page.getByRole('region',{name:'Configuration assumptions',exact:true});
  await assumptions.getByRole('button',{name:'Edit assumption: Retained configuration condition',exact:true}).click();
  await changeVersion(page);
  await page.getByRole('button',{name:/^Choose Revocation target E2/}).click();
  await request.post('/fixture/membership',{data:{enabled:false}});
  try{
    await page.getByRole('button',{name:'Apply version change',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Change evidence version',exact:true});
    await expect(dialog).toContainText('Evidence unavailable');
    await expect(dialog).not.toContainText('Revocation target E2');
    await page.getByRole('button',{name:'Keep current version',exact:true}).click();
    await expect(page.getByLabel('Statement',{exact:true})).toHaveValue('Retained configuration condition');
    await expect(page.getByRole('dialog',{name:'Edit assumption',exact:true})).not.toContainText('Retained calibration E1');
    await expect(page.locator('#configuration')).not.toContainText('Retained calibration E1');
    expect(await configurationCounts(request)).toEqual(before);
    await shots(page,'configuration-revoked-preserved');
  }finally{await request.post('/fixture/membership',{data:{enabled:true}});}
});

test('@ae-configuration same model owner switch rejects late evidence and resets local editor',async({page,request})=>{
  const data=await configurationCase(request,'criteria-free'),library=await writer(request),source=data.saved.configuration;
  // A second configuration 6 of the same model version, written through the public API.
  const candidate={schema_version:'6',study_id:data.sid,model_id:source.model_id,model_revision_id:source.model_revision_id,name:'Second same-model owner',
    inputs:source.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),numerical:source.numerical,
    context_source:{kind:'current_study',expected_study_revision:(await (await request.get(`/api/1/studies/${data.sid}`)).json()).data.revision},
    notes:[],derivation:null,assumptions:[{assumption_id:crypto.randomUUID(),statement:'Independent second owner',evidence_links:[]}],general_context_evidence_version_ids:[]};
  const preview=await request.post(`/api/1/studies/${data.sid}/configurations/preview`,{headers:library.headers,data:candidate});expect(preview.status()).toBe(200);
  const saved=await request.post(`/api/1/studies/${data.sid}/configurations`,{headers:library.headers,data:{command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration:candidate,expected_preview_digest:(await preview.json()).data.candidate_digest}});expect(saved.status()).toBe(201);
  const second=(await saved.json()).data.configuration.configuration_revision_id;
  await page.goto('/ui/?configuration-harness');
  await page.getByRole('button',{name:'Fixture sign in',exact:true}).click();
  await expect(page.getByLabel('Configuration name',{exact:true})).toBeVisible();
  await page.evaluate(id=>(window as any).aeConfiguration.copy(id),data.saved.configuration.configuration_revision_id);
  await page.getByRole('button',{name:'Edit assumption: Retained configuration condition',exact:true}).click();
  let release!:()=>void;const held=new Promise<void>(resolve=>release=resolve);let requested!:()=>void;const observed=new Promise<void>(resolve=>requested=resolve);
  await page.route('**/evidence-families/*/versions?*',async route=>{const response=await route.fetch();requested();await held;await route.fulfill({response});});
  await page.getByRole('dialog',{name:'Edit assumption',exact:true}).getByRole('button',{name:'View evidence (1)',exact:true}).click();await page.getByRole('button',{name:'Change version',exact:true}).click();await observed;
  // The fixture invokes the production handle to exercise an imperative same-model
  // owner transition while the old owner's request remains queued.
  await page.evaluate(id=>(window as any).aeConfiguration.copy(id),second);
  release();
  await expect(page.getByRole('dialog',{name:'Change evidence version',exact:true})).toHaveCount(0);
  await expect(page.getByRole('dialog',{name:'Edit assumption',exact:true})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Configuration assumptions',exact:true})).not.toContainText('Retained configuration condition');
  await page.getByRole('button',{name:'Edit assumption: Independent second owner',exact:true}).click();
  await page.getByLabel('Statement',{exact:true}).fill('Unsaved owner field');
  await page.evaluate(()=>(window as any).aeConfiguration.discard());
  await expect(page.getByRole('dialog',{name:'Edit assumption',exact:true})).toHaveCount(0);
  await expect(page.getByText('Unsaved owner field',{exact:true})).toHaveCount(0);
  await shots(page,'configuration-owner-reset');
});

test('@ae-integration run evidence groups exact retained uses during model outage and preserves file downloads',async({page,request})=>{
  const data=await configurationCase(request,'grouped'), library=await writer(request);
  await library.revise(data.evidence,'Current head must never replace E1');
  await request.post('/fixture/configuration-control',{data:{offline:true}});
  try {
    await openConfigurationLink(page,data,true);
    await expect(page.getByRole('tab',{name:'Evidence',exact:true})).toBeVisible();
    const response=await page.request.get(`/api/1/studies/${data.sid}/runs/${data.rid}`);
    expect(response.status()).toBe(200);const before=(await response.json()).data.history;
    expect(before).toMatchObject({history_schema_version:'2',bundle:{schema_version:'4'},configuration:data.saved.configuration,model_snapshot:data.saved.model_snapshot,evidence:[data.evidence]});
    let liveReads=0;page.on('request',r=>{if(/evidence-families|assumption-evidence/.test(r.url()))liveReads++;});
    const heading=page.locator('.run-heading');
    for(const name of ['Results','Model','Configuration']) {
      await page.getByRole('tab',{name,exact:true}).click();
      const recordAction=heading.getByRole('button',{name:'Record details',exact:true});
      await expect(recordAction).toBeVisible();await recordAction.click();
      const runRecord=page.getByRole('dialog',{name:'Run record',exact:true});
      await expect(runRecord).toContainText(data.rid);
      await expect(runRecord).toContainText(before.configuration.digest);
      await page.keyboard.press('Escape');await expect(recordAction).toBeFocused();
      await shots(page,'run-coherence-'+name.toLowerCase());
    }
    await page.getByRole('tab',{name:'Configuration',exact:true}).click();
    const retained=page.getByRole('tabpanel',{name:'Configuration',exact:true});
    const context=retained.getByRole('region',{name:'Configuration context',exact:true});
    await expect(context).toContainText(before.configuration.context_snapshot.description);
    expect(await context.evaluate(el=>!!(el.compareDocumentPosition(document.querySelector('#run-panel-2 .configuration-inputs')!) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true);
    await expect(retained.locator('.hf-criterion-record')).toHaveCount(before.configuration.criteria.length);
    expect(await retained.locator('.hf-criterion-record').first().evaluate(el=>parseFloat(getComputedStyle(el).paddingLeft))).toBeGreaterThan(0);
    await retained.getByRole('button',{name:'Configuration record details',exact:true}).click();
    await expect(page.getByRole('dialog',{name:'Configuration record',exact:true})).toContainText(before.configuration.configuration_revision_id);
    await page.keyboard.press('Escape');
    await expect(retained.getByRole('button',{name:'Configuration record details',exact:true})).toBeFocused();
    await retained.locator('.configuration-criterion').scrollIntoViewIfNeeded();await shots(page,'run-coherence-criteria');
    await page.getByRole('tab',{name:'Evidence',exact:true}).click();
    const evidence=page.getByRole('tabpanel',{name:'Evidence',exact:true});
    await expect(evidence.getByRole('button',{name:'Record details',exact:true})).toHaveCount(0);
    // Model and component assumptions form one owner group (each item names Whole model or
    // its component); configuration assumptions are their own group. Uses follow the index.
    for(const [group,word] of [['Model assumptions','Supports'],['Model assumptions','Context'],['Configuration assumptions','Challenges'],['Input provenance',''],['Criterion evidence',''],['General context','']]) {
      const region=evidence.getByRole('region',{name:group,exact:true});
      await expect(region.getByRole('heading',{name:data.evidence.title,exact:true}).first()).toBeVisible();
      if(word)await expect(region.getByText(word,{exact:true}).first()).toBeVisible();
    }
    const components=evidence.getByRole('region',{name:'Model assumptions',exact:true});
    await expect(components).toContainText('No evidence linked');await expect(components).toContainText('Second retained component condition');
    const owner=data.saved.model_snapshot.instances.find((i:any)=>i.instance_id===data.saved.model_snapshot.assumptions[1].owner.instance_id).name;await expect(components.getByText('Component · '+owner,{exact:true})).toHaveCount(data.saved.model_snapshot.assumptions.filter((a:any)=>a.owner.kind==='instance'&&a.owner.instance_id===data.saved.model_snapshot.assumptions[1].owner.instance_id).length);
    await expect(components.getByText('Whole model',{exact:true})).toHaveCount(data.saved.model_snapshot.assumptions.filter((a:any)=>a.owner.kind==='model').length);
    await expect(evidence.getByRole('region',{name:'Criterion evidence',exact:true})).toContainText('equal to 500 dimensionless');await expect(evidence.getByRole('region',{name:'Criterion evidence',exact:true})).toContainText('Absolute tolerance: 0.01 · Relative tolerance: 0.001');
    await expect(evidence).not.toContainText('Current head must never replace E1');
    await evidence.getByRole('region',{name:'Model assumptions',exact:true}).scrollIntoViewIfNeeded();await shots(page,'run-evidence-model');
    await evidence.getByRole('region',{name:'Configuration assumptions',exact:true}).scrollIntoViewIfNeeded();await shots(page,'run-evidence-configuration');
    await evidence.getByRole('region',{name:'General context',exact:true}).scrollIntoViewIfNeeded();await shots(page,'run-evidence-context');
    await evidence.getByRole('region',{name:'General context',exact:true}).getByRole('button',{name:'View evidence (1)',exact:true}).click();
    const detail=page.getByRole('region', { name: 'Evidence details', exact: true });
    await expect(detail).toContainText(data.evidence.evidence_version_id.slice(0,8));
    await expect(detail.getByRole('button',{name:'Versions',exact:true})).toHaveCount(0);
    await detail.getByRole('button',{name:'Evidence record details',exact:true}).click();
    const downloaded=page.waitForEvent('download');await page.getByRole('dialog',{name:'Evidence record',exact:true}).getByRole('button',{name:'Download evidence record',exact:true}).click();
    expect(JSON.parse(await readFile((await (await downloaded).path())!,'utf8'))).toEqual(data.evidence);
    await shots(page,'run-evidence-detail');await page.keyboard.press('Escape');
    const files=evidence.getByRole('region',{name:'Run files',exact:true});
    await files.getByRole('combobox',{name:'File group',exact:true}).selectOption('');
    const firstNames=await files.locator('tbody th').allTextContents();
    if(before.artifacts.length>20){await files.getByRole('button',{name:'Next files',exact:true}).click();expect(await files.locator('tbody th').allTextContents()).not.toEqual(firstNames);await files.getByRole('button',{name:'Previous files',exact:true}).click();}
    await files.getByLabel('Find a file',{exact:true}).fill('configuration.json');
    const artifact=before.artifacts.find((a:any)=>a.name==='configuration.json');expect(artifact).toBeDefined();
    const row=files.getByRole('row').filter({has:page.getByRole('rowheader',{name:'configuration.json',exact:true})});
    await row.getByRole('button',{name:'Preview',exact:true}).click();await expect(page.getByLabel('Read-only run file')).toContainText('Retained AE configuration');
    await page.getByRole('button',{name:'Close preview',exact:true}).click();
    const fileDownload=page.waitForEvent('download');await row.getByRole('button',{name:'Download',exact:true}).click();
    const bytes=await readFile((await (await fileDownload).path())!);expect(bytes.length).toBe(artifact.size);expect(createHash('sha256').update(bytes).digest('hex')).toBe(artifact.sha256);
    await shots(page,'run-evidence-files');expect(liveReads).toBe(0);
    const after=await page.request.get(`/api/1/studies/${data.sid}/runs/${data.rid}`);expect(after.status()).toBe(200);expect((await after.json()).data.history).toEqual(before);
  } finally {await request.post('/fixture/configuration-control',{data:{offline:false}});}
});


test('@ae-integration actual Package2 export import rejects corrupt files and requires explicit citation repair before configuration',async({page,request})=>{
  const data = await configurationCase(request, 'unresolved'),
    library = await writer(request);
  const props = await openModel(page);
  await page.getByRole('button', { name: 'Save model version', exact: true }).click();
  const draftPath = `/api/1/studies/${data.sid}/models/${data.mid}`;
  await expect
    .poll(async () => (await (await request.get(draftPath + '/revisions')).json()).data.length)
    .toBeGreaterThan(1);
  const selected = (await (await request.get(draftPath + '/revisions')).json()).data[0];
  await page.getByLabel('Model version', { exact: true }).selectOption(selected.model_revision_id);
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Export model', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download portable model record', exact: true }).click();
  const raw = await readFile((await (await download).path())!, 'utf8'),
    pkg = JSON.parse(raw);
  expect(pkg.schema_version).toBe('2');
  const original = pkg.revisions.find((r: any) => r.model_revision_id === pkg.model_revision_id);
  expect(original.assumptions[0].evidence_links).toHaveLength(1);
  expect(original.source_files.length).toBeGreaterThan(0);
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: 'Home', exact: true })
    .click();
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('Study name').fill('Isolated Package2 destination');
  await page.getByLabel('Study question', { exact: true })
    .fill('What must this engineering study establish?');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await page
    .getByRole('navigation', { name: 'Workspace sections' })
    .getByRole('button', { name: 'Models', exact: true })
    .click();
  const sid = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  await page.getByRole('button', { name: 'Import model', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Import model', exact: true });
  let posts = 0;
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/model-imports')) posts++;
  });
  const canonical = (v: any): string =>
    v === null || typeof v !== 'object'
      ? JSON.stringify(v)
      : Array.isArray(v)
        ? '[' + v.map(canonical).join(',') + ']'
        : '{' +
          Object.keys(v)
            .sort()
            .map((k) => JSON.stringify(k) + ':' + canonical(v[k]))
            .join(',') +
          '}';
  const sign = (v: any) => {
    delete v.digest;
    v.digest = createHash('sha256').update(canonical(v)).digest('hex');
  };
  const rejected = [];
  for (const kind of [
    'pairing',
    'revision-version',
    'package-digest',
    'revision-digest',
    'source',
    'size',
  ]) {
    const bad = structuredClone(pkg),
      root = bad.revisions.find((r: any) => r.model_revision_id === bad.model_revision_id);
    if (kind === 'pairing') bad.schema_version = '1';
    if (kind === 'revision-version') root.schema_version = '99';
    if (kind === 'revision-digest') root.digest = '0'.repeat(64);
    if (kind === 'source') {
      root.source_files[0].bytes = Buffer.from('corrupt source').toString('base64');
      sign(root);
    }
    sign(bad);
    if (kind === 'package-digest') bad.digest = '0'.repeat(64);
    const buffer =
      kind === 'size' ? Buffer.alloc(2 * 1024 * 1024, 32) : Buffer.from(JSON.stringify(bad));
    await dialog
      .getByLabel('Portable model record file')
      .setInputFiles({ name: kind + '.json', mimeType: 'application/json', buffer });
    if (kind !== 'size')
      await dialog.getByRole('button', { name: 'Preview model import', exact: true }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Import model', exact: true })).toHaveCount(0);
    rejected.push(kind);
    expect(posts).toBe(0);
  }
  await shots(page, 'package-rejected');
  await dialog
    .getByLabel('Portable model record file')
    .setInputFiles({
      name: 'exact-package.json',
      mimeType: 'application/json',
      buffer: Buffer.from(raw),
    });
  await dialog.getByRole('button', { name: 'Preview model import', exact: true }).click();
  await expect(dialog.getByRole('region', { name: 'Model import preview' })).toContainText(
    'Ready to import',
  );
  await shots(page, 'package-import-preview');
  const importing = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/model-imports'),
  );
  await dialog.getByRole('button', { name: 'Import model', exact: true }).click();
  const importedResponse = await importing;
  expect(importedResponse.status()).toBe(200);
  const imported = (await importedResponse.json()).data;
  expect(imported.assumptions).toEqual(original.assumptions);
  expect(imported.source_files).toEqual(original.source_files);
  expect(posts).toBe(1);
  const importedPath = `/api/1/studies/${sid}/models/${data.mid}`;
  await expect(page.getByRole('button', { name: 'Model actions', exact: true })).toBeVisible();
  const assumptions = await modelDetails(page);
  await expect(assumptions).toContainText('Evidence unavailable');
  await expect(assumptions).toContainText(
    original.assumptions[0].evidence_links[0].evidence_version_id,
  );
  await shots(page, 'package-unresolved-assumption');
  await page.getByLabel('Model version', { exact: true }).selectOption(selected.model_revision_id);
  await page.getByRole('button', { name: 'Create configuration', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText(
    'This evidence reference could not be resolved.',
  );
  await expect(
    page.getByRole('button', { name: 'Save configuration', exact: true }),
  ).toBeDisabled();
  await shots(page, 'package-blocked-configuration');
  const before = await configurationCounts(request),
    saved = data.saved.configuration;
  const candidate = {
    schema_version: '3',
    study_id: sid,
    model_id: data.mid,
    model_revision_id: selected.model_revision_id,
    name: 'Imported unresolved',
    inputs: saved.inputs.map((i: any) => ({
      kind: 'literal',
      target: i.target,
      value: i.value,
      units: i.units,
      provenance: { ...i.provenance, evidence_version_ids: [] },
    })),
    criteria: [],
    numerical: saved.numerical,
    context_source: {
      kind: 'current_study',
      expected_study_revision: (await (await request.get('/api/1/studies/' + sid)).json()).data
        .revision,
    },
    notes: [],
    assumptions: [],
    general_context_evidence_version_ids: [],
    derivation: null,
  };
  for (const commit of [false, true]) {
    const response = await request.post(
      `/api/1/studies/${sid}/configurations` + (commit ? '' : '/preview'),
      {
        headers: library.headers,
        data: commit
          ? {
              command_id: crypto.randomUUID(),
              configuration_id: null,
              expected_revision: null,
              configuration: candidate,
              expected_preview_digest: '0'.repeat(64),
            }
          : candidate,
      },
    );
    expect(response.status()).toBe(422);
    expect(
      (await response.json()).error.fields.some((f: any) => f.code === 'unresolved_evidence'),
    ).toBe(true);
  }
  expect(await configurationCounts(request)).toEqual(before);
  // Leave the unsaved configuration and repair the imported owner explicitly.
  await page
    .getByRole('navigation', { name: 'Workspace sections' })
    .getByRole('button', { name: 'Models', exact: true })
    .click();
  const dirty = page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
  if (await dirty.isVisible())
    await dirty.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await modelDetails(page);
  await assumptions
    .getByRole('button', {
      name: 'Edit assumption: ' + original.assumptions[0].statement,
      exact: true,
    })
    .click();
  await page
    .getByRole('dialog', { name: 'Edit assumption', exact: true })
    .getByRole('button', { name: 'Remove attachment', exact: true })
    .click();
  await page.getByRole('button', { name: 'Apply assumption', exact: true }).click();
  await assumptions.getByRole('button', { name: 'Save model draft', exact: true }).click();
  await page.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Preview changes', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Save model version', exact: true }).click();
  const draft = (await (await request.get(importedPath)).json()).data;
  expect(draft.assumptions[0].evidence_links).toEqual([]);
  expect(draft.source_files).toEqual(original.source_files);
  await expect
    .poll(
      async () =>
        (await (await request.get(importedPath + '/revisions')).json()).data[0].model_revision_id,
    )
    .not.toBe(selected.model_revision_id);
  let repaired = (await (await request.get(importedPath + '/revisions')).json()).data[0];
  await page.getByLabel('Model version', { exact: true }).selectOption(repaired.model_revision_id);
  await page.getByRole('button', { name: 'Create configuration', exact: true }).click();
  await page.getByRole('button', { name: 'Save model version', exact: true }).click();
  const binding = page.getByRole('dialog', { name: 'Review model binding', exact: true });
  await expect(
    binding.getByRole('region', { name: 'Model assumption changes', exact: true }).first(),
  ).toContainText('Evidence unavailable');
  await binding.getByRole('button', { name: 'Use reviewed model version', exact: true }).click();
  repaired = (await (await request.get(importedPath + '/revisions')).json()).data[0];
  await page.getByLabel('Configuration name', { exact: true }).fill('Explicitly repaired import');
  for (const input of await page.locator('input[data-input-key]').all()) await input.fill('2');
  for (const provenance of await page.getByRole('textbox', { name: / provenance$/ }).all())
    await provenance.fill('Explicit input after repair');
  await page.getByRole('button', { name: 'Save configuration', exact: true }).click();
  await expect(page.getByText('Read-only', { exact: true })).toBeVisible();
  await shots(page, 'package-repaired-saved');
  const configs = await request.get(`/api/1/studies/${sid}/configurations`);
  expect(configs.status()).toBe(200);
  const rows = (await configs.json()).data;
  expect(rows).toHaveLength(1);
  expect(rows[0].model_snapshot.model_revision_id).toBe(repaired.model_revision_id);
  expect(rows[0].model_snapshot.assumptions[0].evidence_links).toEqual([]);
  const retained = await request.get(importedPath + '/revisions/' + selected.model_revision_id);
  expect(retained.status()).toBe(200);
  expect((await retained.json()).data).toEqual(original);
  await writeFile(
    join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!, 'evidence/package-roundtrip.json'),
    JSON.stringify(
      { exported: pkg, imported, rejected, repaired: rows[0], sourceUnchanged: true, posts },
      null,
      2,
    ),
  );
});

test('@ae-integration genuine browser 200 percent assumption and evidence keyboard recovery',async({baseURL,request})=>{
  test.setTimeout(120000);
  const data=await configurationCase(request),root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const extension=join(root,'artifacts/ae-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Assumptions evidence zoom',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/ae-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');let tabId:number|undefined;
  const bounds:any[]=[];
  try {
    const page=context.pages()[0]??await context.newPage();await openConfigurationLink(page,data);
    await page.getByRole('button',{name:'Create new version',exact:true}).click();
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    tabId=await worker.evaluate(async(url)=>{const tabs=await (globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tabId);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId)).toBe(2);
    expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){
      await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
      const geometry=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));
      bounds.push({name,geometry});expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width+1);
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
      await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));
    }
    async function activate(button:ReturnType<Page['getByRole']>){
      await button.focus();await button.scrollIntoViewIfNeeded();await expect(button).toBeFocused();
      const box=await button.evaluate(element=>{const r=element.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {text:element.textContent,x:r.x,y:r.y,width:r.width,height:r.height,hit:element===hit||element.contains(hit),outline:getComputedStyle(element).outlineStyle};});
      bounds.push(box);expect(box.hit).toBe(true);expect(box.x).toBeGreaterThanOrEqual(0);expect(box.width+box.x).toBeLessThanOrEqual(721);
      await page.keyboard.press('Enter');
    }
    const assumptions=page.getByRole('region',{name:'Configuration assumptions',exact:true});
    await activate(assumptions.getByRole('button',{name:'Add assumption',exact:true}));
    const editor=page.getByRole('dialog',{name:'Edit assumption',exact:true}),statement=editor.getByLabel('Statement',{exact:true});
    await expect(statement).toBeFocused();await statement.fill('Long operating assumption with exact retained owner and evidence');
    await page.keyboard.press('Enter');await page.keyboard.type('Second line remains a scientific statement.');
    await page.keyboard.press('Escape');await expect(editor).toContainText('Discard unsaved assumption changes?');
    await activate(editor.getByRole('button',{name:'Keep editing',exact:true}));await expect(statement).toBeFocused();await expect(statement).toHaveValue(/\nSecond line/);
    await capture('ae-assumption-200-light');
    async function tabCycle(surface:ReturnType<Page['getByRole']>,name:string,count:number){
      for(const key of ['Tab','Shift+Tab'])for(let index=0;index<count;index++){
        await page.keyboard.press(key);
        const focus=await surface.evaluate(dialog=>{const active=document.activeElement as HTMLElement,r=active.getBoundingClientRect();return {inside:dialog.contains(active)&&active.closest('dialog:modal')===dialog,tag:active.tagName,label:active.getAttribute('aria-label')||active.textContent?.slice(0,200),html:active.outerHTML.slice(0,600),documentFocused:document.hasFocus(),dialogs:Array.from(document.querySelectorAll('dialog[open]')).map(d=>({label:d.getAttribute('aria-label'),modal:d.matches(':modal'),containsActive:d.contains(active)})),outline:getComputedStyle(active).outlineStyle,x:r.x,y:r.y,width:r.width,height:r.height};});
        bounds.push({surface:name,key,tab:index,...focus});
        await writeFile(join(root,'evidence/ae-tab-diagnostics.json'),JSON.stringify(bounds,null,2));
        expect(focus.inside).toBe(true);expect(focus.documentFocused).toBe(true);expect(focus.outline).not.toBe('none');
      }
    }
    await tabCycle(editor,'assumption editor',8);
    await activate(editor.getByRole('button',{name:'Add evidence',exact:true}));
    const picker=page.getByRole('dialog',{name:'Add evidence to Configuration assumption',exact:true});
    await page.getByLabel('Find evidence',{exact:true}).fill(data.evidence.title);
    await chooseLoadedEvidence(page,data.evidence.title,true);
    await page.getByLabel('Relationship',{exact:true}).selectOption('context');
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.emulateMedia({reducedMotion:'reduce'});
    await page.getByRole('button',{name:'Attach evidence',exact:true}).focus();await page.getByRole('button',{name:'Attach evidence',exact:true}).scrollIntoViewIfNeeded();
    await capture('ae-picker-200-dark');
    await activate(page.getByRole('button',{name:'Attach evidence',exact:true}));await expect(picker).toHaveCount(0);
    await expect(editor.getByRole('button',{name:'Add evidence',exact:true})).toBeFocused();
    await activate(editor.getByRole('button',{name:'View evidence (1)',exact:true}));
    const detail=page.getByRole('region', { name: 'Evidence details', exact: true });await expect(detail).toContainText(data.evidence.content);
    await tabCycle(detail,'nested evidence detail',8);
    await capture('ae-detail-200-dark');await page.keyboard.press('Escape');
    await writeFile(join(root,'evidence/ae-nested-escape.json'),JSON.stringify(await page.evaluate(()=>({active:document.activeElement?.outerHTML,dialogs:Array.from(document.querySelectorAll('dialog')).filter(d=>d.open).map(d=>({label:d.getAttribute('aria-label'),labelledby:d.getAttribute('aria-labelledby'),text:d.textContent?.slice(0,600)}))})),null,2));
    await expect(editor.getByRole('button',{name:'View evidence (1)',exact:true})).toBeFocused();
    await expect(editor.getByText('Discard unsaved assumption changes?',{exact:true})).toHaveCount(0);
    const library=await writer(request),newer=await library.revise(data.evidence,'Calibration selected at native 200 percent');
    await activate(editor.getByRole('button',{name:'Change version',exact:true}));
    const replacement=page.getByRole('dialog',{name:'Change evidence version',exact:true});
    await expect(replacement.getByRole('button',{name:'Apply version change',exact:true})).toBeDisabled();
    await tabCycle(replacement,'version selector without proposal',8);
    await activate(replacement.getByRole('button',{name:new RegExp('^Choose '+newer.title)}));
    const proposal=replacement.getByRole('region',{name:'Proposed evidence replacement',exact:true});
    await expect(proposal).toContainText('From evidence version '+data.evidence.evidence_version_id+' to evidence version '+newer.evidence_version_id+'.');
    await expect(replacement.getByRole('button',{name:'Apply version change',exact:true})).toBeEnabled();
    await tabCycle(replacement,'version selector with proposal',12);
    await capture('ae-version-200-dark');
    await activate(proposal.getByRole('button',{name:'View evidence (1)',exact:true}));
    const proposedDetail=page.getByRole('region', { name: 'Evidence details', exact: true });await expect(proposedDetail).toContainText(newer.content);
    await tabCycle(proposedDetail,'version nested detail',8);
    await capture('ae-version-detail-200-dark');await page.keyboard.press('Escape');
    await expect(proposedDetail).not.toBeVisible();await expect(replacement).toBeVisible();
    await expect(proposal.getByRole('button',{name:'View evidence (1)',exact:true})).toBeFocused();
    await expect(replacement.getByRole('button',{name:new RegExp('^Choose '+newer.title)})).toHaveAttribute('aria-pressed','true');
    await expect(proposal).toContainText('From evidence version '+data.evidence.evidence_version_id+' to evidence version '+newer.evidence_version_id+'.');
    await capture('ae-version-preserved-200-dark');
    await activate(replacement.getByRole('button',{name:'Apply version change',exact:true}));
    await expect(statement).toBeFocused();await expect(editor).toContainText(newer.title);
    await activate(editor.getByRole('button',{name:'Apply assumption',exact:true}));
    await expect(assumptions.getByRole('button',{name:'Add assumption',exact:true})).toBeFocused();
    await activate(page.getByRole('button',{name:'Save configuration',exact:true}));await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
    await assumptions.scrollIntoViewIfNeeded();await capture('ae-configuration-200-dark');
    await page.evaluate(()=>document.documentElement.dataset.theme='light');await capture('ae-configuration-200-light');
    await writeFile(join(root,'evidence/ae-zoom.json'),JSON.stringify({factor:await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId),viewport:page.viewportSize(),bounds},null,2));
  } finally {if(tabId!==undefined)await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tabId);await context.close();}
});

for(const saved of [true,false])test('@ae-integration uncertain configuration '+(saved?'returns original receipt':'retries identical original payload')+' without duplicate allocation',async({page,request})=>{
  const data=await configurationCase(request),library=await writer(request),before=await configurationCounts(request);
  await openConfigurationLink(page,data);
  await page.getByRole('button',{name:'Create new version',exact:true}).click();
  await page.getByLabel('Configuration name',{exact:true}).fill(saved?'Recovered acknowledged configuration':'Retried original configuration');
  const path=`/api/1/studies/${data.sid}/configurations`,bodies:any[]=[];
  await page.route('**'+path,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    bodies.push(route.request().postDataJSON());
    if(bodies.length===1){if(saved)expect((await route.fetch()).status()).toBe(201);return route.abort('failed');}
    await route.continue();
  });
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByRole('button',{name:'Check original configuration command',exact:true})).toBeVisible();
  await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue(saved?'Recovered acknowledged configuration':'Retried original configuration');
  await page.getByRole('button',{name:'Check original configuration command',exact:true}).scrollIntoViewIfNeeded();
  await shots(page,saved?'configuration-uncertain-saved':'configuration-uncertain-absent');
  await page.getByRole('button',{name:'Check original configuration command',exact:true}).click();
  if(!saved){
    await expect(page.getByRole('button',{name:'Retry original configuration command',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Retry original configuration command',exact:true}).click();
  }
  await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
  expect(bodies).toHaveLength(saved?1:2);if(!saved)expect(bodies[1]).toEqual(bodies[0]);
  const after=await configurationCounts(request);expect(after.configurations).toBe(before.configurations+1);expect(after.configuration_families).toBe(before.configuration_families+1);expect(after.outbox).toBe(before.outbox);
  const altered=structuredClone(bodies[0]);altered.configuration.name='Changed replay must fail';
  const denied=await request.post(path,{headers:library.headers,data:altered});expect(denied.status()).toBe(409);expect((await denied.json()).error.code).toBe('command_payload_conflict');
  const replay=await request.post(path,{headers:library.headers,data:bodies[0]});expect(replay.status()).toBe(201);
  expect((await replay.json()).data.configuration.name).toBe(bodies[0].configuration.name);expect(await configurationCounts(request)).toEqual(after);
  await shots(page,saved?'configuration-receipt-recovered':'configuration-identical-retry');
});

test('@ae-integration stale model preserves its staged assumption and original revision',async({page,request})=>{
  const data=await configurationCase(request),library=await writer(request);await openModel(page);
  const dialog=await modelDetails(page);
  await dialog.getByRole('button',{name:'Add assumption',exact:true}).click();await page.getByLabel('Statement',{exact:true}).fill('My preserved staged model assumption');
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  const path=`/api/1/studies/${data.sid}/models/${data.mid}`,draft=(await (await request.get(path)).json()).data;
  const concurrent=await request.post(path+'/edits',{headers:library.headers,data:{schema_version:'2',command_id:crypto.randomUUID(),expected_revision:draft.draft_revision,edits:[{kind:'add_assumption',temp_key:'concurrent',owner:{kind:'model'},statement:'Concurrent condition',evidence_links:[]}]}});
  expect(concurrent.status()).toBe(200);const current=(await concurrent.json()).data;
  await dialog.getByRole('button',{name:'Save model draft',exact:true}).click();
  const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});await expect(preview.getByRole('alert')).toContainText('changed');await preview.getByRole('button',{name:'Review current revision',exact:true}).click();await expect(preview.getByRole('region',{name:'Current revision differences'})).toContainText('Concurrent condition');await shots(page,'model-stale-preview');await preview.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(dialog).toContainText('My preserved staged model assumption');await shots(page,'model-stale-preserved');
  expect((await (await request.get(path)).json()).data).toEqual(current);
  const retained=await request.get(path+'/revisions/'+data.saved.model_snapshot.model_revision_id);expect(retained.status()).toBe(200);expect((await retained.json()).data).toEqual(data.saved.model_snapshot);
});

test('@ae-integration uncertain model assumption keeps modal draft and recovers the original receipt',async({page,request})=>{
  const data=await configurationCase(request),library=await writer(request);await openModel(page);
  const path=`/api/1/studies/${data.sid}/models/${data.mid}`;
  const editor=await modelDetails(page);
  await editor.getByRole('button',{name:'Add assumption',exact:true}).click();await page.getByLabel('Statement',{exact:true}).fill('Uncertain command retains this exact assumption');
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  let body:any,writes=0;
  await page.route('**'+path+'/edits',async route=>{writes++;body=route.request().postDataJSON();expect((await route.fetch()).status()).toBe(200);await route.abort('failed');});
  await editor.getByRole('button',{name:'Save model draft',exact:true}).click();
  const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});
  await expect(preview).toContainText('Uncertain command retains this exact assumption');
  await preview.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(preview).toContainText('Check the original command in command recovery.');
  await expect(preview.getByRole('button',{name:'Apply changes',exact:true})).toBeDisabled();await shots(page,'model-uncertain-preview');
  await preview.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(editor).toContainText('Uncertain command retains this exact assumption');
  await expect(editor.getByRole('button',{name:'Save model draft',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Check original command',exact:true}).click();await expect(page.getByText(/Original command: committed/)).toBeVisible();expect(writes).toBe(1);
  const receipt=await request.get(`/api/1/studies/${data.sid}/commands/${body.command_id}?category=model`);expect(receipt.status()).toBe(200);expect((await receipt.json()).data.state).toBe('committed');
  const current=await request.get(path);expect(current.status()).toBe(200);
  const draft=(await current.json()).data;expect(draft.assumptions.filter((a:any)=>a.statement==='Uncertain command retains this exact assumption')).toHaveLength(1);
  const changed=structuredClone(body);changed.edits[0].statement='Changed replay must fail';
  const conflict=await request.post(path+'/edits',{headers:library.headers,data:changed});expect(conflict.status()).toBe(409);expect((await conflict.json()).error.code).toBe('command_payload_conflict');
  await modelDetails(page);
  await expect(editor).toContainText('Uncertain command retains this exact assumption');await shots(page,'model-recovered-staged');
  expect((await (await request.get(path)).json()).data).toEqual(draft);
});

test('@ae-configuration genuine 200 percent context, criteria in the study brief and retained run actions',async({baseURL,request})=>{
  test.setTimeout(120000);
  const data=await configurationCase(request,'criteria-free'),root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!;
  const extension=join(root,'artifacts/coherence-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Configuration coherence zoom',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/coherence-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');let tabId:number|undefined;
  const bounds:any[]=[];
  try {
    const page=context.pages()[0]??await context.newPage();await openConfigurationLink(page,data);
    await page.getByRole('button',{name:'Create new version',exact:true}).click();
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    tabId=await worker.evaluate(async(url)=>{const tabs=await (globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tabId);
    expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId)).toBe(2);
    expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){
      await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
      const geometry=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));
      bounds.push({name,geometry});expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width+1);
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
      await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));
    }
    async function activate(button:ReturnType<Page['getByRole']>){
      await button.focus();await button.scrollIntoViewIfNeeded();await expect(button).toBeFocused();
      const box=await button.evaluate(element=>{const r=element.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {text:element.textContent,x:r.x,y:r.y,width:r.width,height:r.height,hit:element===hit||element.contains(hit),outline:getComputedStyle(element).outlineStyle};});
      bounds.push(box);expect(box.hit).toBe(true);expect(box.x).toBeGreaterThanOrEqual(0);expect(box.width+box.x).toBeLessThanOrEqual(721);
      await button.press('Enter');
    }
    await page.bringToFront();
    const contextSection=page.locator('#configuration .configuration-context');
    await activate(page.getByRole('button',{name:'Input tools',exact:true}));
    await page.getByLabel('Description',{exact:true}).fill('Temporary context to discard');
    await page.getByRole('dialog',{name:'Input tools and model binding',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
    await expect(page.getByRole('button',{name:'Input tools',exact:true})).toBeFocused();
    await page.getByRole('button',{name:'Discard configuration changes',exact:true}).click();
    await activate(page.getByRole('button',{name:'Input tools',exact:true}));
    await expect(page.getByLabel('Description',{exact:true})).toHaveValue(data.saved.configuration.context_snapshot.description);
    await page.getByRole('dialog',{name:'Input tools and model binding',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
    await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue(data.saved.configuration.name);
    await activate(page.getByRole('button',{name:'Input tools',exact:true}));
    await page.getByLabel('Description',{exact:true}).fill('Independent description at native zoom');
    await capture('coherence-context-200-light');
    await page.getByRole('dialog',{name:'Input tools and model binding',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
    await expect(page.getByRole('button',{name:'Input tools',exact:true})).toBeFocused();
    // Criteria belong to the study brief; the configuration offers no criterion editor.
    const criteria=page.locator('#configuration .configuration-criterion');
    await expect(criteria).toContainText(studyCriteria);await expect(criteria.getByRole('button')).toHaveCount(0);
    for(const theme of ['light','dark']){
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      await criteria.scrollIntoViewIfNeeded();await capture('coherence-criteria-200-'+theme);
    }
    const inputEvidence=page.locator('#configuration .configuration-inputs tbody tr').first().getByRole('button',{name:'View evidence (1)',exact:true});
    await activate(inputEvidence);
    await expect(page.getByRole('region', { name: 'Evidence details', exact: true })).toContainText('Exact retained calibration observation');
    await page.keyboard.press('Escape');
    await page.getByLabel('Configuration name',{exact:true}).fill('Copied at native zoom');
    await activate(page.getByRole('button',{name:'Save configuration',exact:true}));
    await expect(page.getByText('Read-only',{exact:true})).toBeVisible();
    const saved=page.getByRole('region',{name:'Saved configuration',exact:true});

    await expect(saved.locator('.configuration-criterion')).toContainText(studyCriteria);
    await expect(saved.getByRole('article',{name:'Criterion 1',exact:true})).toHaveCount(0);

    await activate(saved.getByRole('button',{name:'Configuration record details',exact:true}));
    await expect(page.getByRole('dialog',{name:'Configuration record',exact:true})).toContainText('Independent description at native zoom');
    await page.keyboard.press('Escape');await saved.getByRole('heading').first().scrollIntoViewIfNeeded();
    await capture('coherence-saved-200-dark');
    await page.keyboard.press('Escape');
    await request.post('/fixture/configuration-control',{data:{offline:true}});
    await page.goto('/ui/#'+new URLSearchParams({v:'1',study:data.sid,view:'runs',run:data.rid}));
    for(const name of ['Results','Model','Configuration']) {
      await activate(page.getByRole('tab',{name,exact:true}));
      const action=page.locator('.run-heading').getByRole('button',{name:'Run record details',exact:true});
      await activate(action);await expect(page.getByRole('dialog',{name:'Run record',exact:true})).toContainText(data.rid);
      await page.keyboard.press('Escape');await expect(action).toBeFocused();
      for(const theme of ['light','dark']) {
        await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
        await action.scrollIntoViewIfNeeded();await capture('coherence-run-'+name.toLowerCase()+'-200-'+theme);
      }
    }
    await activate(page.getByRole('tab',{name:'Configuration',exact:true}));
    const retained=page.getByRole('tabpanel',{name:'Configuration',exact:true});
    // The retained configuration 6 carries no criteria of its own.
    const compact=retained.locator('.configuration-criterion');
    await expect(compact).toContainText(studyCriteria);
    await expect(retained.getByRole('article',{name:'Criterion 1',exact:true})).toHaveCount(0);
    const evidenceAction=retained.locator('.configuration-inputs tbody tr').first().getByRole('button',{name:'View evidence (1)',exact:true});
    await activate(evidenceAction);await expect(page.getByRole('region', { name: 'Evidence details', exact: true })).toContainText(data.evidence.content);
    await page.keyboard.press('Escape');await expect(evidenceAction).toBeFocused();
    for(const theme of ['light','dark']) {
      await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
      await compact.scrollIntoViewIfNeeded();await capture('coherence-run-criteria-200-'+theme);
    }
    await activate(retained.getByRole('button',{name:'Configuration record details',exact:true}));
    await expect(page.getByRole('dialog',{name:'Configuration record',exact:true})).toContainText(data.saved.configuration.configuration_revision_id);
    await page.keyboard.press('Escape');
    await request.post('/fixture/configuration-control',{data:{offline:false}});
    await writeFile(join(root,'evidence/coherence-zoom.json'),JSON.stringify({factor:await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tabId),viewport:page.viewportSize(),bounds},null,2));
  } finally {if(tabId!==undefined)await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,1),tabId);await context.close();}
});


test('@ae-model projected preview revision never replaces the original apply revision',async({page})=>{
  const props=await openModel(page),path=`/api/1/studies/${props.sid}/models/${props.mid}`;
  const before=(await(await page.request.get(path)).json()).data;
  const projected=crypto.randomUUID();let applied:any;
  // Backend/native HTTP regressions establish this projection behavior; this
  // boundary test proves the browser keeps its original compare-and-swap token.
  await page.route('**/models/*/preview',async route=>{
    const response=await route.fetch();expect(response.status()).toBe(200);
    const body=await response.json();body.data.draft_revision=projected;
    await route.fulfill({response,json:body});
  });
  await page.route('**/models/*/edits',async route=>{applied=route.request().postDataJSON();await route.continue();});
  await editComponent(page);
  await page.getByRole('button',{name:'Add assumption',exact:true}).click();
  await page.getByLabel('Statement',{exact:true}).fill('Preview projection must not change the saved draft.');
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  await (await editComponent(page)).getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toBeVisible();
  expect((await(await page.request.get(path)).json()).data).toEqual(before);
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Preview changes'})).toHaveCount(0);
  expect(applied.expected_revision).toBe(before.draft_revision);expect(applied.expected_revision).not.toBe(projected);
  const after=(await(await page.request.get(path)).json()).data;
  expect(after.assumptions.some((a:any)=>a.statement==='Preview projection must not change the saved draft.')).toBe(true);
});

// Guard characterization. The new-evidence editor is a modal dialog, so leaving
// uses hash navigation (the Workspace hashchange guard), as approach.spec does.
const leaveByHash = (page: Page) => page.evaluate(() => { location.hash = ''; });
test('@ae-evidence workspace guard keeps a refused evidence draft and saves a valid one before leaving', async ({page}) => {
  const props = await openEvidence(page, 'Guarded report');
  const dirty = page.getByRole('dialog', {name: 'Unsaved changes', exact: true}), note = page.getByRole('textbox',{name:'Evidence note',exact:true});
  await note.fill('');
  const exact = page.url(); await leaveByHash(page); await expect(dirty).toBeVisible();
  await expect(dirty.getByRole('button', {name: 'Keep editing', exact: true})).toBeFocused();
  await dirty.getByRole('button', {name: 'Save changes', exact: true}).click();
  await expect(dirty).toBeHidden(); await expect(page).toHaveURL(exact); await expect(note).toBeFocused();
  await expect(page.getByText('Enter an explanation or note.', {exact: true})).toBeVisible();
  await expect(page.getByLabel('Title', {exact: true})).toHaveValue('Guarded report');
  await note.fill('Saved through the workspace guard.');
  await leaveByHash(page); await dirty.getByRole('button', {name: 'Save changes', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Studies', exact: true})).toBeVisible();
  const rows = await (await page.request.get(`/api/1/studies/${props.sid}/evidence`)).json();
  expect(rows.data.filter((r: {title?: string}) => r.title === 'Guarded report').map((r: {content: string}) => r.content)).toEqual(['Saved through the workspace guard.']);
});

test('@ae-evidence workspace guard Discard drops the evidence draft and leaves', async ({page}) => {
  const props = await openEvidence(page, 'Discarded report');
  const dirty = page.getByRole('dialog', {name: 'Unsaved changes', exact: true});
  await leaveByHash(page); await dirty.getByRole('button', {name: 'Keep editing', exact: true}).click();
  await expect(dirty).toBeHidden(); await expect(page.getByLabel('Title', {exact: true})).toHaveValue('Discarded report');
  await leaveByHash(page); await dirty.getByRole('button', {name: 'Discard changes', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Studies', exact: true})).toBeVisible();
  const rows = await (await page.request.get(`/api/1/studies/${props.sid}/evidence`)).json();
  expect(rows.data.filter((r: {title?: string}) => r.title === 'Discarded report')).toEqual([]);
});

// Evidence index, and the run artifact, modified-run seed and export reads on the session seam.
const deniedText='Access to this resource is no longer available.', unverifiedText='Study access could not be verified. Retry the read.';
function watchWrites(page: Page){const writes:string[]=[];page.on('request',r=>{const path=new URL(r.url()).pathname;if(r.method()!=='GET'&&path.startsWith('/api/1/')&&path!=='/api/1/session')writes.push(r.method()+' '+path);});return writes;}
const showView=(page: Page, sid: string, view: string, extra: Record<string,string> = {})=>page.evaluate(([sid,view,extra])=>{location.hash=new URLSearchParams({v:'1',study:sid,view,...extra}).toString();},[sid,view,extra] as const);
async function openEvidencePage(page: Page, sid: string) {
  await page.goto('/ui/#'+new URLSearchParams({v:'1',study:sid,view:'evidence'}));
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Evidence',exact:true,level:2})).toBeVisible();
}
const refused=(code:string,message:string)=>({status:code==='forbidden'?403:code==='backend_unavailable'?503:code==='resource_not_found'?404:500,json:{error:{code,message,fields:[],outcome:'unchanged'}}});

test('@ae-evidence referenced library preserves exact membership with partial reads and confirmed denial', async ({page,request}) => {
  const api = await writer(request), original = await api.create('Cited original source');
  await api.revise(original, 'Uncited successor source');
  await openEvidencePage(page,api.sid);
  const library=page.getByRole('region',{name:'Evidence library',exact:true});
  await expect(page.getByRole('button',{name:'Refresh evidence',exact:true})).toBeEnabled();
  await expect(library.getByRole('heading',{name:'Cited original source',exact:true})).toHaveCount(0);
  await pinLibraryEvidence(page,request,'Cited original source');
  await expect(library.getByRole('heading',{name:'Uncited successor source',exact:true})).toHaveCount(0);
  await expect(library.getByRole('button',{name:/View evidence/})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Assumptions by owner',exact:true})).toHaveCount(0);
  await library.locator('article').filter({has:page.getByRole('heading',{name:'Cited original source',exact:true})}).getByRole('button',{name:'Evidence record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Evidence record',exact:true})).toContainText(original.evidence_version_id);
  await page.keyboard.press('Escape');
  await page.route(`**/api/1/studies/${api.sid}/models`,route=>route.fulfill(refused('backend_unavailable','Declared modeling outage')));
  await page.getByRole('button',{name:'Refresh evidence',exact:true}).click();
  await expect(library.getByRole('alert')).toContainText('may be incomplete');
  await expect(library.getByRole('heading',{name:'Cited original source',exact:true})).toBeVisible();
  await page.unroute(`**/api/1/studies/${api.sid}/models`);
  await library.getByRole('button',{name:'Retry loading evidence',exact:true}).click();
  await expect(library.getByRole('alert')).toHaveCount(0);
  try {
    expect((await request.post('/fixture/membership',{data:{enabled:false}})).status()).toBe(200);
    await expect(page.getByRole('button',{name:'Refresh evidence',exact:true})).toBeEnabled();
    await page.getByRole('button',{name:'Refresh evidence',exact:true}).click();
    await expect(library.getByRole('heading',{name:'Cited original source',exact:true})).toHaveCount(0);
    await expect(library.getByRole('alert')).toContainText(deniedText);
  } finally { expect((await request.post('/fixture/membership',{data:{enabled:true}})).status()).toBe(200); }
});

test('@ae-evidence library reads each missing frozen owner once instead of every sampled run', async ({page,request}) => {
  const api = await writer(request), source = await api.create('Frozen owner source');
  const rows = Array.from({length:200},(_,n)=>({run_id:'sample-'+n,configuration_revision_id:'retained'}));
  rows.push({run_id:'missing-1',configuration_revision_id:'missing'},{run_id:'missing-2',configuration_revision_id:'missing'});
  const reads:string[]=[];
  await page.route(`**/api/1/studies/${api.sid}/configurations`,route=>route.fulfill({json:{schema_version:'1',data:[{configuration:{configuration_revision_id:'retained',general_context_evidence_version_ids:[source.evidence_version_id]}}]}}));
  await page.route(`**/api/1/studies/${api.sid}/runs`,route=>route.fulfill({json:{schema_version:'1',data:rows}}));
  await page.route(`**/api/1/studies/${api.sid}/runs/*`,route=>{
    reads.push(new URL(route.request().url()).pathname.split('/').pop()!);
    return route.fulfill({json:{schema_version:'1',data:{history:{configuration:{evidence_version_ids:[source.evidence_version_id]}}}}});
  });
  await openEvidencePage(page,api.sid);
  const library=page.getByRole('region',{name:'Evidence library',exact:true});
  await expect(library.getByRole('heading',{name:'Frozen owner source',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Refresh evidence',exact:true})).toBeEnabled();
  expect(reads).toEqual(['missing-1']);
});

test('@ae-configuration run artifact and modified-run seed reads clear the run on a confirmed denial and retry a transient probe',async({page,request})=>{
  const data=await configurationCase(request,'grouped'),sid=data.sid,writes=watchWrites(page);
  const heading=page.locator('.run-heading').getByRole('heading',{name:data.saved.configuration.name,exact:true});
  const preview=async()=>{
    await page.getByRole('tab',{name:'Results',exact:true}).click();
    const disclosure=page.locator('details.run-files');
    if (!(await disclosure.getAttribute('open')!==null)) await disclosure.locator('summary').click();
    const files=page.getByRole('region',{name:'Run files',exact:true});
    await files.getByRole('combobox',{name:'File group',exact:true}).selectOption('');await files.getByLabel('Find a file',{exact:true}).fill('configuration.json');
    await files.getByRole('row').filter({has:page.getByRole('rowheader',{name:'configuration.json',exact:true})}).getByRole('button',{name:'Preview',exact:true}).click();
  };
  // Modified-run seed: a transient study probe keeps the run and offers an explicit retry.
  let releaseSeed!:()=>void;const seedHeld=new Promise<void>(resolve=>{releaseSeed=resolve;});
  await page.route('**/modified-run-seed',async route=>{await seedHeld;await route.fulfill(refused('resource_not_found','Not found'));},{times:1});
  await openConfigurationLink(page,data,true);await expect(heading).toBeVisible();
  let probes=0;await page.route(`**/api/1/studies/${sid}`,async route=>{if(route.request().method()==='GET'){probes++;await route.abort();}else await route.fallback();},{times:1});
  releaseSeed();
  await expect(page.getByText(unverifiedText,{exact:true})).toBeVisible();expect(probes).toBe(1);
  await expect(heading).toBeVisible();await expect(page.getByRole('button',{name:'Create modified run',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Check modified run again',exact:true}).click();
  await expect(page.getByRole('button',{name:'Create modified run',exact:true})).toBeEnabled();await expect(page.getByText(unverifiedText,{exact:true})).toHaveCount(0);
  // Artifact: a transient study probe keeps the record; the same read succeeds when retried.
  await page.route(`**/api/1/studies/${sid}/runs/${data.rid}/artifacts/*`,route=>route.fulfill(refused('resource_not_found','Not found')),{times:1});
  await page.route(`**/api/1/studies/${sid}`,async route=>{if(route.request().method()==='GET'){probes++;await route.abort();}else await route.fallback();},{times:1});
  await preview();
  await expect(page.getByText(unverifiedText,{exact:true})).toBeVisible();expect(probes).toBe(2);await expect(heading).toBeVisible();
  await page.getByRole('row').filter({has:page.getByRole('rowheader',{name:'configuration.json',exact:true})}).getByRole('button',{name:'Preview',exact:true}).click();
  await expect(page.getByLabel('Read-only run file')).toContainText('Retained AE configuration');
  // Artifact: revoked membership is confirmed by the study probe and clears the run in place.
  try {
    expect((await request.post('/fixture/membership',{data:{enabled:false}})).status()).toBe(200);
    await page.getByRole('button',{name:'Close preview',exact:true}).click();await preview();
    await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();
    await expect(heading).toHaveCount(0);await expect(page.getByRole('tab',{name:'Evidence',exact:true})).toHaveCount(0);
    await expect(page.getByLabel('Read-only run file')).toHaveCount(0);await expect(page.getByText('Retained configuration condition')).toHaveCount(0);
    await expect(page.getByRole('button',{name:'Create modified run',exact:true})).toHaveCount(0);
    await s3Shots(page,'s2l1-run-artifact-denied');
  } finally {expect((await request.post('/fixture/membership',{data:{enabled:true}})).status()).toBe(200);}
  // Modified-run seed: a confirmed denial clears the run record.
  await page.route('**/modified-run-seed',route=>route.fulfill(refused('forbidden','Refused')),{times:1});
  await page.goto('about:blank');await openConfigurationLink(page,data,true);
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();
  await expect(heading).toHaveCount(0);await expect(page.getByRole('tab',{name:'Evidence',exact:true})).toHaveCount(0);
  expect(writes).toEqual([]);
});

test('@ae-configuration export status read clears on a confirmed denial',async({page,request})=>{
  const data=await configurationCase(request,'grouped'),sid=data.sid,writes=watchWrites(page),requestId=crypto.randomUUID();
  const queued={schema_version:'1',request_id:requestId,kind:'preview',state:'queued',selected_run_ids:[data.rid],preview:null,error:null,download:null};
  // Transport-level doubles: the preview command is answered as queued; the status read is refused.
  await page.route(`**/api/1/studies/${sid}/computational-record-previews`,route=>route.fulfill({status:202,json:{schema_version:'1',data:queued}}));
  let statusReads=0;await page.route(`**/api/1/studies/${sid}/computational-records/${requestId}`,route=>{statusReads++;return route.fulfill(refused('forbidden','Refused'));});
  await openConfigurationLink(page,data,true);
  await page.getByRole('button',{name:'Export computational record',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Export computational record',exact:true});
  await dialog.getByRole('button',{name:'Check contents',exact:true}).click();
  await expect.poll(()=>statusReads).toBe(1);
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();
  await expect(dialog).toHaveCount(0);await expect(page.locator('.run-heading').getByRole('heading',{name:data.saved.configuration.name,exact:true})).toHaveCount(0);
  await page.waitForTimeout(2500);expect(statusReads).toBe(1);
  expect(writes).toEqual([`POST /api/1/studies/${sid}/computational-record-previews`]);
});

test('@ae-evidence source excerpt and explanation remain separate through save, revise and exact history', async ({page,request}) => {
  const props = await openEvidence(page, 'Thermal reference source');
  await page.getByRole('checkbox', {name: 'Include source excerpt', exact: true}).check();
  await page.getByRole('textbox',{name:'Source excerpt',exact:true}).fill('The reference temperature is 293.15 K.');
  await page.getByLabel('Source reference', {exact: true}).fill('Thermal reference report');
  await page.getByRole('textbox',{name:'Explanation',exact:true}).fill('This supports the reference condition, not the operating temperature.');
  await page.getByRole('button', {name: 'Create evidence', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('page or location');
  await page.getByLabel('Page or location', {exact: true}).fill('p. 7, Table 2');
  await page.getByRole('button', {name: 'Create evidence', exact: true}).click();
  const card = page.locator('article').filter({has: page.getByRole('heading', {name: 'Thermal reference source', exact: true})});
  await pinLibraryEvidence(page, request, 'Thermal reference source');
  await expect(card.getByRole('button',{name:/View evidence/})).toHaveCount(0);
  await expect(card.getByRole('region',{name:'Source',exact:true})).toContainText('Thermal reference report');
  await page.getByRole('button',{name:'Overview',exact:true}).click();
  const brief = page.getByRole('region',{name:'Study brief',exact:true});
  await brief.getByLabel('Study brief version',{exact:true}).selectOption('draft');
  const claim = brief.locator('article').filter({hasText:'Claim supported by Thermal reference source'});
  const trigger = claim.getByRole('button',{name:'View evidence (1)',exact:true});
  await expect(trigger).toHaveClass(/hf-open-link/); await trigger.click();
  const panel = page.getByRole('region', {name: 'Evidence details', exact: true});
  await expect(panel.getByRole('region', {name: 'Source excerpt', exact: true})).toContainText('p. 7, Table 2');
  await expect(panel.locator('blockquote')).toHaveText('The reference temperature is 293.15 K.');
  await expect(panel.getByRole('region', {name: 'Explanation', exact: true})).toContainText('This supports the reference condition');
  await expect(panel.locator('blockquote')).not.toContainText('operating temperature');
  await expect(panel.getByRole('button', {name: 'Download evidence record', exact: true})).not.toBeVisible();
  for (const width of [1440, 720]) {
    await page.setViewportSize({width, height: 1000});
    await expect.poll(async () => {
      const box = await panel.boundingBox();
      return box?.height ?? 0;
    }).toBeGreaterThan(900);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 720) {
      const canvas = page.locator('.hf-workspace__canvas');
      expect(await canvas.evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true);
      const canvasBox = await canvas.boundingBox(), panelBox = await panel.boundingBox();
      expect(panelBox!.y).toBeGreaterThanOrEqual(canvasBox!.y + canvasBox!.height);
    }
    await expect(panel.getByRole('button', {name: 'Close Evidence', exact: true})).toBeVisible();
  }
  await page.setViewportSize({width: 1440, height: 1000});
  const launcher = page.getByRole('button', {name: 'Open assistant', exact: true});
  await launcher.click();
  const assistant = page.getByRole('region', {name: 'Assistant', exact: true});
  await expect(launcher).toHaveCount(0);
  await expect(panel).toBeVisible();
  const dock = (await assistant.boundingBox())!, details = (await panel.boundingBox())!;
  expect(details.x + details.width).toBeLessThanOrEqual(dock.x);
  expect(dock.height).toBeGreaterThan(900);
  const separator = page.getByRole('separator', {name: 'Resize assistant', exact: true});
  await separator.press('ArrowLeft');
  expect((await assistant.boundingBox())!.width).toBeGreaterThan(dock.width);
  await separator.press('End');
  expect((await page.locator('.hf-workspace__canvas').boundingBox())!.width).toBeGreaterThanOrEqual(300);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await separator.dblclick();
  expect((await assistant.boundingBox())!.width).toBeCloseTo(dock.width, 0);
  await assistant.getByRole('button', {name: 'Expand to full width', exact: true}).click();
  await expect(panel).not.toBeVisible();
  await expect(page.locator('.hf-workspace__canvas')).not.toBeVisible();
  await assistant.getByRole('button', {name: 'Exit full screen', exact: true}).click();
  await expect(panel.locator('blockquote')).toHaveText('The reference temperature is 293.15 K.');
  await assistant.getByRole('button', {name: 'Hide assistant', exact: true}).click();
  await expect(panel).toBeVisible();
  await expect(launcher).toBeFocused();
  await page.screenshot({path: `${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/structured-evidence.png`});
  await panel.getByRole('button', {name: 'Close Evidence', exact: true}).click();
  await showView(page,props.sid,'evidence');
  await card.getByRole('button', {name: 'Edit', exact: true}).click();
  await expect(page.getByRole('textbox',{name:'Source excerpt',exact:true})).toHaveValue('The reference temperature is 293.15 K.');
  await expect(page.getByLabel('Page or location', {exact: true})).toHaveValue('p. 7, Table 2');
  await page.getByRole('textbox',{name:'Explanation',exact:true}).fill('A revised interpretation.');
  await page.getByRole('button', {name: 'Save new version', exact: true}).click();
  await expect(page.getByRole('dialog', {name: 'Edit evidence', exact: true})).not.toBeVisible();
  const records = (await (await page.request.get(`/api/1/studies/${props.sid}/evidence?view=versions`)).json()).data.filter((r:any) => r.title === 'Thermal reference source');
  expect(records).toHaveLength(2);
  const original = JSON.parse(records[1].content.split('\n').slice(1).join('\n'));
  expect(original.explanation).toBe('This supports the reference condition, not the operating temperature.');
  expect(JSON.parse(records[0].content.split('\n').slice(1).join('\n')).excerpt).toBe(original.excerpt);
});

test('@ae-model explanation drafts save once per exact model version', async ({
  page,
  request,
}) => {
  const library = await writer(request),
    note = await library.create('Explanation basis report');
  const props = await openModel(page);
  const base = `/api/1/studies/${props.sid}/models/${props.mid}`;
  const read = async (path: string) => (await (await page.request.get(base + path)).json()).data;
  await page.getByRole('tab', { name: 'Model explanation', exact: true }).click();
  const explanation = page.getByRole('region', {
    name: 'Application model explanation',
    exact: true,
  });
  await expect(explanation).toContainText('No model explanation yet.');
  await expect(page.getByRole('heading',{name:'Model explanation',exact:true})).toHaveCount(1);
  await expect(page.getByRole('heading',{name:'Explanation',exact:true})).toHaveCount(0);
  await expect(explanation).toContainText('New draft');
  await expect(explanation.getByRole('combobox')).toHaveCount(0);
  await expect(explanation.getByRole('region',{name:'Explanation evidence',exact:true})).toHaveCount(0);
  await expect(
    explanation.getByRole('button', { name: 'Save explanation version', exact: true }),
  ).toHaveCount(0);
  await explanation.getByRole('button', { name: 'Edit explanation', exact: true }).click();
  await explanation
    .getByLabel('Description', { exact: true })
    .fill('Output y of one repeated scaling.');
  await explanation
    .getByLabel('Basis and reasoning', { exact: true })
    .fill('Identity relation of the source report.');
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  const unsaved = page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
  await expect(unsaved).toBeVisible();
  await unsaved.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await shots(page, 'model-explanation-keep-editing');
  await expect(explanation.getByLabel('Description', { exact: true })).toHaveValue(
    'Output y of one repeated scaling.',
  );
  await explanation
    .getByLabel('Component explanation · Component A', { exact: true })
    .fill('Copies x to y.');
  await explanation.getByRole('button', { name: 'Add evidence', exact: true }).click();
  await page.getByLabel('Find evidence', { exact: true }).fill('Explanation basis report');
  await page.getByRole('button', { name: /^Choose Explanation basis report/ }).click();
  await page.getByLabel('Relationship', { exact: true }).selectOption('supports');
  await page.getByRole('button', { name: 'Attach evidence', exact: true }).click();
  await expect(explanation).toContainText('Explanation basis report');
  await shots(page, 'model-explanation-editor');
  await expect(explanation).toContainText('Unsaved changes');
  await expect(explanation).toContainText('numerical checks belong in Analysis details');
  await explanation.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    explanation.getByRole('button', { name: 'Edit explanation', exact: true }),
  ).toBeFocused();
  const draft = (await read('/explanation')).draft;
  expect(draft.content).toMatchObject({
    represents: 'Output y of one repeated scaling.',
    calculation_logic: '',
    components: [
      {
        kind: 'instance',
        instance_id: props.instances[1].instance_id,
        explanation: 'Copies x to y.',
      },
    ],
    evidence_links: [{ evidence_version_id: note.evidence_version_id, relation: 'supports' }],
  });
  // A blank component explanation is left out, never saved as an empty claim.
  expect(draft.content.components).toHaveLength(1);
  await expect(
    explanation.getByRole('region', { name: 'Calculation logic', exact: true }),
  ).toHaveCount(0);
  // Saving pins the one chosen saved model version, once.
  const latest = props.revision.model_revision_id;
  await explanation.getByRole('button', {name:'Edit explanation',exact:true}).click();
  await explanation.getByLabel('Basis and reasoning',{exact:true}).fill('Identity relation of the source report. Domain restricted to finite real scalars.');
  await explanation.getByRole('button', {name:'Save for model version',exact:true}).click();
  const publish=page.getByRole('dialog',{name:'Save explanation version',exact:true});
  await expect(publish.getByRole('button',{name:'Save explanation version',exact:true})).toBeDisabled();
  await publish.getByLabel('Model version to explain',{exact:true}).selectOption(latest);
  // If the draft is saved but publication fails, retry uses the acknowledged draft token.
  await page.route('**/models/*/explanation/versions', route => route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'backend_unavailable',message:'Temporary publication outage',fields:[]}})}), {times:1});
  await publish.getByRole('button',{name:'Save explanation version',exact:true}).click();
  await expect(publish.getByRole('alert')).toContainText('not saved');
  const acknowledged=(await read('/explanation')).draft;
  expect(acknowledged.content.basis).toContain('Domain restricted to finite real scalars.');
  expect((await read(`/revisions/${latest}/explanation`)).explanation).toBeNull();
  await publish.getByRole('button',{name:'Save explanation version',exact:true}).click();
  await expect(publish).toBeHidden();
  await expect(explanation).toContainText('Saved draft');
  await expect(explanation.getByRole('combobox')).toHaveCount(0);
  const saved = (await read(`/revisions/${latest}/explanation`)).explanation;
  expect(saved.model_revision_id).toBe(latest);
  expect(saved.content).toEqual(acknowledged.content);
  await library.revise(note,'Later report must not substitute the attached source');
  // A later draft never changes the saved explanation.
  await explanation.getByRole('button', { name: 'Edit explanation', exact: true }).click();
  await explanation
    .getByLabel('Description', { exact: true })
    .fill('Changed after saving.');
  await explanation.getByRole('button',{name:'Save for model version',exact:true}).click();
  await publish.getByLabel('Model version to explain',{exact:true}).selectOption(latest);
  await expect(publish).toContainText('already has an explanation');
  await expect(publish.getByRole('button',{name:'Save explanation version',exact:true})).toBeDisabled();
  await publish.getByRole('button',{name:'Done',exact:true}).click();
  await explanation.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    explanation.getByRole('region', { name: 'Description', exact: true }),
  ).toContainText('Changed after saving.');
  expect((await read(`/revisions/${latest}/explanation`)).explanation).toEqual(saved);
  // The saved model version shows its own explanation, read-only.
  await page.getByLabel('Model version', { exact: true }).selectOption(latest);
  await page.getByRole('tab', { name: 'Model explanation', exact: true }).click();
  await expect(explanation).toContainText('Read-only');
  await expect(
    explanation.getByRole('region', { name: 'Description', exact: true }),
  ).toContainText('Output y of one repeated scaling.');
  await expect(
    explanation.getByRole('region', { name: 'Component explanations', exact: true }),
  ).toContainText('Component A: Copies x to y.');
  await expect(
    explanation.getByRole('region', { name: 'Calculation logic', exact: true }),
  ).toHaveCount(0);
  await expect(
    explanation.getByRole('button', { name: 'Edit explanation', exact: true }),
  ).toHaveCount(0);
  await expectEvidence(page, explanation, 'Explanation basis report', 'Supports');
  await expect(page.getByText('Later report must not substitute the attached source',{exact:true})).toHaveCount(0);
  await explanation.getByRole('button',{name:'Model explanation record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Model explanation record',exact:true})).toContainText(saved.explanation_version_id);
  await expect(page.getByRole('dialog',{name:'Model explanation record',exact:true})).toContainText(latest);
  await page.getByRole('dialog',{name:'Model explanation record',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  for (const width of [1440,720,390]) {
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await shots(page, 'model-explanation-saved-'+width);
  }
});

test('@ae-model editing layouts keep controls and completion actions inside narrow light and dark dialogs', async ({page}) => {
  await openModel(page);
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    for (const width of [1440, 720, 390]) {
      await page.setViewportSize({width, height: 700});
      await page.getByRole('button', {name:'＋ Component', exact:true}).click();
      const add = page.getByRole('dialog', {name:'Add component', exact:true});
      await expect(add.locator('.dialog-footer').getByRole('button')).toHaveText(['Done', 'Add component']);
      const gaps = await add.evaluate(dialog => {
        const body = dialog.querySelector('.dialog-body')!;
        const field = body.querySelector('label')!;
        return { top:field.getBoundingClientRect().top-body.getBoundingClientRect().top,
          padding:parseFloat(getComputedStyle(body).paddingTop), overflow:dialog.scrollWidth-dialog.clientWidth };
      });
      expect(gaps.top).toBeCloseTo(gaps.padding, 0);
      expect(gaps.overflow).toBeLessThanOrEqual(1);
      await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/component-editor-${theme}-${width}.png`});
      await add.getByRole('button', {name:'Done', exact:true}).click();
      await page.getByRole('tab', {name:'Quantities', exact:true}).click();
      await page.getByRole('button', {name:'Edit quantity', exact:true}).first().click();
      const quantity = page.getByRole('dialog', {name:'Edit quantity', exact:true});
      const layout = await quantity.evaluate(dialog => {
        const grid = dialog.querySelector('.hf-quantity-fields')!;
        const labels = grid.querySelectorAll(':scope > label');
        const first = labels[0].getBoundingClientRect(), second = labels[1].getBoundingClientRect();
        return {columns:getComputedStyle(grid).gridTemplateColumns.split(' ').length,
          right:second.right, gridRight:grid.getBoundingClientRect().right,
          firstBottom:first.bottom, secondTop:second.top,
          overflow:dialog.scrollWidth-dialog.clientWidth};
      });
      expect(layout.columns).toBe(width === 390 ? 1 : 2);
      expect(layout.right).toBeCloseTo(layout.gridRight, 0);
      expect(layout.overflow).toBeLessThanOrEqual(1);
      if (width === 390) expect(layout.secondTop-layout.firstBottom).toBeGreaterThanOrEqual(8);
      await quantity.getByRole('button', {name:'Done', exact:true}).scrollIntoViewIfNeeded();
      const buttons = quantity.locator('.dialog-footer').getByRole('button');
      await expect(buttons).toHaveText(['Done', 'Preview quantity changes']);
      const bounds = await buttons.evaluateAll(elements => elements.map(element => {
        const box=element.getBoundingClientRect(); return {left:box.left, right:box.right, top:box.top, bottom:box.bottom};
      }));
      expect(bounds[0].right).toBeLessThanOrEqual(bounds[1].left);
      expect(Math.abs(bounds[0].bottom-bounds[1].bottom)).toBeLessThanOrEqual(1);
      await page.screenshot({path:`${process.env.HYPRN_MVP_TEST_SCOPE_ROOT}/evidence/quantity-editor-${theme}-${width}.png`});
      await quantity.getByRole('button', {name:'Done', exact:true}).click();
    }
  }
});

test('@ae-model description assumptions and limits share one editor and saved versions retain their exact content', async ({page,request}) => {
  const props = await openModel(page);
  const base = `/api/1/studies/${props.sid}/models/${props.mid}`;
  const editor = await editComponent(page);
  await expect(editor.locator('.dialog-body > fieldset > section')).toHaveCount(3);
  await editor.getByLabel('Component description', {exact:true}).fill('Converts input x into output y.');
  await editor.getByLabel('Component limits', {exact:true}).fill('Finite real scalars only.');
  await editor.getByRole('button', {name:'Add assumption', exact:true}).click();
  await page.getByLabel('Statement', {exact:true}).fill('The coefficient remains constant.');
  await page.getByRole('button', {name:'Apply assumption', exact:true}).click();
  const footer = editor.locator(':scope > .dialog-footer');
  await expect(footer.getByRole('button')).toHaveText(['Cancel', 'Save draft']);
  for (const theme of ['light','dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    await page.setViewportSize({width:390, height:760});
    expect(await editor.evaluate(node => node.scrollWidth - node.clientWidth)).toBeLessThanOrEqual(1);
    await shots(page, `component-documentation-${theme}`);
  }
  await footer.getByRole('button', {name:'Save draft', exact:true}).click();
  await page.getByRole('dialog',{name:'Preview changes',exact:true}).getByRole('button',{name:'Apply changes',exact:true}).click();
  await expect(editor).toBeHidden();
  const state = (await (await page.request.get(base+'/explanation')).json()).data;
  expect(state.draft.content.schema_version).toBe('2');
  expect(state.draft.content.component_details).toEqual([{
    instance_id: props.instances[1].instance_id,
    description: 'Converts input x into output y.', limits: 'Finite real scalars only.',
  }]);
  expect((await (await page.request.get(base)).json()).data.assumptions.some((item:any) => item.statement === 'The coefficient remains constant.')).toBe(true);
  await editComponent(page);
  await editor.getByLabel('Component limits', {exact:true}).fill('Unsaved replacement.');
  await editor.getByRole('button', {name:'Cancel', exact:true}).click();
  await editComponent(page);
  await expect(editor.getByLabel('Component limits', {exact:true})).toHaveValue('Finite real scalars only.');
  await editor.getByRole('button', {name:'Cancel', exact:true}).click();
  await page.setViewportSize({width:1440,height:900});
  const beforeVersions = (await (await page.request.get(base+'/revisions')).json()).data;
  await page.getByRole('button',{name:'Save model version',exact:true}).click();
  await expect.poll(async () => (await (await page.request.get(base+'/revisions')).json()).data.length).toBe(beforeVersions.length+1);
  const versions = (await (await page.request.get(base+'/revisions')).json()).data;
  const version = versions.find((v:any) => !beforeVersions.some((old:any) => old.model_revision_id === v.model_revision_id)).model_revision_id;
  await page.getByRole('tab',{name:'Model explanation',exact:true}).click();
  await page.getByRole('button',{name:'Edit explanation',exact:true}).click();
  await page.getByRole('button',{name:'Save for model version',exact:true}).click();
  const publish=page.getByRole('dialog',{name:'Save explanation version',exact:true});
  await publish.getByLabel('Model version to explain',{exact:true}).selectOption(version);
  await publish.getByRole('button',{name:'Save explanation version',exact:true}).click();
  await expect(publish).toBeHidden();
  await page.getByLabel('Model version',{exact:true}).selectOption(version);
  await page.getByRole('tab',{name:'Diagram',exact:true}).click();
  await page.getByRole('button',{name:'1 Component A',exact:true}).click();
  await expect(page.getByText('Finite real scalars only.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Edit component',exact:true})).toHaveCount(0);
});
