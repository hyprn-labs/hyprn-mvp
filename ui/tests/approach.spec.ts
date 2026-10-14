import { test, expect, chromium, type Page, type Locator } from 'playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromiumExecutable } from './support/browser';

// Guarded fixture mounts the real controller/client, not the product screen.
async function open(page: Page) {
  await page.goto('/ui/');
  return page.evaluate(async () => {
    const h = (window as any).approachHarness;
    await h.api.login('owner', 'correct horse battery staple');
    const study = await h.api.createStudy('Controller study');
    await h.controller.open(study.study_id);
    return study.study_id as string;
  });
}
const state = (page: Page) => page.evaluate(() => (window as any).approachHarness.controller.getSnapshot());
const edit = (page: Page, question: string) => page.evaluate(q => { const c = (window as any).approachHarness.controller; c.edit({ ...c.getSnapshot().local, question: q }); }, question);
const act = (page: Page, method: string) => page.evaluate(m => (window as any).approachHarness.controller[m](), method);

test('@approach-controller keeps precise validation fields and clears them after recovery', async ({ page }) => {
  const sid = await open(page); await edit(page, 'Keep the engineering explanation');
  const fields = [{ path: '/content/steps/0/model_refs/0', code: 'invalid_reference', message: 'The selected component is not in this model version.', element_ref: null }];
  // Transport error fixture tests presentation; service regressions prove the actual validation.
  await page.route(`**/api/1/studies/${sid}/approach/preview`, route => route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ error: { code: 'invalid_request', message: 'Review the approach references.', fields, outcome: 'unchanged' } }) }), { times: 1 });
  expect(await act(page, 'preview')).toBe(false);
  expect((await state(page)).diagnostics).toEqual(fields);
  expect((await state(page)).local.question).toBe('Keep the engineering explanation');
  expect(await act(page, 'preview')).toBe(true);
  expect((await state(page)).diagnostics).toEqual([]);
  expect((await state(page)).error).toBe('');
});

test('@approach-controller separates local draft and immutable version with public receipts', async ({ page }) => {
  const sid = await open(page);
  expect((await state(page)).server.draft).toBeNull();
  await edit(page, 'Why use this method?');
  await expect(page.getByLabel('Dirty', { exact: true })).toHaveText('true');
  expect((await (await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft).toBeNull();
  await act(page, 'preview');
  expect((await state(page)).preview.issues).toEqual([]);
  expect(await act(page, 'save')).toBe(true);
  await expect(page.getByLabel('Dirty', { exact: true })).toHaveText('false');
  const draft = (await state(page)).server.draft;
  expect(draft.content.question).toBe('Why use this method?');
  expect(await act(page, 'saveVersion')).toBe(true);
  const saved = (await state(page)).saved;
  expect(saved.version.content.question).toBe(draft.content.question);
  const pages = await page.evaluate(async ({ sid, id }) => { const api = (window as any).approachHarness.api; return [await api.approachVersions(sid, { limit: 1 }), await api.approachUsage(sid, id, { limit: 1 })]; }, { sid, id: saved.version.approach_version_id });
  expect(pages[0].items[0].approach_version_id).toBe(saved.version.approach_version_id);
  expect(pages[1]).toEqual({ items: [], next_cursor: null });
  await page.evaluate(async sid => { const c = (window as any).approachHarness.controller; await c.open(sid); }, sid);
  await edit(page, 'Changed draft'); await act(page, 'save');
  expect((await (await page.request.get(`/api/1/studies/${sid}/approach/versions/${saved.version.approach_version_id}`)).json()).data).toEqual(saved);
  await page.evaluate(async id => (window as any).approachHarness.controller.restore(id), saved.version.approach_version_id);
  expect((await state(page)).local.question).toBe('Why use this method?');
  await page.reload();
  await page.evaluate(async sid => { const h=(window as any).approachHarness; await h.api.login('owner','correct horse battery staple'); await h.controller.open(sid); },sid);
  expect((await state(page)).server.draft.content.question).toBe('Why use this method?');
});

test('@approach-controller stale save preserves local work and explicitly reviews latest', async ({ page }) => {
  const sid = await open(page); await edit(page, 'Baseline'); await act(page, 'save');
  await edit(page, 'My local explanation'); await act(page, 'preview');
  await page.evaluate(async sid => { const h=(window as any).approachHarness, snapshot=await h.api.approach(sid), content={...snapshot.draft.content,question:'Concurrent explanation'}; const p=await h.api.previewApproach(sid,{schema_version:content.schema_version,expected_revision:snapshot.draft.revision,content}); await h.api.saveApproachDraft(sid,{schema_version:content.schema_version,command_id:crypto.randomUUID(),expected_revision:snapshot.draft.revision,content,expected_preview_digest:p.preview_digest}); },sid);
  expect(await act(page,'save')).toBe(false);
  expect((await state(page)).local.question).toBe('My local explanation');
  expect((await state(page)).status).toBe('stale');
  await act(page,'reviewLatest');
  expect((await state(page)).latest.draft.content.question).toBe('Concurrent explanation');
  expect((await state(page)).server.draft.content.question).toBe('Baseline');
  expect((await state(page)).local.question).toBe('My local explanation');
  await act(page,'reapplyToLatest'); expect(await act(page,'save')).toBe(true);
  expect((await (await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content.question).toBe('My local explanation');
});

for (const committed of [true,false]) test(`@approach-controller lost ${committed?'acknowledgement':'request'} uses original command and payload`,async({page})=>{
  const sid=await open(page); await edit(page,'Retain this uncertain proposal');
  let original: any;
  await page.route(`**/api/1/studies/${sid}/approach/draft`,async route=>{original=route.request().postDataJSON(); if(committed) await route.fetch(); await route.abort();},{times:1});
  expect(await act(page,'save')).toBe(false);
  expect((await state(page)).status).toBe('uncertain');
  expect((await state(page)).local.question).toBe(original.content.question);
  expect(await act(page,'save')).toBe(false);
  const frozen=await page.evaluate(()=> (window as any).approachHarness.api.pending.body);
  expect(frozen).toEqual(original);
  await act(page,'reconcile');
  if(!committed){
    expect(await page.evaluate(()=> (window as any).approachHarness.api.retryReady)).toBe(true);
    await act(page,'retryOriginal');
  }
  expect((await state(page)).server.draft.content).toEqual(original.content);
  const receipt=(await (await page.request.get(`/api/1/studies/${sid}/commands/${original.command_id}?category=approach_draft`)).json()).data;
  expect(receipt.state).toBe('committed'); expect(receipt.result.content).toEqual(original.content);
  expect(await page.evaluate(()=> (window as any).approachHarness.api.pending)).toBeNull();
  await expect(page.getByLabel('Dirty',{exact:true})).toHaveText('false');
});

test('@approach-controller dirty navigation and restore require explicit disposition',async({page})=>{
  const sid=await open(page); await edit(page,'Saved'); await act(page,'save'); await act(page,'saveVersion');
  const version=(await state(page)).saved.version.approach_version_id;
  await page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid);
  await edit(page,'Keep my unsaved draft');
  expect(await page.evaluate(async ({sid,version})=>(window as any).approachHarness.controller.open(sid,version),{sid,version})).toBe(false);
  expect(await page.evaluate(id=>(window as any).approachHarness.controller.restore(id),version)).toBe(false);
  expect((await state(page)).local.question).toBe('Keep my unsaved draft');
  await act(page,'discard'); expect((await state(page)).local.question).toBe('Saved');
  expect(await page.evaluate(({sid,version})=>(window as any).approachHarness.controller.open(sid,version),{sid,version})).toBe(true);
  await edit(page,'Attempt historical edit');
  expect((await state(page)).saved.version.content.question).toBe('Saved');
  expect((await state(page)).local).toBeNull();
});

test('@approach-controller late response cannot cross study or actor scope',async({page})=>{
  const sid=await open(page); await edit(page,'Protected first study'); await act(page,'save');
  const second=await page.evaluate(async()=> (await (window as any).approachHarness.api.createStudy('Second study')).study_id);
  let release!:()=>void; const gate=new Promise<void>(resolve=>{release=resolve;}); let captured!:()=>void; const arrived=new Promise<void>(resolve=>{captured=resolve;});
  await page.route(`**/api/1/studies/${sid}/approach`,async route=>{const response=await route.fetch();captured();await gate;await route.fulfill({response});},{times:1});
  const late=page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid);
  await arrived;
  await page.evaluate(async sid=>{const c=(window as any).approachHarness.controller;c.clear();await c.open(sid);},second);
  release(); await late;
  expect((await state(page)).studyId).toBe(second); expect((await state(page)).local.question).toBe('');
  await page.evaluate(async sid=>{const h=(window as any).approachHarness;await h.api.logout();h.controller.clear();await h.controller.open(sid);},sid);
  expect((await state(page)).server).toBeNull(); expect((await state(page)).local).toBeNull();
  await expect(page.getByText('Protected first study',{exact:true})).toHaveCount(0);
});

test('@approach-controller rejected exact reference retains edits and session loss clears protected state',async({page})=>{
  await open(page); await edit(page,'Local source rationale');
  await page.evaluate(()=>{const c=(window as any).approachHarness.controller;c.edit({...c.getSnapshot().local,basis_refs:[{kind:'run',run_id:crypto.randomUUID(),reason:'Unknown exact record',relation:'supports'}]});});
  expect(await act(page,'save')).toBe(false);
  expect((await state(page)).local.question).toBe('Local source rationale');
  expect((await state(page)).status).toBe('error');
  expect((await state(page)).error).toBeTruthy();
  expect((await state(page)).server.draft).toBeNull();
  await page.context().clearCookies(); await act(page,'reviewLatest');
  expect((await state(page)).local).toBeNull(); expect((await state(page)).server).toBeNull();
});

test('@approach-controller version acknowledgement recovery does not create a duplicate version',async({page})=>{
  const sid=await open(page); await edit(page,'Versioned explanation'); await act(page,'save');
  let original:any;
  await page.route(`**/api/1/studies/${sid}/approach/versions`,async route=>{original=route.request().postDataJSON();await route.fetch();await route.abort();},{times:1});
  expect(await act(page,'saveVersion')).toBe(false); expect((await state(page)).status).toBe('uncertain');
  expect(await act(page,'saveVersion')).toBe(false);
  expect(await act(page,'reconcile')).toBe(true);
  const saved=(await state(page)).saved;
  expect(saved.version.version_number).toBe(1);
  const receipt=(await (await page.request.get(`/api/1/studies/${sid}/commands/${original.command_id}?category=approach_version`)).json()).data;
  expect(receipt.result.saved).toEqual(saved);
  const versions=(await (await page.request.get(`/api/1/studies/${sid}/approach/versions`)).json()).data;
  expect(versions.items).toHaveLength(1);
});

test('@approach-controller revoked membership clears protected content and rejects original receipt',async({page})=>{
  const sid=await open(page); await edit(page,'Protected after revocation');
  let id='';page.on('request',request=>{if(request.url().endsWith('/approach/draft')) id=request.postDataJSON().command_id;});
  await act(page,'save');
  expect((await page.request.post('/fixture/revoke',{data:{study_id:sid}})).ok()).toBe(true);
  expect(await act(page,'reviewLatest')).toBe(false);
  expect((await state(page)).server).toBeNull();expect((await state(page)).local).toBeNull();
  const receipt=await page.request.get(`/api/1/studies/${sid}/commands/${id}?category=approach_draft`);
  expect(receipt.status()).toBe(404);
  expect(await receipt.text()).not.toContain('Protected after revocation');
});

test('@approach-controller definite stale retry unlocks recovery without losing local edits',async({page})=>{
  const sid=await open(page); await edit(page,'Baseline'); await act(page,'save');
  await edit(page,'Unacknowledged local proposal');
  await page.route(`**/api/1/studies/${sid}/approach/draft`,route=>route.abort(),{times:1});
  expect(await act(page,'save')).toBe(false); await act(page,'reconcile');
  // Independent real HTTP command advances CAS after the missing receipt read.
  await page.evaluate(async sid=>{
    const h=(window as any).approachHarness, api=h.api, current=await api.approach(sid), content={...current.draft.content,question:'Concurrent saved proposal'};
    const preview=await api.previewApproach(sid,{schema_version:content.schema_version,expected_revision:current.draft.revision,content});
    const response=await fetch(`/api/1/studies/${sid}/approach/draft`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':api.csrf},body:JSON.stringify({schema_version:content.schema_version,command_id:crypto.randomUUID(),expected_revision:current.draft.revision,expected_preview_digest:preview.preview_digest,content})});
    if(!response.ok)throw Error('Concurrent save failed');
  },sid);
  expect(await act(page,'retryOriginal')).toBe(false);
  expect((await state(page)).status).toBe('stale'); expect((await state(page)).local.question).toBe('Unacknowledged local proposal');
  expect(await page.evaluate(()=> (window as any).approachHarness.api.pending)).toBeNull();
  expect(await act(page,'reviewLatest')).toBe(true); await act(page,'reapplyToLatest');
  await edit(page,'Reviewed local proposal'); expect(await act(page,'save')).toBe(true);
  expect((await state(page)).server.draft.content.question).toBe('Reviewed local proposal');
});

async function openProduct(page:Page){
  const studyName='Engineering method '+crypto.randomUUID().slice(0,6);
  await page.goto('/ui/?workspace');
  await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'New study',exact:true}).click();
  await page.getByLabel('New study name',{exact:true}).fill(studyName);
  await page.getByRole('button',{name:'Create study',exact:true}).click();
  await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Modeling approach',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create modeling approach',exact:true}).click();
  return studyName;
}
async function writeQuestion(page:Page,question='Can the selected method answer the engineering question?'){
  if(!await page.getByRole('button',{name:'Leave editing',exact:true}).isVisible())await page.getByRole('button',{name:'Edit approach',exact:true}).click();
  await page.getByRole('button',{name:'Edit question and scope',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Edit question and scope',exact:true});
  await expect(dialog.getByLabel('Engineering question',{exact:true})).toBeFocused();
  await dialog.getByLabel('Engineering question',{exact:true}).fill(question);
  await dialog.getByLabel('Scope',{exact:true}).fill('An initial scientific screening.\n\nOperating conditions are supplied in configurations.');
  await dialog.getByLabel('Limitations',{exact:true}).fill('This explanation records the method; it does not establish scientific validity.');
  await dialog.getByLabel('Open questions',{exact:true}).fill('Which measurements would distinguish the competing explanations?');
  await dialog.getByRole('button',{name:'Apply to draft',exact:true}).click();
  await expect(page.getByRole('button',{name:'Edit question and scope',exact:true})).toBeFocused();
}
async function findingsShot(page:Page,name:string){const usage=page.getByRole('region',{name:'Approach usage',exact:true});await (name.includes('qualified')||name.includes('unavailable')?usage.getByRole('region',{name:'Source-linked inputs',exact:true}):usage).evaluate(element=>element.scrollIntoView({block:'start'}));await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence',name+'.png'),fullPage:false,animations:'disabled'});}
async function readingShot(page:Page,name:string){await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence',name+'.png'),fullPage:true,animations:'disabled'});}

test('@approach-method precise reference errors remain visible and recover without losing edits', async ({ page }) => {
  await openProduct(page); await writeQuestion(page, 'Preserve my rationale while correcting a reference');
  await page.route('**/approach/preview', route => route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ error: { code: 'invalid_request', message: 'Review the approach references.', outcome: 'unchanged', fields: [{ path: '/content/steps/0/model_refs/0', code: 'invalid_reference', message: 'The selected component is not in this model version.', element_ref: null }] } }) }), { times: 1 });
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  const alert = page.getByRole('alert').filter({ hasText: 'Review the approach references.' });
  await expect(alert).toContainText('The selected component is not in this model version.');
  await expect(alert).toContainText('/content/steps/0/model_refs/0');
  await expect(page.getByLabel('The modeling approach', { exact: true }).getByRole('heading', {name:'Preserve my rationale while correcting a reference', exact:true})).toBeVisible();
  await readingShot(page, 'precise-reference-error-light');
  await page.emulateMedia({ colorScheme: 'dark' }); await readingShot(page, 'precise-reference-error-dark');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(alert).toHaveCount(0);
  await expect(page.getByText('Draft · saved', { exact: true })).toBeVisible();
  // An unchanged saved draft also needs visible issues from a successful preview response.
  await page.route('**/approach/preview', async route => {
    const response = await route.fetch(), value = await response.json();
    value.data.issues = [{ path: '/model_bindings/0', code: 'invalid_reference', message: 'Review the selected immutable model version.' }];
    await route.fulfill({ response, json: value });
  }, { times: 1 });
  await page.getByRole('button', { name: 'Save approach version', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'References to review', exact: true })).toBeVisible();
  await expect(page.getByRole('alert').filter({ hasText: 'Review the selected immutable model version.' })).toContainText('/model_bindings/0');
  await expect(page.getByRole('dialog', { name: 'Save approach version', exact: true })).not.toBeVisible();
  await readingShot(page, 'saved-draft-reference-issue-dark');
});

test('@approach-assumptions local method assumptions save without model mutation',async({page})=>{
  await openProduct(page);await writeQuestion(page);
  // Approach assumptions live in Study details (See more details on the question box).
  await page.getByRole('button',{name:'See more details',exact:true}).click();
  // One empty state and one action name for every assumption owner.
  const conditions=page.getByRole('dialog',{name:'Study details',exact:true});
  await expect(conditions.getByText('No assumptions', { exact: true })).toHaveCount(0);
  await expect(
    conditions.getByRole('button', { name: 'Add approach assumption', exact: true }),
  ).toHaveCount(0);
  await conditions.getByRole('button',{name:'Add assumption',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Approach assumption',exact:true});
  await editor.getByLabel('Assumption statement',{exact:true}).fill('A scalar approximation is suitable for this investigation.');
  await editor.getByLabel('Assumption role',{exact:true}).selectOption('overall_method');
  await editor.getByRole('button',{name:'Apply assumption',exact:true}).click();await page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const content=(await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content;
  expect(content.assumptions).toHaveLength(1);expect(content.assumptions[0].role).toBe('overall_method');expect(content.model_bindings).toEqual([]);
});

async function seededConditions(page:Page,browser:any,baseURL:string|undefined,options:{cases?:boolean;failure?:boolean;second?:boolean}={}){
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  const data=await helper.evaluate(async({sid,options})=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');const fixture=options.failure?await(await fetch('/fixture/failure-package')).json():null,pkg=fixture?.package??await(await fetch('/fixture/model-package')).json(),m=pkg.revisions[0];
    await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:pkg},'model',sid);
    const evidence=await api.createEvidence(sid,{evidence_schema_version:'3',kind:'note',title:'Screening measurements',content:'The approximation applies within the measured operating range.',source_refs:[],resource_scope:{scope_version:'1',kind:'study',study_id:sid}});
    await c.open(sid);const content=structuredClone(c.getSnapshot().local),binding={binding_id:crypto.randomUUID(),model_id:m.model_id,model_revision_id:m.model_revision_id},proposal={assumption_id:crypto.randomUUID(),statement:'The response is approximately linear in the measured range.',role:'proposed_model_condition',evidence_links:[{evidence_version_id:evidence.evidence_version_id,relation:'supports',locator:'Section 2 · Operating range'}]};
    content.question='Why use the scalar response approximation?';content.scope='Measured operating conditions';content.model_bindings=[binding];content.assumptions=[proposal];content.steps=[{step_id:crypto.randomUUID(),title:'Predict the measured response',purpose:'Relate the imposed conditions to the response.',rationale:'Use the measured range as the basis for the approximation.',remaining_work:'',intent:{transformation:'Linear scalar response',inputs:'Measured operating condition',outputs:'Predicted response',depends_on_step_ids:[]},implementation_state:'linked',implementation_refs:[{kind:'model',binding_id:binding.binding_id}],assumption_refs:[{kind:'approach',assumption_id:proposal.assumption_id}],evidence_links:[]}];content.cases=[{case_id:crypto.randomUUID(),title:'Nominal range',question:'Does the response fit the measured range?',rationale:'Initial screening',binding_id:binding.binding_id,evidence_links:[]}];
    if(options.cases)content.cases.push({...content.cases[0],case_id:crypto.randomUUID(),title:'Upper operating range',question:'Does the upper operating range satisfy the criterion?'});
    c.edit(content);if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);const saved=c.getSnapshot().saved;
    let second=null;if(options.second){await c.open(sid);c.edit({...c.getSnapshot().local,question:'Second saved interpretation'});if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);second=c.getSnapshot().saved;}
    return {sid,model:m,proposal,evidence,saved,second,fixture};
  },{sid,options});await context.close();await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Edit approach',exact:true}).click();return data;
}

test('@approach-configuration saved case opens explicit configuration with exact approach context',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();
  await expect(page.getByLabel('Configuration name',{exact:true})).toBeVisible();
  await expect(page.getByLabel('Configuration context',{exact:true})).toContainText('Nominal range');
  await expect(page.getByLabel('Configuration context',{exact:true})).toContainText('Approach version 1');
  const values=page.getByRole('region',{name:'Configuration inputs',exact:true}).locator('input[type="number"]');
  expect(await values.count()).toBeGreaterThan(0);for(const value of await values.all())await expect(value).toHaveValue('');
  await expect(page.getByText('No criteria specified.',{exact:true})).toBeVisible();
  // The approach record has no study conditions; saved records carry no Mode, Derivatives or "Deterministic scalar" line.
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  await fillCaseConfiguration(page,'S1 saved record');await saveCaseConfiguration(page);
  const saved=page.getByRole('region',{name:'Saved configuration',exact:true});
  await expect(saved.getByRole('button',{name:'View modeling approach',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  await expect(saved).not.toContainText('Deterministic scalar calculation');
  await expect(saved.getByRole('button',{name:'Run this configuration',exact:true})).toBeVisible();
  await saved.getByRole('button',{name:'Record details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Configuration record',exact:true}).locator('dt')).toHaveText(['Configuration version','Model version']);
  await page.keyboard.press('Escape');
});

async function casesTab(page:Page){const tab=page.getByRole('tab',{name:'Cases & results',exact:true});if(await tab.getAttribute('aria-selected')!=='true')await tab.click();}
async function stepTab(page:Page,name:string){await page.getByRole('region',{name:'Selected method step',exact:true}).getByRole('tab',{name,exact:true}).click();}
async function fillCaseConfiguration(page:Page,name:string,value='2'){
  await page.getByLabel('Configuration name',{exact:true}).fill(name);
  await expect(page.getByRole('region',{name:'Configuration inputs',exact:true}).getByRole('combobox').first()).toBeEnabled();
  for(const select of await page.getByRole('region',{name:'Configuration inputs',exact:true}).getByRole('combobox').all())await select.selectOption('dimensionless');

  for(const input of await page.locator('input[data-input-key]').all())await input.fill(value);
  for(const input of await page.locator('input[aria-label$=" provenance"]').all())await input.fill('Explicit measurement supplied for this case.');
}
async function saveCaseConfiguration(page:Page){
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&/\/configurations$/.test(r.url()));
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  const saved=await response;expect(saved.status()).toBe(201);await expect(page.getByText('Saved · read-only',{exact:true})).toBeVisible();return (await saved.json()).data;
}

test('@approach-configuration two cases save independent inputs criteria pins and immutable interpretation',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL,{cases:true});
  await casesTab(page);await expect(page.getByRole('button',{name:'Create configuration for Nominal range',exact:true})).toHaveCount(0);
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);
  const saved:any[]=[];
  for(const [index,c] of data.saved.version.content.cases.entries()){
    await casesTab(page);await page.getByRole('button',{name:'Create configuration for '+c.title,exact:true}).click();await fillCaseConfiguration(page,c.title+' configuration',String(index+2));
    await page.locator('.configuration-criterion').getByRole('button',{name:'Edit',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Edit criteria',exact:true});await dialog.getByRole('button',{name:'Add criterion',exact:true}).click();await dialog.getByLabel('Criterion 1 output',{exact:true}).selectOption({index:1});await dialog.getByLabel('Criterion 1 threshold',{exact:true}).fill('10');await dialog.getByLabel('Criterion 1 units',{exact:true}).selectOption('dimensionless');await dialog.getByRole('button',{name:'Done',exact:true}).click();
    const record=await saveCaseConfiguration(page);saved.push(record);expect(record.configuration.schema_version).toBe('4');expect(record.configuration.approach_binding.case_id).toBe(c.case_id);expect(record.configuration.inputs.every((i:any)=>i.value===index+2)).toBe(true);expect(record.configuration.criteria).toHaveLength(1);
    await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(data.saved.version.approach_version_id);
  }
  expect(saved[0].configuration.configuration_revision_id).not.toBe(saved[1].configuration.configuration_revision_id);
  await expect(page.getByRole('region',{name:'Approach usage',exact:true})).toContainText('Nominal range configuration');await expect(page.getByRole('region',{name:'Approach usage',exact:true})).toContainText('Upper operating range configuration');
  await page.getByLabel('Findings case',{exact:true}).selectOption(data.saved.version.content.cases[1].case_id);await expect(page.getByRole('region',{name:'Approach usage',exact:true})).not.toContainText('Nominal range configuration');
  await page.getByRole('button',{name:'View configuration',exact:true}).click();await expect(page.getByText('Saved · read-only',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await expect(page.getByRole('button',{name:'Leave editing',exact:true})).toBeVisible();await writeQuestion(page,'A later interpretation that must not rewrite configurations');await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  for(const record of saved)expect((await(await page.request.get(`/api/1/studies/${data.sid}/configurations/${record.configuration.configuration_revision_id}`)).json()).data).toEqual(record);
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await expect(page.getByRole('region',{name:'Approach usage',exact:true})).toContainText('Nominal range configuration');await readingShot(page,'approach-configuration-usage-light');await page.evaluate(()=>document.documentElement.dataset.theme='dark');await readingShot(page,'approach-configuration-usage-dark');
});

test('@approach-configuration exact pin change remove and copy preserve assumptions and context',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL,{cases:true});await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Pin choices');
  await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Choose modeling approach',exact:true});await dialog.getByLabel('Intended case',{exact:true}).selectOption(data.saved.version.content.cases[1].case_id);await dialog.getByRole('button',{name:'Use selected approach',exact:true}).click();
  const original=await saveCaseConfiguration(page);expect(original.configuration.approach_binding.case_id).toBe(data.saved.version.content.cases[1].case_id);
  await page.getByRole('button',{name:'Copy configuration to draft',exact:true}).click();await page.getByLabel('Configuration name',{exact:true}).fill('Unlinked independent copy');await page.getByRole('button',{name:'Remove approach link',exact:true}).click();const copy=await saveCaseConfiguration(page);expect(copy.configuration.schema_version).toBe('4');expect(copy.configuration.approach_binding).toBeNull();expect(copy.approach_closure).toBeNull();expect(copy.configuration.assumptions).toEqual(original.configuration.assumptions);expect(copy.configuration.context_snapshot).toEqual(original.configuration.context_snapshot);
  expect((await(await page.request.get(`/api/1/studies/${data.sid}/configurations/${original.configuration.configuration_revision_id}`)).json()).data).toEqual(original);
});

test('@approach-configuration unapplied pin choice is protected and cancellation clears its guard',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL,{cases:true});await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Approach version 1');await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();const pin=page.getByRole('dialog',{name:'Choose modeling approach',exact:true});await pin.getByLabel('Intended case',{exact:true}).selectOption(data.saved.version.content.cases[1].case_id);
  await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'overview'}).toString();},data.sid);const guard=page.getByRole('dialog',{name:'Unsaved changes',exact:true});await expect(guard).toBeVisible();await guard.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(pin.getByLabel('Intended case',{exact:true})).toHaveValue(data.saved.version.content.cases[1].case_id);await pin.getByRole('button',{name:'Keep current choice',exact:true}).click();await expect(page.getByRole('region',{name:'Configuration context',exact:true})).toContainText('Nominal range');await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();await expect(guard).toHaveCount(0);await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(data.saved.version.approach_version_id);
});

test('@approach-configuration usage pagination and incompatible approach choice are explicit',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'First usage');const source=await saveCaseConfiguration(page);
  const helperContext=await browser.newContext({baseURL}),helper=await helperContext.newPage();await helper.goto('/ui/');
  const incompatible=await helper.evaluate(async({sid,source})=>{const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');const original=source.configuration;for(let i=0;i<10;i++){const configuration={schema_version:'4',study_id:sid,model_id:original.model_id,model_revision_id:original.model_revision_id,name:'Usage sample '+i,inputs:original.inputs.map((v:any)=>({kind:'literal',target:v.target,value:v.value,units:v.units,provenance:v.provenance})),criteria:[],numerical:original.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(sid)).revision},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[],approach_selection:{approach_version_id:original.approach_binding.approach_version_id,case_id:original.approach_binding.case_id}};const p=await api.previewConfiguration4(configuration);await api.commitConfiguration4({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:p.candidate_digest});}await c.open(sid);c.edit({...c.getSnapshot().local,question:'Proposed alternative without model correspondence',model_bindings:[],steps:[],cases:[],assumptions:[]});if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);return c.getSnapshot().saved;},{sid:data.sid,source});await helperContext.close();
  await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();const usage=page.getByRole('region',{name:'Approach usage',exact:true});await expect(usage.getByRole('button',{name:'View configuration',exact:true})).toHaveCount(10);await usage.getByRole('button',{name:'Load more usage',exact:true}).click();await expect(usage.getByRole('button',{name:'View configuration',exact:true})).toHaveCount(11);await expect(usage.getByRole('button',{name:'Load more usage',exact:true})).toHaveCount(0);
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();const pin=page.getByRole('dialog',{name:'Choose modeling approach',exact:true});await pin.getByLabel('Saved approach version',{exact:true}).selectOption(incompatible.version.approach_version_id);await expect(pin).toContainText('does not reference the configuration’s model version');await expect(pin.getByRole('button',{name:'Use selected approach',exact:true})).toBeDisabled();await pin.getByRole('button',{name:'Keep current choice',exact:true}).click();await expect(page.getByRole('region',{name:'Configuration context',exact:true})).toContainText('Approach version 1');
});

test('@approach-configuration failed run usage and modified seed keep change remove exact interpretation',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL,{cases:true,failure:true});await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Failed screening');const source=await saveCaseConfiguration(page);
  const helperContext=await browser.newContext({baseURL}),helper=await helperContext.newPage();await helper.goto('/ui/');
  const run=await helper.evaluate(async({sid,id,key})=>{const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const run=await api.submitRun(sid,id);const response=await fetch('/fixture/retain-failed-outcome',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,study_id:sid,run_id:run.run_id})});if(!response.ok)throw new Error(await response.text());return api.run(sid,run.run_id);},{sid:data.sid,id:source.configuration.configuration_revision_id,key:data.fixture.key});await helperContext.close();expect(run.history.history_schema_version).toBe('6');expect(run.history.approach_closure.schema_version).toBe('3');expect(run.history.results.execution.state).toBe('failed');
  await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();const usage=page.getByRole('region',{name:'Approach usage',exact:true});await expect(usage.getByLabel('Run outcomes',{exact:true})).toContainText('None defined');await expect(usage.getByLabel('Run outcomes',{exact:true})).not.toContainText('Completed');await readingShot(page,'approach-failed-findings');
  for(const mode of ['keep','change','remove']){
    await usage.getByRole('button',{name:'View run',exact:true}).click();await page.getByRole('button',{name:'Create modified run',exact:true}).click();await expect(page.getByRole('region',{name:'Configuration context',exact:true})).toContainText('Nominal range');await expect(page.getByRole('button',{name:'Save model version',exact:true})).toHaveCount(0);
    await page.getByLabel('Configuration name',{exact:true}).fill('Modified '+mode);await page.getByRole('button',{name:'Edit context',exact:true}).click();const context=page.getByRole('dialog',{name:'Edit context',exact:true});await context.getByLabel('Description',{exact:true}).fill('Editable inherited interpretation '+mode);await context.getByRole('button',{name:'Done',exact:true}).click();
    if(mode==='remove')await page.getByRole('button',{name:'Remove approach link',exact:true}).click();
    if(mode==='change'){await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();const pin=page.getByRole('dialog',{name:'Choose modeling approach',exact:true});await pin.getByLabel('Intended case',{exact:true}).selectOption(data.saved.version.content.cases[1].case_id);await pin.getByRole('button',{name:'Use selected approach',exact:true}).click();}
    await page.getByRole('button',{name:'Save configuration',exact:true}).click();const review=page.getByRole('dialog',{name:'Review modified run',exact:true});await expect(review).toBeVisible();if(mode!=='keep')await expect(review).toContainText('Modeling approach');const committed=page.waitForResponse(r=>r.request().method()==='POST'&&/\/configurations$/.test(r.url()));await review.getByRole('button',{name:'Save modified configuration',exact:true}).click();const response=await committed;expect(response.status()).toBe(201);const saved=(await response.json()).data;expect(saved.configuration.model_revision_id).toBe(source.configuration.model_revision_id);expect(saved.configuration.context_snapshot.description).toBe('Editable inherited interpretation '+mode);expect(saved.configuration.approach_binding?.case_id??null).toBe(mode==='remove'?null:data.saved.version.content.cases[mode==='change'?1:0].case_id);await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();
  }
  expect((await(await page.request.get(`/api/1/studies/${data.sid}/configurations/${source.configuration.configuration_revision_id}`)).json()).data).toEqual(source);
});

test('@approach-configuration genuine 200 percent context and pin picker keyboard theme review',async({baseURL,browser})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/configuration-zoom-extension');await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Configuration zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/configuration-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try{const page=context.pages()[0]??await context.newPage(),data=await seededConditions(page,browser,baseURL,{cases:true});await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Nominal operating range');await expect(page.getByRole('region',{name:'Configuration context',exact:true})).toContainText('Approach version 1');
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'approach-configuration-context-'+theme);}
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));const bounds=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width+1);geometry.push({name,...bounds});const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));}
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.getByRole('region',{name:'Configuration context',exact:true}).evaluate(e=>e.scrollIntoView({block:'start'}));await capture('approach-configuration-context-200-'+theme);const change=page.getByRole('button',{name:'Change modeling approach',exact:true});await change.focus();await change.press('Enter');const pin=page.getByRole('dialog',{name:'Choose modeling approach',exact:true});await expect(pin.getByRole('button',{name:'Use selected approach',exact:true})).toBeEnabled();await pin.getByLabel('Intended case',{exact:true}).focus();await expect(pin.getByLabel('Intended case',{exact:true})).toBeFocused();await capture('approach-configuration-picker-200-'+theme);await page.keyboard.press('Escape');await expect(change).toBeFocused();}
    await writeFile(join(root,'evidence/approach-configuration-zoom-geometry.json'),JSON.stringify({zoom:2,viewport:page.viewportSize(),geometry},null,2));
  }finally{await context.close();}
});

test('@approach-assumptions contextual evidence and exact model assumptions retain ownership',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);
  await stepTab(page,'Assumptions & evidence');
  const step=page.getByRole('region',{name:'Predict the measured response assumptions and evidence',exact:true});
  await step.getByRole('button',{name:'View evidence',exact:true}).click();const detail=page.getByRole('dialog',{name:/Evidence/}).last();await expect(detail).toContainText(data.evidence.content);await detail.getByRole('button',{name:'Done',exact:true}).click();
  await step.getByRole('button',{name:'Link assumption to Predict the measured response',exact:true}).click();const picker=page.getByRole('dialog',{name:'Link assumption',exact:true});await picker.getByRole('button',{name:/A scalar approximation is appropriate/}).click();await expect(step).toContainText('version '+data.model.model_revision_id.slice(0,8)+' · Model');await expect(step).not.toContainText('(read-only)');
  await step.getByRole('button',{name:'Add evidence to Predict the measured response rationale',exact:true}).click();const evidence=page.getByRole('dialog',{name:'Add evidence to Predict the measured response rationale',exact:true});await evidence.getByRole('button',{name:/Choose Screening measurements/}).click();await evidence.getByLabel('Relationship',{exact:true}).selectOption('challenges');await evidence.getByRole('button',{name:'Attach evidence',exact:true}).click();await step.getByRole('button',{name:'Edit citation',exact:true}).click();const citation=page.getByRole('dialog',{name:'Edit citation',exact:true});await citation.getByLabel('Evidence locator',{exact:true}).fill('Table 3 · Residuals');await citation.getByRole('button',{name:'Apply citation',exact:true}).click();
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  const current=(await(await page.request.get(`/api/1/studies/${data.sid}/approach`)).json()).data.draft.content;expect(current.steps[0].assumption_refs[1]).toMatchObject({kind:'model',assumption_id:data.model.assumptions[0].assumption_id});expect(current.steps[0].evidence_links[0]).toEqual({evidence_version_id:data.evidence.evidence_version_id,relation:'challenges',locator:'Table 3 · Residuals'});
  const model=(await(await page.request.get(`/api/1/studies/${data.sid}/models/${data.model.model_id}`)).json()).data;expect(model.assumptions).toEqual(data.model.assumptions);
  await readingShot(page,'approach-assumptions-light');await page.evaluate(()=>document.documentElement.dataset.theme='dark');await readingShot(page,'approach-assumptions-dark');
});

