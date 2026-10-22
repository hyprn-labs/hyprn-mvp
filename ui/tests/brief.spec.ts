import { test, expect, type Page } from 'playwright/test';
import { join } from 'node:path';

// The study brief on Overview through the real product, HTTP API, receipts and store.
const password = 'correct horse battery staple';

async function openStudy(page: Page) {
  const name = 'Fuel choice ' + crypto.randomUUID().slice(0, 6);
  await page.goto('/ui/?workspace');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await expect(page.locator('.hf-form-actions').getByRole('button')).toHaveText(['Cancel', 'Create study']);
  await page.getByLabel('New study name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  const brief = page.getByRole('region', { name: 'Study brief', exact: true });
  await expect(
    brief.getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ }),
  ).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Edit study', exact: true })).toHaveCount(0);
  const sid = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  return { brief, sid };
}

async function shot(page: Page, name: string) {
  await page.screenshot({
    path: join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!, 'evidence', name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}

test('@brief an engineer frames the decision on Overview, saves a draft and a version, and reads either', async ({
  page,
}) => {
  const { brief, sid } = await openStudy(page);
  await expect(brief).toContainText('No study brief yet.');
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  await expect(brief.locator('.hf-form-actions').getByRole('button')).toHaveText(['Cancel editing', 'Save draft']);
  await brief
    .getByLabel('Study question', { exact: true })
    .fill('Which fuel should a 100-passenger hypersonic aircraft use?');
  await brief.getByRole('button', { name: 'Add alternative', exact: true }).click();
  await brief.getByLabel('Alternative 1 name', { exact: true }).fill('Kerosene');
  const description = brief.getByLabel('Alternative 1 description', { exact: true });
  await expect(description).toBeVisible();
  await expect(description.locator('..')).toContainText('Alternative 1 description (optional)');
  await expect(brief.getByLabel('Scope', { exact: true }).locator('..')).toContainText(
    'Scope (optional)',
  );
  await brief.getByRole('button', { name: 'Add alternative', exact: true }).click();
  await brief.getByLabel('Alternative 2 name', { exact: true }).fill('Liquid hydrogen');
  await brief.getByRole('button', { name: 'Add constraint', exact: true }).click();
  await brief.getByLabel('Criterion 1 name', { exact: true }).fill('Take-off mass');
  await brief.getByLabel('Criterion 1 comparison', { exact: true }).selectOption('lt');
  await brief.getByLabel('Criterion 1 unit', { exact: true }).fill('kg');
  await brief.getByRole('button', { name: 'Add objective', exact: true }).click();
  await brief.getByLabel('Criterion 2 name', { exact: true }).fill('Fuel expense per seat');
  await brief.getByLabel('Criterion 2 unit', { exact: true }).fill('USD');
  // A blank threshold is unassigned: it is refused, never saved as a number.
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(brief.getByRole('alert')).toContainText('Criterion 1: the threshold is unassigned');
  expect(
    (await (await page.request.get(`/api/1/studies/${sid}/brief`)).json()).data.draft,
  ).toBeNull();
  await brief.getByLabel('Criterion 1 threshold', { exact: true }).fill('575000');
  // Priority is the order: the objective moves first.
  await brief.getByRole('button', { name: 'Move Criterion 2 up', exact: true }).click();
  await expect(brief.getByLabel('Criterion 1 name', { exact: true })).toHaveValue(
    'Fuel expense per seat',
  );
  await shot(page, 'brief-editor-light');
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    brief.getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ }),
  ).toBeFocused();
  await expect(brief.getByLabel('Study brief version', { exact: true })).toHaveValue('draft');
  const table = brief.getByRole('table', { name: 'Study criteria in priority order', exact: true });
  await expect(table.getByRole('row')).toHaveCount(3);
  await expect(table.getByRole('row').nth(1)).toContainText('Fuel expense per seat');
  await expect(table.getByRole('row').nth(2)).toContainText('less than 575000');
  const draft = (await (await page.request.get(`/api/1/studies/${sid}/brief`)).json()).data.draft;
  expect(draft.content.criteria.map((c: any) => c.kind)).toEqual(['objective', 'constraint']);
  expect(draft.content.criteria[1]).toMatchObject({
    operator: 'lt',
    threshold: 575000,
    units: 'kg',
  });
  expect('absolute_tolerance' in draft.content.criteria[1]).toBe(false);
  expect(draft.content.alternatives.map((a: any) => a.name)).toEqual([
    'Kerosene',
    'Liquid hydrogen',
  ]);

  await brief.getByRole('button', { name: 'Save brief version', exact: true }).click();
  const select = brief.getByLabel('Study brief version', { exact: true });
  await expect(select).not.toHaveValue('draft');
  const versions = (await (await page.request.get(`/api/1/studies/${sid}/brief/versions`)).json())
    .data.items;
  expect(versions.map((v: any) => v.version_number)).toEqual([1]);
  const first = versions[0];
  expect(first.content).toEqual(draft.content);
  await expect(select).toHaveValue(first.brief_version_id);
  await expect(select.locator('option:checked')).toContainText('Version 1');
  await expect(brief.getByRole('button', { name: 'Save brief version', exact: true })).toHaveCount(
    0,
  );
  await shot(page, 'brief-version-light');
  await page.evaluate(() => (document.documentElement.dataset.theme = 'dark'));
  await shot(page, 'brief-version-dark');
  await page.evaluate(() => (document.documentElement.dataset.theme = 'light'));

  // A later draft never changes the saved version.
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  await brief
    .getByLabel('Study question', { exact: true })
    .fill('Which fuel minimises expense per seat?');
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(select).toHaveValue('draft');
  await expect(brief.getByRole('region', { name: 'Study question', exact: true })).toContainText(
    'Which fuel minimises expense per seat?',
  );
  await select.selectOption(first.brief_version_id);
  await expect(brief.getByRole('region', { name: 'Study question', exact: true })).toContainText(
    'Which fuel should a 100-passenger hypersonic aircraft use?',
  );
  expect(
    (
      await (
        await page.request.get(`/api/1/studies/${sid}/brief/versions/${first.brief_version_id}`)
      ).json()
    ).data,
  ).toEqual(first);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
});

