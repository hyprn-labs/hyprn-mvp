import { test, expect, Page } from 'playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { evidenceRoot as evidence } from './evidence';
import { ownerPassword } from './support/served';
async function openModelTools(page: Page) { const tools = page.locator('details.model-tools'); if (await tools.count() && await tools.getAttribute('open') === null) await tools.locator(':scope > summary').click(); }

const source1 = '\ufeff# café: explicit coefficient, no physical defaults\r\noutputs["u"] = 2 * inputs["x"] + inputs["z"]\r\n';
const source2 = '# Explicit revised coefficient\noutputs["u"] = 3 * inputs["x"] + inputs["z"]\n';
async function login(page: Page) {
  await page.goto('/ui/');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(ownerPassword());
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Create study', exact: true })).toBeVisible();
}
async function component(page: Page, name: string, inputs: string, outputs: string, source: string) {
  await openModelTools(page);
  await page.getByLabel('New component name').fill(name);
  await page.getByLabel('Input symbols').fill(inputs);
  await page.getByLabel('Output symbols').fill(outputs);
  await page.getByRole('button', { name: 'Add component', exact: true }).click();
  await expect(page.getByLabel('Component name', { exact: true })).toHaveValue(name);
  await page.getByLabel('Load Python source file').setInputFiles({ name: 'equation.py', mimeType: 'text/x-python', buffer: Buffer.from(source) });
  if (!await page.getByLabel('Component assumptions').isVisible()) await page.getByText('Assumptions', { exact: true }).click();
  await page.getByLabel('Component assumptions').fill('Real scalar inputs; equation declared explicitly for this rehearsal.');
  await page.getByRole('button', { name: 'Save component', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Component saved');
}
async function configuration(page: Page, name: string, inputs: Record<string, string>) {
  await page.getByRole('button', { name: 'Commit model snapshot', exact: true }).click();
  await page.getByLabel('Configuration name', { exact: true }).fill(name);
  for (const [label, value] of Object.entries(inputs)) {
    await page.getByLabel(label + ' value', { exact: true }).fill(value);
    await page.getByRole('textbox', { name: label + ' provenance', exact: true }).fill('Explicit manual acceptance input; dimensionless.');
  }
  // Configuration notes are no longer authored in the UI.
  await expect(page.getByRole('textbox', { name: 'Configuration notes', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
  await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
}
async function run(page: Page, sid: string, expected: number[]) {
  const response = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith(`/studies/${sid}/runs`));
  await page.getByRole('button', { name: 'Run model', exact: true }).click();
  const accepted = (await (await response).json()).data;
  const url = `/api/1/studies/${sid}/runs/${accepted.run_id}`;
  let detail: any;
  await expect.poll(async () => {
    detail = (await (await page.request.get(url)).json()).data;
    return detail.history?.results?.outputs.map((o: any) => o.value).sort((a: number,b: number) => a-b);
  }, { timeout: 120000 }).toEqual(expected);
  await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible();
  expect(detail.history.errors).toEqual([]);
  const root = `${evidence}/09-3-artifacts/${accepted.run_id}`;
  mkdirSync(root, { recursive: true });
  writeFileSync(`${root}/detail.json`, JSON.stringify(detail, null, 2));
  // Download executable/source/identity/result proof through the public API.
  // Full license/provenance inventories are compared data-only against native
  // storage by the companion harness, avoiding thousands of duplicate HTTP reads.
  const selected = detail.history.artifacts.filter((a:any) => /^(generated\/|sources\/|locks\/|configuration.json$|context.json$|model.json$|manifest.json$|preparation.json$|result.json$|evidence\/)/.test(a.name));
  for (const artifact of selected) {
    const response = await page.request.get(`${url}/artifacts/${artifact.artifact_id}`);
    expect(response.status()).toBe(200);
    const raw = await response.body();
    expect(raw.length).toBe(artifact.size);
    expect(createHash('sha256').update(raw).digest('hex')).toBe(artifact.sha256);
    writeFileSync(`${root}/${artifact.artifact_id}`, raw);
  }
  writeFileSync(`${root}/downloaded.json`, JSON.stringify(selected.map((a:any)=>a.artifact_id)));
  return detail;
}

test('empty authoring to 7/49, coefficient edit to 9/81, unrelated equation and frozen original', async ({ page }) => {
  test.setTimeout(360000);
  const traffic: Array<{method:string,url:string}> = [];
  page.on('request', r => { if (['fetch','xhr'].includes(r.resourceType())) traffic.push({method:r.method(),url:r.url()}); });
  try {
    await login(page);
    await page.getByLabel('New study name').fill(`Full migration ${crypto.randomUUID()}`);
    await page.getByRole('button', { name: 'Create study', exact: true }).click();
    await page.getByLabel('New model name').fill('Explicit scalar chain');
    await page.getByRole('button', { name: 'Create model', exact: true }).click();
    await expect(page.getByText('Add a component to start.', { exact: true })).toBeVisible();
    const sid = await page.getByRole('combobox', { name: 'Study', exact: true }).inputValue();
    const mid = await page.getByRole('combobox', { name: 'Model', exact: true }).inputValue();
    await page.getByText('Study context', { exact: true }).click();
    await page.getByLabel('Description', { exact: true }).fill('Original frozen scalar rehearsal context.');
    await page.getByLabel('Boundary', { exact: true }).fill('Two real scalar components; explicit dimensionless inputs.');
    await page.getByRole('button', { name: 'Save study context', exact: true }).click();
    await component(page, 'Scale', 'x, z', 'u', source1);
    await component(page, 'Square', 'u', 'y', 'outputs["y"] = inputs["u"] ** 2\n');
    await openModelTools(page);
    await page.getByLabel('Connection output').selectOption({ label: 'Scale · u (dimensionless)' });
    await page.getByLabel('Connection input').selectOption({ label: 'Square · u (dimensionless)' });
    const connect = page.getByRole('button', { name: 'Connect ports', exact: true });
    await connect.focus(); await connect.press('Enter');
    await expect(page.getByText('Scale · u → Square · u', { exact: true })).toBeVisible();
    await configuration(page, 'Original 2 and 3', {'Scale · x':'2', 'Scale · z':'3'});
    const first = await run(page, sid, [7,49]);
    expect(first.history.model_snapshot.source_files.some((s:any) => Buffer.from(s.bytes,'base64').equals(Buffer.from(source1)))).toBeTruthy();
    await openModelTools(page);
    await page.getByRole('button', { name: 'Select Scale', exact: true }).click();
    await page.getByRole('textbox', { name: 'Python source', exact: true }).fill(source2);
    await page.getByRole('button', { name: 'Save component', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Component saved');
    await expect(page.getByRole('button', { name: 'Run model', exact: true })).toBeDisabled();
    await configuration(page, 'Coefficient changed, same inputs', {'Scale · x':'2', 'Scale · z':'3'});
    const second = await run(page, sid, [9,81]);
    expect(second.history.configuration.model_revision_id).not.toBe(first.history.configuration.model_revision_id);
    expect(second.history.model_snapshot.source_files.some((s:any) => Buffer.from(s.bytes,'base64').toString() === source2)).toBeTruthy();
    await page.getByRole('button', { name: 'Copy configuration to draft', exact: true }).click();
    await page.getByLabel('Scale · x value', { exact: true }).fill('4');
    await page.getByRole('button', { name: 'Commit configuration', exact: true }).click();
    await expect(page.getByText('Configuration committed. Run is a separate action.', { exact: true })).toBeVisible();
    expect((await (await page.request.get(`/api/1/studies/${sid}/runs`)).json()).data).toHaveLength(2);
    await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Changed context after both frozen runs.');
    await page.getByRole('button', { name: 'Save study context', exact: true }).click();
    await page.getByLabel('New model name').fill('Unrelated rational equation');
    await page.getByRole('button', { name: 'Create model', exact: true }).click();
    await expect(page.getByText('Add a component to start.', { exact: true })).toBeVisible();
    await component(page, 'Rational', 'x, k', 'y', 'outputs["y"] = inputs["k"] / (1 + inputs["x"] ** 2)\n');
    await configuration(page, 'Unrelated explicit inputs', {'Rational · x':'2','Rational · k':'3'});
    const third = await run(page, sid, [0.6]);
    await page.getByRole('combobox', { name: 'Model', exact: true }).selectOption(mid);
    const inspect = page.getByRole('button', { name: `Inspect run ${first.run_id}`, exact: true });
    await inspect.focus(); await inspect.press('Enter');
    await expect(page.getByRole('heading', { name: 'Outputs', exact: true })).toBeVisible();
    expect((await (await page.request.get(`/api/1/studies/${sid}/runs/${first.run_id}`)).json()).data).toEqual(first);
    await page.getByRole('region', { name:'Run details' }).scrollIntoViewIfNeeded();
    await page.screenshot({path:`${evidence}/09-3-desktop.png`});
    await page.setViewportSize({width:720,height:900});
    await page.getByRole('heading', { name:'Outputs',exact:true }).scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({path:`${evidence}/09-3-reflow-720.png`});
    writeFileSync(`${evidence}/09-3-journey.json`, JSON.stringify({entry:'empty_model',study_id:sid,model_id:mid,
      expected_outputs:[[7,49],[9,81],[0.6]], original_unchanged:true,source_changed:true,input_changed:true,human_observer:null,
      reflow:'720px viewport equivalent to 1440px at 200%; not actual browser zoom',
      runs:[first,second,third].map((r:any) => ({run_id:r.run_id,outputs:r.history.results.outputs.map((o:any)=>o.value).sort((a:number,b:number)=>a-b)}))},null,2));
  } finally {writeFileSync(`${evidence}/09-3-public-requests.json`,JSON.stringify(traffic,null,2));}
});

test('long source remains locally scrollable with keyboard escape at equivalent reflow', async ({page}) => {
  // The journey above recorded its study and model in this run's evidence folder.
  const saved = JSON.parse(readFileSync(`${evidence}/09-3-journey.json`, 'utf8'));
  await login(page);
  let writes = 0; page.on('request',r=>{if(['POST','PATCH','DELETE'].includes(r.method()))writes++;});
  await page.getByRole('combobox',{name:'Study',exact:true}).selectOption(saved.study_id);
  await page.getByRole('combobox',{name:'Model',exact:true}).selectOption(saved.model_id);
  await openModelTools(page);
  await page.getByRole('button',{name:'Select Scale',exact:true}).click();
  await page.setViewportSize({width:720,height:900});
  const source=page.getByRole('textbox',{name:'Python source',exact:true});
  const long='# Local unsaved long source — café '.repeat(30)+'\n'+Array.from({length:300},(_,i)=>`# Explicit engineering note ${i}`).join('\n')+'\n'+source2;
  await source.fill(long);
  await expect(source).toHaveValue(long);
  expect(await source.evaluate(e=>e.scrollHeight>e.clientHeight)).toBeTruthy();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await source.press('Escape');
  await expect(page.getByRole('button',{name:'Save component',exact:true})).toBeFocused();
  await source.scrollIntoViewIfNeeded();
  await page.screenshot({path:`${evidence}/09-3-long-source.png`});
  expect(writes).toBe(0);
  writeFileSync(`${evidence}/09-3-long-source.json`,JSON.stringify({source_length:long.length,lines:long.split('\n').length,keyboard_escape:true,document_overflow:false,mutations_after_login:writes,reflow:'720px equivalent; not actual browser zoom'}));
});