for(const uncertain of ['', 'acknowledgement', 'request'])test(`@approach-assumptions explicit handoff ${uncertain?'recovers lost '+uncertain:'retains old proposed version'}`,async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);const sid=data.sid,mid=data.model.model_id;
  if(!await page.getByRole('button',{name:'Leave editing',exact:true}).isVisible())await page.getByRole('button',{name:'Edit approach',exact:true}).click();await page.getByRole('button',{name:'See more details',exact:true}).click();await page.getByRole('button',{name:'Implement condition: '+data.proposal.statement,exact:true}).click();let handoff=page.getByRole('dialog',{name:'Implement proposed condition',exact:true});await handoff.getByLabel('Condition target model',{exact:true}).selectOption(mid);await expect(handoff).toContainText('current saved draft');await expect(handoff).toContainText(data.model.model_revision_id.slice(0,8));await handoff.getByRole('button',{name:'Open model assumption editor',exact:true}).click();
  const previewResponse=page.waitForResponse(r=>r.url().endsWith('/models/'+mid+'/preview'));await page.getByRole('button',{name:'Preview proposed model condition',exact:true}).click();const previewHttp=await previewResponse;expect(previewHttp.status(),await previewHttp.text()).toBe(200);const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});await expect(preview.getByRole('alert')).toHaveCount(0);await expect(preview.getByRole('button',{name:'Apply changes',exact:true})).toBeEnabled();let command:any;const commands:any[]=[];let requests=0;
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith(`/models/${mid}/edits`)){requests++;command=r.postDataJSON();commands.push(command);}});
  if(uncertain)await page.route(`**/models/${mid}/edits`,async route=>{if(uncertain==='acknowledgement')await route.fetch();await route.abort();},{times:1});
  await preview.getByRole('button',{name:'Apply changes',exact:true}).click();
  if(uncertain){await expect(preview).toContainText('uncertain');await preview.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(page.getByRole('button',{name:'Return to modeling approach',exact:true})).toBeDisabled();await page.getByRole('button',{name:'Check original command',exact:true}).click();if(uncertain==='request')await page.getByRole('button',{name:'Retry original command',exact:true}).click();await expect(page.getByRole('button',{name:'Check original command',exact:true})).toHaveCount(0);}
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content.assumptions).toEqual([data.proposal]);
  await page.getByRole('button',{name:'Save model version',exact:true}).click();await expect(page.getByText(/Model version .* saved\./)).toBeVisible();
  const model=(await(await page.request.get(`/api/1/studies/${sid}/models/${mid}`)).json()).data;expect(model.assumptions).toHaveLength(2);const target=model.assumptions.find((a:any)=>a.statement===data.proposal.statement);expect(target.evidence_links).toEqual([{evidence_version_id:data.evidence.evidence_version_id,relation:'supports'}]);expect(requests).toBe(uncertain==='request'?2:1);for(const retry of commands)expect(retry).toEqual(commands[0]);expect(command.command_id).toBeTruthy();
  const revisions=(await(await page.request.get(`/api/1/studies/${sid}/models/${mid}/revisions`)).json()).data;const committed=revisions.find((r:any)=>r.model_revision_id!==data.model.model_revision_id);expect(committed).toBeTruthy();
  await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();if(!await page.getByRole('button',{name:'Leave editing',exact:true}).isVisible())await page.getByRole('button',{name:'Edit approach',exact:true}).click();await page.getByRole('button',{name:'See more details',exact:true}).click();await page.getByRole('button',{name:'Implement condition: '+data.proposal.statement,exact:true}).click();handoff=page.getByRole('dialog',{name:'Implement proposed condition',exact:true});await handoff.getByLabel('Condition target model',{exact:true}).selectOption(mid);await handoff.getByLabel('Condition committed model version',{exact:true}).selectOption(committed.model_revision_id);await handoff.getByLabel('Committed model assumption',{exact:true}).selectOption(target.assumption_id);await handoff.getByLabel('Condition method step',{exact:true}).selectOption(data.saved.version.content.steps[0].step_id);await handoff.getByRole('button',{name:'Replace with model assumption',exact:true}).click();await page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  if(!uncertain){const other=await browser.newContext({baseURL}),helper=await other.newPage();await helper.goto('/ui/');await helper.evaluate(async sid=>{const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const d=(await api.approach(sid)).draft,body={schema_version:d.content.schema_version,expected_revision:d.revision,content:{...d.content,scope:'Another engineer updated the scientific scope.'}};const p=await api.previewApproach(sid,body);await api.saveApproachDraft(sid,{...body,command_id:crypto.randomUUID(),expected_preview_digest:p.preview_digest});},sid);await other.close();await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.getByRole('button',{name:'Review latest draft',exact:true}).click();await expect(page.getByLabel('Review latest draft',{exact:true})).toContainText('Another engineer updated the scientific scope.');await page.getByRole('button',{name:'Reapply my changes',exact:true}).click();}
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Save approach version',exact:true}).click();await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();await expect(page.getByLabel('Approach version',{exact:true})).toContainText('v2 (read-only)');
  const v=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions`)).json()).data.items[0];const saved=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${v.approach_version_id}`)).json()).data;expect(saved.version.content.assumptions).toEqual([]);expect(saved.version.content.steps[0].assumption_refs[0]).toMatchObject({kind:'model',assumption_id:target.assumption_id,origin:{approach_version_id:data.saved.version.approach_version_id,assumption_id:data.proposal.assumption_id,digest:data.saved.version.digest}});
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await expect(page.getByLabel('The modeling approach')).toContainText('Proposed model condition');await expect(page.getByLabel('The modeling approach').getByText('Proposed model condition · Approach-owned',{exact:true})).toHaveCount(0);expect((await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${data.saved.version.approach_version_id}`)).json()).data).toEqual(data.saved);
});

test('@approach-assumptions prior configuration assumption reference stays exact and read-only',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  const original=await helper.evaluate(async sid=>{const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const test=await(await fetch('/fixture/failure-package')).json(),m=test.package.revisions[0],c=test.configuration;await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:test.package},'model',sid);const study=await api.study(sid);const configuration={schema_version:'3',study_id:sid,model_id:m.model_id,model_revision_id:m.model_revision_id,name:'Prior measurement comparison',inputs:c.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),criteria:[],numerical:c.numerical,context_source:{kind:'current_study',expected_study_revision:study.revision},notes:['Earlier interpretation'],derivation:null,assumptions:[{assumption_id:crypto.randomUUID(),statement:'The earlier measurement uses the same operating range.',evidence_links:[]}],general_context_evidence_version_ids:[]};const preview=await api.previewConfiguration3(configuration);return api.commitConfiguration3({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:preview.candidate_digest});},data.sid);await context.close();
  await stepTab(page,'Assumptions & evidence');await page.getByRole('button',{name:'Link assumption to Predict the measured response',exact:true}).click();await page.getByRole('dialog',{name:'Link assumption',exact:true}).getByRole('button',{name:/Configuration Prior measurement comparison/}).click();await expect(page.getByRole('region',{name:'Predict the measured response assumptions and evidence',exact:true})).toContainText('Prior measurement comparison');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();const draft=(await(await page.request.get(`/api/1/studies/${data.sid}/approach`)).json()).data.draft;expect(draft.content.steps[0].assumption_refs[1]).toEqual({kind:'configuration',configuration_revision_id:original.configuration.configuration_revision_id,assumption_id:original.configuration.assumptions[0].assumption_id});expect((await(await page.request.get(`/api/1/studies/${data.sid}/configurations/${original.configuration.configuration_revision_id}`)).json()).data).toEqual(original);
  for(const close of ['Cancel','Escape']){if(!await page.getByRole('button',{name:'Leave editing',exact:true}).isVisible())await page.getByRole('button',{name:'Edit approach',exact:true}).click();await expect(page.getByRole('button',{name:'Leave editing',exact:true})).toBeVisible();await page.getByRole('button',{name:'Approach actions',exact:true}).click();await page.getByRole('button',{name:'Earlier work',exact:true}).click();await expect(page.getByRole('dialog',{name:'Earlier work',exact:true})).toContainText('Add earlier work');await page.getByRole('button',{name:'Add earlier work',exact:true}).click();const basis=page.getByRole('dialog',{name:'Earlier work',exact:true});await basis.getByLabel('Earlier record',{exact:true}).selectOption('configuration/'+original.configuration.configuration_revision_id);await basis.getByLabel('Basis reason',{exact:true}).fill('A reason that will be cancelled.');if(close==='Cancel')await basis.getByRole('button',{name:'Cancel',exact:true}).click();else await page.keyboard.press('Escape');await page.getByRole('dialog',{name:'Earlier work',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await page.getByRole('dialog',{name:'Approach actions',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await page.getByRole('button',{name:'Back to overview',exact:true}).click();await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toBeVisible();await expect(page.getByRole('dialog',{name:'Unsaved changes',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'View modeling approach',exact:true}).click();}

});

for(const form of ['assumption','citation','evidence','question','step','case'])test(`@approach-assumptions unapplied ${form} edits survive hash navigation`,async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);let field:any;
  if(form==='assumption'){await page.getByRole('button',{name:'See more details',exact:true}).click();await page.getByRole('button',{name:'Edit assumption: '+data.proposal.statement,exact:true}).click();field=page.getByRole('dialog',{name:'Approach assumption',exact:true}).getByLabel('Assumption statement',{exact:true});}
  else if(form==='question'){await page.getByRole('button',{name:'Edit question and scope',exact:true}).click();field=page.getByRole('dialog',{name:'Edit question and scope',exact:true}).getByLabel('Engineering question',{exact:true});}
  else if(form==='step'){await page.getByRole('button',{name:'Edit step 1',exact:true}).click();field=page.getByRole('dialog',{name:'Method step',exact:true}).getByLabel('Purpose',{exact:true});}
  else if(form==='case'){await casesTab(page);await page.getByRole('button',{name:'Edit case 1',exact:true}).click();field=page.getByRole('dialog',{name:'Intended case',exact:true}).getByLabel('Case question',{exact:true});}
  else{await stepTab(page,'Assumptions & evidence');await page.getByRole('button',{name:'Add evidence to Predict the measured response rationale',exact:true}).click();const picker=page.getByRole('dialog',{name:'Add evidence to Predict the measured response rationale',exact:true});if(form==='evidence'){await picker.getByRole('button',{name:'Create new',exact:true}).click();field=picker.getByLabel('Title',{exact:true});}else{await picker.getByRole('button',{name:/Choose Screening measurements/}).click();await picker.getByLabel('Relationship',{exact:true}).selectOption('context');await picker.getByRole('button',{name:'Attach evidence',exact:true}).click();await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Edit citation',exact:true}).click();field=page.getByRole('dialog',{name:'Edit citation',exact:true}).getByLabel('Evidence locator',{exact:true});}}
  await field.fill('Preserve these unapplied local changes.');const exact=page.url();await page.evaluate(()=>{location.hash='';});const guard=page.getByRole('dialog',{name:'Unsaved changes',exact:true});await expect(guard).toBeVisible();await expect(guard.getByRole('button',{name:'Save changes',exact:true})).toBeDisabled();await guard.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(field).toHaveValue('Preserve these unapplied local changes.');await expect(page).toHaveURL(exact);
  await page.evaluate(()=>{location.hash='';});await guard.getByRole('button',{name:'Discard changes',exact:true}).click();await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();
});

test('@approach-assumptions unknown and foreign evidence fail without losing local explanation',async({page})=>{
  const sid=await open(page);await edit(page,'Keep this exact scientific rationale');await act(page,'save');
  const result=await page.evaluate(async sid=>{const {api,controller:c}=(window as any).approachHarness;const other=await api.createStudy('Foreign evidence owner');const foreign=await api.createEvidence(other.study_id,{evidence_schema_version:'3',kind:'note',title:'Foreign evidence',content:'Private to another study.',source_refs:[],resource_scope:{scope_version:'1',kind:'study',study_id:other.study_id}});const outcomes=[];for(const id of [crypto.randomUUID(),foreign.evidence_version_id]){c.edit({...c.getSnapshot().local,assumptions:[{assumption_id:crypto.randomUUID(),statement:'Keep the local condition text.',role:'overall_method',evidence_links:[{evidence_version_id:id,relation:'supports',locator:'Table 1'}]}]});outcomes.push({saved:await c.save(),state:structuredClone(c.getSnapshot())});}return outcomes;},sid);
  for(const entry of result){expect(entry.saved).toBe(false);expect(entry.state.local.question).toBe('Keep this exact scientific rationale');expect(entry.state.local.assumptions[0].statement).toBe('Keep the local condition text.');}
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content.assumptions).toEqual([]);
});

test('@approach-method proposed steps and cases persist through actual draft and version commands',async({page})=>{
  await openProduct(page);await writeQuestion(page);
  await page.getByRole('tab',{name:'Methods',exact:true}).click();await page.getByRole('button',{name:'Add method step',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Method step',exact:true});
  await dialog.getByLabel('Step title',{exact:true}).fill('Estimate the response');
  await dialog.getByLabel('Purpose',{exact:true}).fill('Relate operating conditions to the response.');
  await dialog.getByLabel('Why this method',{exact:true}).fill('A scalar approximation supports initial screening.');
  await dialog.getByLabel('Intended transformation',{exact:true}).fill('Convert the imposed quantity into a predicted response.');
  await dialog.getByLabel('Intended inputs',{exact:true}).fill('Explicit operating condition');
  await dialog.getByLabel('Intended outputs',{exact:true}).fill('Predicted response');
  await dialog.getByRole('button',{name:'Apply step',exact:true}).click();
  await page.getByRole('tab',{name:'Cases & results',exact:true}).click();await page.getByRole('button',{name:'Add intended case',exact:true}).click();
  const caseDialog=page.getByRole('dialog',{name:'Intended case',exact:true});await caseDialog.getByLabel('Case title',{exact:true}).fill('Nominal conditions');await caseDialog.getByLabel('Case question',{exact:true}).fill('What is the nominal response?');await caseDialog.getByRole('button',{name:'Apply case',exact:true}).click();
  await page.getByRole('tab',{name:'Methods',exact:true}).click();await page.getByRole('button',{name:'Add method step',exact:true}).click();await dialog.getByLabel('Step title',{exact:true}).fill('Interpret the response');await dialog.getByRole('checkbox',{name:'Estimate the response',exact:true}).check();await dialog.getByRole('button',{name:'Apply step',exact:true}).click();
  await page.getByRole('button',{name:'Step 1 actions',exact:true}).click();await page.getByRole('button',{name:'Remove step 1',exact:true}).click();await page.getByRole('button',{name:'Remove this step',exact:true}).click();await page.getByRole('dialog',{name:'Remove method step',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await page.getByRole('dialog',{name:'Step 1 actions',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Another step depends');
  await page.getByRole('button',{name:'Step 2 actions',exact:true}).click();await page.getByRole('button',{name:'Move step 2 up',exact:true}).click();await page.getByRole('dialog',{name:'Step 1 actions',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toContainText('Interpret the response');
  await page.getByRole('button',{name:'Step 1 actions',exact:true}).click();await page.getByRole('button',{name:'Remove step 1',exact:true}).click();await page.getByRole('button',{name:'Remove this step',exact:true}).click();await expect(page.getByRole('button',{name:'Select step 2',exact:true})).toHaveCount(0);await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('tab',{name:'Cases & results',exact:true}).click();await page.getByRole('button',{name:'Add intended case',exact:true}).click();await caseDialog.getByLabel('Case title',{exact:true}).fill('Alternative conditions');await caseDialog.getByRole('button',{name:'Apply case',exact:true}).click();await page.getByRole('button',{name:'More actions for case 2',exact:true}).click();await page.getByRole('button',{name:'Move case 2 up',exact:true}).click();await page.getByRole('dialog',{name:'Case 1 actions',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await page.getByRole('button',{name:'Edit case 1',exact:true}).click();await caseDialog.getByLabel('Case question',{exact:true}).fill('Which operating condition distinguishes the response?');await caseDialog.getByRole('button',{name:'Apply case',exact:true}).click();await page.getByRole('button',{name:'More actions for case 1',exact:true}).click();await page.getByRole('button',{name:'Remove case 1',exact:true}).click();await page.getByRole('button',{name:'Remove this case',exact:true}).click();await expect(page.getByRole('heading',{name:'Alternative conditions',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save approach version',exact:true}).click();await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();
  await page.getByRole('tab',{name:'Methods',exact:true}).click();await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toBeVisible();await page.getByRole('tab',{name:'Cases & results',exact:true}).click();await expect(page.getByRole('region',{name:'Approach usage',exact:true}).getByRole('article',{name:'Nominal conditions',exact:true})).toContainText('What is the nominal response?');
  await expect(page.getByRole('button',{name:'Add method step',exact:true})).toHaveCount(0);
});

test('@approach-method exact repeated-instance references and parallel connections select all matching steps',async({page,browser,baseURL})=>{
  await openProduct(page);await writeQuestion(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  // Independent authenticated context leaves the product session/CSRF unchanged.
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  const model=await helper.evaluate(async sid=>{const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const pkg=await(await fetch('/fixture/model-package')).json();await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:pkg},'model',sid);return pkg.revisions[0];},sid);
  await context.close();
  for(const title of ['Predict the response','Review the response']){
    await page.getByRole('tab',{name:'Methods',exact:true}).click();await page.getByRole('button',{name:'Add method step',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Method step',exact:true});
    await dialog.getByLabel('Step title',{exact:true}).fill(title);await dialog.getByLabel('Purpose',{exact:true}).fill('Connect the explicit operating condition to the declared response.');await dialog.getByLabel('Why this method',{exact:true}).fill('Use the same exact component instance for two distinct scientific steps.');
    await dialog.getByLabel('Implementation status',{exact:true}).selectOption('linked');await dialog.getByLabel('Implementation model',{exact:true}).selectOption(model.model_id);await dialog.getByLabel('Implementation model version',{exact:true}).selectOption(model.model_revision_id);
    await dialog.getByRole('checkbox',{name:'Response · instance 1 · u · output · Dimensionless',exact:true}).check();
    await dialog.getByRole('checkbox',{name:'Response · instance 1 · u · Dimensionless → Response · instance 2 · x · Dimensionless',exact:true}).check();
    if(title==='Review the response'){await dialog.getByLabel('Implementation status',{exact:true}).selectOption('partial');await dialog.getByLabel('Remaining implementation work',{exact:true}).fill('Compare the response with supporting measurements.');}
    await dialog.getByRole('button',{name:'Apply step',exact:true}).click();
  }
  await page.getByRole('button',{name:'Select step 1',exact:true}).click();
  // Every approach tab panel is named by its tab. The step has two tabs; its model opens in the canonical view.
  await expect(page.getByRole('tabpanel',{name:'Methods',exact:true})).toBeVisible();const detail=page.getByRole('region',{name:'Selected method step',exact:true});
  await expect(detail.getByRole('tab')).toHaveText(['Explanation','Assumptions & evidence']);await expect(detail.getByRole('tabpanel',{name:'Explanation',exact:true})).toBeVisible();
  await detail.getByRole('button',{name:'Open model version',exact:true}).click();const open=page.getByRole('dialog',{name:'Model version '+model.model_revision_id.slice(0,8),exact:true});
  // The step's exact port reference highlights exactly one port in the read-only model view.
  const highlighted=open.locator('.hf-node__port[aria-pressed="true"]');await expect(highlighted).toHaveCount(1);await expect(highlighted).toHaveAttribute('title',/^u · /);
  const graph=open.getByLabel('Directed graph',{exact:true});await graph.getByRole('button',{name:/Exchange 2 links/}).click();await expect(open.getByRole('status').filter({hasText:'2 method steps reference'})).toBeVisible();
  await expect(open.getByText('Connections · 2',{exact:true})).toBeVisible();await open.getByRole('button',{name:'Connection 2: v → z',exact:true}).click();await expect(open.getByRole('status').filter({hasText:'0 method steps reference'})).toHaveCount(1);
  // The component's source opens read-only from View source in the same view.
  await open.getByRole('button',{name:'1 Response',exact:true}).click();await open.getByRole('button',{name:'View source',exact:true}).click();const componentSource=page.getByRole('dialog',{name:/^Source · Response/});await expect(componentSource.getByLabel('Read-only authored source').filter({hasText:"outputs['u'] = inputs['x'] + inputs['z']"})).toBeVisible();await componentSource.getByRole('button',{name:'Done',exact:true}).click();await open.getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  // Port and connection references resolve to their exact endpoints only: one input, one output.
  await page.getByRole('button',{name:'Select step 1',exact:true}).click();
  await expect(detail).toContainText('Implemented in Model version '+model.model_revision_id.slice(0,8)+' · 1 input · 1 output');
  await expect(detail.getByRole('region',{name:'Referenced inputs',exact:true})).toHaveCount(0);await expect(detail.getByRole('tab',{name:'Model & quantities',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Select step 2',exact:true}).click();await expect(detail).toContainText('Partially linked');await expect(detail).toContainText('Compare the response with supporting measurements.');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'polish-method-partial-'+theme);}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  await readingShot(page,'approach-method-light');await page.evaluate(()=>document.documentElement.dataset.theme='dark');await readingShot(page,'approach-method-dark');
});

async function openEarlier(page:Page){await page.getByRole('button',{name:'Approach actions',exact:true}).click();await page.getByRole('button',{name:'Earlier work',exact:true}).click();}
async function closeEarlier(page:Page){await page.getByRole('dialog',{name:'Earlier work',exact:true}).getByRole('button',{name:'Done',exact:true}).last().click();await page.getByRole('dialog',{name:'Approach actions',exact:true}).getByRole('button',{name:'Done',exact:true}).last().click();}

test('@approach-method prior configuration and failed run rationale are exact retained basis',async({page,browser,baseURL})=>{
  await openProduct(page);await writeQuestion(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  const data=await helper.evaluate(async sid=>{
    const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const test=await(await fetch('/fixture/failure-package')).json();
    await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:test.package},'model',sid);
    const study=await api.study(sid),c=test.configuration,m=test.package.revisions[0];
    const configuration={schema_version:'3',study_id:sid,model_id:m.model_id,model_revision_id:m.model_revision_id,name:'Earlier screening',inputs:c.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),criteria:[],numerical:c.numerical,context_source:{kind:'current_study',expected_study_revision:study.revision},notes:['Earlier screening context'],derivation:null,assumptions:[],general_context_evidence_version_ids:[]};
    const preview=await api.previewConfiguration3(configuration);const saved=await api.commitConfiguration3({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:preview.candidate_digest});
    const run=await api.submitRun(sid,saved.configuration.configuration_revision_id);
    const handed=await fetch('/fixture/retain-failure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:test.key,study_id:sid,run_id:run.run_id})});if(!handed.ok)throw new Error(await handed.text());
    return {configuration:saved.configuration,run:await api.run(sid,run.run_id)};
  },sid);await context.close();expect(data.run.state).toBe('recorded');expect(data.run.history.results).toBeNull();
  await openEarlier(page);
  for(const [kind,id] of [['configuration',data.configuration.configuration_revision_id],['run',data.run.run_id]]){
    await page.getByRole('button',{name:'Add earlier work',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Earlier work',exact:true});await dialog.getByLabel('Earlier record',{exact:true}).selectOption(kind+'/'+id);await dialog.getByLabel('Basis relation',{exact:true}).selectOption('challenges');await dialog.getByLabel('Basis reason',{exact:true}).fill(kind==='run'?'The failed screening motivated a revised method.':'These explicit inputs define the earlier scientific comparison.');await dialog.getByRole('button',{name:'Apply basis',exact:true}).click();
  }
  await closeEarlier(page);await page.getByRole('button',{name:'Review approach changes',exact:true}).click();await expect(page.getByRole('heading',{name:'Approach changes',exact:true})).toBeVisible();await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await expect(page.getByRole('button',{name:'Save draft',exact:true})).toBeDisabled();await page.getByRole('button',{name:'Load linked records',exact:true}).click();await openEarlier(page);await page.getByRole('button',{name:'View earlier work',exact:true}).nth(1).click();const cleanRecord=page.getByRole('dialog',{name:'Earlier work record',exact:true});await expect(cleanRecord).toContainText('Earlier screening context');await cleanRecord.getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Edit earlier work 2',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Earlier work',exact:true});await dialog.getByLabel('Basis reason',{exact:true}).fill('The recorded failure challenges the original interpretation.');await dialog.getByRole('button',{name:'Apply basis',exact:true}).click();await closeEarlier(page);await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save approach version',exact:true}).click();await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();
  await openEarlier(page);await page.getByRole('button',{name:'View earlier work',exact:true}).nth(1).click();const record=page.getByRole('dialog',{name:'Earlier work record',exact:true});await expect(record).toContainText('Earlier screening');await expect(record).toContainText('Results unavailable');await expect(record).toContainText('Earlier screening context');await readingShot(page,'approach-prior-failure');await record.getByRole('button',{name:'Done',exact:true}).click();
  await closeEarlier(page);await page.getByRole('button',{name:'Edit approach',exact:true}).click();await openEarlier(page);await page.getByRole('button',{name:'Remove earlier work 1',exact:true}).click();await page.getByRole('dialog',{name:'Remove earlier work',exact:true}).getByRole('button',{name:'Remove this basis',exact:true}).click();await expect(page.getByRole('button',{name:'Remove earlier work 2',exact:true})).toHaveCount(0);await closeEarlier(page);await page.getByRole('button',{name:'Review approach changes',exact:true}).click();await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content.basis_refs).toHaveLength(1);
});

for(const dependent of ['case','assumption'])test(`@approach-method protects last implementation reference used by ${dependent}`,async({page,browser,baseURL})=>{
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  const original=await helper.evaluate(async({sid,dependent})=>{
    const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');
    const pkg=await(await fetch('/fixture/model-package')).json(),m=pkg.revisions[0];
    await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:pkg},'model',sid);
    const c=(window as any).approachHarness.controller;await c.open(sid);const content=structuredClone(c.getSnapshot().local),binding={binding_id:crypto.randomUUID(),model_id:m.model_id,model_revision_id:m.model_revision_id};
    const step={step_id:crypto.randomUUID(),title:'Implemented method',purpose:'Purpose retained',rationale:'Reason retained',remaining_work:'',intent:{transformation:'Scalar response',inputs:'Operating quantities',outputs:'Response',depends_on_step_ids:[]},implementation_state:'linked',implementation_refs:[{kind:'model',binding_id:binding.binding_id}],assumption_refs:[],evidence_links:[]};
    content.question='Explain the response';content.model_bindings=[binding];content.steps=[step];
    if(dependent==='case')content.cases=[{case_id:crypto.randomUUID(),title:'Nominal case',question:'Nominal response?',rationale:'Baseline comparison',binding_id:binding.binding_id,evidence_links:[]}];
    else content.steps.push({...step,step_id:crypto.randomUUID(),title:'Interpret the response',implementation_state:'proposed',implementation_refs:[],assumption_refs:[{kind:'model',binding_id:binding.binding_id,assumption_id:m.assumptions[0].assumption_id,origin:null}]});
    const bad=structuredClone(content);bad.steps[0].implementation_refs=[{kind:'instance',binding_id:binding.binding_id,instance_id:crypto.randomUUID()}];
    const badPreview=await api.previewApproach(sid,{schema_version:bad.schema_version,expected_revision:null,content:bad});if(!badPreview.issues.length)throw new Error('Unknown exact instance was accepted');
    const other=await api.createStudy('Unrelated study');let rejected=false;try{await api.previewApproach(other.study_id,{schema_version:content.schema_version,expected_revision:null,content});}catch{rejected=true;}if(!rejected)throw new Error('Foreign-study model reference was accepted');
    c.edit(content);if(!await c.save())throw new Error(c.getSnapshot().error);return c.getSnapshot().server.draft.content;
  },{sid,dependent});await context.close();
  await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toContainText('Implemented method');
  // Edit only after the current draft read has settled (run 08 lost an edit made before it).
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Edit step 1',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Method step',exact:true});
  await dialog.getByLabel('Purpose',{exact:true}).fill('Keep this unsaved explanation');await dialog.getByRole('button',{name:'Remove reference 1',exact:true}).click();
  await expect(dialog.getByRole('alert')).toContainText(dependent==='case'?'An intended case uses':'references an assumption');
  await expect(dialog.getByRole('button',{name:'Remove reference 1',exact:true})).toBeVisible();await expect(dialog.getByLabel('Purpose',{exact:true})).toHaveValue('Keep this unsaved explanation');
  await dialog.getByRole('button',{name:'Apply step',exact:true}).click();await page.getByRole('button',{name:'Step 1 actions',exact:true}).click();await page.getByRole('button',{name:'Remove step 1',exact:true}).click();const removal=page.getByRole('dialog',{name:'Remove method step',exact:true});await removal.getByRole('button',{name:'Remove this step',exact:true}).click();await removal.getByRole('button',{name:'Done',exact:true}).click();await page.getByRole('dialog',{name:'Step 1 actions',exact:true}).getByRole('button',{name:'Done',exact:true}).click();await expect(page.getByRole('alert')).toContainText(dependent==='case'?'An intended case uses':'references an assumption');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  const saved=(await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content;
  expect(saved.model_bindings).toEqual(original.model_bindings);expect(saved.cases).toEqual(original.cases);expect(saved.steps.map((s:any)=>s.assumption_refs)).toEqual(original.steps.map((s:any)=>s.assumption_refs));expect(saved.steps[0].purpose).toBe('Keep this unsaved explanation');
});

test('@approach-reading actual Overview entry, question editing, version restore and immutable reads',async({page})=>{
  await openProduct(page);await writeQuestion(page);
  const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study');
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft).toBeNull();
  await readingShot(page,'approach-draft-light');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save approach version',exact:true}).click();
  await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();
  await expect(page.getByLabel('Approach version',{exact:true})).toContainText('v1 (read-only)');
  const original=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions`)).json()).data.items[0];
  const saved=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${original.approach_version_id}`)).json()).data;
  await expect(page.getByRole('button',{name:'Edit question and scope',exact:true})).toHaveCount(0);
  await readingShot(page,'approach-version-light');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');await readingShot(page,'approach-version-dark');
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await writeQuestion(page,'A later explanation');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await page.getByLabel('Approach version',{exact:true}).selectOption(original.approach_version_id);
  await expect(page.getByLabel('The modeling approach').getByRole('heading',{name:saved.version.content.question,exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Approach actions',exact:true}).click();await page.getByRole('button',{name:'Use this version in draft',exact:true}).click();
  await page.getByRole('dialog',{name:'Use this version in draft',exact:true}).getByRole('button',{name:'Restore draft',exact:true}).click();
  await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content).toEqual(saved.version.content);
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${original.approach_version_id}`)).json()).data).toEqual(saved);
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();
  await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toBeFocused();
});

test('@approach-reading dirty navigation and uncertain draft remain recoverable in the product',async({page})=>{
  const studyName=await openProduct(page);await writeQuestion(page,'Keep these local changes');
  await page.getByRole('button',{name:'Home',exact:true}).click();
  const dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true});await expect(dirty).toBeVisible();
  await dirty.getByRole('button',{name:'Keep editing',exact:true}).click();
  await expect(page.getByLabel('The modeling approach').getByRole('heading',{name:'Keep these local changes',exact:true})).toBeVisible();
  await page.route('**/approach/draft',async route=>{await route.fetch();await route.abort();},{times:1});
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByRole('button',{name:'Check original command',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Home',exact:true}).click();
  await expect(page.getByLabel('The modeling approach').getByRole('heading',{name:'Keep these local changes',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Check original command',exact:true}).click();
  await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await writeQuestion(page,'Discard this proposal');await page.getByRole('button',{name:'Home',exact:true}).click();
  await dirty.getByRole('button',{name:'Discard changes',exact:true}).click();await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Open study '+studyName,exact:true}).first().click();await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
  await expect(page.getByLabel('The modeling approach').getByRole('heading',{name:'Keep these local changes',exact:true})).toBeVisible();
});

test('@approach-reading historical retry keeps the exact selected version during an outage',async({page})=>{
  await openProduct(page);await writeQuestion(page,'Original interpretation');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save approach version',exact:true}).click();
  await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();
  const select=page.getByLabel('Approach version',{exact:true});await expect(select).toContainText('v1 (read-only)');
  const version=await select.inputValue();
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await writeQuestion(page,'Today’s changed explanation');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.route('**/approach/versions/'+version,route=>route.abort(),{times:1});
  await select.selectOption(version);await expect(page.getByRole('button',{name:'Retry this version',exact:true})).toBeVisible();
  expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('approach')).toBe(version);
  await page.getByRole('button',{name:'Retry this version',exact:true}).click();
  await expect(page.getByLabel('The modeling approach')).toContainText('Original interpretation');
  await expect(page.getByLabel('The modeling approach')).not.toContainText('Today’s changed explanation');
  await expect(select).toHaveValue(version);
  await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByLabel('The modeling approach')).toContainText('Original interpretation');await expect(select).toHaveValue(version);
});

test('@approach-reading stale draft compares explanation fields before explicit reapplication',async({page,browser,baseURL})=>{
  await openProduct(page);await writeQuestion(page,'Initial method');await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study');await writeQuestion(page,'My local method');
  const other=await browser.newContext({baseURL});
  try{
    const otherPage=await other.newPage();await otherPage.goto('/ui/');
    const content=await otherPage.evaluate(async sid=>{const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const draft=(await api.approach(sid)).draft;const content={...draft.content,question:'Another engineer’s method',scope:'A changed scientific scope',limitations:'A new limitation',open_questions:'An unresolved alternative'};const body={schema_version:content.schema_version,expected_revision:draft.revision,content};const preview=await api.previewApproach(sid,body);await api.saveApproachDraft(sid,{...body,command_id:crypto.randomUUID(),expected_preview_digest:preview.preview_digest});return content;},sid);
    await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.getByRole('button',{name:'Review latest draft',exact:true}).click();
    const review=page.getByLabel('Review latest draft',{exact:true});await expect(review).toContainText('My local method');await expect(review).toContainText(content.scope);await expect(review).toContainText(content.limitations);await expect(review).toContainText(content.open_questions);
    await readingShot(page,'approach-stale-review');await review.getByRole('button',{name:'Reapply my changes',exact:true}).click();await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
    expect((await(await page.request.get(`/api/1/studies/${sid}/approach`)).json()).data.draft.content.question).toBe('My local method');
  }finally{await other.close();}
});

test('@approach-reading session loss preserves original pending command recovery after reauthentication',async({page})=>{
  await openProduct(page);await writeQuestion(page,'A command retained across reauthentication');
  let original:any;await page.route('**/approach/draft',async route=>{original=route.request().postDataJSON();await route.abort();},{times:1});
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  const check=page.getByRole('button',{name:'Check original command',exact:true});await expect(check).toBeVisible();
  await page.route('**/commands/*?category=approach_draft',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({error:{code:'unauthorized',message:'Session expired',fields:[],outcome:'unchanged'}})}),{times:1});
  await check.click();await expect(page.getByRole('heading',{name:'Sign in to HYPRN MVP',exact:true})).toBeVisible();
  await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(check).toBeVisible();await check.click();
  let retry:any;page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith('/approach/draft'))retry=request.postDataJSON();});
  await page.getByRole('button',{name:'Retry original command',exact:true}).click();await expect(check).toHaveCount(0);
  expect(retry).toEqual(original);
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
  await expect(page.getByLabel('The modeling approach')).toContainText(original.content.question);
});