test('@brief unsaved brief edits are guarded on navigation and a stale save keeps them', async ({
  page,
  browser,
  baseURL,
}) => {
  const { brief, sid } = await openStudy(page);
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  await brief.getByLabel('Study question', { exact: true }).fill('First wording');
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    brief.getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ }),
  ).toBeFocused();
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  const question = brief.getByLabel('Study question', { exact: true });
  await question.fill('My local wording');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  const dirty = page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
  await expect(dirty).toBeVisible();
  await dirty.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(question).toHaveValue('My local wording');

  // Another session changes the draft first.
  const origin = new URL(baseURL!).origin;
  const other = await browser.newContext({ baseURL });
  const session = await other.request.post('/api/1/session', {
    data: { username: 'owner', password },
    headers: { Origin: origin },
  });
  const csrf = (await session.json()).data.csrf_token;
  const current = (await (await other.request.get(`/api/1/studies/${sid}/brief`)).json()).data
    .draft;
  const concurrent = await other.request.post(`/api/1/studies/${sid}/brief/draft`, {
    headers: { Origin: origin, 'X-CSRF-Token': csrf },
    data: {
      command_id: crypto.randomUUID(),
      expected_revision: current.revision,
      content: { ...current.content, question: 'Concurrent wording' },
    },
  });
  expect(concurrent.status()).toBe(200);
  await other.close();

  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(brief.getByRole('alert')).toContainText(
    'The brief draft changed since you opened it. Your edits are preserved.',
  );
  await expect(question).toHaveValue('My local wording');
  expect(
    (await (await page.request.get(`/api/1/studies/${sid}/brief`)).json()).data.draft.content
      .question,
  ).toBe('Concurrent wording');
  await brief.getByRole('button', { name: 'Load latest draft', exact: true }).click();
  await expect(question).toHaveValue('My local wording');
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    brief.getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ }),
  ).toBeFocused();
  expect(
    (await (await page.request.get(`/api/1/studies/${sid}/brief`)).json()).data.draft.content
      .question,
  ).toBe('My local wording');

  // Cancelling discards local edits; the saved draft is unchanged and navigation is free.
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  await question.fill('Discard this');
  await brief.getByRole('button', { name: 'Cancel editing', exact: true }).click();
  await expect(brief.getByRole('region', { name: 'Study question', exact: true })).toContainText(
    'My local wording',
  );
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Studies', exact: true })).toBeVisible();
});


