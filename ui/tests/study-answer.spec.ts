import { test, expect, type Page } from 'playwright/test';
import { join } from 'node:path';

async function openStudy(page: Page) {
  await page.goto('/ui/?workspace');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page
    .getByLabel('Study name', { exact: true })
    .fill('Response decision ' + crypto.randomUUID().slice(0, 6));
  await page.getByLabel('Study question', { exact: true })
    .fill('What must this engineering study establish?');
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  const answer = page.getByRole('region', { name: 'Study answer', exact: true });
  await expect(
    answer.getByRole('button', { name: /^(Edit answer|Create new version|Continue draft)$/ }),
  ).toBeEnabled();
  const sid = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  return { answer, sid };
}

async function navigate(page: Page, name: string) {
  await page
    .getByRole('navigation', { name: 'Workspace sections' })
    .getByRole('button', { name, exact: true })
    .click();
}

async function shot(page: Page, name: string) {
  await page.screenshot({
    path: join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!, 'evidence', name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}

test('@study-answer answers cite analyses and retain exact history', async ({ page }) => {
  const { answer, sid } = await openStudy(page);
  const seeded = await page.request.post('/fixture/calculation-seed', { data: { study_id: sid } });
  expect(seeded.ok()).toBe(true);
  const seed = await seeded.json();
  await navigate(page, 'Experiments');
  await page.getByRole('button', { name: 'New analysis', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'New analysis', exact: true });
  await editor.getByLabel('Analysis name', { exact: true }).fill('Response screen');
  await editor.getByLabel(seed.configuration_name, { exact: true }).check();
  await expect(editor.getByText('Evaluate study criteria', { exact: true })).toHaveCount(0);
  await editor.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(editor).toBeHidden();
  await navigate(page, 'Overview');
  await expect(page.getByLabel('Study brief version', { exact: true })).not.toHaveValue('draft');
  await answer
    .getByRole('button', { name: /^(Edit answer|Create new version|Continue draft)$/ })
    .click();
  await answer.getByLabel('Brief version answered', { exact: true }).selectOption({ index: 1 });
  await answer
    .getByRole('checkbox', { name: 'Design A: Response screen · version 1', exact: true })
    .check();
  await answer.getByLabel('Cell alternative', { exact: true }).selectOption({ label: 'Design A' });
  await answer.getByLabel('Cell criterion', { exact: true }).selectOption({ label: 'u' });
  await answer.getByLabel('Cell analysis version', { exact: true }).selectOption({ index: 1 });
  await expect(answer.getByLabel('Cell run', { exact: true })).toBeEnabled();
  await answer.getByLabel('Cell run', { exact: true }).selectOption(seed.run);
  await answer.getByRole('button', { name: 'Add table cell', exact: true }).click();
  await answer.getByLabel('Outcome kind', { exact: true }).selectOption('recommended');
  await answer
    .getByLabel('Outcome reason', { exact: true })
    .fill(
      'The reference point meets the response constraint; this screen does not qualify a design.',
    );
  await answer
    .getByLabel('Exploration analysis version', { exact: true })
    .selectOption({ index: 1 });
  const shownOutputs = answer.getByRole('group', { name: 'Shown outcomes', exact: true });
  await expect(shownOutputs.getByRole('checkbox')).toHaveCount(2);
  await shownOutputs.getByRole('checkbox').first().check();
  await shot(page, 'answer-editor-light');
  let failExplorationRead = true;
  await page.route('**/analysis-versions/*/exploration?*', async (route) => {
    if (failExplorationRead) {
      failExplorationRead = false;
      await route.abort('timedout');
    } else {
      await route.continue();
    }
  });
  await answer.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    answer.getByRole('button', { name: /^(Edit answer|Create new version|Continue draft)$/ }),
  ).toBeFocused();
  await answer.getByRole('button', { name: 'Retry loading results', exact: true }).click();
  await expect(answer.getByLabel(/Calculated: 15[01]/)).toBeVisible();
  await page.unroute('**/analysis-versions/*/exploration?*');
  const comparison = answer.getByRole('table', {
    name: 'Alternatives comparison',
  });
  await expect(comparison).toContainText(/15[01] Dimensionless/);
  await expect(comparison).toContainText('Met');
  // Headings and help align independently of the version selector's caption.
  const geometry = await answer.evaluate((region) => {
    const heading = region.querySelector('h2')!;
    const help = region.querySelector('[aria-label="Help: Study answer"]')!;
    const section = region.querySelector('h3')!;
    const a = heading.getBoundingClientRect(),
      b = help.getBoundingClientRect();
    return {
      gap: b.left - a.right,
      centers: Math.abs(a.top + a.height / 2 - b.top - b.height / 2),
      title: parseFloat(getComputedStyle(heading).fontSize),
      section: parseFloat(getComputedStyle(section).fontSize),
    };
  });
  expect(geometry.gap).toBeGreaterThan(0);
  expect(geometry.gap).toBeLessThan(20);
  expect(geometry.centers).toBeLessThan(2);
  expect(geometry.title).toBeGreaterThan(geometry.section);
  await expect(answer.getByRole('region', { name: 'Conclusion', exact: true })).toContainText(
    'Recommended',
  );
  await answer.getByRole('button', { name: 'View model', exact: true }).click();
  const modelDialog = page.getByRole('dialog', { name: 'Model', exact: true });
  await expect(modelDialog.getByRole('region', { name: 'Model view', exact: true })).toBeVisible();
  await expect(
    modelDialog.getByRole('button', { name: 'Open model page', exact: true }),
  ).toBeVisible();
  const alignedHelp = await modelDialog.evaluate((dialog) => {
    const title = dialog.querySelector('h2')!.getBoundingClientRect();
    const help = dialog.querySelector('[aria-label="Help: Model"]')!.getBoundingClientRect();
    return Math.abs(title.top + title.height / 2 - help.top - help.height / 2) < 2;
  });
  expect(alignedHelp).toBe(true);
  await modelDialog.getByRole('button', { name: 'Done', exact: true }).click();
  const draft = (await (await page.request.get(`/api/1/studies/${sid}/answer`)).json()).data.draft;
  expect(draft.content.comparison[0].run_id).toBe(seed.run);
  expect(draft.content.comparison[0].evaluation.outcome).toBe('met');
  await answer.getByRole('button', { name: 'Save answer version', exact: true }).click();
  await expect(answer.getByRole('alert')).toContainText('Prepare and check joint exploration');
  await answer
    .getByRole('button', { name: /^(Edit answer|Create new version|Continue draft)$/ })
    .click();
  await answer.getByLabel('Exploration analysis version', { exact: true }).selectOption('');
  await answer.getByRole('button', { name: 'Save draft', exact: true }).click();
  await answer.getByRole('button', { name: 'Save answer version', exact: true }).click();
  await expect(answer.getByLabel('Study answer version', { exact: true })).not.toHaveValue('draft');
  const saved = (await (await page.request.get(`/api/1/studies/${sid}/answer`)).json()).data
    .latest_version;
  expect(saved.content.schema_version).toBe('2');
  expect(saved.content.comparison).toEqual(draft.content.comparison);
  expect(saved.content.exploration_basis).toBeNull();
  await expect(
    answer.getByRole('heading', { name: 'Alternatives comparison', exact: true }),
  ).toBeVisible();
  await expect(answer).not.toContainText('saved versions never change');
  await expect(answer).not.toContainText(seed.run);
  await shot(page, 'answer-version-light');
  await page.evaluate(() => (document.documentElement.dataset.theme = 'dark'));
  await shot(page, 'answer-version-dark');
  await answer
    .getByRole('button', { name: /^(Edit answer|Create new version|Continue draft)$/ })
    .click();
  await answer.getByLabel('Outcome reason', { exact: true }).fill('Later interpretation');
  await navigate(page, 'Experiments');
  const unsaved = page.getByRole('dialog', { name: 'Unsaved changes', exact: true });
  await expect(unsaved).toBeVisible();
  await unsaved.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(answer.getByLabel('Outcome reason', { exact: true })).toHaveValue(
    'Later interpretation',
  );
  await answer.getByRole('button', { name: 'Save draft', exact: true }).click();
  await answer
    .getByLabel('Study answer version', { exact: true })
    .selectOption(saved.answer_version_id);
  await expect(answer).not.toContainText('Later interpretation');
  expect(
    (
      await (
        await page.request.get(`/api/1/studies/${sid}/answer/versions/${saved.answer_version_id}`)
      ).json()
    ).data,
  ).toEqual(saved);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
});

test('@study-answer fresh briefs appear and missing evidence stays explicit', async ({ page }) => {
  const sessionRead = page.waitForResponse((response) => response.url().endsWith('/api/1/session') && response.request().method() === 'POST');
  const { answer, sid } = await openStudy(page);
  const headers = {Origin:new URL(page.url()).origin, 'X-CSRF-Token':(await (await sessionRead).json()).data.csrf_token};
  const created = await page.request.post(`/api/1/studies/${sid}/evidence`,{headers,data:{command_id:crypto.randomUUID(),evidence_schema_version:'3',title:'Review basis',kind:'note',content:'An authored reference note, without an exact excerpt.',source_refs:[],resource_scope:{scope_version:'1',kind:'study',study_id:sid}}});
  expect(created.status()).toBe(201);
  const citedEvidence = (await created.json()).data;
  const brief = page.getByRole('region', { name: 'Study brief', exact: true });
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  await brief
    .getByLabel('Study question', { exact: true })
    .fill('Can the proposed design meet the response limit?');
  await brief.getByRole('button', { name: 'Add alternative', exact: true }).click();
  await brief.getByLabel('Alternative 1 name', { exact: true }).fill('Proposed design');
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await brief.getByRole('button', { name: 'Save brief version', exact: true }).click();
  await expect(brief.getByLabel('Study brief version', { exact: true })).not.toHaveValue('draft');
  await answer
    .getByRole('button', { name: /^(Edit answer|Create new version|Continue draft)$/ })
    .click();
  await answer.getByLabel('Brief version answered', { exact: true }).selectOption({ index: 1 });
  await answer.getByLabel('Cited record kind',{exact:true}).selectOption('evidence_version');
  await answer.getByLabel('Cited record',{exact:true}).selectOption(citedEvidence.evidence_version_id);
  await answer.getByRole('button',{name:'Add justification',exact:true}).click();
  await answer.getByLabel('Justification 1 reason',{exact:true}).fill('This note records the review context.');
  await answer.getByLabel('Outcome kind', { exact: true }).selectOption('no_recommendation');
  await answer
    .getByLabel('Outcome reason', { exact: true })
    .fill('No analysis has yet assessed the proposed design.');
  await answer.getByRole('button', { name: 'Save draft', exact: true }).click();
  await answer.getByRole('button', { name: 'Save answer version', exact: true }).click();
  await expect(answer.getByLabel('Study answer version', { exact: true })).not.toHaveValue('draft');
  const recommendation = answer.getByLabel('Recommendation', { exact: true });
  await expect(recommendation).toContainText('No recommendation');
  await expect(answer.getByRole('region', { name: 'Evidence and reasoning', exact: true })).toContainText('Insufficient evidence');
  const evidenceButton = answer.getByRole('region',{name:'Answer basis',exact:true}).getByRole('button',{name:'View evidence (1)',exact:true});
  await evidenceButton.click();
  const reader = page.getByRole('region',{name:'Evidence details',exact:true});
  await expect(reader.getByRole('region',{name:'Evidence note',exact:true})).toContainText(citedEvidence.content);
  await expect(reader.getByRole('button',{name:/View evidence/})).toHaveCount(0);
  await page.keyboard.press('Escape'); await expect(evidenceButton).toBeFocused();
  await expect(answer.getByRole('table', { name: 'Alternatives comparison' })).toContainText(
    'No comparison recorded',
  );
});