test('@approach-reading @approach-method @approach-assumptions genuine 200 percent zoom, keyboard editing and theme geometry',async({baseURL,browser})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/approach-zoom-extension');await mkdir(extension);
  await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Approach zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/approach-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});
  const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try{
    const page=context.pages()[0]??await context.newPage();await openProduct(page);await writeQuestion(page);
    const packageResponse=await page.request.get('/fixture/model-package');
    if(packageResponse.ok()){
      await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
      const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!,other=await browser.newContext({baseURL}),helper=await other.newPage();await helper.goto('/ui/');
      await helper.evaluate(async({sid,pkg})=>{const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:pkg},'model',sid);await c.open(sid);const content=structuredClone(c.getSnapshot().local),m=pkg.revisions[0],binding={binding_id:crypto.randomUUID(),model_id:m.model_id,model_revision_id:m.model_revision_id};content.model_bindings=[binding];content.steps=[{step_id:crypto.randomUUID(),title:'Predict response from operating conditions',purpose:'Connect the imposed quantities to the predicted response.',rationale:'An explicit scalar approximation supports the initial screening.',intent:{transformation:'Combine the two operating quantities using the authored response law.',inputs:'Operating quantities x and z',outputs:'Predicted response u',depends_on_step_ids:[]},implementation_state:'partial',remaining_work:'Compare the declared relationship with supporting measurements.',implementation_refs:[{kind:'port',binding_id:binding.binding_id,instance_id:m.instances[1].instance_id,port_id:m.definitions[1].ports[2].port_id},{kind:'connection',binding_id:binding.binding_id,connection_id:m.connections[0].connection_id}],assumption_refs:[],evidence_links:[]}];content.cases=[{case_id:crypto.randomUUID(),title:'Nominal operating conditions',question:'Does the response remain within the intended operating envelope?',rationale:'Compare one explicit configuration with the initial screening.',binding_id:binding.binding_id,evidence_links:[]}];const evidence=await api.createEvidence(sid,{evidence_schema_version:'3',kind:'note',title:'Operating range measurements',content:'The scalar approximation is supported only within the measured range.',source_refs:[],resource_scope:{scope_version:'1',kind:'study',study_id:sid}});content.assumptions=[{assumption_id:crypto.randomUUID(),statement:'A scalar approximation describes the measured range.',role:'overall_method',evidence_links:[{evidence_version_id:evidence.evidence_version_id,relation:'supports',locator:'Table 2 · Operating range'}]}];content.steps[0].assumption_refs=[{kind:'approach',assumption_id:content.assumptions[0].assumption_id}];content.cases[0].evidence_links=[{evidence_version_id:evidence.evidence_version_id,relation:'context',locator:'Nominal measurement'}];c.edit(content);if(!await c.save())throw new Error(c.getSnapshot().error);},{sid,pkg:await packageResponse.json()});await other.close();
      await page.getByRole('button',{name:'Back to overview',exact:true}).click();await page.getByRole('button',{name:'View modeling approach',exact:true}).click();await page.getByRole('button',{name:'Edit approach',exact:true}).click();await page.getByRole('button',{name:'Select step 1',exact:true}).click();
      await readingShot(page,'approach-populated-light');await page.evaluate(()=>document.documentElement.dataset.theme='dark');await readingShot(page,'approach-populated-dark');
    }
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});
    const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);
    await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));const bounds=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width+1);geometry.push({name,...bounds});const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));}
    for(const theme of ['light','dark']){
      await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.evaluate(()=>scrollTo(0,0));await capture('approach-200-'+theme);
      await page.getByRole('region',{name:'The modeling approach',exact:true}).locator('.approach-question').evaluate(element=>element.scrollIntoView({block:'start'}));await capture('approach-content-200-'+theme);
      // One Study details dialog (question, context, assumptions, limits) replaces Question in detail and Study conditions & limits.
      await page.getByRole('button',{name:'See more details',exact:true}).click();await capture('polish-question-detail-200-'+theme);await page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('region',{name:'Study limits',exact:true}).scrollIntoViewIfNeeded();await capture('polish-conditions-200-'+theme);await page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('button',{name:'Done',exact:true}).click();

      if(packageResponse.ok()){await page.locator('.method-implemented').scrollIntoViewIfNeeded();await capture('approach-method-200-'+theme);await page.getByRole('tab',{name:'Cases & results',exact:true}).click();await page.locator('.approach-case').scrollIntoViewIfNeeded();await capture('approach-case-200-'+theme);await page.getByRole('tab',{name:'Methods',exact:true}).click();await page.getByRole('button',{name:'See more details',exact:true}).click();await page.getByRole('region',{name:'Modeling approach assumptions',exact:true}).scrollIntoViewIfNeeded();await capture('approach-assumptions-200-'+theme);const add=page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('button',{name:'Add assumption',exact:true});await add.focus();await add.press('Enter');const assumption=page.getByRole('dialog',{name:'Approach assumption',exact:true});await expect(assumption.getByLabel('Assumption statement',{exact:true})).toBeFocused();await capture('approach-assumption-editor-200-'+theme);await page.keyboard.press('Escape');await expect(add).toBeFocused();await page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('button',{name:'Done',exact:true}).click();}
      await page.getByRole('tablist',{name:'Approach sections'}).scrollIntoViewIfNeeded();await capture('approach-sidebar-200-'+theme);
      const edit=page.getByRole('button',{name:'Edit question and scope',exact:true});await edit.focus();await edit.press('Enter');
      const dialog=page.getByRole('dialog',{name:'Edit question and scope',exact:true}),question=dialog.getByLabel('Engineering question',{exact:true});await expect(question).toBeFocused();await question.fill('Temporary edit at native zoom');
      await question.press('Shift+Tab');await expect(dialog.getByRole('button',{name:'Cancel',exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(question).toBeFocused();await capture('approach-edit-200-'+theme);
      await page.keyboard.press('Escape');await expect(edit).toBeFocused();await expect(page.getByLabel('The modeling approach')).not.toContainText('Temporary edit at native zoom');
      const chapter=page.getByRole('tab',{name:'Methods',exact:true});await chapter.focus();await chapter.press('Enter');await expect(chapter).toHaveAttribute('aria-selected','true');await expect(chapter).toBeFocused();
    }
    await writeFile(join(root,'evidence/approach-native-zoom.json'),JSON.stringify({zoom:2,viewport:null,geometry},null,2));
    if(packageResponse.ok()){
      await page.getByRole('button',{name:'Save approach version',exact:true}).click();await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();await expect(page.getByRole('button',{name:'Add method step',exact:true})).toHaveCount(0);
      const exactUrl=page.url();await page.request.post('/fixture/model-outage');await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(exactUrl);await page.getByRole('button',{name:'Select step 1',exact:true}).click();await expect(page.getByRole('region',{name:'Selected method step'})).toContainText('Partially linked');await expect(page.getByRole('region',{name:'Selected method step'}).getByRole('heading',{name:'Remaining work',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'Selected method step'}).getByText('Compare the declared relationship with supporting measurements.',{exact:true})).toBeVisible();await readingShot(page,'approach-retained-model-outage');
    }
  }finally{await context.close();}
});


test('@approach-history normal new configuration uses nullable approach protocol without opening picker',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL);
  await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'configurations'}).toString();},data.sid);
  await page.getByRole('button',{name:'New configuration',exact:true}).click();
  await page.getByRole('button',{name:/^Use /}).click();
  await fillCaseConfiguration(page,'Independent screening');
  const saved=await saveCaseConfiguration(page);
  expect(saved.configuration.schema_version).toBe('4');
  expect(saved.configuration.approach_binding).toBeNull();
  expect(saved.approach_closure).toBeNull();
});


async function retainedApproach(page:Page,browser:any,baseURL:string|undefined){
  await page.request.post('/fixture/model-available');
  const data=await seededConditions(page,browser,baseURL,{failure:true});
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Prior screening');const original=await saveCaseConfiguration(page);
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const retained=await helper.evaluate(async({data,original})=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');const sid=data.sid;
    async function retain(configuration:any,complete=true){const r=await api.submitRun(sid,configuration.configuration_revision_id),response=await fetch(complete?'/fixture/retain-failed-outcome':'/fixture/retain-failure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({study_id:sid,run_id:r.run_id,key:data.fixture.key})});if(!response.ok)throw new Error(await response.text());return api.run(sid,r.run_id);}
    const prior=await retain(original.configuration);await c.open(sid);c.edit({...c.getSnapshot().local,question:'Explain the screening after the prior failure',basis_refs:[{kind:'run',run_id:prior.run_id,relation:'challenges',reason:'The prior failure exposes a limitation; it is not a numerical input.'}]});if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);const saved=c.getSnapshot().saved,o=original.configuration;
    async function config(name:string,selection:any,legacy=false){const configuration:any={schema_version:legacy?'3':'4',study_id:sid,model_id:o.model_id,model_revision_id:o.model_revision_id,name,inputs:o.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),criteria:o.criteria,numerical:o.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(sid)).revision},context_override:{schema_version:'1',description:'Interpretation retained for the screening.',boundary:''},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[]};if(!legacy)configuration.approach_selection=selection;const p=legacy?await api.previewConfiguration3(configuration):await api.previewConfiguration4(configuration),body={command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:p.candidate_digest};return (legacy?await api.commitConfiguration3(body):await api.commitConfiguration4(body)).configuration;}
    const selected=await config('Retained screening',{approach_version_id:saved.version.approach_version_id,case_id:saved.version.content.cases[0].case_id}),run=await retain(selected),partial=await retain(selected,false),legacy=await retain(await config('Earlier configuration without approach',null,true)),queued=await api.submitRun(sid,selected.configuration_revision_id);
    const uncertain=await api.submitRun(sid,selected.configuration_revision_id);const uncertainResponse=await fetch('/fixture/retain-uncertain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({study_id:sid,run_id:uncertain.run_id,key:data.fixture.key})});if(!uncertainResponse.ok)throw new Error(await uncertainResponse.text());
    await c.open(sid);c.edit({...c.getSnapshot().local,question:'Later interpretation must never replace retained history'});if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);
    const family=await api.evidenceFamily(sid,data.evidence.evidence_id);await api.reviseEvidence(sid,data.evidence.evidence_id,{command_id:crypto.randomUUID(),expected_revision:family.head_evidence_version_id,evidence_schema_version:'3',kind:'note',title:'Later measurements',content:'Later evidence must never replace retained history.',source_refs:[],resource_scope:data.evidence.resource_scope});
    const draft=await api.model(sid,data.model.model_id);await api.apply(draft,[{kind:'add_assumption',temp_key:'later',owner:{kind:'model'},statement:'A later model assumption.',evidence_links:[]}]);
    return {run,prior,partial,legacy,queued,uncertain,saved};
  },{data,original});await ctx.close();return {...data,...retained};
}
async function openRetainedRun(page:Page,sid:string,rid:string){await page.evaluate(({sid,rid})=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'runs',run:rid}).toString();},{sid,rid});await expect(page.getByRole('tab',{name:'Configuration',exact:true})).toBeVisible();}

test('@approach-history bounded failure diagnostic is readable beside truthful results', async ({ page, browser, baseURL }) => {
  const d = await retainedApproach(page, browser, baseURL);
  const diagnostic = `AssertionError: Required pressure closure not reached [source sources/${'a'.repeat(64)}.py:2; instance ${d.run.history.model_snapshot.instances[0].instance_id}; definition ${d.run.history.model_snapshot.instances[0].definition_version_id}]`;
  // Presentation fixture only; actual native-origin diagnostics are verified separately.
  await page.route(`**/api/1/studies/${d.sid}/runs/${d.run.run_id}`, async route => {
    const response = await route.fetch(), value = await response.json();
    value.data.history.results.execution.message = diagnostic;
    await route.fulfill({ response, json: value });
  });
  await openRetainedRun(page, d.sid, d.run.run_id);
  const panel = page.getByRole('region', { name: 'Execution diagnostic', exact: true });
  await expect(panel).toHaveText(/Required pressure closure not reached/);
  await expect(panel).toContainText('sources/' + 'a'.repeat(64) + '.py:2');
  await expect(page.getByRole('region', { name: 'Output values', exact: true })).toContainText('not computed');
  const bounds = await panel.boundingBox(); expect(bounds!.width).toBeGreaterThan(600);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  for (const theme of ['light', 'dark']) { await page.evaluate(t => document.documentElement.dataset.theme = t, theme); await readingShot(page, 'bounded-run-diagnostic-' + theme); }
  // Execution and Criteria only, never merged; removed facets, notes and ids stay absent.
  expect(d.run.history.results.criteria).toEqual([]);
  await expectRunHeadline(page, 'Failed', 'None defined');
  await expectRunCleanup(page, d.run.run_id);
  await s1Shots(page, browser, baseURL, d.sid, d.run.run_id, 's1-run-failed');
});

/** Run headline: exactly Execution then Criteria, each with its own tag. */
async function expectRunHeadline(page: Page, execution: string, criteria: string) {
  const ledger = page.getByRole('list', { name: 'Run status', exact: true });
  await expect(ledger.locator('.hf-facet__k')).toHaveText(['Execution', 'Criteria']);
  await expect(ledger.locator('.hf-facet__v')).toHaveText([execution, criteria]);
  await expect(ledger.locator('.hf-tag')).toHaveCount(2);
}
/** Run page cleanup: no constant facets, display note, readout id or study conditions; ids only in Record details. */
async function expectRunCleanup(page: Page, rid: string, pinned = true) {
  const details = page.getByRole('region', { name: 'Run details', exact: true });
  for (const removed of ['Convergence', 'Termination', 'Feasibility', 'Sample completeness', 'Output completeness', 'Applicability', 'Not assessed', 'Display: up to 3 decimals', 'Full-precision values and exports retain full precision', 'Deterministic scalar calculation', 'Assessment evaluator'])
    await expect(details).not.toContainText(removed);
  await expect(details.locator('.run-key-outputs .hf-readout__basis')).toHaveCount(0);
  await expect(details.locator('.hf-record')).toContainText('Run record · Read-only');
  await expect(details.locator('.hf-record')).not.toContainText(rid);
  await expect(details.locator('.run-heading .context-line').first()).toHaveText(new RegExp('^Run ' + rid.slice(0, 8) + '( · Case: .*)?$'));
  await expect(page.getByRole('button', { name: 'Study conditions & limits', exact: true })).toHaveCount(0);
  const action = details.locator('.run-heading').getByRole('button', { name: 'Record details', exact: true });
  await action.click();
  const record = page.getByRole('dialog', { name: 'Run record', exact: true });
  await expect(record).toContainText(rid); await expect(record).toContainText('Criterion evaluator');
  await page.keyboard.press('Escape'); await expect(action).toBeFocused();
  await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
  const configuration = page.getByRole('tabpanel', { name: 'Configuration', exact: true });
  if (pinned) await expect(configuration.getByRole('button', { name: 'View modeling approach', exact: true })).toBeVisible();
  else await expect(configuration).toContainText('No modeling approach is linked.');
  await configuration.getByRole('button', { name: 'Record details', exact: true }).click();
  const configurationRecord = page.getByRole('dialog', { name: 'Configuration record', exact: true });
  await expect(configurationRecord.locator('dt')).toHaveText(['Configuration version', 'Model version']);
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: 'Results', exact: true }).click();
}
/** Light and dark at 1440 x 1000, then 200 percent (720 CSS px at device scale 2, the layout of genuine 200 percent zoom). */
async function s1Shots(page: Page, browser: any, baseURL: string | undefined, sid: string, rid: string, name: string) {
  for (const theme of ['light', 'dark']) { await page.evaluate(t => document.documentElement.dataset.theme = t, theme); await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!, 'evidence', name + '-1440-' + theme + '.png'), animations: 'disabled' }); await readingShot(page, name + '-1440-full-' + theme); }
  await page.evaluate(() => { delete document.documentElement.dataset.theme; });
  const context = await browser.newContext({ baseURL, viewport: { width: 720, height: 500 }, deviceScaleFactor: 2 }), zoomed = await context.newPage();
  try {
    await zoomed.goto('/ui/?workspace#' + new URLSearchParams({ v: '1', study: sid, view: 'runs', run: rid }));
    await zoomed.getByLabel('Username', { exact: true }).fill('owner'); await zoomed.getByLabel('Password', { exact: true }).fill('correct horse battery staple'); await zoomed.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(zoomed.getByRole('list', { name: 'Run status', exact: true }).locator('.hf-facet__k')).toHaveText(['Execution', 'Criteria']);
    for (const theme of ['light', 'dark']) {
      await zoomed.evaluate(t => document.documentElement.dataset.theme = t, theme);
      expect(await zoomed.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await zoomed.screenshot({ path: join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!, 'evidence', name + '-200-' + theme + '.png'), fullPage: true, animations: 'disabled' });
    }
  } finally { await context.close(); }
}

test('@approach-history completed runs show Execution and Criteria only, met and not met, with not computed outputs kept', async ({ page, browser, baseURL }) => {
  const d = await nativeFindings(page, browser, baseURL);
  await openRetainedRun(page, d.sid, d.downstream.run_id);
  await expectRunHeadline(page, 'Completed', '2 of 2 met');
  await expectRunCleanup(page, d.downstream.run_id, false);
  await s1Shots(page, browser, baseURL, d.sid, d.downstream.run_id, 's1-run-met');
  await openRetainedRun(page, d.sid, d.source.run_id);
  const violated = d.source.history.results.criteria.filter((c: any) => c.outcome === 'violated').length;
  expect(violated).toBeGreaterThan(0);
  await expectRunHeadline(page, 'Completed', `${violated} of ${d.source.history.results.criteria.length} not met`);
  await expectRunCleanup(page, d.source.run_id, false);
  // Per-criterion outcomes stay with the configuration; the headline never merges them.
  await page.getByRole('tab', { name: 'Configuration', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'Configuration', exact: true }).locator('.hf-criterion').filter({ hasText: 'Not met' })).toHaveCount(violated);
  await page.getByRole('tab', { name: 'Results', exact: true }).click();
  await s1Shots(page, browser, baseURL, d.sid, d.source.run_id, 's1-run-notmet');
  // Overview recent runs reuse the same two outcomes.
  await page.evaluate(sid => { location.hash = new URLSearchParams({ v: '1', study: sid, view: 'overview' }).toString(); }, d.sid);
  // (The five latest runs of this fixture study need not include the two runs above.)
  const recent = page.getByRole('region', { name: 'Recent runs', exact: true }).getByLabel('Run outcomes', { exact: true });
  await expect(recent).toHaveCount(5);
  for (const summary of await recent.all()) { await expect(summary.locator('.hf-tag')).toHaveCount(2); await expect(summary).toContainText('Execution'); await expect(summary).toContainText('Criteria'); await expect(summary).not.toContainText('Applicability'); }
});

test('@approach-history retained interpretation source evidence and prior basis survive later edits and outage',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL);await page.request.post('/fixture/model-outage');const forbidden:string[]=[];
  await page.route('**/api/1/**',async route=>{const path=new URL(route.request().url()).pathname;if(/\/(approach|evidence|evidence-families)(\/|$)/.test(path)||/\/models\/[^/]+(\/|$)/.test(path)){forbidden.push(path);await route.abort();}else await route.continue();});
  await openRetainedRun(page,d.sid,d.run.run_id);await expect(page.getByRole('region',{name:'Output values',exact:true})).toContainText('not computed');await expect(page.getByRole('region',{name:'Output values',exact:true})).not.toContainText('0.000');
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();const trigger=page.getByRole('button',{name:'View modeling approach',exact:true});await trigger.focus();await trigger.press('Enter');const reader=page.getByRole('dialog',{name:'Linked modeling approach',exact:true});await expect(reader).toContainText('Explain the screening after the prior failure');await expect(reader).not.toContainText('Later interpretation');await expect(reader.getByRole('button',{name:'Edit',exact:true})).toHaveCount(0);
  await reader.getByRole('tab',{name:'Assumptions & evidence',exact:true}).click();await reader.getByRole('button',{name:'View evidence',exact:true}).first().click();const evidence=page.getByRole('dialog',{name:'Evidence detail',exact:true});await expect(evidence).toContainText(d.evidence.content);await expect(evidence).not.toContainText('Later evidence');await page.keyboard.press('Escape');
  await reader.getByRole('button',{name:'Earlier work',exact:true}).click();const earlier=page.getByRole('dialog',{name:'Earlier work',exact:true});await expect(earlier).toContainText('The prior failure exposes a limitation; it is not a numerical input.');
  await earlier.getByRole('button',{name:'View earlier work',exact:true}).click();const basis=page.getByRole('dialog',{name:'Earlier work record',exact:true});await expect(basis).toContainText('Prior screening');await expect(basis).toContainText('Failed');await basis.getByRole('button',{name:'View modeling approach',exact:true}).click();await expect(page.getByRole('dialog',{name:'Linked modeling approach',exact:true}).last()).toContainText('Why use the scalar response approximation?');for(let i=0;i<4;i++)await page.keyboard.press('Escape');await expect(trigger).toBeFocused();
  await page.getByRole('tab',{name:'Model',exact:true}).click();await expect(page.getByRole('button',{name:'Save model version',exact:true})).toHaveCount(0);
  await page.getByRole('tab',{name:'Evidence',exact:true}).click();await expect(page.locator('#run-panel-3').getByRole('region',{name:'Configuration assumptions',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'Modeling approach evidence',exact:true})).toContainText('Screening measurements');const source=d.run.history.artifacts.find((a:any)=>a.role==='source');await page.getByLabel('Find a file',{exact:true}).fill(source.name);await page.getByRole('region',{name:'Run files table',exact:true}).getByRole('button',{name:'Preview',exact:true}).click();await expect(page.getByLabel('Read-only run file',{exact:true})).toHaveText(Buffer.from(d.run.history.model_snapshot.source_files.find((s:any)=>s.sha256===source.sha256).bytes,'base64').toString());
  expect(forbidden).toEqual([]);await writeFile(join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/history-outage-proof.json'),JSON.stringify({run:d.run,prior:d.prior,forbidden},null,2));
});

test('@approach-history export scope matches real typed preview status and created portable manifest',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL);await openRetainedRun(page,d.sid,d.run.run_id);await page.getByRole('button',{name:'Export computational record',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Export computational record',exact:true});
  async function process(label:string,path:string){const pending=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes(path));await dialog.getByRole('button',{name:label,exact:true}).click();const request=(await(await pending).json()).data;const response=await page.request.post('/fixture/process-export',{data:{study_id:d.sid,request_id:request.request_id}});expect(response.ok()).toBeTruthy();const proof=await response.json();expect(proof.record.state).toBe(label==='Review record'?'reviewable':'ready');return proof;}
  const preview=await process('Review record','/computational-record-previews');await expect(dialog.getByRole('region',{name:'Included modeling approach',exact:true})).toBeVisible();await expect(dialog).toContainText('Earlier-work runs');await expect(dialog).not.toContainText(d.prior.run_id);const created=await process('Create record export','/computational-records');expect(created.manifest.approach_summary).toEqual(preview.record.preview.approach_summary);expect(created.manifest.approach_summary.basis_run_ids).toEqual([d.prior.run_id]);expect(created.manifest.computational_run_ids).toEqual([d.run.run_id]);await expect(dialog.getByRole('button',{name:'Download record export',exact:true})).toBeEnabled();for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'approach-history-export-'+theme);}
});

test('@approach-history old unlinked and missing terminal results remain coherent and queued is not finished',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL);await openRetainedRun(page,d.sid,d.legacy.run_id);await page.getByRole('tab',{name:'Configuration',exact:true}).click();await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toHaveCount(0);await expect(page.getByRole('region',{name:'Configuration context',exact:true})).toContainText('Interpretation retained');await openRetainedRun(page,d.sid,d.partial.run_id);await expect(page.getByText('No results for this run. Missing values are never shown as zero.',{exact:true})).toBeVisible();await page.getByRole('tab',{name:'Configuration',exact:true}).click();await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toBeVisible();await openRetainedRun(page,d.sid,d.queued.run_id);await expect(page.getByText('Queued for preparation',{exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'Output values',exact:true})).toHaveCount(0);await openRetainedRun(page,d.sid,d.uncertain.run_id);await expect(page.getByText('Submission outcome is uncertain',{exact:true})).toBeVisible();await expect(page.getByText('No results for this run. Missing values are never shown as zero.',{exact:true})).toBeVisible();
});


test('@approach-history retained reader and export genuine 200 percent keyboard and themes',async({baseURL,browser})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/history-zoom-extension');await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'History zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/history-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try{const page=context.pages()[0]??await context.newPage(),d=await retainedApproach(page,browser,baseURL);await openRetainedRun(page,d.sid,d.run.run_id);await page.getByRole('tab',{name:'Configuration',exact:true}).click();
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.getByRole('button',{name:'View modeling approach',exact:true}).click();await readingShot(page,'approach-history-reader-'+theme);await page.keyboard.press('Escape');}
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));const bounds=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width+1);geometry.push({name,...bounds});const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));}
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);const trigger=page.getByRole('button',{name:'View modeling approach',exact:true});await trigger.focus();await trigger.press('Enter');const reader=page.getByRole('dialog',{name:'Linked modeling approach',exact:true});await expect(reader.locator('.approach-question').first()).toHaveText('Explain the screening after the prior failure');const detail=reader.getByRole('button',{name:'See more details',exact:true});await detail.focus();await detail.press('Enter');const question=page.getByRole('dialog',{name:'Study details',exact:true});await expect(question).toContainText('Explain the screening after the prior failure');await page.keyboard.press('Escape');await expect(detail).toBeFocused();await capture('approach-history-reader-200-'+theme);
      const earlier=reader.getByRole('button',{name:'Earlier work',exact:true});await earlier.focus();await earlier.press('Enter');await page.getByRole('dialog',{name:'Earlier work',exact:true}).getByRole('button',{name:'View earlier work',exact:true}).press('Enter');const basis=page.getByRole('dialog',{name:'Earlier work record',exact:true});await basis.getByRole('button',{name:'View modeling approach',exact:true}).press('Enter');const nested=page.getByRole('dialog',{name:'Linked modeling approach',exact:true}).last();const methods=nested.getByRole('tab',{name:'Methods',exact:true});await methods.focus();await methods.press('ArrowRight');const cases=nested.getByRole('tab',{name:'Cases & results',exact:true});await expect(cases).toBeFocused();await expect(cases).toHaveAttribute('aria-selected','true');await expect(nested.getByRole('heading',{name:'Cases and evaluation',exact:true})).toBeVisible();await capture('approach-history-prior-200-'+theme);for(let i=0;i<4;i++)await page.keyboard.press('Escape');await expect(trigger).toBeFocused();}
    await page.getByRole('button',{name:'Export computational record',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Export computational record',exact:true}),response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/computational-record-previews'));await dialog.getByRole('button',{name:'Review record',exact:true}).click();const queued=(await(await response).json()).data;await page.request.post('/fixture/process-export',{data:{study_id:d.sid,request_id:queued.request_id}});await expect(dialog.getByRole('region',{name:'Included modeling approach',exact:true})).toBeVisible();
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await dialog.getByRole('heading',{name:'Modeling approach',exact:true}).evaluate(e=>e.scrollIntoView({block:'center'}));await capture('approach-history-export-200-'+theme);}await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Export computational record',exact:true})).toBeFocused();
    await writeFile(join(root,'evidence/approach-history-zoom-geometry.json'),JSON.stringify({zoom:2,viewport:page.viewportSize(),geometry},null,2));
  }finally{await context.close();}
});

// Findings: real HTTP authoring/retention for coverage; response fault injection is
// explicitly supplementary UI robustness evidence, not numerical execution.
test('@approach-history Findings retains partial pages, exact cases and per-row failures',async({page,browser,baseURL})=>{
  const d=await seededConditions(page,browser,baseURL,{cases:true,failure:true});
  await page.getByLabel('Approach version',{exact:true}).selectOption(d.saved.version.approach_version_id);
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Repeated screening');const original=await saveCaseConfiguration(page);
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const created=await helper.evaluate(async({d,original})=>{
    const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const o=original.configuration,ids=[o.configuration_revision_id];
    for(let i=0;i<11;i++){const configuration={schema_version:'4',study_id:d.sid,model_id:o.model_id,model_revision_id:o.model_revision_id,name:'Repeated screening',inputs:o.inputs.map((x:any)=>({kind:'literal',target:x.target,value:x.value,units:x.units,provenance:x.provenance})),criteria:o.criteria,numerical:o.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(d.sid)).revision},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[],approach_selection:{approach_version_id:d.saved.version.approach_version_id,case_id:i===10?null:d.saved.version.content.cases[0].case_id}};const p=await api.previewConfiguration4(configuration),v=await api.commitConfiguration4({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:p.candidate_digest});ids.push(v.configuration.configuration_revision_id);}
    const run=await api.submitRun(d.sid,o.configuration_revision_id);const response=await fetch('/fixture/retain-failed-outcome',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:d.fixture.key,study_id:d.sid,run_id:run.run_id})});if(!response.ok)throw new Error(await response.text());return {ids,run:run.run_id};
  },{d,original});await ctx.close();
  await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();const usage=page.getByRole('region',{name:'Approach usage',exact:true});
  await expect(usage).toContainText('10 usage rows loaded');await expect(usage).toContainText('More usage is available');await expect(usage).not.toContainText('Not evaluated in the loaded review');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await findingsShot(page,'findings-incomplete-'+theme);}
  let fail=true;await page.route('**/approach/versions/*/usage**',async route=>{if(fail&&new URL(route.request().url()).searchParams.has('cursor')){fail=false;await route.abort();}else await route.continue();});
  await usage.getByRole('button',{name:'Load more usage',exact:true}).click();await expect(usage).toContainText('Usage unavailable');await expect(usage).toContainText('10 usage rows loaded');
  await usage.getByRole('button',{name:'Retry usage page',exact:true}).click();await expect(usage).toContainText('13 usage rows loaded');await expect(usage).toContainText('All usage loaded');await expect(usage).toContainText('Not evaluated in the loaded review · no run found for this case');
  await expect(usage.getByRole('button',{name:'View configuration',exact:true})).toHaveCount(11);await expect(usage.getByRole('button',{name:'View run',exact:true})).toHaveCount(1);await expect(usage).toContainText('No specific case');
  await usage.getByRole('button',{name:'Run details',exact:true}).press('Enter');await expect(usage.getByLabel('Run status',{exact:true})).toContainText('Failed');await expect(usage.getByLabel('Run status',{exact:true}).locator('.hf-facet__k')).toHaveText(['Execution','Criteria']);for(const removed of ['Not assessed','Applicability','Convergence','Termination','Feasibility','Output completeness'])await expect(usage).not.toContainText(removed);
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await findingsShot(page,'findings-populated-'+theme);}
  await usage.getByLabel('Findings case',{exact:true}).selectOption(d.saved.version.content.cases[1].case_id);await expect(usage).toContainText('0 usage rows loaded');await expect(usage.getByRole('article',{name:'Nominal range',exact:true})).toHaveCount(0);
  await usage.getByLabel('Findings case',{exact:true}).selectOption('');await expect(usage).toContainText('10 usage rows loaded');
  await page.route('**/configurations/'+created.ids.sort()[0],route=>route.abort());await usage.getByRole('button',{name:'Refresh usage',exact:true}).press('Enter');await expect(usage).toContainText('Record unavailable');await expect(usage.getByRole('button',{name:'View configuration',exact:true})).toHaveCount(10);
});

async function nativeFindings(page:Page,browser:any,baseURL:string|undefined){
  await page.request.post('/fixture/model-available');
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const data=await helper.evaluate(async()=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');const pair=await(await fetch('/fixture/native-pair')).json(),sid=pair.study_id;
    const source=await api.run(sid,pair.source_id),downstream=await api.run(sid,pair.downstream_id),o=downstream.history.configuration,m=downstream.history.model_snapshot;
    await c.open(sid);const content=structuredClone(c.getSnapshot().local),binding={binding_id:crypto.randomUUID(),model_id:m.model_id,model_revision_id:m.model_revision_id};
    content.steps=[{step_id:crypto.randomUUID(),title:'Convert retained energy',purpose:'Review an exact retained source',rationale:'Explicit source qualification',remaining_work:'',intent:{transformation:'Retained energy conversion',inputs:'MJ/kg',outputs:'J/kg',depends_on_step_ids:[]},implementation_state:'linked',implementation_refs:[{kind:'model',binding_id:binding.binding_id}],assumption_refs:[],evidence_links:[]}];content.question='Review retained energy conversion';content.scope='New approach-pinned configuration; original native runs remain unlinked historical numerical proof.';content.model_bindings=[binding];content.cases=[{case_id:crypto.randomUUID(),title:'Retained energy case',question:'What qualifications accompany the retained energy input?',rationale:'Inspect the source criterion without changing downstream outcomes.',binding_id:binding.binding_id,evidence_links:[]}];
    c.edit(content);if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);const saved=c.getSnapshot().saved;
    const configuration={schema_version:'4',study_id:sid,model_id:o.model_id,model_revision_id:o.model_revision_id,name:'Retained energy conversion review',inputs:o.inputs.map((i:any)=>i.result_binding?{kind:'run_result',target:i.target,source_run_id:i.result_binding.source_run_id,source_output:i.result_binding.source_output,expected_results_digest:i.result_binding.results_digest,provenance:i.provenance}:{kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance}),criteria:o.criteria,numerical:o.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(sid)).revision},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[],approach_selection:{approach_version_id:saved.version.approach_version_id,case_id:saved.version.content.cases[0].case_id}};
    const preview=await api.previewConfiguration4(configuration),frozen=await api.commitConfiguration4({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:preview.candidate_digest});return {sid,saved,frozen,source,downstream};
  });await ctx.close();
  await page.goto('/ui/?workspace#'+new URLSearchParams({v:'1',study:data.sid,view:'approach',approach:data.saved.version.approach_version_id}));await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await casesTab(page);const usage=page.getByRole('region',{name:'Approach usage',exact:true});await expect(usage).toContainText('Retained energy conversion review');return data;
}

test('@approach-history Findings authentic retained native conversion qualifies a public pinned configuration',async({page,browser,baseURL})=>{
  const data=await nativeFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  expect(data.source.history.history_schema_version).toBe('4');expect(data.downstream.history.history_schema_version).toBe('4');expect(data.source.history.configuration.approach_binding).toBeNull();expect(data.downstream.history.configuration.approach_binding).toBeNull();expect(data.downstream.history.results.criteria.every((c:any)=>c.outcome==='met')).toBe(true);
  const calls:string[]=[],writes:string[]=[];page.on('request',request=>{if(request.url().includes('/api/1/')&&request.method()!=='GET')writes.push(request.url());if(request.url().includes('/runs/'))calls.push(request.url());});
  await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).press('Enter');await expect(usage).toContainText('Upstream qualifications not loaded');expect(calls).toEqual([]);
  await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).press('Enter');await expect(usage).toContainText('Verified source identity');await expect(usage).toContainText('Upstream criterion not met');await expect(usage).toContainText('Original 1 MJ/kg');await expect(usage).toContainText('factor 1000000 · received 1000000 J/kg');await expect(usage.getByLabel('Run status',{exact:true})).toContainText('Completed');expect(calls).toHaveLength(1);
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await findingsShot(page,'findings-native-qualified-'+theme);}
  await page.request.post('/fixture/model-outage');await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await expect(page.getByRole('region',{name:'Results',exact:true})).toContainText('All usage loaded');await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();await expect(usage).toContainText('Verified source identity');expect(writes).toEqual([]);
  await usage.getByRole('button',{name:'View upstream run',exact:true}).press('Enter');await expect(page.getByRole('tab',{name:'Results',exact:true})).toBeVisible();expect(new URL(page.url()).hash).toContain(data.source.run_id);await page.request.post('/fixture/model-available');
});

test('@approach-history Findings source mismatches and unavailable metadata fail closed without changing recorded facets',async({page,browser,baseURL})=>{
  const d=await nativeFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  // Supplementary response tamper matrix. Original native/API records are unchanged.
  const mutations=['digest','configuration','target','value','units','duplicate','physical','unspecified','absent','null','missing'];
  for(const mutation of mutations){
    await page.route('**/runs/'+d.source.run_id,async route=>{if(mutation==='missing'){await route.fulfill({status:404,json:{error:{code:'resource_not_found',message:'foreign secret must never display',fields:[],outcome:'unchanged'}}});return;}const x=structuredClone(d.source),h=x.history,b=d.frozen.configuration.inputs.find((i:any)=>i.result_binding).result_binding,out=h.results.outputs.find((o:any)=>o.target.instance_id===b.source_output.instance_id&&o.target.port_id===b.source_output.port_id),instance=h.model_snapshot.instances.find((i:any)=>i.instance_id===b.source_output.instance_id),port=h.model_snapshot.definitions.find((v:any)=>v.definition_version_id===instance.definition_version_id).ports.find((p:any)=>p.port_id===b.source_output.port_id);
      if(mutation==='digest')x.retained_integrity.results_digest='0'.repeat(64);if(mutation==='configuration')h.configuration.digest='0'.repeat(64);if(mutation==='target')out.target.port_id=crypto.randomUUID();if(mutation==='value')out.value+=Number.EPSILON;if(mutation==='units')out.units='J/kg';if(mutation==='duplicate')h.results.outputs.push(structuredClone(out));if(mutation==='physical')port.units={kind:'physical',expression:'J/kg'};if(mutation==='unspecified')port.units={kind:'unspecified'};if(mutation==='absent')delete x.retained_integrity;if(mutation==='null')x.retained_integrity.results_digest=null;await route.fulfill({json:{schema_version:'1',data:x}});
    });await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();await expect(usage).toContainText(['absent','null','missing'].includes(mutation)?'Upstream record unavailable':'Source binding mismatch');await expect(usage).not.toContainText('Verified source identity');await expect(usage).not.toContainText('foreign secret');await page.unroute('**/runs/'+d.source.run_id);
  }
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await findingsShot(page,'findings-unavailable-'+theme);}
});