test('@brief sourced assumptions, limits and criteria open exact evidence directly from saved details', async ({page, browser, baseURL}) => {
  const {brief, sid} = await openStudy(page);
  const other = await browser.newContext({baseURL});
  try {
    const origin = new URL(baseURL!).origin;
    const session = await other.request.post('/api/1/session',{headers:{Origin:origin},data:{username:'owner',password}});
    const headers = {Origin:origin, 'X-CSRF-Token':(await session.json()).data.csrf_token};
    const content = 'HYPRN evidence/1\n'+JSON.stringify({source_reference:'Reference report',location:'p. 4',excerpt:'The stated bound is 10 K.',explanation:'This is the stated design limit, not proof of suitability.'});
    const source = await other.request.post(`/api/1/studies/${sid}/evidence`,{headers,data:{command_id:crypto.randomUUID(),evidence_schema_version:'3',title:'Design limit',kind:'note',content,source_refs:[],resource_scope:{scope_version:'1',kind:'study',study_id:sid}}});
    expect(source.status()).toBe(201); const record = (await source.json()).data;
    const links = [{evidence_version_id:record.evidence_version_id,relation:'supports'}];
    const saved = await other.request.post(`/api/1/studies/${sid}/brief/draft`,{headers,data:{command_id:crypto.randomUUID(),expected_revision:null,content:{schema_version:'1',question:'Is the limit met?',original_question:null,elaboration:null,scope:'',alternatives:[],criteria:[{criterion_id:crypto.randomUUID(),kind:'constraint',name:'Rise',statement:'The rise must stay below the limit.',operator:'le',threshold:10,units:'K',evidence_links:links}],assumptions:[{assumption_id:crypto.randomUUID(),statement:'The specified limit applies.',evidence_links:links}],limits:[{limit_id:crypto.randomUUID(),statement:'Only this stated condition.',evidence_links:links}],open_questions:[]}}});
    expect(saved.status()).toBe(200);
    const published = await other.request.post(`/api/1/studies/${sid}/brief/versions`,{headers,data:{command_id:crypto.randomUUID(),expected_revision:(await saved.json()).data.revision}});
    expect(published.ok()).toBe(true);
    const revised = await other.request.post(`/api/1/studies/${sid}/evidence-families/${record.evidence_id}/versions`,{headers,data:{command_id:crypto.randomUUID(),evidence_schema_version:'3',expected_revision:record.evidence_version_id,title:'Changed source',kind:'note',content:'New note must not replace old quotation.',source_refs:[],resource_scope:record.resource_scope}});
    expect(revised.status()).toBe(201);
    await page.reload();
    await page.getByLabel('Username',{exact:true}).fill('owner'); await page.getByLabel('Password',{exact:true}).fill(password); await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await brief.getByRole('button',{name:'See details',exact:true}).click();
    const dialog = page.getByRole('dialog',{name:'Study brief details',exact:true});
    await expect(dialog.getByRole('button',{name:'View evidence (1)',exact:true})).toHaveCount(3);
    for (const section of ['Assumptions','Limits','Study criteria']) {
      const trigger = dialog.getByRole('region',{name:section,exact:true}).getByRole('button',{name:'View evidence (1)',exact:true});
      await trigger.click();
      const reader = dialog.getByRole('region',{name:'Evidence details',exact:true});
      await expect(reader.locator('blockquote')).toHaveText('The stated bound is 10 K.');
      await expect(reader.getByRole('region',{name:'Source',exact:true})).toContainText('Reference report');
      await expect(reader.getByRole('region',{name:'Explanation',exact:true})).toContainText('not proof of suitability');
      await expect(reader.getByRole('button',{name:/View evidence/})).toHaveCount(0);
      await expect(reader).not.toContainText('New note must not replace');
      await page.keyboard.press('Escape'); await expect(trigger).toBeFocused(); await expect(dialog).toBeVisible();
    }
    await shot(page,'brief-evidence');
  } finally { await other.close(); }
});
