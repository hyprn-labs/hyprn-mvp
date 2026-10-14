import { test, expect, type Page } from 'playwright/test';
import { join } from 'node:path';
import { guardOrigin, login, mid, startFixture, stopFixture, version } from './foundry-fixtures';
import {
  agentHarness,
  agentNames,
  agentStudy,
  archivedStudy,
  expectChip,
  expectWhole,
  genuineZoom,
  humanStudy,
  recorded,
} from './agent-fixtures';

// Attribution chips on the in-browser agent double: "{agent} for {user}" on every record an
// agent wrote, nothing on a person's record. No test writes, and no request leaves the double.

test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
let origin = '';
test.beforeAll(async () => {
  origin = await startFixture();
});
test.beforeEach(async ({ page }) => {
  await guardOrigin(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
});
test.afterAll(stopFixture);

const names = agentNames();
const studyLink = (study: string, rest = '&view=overview') => `#v=1&study=${study}${rest}`;
const studyRow = (page: Page, name: string) =>
  page.locator('.study-row').filter({ has: page.getByRole('heading', { name }) });
const heading = (page: Page) => page.locator('.study-heading');
const modelHeading = (page: Page) => page.locator('.model-heading');
const about = (page: Page) => page.getByRole('region', { name: 'About this study', exact: true });

test('Home marks agent-created studies, active and archived, and no person-created study', async ({
  page,
}) => {
  const state = await agentHarness(page);
  await login(page);
  await expectChip(studyRow(page, 'Heat exchanger sizing'), names.codexForAda);
  await expect(studyRow(page, 'Pump selection')).toBeVisible();
  await expect(studyRow(page, 'Pump selection').locator('.hf-attr')).toHaveCount(0);
  // A person's study keeps no chip on Home even when agents wrote records inside it.
  await expect(studyRow(page, recorded.name)).toBeVisible();
  await expect(studyRow(page, recorded.name).locator('.hf-attr')).toHaveCount(0);
  await page.getByRole('tab', { name: /^Archived/ }).click();
  await expectChip(studyRow(page, 'Retired layout study'), names.claudeForBen);
  // Two created studies across two pages: the read follows its cursor, once per Home visit.
  expect(state.attribution.created).toBe(2);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('a study heading names the agent that created it; a person-created study has none', async ({
  page,
}) => {
  const state = await agentHarness(page);
  await login(page, studyLink(agentStudy));
  await expect(heading(page).getByRole('heading', { name: 'Heat exchanger sizing' })).toBeVisible();
  await expectChip(heading(page), names.codexForAda);
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'Open study Pump selection', exact: true }).click();
  await expect(heading(page).getByRole('heading', { name: 'Pump selection' })).toBeVisible();
  await expect(about(page)).toBeVisible();
  await expect(heading(page).locator('.hf-attr')).toHaveCount(0);
  expect(state.attribution.reads).toEqual([agentStudy, humanStudy]);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('Overview marks a description an agent wrote, not one a person wrote since', async ({
  page,
}) => {
  const state = await agentHarness(page);
  await login(page, studyLink(agentStudy));
  await expect(about(page).locator('.context-copy')).toContainText('Size the exchanger');
  const line = about(page).locator('.context-line');
  await expectChip(line, names.codexForAda);
  await expect(about(page).getByRole('button', { name: 'View modeling approach' })).toBeVisible();
  // A signed-in hash change opens the linked study in place.
  await page.goto(origin + '/ui/' + studyLink(humanStudy));
  await expect(about(page).locator('.context-copy')).toContainText('Choose a pump');
  // The study's attribution names an earlier agent revision; the current revision is a person's.
  await expect(about(page).locator('.hf-attr')).toHaveCount(0);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('model headings and Record details name the agent that wrote the draft or version', async ({
  page,
}) => {
  const state = await agentHarness(page);
  await login(page, studyLink(agentStudy, `&model=${mid}&view=model`));
  await expect(modelHeading(page).getByText('Draft · saved', { exact: true })).toBeVisible();
  await expectChip(modelHeading(page).locator('.model-context'), names.claudeForBen);
  await page.getByLabel('Model version', { exact: true }).selectOption(version);
  await expect(
    modelHeading(page).getByText('Read-only model version', { exact: true }),
  ).toBeVisible();
  await expectChip(modelHeading(page).locator('.model-context'), names.codexForAda);
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Record details', exact: true }).click();
  const record = page.getByRole('dialog', { name: 'Model version record', exact: true });
  const details = record.locator('dl');
  await expect(details.locator('dt')).toHaveText(['Model version', 'SHA-256', 'Saved by']);
  await expect(details.locator('dd').nth(2)).toHaveText('Codex (local) for ada');
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  // Switching between versions of the open study never reads its attribution again.
  expect(state.attribution.reads).toEqual([agentStudy]);

  await page.goto(origin + '/ui/' + studyLink(humanStudy, `&model=${mid}&view=model`));
  await expect(modelHeading(page).getByText('Draft · saved', { exact: true })).toBeVisible();
  await expect(modelHeading(page).locator('.hf-attr')).toHaveCount(0);
  await page.getByLabel('Model version', { exact: true }).selectOption(version);
  await expect(
    modelHeading(page).getByText('Read-only model version', { exact: true }),
  ).toBeVisible();
  await expect(modelHeading(page).locator('.hf-attr')).toHaveCount(0);
  await page.getByRole('button', { name: 'Model actions', exact: true }).click();
  await page.getByRole('button', { name: 'Record details', exact: true }).click();
  const human = page.getByRole('dialog', { name: 'Model version record', exact: true });
  await expect(human.locator('dl dt')).toHaveText(['Model version', 'SHA-256']);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('chips keep the hidden prefix and their theme tokens in Day and Control room', async ({
  page,
}) => {
  const state = await agentHarness(page);
  await login(page, studyLink(agentStudy));
  const chip = await expectChip(heading(page), names.codexForAda);
  const seen: string[] = [];
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    const colours = await chip.evaluate((element) => {
      const probe = (token: string) => {
        const sample = document.createElement('span');
        sample.style.setProperty('color', `var(${token})`);
        document.body.append(sample);
        const value = getComputedStyle(sample).color;
        sample.remove();
        return value;
      };
      const mark = element.querySelector('.hf-attr__mark') as HTMLElement;
      const word = element.querySelector('.hf-attr__for') as HTMLElement;
      return {
        background: getComputedStyle(element).backgroundColor,
        text: getComputedStyle(element).color,
        mark: getComputedStyle(mark).backgroundColor,
        word: getComputedStyle(word).color,
        surface: probe('--surface'),
        ink2: probe('--ink-2'),
        ai: probe('--ai'),
        muted: probe('--ink-muted'),
      };
    });
    expect(colours.background, colorScheme).toBe(colours.surface);
    expect(colours.text, colorScheme).toBe(colours.ink2);
    expect(colours.mark, colorScheme).toBe(colours.ai);
    expect(colours.word, colorScheme).toBe(colours.muted);
    seen.push(colours.background);
    await page.screenshot({
      animations: 'disabled',
      path: join(process.env.HYPRN_MVP_UI_EVIDENCE_ROOT!, `attribution-heading-${colorScheme}.png`),
    });
  }
  expect(seen[0]).not.toBe(seen[1]);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('genuine 200 percent zoom keeps every chip whole with the longest names allowed', async () => {
  test.setTimeout(120000);
  const evidence = process.env.HYPRN_MVP_UI_EVIDENCE_ROOT!;
  const long = agentNames({ long: true });
  const zoomed = await genuineZoom(evidence, origin);
  const page = zoomed.page;
  try {
    const state = await agentHarness(page, { long: true });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await login(page);
    await zoomed.zoom(2);
    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });
      await page.getByRole('button', { name: 'Home', exact: true }).click();
      const row = studyRow(page, 'Heat exchanger sizing');
      await expectWhole(page, await expectChip(row, long.codexForAda), long.codexForAda);
      await row.getByRole('button', { name: 'Open study Heat exchanger sizing' }).click();
      await expectWhole(page, await expectChip(heading(page), long.codexForAda), long.codexForAda);
      const line = about(page).locator('.context-line');
      await expectWhole(page, await expectChip(line, long.codexForAda), long.codexForAda);
      await page.screenshot({
        fullPage: true,
        path: join(evidence, `attribution-overview-${colorScheme}-200.png`),
      });
      await page.getByRole('button', { name: 'Models', exact: true }).click();
      await page.getByRole('button', { name: /^Open model / }).click();
      const context = modelHeading(page).locator('.model-context');
      await expect(context.getByText('Draft · saved', { exact: true })).toBeVisible();
      await expectWhole(page, await expectChip(context, long.claudeForBen), long.claudeForBen);
      await page.getByLabel('Model version', { exact: true }).selectOption(version);
      await expect(context.getByText('Read-only model version', { exact: true })).toBeVisible();
      await expectWhole(page, await expectChip(context, long.codexForAda), long.codexForAda);
      await page.screenshot({
        fullPage: true,
        path: join(evidence, `attribution-model-${colorScheme}-200.png`),
      });
    }
    expect(state.writes).toEqual([]);
    expect(state.unknown).toEqual([]);
  } finally {
    await zoomed.context.close();
  }
});

test('an archived agent-created study keeps its chip in its own heading', async ({ page }) => {
  const state = await agentHarness(page);
  await login(page, studyLink(archivedStudy));
  await expectChip(heading(page), names.claudeForBen);
  expect(state.attribution.reads).toEqual([archivedStudy]);
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});