test('@approach-history Findings batches direct sources with two concurrent reads and rejects late scope replies',async({page,browser,baseURL})=>{
  const d=await nativeFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true}),original=d.frozen.configuration.inputs.find((i:any)=>i.result_binding),ids=Array.from({length:12},()=>crypto.randomUUID());
  // Supplementary fan-out fixture; no synthetic numerical values count as native proof.
  await page.route('**/configurations/'+d.frozen.configuration.configuration_revision_id,async route=>{const x=structuredClone(d.frozen);x.configuration.inputs=[...ids,ids[0]].map((id,index)=>({...structuredClone(original),target:{...original.target,port_id:crypto.randomUUID()},result_binding:{...original.result_binding,source_run_id:id}}));await route.fulfill({json:{schema_version:'1',data:x}});});
  let active=0,maximum=0;const requests:string[]=[];const releases:Array<()=>void>=[];let slow=false;
  await page.route('**/runs/*',async route=>{const id=route.request().url().split('/').pop()!;if(!ids.includes(id)){await route.continue();return;}requests.push(id);active++;maximum=Math.max(maximum,active);if(slow)await new Promise<void>(resolve=>{releases.push(resolve);});else await new Promise(resolve=>setTimeout(resolve,75));active--;await route.fulfill({status:404,json:{error:{code:'resource_not_found',message:'unavailable',fields:[],outcome:'unchanged'}}});});
  await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();expect(requests).toHaveLength(0);await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();await expect.poll(()=>requests.length).toBe(10);await expect(usage.getByRole('button',{name:'Load more source runs',exact:true})).toBeEnabled();expect(maximum).toBeLessThanOrEqual(2);expect(new Set(requests).size).toBe(10);await usage.getByRole('button',{name:'Load more source runs',exact:true}).click();await expect.poll(()=>requests.length).toBe(12);await expect(usage.getByRole('button',{name:'Retry upstream read',exact:true})).toBeEnabled();
  slow=true;await usage.getByRole('button',{name:'Retry upstream read',exact:true}).click();await expect.poll(()=>requests.length).toBe(14);await usage.getByLabel('Findings case',{exact:true}).selectOption(d.saved.version.content.cases[0].case_id);releases.forEach(resolve=>resolve());await page.unroute('**/runs/*');await expect(usage).not.toContainText('Upstream record unavailable');
});

test('@approach-history Findings genuine 200 percent zoom and keyboard source review in both themes',async({baseURL,browser})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/findings-zoom-extension');await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Findings zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/findings-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try{const page=context.pages()[0]??await context.newPage();await nativeFindings(page,browser,baseURL);const usage=page.getByRole('region',{name:'Approach usage',exact:true}),cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);const refresh=usage.getByRole('button',{name:'Refresh usage',exact:true});await refresh.focus();await refresh.press('Enter');await expect(refresh).toBeFocused();const review=usage.getByRole('button',{name:'Review source-linked inputs',exact:true});await review.focus();await review.press('Enter');const load=usage.getByRole('button',{name:'Load upstream qualifications',exact:true});await load.focus();await load.press('Enter');await expect(usage).toContainText('Verified source identity');await usage.getByRole('button',{name:'View upstream run',exact:true}).scrollIntoViewIfNeeded();const bounds=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width+1);geometry.push({theme,...bounds});const target=usage.getByRole('button',{name:'View upstream run',exact:true});await target.focus();await expect(target).toBeFocused();expect(await target.evaluate(e=>{const r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===e;})).toBe(true);const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/findings-native-200-'+theme+'.png'),Buffer.from(shot.data,'base64'));}
    await writeFile(join(root,'evidence/findings-zoom-geometry.json'),JSON.stringify({zoom:2,viewport:null,geometry},null,2));
  }finally{await context.close();}
});


test('@approach-history Findings source caveats keep synthetic run outcomes separate and support zero dimensionless matching',async({page,browser,baseURL})=>{
  const d=await nativeFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true}),rid=crypto.randomUUID();
  // Supplementary UI projection only. These cloned response records are not
  // native outcomes or new historical pins; the retained run bytes remain immutable.
  const run=structuredClone(d.downstream);run.run_id=rid;run.history.results.run_id=rid;run.history.configuration=structuredClone(d.frozen.configuration);run.history.approach_closure=d.frozen.approach_closure;
  await page.route('**/approach/versions/'+d.saved.version.approach_version_id+'/usage**',route=>route.fulfill({json:{schema_version:'1',data:{items:[{kind:'run',run_id:rid,configuration_revision_id:d.frozen.configuration.configuration_revision_id,case_id:d.saved.version.content.cases[0].case_id}],next_cursor:null}}}));
  await page.route('**/runs/'+rid,route=>route.fulfill({json:{schema_version:'1',data:run}}));
  let variant='violated';await page.route('**/runs/'+d.source.run_id,async route=>{if(variant==='violated'){await route.continue();return;}const source=structuredClone(d.source),binding=run.history.configuration.inputs.find((i:any)=>i.result_binding).result_binding,out=source.history.results.outputs.find((o:any)=>o.target.instance_id===binding.source_output.instance_id&&o.target.port_id===binding.source_output.port_id);source.history.results.criteria=variant==='unresolved'?[{criterion_id:crypto.randomUUID(),outcome:'unresolved',reason:'Recorded threshold unavailable'}]:[];if(variant==='legacy-zero'||variant==='typed-zero'){out.value=0;out.units='';const instance=source.history.model_snapshot.instances.find((i:any)=>i.instance_id===out.target.instance_id),port=source.history.model_snapshot.definitions.find((v:any)=>v.definition_version_id===instance.definition_version_id).ports.find((p:any)=>p.port_id===out.target.port_id);port.units=variant==='legacy-zero'?'':{kind:'dimensionless'};}await route.fulfill({json:{schema_version:'1',data:source}});});
  for(variant of ['violated','unresolved','none','legacy-zero','typed-zero']){
    if(variant.endsWith('zero')){const input=run.history.configuration.inputs.find((i:any)=>i.result_binding);input.value=0;input.units='';input.result_binding.original_value=0;input.result_binding.original_units='';input.result_binding.conversion={...input.result_binding.conversion,source_units:'',destination_units:'',factor:1,destination_value:0};}
    await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await usage.getByRole('button',{name:'Run details',exact:true}).click();const outcomes=usage.getByLabel('Run status',{exact:true}).first();await expect(outcomes).toContainText('Completed');await expect(outcomes).toContainText('2 of 2 met');await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();await expect(usage).toContainText('Verified source identity');await expect(outcomes).toContainText('2 of 2 met');if(variant==='violated')await expect(usage).toContainText('Upstream criterion not met');if(variant==='unresolved')await expect(usage).toContainText('Upstream criterion not evaluated');if(variant.endsWith('zero'))await expect(usage).toContainText('Original 0 Dimensionless');
    // Source caveats qualify the source only; the downstream result card is unchanged.
    const card=usage.getByRole('article',{name:'Retained energy case',exact:true}).getByRole('article',{name:'run '+rid,exact:true}).getByLabel('Run outcomes',{exact:true});await expect(card).toContainText('2 of 2 met');await expect(card).toContainText('Completed');await expect(card).not.toContainText('Upstream');
  }
  // Exact pin tamper remains a row-local error, not a replacement configuration.
  run.history.configuration.approach_binding.case_id=crypto.randomUUID();await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await expect(usage).toContainText('Record binding mismatch');await expect(usage.getByLabel('Run status',{exact:true})).toHaveCount(0);
});

test('@approach-history Findings late usage replies cannot overwrite a refreshed review',async({page,browser,baseURL})=>{
  const d=await nativeFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true});let release:()=>void=()=>{},started=false,count=0;
  await page.route('**/approach/versions/'+d.saved.version.approach_version_id+'/usage**',async route=>{count++;if(count!==1){await route.continue();return;}started=true;await new Promise<void>(resolve=>{release=resolve;});await route.fulfill({json:{schema_version:'1',data:{items:[],next_cursor:null}}});});
  await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await expect.poll(()=>started).toBe(true);await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await expect(usage).toContainText('1 usage rows loaded');release();await expect(usage).toContainText('Retained energy conversion review');await expect(usage).toContainText('1 usage rows loaded');
  const results=page.getByRole('region',{name:'Results',exact:true});await expect(results).toContainText('0 runs loaded for this approach version.');await expect(results).toContainText('1 configuration loaded');await expect(usage.getByRole('article',{name:'Retained energy case',exact:true})).toContainText('1 configuration without a loaded run');await expect(results).not.toContainText('2 configurations');
});

test('@approach-history Findings clears protected projections after current study access loss',async({page,browser,baseURL})=>{
  const d=await nativeFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true});await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();await expect(usage).toContainText('Verified source identity');await page.request.post('/fixture/revoke',{data:{study_id:d.sid}});await expect(page.getByRole('region',{name:'Results',exact:true})).toContainText('1 configuration loaded');await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await expect(page.getByText('Access to this resource is no longer available.',{exact:true}).first()).toBeVisible();await expect(usage).toHaveCount(0);await expect(page.getByText('Retained energy conversion review')).toHaveCount(0);await expect(page.getByText('Verified source identity')).toHaveCount(0);
  // Confirmed denial removes the protected results review as well:
  // the denial is signalled to the approach page, which clears the whole reader and its usage panel.
  await expect(page.getByRole('region',{name:'Results',exact:true})).toHaveCount(0);await expect(page.getByText('1 configuration loaded')).toHaveCount(0);
});

// Every revocation case owns a fresh real study. Numerical/configuration
// overlays below are presentation fixtures, never new native acceptance proof.
async function repairFindings(page:Page,browser:any,baseURL:string|undefined){
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const d=await helper.evaluate(async()=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');
    const sid=(await api.createStudy('Findings lifecycle fixture')).study_id;await c.open(sid);
    const content=structuredClone(c.getSnapshot().local);content.question='Review protected records';content.cases=[{case_id:crypto.randomUUID(),title:'Protected case',question:'Can this review recover safely?',rationale:'Authorization lifecycle fixture',binding_id:null,evidence_links:[]}];
    c.edit(content);if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);const saved=c.getSnapshot().saved;
    const pair=await(await fetch('/fixture/native-pair')).json(),source=structuredClone(pair.records[pair.source_id]),downstream=structuredClone(pair.records[pair.downstream_id]);
    const configuration=structuredClone(downstream.history.configuration);configuration.configuration_revision_id=crypto.randomUUID();configuration.study_id=sid;configuration.name='Retained energy conversion review';configuration.approach_binding={approach_id:saved.version.approach_id,approach_version_id:saved.version.approach_version_id,approach_digest:saved.version.digest,closure_digest:saved.closure.digest,case_id:saved.version.content.cases[0].case_id};
    return {sid,saved,source,downstream,frozen:{configuration,approach_closure:saved.closure}};
  });await ctx.close();
  await page.route('**/approach/versions/'+d.saved.version.approach_version_id+'/usage**',route=>route.fulfill({json:{schema_version:'1',data:{items:[{kind:'configuration',configuration_revision_id:d.frozen.configuration.configuration_revision_id,case_id:d.saved.version.content.cases[0].case_id}],next_cursor:null}}}));
  await page.route('**/configurations/'+d.frozen.configuration.configuration_revision_id,route=>route.fulfill({json:{schema_version:'1',data:d.frozen}}));
  await page.route('**/api/1/studies/'+d.sid+'/runs/'+d.source.run_id,route=>route.fulfill({json:{schema_version:'1',data:d.source}}));
  await page.goto('/ui/?workspace#'+new URLSearchParams({v:'1',study:d.sid,view:'approach',approach:d.saved.version.approach_version_id}));await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();await casesTab(page);await expect(page.getByRole('region',{name:'Approach usage',exact:true})).toContainText('Retained energy conversion review');return d;
}

// Response overlays exercise the read lifecycle only; they are not native proof.
// The confirmed denial clears the whole approach reader, usage panel included.
for (const entry of ['queued detail','record retry']) test(`@approach-history Findings reader concealed revocation during ${entry} clears cached sources and rejects late details`,async({page,browser,baseURL})=>{
  const d=await repairFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  const original=d.frozen.configuration.configuration_revision_id,bad=crypto.randomUUID(),late=crypto.randomUUID();
  const row=(id:string)=>({kind:'configuration',configuration_revision_id:id,case_id:d.saved.version.content.cases[0].case_id});
  let releaseDenied:()=>void=()=>{},releaseLate:()=>void=()=>{},deniedStarted=false,lateStarted=false,lateFinished=false,probes=0;
  const deniedGate=new Promise<void>(resolve=>{releaseDenied=resolve;}),lateGate=new Promise<void>(resolve=>{releaseLate=resolve;});
  await page.route('**/approach/versions/'+d.saved.version.approach_version_id+'/usage**',route=>route.fulfill({json:{schema_version:'1',data:new URL(route.request().url()).searchParams.has('cursor')?{items:(entry==='queued detail'?[row(bad),row(late)]:[row(late)]),next_cursor:null}:{items:entry==='record retry'?[row(original),row(bad)]:[row(original)],next_cursor:{kind:'configuration',resource_id:original}}}}));
  let badCalls=0;
  await page.route('**/configurations/'+bad,async route=>{badCalls++;if(entry==='record retry'&&badCalls===1){await route.abort();return;}deniedStarted=true;await deniedGate;await route.continue();});
  await page.route('**/configurations/'+late,async route=>{lateStarted=true;await lateGate;const x=structuredClone(d.frozen);x.configuration.configuration_revision_id=late;x.configuration.name='Late protected record';await route.fulfill({json:{schema_version:'1',data:x}});lateFinished=true;});
  await page.route('**/api/1/studies/'+d.sid,async route=>{probes++;await route.continue();});
  await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();
  if(entry==='record retry')await expect(usage).toContainText('Record unavailable');
  await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();await expect(usage).toContainText('Verified source identity');
  await usage.getByRole('button',{name:'Load more usage',exact:true}).click();await expect.poll(()=>lateStarted).toBe(true);
  expect((await page.request.post('/fixture/revoke',{data:{study_id:d.sid}})).ok()).toBe(true);
  if(entry==='record retry'){const retry=usage.getByRole('button',{name:'Retry record',exact:true});await retry.focus();await retry.press('Enter');}
  await expect.poll(()=>deniedStarted).toBe(true);releaseDenied();
  try{await expect(page.getByText('Access to this resource is no longer available.',{exact:true}).first()).toBeVisible();await expect(usage).toHaveCount(0);expect(probes).toBe(1);await expect(page.getByText('Retained energy conversion review')).toHaveCount(0);await expect(page.getByText('Verified source identity')).toHaveCount(0);}
  finally{releaseLate();}
  await expect.poll(()=>lateFinished).toBe(true);await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));await expect(page.getByText('Late protected record')).toHaveCount(0);await expect(usage.getByRole('article')).toHaveCount(0);
});

for(const source of [true,false]) test(`@approach-history Findings reader missing ${source?'source':'record'} with transient study probe recovers in place`,async({page,browser,baseURL})=>{
  const d=await repairFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  const path=source?'**/runs/'+d.source.run_id:'**/configurations/'+d.frozen.configuration.configuration_revision_id;
  await page.route(path,route=>route.fulfill({status:404,json:{error:{code:'resource_not_found',message:'private missing detail',fields:[],outcome:'unchanged'}}}),{times:1});
  await page.route('**/api/1/studies/'+d.sid,route=>route.abort(),{times:1});
  if(source){await usage.getByRole('button',{name:'Review source-linked inputs',exact:true}).click();await usage.getByRole('button',{name:'Load upstream qualifications',exact:true}).click();}
  else await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();
  await expect(usage).toContainText('Study access could not be verified. Retry the read.');await expect(usage).not.toContainText('Access to this resource is no longer available.');await expect(usage).not.toContainText('private missing detail');
  if(source)await expect(usage).toContainText('Retained energy conversion review');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await usage.getByText('Study access could not be verified. Retry the read.',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence',`findings-r1-probe-${source?'source':'record'}-${theme}.png`),fullPage:false,animations:'disabled'});}
  const retry=usage.getByRole('button',{name:source?'Retry upstream read':'Retry record',exact:true});await retry.focus();await retry.press('Enter');
  await expect(usage).toContainText(source?'Verified source identity':'Retained energy conversion review');await expect(usage).not.toContainText('Study access could not be verified.');
});

test('@approach-history Findings reader ordinary missing record stays local and actual output controls work by keyboard',async({page,browser,baseURL})=>{
  const d=await repairFindings(page,browser,baseURL),usage=page.getByRole('region',{name:'Approach usage',exact:true}),missing=crypto.randomUUID(),rid=crypto.randomUUID();
  const run=structuredClone(d.downstream);run.run_id=rid;run.history.results.run_id=rid;run.history.configuration=structuredClone(d.frozen.configuration);run.history.approach_closure=d.frozen.approach_closure;
  const out=run.history.results.outputs[0];run.history.results.outputs=Array.from({length:6},(_,i)=>({...structuredClone(out),value:i===5?null:i===0?0:1.2345678901234567+i,availability:i===5?'unavailable':'available',reason:i===5?'Not produced in this presentation fixture':null}));
  await page.route('**/approach/versions/'+d.saved.version.approach_version_id+'/usage**',route=>route.fulfill({json:{schema_version:'1',data:{items:[{kind:'configuration',configuration_revision_id:missing,case_id:d.saved.version.content.cases[0].case_id},{kind:'run',run_id:rid,configuration_revision_id:d.frozen.configuration.configuration_revision_id,case_id:d.saved.version.content.cases[0].case_id}],next_cursor:null}}}));
  await page.route('**/runs/'+rid,route=>route.fulfill({json:{schema_version:'1',data:run}}));
  let probes=0;await page.route('**/api/1/studies/'+d.sid,async route=>{probes++;await route.continue();});
  await usage.getByRole('button',{name:'Refresh usage',exact:true}).press('Enter');await expect(usage).toContainText('Record unavailable');await expect(usage).toContainText('Retained energy conversion review');await expect.poll(()=>probes).toBe(1);await expect(usage).not.toContainText('Access to this resource is no longer available.');
  const details=usage.getByRole('button',{name:'Run details',exact:true});await details.focus();await details.press('Enter');await expect(details).toHaveAttribute('aria-expanded','true');
  const outputs=usage.locator('.run-key-outputs').locator(':scope > div');await expect(outputs).toHaveCount(4);
  const all=usage.getByRole('button',{name:'Show all 6 outputs',exact:true});await all.focus();await all.press('Enter');await expect(outputs).toHaveCount(6);await expect(outputs.last()).toContainText('not computed');await expect(outputs.first()).toContainText('0');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await usage.locator('.run-key-outputs').scrollIntoViewIfNeeded();await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence',`findings-r1-outputs-${theme}.png`),fullPage:false,animations:'disabled'});}
  const fewer=usage.getByRole('button',{name:'Show fewer outputs',exact:true});await expect(fewer).toHaveAttribute('aria-expanded','true');await fewer.press('Enter');await expect(outputs).toHaveCount(4);
  const exact=usage.getByRole('button',{name:'Full-precision values',exact:true});await exact.focus();await exact.press('Enter');const dialog=page.getByRole('dialog',{name:'Full-precision values',exact:true});await expect(dialog).toBeVisible();await expect(dialog.getByRole('row')).toHaveCount(7);await expect(dialog).toContainText(String(run.history.results.outputs[1].value));await expect(dialog).toContainText('not computed');await dialog.press('Escape');await expect(dialog).toHaveCount(0);await expect(exact).toBeFocused();
  await page.route('**/configurations/'+missing,route=>{const x=structuredClone(d.frozen);x.configuration.configuration_revision_id=missing;x.configuration.name='Recovered record';return route.fulfill({json:{schema_version:'1',data:x}});});
  const retry=usage.getByRole('button',{name:'Retry record',exact:true});await retry.focus();await retry.press('Enter');await expect(usage).toContainText('Recovered record');await expect(usage).not.toContainText('Record unavailable');
});

test('@approach-controller polish question claims and cited limits persist without invented attribution', async ({page}) => {
  const sid=await open(page);
  expect((await state(page)).local.schema_version).toBe('2');
  expect((await state(page)).local.original_question).toBeNull();
  await page.evaluate(()=>{
    const c=(window as any).approachHarness.controller;
    c.edit({...c.getSnapshot().local,question:'Can this response be bounded?',
      original_question:{text:'What bounds the response?',attribution:{kind:'human',label:'Recorded requester'}},
      elaboration:{text:'<script>Never execute supplied prose</script>',attribution:{kind:'agent',label:'Drafting assistant'}},
      limit_items:[{limit_id:crypto.randomUUID(),statement:'Only the measured range is covered.',evidence_links:[]}]});
  });
  expect(await act(page,'save')).toBe(true);expect(await act(page,'saveVersion')).toBe(true);
  const saved=(await state(page)).saved;
  expect(saved.version.content.schema_version).toBe('2');
  expect(saved.version.content.original_question.attribution).toEqual({kind:'human',label:'Recorded requester'});
  expect(saved.version.content.limit_items[0].evidence_links).toEqual([]);
  expect(saved.version.created_by).not.toBe('Recorded requester');
  await page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid);
  await edit(page,'New draft question');expect(await act(page,'save')).toBe(true);
  const retained=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${saved.version.approach_version_id}`)).json()).data;
  expect(retained).toEqual(saved);
});

test('@approach-controller polish legacy draft remains exact until explicit descriptive upgrade', async ({page})=>{
  const sid=await open(page);
  await page.evaluate(async sid=>{
    const h=(window as any).approachHarness;
    const content={schema_version:'1',question:'Legacy question',scope:'Old scope',limitations:'Line one.\nLine two.',open_questions:'',model_bindings:[],steps:[],assumptions:[],cases:[],basis_refs:[]};
    const preview=await h.api.previewApproach(sid,{schema_version:'1',expected_revision:null,content});
    await h.api.saveApproachDraft(sid,{schema_version:'1',command_id:crypto.randomUUID(),expected_revision:null,content,expected_preview_digest:preview.preview_digest});
    await h.controller.open(sid);
  },sid);
  expect((await state(page)).local.schema_version).toBe('1');
  expect((await state(page)).local.original_question).toBeUndefined();
  expect(await act(page,'saveVersion')).toBe(true);
  const original=(await state(page)).saved;
  await page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid);
  await page.evaluate(()=>{const c=(window as any).approachHarness.controller;c.edit({...c.getSnapshot().local,schema_version:'2',original_question:null,elaboration:null,limit_items:[]});});
  expect(await act(page,'save')).toBe(true);
  expect((await state(page)).local.limitations).toBe('Line one.\nLine two.');
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${original.version.approach_version_id}`)).json()).data).toEqual(original);
});

test('@approach-reading polish contextual question and limits use real commands and reading defaults',async({page})=>{
  await openProduct(page);await writeQuestion(page,'Which observations bound the response?');
  await page.getByRole('button',{name:'Edit question and scope',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Edit question and scope',exact:true});
  await editor.getByLabel('Original wording',{exact:true}).fill('What sets the response bounds?');
  await editor.getByLabel('Original wording attribution',{exact:true}).selectOption('human');
  await editor.getByLabel('Original wording attribution label',{exact:true}).fill('Recorded requester');
  await editor.getByLabel('Detailed elaboration',{exact:true}).fill('<script>window.unsafeClaim = true</script> The measured range needs explicit limits.');
  await editor.getByLabel('Detailed elaboration attribution',{exact:true}).selectOption('agent');
  await editor.getByLabel('Detailed elaboration attribution label',{exact:true}).fill('Drafting assistant');
  await editor.getByRole('button',{name:'Apply to draft',exact:true}).click();
  // See more details at the bottom-right of the question box opens Study details.
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Question in detail',exact:true})).toHaveCount(0);
  const trigger=page.getByRole('button',{name:'See more details',exact:true});await trigger.focus();await trigger.press('Enter');
  const conditions=page.getByRole('dialog',{name:'Study details',exact:true});
  await expect(conditions.getByRole('heading', { level: 3 })).toHaveText([
    'Study question',
    'Current approach',
    'Assumptions',
    'Limits',
    'Open questions',
  ]);
  await expect(conditions).not.toContainText('Earlier limits text');
  await conditions.getByRole('button',{name:'Add limit',exact:true}).click();
  const limit=page.getByRole('dialog',{name:'Edit study limit',exact:true});await expect(limit.getByLabel('Limit statement')).toBeFocused();
  await limit.getByLabel('Limit statement').fill('Only the measured operating range is represented.');
  await limit.getByRole('button',{name:'Apply limit',exact:true}).click();
  await expect(
    conditions.getByRole('region', { name: 'Study limits', exact: true }),
  ).not.toContainText('No evidence linked');
  await conditions.getByRole('button',{name:'Done',exact:true}).click();await expect(trigger).toBeFocused();
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save approach version',exact:true}).click();await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();
  await expect(page.getByRole('button',{name:'Edit approach',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Save draft',exact:true})).toHaveCount(0);
  const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!,version=await page.getByLabel('Approach version',{exact:true}).inputValue();
  const saved=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${version}`)).json()).data;
  expect(saved.version.content.schema_version).toBe('2');expect(saved.version.content.limit_items).toHaveLength(1);
  expect(saved.version.content.original_question.attribution.label).toBe('Recorded requester');
  for(const theme of ['light','dark']){
    await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','polish-question-'+theme+'.png')});
    const detailTrigger=page.getByRole('button',{name:'See more details',exact:true});await detailTrigger.focus();await detailTrigger.press('Enter');
    const detail = page.getByRole('dialog', { name: 'Study details', exact: true });
    await expect(detail).toContainText('Supplied agent attribution: Drafting assistant');
    await expect(detail).toContainText('Authorship has not been verified.');
    expect(await page.evaluate(()=>(window as any).unsafeClaim)).toBeUndefined();
    await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','polish-question-detail-'+theme+'.png')});
    await page.keyboard.press('Escape');await expect(detailTrigger).toBeFocused();
    await trigger.click();await expect(conditions.getByRole('button',{name:'Add limit',exact:true})).toHaveCount(0);
    await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','polish-conditions-'+theme+'.png')});await page.keyboard.press('Escape');await expect(trigger).toBeFocused();
  }
  await page.setViewportSize({width:720,height:1000});await trigger.click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(720);
  await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','polish-conditions-narrow.png')});await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await writeQuestion(page,'A changed current draft');await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByLabel('Approach version',{exact:true}).selectOption(version);
  await expect(page.getByRole('heading',{name:'Which observations bound the response?',exact:true})).toBeVisible();
  expect((await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${version}`)).json()).data).toEqual(saved);
  // Overview shows the same question box and the same dialog for the latest saved version.
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();await expect(page.getByRole('region',{name:'Study question',exact:true}).getByRole('heading',{name:'Which observations bound the response?',exact:true})).toBeVisible();await trigger.click();
  await expect(page.getByRole('dialog',{name:'Study details',exact:true})).toContainText('Only the measured operating range is represented.');
});

/** Opens the retained approach of a configuration record, then its study conditions (nested dialogs). */
async function retainedConditions(page:Page,host:ReturnType<Page['getByRole']>){
  await host.getByRole('button',{name:'View modeling approach',exact:true}).click();
  const reader=page.getByRole('dialog',{name:'Linked modeling approach',exact:true});await expect(reader).toBeVisible();
  await reader.getByRole('button',{name:'See more details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Study details',exact:true})).toBeVisible();
}
async function closeRetainedConditions(page:Page){
  await page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('dialog',{name:'Linked modeling approach',exact:true}).getByRole('button',{name:'Done',exact:true}).last().click();
  await expect(page.getByRole('dialog',{name:'Linked modeling approach',exact:true})).toBeHidden();
}

test('@approach-assumptions polish cited limits and conditions retain exact configuration and run context',async({page,browser,baseURL})=>{
  await page.request.post('/fixture/model-available');
  const data=await seededConditions(page,browser,baseURL,{failure:true});
  const statement='Interpretation is limited to the measured operating range.';
  const conditions=page.getByRole('dialog',{name:'Study details',exact:true});
  await page.getByRole('button',{name:'See more details',exact:true}).click();
  await conditions.getByRole('button',{name:'Add limit',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Edit study limit',exact:true});
  await editor.getByLabel('Limit statement',{exact:true}).fill(statement);
  await editor.getByRole('button',{name:'Apply limit',exact:true}).click();
  await conditions.getByRole('button',{name:'Add evidence to '+statement,exact:true}).click();
  const picker=page.getByRole('dialog',{name:'Add evidence to '+statement,exact:true});
  await picker.getByRole('button',{name:/Choose Screening measurements/}).click();
  await picker.getByLabel('Relationship',{exact:true}).selectOption('supports');
  await picker.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await expect(conditions.getByRole('region',{name:statement+' evidence',exact:true})).toContainText('Screening measurements');
  await conditions.getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save approach version',exact:true}).click();await page.getByRole('dialog',{name:'Save approach version',exact:true}).getByRole('button',{name:'Save version',exact:true}).click();
  await expect(page.getByLabel('Approach version',{exact:true})).toContainText('v2 (read-only)');
  const frozen=(await(await page.request.get('/api/1/studies/'+data.sid+'/approach/versions/'+await page.getByLabel('Approach version',{exact:true}).inputValue())).json()).data;
  expect(frozen.version.content.limit_items[0].evidence_links).toEqual([{evidence_version_id:data.evidence.evidence_version_id,relation:'supports'}]);
  for(const theme of ['light','dark']){
    await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    await page.getByRole('button',{name:'See more details',exact:true}).click();
    await expect(conditions).toContainText('Saved approach v2');
    await expect(conditions).toContainText(data.proposal.statement);
    // Four stacked sections in a fixed order, none overflowing.
    const sections=await conditions.locator('.study-details-section').evaluateAll(nodes=>nodes.map(node=>{const r=node.getBoundingClientRect();return {label:node.getAttribute('aria-label'),x:r.x,y:r.y,scroll:node.scrollWidth,client:node.clientWidth};}));
    expect(sections.map((section) => section.label)).toEqual([
      'Study question',
      'Current approach',
      'Study assumptions',
      'Study limits',
    ]);
    for (let i = 1; i < sections.length; i++) {
      expect(sections[i].y).toBeGreaterThan(sections[i - 1].y);
      expect(Math.abs(sections[i].x - sections[0].x)).toBeLessThan(1);
    }
    for (const section of sections) expect(section.scroll).toBeLessThanOrEqual(section.client + 1);
    await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/polish-populated-conditions-'+theme+'.png')});
    const citation=conditions.getByRole('region',{name:statement+' evidence',exact:true});
    await expect(citation.getByText('Supports', { exact: true })).toHaveCount(0);
    await expect(citation.locator('.hf-evidence-heading')).toContainText('Screening measurements');
    await citation.getByRole('button',{name:'View evidence',exact:true}).click();
    await expect(page.getByRole('dialog',{name:'Evidence detail',exact:true})).toContainText('The approximation applies within the measured operating range.');
    await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/polish-limit-evidence-'+theme+'.png')});
    await page.keyboard.press('Escape');
    await conditions.getByRole('button',{name:'Done',exact:true}).click();
  }
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();
  await fillCaseConfiguration(page,'Exact retained conditions');
  const original=await saveCaseConfiguration(page);
  expect(original.approach_closure.schema_version).toBe('3');
  // No separate conditions action on configurations; the retained approach shows them.
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  await retainedConditions(page,page.getByRole('region',{name:'Saved configuration',exact:true}));
  await expect(conditions).toContainText('Saved approach v2');await expect(conditions).toContainText(statement);
  await readingShot(page,'polish-configuration-conditions');
  await closeRetainedConditions(page);
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const runs=await helper.evaluate(async({data,original})=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');const sid=data.sid,o=original.configuration;
    async function retain(id:string){const run=await api.submitRun(sid,id);const response=await fetch('/fixture/retain-failure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({study_id:sid,run_id:run.run_id,key:data.fixture.key})});if(!response.ok)throw new Error(await response.text());return api.run(sid,run.run_id);}
    const pinned=await retain(o.configuration_revision_id);
    const configuration={schema_version:'3',study_id:sid,model_id:o.model_id,model_revision_id:o.model_revision_id,name:'Legacy configuration without approach',inputs:o.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),criteria:o.criteria,numerical:o.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(sid)).revision},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[]};
    const preview=await api.previewConfiguration3(configuration),legacy=await api.commitConfiguration3({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:preview.candidate_digest}),unpinned=await retain(legacy.configuration.configuration_revision_id);
    await c.open(sid);c.edit({...c.getSnapshot().local,assumptions:[],limit_items:[],steps:[],cases:[],model_bindings:[],question:'Later draft without the retained conditions'});if(!await c.save())throw new Error(c.getSnapshot().error);
    return {pinned,unpinned};
  },{data,original});await ctx.close();
  await page.route('**/approach**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'backend_unavailable',message:'Declared approach outage',fields:[],outcome:'unchanged'}})}));
  await openRetainedRun(page,data.sid,runs.pinned.run_id);
  // The run header has no study conditions; the retained approach in the Configuration tab keeps them.
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  await retainedConditions(page,page.getByRole('tabpanel',{name:'Configuration',exact:true}));
  await expect(conditions).toContainText('Saved approach v2');await expect(conditions).toContainText(statement);await expect(conditions).toContainText(data.proposal.statement);
  await expect(conditions).not.toContainText('Later draft');
  await readingShot(page,'polish-run-conditions');
  await closeRetainedConditions(page);
  await openRetainedRun(page,data.sid,runs.unpinned.run_id);
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  const unpinned=page.getByRole('tabpanel',{name:'Configuration',exact:true});
  await expect(unpinned).toContainText('No modeling approach is linked.');await expect(unpinned).not.toContainText(statement);
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  const missing=structuredClone(runs.pinned);missing.history.configuration=null;missing.history.approach_closure=null;
  await page.route('**/api/1/studies/'+data.sid+'/runs/'+runs.pinned.run_id,route=>route.fulfill({json:{schema_version:'1',data:missing}}));
  await openRetainedRun(page,data.sid,runs.pinned.run_id);
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();
  const missingTab=page.getByRole('tabpanel',{name:'Configuration',exact:true});
  await expect(missingTab).toContainText('This run\'s configuration can\'t be shown. The current configuration is not shown in its place.');
  await expect(missingTab).not.toContainText('No modeling approach is linked.');
  await expect(page.getByRole('region',{name:'Run details',exact:true})).not.toContainText(statement);
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  await readingShot(page,'polish-missing-retained-conditions');
  expect((await(await page.request.get('/api/1/studies/'+data.sid+'/configurations/'+original.configuration.configuration_revision_id)).json()).data).toEqual(original);
});

test('@approach-controller package4 reader preserves mixed exact definitions and rejects malformed packages',async({page})=>{
  await page.goto('/ui/');
  const original=await(await page.request.get('/fixture/model-package')).json();
  const result=await page.evaluate(async original=>{
    const {checkPackage,canonical,sha256,unresolvedModelUnits}=(window as any).approachHarness;
    const sign=async(value:any)=>{delete value.digest;value.digest=await sha256(new TextEncoder().encode(canonical(value)));return value;};
    async function pack(model:any,version:string){
      await sign(model);const files=[];
      async function add(path:string,raw:Uint8Array,media_type:string,role:string){const hash=(await sha256(new TextEncoder().encode('model-package-v1:'+path))).slice(0,32);files.push({file_id:[hash.slice(0,8),hash.slice(8,12),hash.slice(12,16),hash.slice(16,20),hash.slice(20)].join('-'),path,size:raw.length,sha256:await sha256(raw),media_type,role});}
      await add('revisions/'+model.model_revision_id+'.json',new TextEncoder().encode(canonical(model)),'application/json','model');
      for(const source of model.source_files)await add('sources/'+source.sha256+'.py',Uint8Array.from(atob(source.bytes),c=>c.charCodeAt(0)),'text/x-python','source');
      return sign({...original,schema_version:version,revisions:[model],files:files.sort((a,b)=>a.path<b.path?-1:1),required_capabilities:model.required_capabilities});
    }
    const old=await pack(structuredClone(original.revisions[0]),'2'),model=structuredClone(old.revisions[0]);
    model.schema_version='4';model.required_capabilities.push('quantity_definitions/1','unit_declarations/1');
    const definition=model.definitions.find((d:any)=>d.ports.length),retired=structuredClone(definition);
    definition.quantity_definitions=[{port_id:definition.ports[0].port_id,statement:'Imposed operating condition, not a numerical value.'}];
    // One legacy-string definition and one exact typed definition coexist.
    retired.definition_version_id=crypto.randomUUID();retired.ports=retired.ports.map((p:any)=>({...p,definition_version_id:retired.definition_version_id,units:{kind:'unspecified'}}));
    model.definitions.push(retired);model.ports=model.definitions.flatMap((d:any)=>d.ports);
    const pkg=await pack(model,'4'),accepted=await checkPackage(JSON.stringify(pkg)),oldAccepted=await checkPackage(JSON.stringify(old));
    const failures=[];
    for(const kind of ['unsupported','missing capability','unknown quantity port','duplicate quantity','blank statement','oversized statement','mixed unit kinds']){
      const bad=structuredClone(pkg),m=bad.revisions[0],d=m.definitions.find((v:any)=>v.quantity_definitions);
      if(kind==='unsupported')bad.schema_version='9';
      if(kind==='missing capability')bad.required_capabilities=bad.required_capabilities.filter((c:string)=>c!=='quantity_definitions/1');
      if(kind==='unknown quantity port')d.quantity_definitions[0].port_id=crypto.randomUUID();
      if(kind==='duplicate quantity')d.quantity_definitions.push(structuredClone(d.quantity_definitions[0]));
      if(kind==='blank statement')d.quantity_definitions[0].statement=' ';
      if(kind==='oversized statement')d.quantity_definitions[0].statement='x'.repeat(4097);
      if(kind==='mixed unit kinds')d.ports[0].units={kind:'dimensionless'};
      // Re-sign exact changed inventory so rejection exercises metadata, not just a stale hash.
      const changed=await pack(m,bad.schema_version);changed.required_capabilities=bad.required_capabilities;await sign(changed);
      try{await checkPackage(JSON.stringify(changed));failures.push(kind+' accepted');}catch{failures.push(kind+' rejected');}
    }
    const active=unresolvedModelUnits(accepted.revisions[0]);
    const switched=structuredClone(accepted.revisions[0]);switched.instances[1].definition_version_id=retired.definition_version_id;
    return {accepted,pkg,oldAccepted,old,failures,active,switched:unresolvedModelUnits(switched),ports:retired.ports.length};
  },original);
  expect(result.accepted).toEqual(result.pkg);expect(result.oldAccepted).toEqual(result.old);
  expect(result.active).toEqual([]);expect(result.switched).toHaveLength(result.ports);
  expect(result.failures).toEqual(['unsupported','missing capability','unknown quantity port','duplicate quantity','blank statement','oversized statement','mixed unit kinds'].map(k=>k+' rejected'));
});

test('@approach-assumptions model4 existing assumption editing preserves quantity metadata and command version',async({page,browser,baseURL})=>{
  await page.request.post('/fixture/model-available');
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const data=await helper.evaluate(async sid=>{
    const {api,canonical,sha256,checkPackage}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');
    const pkg=await(await fetch('/fixture/model-package')).json(),model=pkg.revisions[0],definition=model.definitions.find((d:any)=>d.ports.length);
    pkg.schema_version='4';model.schema_version='4';model.required_capabilities.push('quantity_definitions/1');pkg.required_capabilities=model.required_capabilities;
    definition.quantity_definitions=[{port_id:definition.ports[0].port_id,statement:'Imposed operating condition retained across assumption edits.'}];
    const sign=async(v:any)=>{delete v.digest;v.digest=await sha256(new TextEncoder().encode(canonical(v)));};await sign(model);
    const files=[];async function add(path:string,raw:Uint8Array,media_type:string,role:string){const key=(await sha256(new TextEncoder().encode('model-package-v1:'+path))).slice(0,32);files.push({file_id:[key.slice(0,8),key.slice(8,12),key.slice(12,16),key.slice(16,20),key.slice(20)].join('-'),path,size:raw.length,sha256:await sha256(raw),media_type,role});}
    await add('revisions/'+model.model_revision_id+'.json',new TextEncoder().encode(canonical(model)),'application/json','model');
    for(const source of model.source_files)await add('sources/'+source.sha256+'.py',Uint8Array.from(atob(source.bytes),c=>c.charCodeAt(0)),'text/x-python','source');
    pkg.files=files.sort((a,b)=>a.path<b.path?-1:1);await sign(pkg);await checkPackage(JSON.stringify(pkg));
    const imported=(await api.mutate('/studies/'+sid+'/model-imports',{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:pkg},'model',sid)).data;
    let refused='';try{await api.apply(imported,[{kind:'add_assumption',temp_key:'blocked_downgrade',owner:{kind:'model'},statement:'Should never be sent as version2.',evidence_links:[]}]);}catch(e){refused=String(e);}
    return {imported,refused,model};
  },sid);await ctx.close();
  expect(data.imported.schema_version).toBe('4');expect(data.refused).toContain('explicit version3 or version4');
  await page.evaluate(({sid,mid})=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'model',model:mid}).toString();},{sid,mid:data.model.model_id});
  // Model-wide assumptions are edited in the model view's Details with nothing selected.
  await expect(page.getByRole('button',{name:'Model actions',exact:true})).toBeVisible();await page.getByRole('button',{name:'Clear selection',exact:true}).click();
  const owner=page.getByRole('region',{name:'Selection inspector',exact:true});await expect(owner.getByRole('region',{name:'Model assumptions',exact:true})).toBeVisible();
  await owner.getByRole('button',{name:'Add assumption',exact:true}).click();await page.getByLabel('Statement',{exact:true}).fill('New explicit condition on the version4 model.');
  await page.getByRole('button',{name:'Apply assumption',exact:true}).click();
  const previewResponse=page.waitForResponse(r=>r.url().endsWith('/models/'+data.model.model_id+'/preview'));
  await owner.getByRole('button',{name:'Save model draft',exact:true}).click();const preview=await previewResponse;
  expect(preview.status(),await preview.text()).toBe(200);expect(preview.request().postDataJSON().schema_version).toBe('4');
  const unchanged=(await(await page.request.get('/api/1/studies/'+sid+'/models/'+data.model.model_id)).json()).data;expect(unchanged).toEqual(data.imported);
  const appliedResponse=page.waitForResponse(r=>r.url().endsWith('/models/'+data.model.model_id+'/edits'));
  await page.getByRole('dialog',{name:'Preview changes',exact:true}).getByRole('button',{name:'Apply changes',exact:true}).click();
  const applied=await appliedResponse;expect(applied.status(),await applied.text()).toBe(200);const command=applied.request().postDataJSON(),updated=(await applied.json()).data;
  expect(command.schema_version).toBe('4');expect(command.expected_revision).toBe(data.imported.draft_revision);expect(command.command_id).toBeTruthy();
  expect(updated.schema_version).toBe('4');expect(updated.definitions).toEqual(data.imported.definitions);expect(updated.assumptions).toContainEqual(expect.objectContaining({statement:'New explicit condition on the version4 model.'}));
});


