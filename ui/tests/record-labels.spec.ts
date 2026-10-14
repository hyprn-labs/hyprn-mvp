import { test, expect } from 'playwright/test';
import { startFixture, stopFixture, guardOrigin, harness, login, sid, runFixture } from './foundry-fixtures';

test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture); test.beforeEach(async ({page}) => { await guardOrigin(page); await page.emulateMedia({reducedMotion:'reduce'}); }); test.afterAll(stopFixture);

test('overview distinguishes 42 families and 122 revisions with retained run names', async ({page}) => {
  const state = await harness(page);
  runFixture(state);
  const base = {
    configuration: state.detail.history.configuration,
    model_snapshot: state.detail.history.model_snapshot,
  };
  state.configurations = Array.from({ length: 122 }, (_, i) => ({
    ...structuredClone(base),
    configuration: {
      ...structuredClone(base.configuration),
      configuration_id: `family-${i % 42}`,
      configuration_revision_id: `${String(i).padStart(8, '0')}-0000-4000-8000-000000000001`,
      name: 'Same name',
    },
  }));
  state.runs[0].configuration_name = 'Original design';
  state.studies[0].description =
    'Compare heat transfer methods.\n\nRetain the assumptions and limits.';
  await login(page, `#v=1&study=${sid}&view=overview`);
  await expect(
    page.getByText('42 configurations · 122 saved versions · Showing 5 recent versions', {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open run run-fixture', exact: true })).toHaveText(
    'Original design · run-fixt',
  );
  const about = page.getByRole('region', { name: 'About this study', exact: true });
  await expect(about).toContainText('No study question yet');
  await expect(about).not.toContainText(state.studies[0].description, { useInnerText: true });
  await expect(about.getByRole('heading')).toHaveCount(1);
  const action = about.getByRole('button', { name: 'View modeling approach', exact: true });
  await expect(action).toBeVisible();
  const card = await about.boundingBox(),
    recent = await page.getByRole('region', { name: 'Recent runs', exact: true }).boundingBox(),
    button = await action.boundingBox();
  expect(Math.abs(card!.height - recent!.height)).toBeLessThan(1);
  expect(Math.abs(card!.width - recent!.width)).toBeLessThan(1);
  expect(card!.x + card!.width - button!.x - button!.width).toBeGreaterThan(16);
  expect(card!.x + card!.width - button!.x - button!.width).toBeLessThan(30);
  expect(card!.y + card!.height - button!.y - button!.height).toBeLessThan(30);

  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.screenshot({
      animations: 'disabled',
      path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/names-overview-${colorScheme}.png`,
    });
  }
  await page.getByRole('button', { name: 'View all configurations', exact: true }).click();
  await expect(
    page.getByText('42 configurations · 122 saved versions · All saved versions', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open configuration', exact: true })).toHaveCount(
    122,
  );
  await expect(page.getByText('Version 00000121', { exact: false })).toBeVisible();
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.screenshot({
      animations: 'disabled',
      path: `${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/names-configurations-${colorScheme}.png`,
    });
  }
  expect(state.writes).toEqual([]);
  expect(state.unknown).toEqual([]);
});

test('run history searches retained names and preserves exact identifiers', async ({page}) => {
  const state=await harness(page);runFixture(state);state.runs[0].configuration_name='Original design';
  state.runs.push({...state.runs[0],run_id:'older-run',configuration_revision_id:'older-revision',configuration_name:null});
  await login(page,`#v=1&study=${sid}&view=runs`);
  await expect(page.getByRole('button',{name:'Inspect run run-fixture',exact:true})).toHaveText('Original design · run-fixt');
  await expect(page.getByRole('button',{name:'Inspect run older-run',exact:true})).toHaveText('Run · older-ru');
  await page.getByLabel('Filter loaded runs',{exact:true}).fill('Original design');
  await expect(page.getByRole('button',{name:'Inspect run older-run',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Inspect run run-fixture',exact:true})).toBeVisible();
  await page.getByLabel('Filter loaded runs',{exact:true}).fill('older-revision');
  await expect(page.getByRole('button',{name:'Inspect run older-run',exact:true})).toBeVisible();
  await page.getByLabel('Filter loaded runs',{exact:true}).fill('');
  for(const colorScheme of ['light','dark'] as const){await page.emulateMedia({colorScheme});await page.screenshot({animations:'disabled',path:`${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/names-runs-${colorScheme}.png`});}
  expect(state.writes).toEqual([]);expect(state.unknown).toEqual([]);
});

test('older server run labels remain usable without inventing configuration names',async({page})=>{
  const state=await harness(page);runFixture(state);
  await login(page,`#v=1&study=${sid}&view=overview`);
  await expect(page.getByRole('button',{name:'Open run run-fixture',exact:true})).toHaveText('Run · run-fixt');
  await expect(page.getByText('0 configurations · 0 saved versions · Showing 0 recent versions',{exact:true})).toBeVisible();
  expect(state.writes).toEqual([]);
});
