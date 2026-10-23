import { test, expect, type Page } from 'playwright/test';
import { join } from 'node:path';

// Calculations through the real product, HTTP API, receipts and store. The study holds a saved
// brief version, two saved configurations of one model version and one recorded run; the
// modeling service is declared offline, so everything shown comes from retained records.
const password = 'correct horse battery staple';

async function openStudy(page: Page, seed = '/fixture/calculation-seed') {
  const name = 'Response limits ' + crypto.randomUUID().slice(0, 6);
  await page.goto('/ui/?workspace');
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(password);
  const session = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/1/session') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const csrf = (await (await session).json()).data.csrf_token as string;
  await page.getByRole('button', { name: 'New study', exact: true }).click();
  await page.getByLabel('New study name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Create study', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Study brief', exact: true })).toBeVisible();
  const sid = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('study')!;
  const seeded = await page.request.post(seed, { data: { study_id: sid } });
  expect(seeded.ok()).toBe(true);
  return {
    sid,
    csrf,
    ...((await seeded.json()) as {
      configuration: string;
      configuration_name: string;
      other: string;
      run: string;
    }),
  };
}

async function shot(page: Page, name: string) {
  await page.screenshot({
    path: join(process.env.HYPRN_MVP_TEST_SCOPE_ROOT!, 'evidence', name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}

async function openCalculations(page: Page) {
  await page
    .getByRole('navigation', { name: 'Workspace sections' })
    .getByRole('button', { name: 'Experiments', exact: true })
    .click();
  await expect(page.getByRole('tab', { name: 'Analyses', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
}

test('@calculations each run reads against the brief criteria bound to its configurations', async ({
  page,
}) => {
  const seeded = await openStudy(page);
  await openCalculations(page);
  const list = page.getByRole('region', { name: 'Analyses', exact: true });
  await expect(list).toContainText('No analyses yet.');
  for (const width of [1440, 720, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const rightAligned = await list
      .getByRole('button', { name: 'New analysis', exact: true })
      .evaluate((button) => {
        const parent = button.closest('.hf-collection-status')!;
        return (
          Math.abs(button.getBoundingClientRect().right - parent.getBoundingClientRect().right) < 2
        );
      });
    expect(rightAligned).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });

  await list.getByRole('button', { name: 'New analysis', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'New analysis', exact: true });
  await editor.getByLabel('Analysis name', { exact: true }).fill('Cruise points');
  await editor
    .getByLabel('Analysis description', { exact: true })
    .fill('Compare the selected conditions.');
  await editor.getByLabel(seeded.configuration_name, { exact: true }).check();
  await expect(editor.getByText('Evaluate study criteria', { exact: true })).toHaveCount(0);
  await expect(editor.getByRole('combobox')).toHaveCount(0);
  await editor.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(editor).toBeHidden();

  await expect(page.getByRole('heading', { name: 'Cruise points', exact: true })).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Analysis description', exact: true }),
  ).toContainText('Compare the selected conditions.');
  const bindings = page.getByRole('region', { name: 'Analysis results', exact: true });
  await expect(bindings.getByRole('columnheader', { name: /linear · u/ })).toBeVisible();
  await expect(bindings).toContainText('less than 200 Dimensionless');
  await expect(bindings).toContainText('Minimize');
  const runs = page.getByRole('region', { name: 'Analysis results', exact: true });
  await expect(runs.getByRole('row')).toHaveCount(2);
  // The constraint is compared with its threshold; the objective reports its calculated value.
  await expect(runs).toContainText(/Met\s*15[01]/);
  await expect(runs).toContainText(/Calculated\s*15[01]/);
  await expect(runs).not.toContainText('Not met');
  await expect(page.getByRole('button', { name: 'Help: Versions' })).toHaveCount(0);
  const resultsHelp = page.getByRole('button', { name: 'Help: Results', exact: true });
  await resultsHelp.click();
  const resultsHelpDialog = page.getByRole('dialog', { name: 'Results', exact: true });
  await expect(resultsHelpDialog).toContainText('Completed describes execution');
  await resultsHelpDialog.press('Escape');
  await expect(resultsHelp).toBeFocused();
  const completed = runs.getByText('Completed', { exact: true });
  await expect(completed).toBeVisible();
  expect(await completed.evaluate((node) => node.closest('button,a'))).toBeNull();
  const openPoint = runs.getByRole('button', { name: /^Open configuration ·/ });
  await expect(openPoint).toHaveText('');
  await expect(openPoint.locator('svg')).toHaveCount(1);
  expect(
    await runs
      .locator('tbody tr')
      .first()
      .locator('td')
      .evaluateAll((cells) =>
        cells.every((cell) => getComputedStyle(cell).verticalAlign === 'middle'),
      ),
  ).toBe(true);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await shot(page, 'calculation-record-light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await shot(page, 'calculation-record-dark');
  await page.emulateMedia({ colorScheme: 'light' });

  // A new version adds a point; the saved first version keeps its exact set.
  await page.getByRole('button', { name: 'Analysis settings', exact: true }).click();
  const next = page.getByRole('dialog', { name: 'Analysis settings', exact: true });
  await expect(next).toContainText('Read-only');
  await expect(next.getByLabel('Analysis name', { exact: true })).toHaveCount(0);
  await expect(next.getByText('Name', { exact: true })).toBeVisible();
  await expect(next.getByRole('button', { name: 'Save version', exact: true })).toHaveCount(0);
  await expect(
    next.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toBeVisible();
  await expect(
    next.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toBeDisabled();
  await expect(
    next.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(next.getByRole('button', { name: 'Generate samples', exact: true })).toBeVisible();
  await expect(next.getByRole('button', { name: 'Generate samples', exact: true })).toBeDisabled();
  await expect(next.getByRole('button', { name: 'Generate samples', exact: true })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  await next.getByRole('button', { name: 'Create new version', exact: true }).click();
  await expect(next.getByLabel(seeded.configuration_name, { exact: true })).toBeChecked();
  await next.getByLabel('Cruise point B', { exact: true }).check();
  await next.getByRole('button', { name: 'Save version', exact: true }).click();
  await expect(next).toBeHidden();
  await expect(page.getByText('Configurations 1–2 of 2', { exact: true })).toBeVisible();
  const versions = page.getByLabel('Analysis version', { exact: true });
  await expect(versions.locator('option')).toHaveCount(2);
  // The added configuration is visible before execution; it cannot inherit another point's result.
  await expect(runs.getByRole('row')).toHaveCount(3);
  await expect(runs.getByRole('row').filter({ hasText: 'Cruise point B' })).toContainText(
    'Not run',
  );
  await expect(runs).toContainText('Completed');
  await expect(runs.getByRole('row').filter({ hasText: 'Cruise point B' })).not.toContainText(
    'Measured',
  );
  // Launch pins the existing calculated result and submits only the missing member.
  await page.getByRole('button', { name: 'Launch analysis', exact: true }).click();
  expect(await dispatch(page)).toBeGreaterThan(0);
  await expect(runs.getByRole('row').filter({ hasText: 'Cruise point B' })).toContainText('Queued');
  await expect(runs.getByRole('row').filter({ hasText: seeded.configuration_name })).toContainText(
    'Completed',
  );
  await expect(runs.getByRole('combobox', { name: /displayed run$/ })).toHaveCount(0);
  const first = await versions.locator('option').nth(1).getAttribute('value');
  await versions.selectOption(first!);
  await expect(page.getByText('Configurations 1–1 of 1', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Analysis settings', exact: true }).click();
  const historical = page.getByRole('dialog', { name: 'Analysis settings', exact: true });
  await expect(historical.getByLabel(seeded.configuration_name, { exact: true })).toBeChecked();
  await expect(historical.getByLabel('Cruise point B', { exact: true })).not.toBeChecked();
  await expect(
    historical.getByRole('button', { name: 'Create new version', exact: true }),
  ).toHaveCount(0);
  await historical.getByRole('button', { name: 'Done', exact: true }).click();

  // The run opens its own record.
  await runs.getByRole('button', { name: /^Open run ·/ }).click();
  await expect(page).toHaveURL(new RegExp('run=' + seeded.run));
});

test('@calculations reference marks label a configuration version without changing it', async ({
  page,
}) => {
  const seeded = await openStudy(page);
  const before = await (
    await page.request.get(`/api/1/studies/${seeded.sid}/configurations/${seeded.other}`)
  ).json();
  await openCalculations(page);
  await page.getByRole('tab', { name: 'Configurations', exact: true }).click();
  const list = page.getByRole('region', { name: 'Configurations', exact: true });
  await list
    .getByRole('button', { name: 'Mark as reference: Cruise point B', exact: true })
    .click();
  const card = list.getByRole('article').filter({ hasText: 'Cruise point B' });
  await expect(card).toContainText('Reference');
  // Metadata spacing belongs to the shared row, including when the row wraps.
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate((value) => {
      document.documentElement.dataset.theme = value;
    }, theme);
    for (const width of [1440, 720, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      const tag = card.getByText('Reference', { exact: true });
      const inputs = card.getByText(/^\d+ inputs$/);
      await expect(inputs).toBeVisible();
      const badgeBox = (await tag.boundingBox())!;
      const inputsBox = (await inputs.boundingBox())!;
      const gap = await card.evaluate((element) =>
        parseFloat(getComputedStyle(element).getPropertyValue('--space-2')),
      );
      const sameLine =
        inputsBox.y < badgeBox.y + badgeBox.height && badgeBox.y < inputsBox.y + inputsBox.height;
      const clearance = sameLine
        ? Math.max(
            inputsBox.x - (badgeBox.x + badgeBox.width),
            badgeBox.x - (inputsBox.x + inputsBox.width),
          )
        : Math.max(
            inputsBox.y - (badgeBox.y + badgeBox.height),
            badgeBox.y - (inputsBox.y + inputsBox.height),
          );
      expect(clearance).toBeGreaterThanOrEqual(gap - 0.5);
      await shot(page, `configuration-reference-${theme}-${width}`);
    }
  }
  await page.evaluate(() => {
    document.documentElement.dataset.theme = 'light';
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.reload();
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    list.getByRole('button', { name: 'Clear reference mark of Cruise point B', exact: true }),
  ).toBeVisible();
  await expect(
    list.getByRole('article').filter({ hasText: seeded.configuration_name }),
  ).not.toContainText('Reference');
  await list
    .getByRole('button', { name: 'Clear reference mark of Cruise point B', exact: true })
    .click();
  await expect(
    list.getByRole('button', { name: 'Mark as reference: Cruise point B', exact: true }),
  ).toBeVisible();
  await expect(card.getByText('Reference', { exact: true })).toHaveCount(0);
  await expect(card.getByText(/^\d+ inputs$/)).toBeVisible();
  const after = await (
    await page.request.get(`/api/1/studies/${seeded.sid}/configurations/${seeded.other}`)
  ).json();
  expect(after.data).toEqual(before.data);
});

test('@calculations the analysis record fits genuine 200 percent zoom in both themes', async ({
  page,
}) => {
  const seeded = await openStudy(page);
  await openCalculations(page);
  const list = page.getByRole('region', { name: 'Analyses', exact: true });
  await list.getByRole('button', { name: 'New analysis', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'New analysis', exact: true });
  await editor.getByLabel('Analysis name', { exact: true }).fill('Zoomed points');
  await editor.getByLabel(seeded.configuration_name, { exact: true }).check();
  await editor.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Zoomed points', exact: true })).toBeVisible();
  // Matching criteria show their recorded evaluations even at the narrow layout.
  const runs = page.getByRole('region', { name: 'Analysis results', exact: true });
  await expect(runs).toContainText('Met');
  await expect(runs).toContainText('Calculated');
  await expect(runs).not.toContainText('Criterion not bound');
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await page.setViewportSize({ width: 720, height: 500 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await shot(page, 'calculation-zoom-' + theme);
  }
});

/** One trusted dispatcher pass with data-only design and fit stand-ins (no candidate code). */
async function dispatch(page: Page, action: 'observe' | 'dispatch' | 'record' = 'dispatch') {
  const reply = await page.request.post('/fixture/calculation-step', { data: { action } });
  expect(reply.ok()).toBe(true);
  return ((await reply.json()) as { steps: number }).steps;
}

test('@calculations samples expose their design, points, runs and estimates', async ({ page }) => {
  await openStudy(page, '/fixture/calculation-sample-seed');
  await openCalculations(page);
  const list = page.getByRole('region', { name: 'Analyses', exact: true });
  await list.getByRole('button', { name: 'New analysis', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'New analysis', exact: true });
  await dialog.getByLabel('Analysis name', { exact: true }).fill('Drive sweep');
  await dialog.getByRole('button', { name: 'Generate samples', exact: true }).click();
  await expect(dialog.getByLabel('Reference configuration', { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel('Sampling rationale', { exact: true })).toHaveCount(0);
  const ranges = dialog.getByRole('region', { name: 'Sampling inputs', exact: true });
  await expect(ranges.getByRole('combobox')).toHaveCount(2);
  // No saved configuration supplies hidden values: both fixed fields begin empty.
  await expect(ranges.getByLabel(/ value$/).first()).toHaveValue('');
  await expect(ranges.getByLabel(/ value$/).last()).toHaveValue('');
  await ranges.getByRole('combobox').first().selectOption('range');
  await ranges.getByLabel(/ value$/).fill('7');
  await ranges
    .getByLabel(/ minimum$/)
    .first()
    .fill('0');
  await ranges
    .getByLabel(/ maximum$/)
    .first()
    .fill('20');
  await expect(dialog.getByLabel('Sampling method', { exact: true })).toBeVisible();
  await dialog.getByLabel('Sampling method', { exact: true }).selectOption('latin_hypercube');
  await dialog.getByLabel('Validation points', { exact: true }).fill('3');
  await dialog
    .getByRole('region', { name: 'Sampling settings', exact: true })
    .getByLabel('Training points', { exact: true })
    .fill('5');
  await expect(dialog.getByLabel('Total sample points', { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel('Training points', { exact: true })).toHaveValue('5');
  await dialog.getByLabel('Estimate between calculated points', { exact: true }).check();
  await dialog
    .getByRole('checkbox', { name: /^Estimate / })
    .last()
    .check();
  await dialog.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('Enter both error limits');
  await dialog.getByLabel(/ absolute error$/).fill('0.1');
  await dialog.getByLabel(/ relative error \(\%\)$/).fill('1');
  await page.setViewportSize({ width: 1200, height: 900 });
  await shot(page, 'sampling-inputs-light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await shot(page, 'sampling-inputs-dark');
  await page.emulateMedia({ colorScheme: 'light' });
  await dispatch(page, 'observe');
  await dialog.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(dialog.getByRole('status')).toContainText('Queued');
  expect(await dispatch(page)).toBeGreaterThan(0);
  await expect(dialog).toBeHidden();

  await expect(
    page.getByRole('heading', { name: 'Drive sweep', level: 2, exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Points 1–8 of 8', { exact: true })).toBeVisible();
  await expect(page.getByText('Input ranges and fixed values', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Results pagination' })).toHaveCount(1);
  await expect(page.getByText(/Around Drive sweep/)).toHaveCount(0);
  const members = page.getByRole('region', { name: 'Analysis results', exact: true });
  await expect(members.getByText('Validation', { exact: true })).toHaveCount(2);
  await expect(members.getByText('Training', { exact: true })).toHaveCount(5);
  await expect(members.getByText('Point 1', { exact: true })).toBeVisible();
  await expect(members.getByText('Drive sweep', { exact: true })).toHaveCount(0);
  await expect(members.getByText('Method selection', { exact: true })).toHaveCount(1);
  await expect(members.getByRole('columnheader', { name: /Dimensionless/ }).first()).toBeVisible();

  // Existing calculated points are reused by one launch; no manual fitting action remains.
  const runsPanel = page.getByRole('region', { name: 'Results', exact: true });
  await expect(runsPanel.getByText('Not run', { exact: true })).toHaveCount(8);
  expect(await dispatch(page, 'record')).toBe(8);
  const launched = page.waitForResponse(
    (r) => r.url().endsWith('/execution') && r.request().method() === 'POST',
  );
  await runsPanel.getByRole('button', { name: 'Launch analysis', exact: true }).click();
  expect(
    (await (await launched).json()).data.runs.every((r: { reused: boolean }) => r.reused),
  ).toBe(true);
  expect(await dispatch(page)).toBeGreaterThan(0);
  const runs = page.getByRole('region', { name: 'Analysis results', exact: true });
  await expect(runs.getByRole('row')).toHaveCount(9);
  await expect(runsPanel.getByText('Failed', { exact: true })).toBeVisible();
  const estimates = page.getByRole('region', { name: 'Surrogate', exact: true });
  await expect(estimates.getByRole('button', { name: 'Build surrogate', exact: true })).toHaveCount(
    0,
  );
  await expect(estimates).toContainText('0/1 outputs passed');
  const sampleUse = estimates.getByLabel('Sample use', { exact: true });
  await expect(sampleUse).toContainText('Training points5');
  await expect(sampleUse).toContainText('Method selection1');
  await expect(sampleUse).toContainText('Validation points2');
  await expect(estimates).toContainText('Not usable');
  await expect(estimates).not.toContainText('Validation passed');
  await expect(estimates.getByRole('table')).toHaveCount(1);
  await expect(estimates.getByRole('columnheader', { name: 'Method', exact: true })).toBeVisible();
  await expect(estimates.getByRole('columnheader', { name: 'Points', exact: true })).toBeVisible();
  await expect(estimates).toContainText('% × |output|');
  const validationTable = estimates.getByRole('table');
  await expect(validationTable.getByRole('columnheader')).toHaveText([
    'Output',
    'Method',
    'Points',
    'Max. error',
    'RMSE',
    'Allowed error',
    'Result',
  ]);
  const tableAlignment = await validationTable.evaluate((table) => {
    const heads = [...table.querySelectorAll('thead th')];
    const cells = [...table.querySelectorAll('tbody tr:first-child td')];
    return cells.every(
      (cell, index) =>
        getComputedStyle(cell).textAlign === getComputedStyle(heads[index]).textAlign &&
        getComputedStyle(cell).verticalAlign === 'middle',
    );
  });
  expect(tableAlignment).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await shot(page, 'calculation-sampled-light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await shot(page, 'calculation-sampled-dark');
  await page.emulateMedia({ colorScheme: 'light' });

  await page.getByRole('button', { name: 'Columns', exact: true }).click();
  const columnsDialog = page.getByRole('dialog', { name: 'Table columns' });
  const firstCheckbox = columnsDialog.getByRole('checkbox').first();
  const alignment = await firstCheckbox.evaluate((input) => {
    const parent = input.closest('label')!;
    const box = input.getBoundingClientRect(),
      label = parent.getBoundingClientRect();
    return {
      display: getComputedStyle(parent).display,
      aligned: Math.abs(box.y + box.height / 2 - label.y - label.height / 2) < 2,
    };
  });
  expect(alignment).toEqual({ display: 'flex', aligned: true });
  await columnsDialog.getByRole('button', { name: 'Done', exact: true }).click();
  const help = page.getByRole('button', { name: 'Help: Surrogate validation', exact: true });
  await help.click();
  const helpDialog = page.getByRole('dialog', { name: 'Surrogate validation', exact: true });
  await expect(helpDialog).toContainText('independent validation');
  await helpDialog.press('Escape');
  await expect(helpDialog).toBeHidden();
  await expect(help).toBeFocused();

  // One settings entry opens the saved design and retains both revision paths.
  await expect(page.getByRole('button', { name: 'Analysis settings', exact: true })).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Revise analysis', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Sample points', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Analysis settings', exact: true }).click();
  const more = page.getByRole('dialog', { name: 'Analysis settings', exact: true });
  await expect(more.getByRole('spinbutton')).toHaveCount(0);
  await expect(more.getByRole('region', { name: 'Saved input settings' })).toContainText('0–20');
  await expect(more.getByRole('region', { name: 'Saved input settings' })).toContainText(
    '7 Dimensionless',
  );
  await expect(more.getByRole('region', { name: 'Saved sampling settings' })).toContainText(
    'Validation pool',
  );
  for (const width of [720, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const fits = await more
      .getByRole('region', { name: 'Saved sampling settings' })
      .evaluate((node) => {
        const box = node.getBoundingClientRect();
        return [...node.querySelectorAll('dt, dd')].every((field) => {
          const bounds = field.getBoundingClientRect();
          return bounds.width > 0 && bounds.left >= box.left && bounds.right <= box.right + 1;
        });
      });
    expect(fits).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });

  await expect(more.getByRole('button', { name: 'Save analysis', exact: true })).toHaveCount(0);
  await expect(
    more.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toBeVisible();
  await expect(
    more.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toBeDisabled();
  await expect(
    more.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toHaveAttribute('aria-pressed', 'false');
  await expect(more.getByRole('button', { name: 'Generate samples', exact: true })).toBeVisible();
  await expect(more.getByRole('button', { name: 'Generate samples', exact: true })).toBeDisabled();
  await expect(more.getByRole('button', { name: 'Generate samples', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await more.getByRole('button', { name: 'Create new version', exact: true }).click();
  await expect(more.getByRole('button', { name: 'Generate samples', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await more.getByRole('button', { name: 'Select configurations', exact: true }).click();
  await expect(
    more.getByRole('group', { name: 'Saved configurations', exact: true }),
  ).toBeVisible();
  await more.getByRole('button', { name: 'Generate samples', exact: true }).click();
  await expect(more.getByLabel('Sampling method', { exact: true })).toBeVisible();
  await expect(more.getByLabel('Seed', { exact: true })).toHaveValue('17');
  await expect(more.getByLabel(/ minimum$/)).toHaveValue('0');
  await expect(more.getByLabel(/ maximum$/)).toHaveValue('20');
  await expect(more.getByLabel(/ value$/)).toHaveValue('7');
  await more.getByLabel('Training points', { exact: true }).fill('9');
  await dispatch(page, 'observe');
  await more.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(more.getByRole('status')).toContainText('Queued');
  expect(await dispatch(page)).toBeGreaterThan(0);
  await expect(more).toBeHidden();
  await expect(page.getByText('Points 1–10 of 12', { exact: true }).first()).toBeVisible();
  await expect(page.getByLabel('Analysis version', { exact: true }).locator('option')).toHaveCount(
    2,
  );
  // The kept points keep their runs; the new points have none yet.
  await expect(runs.getByRole('row')).toHaveCount(11);
  await expect(runs.getByText('Not run', { exact: true })).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Load more runs' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(runs.getByRole('row')).toHaveCount(3);
  await expect(runs.getByText('Not run', { exact: true })).toHaveCount(2);
  await expect(page.getByText('Points 11–12 of 12').first()).toBeVisible();
  await page.getByRole('button', { name: 'Previous', exact: true }).first().click();
  await expect(runs.getByRole('row')).toHaveCount(11);
});

test('@calculations one creation dialog preserves selections between existing configurations and sampling', async ({
  page,
}) => {
  const seeded = await openStudy(page);
  await openCalculations(page);
  const list = page.getByRole('region', { name: 'Analyses', exact: true });
  await expect(list.getByRole('button', { name: 'New analysis', exact: true })).toHaveCount(1);
  await expect(list.getByRole('button', { name: 'New sampled analysis', exact: true })).toHaveCount(
    0,
  );
  await list.getByRole('button', { name: 'New analysis', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'New analysis', exact: true });
  const footer = dialog.locator(':scope > .dialog-footer');
  await expect(footer.getByRole('button')).toHaveText(['Cancel', 'Save analysis']);
  await expect(footer.getByRole('button', { name: 'Save analysis', exact: true })).toHaveClass(
    /hf-btn--primary/,
  );
  await expect(footer.getByRole('button', { name: 'Save analysis', exact: true })).toHaveCount(1);
  await expect(footer.getByRole('button', { name: 'Cancel', exact: true })).toBeVisible();
  // The footer retains native form submission even though it sits outside the form.
  expect(
    await footer
      .getByRole('button', { name: 'Save analysis', exact: true })
      .evaluate((button: HTMLButtonElement) => button.form?.tagName),
  ).toBe('FORM');
  await dialog.getByLabel('Analysis name', { exact: true }).fill('Operating points');
  const description = dialog.getByLabel('Analysis description', { exact: true });
  await expect(description).toBeVisible();
  await expect(description.locator('..')).toContainText('Description (optional)');
  await expect(description).toHaveAttribute(
    'placeholder',
    'Sampling design, accuracy targets and numerical checks.',
  );
  await description.fill('Compare the selected operating points.');
  await expect(
    dialog.getByRole('button', { name: 'Select configurations', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(dialog.getByRole('button', { name: 'Save analysis', exact: true })).toBeDisabled();
  await dialog.getByLabel(seeded.configuration_name, { exact: true }).check();
  await expect(dialog.getByRole('button', { name: 'Save analysis', exact: true })).toBeEnabled();
  await dialog.getByLabel('Cruise point B', { exact: true }).check();
  await dialog.getByRole('button', { name: 'Generate samples', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Save analysis', exact: true })).toHaveCount(1);
  await expect(footer.getByRole('button', { name: 'Save analysis', exact: true })).toBeVisible();
  await expect(footer.getByRole('button')).toHaveText(['Cancel', 'Save analysis']);
  await expect(dialog.getByRole('region', { name: 'Sampling inputs', exact: true })).toBeVisible();
  await expect(dialog.getByLabel('Reference configuration', { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel('Total sample points', { exact: true })).toHaveCount(0);
  const settings = dialog.getByRole('region', { name: 'Sampling settings', exact: true });
  await expect(settings.getByLabel('Training points', { exact: true })).toHaveValue('17');
  await expect(settings.getByLabel('Validation points', { exact: true })).toHaveValue('8');
  await expect(description).toBeVisible();
  await expect(description).toHaveValue('Compare the selected operating points.');
  await dialog.getByRole('button', { name: 'Select configurations', exact: true }).click();
  await expect(dialog.getByLabel('Analysis name', { exact: true })).toHaveValue('Operating points');
  await expect(dialog.getByLabel(seeded.configuration_name, { exact: true })).toBeChecked();
  await expect(dialog.getByLabel('Cruise point B', { exact: true })).toBeChecked();
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate((value) => {
      document.documentElement.dataset.theme = value;
    }, theme);
    await page.setViewportSize({ width: 390, height: 600 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      ),
    ).toBeLessThanOrEqual(0);
    const saveBox = await footer
      .getByRole('button', { name: 'Save analysis', exact: true })
      .boundingBox();
    const cancelBox = await footer
      .getByRole('button', { name: 'Cancel', exact: true })
      .boundingBox();
    expect(saveBox).not.toBeNull();
    expect(cancelBox).not.toBeNull();
    expect(Math.abs(saveBox!.y - cancelBox!.y)).toBeLessThanOrEqual(1);
    expect(cancelBox!.x + cancelBox!.width).toBeLessThan(saveBox!.x);
    const edge = await dialog.evaluate((element) => {
      const body = element.querySelector('.dialog-body')!;
      const field = body.querySelector('label')!;
      return {
        gap: field.getBoundingClientRect().top - body.getBoundingClientRect().top,
        padding: parseFloat(getComputedStyle(body).paddingTop),
      };
    });
    expect(edge.gap).toBeCloseTo(edge.padding, 0);
    await shot(page, 'new-analysis-' + theme);
  }
  await dialog.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText('Configurations 1–2 of 2', { exact: true })).toBeVisible();
});

test('@calculations simplified dialogs preserve automatic and saved criterion bindings', async ({
  page,
}) => {
  const seeded = await openStudy(page);
  // Reload the public reader after fixture seeding, then author a matching criterion through UI.
  await page.reload();
  await page.getByLabel('Username', { exact: true }).fill('owner');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const brief = page.getByRole('region', { name: 'Study brief', exact: true });
  await brief
    .getByRole('button', { name: /^(Edit brief|Create new version|Continue draft)$/ })
    .click();
  await brief.getByLabel('Criterion 1 name', { exact: true }).fill('u');
  await brief.getByLabel('Criterion 2 name', { exact: true }).fill('Secondary response');
  await brief.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(brief.getByLabel('Study brief version', { exact: true })).toHaveValue('draft');
  await brief.getByRole('button', { name: 'Save brief version', exact: true }).click();
  await expect(brief.getByLabel('Study brief version', { exact: true })).not.toHaveValue('draft');
  await openCalculations(page);
  await page.getByRole('button', { name: 'New analysis', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'New analysis', exact: true });
  await dialog.getByLabel('Analysis name', { exact: true }).fill('Matched criteria');
  await dialog.getByLabel(seeded.configuration_name, { exact: true }).check();
  await expect(dialog.getByText('Evaluate study criteria', { exact: true })).toHaveCount(0);
  await expect(dialog.getByRole('combobox')).toHaveCount(0);
  expect(await dialog.locator('details').count()).toBe(0);
  const order = await dialog.evaluate((element) =>
    [...element.querySelectorAll('input, textarea, button')].map((control) =>
      control.getAttribute('aria-label'),
    ),
  );
  expect(order.indexOf('Analysis description')).toBeGreaterThan(order.indexOf('Analysis name'));
  expect(order.indexOf('Analysis description')).toBeLessThan(
    order.indexOf('Select configurations'),
  );
  await dialog.getByRole('button', { name: 'Generate samples', exact: true }).click();
  await expect(dialog.getByLabel('Sampling method', { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Select configurations', exact: true }).click();
  await expect(dialog.getByRole('combobox')).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(dialog).toBeHidden();
  const bindings = page.getByRole('region', { name: 'Analysis results', exact: true });
  await expect(bindings.getByRole('columnheader', { name: /linear · u/ })).toBeVisible();
  await expect(bindings.getByRole('row')).toHaveCount(2);
  await expect(bindings.getByRole('columnheader', { name: /Secondary response/ })).toBeVisible();
  await expect(bindings).toContainText('Output not assigned');
  await page.getByRole('button', { name: 'Analysis settings', exact: true }).click();
  const revised = page.getByRole('dialog', { name: 'Analysis settings', exact: true });
  await revised.getByRole('button', { name: 'Create new version', exact: true }).click();
  await expect(revised.getByRole('combobox')).toHaveCount(0);
  await revised.getByRole('button', { name: 'Save version', exact: true }).click();
  await expect(revised).toBeHidden();
  await expect(bindings.getByRole('columnheader', { name: /linear · u/ })).toBeVisible();
  await expect(bindings.getByRole('columnheader', { name: /Secondary response/ })).toBeVisible();
  await expect(bindings).toContainText('Output not assigned');
});

test('@calculations recoverable interruption offers one resume action and preserves result links', async ({
  page,
}) => {
  const seeded = await openStudy(page);
  await openCalculations(page);
  let resumed = false;
  const resumeCommands: string[] = [];
  await page.route('**/analysis-versions/*/execution**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const version = path.split('/analysis-versions/')[1].split('/')[0];
    if (path.endsWith('/recovery')) {
      return route.fulfill({
        json: { data: { schema_version: '1', can_resume: true, reason: null } },
      });
    }
    if (path.endsWith('/resume')) {
      expect(route.request().method()).toBe('POST');
      resumeCommands.push(route.request().postDataJSON().command_id);
      resumed = true;
    }
    return route.fulfill({
      json: {
        data: {
          schema_version: '2',
          calculation_version_id: version,
          state: resumed ? 'complete' : 'failed',
          admission_state: resumed ? 'ready' : 'revoked',
          reason: resumed ? null : 'Permission to execute this analysis was lost.',
          completed_count: 1,
          total_count: 1,
          estimate_id: null,
          runs: [
            {
              configuration_revision_id: seeded.configuration,
              run_id: seeded.run,
              completed: true,
              reused: true,
            },
          ],
        },
      },
    });
  });
  await page.getByRole('button', { name: 'New analysis', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'New analysis', exact: true });
  await editor.getByLabel('Analysis name', { exact: true }).fill('Recoverable investigation');
  await editor.getByLabel(seeded.configuration_name, { exact: true }).check();
  await editor.getByRole('button', { name: 'Save analysis', exact: true }).click();
  await expect(editor).toBeHidden();
  await expect(page.getByText('Paused', { exact: true })).toBeVisible();
  await expect(page.getByText('Permission to execute this analysis was lost.')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Launch analysis', exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 720, height: 900 });
  await page.getByRole('button', { name: 'Resume analysis', exact: true }).click();
  await expect(page.getByText('1/1 calculated', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Resume analysis', exact: true })).toHaveCount(0);
  expect(resumeCommands).toHaveLength(1);
  expect(resumeCommands[0]).toMatch(/^[a-f0-9-]{36}$/);
  await expect(page.getByRole('button', { name: /^Open run ·/ }).first()).toBeVisible();
});