test('@approach-reading paginated version revocation clears context and fences late pages',async({page,browser,baseURL})=>{
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  await helper.evaluate(async sid=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');
    for(let i=0;i<2;i++){await c.open(sid);c.edit({...c.getSnapshot().local,question:'Protected paginated question '+i});if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);}
  },sid);await context.close();
  let release!:()=>void,started=false,finished=false,calls=0;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/1/studies/'+sid+'/approach/versions?*',async route=>{
    const url=new URL(route.request().url());
    if(!url.searchParams.has('cursor')){url.searchParams.set('limit','1');await route.fulfill({response:await route.fetch({url:url.toString()})});return;}
    calls++;
    if(calls===1){await route.fulfill({status:404,json:{error:{code:'resource_not_found',message:'Undisclosed reference',fields:[],outcome:'unchanged'}}});return;}
    if(calls===2){const response=await route.fetch();started=true;await gate;await route.fulfill({response});finished=true;}
    else await route.continue();
  });
  await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Protected paginated question 1',exact:true})).toBeVisible();
  const more=page.getByRole('button',{name:'Load more versions',exact:true});
  await page.route('**/api/1/studies/'+sid,route=>route.abort(),{times:1});await more.click();
  await expect(page.getByText('Versions could not be loaded. Study access could not be verified. Retry the read.',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Protected paginated question 1',exact:true})).toBeVisible();
  await more.click();await expect.poll(()=>started).toBe(true);
  expect((await page.request.post('/fixture/revoke',{data:{study_id:sid}})).ok()).toBe(true);
  await more.click();
  try{await expect(page.getByRole('heading',{name:'Protected paginated question 1',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'See more details',exact:true})).toHaveCount(0);}
  finally{release();}
  await expect.poll(()=>finished).toBe(true);await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect(page.getByLabel('Approach version',{exact:true})).not.toContainText('read-only');await expect(more).toHaveCount(0);
});


test('@approach-reading Overview requires a saved approach and links its existing editor',async({page})=>{
  await openProduct(page);
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();
  // The Overview question box shows only the latest saved version; About keeps View modeling approach.
  const box=page.getByRole('region',{name:'Study question',exact:true});
  await expect(box).toContainText('No saved approach version is available.');await expect(box.getByRole('button',{name:'See more details',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Study conditions & limits',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Modeling approach',exact:true})).toBeVisible();
  // The heading renders before the approach read; wait for the read so the non-waiting check below is not a race.
  await expect(page.getByRole('button',{name:/^(Create modeling approach|Edit approach|Leave editing)$/}).first()).toBeVisible();
  if(await page.getByRole('button',{name:'Create modeling approach',exact:true}).isVisible())await page.getByRole('button',{name:'Create modeling approach',exact:true}).click();
  await writeQuestion(page,'Draft-only question must not become saved study context');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();
  await expect(box).toContainText('A draft is available, but no approach version has been saved.');
  await expect(box).not.toContainText('Draft-only question must not become saved study context');
  await expect(page.getByRole('dialog',{name:'Study details',exact:true})).toHaveCount(0);
  await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/cr03-overview-draft-only.png')});
});

test('@approach-reading Overview reads the exact saved version and fences outage and revoked reads',async({page,browser,baseURL})=>{
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  const saved=await helper.evaluate(async sid=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');await c.open(sid);
    c.edit({...c.getSnapshot().local,question:'Saved question A',assumptions:[{assumption_id:crypto.randomUUID(),statement:'Saved condition A',role:'overall_method',evidence_links:[]}],limit_items:[{limit_id:crypto.randomUUID(),statement:'Saved limit A',evidence_links:[]}]});
    if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);const saved=c.getSnapshot().saved;
    await c.open(sid);c.edit({...c.getSnapshot().local,question:'Draft question B',assumptions:[{assumption_id:crypto.randomUUID(),statement:'Draft condition B',role:'overall_method',evidence_links:[]}],limit_items:[{limit_id:crypto.randomUUID(),statement:'Draft limit B',evidence_links:[]}]});
    if(!await c.save())throw new Error(c.getSnapshot().error);return saved;
  },sid);await context.close();await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  const trigger=page.getByRole('button',{name:'See more details',exact:true}),dialog=page.getByRole('dialog',{name:'Study details',exact:true}),box=page.getByRole('region',{name:'Study question',exact:true});
  const exact='**/api/1/studies/'+sid+'/approach/versions/'+saved.version.approach_version_id;
  let reads=0,stateReads=0;page.on('request',request=>{if(request.url().endsWith('/approach/versions/'+saved.version.approach_version_id))reads++;if(request.url().endsWith('/studies/'+sid+'/approach'))stateReads++;});
  const overview=async()=>{await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'overview'}).toString();},sid);};
  const leave=async()=>{await page.getByRole('navigation',{name:'Workspace sections'}).getByRole('button',{name:'Models',exact:true}).click();await expect(page.getByRole('heading',{name:'Models',exact:true})).toBeVisible();};
  // The Overview question box reads the latest saved version when Overview opens; never the draft.
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();
  await expect(box.getByRole('heading',{name:'Saved question A',exact:true})).toBeVisible();await expect(box).not.toContainText('Draft question B');expect(reads).toBe(1);
  await trigger.click();await expect(dialog).toContainText('Current saved approach v1');await expect(dialog).toContainText('Saved condition A');await expect(dialog).toContainText('Saved limit A');await expect(dialog).not.toContainText('Draft condition B');expect(reads).toBe(1);
  await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/cr03-overview-saved-light.png')});
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/cr03-overview-saved-dark.png')});
  await dialog.getByRole('button',{name:'Done',exact:true}).click();
  // An outage of the exact version is named; a retry re-reads only that version.
  await leave();
  // The exact version stays unavailable until the reader explicitly retries.
  // An earlier in-flight read cannot consume the outage intended for Overview.
  const outage: Parameters<Page['route']>[1] = route => route.fulfill({
    status: 503,
    json: {error: {
      code: 'backend_unavailable', message: 'Exact saved approach is temporarily unavailable',
      fields: [], outcome: 'unchanged',
    }},
  });
  await page.route(exact, outage);
  await overview();await expect(box.getByRole('alert')).toContainText('The study question is temporarily unavailable. Retry this read.');await expect(box).not.toContainText('Saved question A');await expect(box).not.toContainText('Draft question B');await expect(trigger).toHaveCount(0);
  await page.unroute(exact, outage);
  const priorStateReads=stateReads,priorVersionReads=reads;await box.getByRole('button',{name:'Retry study question',exact:true}).click();await expect(box.getByRole('heading',{name:'Saved question A',exact:true})).toBeVisible();expect(stateReads).toBe(priorStateReads);expect(reads).toBe(priorVersionReads+1);
  // A reply that arrives after leaving Overview is discarded.
  let release!:()=>void,started=false,finished=false;const gate=new Promise<void>(resolve=>{release=resolve;});
  await leave();await page.route(exact,async route=>{const response=await route.fetch();started=true;await gate;try{await route.fulfill({response});}catch{/* the product aborts the read */}finally{finished=true;}},{times:1});
  await overview();await expect.poll(()=>started).toBe(true);await leave();release();await expect.poll(()=>finished).toBe(true);await expect(page.getByText('Saved question A',{exact:true})).toHaveCount(0);await expect(dialog).toHaveCount(0);
  // Access revoked while the exact read is in flight: the confirmed denial clears the box; nothing protected remains.
  let resume!:()=>void,held=false;const hold=new Promise<void>(resolve=>{resume=resolve;});
  await page.route(exact,async route=>{held=true;await hold;await route.continue();},{times:1});
  await overview();await expect.poll(()=>held).toBe(true);
  expect((await page.request.post('/fixture/revoke',{data:{study_id:sid}})).ok()).toBe(true);resume();
  await expect(box.getByRole('alert')).toHaveText('Access to this resource is no longer available.');await expect(box).not.toContainText('Saved question A');await expect(box).not.toContainText('Draft question B');await expect(trigger).toHaveCount(0);
});


test('@approach-assumptions Overview uses retained evidence after the current draft changes',async({page,browser,baseURL})=>{
  await page.request.post('/fixture/model-available');
  const data=await seededConditions(page,browser,baseURL);
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  await helper.evaluate(async sid=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');await c.open(sid);
    c.edit({...c.getSnapshot().local,assumptions:c.getSnapshot().local.assumptions.map((a:any)=>({...a,statement:'Unpublished replacement condition B',evidence_links:[]}))});
    if(!await c.save())throw new Error(c.getSnapshot().error);
  },data.sid);await context.close();await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();
  let evidenceReads=0;page.on('request',r=>{if(r.url().includes('/evidence/'))evidenceReads++;});
  await page.getByRole('button',{name:'See more details',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Study details',exact:true});await expect(dialog).toContainText('Current saved approach v1');await expect(dialog).toContainText(data.proposal.statement);await expect(dialog).not.toContainText('Unpublished replacement condition B');await expect(dialog).toContainText('Screening measurements');
  await expect(dialog).toContainText('Proposed condition');
  await expect(dialog).not.toContainText('Proposed model condition');
  await expect(
    dialog.getByText('Version ' + data.evidence.evidence_version_id.slice(0, 8), { exact: true }),
  ).not.toBeVisible();
  await expect(dialog.getByText('Supports', { exact: true })).toHaveCount(0);
  await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence/cr03-overview-retained-citation.png')});
  await dialog.getByRole('button',{name:'View evidence',exact:true}).click();await expect(page.getByRole('dialog',{name:'Evidence detail',exact:true})).toContainText(data.evidence.content);expect(evidenceReads).toBe(0);
  const evidence = page.getByRole('dialog', { name: 'Evidence detail', exact: true });
  await expect(evidence).toContainText('Version ' + data.evidence.evidence_version_id.slice(0, 8));
  await expect(evidence).toContainText('Relationship to this statement: supports');
});

test('@approach-method Method map and detail preserve proposed intent without invented quantities',async({page})=>{
  await openProduct(page);await writeQuestion(page);
  await expect(page.getByRole('heading',{name:'How the method fits together',exact:true})).toBeVisible();
  await expect(page.getByText('No method steps',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Add method step',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Method step',exact:true});
  await editor.getByLabel('Step title',{exact:true}).fill('Unimplemented sensitivity study');
  await editor.getByLabel('Intended transformation',{exact:true}).fill('Explore the declared uncertainty');
  await editor.getByRole('button',{name:'Apply step',exact:true}).click();
  const detail=page.getByRole('region',{name:'Selected method step',exact:true});
  await expect(detail.getByRole('tab',{name:'Explanation',exact:true})).toBeVisible();
  await expect(detail).toContainText('Proposed work — no model linked. No calculation is implied.');
  await expect(detail).toContainText('Explore the declared uncertainty');
  await expect(detail.getByRole('button',{name:'Open model version',exact:true})).toHaveCount(0);
  // Two tabs; proposed intent stays prose and no quantities are invented.
  await expect(detail.getByRole('tab')).toHaveText(['Explanation','Assumptions & evidence']);await expect(detail).not.toContainText('Implemented in Model version');
  await detail.getByRole('tab',{name:'Assumptions & evidence',exact:true}).click();
  await readingShot(page,'polish-method-proposed-assumptions');
  await detail.getByRole('tab',{name:'Explanation',exact:true}).click();
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'polish-method-proposed-'+theme);}
});


/** One retained Model4 with two component instances of one definition. By
 * default the second instance uses a later definition version with identical
 * port IDs. shared keeps both instances on one version; faults adds undecodable
 * retained bytes and a later exact revision whose referenced source is absent. */
async function describedApproach(page:Page,browser:any,baseURL:string|undefined,options:{shared?:boolean;faults?:boolean}={}){
  // An earlier scenario may leave the declared private modeling double offline.
  expect((await page.request.post('/fixture/model-available')).ok()).toBe(true);
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const other=await browser.newContext({baseURL}),helper=await other.newPage();await helper.goto('/ui/');
  const data=await helper.evaluate(async ({sid,options})=>{
    const h=(window as any).approachHarness,api=h.api;await api.login('owner','correct horse battery staple');
    const enc=(text:string)=>new TextEncoder().encode(text),bytes=(s:any)=>Uint8Array.from(atob(s.bytes),c=>c.charCodeAt(0));
    const seal=async(value:any)=>{const copy={...value};delete copy.digest;value.digest=await h.sha256(enc(h.canonical(copy)));};
    const pkg=await(await fetch('/fixture/model-package')).json(),m=pkg.revisions[0],d=m.definitions[1];
    // Human names differ from the exact source symbols.
    const names:Record<string,string>={x:'Operating condition',z:'Secondary condition',u:'Response sum',v:'Response difference'};
    d.ports.forEach((p:any)=>{p.name=names[p.code_symbol];});
    m.schema_version='4';m.required_capabilities.push('quantity_definitions/1');
    d.quantity_definitions=d.ports.map((p:any)=>({port_id:p.port_id,statement:'Original definition of '+p.code_symbol}));
    const raw='# Second retained file; inert in the browser.\nresult = 42\n';
    m.source_files.push({sha256:await h.sha256(enc(raw)),bytes:btoa(raw),encoding:'base64',media_type:'text/x-python'});d.source_refs.push(m.source_files[1].sha256);
    if(options.faults){const invalid=new Uint8Array([0xff,0xfe,0x00,0x41]);m.source_files.push({sha256:await h.sha256(invalid),bytes:btoa(String.fromCharCode(...invalid)),encoding:'base64',media_type:'text/x-python'});d.source_refs.push(m.source_files[2].sha256);}
    const next=structuredClone(d);next.definition_version_id=crypto.randomUUID();next.ports.forEach((p:any)=>p.definition_version_id=next.definition_version_id);next.quantity_definitions[0].statement='Revised definition of x';m.definitions.push(next);
    if(!options.shared)m.instances[2].definition_version_id=next.definition_version_id;
    m.ports=m.definitions.flatMap((x:any)=>x.ports);await seal(m);
    const revisions=[m];let branch=null;
    if(options.faults){
      const b=structuredClone(m),bd=structuredClone(d);b.model_revision_id=crypto.randomUUID();b.parent_model_revision_id=m.model_revision_id;b.originating_draft_revision=crypto.randomUUID();
      bd.definition_version_id=crypto.randomUUID();bd.ports.forEach((p:any)=>p.definition_version_id=bd.definition_version_id);bd.quantity_definitions[0].statement='Branch definition of x';
      bd.source_refs=[await h.sha256(enc('# Referenced but never retained\n'))];b.definitions.push(bd);b.instances[1].definition_version_id=bd.definition_version_id;
      b.ports=b.definitions.flatMap((x:any)=>x.ports);await seal(b);revisions.push(b);branch=b;
    }
    const files=new Map<string,any>(),add=async(path:string,raw:Uint8Array,role:string,media:string)=>{files.set(path,{file_id:crypto.randomUUID(),path,size:raw.length,sha256:await h.sha256(raw),role,media_type:media});};
    for(const r of revisions){await add('revisions/'+r.model_revision_id+'.json',enc(h.canonical(r)),'model','application/json');for(const s of r.source_files)await add('sources/'+s.sha256+'.py',bytes(s),'source',s.media_type);}
    pkg.schema_version='4';pkg.revisions=revisions;pkg.model_revision_id=revisions[revisions.length-1].model_revision_id;pkg.required_capabilities=m.required_capabilities;pkg.files=[...files.values()];await seal(pkg);
    await api.mutate(`/studies/${sid}/model-imports`,{command_id:crypto.randomUUID(),expected_revision:(await api.study(sid)).revision,package:pkg},'model',sid);
    const c=h.controller;await c.open(sid);const content=structuredClone(c.getSnapshot().local),binding={binding_id:crypto.randomUUID(),model_id:m.model_id,model_revision_id:m.model_revision_id};
    content.question='How does the declared response depend on the operating quantities?';content.model_bindings=[binding];content.steps=[{step_id:crypto.randomUUID(),title:'Predict response',purpose:'Connect explicit operating quantities to response.',rationale:'Use the declared response law for a bounded screening.',remaining_work:'',intent:{transformation:'Combine the operating quantities using the authored response law.',inputs:'',outputs:'',depends_on_step_ids:[]},implementation_state:'linked',implementation_refs:[{kind:'model',binding_id:binding.binding_id}],assumption_refs:[],evidence_links:[]}];c.edit(content);if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);
    return {sid,model:m,branch,saved:c.getSnapshot().saved};
  },{sid,options});await other.close();
  await page.goto('/ui/?workspace#'+new URLSearchParams({v:'1',view:'approach',study:sid,approach:data.saved.version.approach_version_id}));
  // A hash-only goto keeps the document; reloading clears the memory-only session and stale local draft.
  await page.reload();
  await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);
  return data;
}
const quantityRow=(page:Page,table:any,instance:string,symbol:string)=>table.getByRole('row').filter({hasText:instance}).filter({has:page.locator('code').filter({hasText:new RegExp('^'+symbol+'$')})});
/** One row of the canonical quantities table, by its owning component (not by "from …" text). */
const viewRow=(page:Page,table:any,instance:string,symbol:string)=>table.getByRole('row').filter({has:page.getByRole('button',{name:'Inspect component '+instance,exact:true})}).filter({has:page.locator('code').filter({hasText:new RegExp('^'+symbol+'$')})});

test('@approach-method exact quantity occurrences and every source stay pinned in saved reading',async({page,browser,baseURL})=>{
  const data=await describedApproach(page,browser,baseURL),detail=page.getByRole('region',{name:'Selected method step',exact:true}),id8=data.model.model_revision_id.slice(0,8);
  await expect(page.getByRole('button',{name:'Add method step',exact:true})).toHaveCount(0);
  // One exact binding needs no redundant selector.
  await expect(detail.getByLabel('Approach model version',{exact:true})).toHaveCount(0);
  // One implementation line instead of quantity cards, no source excerpt.
  await expect(detail.getByRole('tab')).toHaveText(['Explanation','Assumptions & evidence']);
  await expect(detail).toContainText('Implemented in Model version '+id8+' · 4 inputs · 4 outputs');
  await expect(detail.getByRole('region',{name:'Referenced inputs',exact:true})).toHaveCount(0);await expect(detail.getByRole('region',{name:'Source excerpt',exact:true})).toHaveCount(0);await expect(detail.getByRole('button',{name:'View exact source',exact:true})).toHaveCount(0);
  await expect(detail).toContainText('Combine the operating quantities using the authored response law.');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'polish-method-saved-'+theme);}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  // Open model version: the canonical view, every exact quantity occurrence once.
  const opener=detail.getByRole('button',{name:'Open model version',exact:true});await opener.focus();await opener.press('Enter');
  const open=page.getByRole('dialog',{name:'Model version '+id8,exact:true}),table=open.getByRole('table',{name:'Quantities',exact:true});
  await expect(table.getByRole('row')).toHaveCount(9);
  // The human name and the exact source symbol are distinct facts in one row.
  const first=viewRow(page,table,'Response · instance 1','x');await expect(first).toContainText('Operating condition');await expect(first.locator('code')).toHaveText('x');
  // Identical port IDs in two definition versions remain two exact occurrences.
  await expect(first).toContainText('Original definition of x');
  await expect(viewRow(page,table,'Response · instance 2','x')).toContainText('Revised definition of x');
  await expect(viewRow(page,table,'Response · instance 2','z')).toContainText('Original definition of z');
  await readingShot(page,'polish-method-all-quantities');
  // Every source file of the component version, each checked against its SHA256 and shown as text only.
  await open.getByRole('button',{name:'1 Response',exact:true}).click();await open.getByRole('button',{name:'View source',exact:true}).click();
  const source=page.getByRole('dialog',{name:'Source · Response · instance 1',exact:true});
  await expect(source.getByLabel('Read-only authored source')).toHaveCount(2);await expect(source.getByLabel('Read-only authored source').first()).toContainText("outputs['u'] = inputs['x'] + inputs['z']");
  await expect(source.getByLabel('Read-only authored source').last()).toHaveText('# Second retained file; inert in the browser.\nresult = 42\n');
  await expect(source).toContainText('File 2 of 2 · SHA-256 '+data.model.source_files[1].sha256);await expect(source).toContainText('SHA-256 '+data.model.source_files[0].sha256);
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'polish-method-exact-source-'+theme);}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  await source.getByRole('button',{name:'Done',exact:true}).click();await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
  await detail.getByRole('tab',{name:'Assumptions & evidence',exact:true}).click();await readingShot(page,'polish-method-saved-assumptions');
  await page.setViewportSize({width:720,height:1000});await detail.getByRole('tab',{name:'Explanation',exact:true}).click();await readingShot(page,'polish-method-saved-720');expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(720);
});

/** Evidence: 1440 x 1000 and 720 px light/dark, and 200 percent (720 CSS px at device scale 2), without horizontal overflow. */
async function s4Shots(page:Page,name:string,target?:Locator){
  const cdp=await page.context().newCDPSession(page);
  try{
    for(const [size,metrics] of [['1440',{width:1440,height:1000,deviceScaleFactor:1,mobile:false}],['720',{width:720,height:1000,deviceScaleFactor:1,mobile:false}],['200',{width:720,height:500,deviceScaleFactor:2,mobile:false}]] as const){
      await cdp.send('Emulation.setDeviceMetricsOverride',metrics);
      for(const theme of ['light','dark']){
        await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
        if(target)await target.evaluate(element=>element.scrollIntoView({block:'start'}));
        await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
        // Theme changes animate Foundry controls; capture only after every transition has finished.
        await expect.poll(()=>page.evaluate(()=>document.getAnimations().every(a=>a.playState!=='running'))).toBe(true);
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' '+size).toBe(true);
        const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
        await writeFile(join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence',name+'-'+size+'-'+theme+'.png'),Buffer.from(shot.data,'base64'));
      }
    }
  }finally{await cdp.send('Emulation.clearDeviceMetricsOverride');await cdp.detach();await page.evaluate(()=>document.documentElement.dataset.theme='light');}
}

test('@approach-method canonical model view explains each component with its linked method step and lists quantities once',async({page,browser,baseURL})=>{
  test.setTimeout(120000);
  const data=await describedApproach(page,browser,baseURL),detail=page.getByRole('region',{name:'Selected method step',exact:true});
  await page.setViewportSize({width:1440,height:1000});
  // Approach "Open model version": the canonical view, read-only, with the step's components in focus.
  await detail.getByRole('button',{name:'Open model version',exact:true}).click();
  const open=page.getByRole('dialog',{name:'Model version '+data.model.model_revision_id.slice(0,8),exact:true}),view=open.getByRole('region',{name:'Model view',exact:true});
  await expect(view.getByRole('tab',{name:'Graph',exact:true})).toHaveAttribute('aria-selected','true');await expect(view.getByRole('tab',{name:'XDSM',exact:true})).toBeVisible();
  await expect(view.getByRole('tab',{name:'Variables',exact:true})).toHaveCount(0);
  await expect(view.getByRole('button',{name:'＋ Component',exact:true})).toHaveCount(0);
  const quantities=view.getByRole('table',{name:'Quantities',exact:true});
  await expect(quantities.getByRole('columnheader')).toHaveText(['Quantity','Component','Direction','Definition','Unit']);
  await open.getByRole('button',{name:'1 Response',exact:true}).click();
  const details=view.getByRole('region',{name:'Selection inspector',exact:true});
  await expect(details.getByRole('heading',{name:'What it computes',exact:true})).toBeVisible();
  await expect(details).toContainText('Combine the operating quantities using the authored response law.');
  await expect(details.getByRole('heading',{name:'Why',exact:true})).toBeVisible();
  await expect(details).toContainText('Connect explicit operating quantities to response.');await expect(details).toContainText('Use the declared response law for a bounded screening.');
  await expect(details).toContainText('Method step 1 · Predict response · Approach version '+data.saved.version.version_number);
  await expect(details.getByRole('heading',{name:'Assumptions',exact:true})).toBeVisible();
  // No ports table, no incoming/outgoing lists, no notes: quantities are listed once, below.
  await expect(details.locator('table')).toHaveCount(0);await expect(details.getByText(/^(Incoming|Outgoing) quantities/)).toHaveCount(0);await expect(details.getByRole('tab')).toHaveCount(0);
  await expect(view.getByText(/^Showing 4 of \d+ quantities · Response · instance 1$/)).toBeVisible();
  const row=quantityRow(page,quantities,'Response · instance 1','x');await expect(row).toContainText('Original definition of x');await expect(row).toContainText('Input');await expect(row).toContainText('Dimensionless');
  await expect(row).toHaveAttribute('aria-selected','true');
  await s4Shots(page,'s4-approach-open-model-version',view);
  await view.getByRole('button',{name:'Show all quantities',exact:true}).click();await expect(view.getByText(/^Showing (\d+) of \1 quantities$/)).toBeVisible();
  await expect(quantityRow(page,quantities,'Response · instance 2','x')).toContainText('Revised definition of x');
  await details.getByRole('button',{name:'View source',exact:true}).click();
  const source=page.getByRole('dialog',{name:'Source · Response · instance 1',exact:true});
  await expect(source).toContainText('Shown as text; never run.');await expect(source).toContainText('SHA-256 '+data.model.source_files[0].sha256);
  await expect(source.getByLabel('Read-only authored source').filter({hasText:"outputs['u'] = inputs['x'] + inputs['z']"})).toBeVisible();
  await source.getByRole('button',{name:'Done',exact:true}).click();
  // The link returns to the exact step of this approach version.
  await details.getByRole('button',{name:'Open step 1 in modeling approach →',exact:true}).click();
  await expect(open).toBeHidden();await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toHaveAttribute('aria-pressed','true');
  // Models: the same view; the latest saved approach version explains the draft's components.
  await page.evaluate(({sid,mid})=>{location.hash=new URLSearchParams({v:'1',view:'model',study:sid,model:mid}).toString();},{sid:data.sid,mid:data.model.model_id});
  const models=page.getByRole('region',{name:'Model view',exact:true}),md=models.getByRole('region',{name:'Selection inspector',exact:true});
  await expect(md.getByRole('button',{name:'Edit ports',exact:true})).toBeVisible();
  await expect(md).toContainText('Use the declared response law for a bounded screening.');
  await expect(md).toContainText('linked to Model version '+data.model.model_revision_id.slice(0,8));
  await expect(md.getByText('Edit source',{exact:true})).toBeVisible();await expect(md.locator('table')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Model actions',exact:true})).toBeVisible();
  await s4Shots(page,'s4-models-component',md);
  await models.getByRole('tab',{name:'XDSM',exact:true}).click();await expect(models.getByRole('region',{name:'Component exchange matrix',exact:true})).toBeVisible();
  await s4Shots(page,'s4-models-xdsm',models);
  await models.getByRole('tab',{name:'Graph',exact:true}).click();
  // Nothing selected: the model and its own assumptions (Add assumption in a draft).
  await page.getByRole('button',{name:'Clear selection',exact:true}).click();
  await expect(md.getByRole('heading',{name:'Model',exact:true})).toBeVisible();
  const own=md.getByRole('region',{name:'Model assumptions',exact:true});await expect(own.getByRole('button',{name:'Add assumption',exact:true})).toBeVisible();
  await expect(md).toContainText('select a component to see what it computes and why');
  await expect(models.getByRole('button',{name:'Show all quantities',exact:true})).toHaveCount(0);
  await s4Shots(page,'s4-models-nothing-selected',md);
  // The former ⋯ › Model assumptions dialog is gone; Model actions keep rename, reload and import/compare.
  await page.getByRole('button',{name:'Model actions',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Model actions',exact:true}).getByRole('button',{name:'Model assumptions',exact:true})).toHaveCount(0);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'1 Response',exact:true}).click();
  await md.getByRole('button',{name:'Open step 1 in modeling approach →',exact:true}).click();
  await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toHaveAttribute('aria-pressed','true');
  expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('approach')).toBe(data.saved.version.approach_version_id);
});
test('@approach-method model-owned description edit rebinds only the selected instance while the saved approach keeps its exact definition',async({page,browser,baseURL})=>{
  const data=await describedApproach(page,browser,baseURL,{shared:true}),m=data.model,d=m.definitions[1];
  // Navigation is refused while the approach reader is still loading its exact version.
  await expect(page.getByRole('region',{name:'Selected method step',exact:true})).toContainText('Implemented in Model version '+m.model_revision_id.slice(0,8));
  const commands:any[]=[];page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname.endsWith('/models/'+m.model_id+'/edits'))commands.push(request.postDataJSON());});
  await page.evaluate(({sid,mid})=>{location.hash=new URLSearchParams({v:'1',view:'model',study:sid,model:mid}).toString();},{sid:data.sid,mid:m.model_id});
  await page.getByRole('tab',{name:'Graph',exact:true}).click();await page.locator('[data-instance="'+m.instances[1].instance_id+'"]').first().click();
  await page.getByRole('button',{name:'Edit ports',exact:true}).click();const ports=page.getByRole('dialog',{name:'Edit ports',exact:true});
  await expect(ports.getByLabel('Port 1 definition',{exact:true})).toHaveValue('Original definition of x');
  await ports.getByLabel('Port 1 definition',{exact:true}).fill('Updated descriptive meaning for the selected instance');await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Save component',exact:true}).click();const preview=page.getByRole('dialog',{name:'Preview changes',exact:true});
  await expect(preview).toContainText('Response · instance 1 · quantity definitions');await expect(preview).not.toContainText('Response · instance 2 · quantity definitions');
  await expect(preview).toContainText('x: Original definition of x');await expect(preview).toContainText('x: Updated descriptive meaning for the selected instance');
  // A description-only edit changes neither ports nor source.
  await expect(preview).not.toContainText('· ports');await expect(preview).not.toContainText('· source');
  await readingShot(page,'polish-quantity-definition-preview');await preview.getByRole('button',{name:'Apply changes',exact:true}).click();await expect(preview).not.toBeVisible();
  expect(commands).toHaveLength(1);
  expect(commands[0].edits).toEqual([
    {kind:'revise_definition',temp_key:'revised',definition_id:d.definition_id,expected_definition_version_id:d.definition_version_id,changes:[{kind:'set_quantity_definition',port_id:d.ports[0].port_id,statement:'Updated descriptive meaning for the selected instance'}]},
    {kind:'replace_local_instance_version',instance_id:m.instances[1].instance_id,expected_definition_version_id:d.definition_version_id,version_ref:{temp_key:'revised'}}]);
  const draft=(await(await page.request.get(`/api/1/studies/${data.sid}/models/${m.model_id}`)).json()).data;
  const revised=draft.definitions.find((x:any)=>x.definition_version_id===draft.instances[1].definition_version_id);
  expect(draft.instances[1].definition_version_id).not.toBe(d.definition_version_id);expect(draft.instances[2].definition_version_id).toBe(d.definition_version_id);
  expect(revised.ports.map((p:any)=>[p.port_id,p.direction,p.name,p.code_symbol,p.units])).toEqual(d.ports.map((p:any)=>[p.port_id,p.direction,p.name,p.code_symbol,p.units]));
  expect(revised.source_refs).toEqual(d.source_refs);expect(draft.source_files).toEqual(m.source_files);
  // The quantities table sits below the canvas, scoped to the selected component until Show all quantities.
  await page.getByRole('button',{name:'Show all quantities',exact:true}).click();const variables=page.getByRole('table',{name:'Quantities',exact:true});
  await expect(variables.getByRole('row').filter({has:page.getByRole('button',{name:'Inspect component Response · instance 1',exact:true})}).filter({has:page.locator('code').filter({hasText:/^x$/})})).toContainText('Updated descriptive meaning for the selected instance');
  await expect(variables.getByRole('row').filter({has:page.getByRole('button',{name:'Inspect component Response · instance 2',exact:true})}).filter({has:page.locator('code').filter({hasText:/^x$/})})).toContainText('Original definition of x');
  await page.evaluate(({sid,id})=>{location.hash=new URLSearchParams({v:'1',view:'approach',study:sid,approach:id}).toString();},{sid:data.sid,id:data.saved.version.approach_version_id});await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);
  const detail=page.getByRole('region',{name:'Selected method step',exact:true});
  // Definitions are read in the step's model version, which keeps its exact definition.
  await detail.getByRole('button',{name:'Open model version',exact:true}).click();const open=page.getByRole('dialog',{name:'Model version '+m.model_revision_id.slice(0,8),exact:true});
  await expect(viewRow(page,open.getByRole('table',{name:'Quantities',exact:true}),'Response · instance 1','x')).toContainText('Original definition of x');await expect(open).not.toContainText('Updated descriptive meaning for the selected instance');await page.keyboard.press('Escape');
  const retained=(await(await page.request.get(`/api/1/studies/${data.sid}/approach/versions/${data.saved.version.approach_version_id}`)).json()).data;expect(retained).toEqual(data.saved);
});

test('@approach-method several exact model versions need an explicit choice and absent or undecodable source stays named',async({page,browser,baseURL})=>{
  const data=await describedApproach(page,browser,baseURL,{faults:true}),m=data.model,b=data.branch,detail=page.getByRole('region',{name:'Selected method step',exact:true});
  // Source is read in the canonical model view (View source); undecodable bytes stay named, never shown.
  await detail.getByRole('button',{name:'Open model version',exact:true}).click();let open=page.getByRole('dialog',{name:'Model version '+m.model_revision_id.slice(0,8),exact:true});
  await open.getByRole('button',{name:'1 Response',exact:true}).click();await open.getByRole('button',{name:'View source',exact:true}).click();
  let source=page.getByRole('dialog',{name:'Source · Response · instance 1',exact:true});
  await expect(source.getByRole('alert')).toContainText('not valid UTF-8 text');await expect(source).toContainText(m.source_files[2].sha256);await expect(source.locator('pre')).toHaveCount(2);
  await readingShot(page,'polish-method-source-undecodable');
  await source.getByRole('button',{name:'Done',exact:true}).click();await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await page.getByRole('button',{name:'Edit step 1',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Method step',exact:true});
  await editor.getByLabel('Implementation model',{exact:true}).selectOption(m.model_id);await editor.getByLabel('Implementation model version',{exact:true}).selectOption(b.model_revision_id);
  await editor.getByRole('group',{name:'Model elements',exact:true}).getByRole('checkbox',{name:'Whole model',exact:true}).check();
  await editor.getByRole('button',{name:'Apply step',exact:true}).click();
  // Two exact bindings: nothing is selected or shown until the reader chooses.
  const choice=detail.getByLabel('Approach model version',{exact:true});await expect(choice).toHaveValue('');
  await expect(detail).toContainText('This step references 2 model versions.');await expect(detail).not.toContainText('Implemented in Model version');
  await expect(detail.getByRole('button',{name:'Open model version',exact:true})).toHaveCount(0);
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'polish-method-multiple-binding-'+theme);}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  const label=(r:any)=>'Response investigation · version '+r.model_revision_id.slice(0,8);
  const rowX=async(r:any,text:string,absent?:string)=>{await detail.getByRole('button',{name:'Open model version',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Model version '+r.model_revision_id.slice(0,8),exact:true});await expect(viewRow(page,dialog.getByRole('table',{name:'Quantities',exact:true}),'Response · instance 1','x')).toContainText(text);if(absent)await expect(dialog).not.toContainText(absent);await page.keyboard.press('Escape');};
  await choice.selectOption({label:label(b)});await expect(detail).toContainText('Implemented in Model version '+b.model_revision_id.slice(0,8));await rowX(b,'Branch definition of x');
  await choice.selectOption({label:label(m)});await rowX(m,'Original definition of x','Branch definition of x');
  await choice.selectOption({label:label(b)});
  await detail.getByRole('button',{name:'Open model version',exact:true}).click();open=page.getByRole('dialog',{name:'Model version '+b.model_revision_id.slice(0,8),exact:true});
  await open.getByRole('button',{name:'1 Response',exact:true}).click();await open.getByRole('button',{name:'View source',exact:true}).click();source=page.getByRole('dialog',{name:'Source · Response · instance 1',exact:true});
  await expect(source.getByRole('alert')).toContainText('This source file is missing from the model version.');await expect(source).toContainText(b.definitions[b.definitions.length-1].source_refs[0]);await expect(source.locator('pre')).toHaveCount(0);
  await readingShot(page,'polish-method-source-missing');
});

test('@approach-method definition owner navigation returns to the same step tab and focus',async({page,browser,baseURL})=>{
  const data=await describedApproach(page,browser,baseURL),detail=page.getByRole('region',{name:'Selected method step',exact:true});
  await expect(detail).toContainText('Original definition of x');
  // Reading offers no owner editing control. In edit mode it sits on the implementation line in Explanation.
  await expect(detail.getByRole('button',{name:'Edit definitions in model',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Edit approach',exact:true}).click();await expect(detail.getByRole('tab',{name:'Explanation',exact:true})).toHaveAttribute('aria-selected','true');
  await detail.getByRole('button',{name:'Edit definitions in model',exact:true}).click();const owner=page.getByRole('dialog',{name:'Edit definitions at their owner',exact:true});
  await expect(owner).toContainText('keeps model version '+data.model.model_revision_id.slice(0,8));await owner.getByRole('button',{name:'Open current model draft',exact:true}).click();
  await expect(page.getByRole('tab',{name:'Graph',exact:true})).toBeVisible();
  await page.goBack();
  await expect(detail.getByRole('tab',{name:'Explanation',exact:true})).toHaveAttribute('aria-selected','true');
  await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toBeFocused();
});

// The configuration approach picker must not retain protected approach
// context after a confirmed concealed denial. Actual public API, membership and auth.
const pickerProtected=['Why use the scalar response approximation?','The response is approximately linear in the measured range.','Screening measurements','Upper operating range','Second saved interpretation'];
const notFoundReply={status:404,json:{error:{code:'resource_not_found',message:'Undisclosed reference',fields:[],outcome:'unchanged'}}};
async function settle(page:Page){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));}
function heldReply(rewrite?:(value:any)=>any){
  let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;}),state={started:false,finished:false,release:()=>release()};
  const handler=async(route:any)=>{const response=await route.fetch();state.started=true;await gate;try{if(rewrite)await route.fulfill({response,json:rewrite(await response.json())});else await route.fulfill({response});}catch{/* the product may abort the request */}finally{state.finished=true;}};
  return {state,handler};
}
async function linkedPicker(page:Page,browser:any,baseURL:string|undefined,options:{second?:boolean}={}){
  const data=await seededConditions(page,browser,baseURL,{cases:true,...options});
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);await casesTab(page);return data;
}
async function createLinked(page:Page,loaded=true){
  await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await expect(page.getByLabel('Configuration name',{exact:true})).toBeVisible();
  if(loaded)await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Why use the scalar response approximation?');
}
const revoke=async(page:Page,sid:string)=>expect((await page.request.post('/fixture/revoke',{data:{study_id:sid}})).ok()).toBe(true);
const picker=(page:Page)=>page.getByRole('dialog',{name:'Choose modeling approach',exact:true});
async function expectPickerCleared(page:Page){
  for(const text of pickerProtected)await expect(page.getByText(text),text).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toHaveCount(0);
  await expect(page.getByLabel('Intended case',{exact:true})).toHaveCount(0);
  await expect(picker(page).getByLabel('Saved approach version',{exact:true}).locator('option')).toHaveCount(1);
  await expect(picker(page).getByRole('button',{name:'Load more approach versions',exact:true})).toHaveCount(0);
  await expect(page.getByText('Access to this resource is no longer available.',{exact:true}).first()).toBeVisible();
}
async function expectPinRetained(page:Page,commits:string[]){
  await picker(page).getByRole('button',{name:'Keep current choice',exact:true}).click();await expect(picker(page)).not.toBeVisible();
  await expect(page.getByText('The linked modeling approach could not be loaded. The link to its version is unchanged.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Remove approach link',exact:true})).toBeVisible();
  for(const text of pickerProtected)await expect(page.getByText(text),text).toHaveCount(0);
  expect(commits).toEqual([]);
}
function watchCommits(page:Page){const commits:string[]=[];page.on('request',r=>{const path=new URL(r.url()).pathname;if(r.method()!=='GET'&&/\/(configurations|commands)(\/|$)/.test(path)&&!/\/preview$/.test(path))commits.push(r.method()+' '+path);});return commits;}

test('@approach-configuration revoked initial picker read clears retained approach context and keeps the pin',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);await createLinked(page);
  const commits=watchCommits(page);await revoke(page,data.sid);
  await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();await expect(picker(page)).toBeVisible();
  await expectPickerCleared(page);await readingShot(page,'t4503-picker-denied');await expectPinRetained(page,commits);await readingShot(page,'t4503-pin-retained');
});

test('@approach-configuration revoked pagination clears picker context and fences the late cached record reply',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL,{second:true});
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions?*',async route=>{const url=new URL(route.request().url());if(url.searchParams.has('cursor'))await route.continue();else{url.searchParams.set('limit','1');await route.fulfill({response:await route.fetch({url:url.toString()})});}});
  const record=heldReply();await page.route('**/api/1/studies/'+data.sid+'/approach/versions/'+data.saved.version.approach_version_id,record.handler,{times:1});
  await createLinked(page,false);await expect.poll(()=>record.state.started).toBe(true);const commits=watchCommits(page);
  await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();const more=picker(page).getByRole('button',{name:'Load more approach versions',exact:true});await expect(more).toBeVisible();
  await revoke(page,data.sid);await more.click();
  try{await expectPickerCleared(page);}finally{record.state.release();}
  await expect.poll(()=>record.state.finished).toBe(true);await settle(page);
  await expectPickerCleared(page);await expectPinRetained(page,commits);
});

test('@approach-configuration revoked exact version choice clears picker context',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL,{second:true});await createLinked(page);const commits=watchCommits(page);
  await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();const versions=picker(page).getByLabel('Saved approach version',{exact:true});await expect(versions.locator('option')).toHaveCount(3);
  await expect(picker(page)).toContainText('Why use the scalar response approximation?');
  await revoke(page,data.sid);await versions.selectOption(data.second.version.approach_version_id);
  await expectPickerCleared(page);await expectPinRetained(page,commits);
});

test('@approach-configuration late page and exact version replies cannot repopulate after confirmed denial',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL,{second:true});const page2=heldReply(),choice=heldReply();let pages=0;
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions?*',async route=>{const url=new URL(route.request().url());if(url.searchParams.has('cursor')){if(++pages===1)await page2.handler(route);else await route.continue();}else{url.searchParams.set('limit','1');await route.fulfill({response:await route.fetch({url:url.toString()})});}});
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions/'+data.second.version.approach_version_id,choice.handler,{times:1});
  await createLinked(page);const commits=watchCommits(page),change=page.getByRole('button',{name:'Change modeling approach',exact:true});
  await change.click();await picker(page).getByRole('button',{name:'Load more approach versions',exact:true}).click();await expect.poll(()=>page2.state.started).toBe(true);
  await picker(page).getByRole('button',{name:'Keep current choice',exact:true}).click();await change.click();
  const versions=picker(page).getByLabel('Saved approach version',{exact:true});await expect(versions.locator('option')).toHaveCount(2);
  await versions.selectOption(data.second.version.approach_version_id);await expect.poll(()=>choice.state.started).toBe(true);
  await revoke(page,data.sid);await picker(page).getByRole('button',{name:'Keep current choice',exact:true}).click();await change.click();
  try{await expectPickerCleared(page);}finally{page2.state.release();choice.state.release();}
  await expect.poll(()=>page2.state.finished&&choice.state.finished).toBe(true);await settle(page);
  await expectPickerCleared(page);await expectPinRetained(page,commits);
});

test('@approach-configuration session change fences a pending picker record reply',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);const marker='Late reply from the previous session';
  const record=heldReply(value=>({...value,data:{...value.data,version:{...value.data.version,content:{...value.data.version.content,question:marker}}}}));
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions/'+data.saved.version.approach_version_id,record.handler,{times:1});
  await createLinked(page,false);await expect.poll(()=>record.state.started).toBe(true);
  await page.context().clearCookies();await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();
  try{await expect(page.getByLabel('Username',{exact:true})).toBeVisible();await expect(page.getByText(marker)).toHaveCount(0);}finally{record.state.release();}
  await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByLabel('Username',{exact:true})).toHaveCount(0);
  await expect.poll(()=>record.state.finished).toBe(true);await settle(page);await expect(page.getByText(marker)).toHaveCount(0);
});

test('@approach-configuration transient study probe failure keeps picker context retryable',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL,{second:true});let armed=false,probes=0,record=0,initial=0,more=0;
  await page.route('**/api/1/studies/'+data.sid,async route=>{if(armed&&route.request().method()==='GET'){armed=false;probes++;await route.abort();}else await route.continue();});
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions/'+data.saved.version.approach_version_id,async route=>{if(++record===1){armed=true;await route.fulfill(notFoundReply);}else await route.continue();});
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions?*',async route=>{const url=new URL(route.request().url());
    if(url.searchParams.has('cursor')){if(++more===1){armed=true;await route.fulfill(notFoundReply);}else await route.continue();return;}
    if(++initial===1){armed=true;await route.fulfill(notFoundReply);return;}url.searchParams.set('limit','1');await route.fulfill({response:await route.fetch({url:url.toString()})});});
  const transient='Study access could not be verified. Retry the read.';
  await createLinked(page,false);await expect(page.getByText(transient,{exact:true}).first()).toBeVisible();expect(probes).toBe(1);await readingShot(page,'t4503-record-transient');
  await page.getByRole('button',{name:'Retry loading modeling approach',exact:true}).click();await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Why use the scalar response approximation?');await expect(page.getByText(transient,{exact:true})).toHaveCount(0);
  const change=page.getByRole('button',{name:'Change modeling approach',exact:true});await change.click();
  await expect(picker(page).getByText(transient,{exact:true})).toBeVisible();expect(probes).toBe(2);
  await expect(picker(page)).toContainText('Why use the scalar response approximation?');await expect(picker(page).getByLabel('Intended case',{exact:true})).toBeVisible();
  await picker(page).getByRole('button',{name:'Keep current choice',exact:true}).click();await change.click();
  const load=picker(page).getByRole('button',{name:'Load more approach versions',exact:true});await expect(load).toBeVisible();await load.click();
  await expect(picker(page).getByText(transient,{exact:true})).toBeVisible();expect(probes).toBe(3);await expect(load).toBeEnabled();await readingShot(page,'t4503-pagination-transient');
  await expect(picker(page)).toContainText('Why use the scalar response approximation?');await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Why use the scalar response approximation?');
  await load.click();await expect(picker(page).getByLabel('Saved approach version',{exact:true}).locator('option')).toHaveCount(3);await expect(load).toHaveCount(0);
  await expect(page.getByText('Access to this resource is no longer available.',{exact:true})).toHaveCount(0);
});

// Every host that shows retained approach or run context clears it
// after a confirmed denial of its own read, keeps it after a transient study
// probe failure and fences late replies. A denial is confirmed against the
// captured study, actor, session and access epoch, never a dialog generation.
// Actual public API, membership revocation and auth; no configuration writes.
const deniedText='Access to this resource is no longer available.',unverifiedText='Study access could not be verified. Retry the read.';
function heldFailure(){
  let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;}),state={started:false,finished:false,release:()=>release()};
  const handler=async(route:any)=>{state.started=true;await gate;try{await route.fulfill(notFoundReply);}catch{/* the product may abort the request */}finally{state.finished=true;}};
  return {state,handler};
}
function countGets(page:Page,path:string){const reads={count:0};page.on('request',r=>{if(r.method()==='GET'&&new URL(r.url()).pathname===path)reads.count++;});return reads;}
async function expectNoMoreReads(page:Page,reads:{count:number},ms=4500){const before=reads.count;await page.waitForTimeout(ms);expect(reads.count,'no read after confirmed denial').toBe(before);}
async function expectConfigurationContextCleared(page:Page,commits:string[]){
  await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toHaveCount(0);
  for(const text of pickerProtected)await expect(page.getByText(text),text).toHaveCount(0);
  await expect(page.getByText('The linked modeling approach could not be loaded. The link to its version is unchanged.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Remove approach link',exact:true})).toBeVisible();
  expect(commits).toEqual([]);
}

test('@approach-configuration picker denial confirmed after the dialog closed mid-flight still clears retained context',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);await createLinked(page);const commits=watchCommits(page),list=heldFailure();
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions?*',list.handler,{times:1});
  await page.getByRole('button',{name:'Change modeling approach',exact:true}).click();await expect.poll(()=>list.state.started).toBe(true);
  await revoke(page,data.sid);await picker(page).getByRole('button',{name:'Keep current choice',exact:true}).click();await expect(picker(page)).not.toBeVisible();
  list.state.release();await expect.poll(()=>list.state.finished).toBe(true);
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();await expectConfigurationContextCleared(page,commits);await readingShot(page,'t46r1-picker-closed-denied');
});

test('@approach-configuration configuration host denial clears the picker display and keeps the pin and draft',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);await createLinked(page);await fillCaseConfiguration(page,'Host denial draft');const commits=watchCommits(page);
  await revoke(page,data.sid);await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expectConfigurationContextCleared(page,commits);await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Host denial draft');
  await expect(page.getByText('Saved · read-only',{exact:true})).toHaveCount(0);await readingShot(page,'t46n1-configuration-host-denied');
});

test('@approach-configuration configuration host denial fences a late picker record reply',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);const record=heldReply();
  await page.route('**/api/1/studies/'+data.sid+'/approach/versions/'+data.saved.version.approach_version_id,record.handler,{times:1});
  await createLinked(page,false);await expect.poll(()=>record.state.started).toBe(true);await fillCaseConfiguration(page,'Late record draft');const commits=watchCommits(page);
  await revoke(page,data.sid);await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  try{await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();}finally{record.state.release();}
  await expect.poll(()=>record.state.finished).toBe(true);await settle(page);
  await expectConfigurationContextCleared(page,commits);await expect(page.getByLabel('Configuration name',{exact:true})).toHaveValue('Late record draft');
});

test('@approach-configuration configuration host transient study probe keeps picker context retryable',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);await createLinked(page);await fillCaseConfiguration(page,'Transient host draft');const commits=watchCommits(page);let armed=false,probes=0;
  await page.route('**/api/1/studies/'+data.sid+'/configurations/preview',async route=>{armed=true;await route.fulfill(notFoundReply);},{times:1});
  await page.route('**/api/1/studies/'+data.sid,async route=>{if(armed&&route.request().method()==='GET'){armed=false;probes++;await route.abort();}else await route.continue();});
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();
  await expect(page.getByText(unverifiedText,{exact:true}).first()).toBeVisible();expect(probes).toBe(1);
  await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Why use the scalar response approximation?');
  await expect(page.getByText(deniedText,{exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Save configuration',exact:true})).toBeEnabled();
  expect(commits).toEqual([]);await readingShot(page,'t46n1-configuration-host-transient');
});

test('@approach-configuration saved configuration record clears on a denied availability read',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);await createLinked(page);await fillCaseConfiguration(page,'Saved record under revocation');await saveCaseConfiguration(page);
  const record=page.getByRole('region',{name:'Linked modeling approach',exact:true});await expect(record).toContainText('Why use the scalar response approximation?');
  await revoke(page,data.sid);await page.getByRole('button',{name:'Check again',exact:true}).click();
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();await expect(record).toHaveCount(0);
  for(const text of pickerProtected)await expect(page.getByText(text),text).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Saved record under revocation',exact:true})).toHaveCount(0);await expect(page.getByRole('region',{name:'Saved configuration inputs',exact:true})).toHaveCount(0);
  await readingShot(page,'t46n1-saved-configuration-denied');
});

test('@approach-configuration saved configuration record keeps context after a transient study probe',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);await createLinked(page);await fillCaseConfiguration(page,'Saved record transient');await saveCaseConfiguration(page);
  const record=page.getByRole('region',{name:'Linked modeling approach',exact:true});await expect(record).toContainText('Why use the scalar response approximation?');let armed=false,probes=0;
  await page.route('**/api/1/studies/'+data.sid+'/execution-readiness',async route=>{armed=true;await route.fulfill(notFoundReply);},{times:1});
  await page.route('**/api/1/studies/'+data.sid,async route=>{if(armed&&route.request().method()==='GET'){armed=false;probes++;await route.abort();}else await route.continue();});
  await page.getByRole('button',{name:'Check again',exact:true}).click();
  await expect(page.getByText(unverifiedText,{exact:true}).first()).toBeVisible();expect(probes).toBe(1);await expect(record).toContainText('Why use the scalar response approximation?');
  await page.getByRole('button',{name:'Check again',exact:true}).click();await expect(page.getByText(unverifiedText,{exact:true})).toHaveCount(0);
  await expect(record).toContainText('Why use the scalar response approximation?');await expect(page.getByText(deniedText,{exact:true})).toHaveCount(0);
});

test('@approach-history reopened run record clears retained approach, inputs, results, evidence and run list after denial',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL);await openRetainedRun(page,d.sid,d.run.run_id);const detail=countGets(page,`/api/1/studies/${d.sid}/runs/${d.run.run_id}`);
  await expect(page.getByRole('region',{name:'Output values',exact:true})).toBeVisible();
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();const linked=page.getByRole('region',{name:'Linked modeling approach',exact:true});await expect(linked).toContainText('Explain the screening after the prior failure');
  await page.getByRole('button',{name:'Back to run history',exact:true}).click();await expect(runRow(page,d.run.run_id)).toBeVisible();
  await revoke(page,d.sid);await page.getByRole('button',{name:`Inspect run ${d.run.run_id}`,exact:true}).click();
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();
  await expect(linked).toHaveCount(0);await expect(page.getByText('Explain the screening after the prior failure')).toHaveCount(0);await expect(page.getByText('Screening measurements')).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Saved configuration inputs',exact:true})).toHaveCount(0);await expect(page.getByRole('region',{name:'Output values',exact:true})).toHaveCount(0);
  await expect(page.getByRole('tab',{name:'Evidence',exact:true})).toHaveCount(0);await expect(page.getByRole('heading',{name:'Retained screening',exact:true})).toHaveCount(0);
  await expectNoMoreReads(page,detail);await readingShot(page,'t46n1-run-record-denied');
  // An explicit status refresh reads again under a new fence and re-confirms the denial.
  const reads=detail.count;await page.getByRole('button',{name:'Refresh run status',exact:true}).click();await expect.poll(()=>detail.count).toBeGreaterThan(reads);
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();await expect(linked).toHaveCount(0);await expect(page.getByRole('region',{name:'Output values',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Back to run history',exact:true}).click();await expect(page.locator('.run-list li')).toHaveCount(0);
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();await expect(page.getByText(/This study has no runs yet/)).toHaveCount(0);await expect(page.getByText(/approach v\d/)).toHaveCount(0);
});

test('@approach-history queued run status backoff stops after a confirmed denial and clears case context',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);const detail=countGets(page,`/api/1/studies/${d.sid}/runs/${d.runs.v2}`);
  await page.getByRole('button',{name:`Inspect run ${d.runs.v2}`,exact:true}).click();await expect(page.locator('.run-detail-case')).toContainText('Case: Nominal range · approach v2');
  await expect.poll(()=>detail.count).toBeGreaterThan(1);await revoke(page,d.sid);
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible({timeout:15000});await expect(page.locator('.run-detail-case')).toHaveCount(0);await expect(page.getByText('Nominal range · approach v2')).toHaveCount(0);
  await expectNoMoreReads(page,detail);
  await page.getByRole('button',{name:'Back to run history',exact:true}).click();await expect(page.locator('.run-list li')).toHaveCount(0);await expect(page.getByLabel('Run case',{exact:true})).toHaveCount(0);
  await expect(page.getByText(/approach v\d/)).toHaveCount(0);await readingShot(page,'t46n1-run-backoff-denied');
});

test('@approach-history late successful run status reply cannot repopulate after a confirmed denial',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);const path=`/api/1/studies/${d.sid}/runs/${d.runs.v2}`,detail=countGets(page,path);
  await page.getByRole('button',{name:`Inspect run ${d.runs.v2}`,exact:true}).click();await expect(page.locator('.run-detail-case')).toContainText('Case: Nominal range · approach v2');
  const late=heldReply();await page.route('**'+path,late.handler,{times:1});await expect.poll(()=>late.state.started,{timeout:15000}).toBe(true);
  await revoke(page,d.sid);await page.getByRole('button',{name:'Refresh run status',exact:true}).click();
  try{await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();}finally{late.state.release();}
  await expect.poll(()=>late.state.finished).toBe(true);await settle(page);
  await expect(page.locator('.run-detail-case')).toHaveCount(0);await expect(page.getByText('Nominal range · approach v2')).toHaveCount(0);await expect(page.getByText('Queued for preparation',{exact:true})).toHaveCount(0);
  await expectNoMoreReads(page,detail);
});

test('@approach-history queued run keeps case context after a transient study probe and refreshes manually',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);const path=`/api/1/studies/${d.sid}/runs/${d.runs.v2}`;
  await page.getByRole('button',{name:`Inspect run ${d.runs.v2}`,exact:true}).click();const label=page.locator('.run-detail-case');await expect(label).toContainText('Case: Nominal range · approach v2');
  let probes=0;await page.route('**'+path,route=>route.fulfill(notFoundReply));await page.route('**/api/1/studies/'+d.sid,async route=>{if(route.request().method()==='GET'){probes++;await route.abort();}else await route.continue();});
  await page.getByRole('button',{name:'Refresh run status',exact:true}).click();
  await expect(page.getByText(unverifiedText,{exact:true}).first()).toBeVisible();expect(probes).toBeGreaterThan(0);
  await expect(label).toContainText('Case: Nominal range · approach v2');await expect(page.getByText('Queued for preparation',{exact:true})).toBeVisible();await expect(page.getByText(deniedText,{exact:true})).toHaveCount(0);
  await readingShot(page,'t46n1-run-status-transient');
  await page.unroute('**'+path);await page.unroute('**/api/1/studies/'+d.sid);await page.getByRole('button',{name:'Refresh run status',exact:true}).click();
  await expect(page.getByText(unverifiedText,{exact:true})).toHaveCount(0);await expect(label).toContainText('Case: Nominal range · approach v2');await expect(page.getByText(deniedText,{exact:true})).toHaveCount(0);
});

test('@approach-controller approach version page denial survives a version switch and late replies cannot repopulate',async({page,browser,baseURL})=>{
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  await helper.evaluate(async sid=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');
    for(let i=0;i<2;i++){await c.open(sid);c.edit({...c.getSnapshot().local,question:'Protected switch question '+i});if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);}
  },sid);await context.close();
  const more=heldFailure();let lateList:any=null,pages=0;
  await page.route('**/api/1/studies/'+sid+'/approach/versions?*',async route=>{
    const url=new URL(route.request().url());
    if(url.searchParams.has('cursor')){if(++pages===1)await more.handler(route);else await route.continue();return;}
    if(lateList){await route.fulfill({json:lateList});return;}
    url.searchParams.set('limit','1');await route.fulfill({response:await route.fetch({url:url.toString()})});
  });
  await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Protected switch question 1',exact:true})).toBeVisible();
  // Successful replies captured before revocation are released late.
  const first=await(await page.request.get(`/api/1/studies/${sid}/approach/versions?limit=1`)).json(),target=first.data.items[0].approach_version_id;
  const exact=await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${target}`)).json();
  await page.route('**/api/1/studies/'+sid+'/approach/versions/'+target,route=>route.fulfill({json:exact}));
  // The version page also reads that version's usage. Its reply is captured before the revocation
  // as well, so the only denial the page can observe is the held page of versions.
  const usage=await(await page.request.get(`/api/1/studies/${sid}/approach/versions/${target}/usage?limit=10`)).json();
  await page.route('**/api/1/studies/'+sid+'/approach/versions/'+target+'/usage*',route=>route.fulfill({json:usage}));
  await page.getByRole('button',{name:'Load more versions',exact:true}).click();await expect.poll(()=>more.state.started).toBe(true);
  await revoke(page,sid);lateList=first;
  await page.getByLabel('Approach version',{exact:true}).selectOption(target);
  await expect(page.getByRole('heading',{name:exact.data.version.content.question,exact:true})).toBeVisible();
  more.state.release();await expect.poll(()=>more.state.finished).toBe(true);
  await expect(page.getByText('Versions could not be loaded. '+deniedText,{exact:true})).toBeVisible();
  for(const question of ['Protected switch question 0','Protected switch question 1'])await expect(page.getByRole('heading',{name:question,exact:true})).toHaveCount(0);
  await settle(page);await expect(page.getByLabel('Approach version',{exact:true})).not.toContainText('read-only');await expect(page.getByRole('button',{name:'Load more versions',exact:true})).toHaveCount(0);
});

// Session seam: one shared fence/readFailed/onSessionChange. Each host's own
// read confirms the denial; the signal clears every other host showing that study.
function watchWrites(page:Page){const writes:string[]=[];page.on('request',r=>{const path=new URL(r.url()).pathname;if(r.method()!=='GET'&&path.startsWith('/api/1/')&&path!=='/api/1/session'&&!/\/preview$/.test(path))writes.push(r.method()+' '+path);});return writes;}
async function signOutAndIn(page:Page){
  await page.getByRole('button',{name:'Profile',exact:true}).click();await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('button',{name:'Profile',exact:true})).toBeVisible();
}

test('@approach-controller reconciled denial set: an unauthenticated refusal clears the controller and signals access loss without writes',async({page})=>{
  const sid=await open(page);await edit(page,'Protected before refusal');await act(page,'save');const writes=watchWrites(page);
  await page.evaluate(()=>{const w=window as any;w.p4s2Signals=[];w.approachHarness.api.onSessionChange((change:any)=>w.p4s2Signals.push(change));});
  await page.route(`**/api/1/studies/${sid}/approach`,route=>route.fulfill({status:403,json:{error:{code:'unauthenticated',message:'Refused',fields:[],outcome:'unchanged'}}}));
  expect(await act(page,'reviewLatest')).toBe(false);
  const after=await state(page);expect(after.server).toBeNull();expect(after.local).toBeNull();expect(after.studyId).toBeNull();
  expect(await page.evaluate(()=>(window as any).p4s2Signals)).toEqual([{kind:'access-lost',studyId:sid}]);expect(writes).toEqual([]);
});

// The controller itself is on the session seam, so a denial confirmed by any other host
// clears it even while no approach page is mounted. Clean state is cleared completely; unsaved
// local edits are never dropped silently: they stay, hidden and unsaveable, under the workspace
// guard until the user discards them.
test('@approach-controller access loss reported by another host clears a clean controller and keeps unsaved edits hidden under the guard',async({page})=>{
  const sid=await open(page);await edit(page,'Protected saved question');expect(await act(page,'save')).toBe(true);const writes=watchWrites(page);
  const lose=(id:string)=>page.evaluate(id=>(window as any).approachHarness.api.accessLost(id),id);
  const dirty=()=>page.evaluate(()=>(window as any).approachHarness.controller.dirty);
  // Another study's loss changes nothing here.
  await lose(crypto.randomUUID());expect((await state(page)).server.draft.content.question).toBe('Protected saved question');
  // Clean: cleared completely.
  await lose(sid);let after=await state(page);
  expect(after.studyId).toBeNull();expect(after.server).toBeNull();expect(after.local).toBeNull();expect(after.accessLost).toBe(false);
  await expect(page.getByLabel('Draft question',{exact:true})).toHaveText('');
  // Dirty: every server-derived projection is cleared; only the user's own unsaved edits remain.
  expect(await page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid)).toBe(true);
  await edit(page,'Unsaved edit kept under the guard');expect(await act(page,'preview')).toBe(true);
  await lose(sid);after=await state(page);
  expect(after.studyId).toBe(sid);expect(after.server).toBeNull();expect(after.saved).toBeNull();expect(after.preview).toBeNull();expect(after.latest).toBeNull();
  expect(after.accessLost).toBe(true);expect(after.status).toBe('error');expect(after.error).toBe('Access to this resource is no longer available.');
  expect(after.local.question).toBe('Unsaved edit kept under the guard');expect(await dirty()).toBe(true);
  // Nothing is saved, previewed, edited or re-read while the edits are kept.
  for(const method of ['save','preview','saveVersion','reviewLatest'])expect(await act(page,method)).toBe(false);
  await edit(page,'Ignored after access loss');expect((await state(page)).local.question).toBe('Unsaved edit kept under the guard');
  expect(await page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid)).toBe(false);
  // The guard's explicit Discard clears completely; the approach can then be read again.
  await act(page,'discard');after=await state(page);
  expect(after.studyId).toBeNull();expect(after.local).toBeNull();expect(after.accessLost).toBe(false);expect(await dirty()).toBe(false);
  expect(await page.evaluate(sid=>(window as any).approachHarness.controller.open(sid),sid)).toBe(true);
  expect((await state(page)).server.draft.content.question).toBe('Protected saved question');
  // Sign-out reaches the controller through the same seam.
  await edit(page,'Unsaved before sign-out');await page.evaluate(()=>(window as any).approachHarness.api.logout());
  after=await state(page);expect(after.studyId).toBeNull();expect(after.local).toBeNull();
  expect(writes).toEqual([]);
});

test('@approach-history failed run history refresh after revocation clears listed case labels and stays cleared',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);const writes=watchWrites(page);
  await expect(runRow(page,d.runs.v2)).toContainText('Nominal range · approach v2');const list=countGets(page,`/api/1/studies/${d.sid}/runs`);
  await revoke(page,d.sid);await page.getByRole('button',{name:'Refresh run history',exact:true}).click();
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();
  await expect(page.locator('.run-list li')).toHaveCount(0);await expect(page.getByText(/approach v\d/)).toHaveCount(0);await expect(page.getByText('Renamed nominal range')).toHaveCount(0);
  await expect(page.getByLabel('Run case',{exact:true})).toHaveCount(0);await expect(page.getByText(/This study has no runs yet/)).toHaveCount(0);
  await expectNoMoreReads(page,list,2500);expect(writes).toEqual([]);await readingShot(page,'p4s2-run-list-denied');
});

test('@approach-history run history refresh with a transient study probe keeps case labels and retries',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);const writes=watchWrites(page);
  await expect(runRow(page,d.runs.v2)).toContainText('Nominal range · approach v2');let probes=0;
  await page.route(`**/api/1/studies/${d.sid}/runs`,route=>route.fulfill(notFoundReply),{times:1});
  await page.route('**/api/1/studies/'+d.sid,async route=>{if(route.request().method()==='GET'){probes++;await route.abort();}else await route.continue();},{times:1});
  await page.getByRole('button',{name:'Refresh run history',exact:true}).click();
  await expect(page.getByText(unverifiedText,{exact:true}).first()).toBeVisible();expect(probes).toBe(1);
  await expect(runRow(page,d.runs.v2)).toContainText('Nominal range · approach v2');await expect(page.getByText(deniedText,{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Refresh run history',exact:true}).click();await expect(page.getByText(unverifiedText,{exact:true})).toHaveCount(0);
  await expect(runRow(page,d.runs.v2)).toContainText('Nominal range · approach v2');expect(writes).toEqual([]);
});

test('@approach-history Findings confirmed denial clears the approach reader and its cases panel',async({page,browser,baseURL})=>{
  const data=await linkedPicker(page,browser,baseURL);const writes=watchWrites(page);
  await expect(page.getByRole('heading',{name:'Why use the scalar response approximation?',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'Approach usage',exact:true}).getByRole('article',{name:'Upper operating range',exact:true})).toBeVisible();
  await revoke(page,data.sid);await page.getByLabel('Findings case',{exact:true}).selectOption({label:'Nominal range'});
  await expect(page.getByText(deniedText,{exact:true}).first()).toBeVisible();
  await expect(page.getByRole('heading',{name:'Why use the scalar response approximation?',exact:true})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Approach usage',exact:true})).toHaveCount(0);await expect(page.getByRole('article',{name:'Upper operating range',exact:true})).toHaveCount(0);
  for(const text of pickerProtected)await expect(page.getByText(text),text).toHaveCount(0);
  await expect(page.getByLabel('Approach version',{exact:true})).not.toContainText('read-only');expect(writes).toEqual([]);await readingShot(page,'p4s2-findings-denied');
});

test('@approach-configuration sign-out clears approach reading positions and Workspace return state',async({page,browser,baseURL})=>{
  const data=await seededConditions(page,browser,baseURL,{cases:true});const version=data.saved.version.approach_version_id;
  await page.getByLabel('Approach version',{exact:true}).selectOption(version);
  await page.getByRole('button',{name:'Select step 1',exact:true}).click();await stepTab(page,'Assumptions & evidence');
  await expect(page.getByRole('region',{name:'Selected method step',exact:true}).getByRole('tab',{name:'Assumptions & evidence',exact:true})).toHaveAttribute('aria-selected','true');
  await casesTab(page);await expect(page.getByRole('tab',{name:'Cases & results',exact:true})).toHaveAttribute('aria-selected','true');
  await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'runs'}).toString();},data.sid);await expect(page.getByRole('heading',{name:'Run history',exact:true})).toBeVisible();
  await signOutAndIn(page);
  await page.evaluate(({sid,version})=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'approach',approach:version}).toString();},{sid:data.sid,version});
  await expect(page.getByRole('heading',{name:'Why use the scalar response approximation?',exact:true})).toBeVisible();
  await expect(page.getByRole('tab',{name:'Methods',exact:true})).toHaveAttribute('aria-selected','true');
  await expect(page.getByRole('tab',{name:'Cases & results',exact:true})).toHaveAttribute('aria-selected','false');
  await expect(page.getByRole('region',{name:'Selected method step',exact:true}).getByRole('tab',{name:'Assumptions & evidence',exact:true})).toHaveAttribute('aria-selected','false');
  await expect(page.getByRole('button',{name:/^Return to /})).toHaveCount(0);
});

// Results-first Cases & results and version-qualified case navigation.
// Real public authoring for approach versions, configurations and runs. Runs
// stay queued: only the authorized list projection and exact records are read.
async function caseNavigation(page:Page,browser:any,baseURL:string|undefined){
  await page.request.post('/fixture/model-available');
  const data=await seededConditions(page,browser,baseURL,{cases:true,failure:true});
  await page.getByLabel('Approach version',{exact:true}).selectOption(data.saved.version.approach_version_id);
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Version one nominal');const original=await saveCaseConfiguration(page);
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const made=await helper.evaluate(async({d,original})=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');const sid=d.sid,o=original.configuration,nominal=d.saved.version.content.cases[0].case_id;
    async function version(edit:(content:any)=>any){await c.open(sid);c.edit(edit(structuredClone(c.getSnapshot().local)));if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);return c.getSnapshot().saved;}
    async function config(name:string,selection:any){const configuration:any={schema_version:'4',study_id:sid,model_id:o.model_id,model_revision_id:o.model_revision_id,name,inputs:o.inputs.map((i:any)=>({kind:'literal',target:i.target,value:i.value,units:i.units,provenance:i.provenance})),criteria:o.criteria,numerical:o.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(sid)).revision},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[],approach_selection:selection};const p=await api.previewConfiguration4(configuration);return (await api.commitConfiguration4({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:p.candidate_digest})).configuration;}
    // v2 keeps the same case identity and name; v3 renames that same case.
    const v2=await version(content=>({...content,question:'Second interpretation keeps the nominal case'}));
    const v3=await version(content=>({...content,question:'Third interpretation renames the nominal case',cases:content.cases.map((x:any)=>x.case_id===nominal?{...x,title:'Renamed nominal range'}:x)}));
    const v1none=await config('Version one without case',{approach_version_id:d.saved.version.approach_version_id,case_id:null});
    const v2nominal=await config('Version two nominal',{approach_version_id:v2.version.approach_version_id,case_id:nominal});
    const v3nominal=await config('Version three renamed',{approach_version_id:v3.version.approach_version_id,case_id:nominal});
    const unlinked=await config('Without approach',null);
    const runs:Record<string,string>={};
    for(const [key,id] of Object.entries({v1:o.configuration_revision_id,v1none:v1none.configuration_revision_id,v2:v2nominal.configuration_revision_id,v3:v3nominal.configuration_revision_id,unlinked:unlinked.configuration_revision_id}))runs[key]=(await api.submitRun(sid,id)).run_id;
    // The v3 run is retained through the existing failed-outcome handoff so its record
    // resolves the case from its own closure; the others stay queued (list projection only).
    const retained=await fetch('/fixture/retain-failed-outcome',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:d.fixture.key,study_id:sid,run_id:runs.v3})});if(!retained.ok)throw new Error(await retained.text());
    return {v2,v3,runs,configs:{v1:o.configuration_revision_id,v2:v2nominal.configuration_revision_id}};
  },{d:data,original});await ctx.close();
  return {...data,...made,nominal:data.saved.version.content.cases[0].case_id as string};
}
const runRow=(page:Page,id:string)=>page.locator('.run-list li').filter({has:page.getByRole('button',{name:`Inspect run ${id}`,exact:true})});
async function openRuns(page:Page,sid:string){await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'runs'}).toString();},sid);await expect(page.getByRole('heading',{name:'Run history',exact:true})).toBeVisible();}

test('@approach-configuration Runs case column and filter keep same-name versions, null case, unlinked and unavailable context distinct',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);
  await expect(page.getByText('5 of 5 loaded runs',{exact:true})).toBeVisible();
  await expect(runRow(page,d.runs.v1)).toContainText('Nominal range · approach v1');
  await expect(runRow(page,d.runs.v2)).toContainText('Nominal range · approach v2');
  await expect(runRow(page,d.runs.v3)).toContainText('Renamed nominal range · approach v3');
  await expect(runRow(page,d.runs.v1none)).toContainText('No specific case · approach v1');
  await expect(runRow(page,d.runs.unlinked)).toContainText('No modeling approach');
  for(const id of Object.values(d.runs))await expect(runRow(page,id)).not.toContainText('Case context unavailable');
  const filter=page.getByLabel('Run case',{exact:true});
  expect((await filter.locator('option').allTextContents()).sort()).toEqual(['All cases','Approach v1 · No specific case','Approach v1 · Nominal range','Approach v2 · Nominal range','Approach v3 · Renamed nominal range','No modeling approach'].sort());
  await filter.selectOption({label:'Approach v1 · Nominal range'});await expect(page.getByText('1 of 5 loaded runs',{exact:true})).toBeVisible();await expect(runRow(page,d.runs.v1)).toBeVisible();await expect(runRow(page,d.runs.v2)).toHaveCount(0);
  await filter.selectOption({label:'Approach v2 · Nominal range'});await expect(page.getByText('1 of 5 loaded runs',{exact:true})).toBeVisible();await expect(runRow(page,d.runs.v2)).toBeVisible();await expect(runRow(page,d.runs.v1)).toHaveCount(0);
  await filter.selectOption({label:'Approach v1 · No specific case'});await expect(runRow(page,d.runs.v1none)).toBeVisible();await expect(runRow(page,d.runs.unlinked)).toHaveCount(0);
  await filter.selectOption({label:'No modeling approach'});await expect(runRow(page,d.runs.unlinked)).toBeVisible();await expect(runRow(page,d.runs.v1none)).toHaveCount(0);
  // Existing text and submission-state filters compose with the case filter.
  await filter.selectOption({label:'Approach v2 · Nominal range'});const text=page.getByLabel('Filter loaded runs',{exact:true});await text.fill(d.runs.v1);await expect(page.getByText('0 of 5 loaded runs',{exact:true})).toBeVisible();await expect(page.getByText('No runs match these filters.',{exact:true})).toBeVisible();await text.fill(d.runs.v2);await expect(page.getByText('1 of 5 loaded runs',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Run submission state'}).selectOption('uncertain');await expect(page.getByText('0 of 5 loaded runs',{exact:true})).toBeVisible();await page.getByRole('combobox',{name:'Run submission state'}).selectOption('');await text.fill('');await filter.selectOption('');await expect(page.getByText('5 of 5 loaded runs',{exact:true})).toBeVisible();
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'runs-case-column-'+theme);}
  await page.setViewportSize({width:720,height:1000});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await readingShot(page,'runs-case-column-720');await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>document.documentElement.dataset.theme='light');
  // Missing, unavailable or malformed list metadata is never the explicit null case.
  const listPath=`/api/1/studies/${d.sid}/runs`;
  await page.route('**'+listPath,async route=>{if(route.request().method()!=='GET'){await route.continue();return;}const response=await route.fetch(),value=await response.json();for(const item of value.data){if(item.run_id===d.runs.v2)delete item.case_context;if(item.run_id===d.runs.v3)item.case_context={state:'unavailable'};if(item.run_id===d.runs.v1none)item.case_context={...item.case_context,case_id:'not-an-identity'};}await route.fulfill({response,json:value});});
  await page.getByRole('button',{name:'Refresh run history',exact:true}).click();
  for(const id of [d.runs.v2,d.runs.v3,d.runs.v1none]){await expect(runRow(page,id)).toContainText('Case context unavailable');await expect(runRow(page,id)).not.toContainText('No specific case');await expect(runRow(page,id)).not.toContainText('No modeling approach');}
  await filter.selectOption({label:'Case context unavailable'});await expect(page.getByText('3 of 5 loaded runs',{exact:true})).toBeVisible();await readingShot(page,'runs-case-unavailable-light');
  await page.unroute('**'+listPath);let lists=0;page.on('request',r=>{if(r.method()==='GET'&&new URL(r.url()).pathname===listPath)lists++;});
  const retry=page.getByRole('button',{name:'Retry case context',exact:true});await retry.focus();await retry.press('Enter');await expect.poll(()=>lists).toBe(1);
  // The still-selected unavailable filter now matches nothing; clearing it shows the restored context.
  await expect(page.getByRole('button',{name:'Retry case context',exact:true})).toHaveCount(0);await expect(page.getByText('0 of 5 loaded runs',{exact:true})).toBeVisible();await filter.selectOption('');await expect(page.getByText('5 of 5 loaded runs',{exact:true})).toBeVisible();await expect(runRow(page,d.runs.v2)).toContainText('Nominal range · approach v2');await expect(runRow(page,d.runs.v1none)).toContainText('No specific case · approach v1');
});

test('@approach-configuration exact case links open the version-qualified case and return focus and filters',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);await openRuns(page,d.sid);const results=page.getByRole('region',{name:'Results',exact:true}),usage=page.getByRole('region',{name:'Approach usage',exact:true}),filter=page.getByLabel('Run case',{exact:true});
  await filter.selectOption({label:'Approach v1 · Nominal range'});
  const link=page.getByRole('button',{name:`Nominal range · approach v1, open case for run ${d.runs.v1.slice(0,8)}`,exact:true});
  // WCAG 2.5.3: every case link's accessible name starts with its visible text.
  await expect(page.locator('.case-context-link').first()).toBeVisible();expect(await page.locator('.case-context-link').evaluateAll(es=>es.filter(e=>!(e.getAttribute('aria-label')??'').startsWith((e.textContent??'').trim())).map(e=>e.getAttribute('aria-label')))).toEqual([]);
  await link.focus();await link.press('Enter');
  await expect(page.getByRole('tabpanel',{name:'Cases & results',exact:true}).getByRole('region',{name:'Results',exact:true})).toBeVisible();
  await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(d.saved.version.approach_version_id);
  await expect.poll(()=>new URLSearchParams(new URL(page.url()).hash.slice(1)).get('case')).toBe(d.nominal);expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('approach')).toBe(d.saved.version.approach_version_id);
  await expect(page.getByRole('tab',{name:'Cases & results',exact:true})).toHaveAttribute('aria-selected','true');
  await expect(usage.getByRole('heading',{name:'Nominal range',exact:true})).toBeFocused();await expect(usage).not.toContainText('Renamed nominal range');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await readingShot(page,'case-navigation-results-'+theme);}await page.evaluate(()=>document.documentElement.dataset.theme='light');
  await page.getByRole('button',{name:'Return to run history',exact:true}).click();await expect(link).toBeFocused();await expect(filter).toHaveValue(`linked:${d.saved.version.approach_version_id}:${d.nominal}`);await expect(page.getByText('1 of 5 loaded runs',{exact:true})).toBeVisible();
  // The run record resolves its own retained closure: v3 names the renamed case.
  // A queued run without history uses its authorized list projection only.
  await filter.selectOption('');await page.getByRole('button',{name:`Inspect run ${d.runs.v2}`,exact:true}).click();await expect(page.locator('.run-detail-case')).toContainText('Case: Nominal range · approach v2');await page.getByRole('button',{name:'Back to run history',exact:true}).click();
  await page.getByRole('button',{name:`Inspect run ${d.runs.v3}`,exact:true}).click();await expect(page.locator('.run-detail-case')).toContainText('Case: Renamed nominal range · approach v3');
  const detailLink=page.getByRole('button',{name:'View case Renamed nominal range in approach v3',exact:true});await detailLink.click();
  await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(d.v3.version.approach_version_id);await expect(usage.getByRole('heading',{name:'Renamed nominal range',exact:true})).toBeFocused();
  await page.getByRole('button',{name:'Return to run',exact:true}).click();await expect(detailLink).toBeFocused();await expect(page.getByRole('tab',{name:'Configuration',exact:true})).toBeVisible();
  // Only the run header links; the retained Configuration tab stays closure-only.
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();await expect(page.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Approach version 3 · Renamed nominal range');await expect(page.getByRole('button',{name:/^View case in approach\b/})).toHaveCount(0);await expect(page.locator('#run-panel-2 .case-context-link')).toHaveCount(0);
  // The explicit null pin opens the version's No specific case results.
  await page.getByRole('button',{name:'Back to run history',exact:true}).click();await expect(page.getByRole('region',{name:'Run details',exact:true})).toHaveCount(0);
  // Back to run history makes the list the return origin; the last inspected run is not reopened.
  await expect.poll(()=>new URLSearchParams(new URL(page.url()).hash.slice(1)).get('run')).toBeNull();
  const noneLink=page.getByRole('button',{name:`No specific case · approach v1, open case for run ${d.runs.v1none.slice(0,8)}`,exact:true});await noneLink.click();
  await expect.poll(()=>new URLSearchParams(new URL(page.url()).hash.slice(1)).get('case')).toBe('none');await expect(usage.getByRole('heading',{name:'No specific case',exact:true})).toBeFocused();
  await expect(page.getByRole('button',{name:'Return to run',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'Return to run history',exact:true}).click();
  await expect(noneLink).toBeFocused();await expect(page.getByRole('region',{name:'Run details',exact:true})).toHaveCount(0);await expect(page.getByRole('heading',{name:'Run history',exact:true})).toBeVisible();
  // Saved configuration context links to the same exact version and case.
  await page.evaluate(({sid,id})=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'configurations',configuration:id}).toString();},{sid:d.sid,id:d.configs.v2});
  const configurationLink=page.getByRole('button',{name:'View case in approach: Nominal range, approach v2',exact:true});await configurationLink.click();
  await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(d.v2.version.approach_version_id);await expect(usage.getByRole('heading',{name:'Nominal range',exact:true})).toBeFocused();
  await page.getByRole('button',{name:'Return to configuration',exact:true}).click();await expect(configurationLink).toBeFocused();
  // Case identity is never accepted without its exact version, and an unknown
  // case in an exact version is named instead of substituting another case.
  await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'approach',case:crypto.randomUUID()}).toString();},d.sid);await expect(page.getByRole('alert').filter({hasText:'This case link does not name an approach version.'})).toBeVisible();
  await page.evaluate(({sid,version})=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'approach',approach:version,case:crypto.randomUUID()}).toString();},{sid:d.sid,version:d.saved.version.approach_version_id});
  await expect(results.getByRole('alert')).toHaveText('This case is not part of approach v1. No other case is shown in its place.');await expect(results.getByRole('heading',{name:'No study answer has been assessed.',exact:true})).toBeFocused();
});

test('@approach-configuration retained prior-basis configurations in Earlier work never navigate to current case usage',async({page,browser,baseURL})=>{
  const d=await caseNavigation(page,browser,baseURL);
  // v4 cites the exact v2-linked configuration as prior basis; its closure retains v2.
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const v4=await helper.evaluate(async({sid,config})=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');await c.open(sid);
    c.edit({...structuredClone(c.getSnapshot().local),question:'Fourth interpretation cites the version two nominal configuration',basis_refs:[{kind:'configuration',configuration_revision_id:config,relation:'context',reason:'The version two nominal configuration framed this interpretation.'}]});
    if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);return c.getSnapshot().saved.version.approach_version_id as string;
  },{sid:d.sid,config:d.configs.v2});await ctx.close();
  await page.evaluate(({sid,version})=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'approach',approach:version}).toString();},{sid:d.sid,version:v4});
  await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(v4);await expect(page.getByRole('heading',{name:'Fourth interpretation cites the version two nominal configuration',exact:true})).toBeVisible();
  // Page-level Approach actions › Earlier work: the retained basis shows its exact case, never a live link.
  await openEarlier(page);const earlier=page.getByRole('dialog',{name:'Earlier work',exact:true});await expect(earlier).toContainText('The version two nominal configuration framed this interpretation.');
  await earlier.getByRole('button',{name:'View earlier work',exact:true}).click();const record=page.getByRole('dialog',{name:'Earlier work record',exact:true});
  await expect(record.getByRole('region',{name:'Linked modeling approach',exact:true})).toContainText('Approach version 2 · Nominal range');
  await expect(record.locator('.case-context-link')).toHaveCount(0);await expect(record.getByRole('button',{name:/^View case/})).toHaveCount(0);await expect(earlier.locator('.case-context-link')).toHaveCount(0);
  await readingShot(page,'earlier-work-prior-basis-closure-only');
  await record.getByRole('button',{name:'Done',exact:true}).click();await closeEarlier(page);
  expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('approach')).toBe(v4);expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('case')).toBeNull();
});

// Real retained approach, configurations and runs (failed outcome, partial
// failure, queued repeat). No new numerical execution; review coverage only.
async function resultsReview(page:Page,browser:any,baseURL:string|undefined){
  await page.request.post('/fixture/model-available');
  const d=await seededConditions(page,browser,baseURL,{cases:true,failure:true});
  await page.getByLabel('Approach version',{exact:true}).selectOption(d.saved.version.approach_version_id);
  await casesTab(page);await page.getByRole('button',{name:'Create configuration for Nominal range',exact:true}).click();await fillCaseConfiguration(page,'Repeated screening');const original=await saveCaseConfiguration(page);
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const created=await helper.evaluate(async({d,original})=>{
    const api=(window as any).approachHarness.api;await api.login('owner','correct horse battery staple');const o=original.configuration,ids=[o.configuration_revision_id];
    for(let i=0;i<11;i++){const configuration={schema_version:'4',study_id:d.sid,model_id:o.model_id,model_revision_id:o.model_revision_id,name:'Repeated screening',inputs:o.inputs.map((x:any)=>({kind:'literal',target:x.target,value:x.value,units:x.units,provenance:x.provenance})),criteria:o.criteria,numerical:o.numerical,context_source:{kind:'current_study',expected_study_revision:(await api.study(d.sid)).revision},notes:[],derivation:null,assumptions:[],general_context_evidence_version_ids:[],approach_selection:{approach_version_id:d.saved.version.approach_version_id,case_id:i===10?null:d.saved.version.content.cases[0].case_id}};const p=await api.previewConfiguration4(configuration),v=await api.commitConfiguration4({command_id:crypto.randomUUID(),expected_revision:null,configuration_id:null,configuration,expected_preview_digest:p.candidate_digest});ids.push(v.configuration.configuration_revision_id);}
    async function retain(path:string){const run=await api.submitRun(d.sid,o.configuration_revision_id);const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:d.fixture.key,study_id:d.sid,run_id:run.run_id})});if(!response.ok)throw new Error(await response.text());return run.run_id;}
    const failed=await retain('/fixture/retain-failed-outcome'),partial=await retain('/fixture/retain-failure'),queued=(await api.submitRun(d.sid,o.configuration_revision_id)).run_id;
    return {ids,failed,partial,queued};
  },{d,original});await ctx.close();
  await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();return {...d,...created};
}

test('@approach-history Results lead Cases & results with a factual review and generic case cards across repeats, failures and partial pages',async({page,browser,baseURL})=>{
  const d=await resultsReview(page,browser,baseURL),results=page.getByRole('region',{name:'Results',exact:true}),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  // One card per case below the results summary (definition, runs and configurations together).
  const card=(name:string)=>usage.getByRole('article',{name,exact:true});
  await expect(usage).toContainText('More usage is available');
  // First page only: coverage is incomplete and no case is called unevaluated.
  await expect(results.getByRole('heading',{name:'No study answer has been assessed.',exact:true})).toBeVisible();
  await expect(results).toContainText('More usage is available; review coverage is incomplete');await expect(results).not.toContainText('Not evaluated in the loaded review');
  await expect(card('Upper operating range')).toContainText('No run loaded for this case; more usage is available.');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await results.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','results-incomplete-'+theme+'.png'),fullPage:false,animations:'disabled'});}
  await usage.getByRole('button',{name:'Load more usage',exact:true}).click();await expect(usage).toContainText('All usage loaded');
  // Exact counts from actual loaded records; nothing pooled into a verdict.
  await expect(results).toContainText('3 runs loaded for this approach version. 1 has results.');await expect(results).toContainText('12 configurations loaded');await expect(results).toContainText('All usage loaded');
  const nominal=card('Nominal range');await expect(nominal).toContainText('3 runs loaded');await expect(nominal).toContainText('Does the response fit the measured range?');
  for(const id of [d.failed,d.partial,d.queued])await expect(nominal.getByRole('article',{name:'run '+id,exact:true}).getByRole('button',{name:'View run',exact:true})).toBeVisible();
  await expect(nominal).toContainText('Failed');await expect(nominal).not.toContainText('Applicability');await expect(nominal).not.toContainText('Not assessed');for(const outcomes of await nominal.getByLabel('Run outcomes',{exact:true}).all())await expect(outcomes.locator('.hf-tag')).toHaveCount(2);await expect(nominal).toContainText('Results not yet available');await expect(nominal).toContainText('No results for this run');await expect(nominal).toContainText('10 configurations without a loaded run');
  await expect(card('Upper operating range')).toContainText('Not evaluated in the loaded review · no run found for this case');await expect(card('No specific case')).toContainText('1 configuration without a loaded run');
  for(const forbidden of ['Partial answer','Mixed evidence','Valid','success rate','passing'])await expect(results).not.toContainText(forbidden);
  // Results precede the case cards; each case appears once (no separate case or usage panels).
  const order=await page.evaluate(()=>[document.querySelector('section[aria-label="Results"]'),document.querySelector('.approach-case-card')].map(e=>e?e.getBoundingClientRect().top+scrollY:-1));expect(order.every(v=>v>=0)).toBe(true);expect(order[0]).toBeLessThan(order[1]);
  for(const name of ['Cases and evaluation','Cases and recorded runs'])await expect(page.getByRole('region',{name,exact:true})).toHaveCount(0);
  for(const name of ['Nominal range','Upper operating range'])await expect(page.getByRole('tabpanel',{name:'Cases & results',exact:true}).getByRole('heading',{name,exact:true})).toHaveCount(1);
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await results.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','results-populated-'+theme+'.png'),fullPage:false,animations:'disabled'});await readingShot(page,'results-populated-full-'+theme);}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  // Why this case: rationale, model version and evidence of that exact case, in its own card.
  await nominal.getByText('Why this case',{exact:true}).click();await expect(nominal).toContainText('Initial screening');await expect(nominal).toContainText('Model version '+d.model.model_revision_id.slice(0,8));
  // A failed record read keeps coverage incomplete; it never becomes "not evaluated".
  const broken=[...d.ids].sort()[0];await page.route('**/configurations/'+broken,route=>route.abort());await usage.getByRole('button',{name:'Refresh usage',exact:true}).click();await expect(usage).toContainText('Record unavailable');
  await expect(results).toContainText('1 record could not be loaded');await expect(results).toContainText('review coverage is incomplete');await expect(results).not.toContainText('All usage loaded');
  await page.unroute('**/configurations/'+broken);
  // A case filter scopes the factual summary to that exact case.
  await usage.getByLabel('Findings case',{exact:true}).selectOption(d.saved.version.content.cases[1].case_id);await expect(results).toContainText('0 runs loaded for case Upper operating range of this approach version.');await expect(card('Nominal range')).toHaveCount(0);await expect(card('Upper operating range')).toContainText('Not evaluated in the loaded review · no run found for this case');
  // Opening a run from a card keeps the exact run and returns to the approach.
  await usage.getByLabel('Findings case',{exact:true}).selectOption('');await usage.getByRole('button',{name:'Load more usage',exact:true}).click();await expect(usage).toContainText('All usage loaded');await card('Nominal range').getByRole('article',{name:'run '+d.failed,exact:true}).getByRole('button',{name:'View run',exact:true}).click();await expect(page.getByRole('tab',{name:'Results',exact:true})).toBeVisible();expect(new URL(page.url()).hash).toContain(d.failed);await page.getByRole('button',{name:'Return to modeling approach',exact:true}).click();await expect(page.getByLabel('Approach version',{exact:true})).toHaveValue(d.saved.version.approach_version_id);
});

// Results presentation fixture: a real saved approach version; usage, configuration
// and run responses overlay an actual retained run pinned to it (no native claim).
async function resultsFixture(page:Page,browser:any,baseURL:string|undefined){
  const ctx=await browser.newContext({baseURL}),helper=await ctx.newPage();await helper.goto('/ui/');
  const d=await helper.evaluate(async()=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');
    const sid=(await api.createStudy('Results review fixture')).study_id;await c.open(sid);
    const content={...structuredClone(c.getSnapshot().local),schema_version:'2',original_question:null,elaboration:null};
    content.question='Which recorded cases answer the screening question?';content.limitations='Legacy limitation text is recorded verbatim.';
    content.limit_items=[{limit_id:crypto.randomUUID(),statement:'Results apply only within the measured operating range.',evidence_links:[]}];
    content.steps=[{step_id:crypto.randomUUID(),title:'Extend to the full operating envelope',purpose:'Cover conditions beyond the measured range.',rationale:'Not yet modeled.',remaining_work:'Select and link a model for the full envelope.',intent:{transformation:'',inputs:'',outputs:'',depends_on_step_ids:[]},implementation_state:'proposed',implementation_refs:[],assumption_refs:[],evidence_links:[]}];
    content.cases=[{case_id:crypto.randomUUID(),title:'Measured conversion',question:'Does the recorded conversion satisfy its criteria?',rationale:'Exact retained record',binding_id:null,evidence_links:[]},{case_id:crypto.randomUUID(),title:'Envelope extension',question:'Can the full envelope be evaluated?',rationale:'Requires the proposed step',binding_id:null,evidence_links:[]}];
    c.edit(content);if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);const saved=c.getSnapshot().saved;
    const pair=await(await fetch('/fixture/native-pair')).json(),run=structuredClone(pair.records[pair.downstream_id]);
    const configuration=structuredClone(run.history.configuration);configuration.configuration_revision_id=crypto.randomUUID();configuration.study_id=sid;configuration.name='Retained conversion review';configuration.approach_binding={approach_id:saved.version.approach_id,approach_version_id:saved.version.approach_version_id,approach_digest:saved.version.digest,closure_digest:saved.closure.digest,case_id:saved.version.content.cases[0].case_id};
    const rid=crypto.randomUUID();run.run_id=rid;run.history.results.run_id=rid;run.history.configuration=configuration;run.history.approach_closure=saved.closure;
    return {sid,saved,configuration,run};
  });await ctx.close();
  const measured=d.saved.version.content.cases[0].case_id;
  const items=[{kind:'configuration',configuration_revision_id:d.configuration.configuration_revision_id,case_id:measured},{kind:'run',run_id:d.run.run_id,configuration_revision_id:d.configuration.configuration_revision_id,case_id:measured}];
  return {...d,measured,items};
}
async function routeResults(page:Page,d:any,hold?:()=>Promise<void>){
  await page.route('**/approach/versions/'+d.saved.version.approach_version_id+'/usage**',async route=>{const caseId=new URL(route.request().url()).searchParams.get('case_id');if(!caseId&&hold)await hold();await route.fulfill({json:{schema_version:'1',data:{items:d.items.filter((i:any)=>!caseId||i.case_id===caseId),next_cursor:null}}});});
  await page.route('**/configurations/'+d.configuration.configuration_revision_id,route=>route.fulfill({json:{schema_version:'1',data:{configuration:d.configuration,approach_closure:d.saved.closure}}}));
  await page.route('**/runs/'+d.run.run_id,route=>route.fulfill({json:{schema_version:'1',data:d.run}}));
}
async function openResults(page:Page,d:any){await page.goto('/ui/?workspace#'+new URLSearchParams({v:'1',study:d.sid,view:'approach',approach:d.saved.version.approach_version_id}));await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();await casesTab(page);}

test('@approach-history Results cards show exact criterion facts, remaining method work and study-wide limits without a verdict',async({page,browser,baseURL})=>{
  const d=await resultsFixture(page,browser,baseURL);await routeResults(page,d);await openResults(page,d);const results=page.getByRole('region',{name:'Results',exact:true}),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  const measured=usage.getByRole('article',{name:'Measured conversion',exact:true});await expect(measured).toContainText('1 run loaded');await expect(measured).toContainText('Completed');
  const criteria=d.run.history.results.criteria,declared=d.configuration.criteria;expect(criteria.length).toBeGreaterThan(0);
  await expect(measured.getByRole('list',{name:'Criterion evaluations for run '+d.run.run_id.slice(0,8),exact:true}).getByRole('listitem')).toHaveCount(Math.min(3,criteria.length)+(criteria.length>3?1:0));
  const first=declared.find((c:any)=>c.criterion_id===criteria[0].criterion_id),output=d.run.history.results.outputs.find((o:any)=>o.target.instance_id===first.target.instance_id&&o.target.port_id===first.target.port_id);
  await expect(measured).toContainText('Criterion 1');await expect(measured).toContainText('output '+String(output.value));await expect(measured).toContainText(String(first.threshold));
  await expect(usage.getByRole('article',{name:'Envelope extension',exact:true})).toContainText('Not evaluated in the loaded review · no run found for this case');
  const remaining=usage.getByRole('article',{name:'Remaining method work',exact:true});await expect(remaining).toContainText('Extend to the full operating envelope');await expect(remaining).toContainText('Proposed · no model linked');await expect(remaining).toContainText('Select and link a model for the full envelope.');
  // The study-wide limits aside became a Study limits link to Limits in Study details.
  await expect(results.getByRole('complementary')).toHaveCount(0);const limitsLink=results.getByRole('button',{name:'Study limits',exact:true});await limitsLink.click();
  const details=page.getByRole('dialog',{name:'Study details',exact:true}),limits=details.getByRole('region',{name:'Study limits',exact:true});await expect(limits.getByRole('heading',{name:'Limits',exact:true})).toBeFocused();
  await expect(limits).toContainText('Results apply only within the measured operating range.');
  await expect(limits).toContainText('Legacy limitation text is recorded verbatim.');
  await expect(limits).not.toContainText('No limit is mapped to an individual case or result.');
  await page.keyboard.press('Escape');await expect(limitsLink).toBeFocused();
  await expect(results.getByRole('heading',{name:'No study answer has been assessed.',exact:true})).toBeVisible();await expect(results).toContainText('Criteria are fixed-threshold checks on outputs. They do not answer the study question.');
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await results.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','results-cards-'+theme+'.png'),fullPage:false,animations:'disabled'});await readingShot(page,'results-cards-full-'+theme);}
  await page.setViewportSize({width:720,height:1000});await page.evaluate(()=>document.documentElement.dataset.theme='light');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await results.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','results-cards-720.png'),fullPage:false,animations:'disabled'});await page.setViewportSize({width:1440,height:1000});
  // Remaining work opens the exact proposed step in Methods.
  await remaining.getByRole('button',{name:'View remaining method',exact:true}).click();await expect(page.getByRole('tab',{name:'Methods',exact:true})).toHaveAttribute('aria-selected','true');await expect(page.locator('.method-map-step[aria-pressed="true"]')).toBeFocused();await expect(page.locator('.method-map-step[aria-pressed="true"]')).toContainText('Extend to the full operating envelope');
});

test('@approach-history Results late usage reply after a case filter change cannot repopulate another case',async({page,browser,baseURL})=>{
  const d=await resultsFixture(page,browser,baseURL);let release:()=>void=()=>{},held=0;const gate=new Promise<void>(resolve=>{release=resolve;});
  await routeResults(page,d,async()=>{held++;if(held===1)await gate;});await openResults(page,d);const results=page.getByRole('region',{name:'Results',exact:true}),usage=page.getByRole('region',{name:'Approach usage',exact:true});
  await expect.poll(()=>held).toBe(1);await usage.getByLabel('Findings case',{exact:true}).selectOption(d.saved.version.content.cases[1].case_id);
  await expect(results).toContainText('0 runs loaded for case Envelope extension of this approach version.');release();
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect(results).toContainText('0 runs loaded for case Envelope extension of this approach version.');await expect(usage.getByRole('article',{name:'Measured conversion',exact:true})).toHaveCount(0);await expect(results).not.toContainText('Retained conversion review');await expect(usage).not.toContainText('Retained conversion review');
  // Refresh with the filter cleared shows the exact loaded record again.
  await usage.getByLabel('Findings case',{exact:true}).selectOption('');await expect(usage.getByRole('article',{name:'Measured conversion',exact:true})).toContainText('1 run loaded');
});

test('@approach-history Results cards genuine 200 percent zoom and keyboard case navigation in both themes',async({baseURL,browser})=>{
  test.setTimeout(120000);const root=process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,extension=join(root,'artifacts/results-zoom-extension');await mkdir(extension);await writeFile(join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Results zoom verification',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));await writeFile(join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  const context=await chromium.launchPersistentContext(join(root,'artifacts/results-zoom-profile'),{executablePath:chromiumExecutable(),headless:true,viewport:null,baseURL,args:['--disable-extensions-except='+extension,'--load-extension='+extension,'--window-size=1440,1000','--no-first-run']});const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker'),geometry:any[]=[];
  try{const page=context.pages()[0]??await context.newPage(),d=await resultsFixture(page,browser,baseURL);await routeResults(page,d);await openResults(page,d);const results=page.getByRole('region',{name:'Results',exact:true}),usage=page.getByRole('region',{name:'Approach usage',exact:true});await expect(usage.getByRole('article',{name:'Measured conversion',exact:true})).toContainText('1 run loaded');
    const cdp=await context.newCDPSession(page),info=await cdp.send('Browser.getWindowForTarget');await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440,height:1087}});const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));await cdp.send('Browser.setWindowBounds',{windowId:info.windowId,bounds:{width:1440+(1440-dimensions.width),height:1087+(1000-dimensions.height)}});
    const tab=await worker.evaluate(async(url)=>{const tabs=await(globalThis as any).chrome.tabs.query({});return tabs.find((t:any)=>t.url.startsWith(url)).id;},baseURL!);await worker.evaluate(id=>(globalThis as any).chrome.tabs.setZoom(id,2),tab);expect(await worker.evaluate(id=>(globalThis as any).chrome.tabs.getZoom(id),tab)).toBe(2);expect(page.viewportSize()).toBeNull();await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);
    async function capture(name:string){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));const bounds=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio}));expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width+1);geometry.push({name,...bounds});const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await writeFile(join(root,'evidence/'+name+'.png'),Buffer.from(shot.data,'base64'));}
    for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await results.evaluate(e=>e.scrollIntoView({block:'start'}));await capture('results-200-'+theme);
      // Each case is one card; the run's View run is reachable by keyboard and unobscured.
      const view=usage.getByRole('article',{name:'Measured conversion',exact:true}).getByRole('button',{name:'View run',exact:true});await view.focus();await expect(view).toBeFocused();await view.evaluate(e=>e.scrollIntoView({block:'center'}));await capture('results-case-200-'+theme);expect(await view.evaluate(e=>{const r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===e;})).toBe(true);
      const limits=results.getByRole('button',{name:'Study limits',exact:true});await limits.focus();await limits.press('Enter');await expect(page.getByRole('dialog',{name:'Study details',exact:true}).getByRole('heading',{name:'Limits',exact:true})).toBeFocused();await capture('results-limits-200-'+theme);await page.keyboard.press('Escape');await expect(limits).toBeFocused();}
    await writeFile(join(root,'evidence/results-zoom-geometry.json'),JSON.stringify({zoom:2,viewport:null,geometry},null,2));
  }finally{await context.close();}
});

test('@approach-history run evidence reads Model4 model and component assumptions and names formats without them',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL);let variant='4';
  // Presentation overlay of one retained run response only: the exact snapshot is
  // relabelled as a Model4 record carrying model- and instance-owned assumptions.
  await page.route(`**/api/1/studies/${d.sid}/runs/${d.run.run_id}`,async route=>{const response=await route.fetch(),value=await response.json(),model=value.data.history.model_snapshot,instance=model.instances.find((i:any)=>i.instance_id!==model.root_instance_id)??model.instances[0];model.schema_version=variant;for(const definition of model.definitions)definition.quantity_definitions=definition.quantity_definitions??[];model.assumptions=[{assumption_id:crypto.randomUUID(),owner:{kind:'model'},statement:'Model4 model-owned assumption',evidence_links:[]},{assumption_id:crypto.randomUUID(),owner:{kind:'instance',instance_id:instance.instance_id},statement:'Model4 component-owned assumption',evidence_links:[]}];if(variant==='1')delete model.assumptions;await route.fulfill({response,json:value});});
  async function evidence(){await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'overview'}).toString();},d.sid);await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toBeVisible();await openRetainedRun(page,d.sid,d.run.run_id);await page.getByRole('tab',{name:'Evidence',exact:true}).click();return [page.locator('#run-panel-3').getByRole('region',{name:'Model assumptions',exact:true}),page.locator('#run-panel-3').getByRole('region',{name:'Model assumptions',exact:true})];}
  // Model and component assumptions are one owner group; each item names Whole model or its component.
  let [models,components]=await evidence();
  await expect(models).toContainText('Model4 model-owned assumption');await expect(components).toContainText('Model4 component-owned assumption');await expect(models).not.toContainText('No assumptions');
  await expect(models.getByText('Whole model',{exact:true})).toHaveCount(1);await expect(models.getByText(/^Component · /)).toHaveCount(1);
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await models.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence','run-evidence-model4-'+theme+'.png'),fullPage:false,animations:'disabled'});}
  variant='1';[models,components]=await evidence();for(const region of [models,components]){await expect(region).toContainText('Model versions saved in this older format have no assumptions.');await expect(region).not.toContainText('No assumptions');}
  variant='99';[models,components]=await evidence();for(const region of [models,components]){await expect(region).toContainText('This application cannot read assumptions from this model version format.');await expect(region).not.toContainText('No assumptions');await expect(region).not.toContainText('Model4 model-owned assumption');}
});
// An unknown configuration format is named, never read as an older format.
test('@approach-history retained configuration in an unsupported format is stated explicitly, never read as an older format',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL);let variant:string|null='99';
  // Presentation overlay of one retained run response only: the exact configuration is relabelled with an unknown format.
  await page.route(`**/api/1/studies/${d.sid}/runs/${d.run.run_id}`,async route=>{const response=await route.fetch(),value=await response.json();if(variant)value.data.history.configuration.schema_version=variant;await route.fulfill({response,json:value});});
  async function reopen(){await page.evaluate(sid=>{location.hash=new URLSearchParams({v:'1',study:sid,view:'overview'}).toString();},d.sid);await expect(page.getByRole('button',{name:'View modeling approach',exact:true})).toBeVisible();await openRetainedRun(page,d.sid,d.run.run_id);}
  const unsupported='This configuration uses a record format this application cannot display.';
  await reopen();
  await expect(page.locator('.run-detail-case')).toContainText('Case context unavailable');await expect(page.locator('.run-detail-case')).not.toContainText('No modeling approach');
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();const configuration=page.locator('#run-panel-2');
  // Record details keeps the exact serialized record; only the read view must not interpret it.
  const context=configuration.getByRole('region',{name:'Configuration context',exact:true});
  await expect(context).toContainText(unsupported);await expect(context).not.toContainText('No modeling approach is linked.');await expect(context).not.toContainText('Interpretation retained for the screening.');await expect(configuration.getByRole('heading',{name:'Inputs and provenance',exact:true})).toHaveCount(0);
  await expect(configuration.getByRole('button',{name:'Record details',exact:true})).toBeVisible();
  await page.getByRole('tab',{name:'Evidence',exact:true}).click();const evidence=page.locator('#run-panel-3');
  await expect(evidence).toContainText(unsupported);await expect(evidence.getByRole('region',{name:'Configuration assumptions',exact:true})).toHaveCount(0);
  // Control: the same exact supported record still reads with its recorded context and case.
  variant=null;await reopen();
  await expect(page.locator('.run-detail-case')).toContainText('Nominal range');
  await page.getByRole('tab',{name:'Configuration',exact:true}).click();await expect(page.locator('#run-panel-2').getByRole('region',{name:'Configuration context',exact:true})).toContainText('Interpretation retained for the screening.');await expect(page.locator('#run-panel-2')).not.toContainText(unsupported);
  await page.getByRole('tab',{name:'Evidence',exact:true}).click();await expect(page.locator('#run-panel-3').getByRole('region',{name:'Configuration assumptions',exact:true})).toBeVisible();
});
// The modified-run review reads configuration assumptions and general context from Configuration4 too.
test('@approach-history modified run review of a Configuration4 source lists assumption and general context changes',async({page,browser,baseURL})=>{
  const d=await retainedApproach(page,browser,baseURL),assumption=crypto.randomUUID(),context=d.evidence.evidence_version_id;
  // Presentation overlay of the server preview only: one added configuration assumption and one general context attachment.
  await page.route(`**/api/1/studies/${d.sid}/configurations/preview`,async route=>{const response=await route.fetch(),value=await response.json(),candidate=value.data.resolved_candidate;expect(candidate.schema_version).toBe('4');
    candidate.assumptions=[...candidate.assumptions,{assumption_id:assumption,statement:'Overlay configuration assumption',evidence_links:[]}];candidate.general_context_evidence_version_ids=[...candidate.general_context_evidence_version_ids,context];
    if(!candidate.evidence_snapshots.some((e:any)=>e.evidence_version_id===context))candidate.evidence_snapshots=[...candidate.evidence_snapshots,d.evidence];
    value.data.changes=[...value.data.changes,{path:'/assumptions/'+assumption,before:'',after:'Overlay configuration assumption'},{path:'/general_context_evidence_version_ids/'+context,before:'',after:context}];await route.fulfill({response,json:value});});
  await openRetainedRun(page,d.sid,d.run.run_id);await page.getByRole('button',{name:'Create modified run',exact:true}).click();
  await expect(page.getByRole('region',{name:'Configuration context',exact:true})).toContainText('Nominal range');await page.getByLabel('Configuration name',{exact:true}).fill('Modified review of format 4');
  await page.getByRole('button',{name:'Save configuration',exact:true}).click();const review=page.getByRole('dialog',{name:'Review modified run',exact:true});await expect(review).toBeVisible();
  const changes=review.getByRole('region',{name:'Assumption and evidence changes',exact:true});
  await expect(changes.getByRole('row').filter({hasText:'Configuration assumption'})).toContainText('Overlay configuration assumption');
  await expect(changes.getByRole('row').filter({hasText:'General context evidence'})).toContainText('Screening measurements');
  await review.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(review).toBeHidden();
});

// Guard characterization: the Workspace unsaved-changes list (approach draft, study context).
test('@approach-reading editor guard open approach editor blocks Save with its own copy; Keep and Discard follow the list',async({page})=>{
  await openProduct(page);
  if(!await page.getByRole('button',{name:'Leave editing',exact:true}).isVisible())await page.getByRole('button',{name:'Edit approach',exact:true}).click();
  await page.getByRole('button',{name:'Edit question and scope',exact:true}).click();
  const field=page.getByRole('dialog',{name:'Edit question and scope',exact:true}).getByLabel('Engineering question',{exact:true});await field.fill('Unapplied guarded question');
  const dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true});
  await page.evaluate(()=>{location.hash='';});await expect(dirty).toBeVisible();
  await expect(dirty).toContainText('Apply or discard the open editor changes before saving this draft.');
  await expect(dirty.getByRole('button',{name:'Save changes',exact:true})).toBeDisabled();
  await dirty.getByRole('button',{name:'Keep editing',exact:true}).click();await expect(field).toHaveValue('Unapplied guarded question');
  await page.evaluate(()=>{location.hash='';});await dirty.getByRole('button',{name:'Discard changes',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();
});
const refuse=(text:string)=>({status:422,contentType:'application/json',body:JSON.stringify({error:{code:'invalid_request',message:text,fields:[],outcome:'unchanged'}})});
test('@approach-reading editor guard Save writes the approach draft before leaving; a refused save keeps edits and returns focus',async({page})=>{
  const studyName=await openProduct(page);await writeQuestion(page,'Saved through the workspace guard');
  const dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true}),home=page.getByRole('button',{name:'Home',exact:true});
  let refused=false;await page.route('**/approach/draft',async route=>{if(!refused&&route.request().method()==='POST'){refused=true;await route.fulfill(refuse('Draft refused by the guard test.'));return;}await route.fallback();});
  await home.click();await expect(dirty).toBeVisible();await expect(dirty.getByRole('button',{name:'Save changes',exact:true})).toBeEnabled();
  await dirty.getByRole('button',{name:'Save changes',exact:true}).click();
  await expect(dirty).toBeHidden();expect(refused).toBe(true);await expect(home).toBeFocused();
  await expect(page.getByLabel('The modeling approach').getByRole('heading',{name:'Saved through the workspace guard',exact:true})).toBeVisible();
  await home.click();await dirty.getByRole('button',{name:'Save changes',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Open study '+studyName,exact:true}).first().click();await page.getByRole('button',{name:'View modeling approach',exact:true}).click();
  await expect(page.getByLabel('The modeling approach').getByRole('heading',{name:'Saved through the workspace guard',exact:true})).toBeVisible();
  await expect(page.getByText('Draft · saved',{exact:true})).toBeVisible();
});
test('@approach-reading editor guard refused study context save keeps the dialog and its transition; Discard restores the saved context',async({page})=>{
  // The guarded fixture proxy has no PATCH route, so only refusal and discard of study context are exercised here.
  const studyName='Guarded context '+crypto.randomUUID().slice(0,6);
  await page.goto('/ui/?workspace');
  await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'New study',exact:true}).click();await page.getByLabel('New study name',{exact:true}).fill(studyName);
  await page.getByRole('button',{name:'Create study',exact:true}).click();
  const about=page.getByRole('region',{name:'About this study',exact:true}),dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true}),home=page.getByRole('button',{name:'Home',exact:true});
  await about.getByRole('button',{name:'Edit',exact:true}).click();const edit=page.getByRole('dialog',{name:'Edit study',exact:true});
  await edit.getByLabel('Description',{exact:true}).fill('Context refused by the workspace guard');await edit.getByRole('button',{name:'Done',exact:true}).click();
  let refused=0;await page.route('**/api/1/studies/*',async route=>{if(route.request().method()==='PATCH'){refused++;await route.fulfill(refuse('Study context refused by the guard test.'));return;}await route.fallback();});
  await home.click();await expect(dirty).toBeVisible();await dirty.getByRole('button',{name:'Save changes',exact:true}).click();
  await expect(page.getByText('Study context refused by the guard test.').first()).toBeVisible();expect(refused).toBe(1);
  await expect(dirty).toBeVisible();await expect(page.getByRole('heading',{name:studyName,exact:true})).toBeVisible();
  await dirty.getByRole('button',{name:'Discard changes',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();expect(refused).toBe(1);
  await page.getByRole('button',{name:'Open study '+studyName,exact:true}).first().click();
  await expect(about).toContainText('No description yet.');
});

// Approach page and Overview question box.
test('@approach-reading Overview and the approach page share one study question box and its Study details dialog',async({page,browser,baseURL})=>{
  test.setTimeout(180000);
  await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const context=await browser.newContext({baseURL}),helper=await context.newPage();await helper.goto('/ui/');
  await helper.evaluate(async sid=>{
    const {api,controller:c}=(window as any).approachHarness;await api.login('owner','correct horse battery staple');await c.open(sid);
    c.edit({...c.getSnapshot().local,schema_version:'2',question:'Which cruise range keeps take-off mass under the limit?',scope:'Regional aircraft with kerosene and liquid hydrogen variants.',open_questions:'Does tank mass scale linearly with stored energy?',limitations:'',
      original_question:{text:'Can hydrogen work for regional flights?',attribution:{kind:'human',label:'Study owner'}},elaboration:{text:'Compare take-off mass against the certified limit for each range.',attribution:{kind:'agent',label:'Drafting assistant'}},
      assumptions:[{assumption_id:crypto.randomUUID(),statement:'Fuel price is constant over the study horizon.',role:'overall_method',evidence_links:[]}],
      limit_items:[{limit_id:crypto.randomUUID(),statement:'Results apply to regional ranges only.',evidence_links:[]}]});
    if(!await c.save()||!await c.saveVersion())throw new Error(c.getSnapshot().error);
  },sid);await context.close();
  await page.reload();await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'Back to overview',exact:true}).click();
  // Overview: the question box on top; About keeps the description, Edit and View modeling approach only.
  const box=page.getByRole('region',{name:'Study question',exact:true}),about=page.getByRole('region',{name:'About this study',exact:true});
  await expect(box.getByRole('heading',{name:'Which cruise range keeps take-off mass under the limit?',exact:true})).toBeVisible();await expect(box).toContainText('Regional aircraft with kerosene and liquid hydrogen variants.');
  await expect(about.getByRole('button')).toHaveText(['Edit','View modeling approach']);
  for(const removed of ['Study conditions & limits','Question in detail'])await expect(page.getByRole('button',{name:removed,exact:true})).toHaveCount(0);
  const order=await page.evaluate(()=>['section[aria-label="Study question"]','section[aria-label="About this study"]'].map(selector=>document.querySelector(selector)!.getBoundingClientRect().top));expect(order[0]).toBeLessThan(order[1]);
  const more=box.getByRole('button',{name:'See more details',exact:true});
  const moreBox=await more.boundingBox(),boxBox=await box.boundingBox();expect(moreBox!.x+moreBox!.width).toBeGreaterThan(boxBox!.x+boxBox!.width*0.75);expect(moreBox!.y+moreBox!.height).toBeGreaterThan(boxBox!.y+boxBox!.height*0.6);
  await s4Shots(page,'s5-overview-question',box);
  const dialog=page.getByRole('dialog',{name:'Study details',exact:true});
  async function readDetails(label:string){
    await expect(dialog.getByRole('heading', { level: 3 })).toHaveText([
      'Study question',
      'Current approach',
      'Assumptions',
      'Limits',
      'Open questions',
    ]);
    await expect(dialog).toContainText(label);
    const question=dialog.getByRole('region',{name:'Study question',exact:true});await expect(question).toContainText('Can hydrogen work for regional flights?');await expect(question).toContainText('Supplied human attribution: Study owner');await expect(question).toContainText('Supplied agent attribution: Drafting assistant');
    await expect(dialog.getByRole('region', { name: 'Open questions', exact: true })).toContainText(
      'Does tank mass scale linearly with stored energy?',
    );
    await expect(dialog.getByRole('region',{name:'Study assumptions',exact:true})).toContainText('Fuel price is constant over the study horizon.');
    await expect(dialog.getByRole('region',{name:'Study limits',exact:true})).toContainText('Results apply to regional ranges only.');
    await expect(dialog.getByRole('button',{name:'Add limit',exact:true})).toHaveCount(0);await expect(dialog.getByRole('button',{name:'Add assumption',exact:true})).toHaveCount(0);
  }
  await more.focus();await more.press('Enter');await readDetails('Current saved approach v1');
  await s4Shots(page,'s5-overview-details');
  await page.keyboard.press('Escape');await expect(more).toBeFocused();
  // The approach page shows the same box and opens the same dialog.
  await about.getByRole('button',{name:'View modeling approach',exact:true}).click();await expect(page.getByRole('heading',{name:'Modeling approach',exact:true})).toBeVisible();
  const version=(await(await page.request.get(`/api/1/studies/${sid}/approach/versions`)).json()).data.items[0].approach_version_id;await page.getByLabel('Approach version',{exact:true}).selectOption(version);
  const reader=page.getByRole('region',{name:'The modeling approach',exact:true}),approachBox=reader.getByRole('region',{name:'Study question',exact:true});
  await expect(approachBox.getByRole('heading',{name:'Which cruise range keeps take-off mass under the limit?',exact:true})).toBeVisible();
  for(const removed of ['Study conditions & limits','Question in detail'])await expect(page.getByRole('button',{name:removed,exact:true})).toHaveCount(0);
  await s4Shots(page,'s5-approach-question',approachBox);
  await approachBox.getByRole('button',{name:'See more details',exact:true}).click();await readDetails('Saved approach v1');
  await s4Shots(page,'s5-approach-details');
  await page.keyboard.press('Escape');
});

test('@approach-method method step explains in two tabs with one implementation line and opens the canonical model version',async({page,browser,baseURL})=>{
  test.setTimeout(120000);
  const data=await describedApproach(page,browser,baseURL),detail=page.getByRole('region',{name:'Selected method step',exact:true}),id8=data.model.model_revision_id.slice(0,8);
  await page.setViewportSize({width:1440,height:1000});
  await expect(page.getByRole('button',{name:'Select step 1',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(detail.getByRole('tab')).toHaveText(['Explanation','Assumptions & evidence']);
  const explanation=detail.getByRole('tabpanel',{name:'Explanation',exact:true});
  await expect(explanation.getByRole('heading',{level:3})).toHaveText(['Purpose','Why this method','Transformation']);
  await expect(explanation).toContainText('Connect explicit operating quantities to response.');await expect(explanation).toContainText('Use the declared response law for a bounded screening.');await expect(explanation).toContainText('Combine the operating quantities using the authored response law.');
  await expect(explanation.locator('.method-implemented')).toHaveText('Implemented in Model version '+id8+' · 4 inputs · 4 outputs');
  // No Model & quantities tab, quantity cards, source excerpt or element buttons.
  for(const removed of ['.method-quantity','.method-quantity-groups','.method-source','.approach-topology'])await expect(detail.locator(removed)).toHaveCount(0);
  await expect(detail.getByRole('group',{name:'Step implementation elements',exact:true})).toHaveCount(0);await expect(explanation.locator('pre')).toHaveCount(0);await expect(explanation.locator('table')).toHaveCount(0);
  await s4Shots(page,'s5-approach-methods',detail);
  // Open model version is the canonical model view, read-only, titled by its version.
  await detail.getByRole('button',{name:'Open model version',exact:true}).click();
  const open=page.getByRole('dialog',{name:'Model version '+id8,exact:true});await expect(open.getByRole('region',{name:'Model view',exact:true})).toBeVisible();
  await expect(open.getByRole('button',{name:'＋ Component',exact:true})).toHaveCount(0);await expect(open.getByRole('table',{name:'Quantities',exact:true})).toBeVisible();
  for(const removed of ['Model version JSON','Exact model element'])await expect(page.getByRole('dialog',{name:removed,exact:true})).toHaveCount(0);
  await page.keyboard.press('Escape');await expect(detail.getByRole('button',{name:'Open model version',exact:true})).toBeFocused();
});

test('@approach-configuration Cases show runs once and omit an empty limits link', async ({
  page,
  browser,
  baseURL,
}) => {
  test.setTimeout(180000);
  const d = await caseNavigation(page, browser, baseURL);
  await page.evaluate(
    ({ sid, version }) => {
      location.hash = new URLSearchParams({
        v: '1',
        study: sid,
        view: 'approach',
        approach: version,
      }).toString();
    },
    { sid: d.sid, version: d.saved.version.approach_version_id },
  );
  await expect(page.getByLabel('Approach version', { exact: true })).toHaveValue(
    d.saved.version.approach_version_id,
  );
  await casesTab(page);
  const panel = page.getByRole('tabpanel', { name: 'Cases & results', exact: true }),
    results = panel.getByRole('region', { name: 'Results', exact: true }),
    usage = panel.getByRole('region', { name: 'Approach usage', exact: true });
  await expect(usage).toContainText('All usage loaded');
  // Results first (no verdict), then one card per case; the separate case panels are gone.
  await expect(
    results.getByRole('heading', { name: 'No study answer has been assessed.', exact: true }),
  ).toBeVisible();
  await expect(results).toContainText(
    'Criteria are fixed-threshold checks on outputs. They do not answer the study question.',
  );
  for (const name of ['Cases and evaluation', 'Cases and recorded runs'])
    await expect(page.getByRole('region', { name, exact: true })).toHaveCount(0);
  await expect(results.getByRole('complementary')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^View case results/ })).toHaveCount(0);
  for (const name of ['Nominal range', 'Upper operating range', 'No specific case'])
    await expect(panel.getByRole('heading', { name, exact: true })).toHaveCount(1);
  const nominal = usage.getByRole('article', { name: 'Nominal range', exact: true });
  await expect(nominal).toContainText('Does the response fit the measured range?');
  const run = nominal.getByRole('article', { name: 'run ' + d.runs.v1, exact: true });
  await expect(run).toContainText('Version one nominal');
  await expect(run.getByLabel('Run outcomes', { exact: true }).locator('.hf-tag')).toHaveCount(2);
  await expect(run.getByRole('button', { name: 'View run', exact: true })).toBeVisible();
  // The saved configuration that produced the run is named by the run, not listed again.
  await expect(
    nominal.getByRole('button', { name: 'View configuration', exact: true }),
  ).toHaveCount(0);
  await expect(
    nominal.getByRole('button', { name: 'Create configuration for Nominal range', exact: true }),
  ).toBeVisible();
  await nominal.getByText('Why this case', { exact: true }).click();
  await expect(nominal).toContainText('Initial screening');
  await expect(nominal).toContainText('Model version ' + d.model.model_revision_id.slice(0, 8));
  await expect(
    usage
      .getByRole('article', { name: 'No specific case', exact: true })
      .getByRole('article', { name: 'run ' + d.runs.v1none, exact: true }),
  ).toContainText('Version one without case');
  await expect(
    usage.getByRole('article', { name: 'Upper operating range', exact: true }),
  ).toContainText('Not evaluated in the loaded review · no run found for this case');
  await s4Shots(page, 's5-cases-results', results);
  await s4Shots(page, 's5-cases-card', nominal);
  await expect(results.getByRole('button', { name: 'Study limits', exact: true })).toHaveCount(0);
});

// Study-wide archive on Home: a visible quiet Archive button with a confirmation. Archive is presentation
// state only: every read keeps working, nothing is deleted and a reader is refused.
async function s6bShots(page:Page,name:string){
  const cdp=await page.context().newCDPSession(page);
  try{
    for(const [size,metrics] of [['1440',{width:1440,height:1000,deviceScaleFactor:1,mobile:false}],['375',{width:375,height:812,deviceScaleFactor:1,mobile:false}],['200',{width:720,height:500,deviceScaleFactor:2,mobile:false}]] as const){
      await cdp.send('Emulation.setDeviceMetricsOverride',metrics);
      for(const theme of ['light','dark']){
        await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
        await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
        await expect.poll(()=>page.evaluate(()=>document.getAnimations().every(a=>a.playState!=='running'))).toBe(true);
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' '+size).toBe(true);
        const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
        await writeFile(join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!,'evidence',name+'-'+size+'-'+theme+'.png'),Buffer.from(shot.data,'base64'));
      }
    }
  }finally{await cdp.send('Emulation.clearDeviceMetricsOverride');await cdp.detach();await page.evaluate(()=>document.documentElement.dataset.theme='light');}
}
async function s6bListed(page:Page,archived:boolean){
  const ids:string[]=[];let cursor:string|null='';
  while(cursor!==null){const query=new URLSearchParams(archived?{archived:'true'}:{});if(cursor)query.set('cursor',cursor);const body=await(await page.request.get('/api/1/studies?'+query)).json();ids.push(...body.data.map((s:any)=>s.study_id));cursor=body.next_cursor??null;}
  return ids;
}
async function s6bRecords(page:Page,sid:string){
  const read=async(path:string)=>{const response=await page.request.get('/api/1/studies/'+sid+path);expect(response.status(),path).toBe(200);return (await response.json()).data;};
  const {archived,...study}=await read('');
  return {archived,study,approach:await read('/approach'),models:await read('/models'),configurations:await read('/configurations'),runs:await read('/runs'),evidence:await read('/evidence')};
}

test('@approach-reading Home archives a study for everyone, lists it under Archived and restores it; a reader cannot archive and nothing is deleted',async({page,browser,baseURL})=>{
  test.setTimeout(240000);
  const name=await openProduct(page);const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  await writeQuestion(page,'Which study records survive archiving?');
  const home=page.getByRole('button',{name:'Home',exact:true}),dirty=page.getByRole('dialog',{name:'Unsaved changes',exact:true});
  await home.click();await dirty.getByRole('button',{name:'Save changes',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Studies',exact:true})).toBeVisible();
  // Administrative setup before the baseline: a reader member of this study.
  expect((await page.request.post('/fixture/reader',{data:{study_id:sid}})).ok()).toBe(true);
  const before=await s6bRecords(page,sid);expect(before.archived).toBe(false);expect(before.approach.draft).not.toBeNull();
  const writes:string[]=[];page.on('request',r=>{const url=new URL(r.url());if(r.method()!=='GET'&&url.pathname.startsWith('/api/1/')&&url.pathname!=='/api/1/session')writes.push(r.method()+' '+url.pathname);});
  await home.click();
  const tabs=page.getByRole('tablist',{name:'Study list',exact:true}),studiesTab=tabs.getByRole('tab',{name:/^Studies/}),archivedTab=tabs.getByRole('tab',{name:/^Archived/});
  const activePanel=page.getByRole('region',{name:'Studies',exact:true}),archivedPanel=page.getByRole('region',{name:'Archived studies',exact:true});
  const row=activePanel.locator('article').filter({has:page.getByRole('heading',{name,exact:true})}),archivedRow=archivedPanel.locator('article').filter({hasText:name});
  const counts=async()=>[Number(await studiesTab.locator('.hf-tab__count').textContent()),Number(await archivedTab.locator('.hf-tab__count').textContent())];
  await expect(studiesTab).toHaveAttribute('aria-selected','true');await expect(row.getByRole('button')).toHaveText(['Open study','Archive']);
  const [active0,archived0]=await counts();expect(active0).toBe((await s6bListed(page,false)).length);expect(archived0).toBe((await s6bListed(page,true)).length);
  await expect(page.locator('.home-page .page-heading p')).toHaveCount(0);
  await s6bShots(page,'s6b-home-studies');
  // Confirmation; Escape and Cancel change nothing.
  const archive=row.getByRole('button',{name:'Archive study '+name,exact:true}),confirm=page.getByRole('dialog',{name:'Archive study',exact:true});
  await archive.click();await expect(confirm).toBeVisible();
  await expect(confirm).toContainText(`Archive “${name}”? It disappears from Home for everyone. Nothing is deleted; restore it from Archived.`);
  await expect(confirm.getByRole('button',{name:'Cancel',exact:true})).toBeFocused();
  await s6bShots(page,'s6b-home-confirm');
  await page.keyboard.press('Escape');await expect(confirm).toBeHidden();await expect(archive).toBeFocused();
  await archive.click();await confirm.getByRole('button',{name:'Cancel',exact:true}).click();await expect(confirm).toBeHidden();
  expect(writes).toEqual([]);await expect(row).toHaveCount(1);
  // An unknown outcome is held as the pending command and checked through its receipt, like any other command.
  await page.route(`**/api/1/studies/${sid}/archive`,async route=>{await route.fetch();await route.abort();},{times:1});
  await archive.click();await confirm.getByRole('button',{name:'Archive study',exact:true}).click();
  const check=page.getByRole('button',{name:'Check original command',exact:true});await expect(check).toBeVisible();
  await expect(page.getByText('Command outcome is uncertain. Check the original command before making more changes.',{exact:true})).toBeVisible();
  await expect(archive).toBeDisabled();await expect(page.getByRole('button',{name:'New study',exact:true})).toBeDisabled();
  await check.click();await expect(page.getByText('Original command: committed. Study lists reloaded.',{exact:true})).toBeVisible();
  await expect(check).toHaveCount(0);await expect(row).toHaveCount(0);
  expect(await counts()).toEqual([active0-1,archived0+1]);
  expect(await s6bListed(page,false)).not.toContain(sid);expect(await s6bListed(page,true)).toContain(sid);
  const archived=await s6bRecords(page,sid);expect(archived.archived).toBe(true);expect({...archived,archived:false}).toEqual(before);
  // Archived view: tag, Open study and Restore.
  await archivedTab.click();await expect(archivedTab).toHaveAttribute('aria-selected','true');
  await expect(page.getByText('Archived studies are hidden from Home for everyone. Nothing in them is deleted.',{exact:true})).toBeVisible();
  await expect(archivedRow.locator('.hf-tag')).toContainText('Archived');await expect(archivedRow.getByRole('button')).toHaveText(['Open study','Restore']);
  await s6bShots(page,'s6b-home-archived');
  // Study-wide: the reader sees it under Archived too, and cannot restore it.
  const context=await browser.newContext({baseURL}),reader=await context.newPage();
  try{
    await reader.goto('/ui/?workspace');await reader.getByLabel('Username',{exact:true}).fill('reader');await reader.getByLabel('Password',{exact:true}).fill('correct horse battery staple');await reader.getByRole('button',{name:'Sign in',exact:true}).click();
    await expect(reader.getByRole('region',{name:'Studies',exact:true})).toContainText('No studies. Archived studies are listed under Archived.');
    await reader.getByRole('tab',{name:/^Archived/}).click();
    const readerArchived=reader.getByRole('region',{name:'Archived studies',exact:true}).locator('article').filter({hasText:name});
    await readerArchived.getByRole('button',{name:'Restore study '+name,exact:true}).click();
    await expect(reader.getByRole('alert')).toContainText('Only owners and writers of this study can archive or restore it. Nothing was changed.');
    await expect(readerArchived).toHaveCount(1);expect((await s6bRecords(page,sid)).archived).toBe(true);
    // An archived study opens and reads as usual; the study header names the study once.
    await archivedRow.getByRole('button',{name:'Open study '+name,exact:true}).click();
    await expect(page.getByRole('heading',{name,exact:true,level:1})).toBeVisible();
    await expect(page.locator('.study-heading')).toHaveText(name);
    await expect(page.getByRole('region',{name:'About this study',exact:true}).getByRole('button')).toHaveText(['Edit','View modeling approach']);
    await expect(page.locator('main>footer')).toHaveText('Third-party software notices');
    await expect(page.locator('main>footer').getByRole('link',{name:'Third-party software notices',exact:true})).toHaveAttribute('href','/ui/THIRD_PARTY_NOTICES.txt');
    await s6bShots(page,'s6b-overview-archived-study');
    // Restore from Archived; the Home view is kept.
    await home.click();await expect(archivedTab).toHaveAttribute('aria-selected','true');
    await archivedRow.getByRole('button',{name:'Restore study '+name,exact:true}).click();
    await expect(page.getByText(`“${name}” restored to Studies.`,{exact:true})).toBeVisible();await expect(archivedRow).toHaveCount(0);
    expect(await counts()).toEqual([active0,archived0]);
    await studiesTab.click();await expect(row).toHaveCount(1);
    const restored=await s6bRecords(page,sid);expect(restored.archived).toBe(false);expect(restored).toEqual(before);
    // The reader cannot archive the restored study either.
    await reader.getByRole('button',{name:'Home',exact:true}).click();await reader.getByRole('tab',{name:/^Studies/}).click();
    await reader.getByRole('button',{name:'Archive study '+name,exact:true}).click();
    await reader.getByRole('dialog',{name:'Archive study',exact:true}).getByRole('button',{name:'Archive study',exact:true}).click();
    await expect(reader.getByRole('alert')).toContainText('Only owners and writers of this study can archive or restore it. Nothing was changed.');
    await expect(reader.getByRole('region',{name:'Studies',exact:true}).getByRole('heading',{name,exact:true})).toBeVisible();
  }finally{await context.close();}
  expect(await s6bListed(page,false)).toContain(sid);expect(await s6bListed(page,true)).not.toContain(sid);
  expect(await s6bRecords(page,sid)).toEqual(before);
  expect(writes).toEqual([`POST /api/1/studies/${sid}/archive`,`POST /api/1/studies/${sid}/restore`]);
});


test('@approach-reading Empty Study details preserves the full question', async ({
  page,
}) => {
  await openProduct(page);
  const question =
    'Compare fuel choices for 100 passengers over 3000–15000 km, primarily 9000 km, ' +
    'at Mach 4–8 below 575 tonnes, including ticket price.';
  await page.getByRole('button', { name: 'Edit question and scope', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'Edit question and scope', exact: true });
  await editor.getByLabel('Engineering question', { exact: true }).fill(question);
  await editor.getByRole('button', { name: 'Apply to draft', exact: true }).click();
  const trigger = page.getByRole('button', { name: 'See more details', exact: true });
  await trigger.click();
  const details = page.getByRole('dialog', { name: 'Study details', exact: true });
  // Empty authoring areas retain their add actions, without read-only filler.
  await expect(details.getByRole('button', { name: 'Add assumption', exact: true })).toBeVisible();
  await expect(details.getByRole('button', { name: 'Add limit', exact: true })).toBeVisible();
  await expect(details).not.toContainText('No assumptions');
  await expect(details).not.toContainText('No limits');
  await details.getByRole('button', { name: 'Done', exact: true }).click();
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(page.getByText('Draft · saved', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Save approach version', exact: true }).click();
  await page
    .getByRole('dialog', { name: 'Save approach version', exact: true })
    .getByRole('button', { name: 'Save version', exact: true })
    .click();
  await expect(page.getByRole('button', { name: 'Edit approach', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Back to overview', exact: true }).click();
  await trigger.click();
  await expect(details.getByRole('heading', { level: 3 })).toHaveText(['Study question']);
  await expect(details.getByRole('region', { name: 'Study question', exact: true })).toContainText(
    question,
  );
  for (const label of [
    'Original wording',
    'Elaboration',
    'Current approach',
    'Open questions',
    'Assumptions',
    'Limits',
  ])
    await expect(details.getByRole('heading', { name: label, exact: true })).toHaveCount(0);
  for (const filler of [
    'No original wording',
    'No elaboration',
    'No scope',
    'No open questions',
    'No evidence linked',
    'Earlier limits text',
  ])
    await expect(details).not.toContainText(filler);
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
});

test('@approach-assumptions Conflicting evidence stays visible in the study brief', async ({
  page,
  browser,
  baseURL,
}) => {
  await page.request.post('/fixture/model-available');
  const data = await seededConditions(page, browser, baseURL);
  const context = await browser.newContext({ baseURL }),
    helper = await context.newPage();
  await helper.goto('/ui/');
  await helper.evaluate(async (sid) => {
    const { api, controller: c } = (window as any).approachHarness;
    await api.login('owner', 'correct horse battery staple');
    await c.open(sid);
    c.edit({
      ...c.getSnapshot().local,
      assumptions: c
        .getSnapshot()
        .local.assumptions.map((a: any) => ({
          ...a,
          role: 'overall_method',
          evidence_links: a.evidence_links.map((link: any) => ({
            ...link,
            relation: 'challenges',
          })),
        })),
    });
    if (!(await c.save()) || !(await c.saveVersion())) throw new Error(c.getSnapshot().error);
  }, data.sid);
  await context.close();
  await page.reload();
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Back to overview', exact: true }).click();
  await page.getByRole('button', { name: 'See more details', exact: true }).click();
  const details = page.getByRole('dialog', { name: 'Study details', exact: true });
  await expect(details.getByText('Conflicting evidence', { exact: true })).toBeVisible();
  await expect(details).not.toContainText('Overall method assumption');
  await expect(details).toContainText('Screening measurements');
  await details.getByRole('button', { name: 'View evidence', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Evidence detail', exact: true })).toContainText(
    'Relationship to this statement: challenges',
  );
});
