import { chromium, expect, type Locator, type Page } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { AgentAttribution1, Study } from '../src/contract';
import { chromiumExecutable } from './support/browser';
import { guardOrigin, harness, mid, sid, sid2, version } from './foundry-fixtures';

// Agent attribution double for the agent-ui browser group. It is layered over the foundry
// in-browser double, which keeps serving the record reads (model, configurations, runs,
// evidence) and records every write and every unknown request; this layer adds the study
// shell's two attribution reads, the studies they mark and one recorded study served whole for
// the record views. Declared presentation double only: it never contacts an application and
// never claims real API acceptance.

/** A study an agent created (records written by agents for two different people). */
export const agentStudy = sid;
/** A study a person created; one of its descriptions was written through an agent and has
 * since been replaced by a person's, so its current description carries no attribution. */
export const humanStudy = sid2;
/** An archived study an agent created. */
export const archivedStudy = '10000000-0000-4000-8000-000000000003';
export const configurationVersion = '40000000-0000-4000-8000-000000000001';

/** A complete study recorded from the public API, shared with the agent tools' read tests (every
 * body there is validated against the contract). A person created it; agents wrote some of its
 * records. Served whole by this double; its ids are named below. */
const recordedApi = JSON.parse(
  readFileSync(
    new URL('../../application/tests/agent/fixtures/recorded_api.json', import.meta.url),
    'utf8',
  ),
);
export const recordedStudy: string = recordedApi.study_id;
const [recordedModel] = recordedApi.models.map((m: { model_id: string }) => m.model_id);
const ids = <T>(items: T[], key: (item: T) => string) => items.map(key);
export const recorded = {
  name: recordedApi.study.name as string,
  model: recordedModel as string,
  modelVersions: ids(recordedApi.model_revisions[recordedModel], (r: any) => r.model_revision_id),
  draftRevision: recordedApi.model_drafts[recordedModel].draft_revision as string,
  approachDraft: recordedApi.approach.draft.revision as string,
  /** Newest first: version 2, then version 1. */
  approachVersions: ids(recordedApi.approach_versions, (v: any) => v.approach_version_id),
  configurations: ids(
    recordedApi.configurations,
    (c: any) => c.configuration.configuration_revision_id,
  ),
  runs: ids(recordedApi.runs, (r: any) => r.run_id),
  evidence: ids(recordedApi.evidence_heads, (e: any) => e.evidence_version_id),
};

const person = (n: number, name: string | null) => ({
  actor_id: `60000000-0000-4000-8000-00000000000${n}`,
  display_name: name,
});
const agent = (n: number, name: string) => ({
  actor_id: `70000000-0000-4000-8000-00000000000${n}`,
  display_name: name,
});
/** Layout stress uses 200 characters (beyond the API's 128-character limit), with an
 * unbroken run of letters so wrapping cannot rely on spaces. */
const longest = (lead: string) =>
  (lead + ' ' + 'W'.repeat(144) + ' tail').padEnd(200, ' x').slice(0, 200);

export type AgentNames = { agent: string; user: string };
export type AgentOptions = { long?: boolean };

/** The two agents and the two people they acted for, as the API names them. */
export function agentNames({ long = false }: AgentOptions = {}) {
  return {
    codexForAda: {
      agent: long ? longest('Codex (local)') : 'Codex (local)',
      user: long ? longest('ada') : 'ada',
    },
    claudeForBen: {
      agent: long ? longest('Claude Code (local)') : 'Claude Code (local)',
      user: long ? longest('ben') : 'ben',
    },
    /** The agent of a user who has no name any more: the chip still marks the record. */
    codexForUnknown: {
      agent: long ? longest('Codex (local)') : 'Codex (local)',
      user: 'unknown user',
    },
  };
}

const CATEGORY: Record<AgentAttribution1['record_kind'], string> = {
  study: 'study_create',
  study_context: 'study',
  evidence_version: 'evidence',
  model_draft: 'model',
  model_version: 'model',
  approach_draft: 'approach_draft',
  approach_version: 'approach_version',
  configuration_version: 'configuration',
  run: 'run',
};

function entries(options: AgentOptions) {
  const names = agentNames(options);
  const ada = [agent(1, names.codexForAda.agent), person(1, names.codexForAda.user)] as const;
  const ben = [agent(2, names.claudeForBen.agent), person(2, names.claudeForBen.user)] as const;
  const nameless = [agent(1, names.codexForUnknown.agent), person(3, null)] as const;
  let n = 0;
  const entry = (
    study_id: string,
    record_kind: AgentAttribution1['record_kind'],
    record_id: string,
    version_id: string | null,
    [actor, delegator]: typeof ada | typeof nameless,
  ): AgentAttribution1 => ({
    study_id,
    record_kind,
    record_id,
    version_id,
    command_category: CATEGORY[record_kind],
    command_id: `80000000-0000-4000-8000-${String(++n).padStart(12, '0')}`,
    agent: actor,
    delegator,
    recorded_at: `2026-10-14T10:${String(60 - n).padStart(2, '0')}:00.000000Z`,
  });
  return {
    [agentStudy]: [
      entry(agentStudy, 'run', 'run-fixture', null, ben),
      entry(agentStudy, 'configuration_version', 'configuration-family', configurationVersion, ada),
      entry(agentStudy, 'evidence_version', 'e1', 'evidence-v1', ben),
      entry(agentStudy, 'model_version', mid, version, ada),
      entry(agentStudy, 'model_draft', mid, 'draft-r1', ben),
      entry(agentStudy, 'study_context', agentStudy, 'study-a-r2', ada),
      entry(agentStudy, 'study', agentStudy, null, ada),
    ],
    [humanStudy]: [entry(humanStudy, 'study_context', humanStudy, 'study-h-r1', ada)],
    [archivedStudy]: [entry(archivedStudy, 'study', archivedStudy, null, ben)],
    // The recorded study: a person's study in which agents wrote some records. Run 2,
    // configuration version 2, approach version 1, the first evidence head and every model
    // record are a person's. The third evidence head's delegating user has no name.
    [recordedStudy]: [
      entry(recordedStudy, 'run', recorded.runs[2], null, ben),
      entry(recordedStudy, 'run', recorded.runs[0], null, ada),
      entry(recordedStudy, 'configuration_version', 'family-1', recorded.configurations[0], ben),
      entry(recordedStudy, 'approach_version', 'approach', recorded.approachVersions[0], ada),
      entry(recordedStudy, 'approach_draft', 'approach', recorded.approachDraft, ben),
      entry(recordedStudy, 'evidence_version', 'family-2', recorded.evidence[1], ben),
      entry(recordedStudy, 'evidence_version', 'family-3', recorded.evidence[2], nameless),
    ],
  };
}

type Served = { data: unknown; next_cursor?: null } | { status: number; code: string };

/** The recorded study's public reads, routed like the agent tools' recorded API double. */
function serveRecorded(path: string, query: URLSearchParams): Served | null {
  const d = recordedApi;
  const base = `/studies/${recordedStudy}`;
  if (path !== base && !path.startsWith(base + '/')) return null;
  const parts = path.slice(base.length).split('/').filter(Boolean);
  const list = (items: unknown[]) => ({ data: items, next_cursor: null });
  const found = (value: unknown) =>
    value === undefined ? { status: 404, code: 'resource_not_found' } : { data: value };
  const [head, id, tail, more] = parts;
  if (!parts.length) return { data: d.study };
  if (head === 'approach' && !id) return { data: d.approach };
  if (head === 'approach' && id === 'versions' && !tail) {
    return { data: { items: d.approach_versions, next_cursor: null } };
  }
  if (head === 'approach' && id === 'versions' && tail && !more) {
    return found(d.approach_saved[tail]);
  }
  if (head === 'approach' && id === 'versions' && more === 'usage') {
    const caseId = query.get('case_id');
    const items = (d.approach_usage[tail] ?? []).filter(
      (item: any) => !caseId || item.case_id === caseId,
    );
    return { data: { items, next_cursor: null } };
  }
  if (head === 'unit-catalog') return { data: d.unit_catalog };
  if (head === 'execution-readiness') return { data: d.readiness };
  if (head === 'models' && !id) return list(d.models);
  if (head === 'models' && id === recordedModel) {
    if (!tail) return { data: d.model_drafts[id] };
    if (tail === 'revisions' && !more) return list(d.model_revisions[id]);
    if (tail === 'revisions') return found(d.model_revision[more]);
    if (tail === 'assumption-evidence') {
      const table = d.assumption_evidence[id];
      const draft = query.get('draft_revision') === d.model_drafts[id].draft_revision;
      return found(draft ? table.draft : table[query.get('model_revision_id') ?? '']);
    }
  }
  if (head === 'evidence' && !id) {
    const records = d[query.get('view') === 'versions' ? 'evidence_versions' : 'evidence_heads'];
    return list(records);
  }
  if (head === 'evidence') {
    return found(d.evidence_versions.find((e: any) => e.evidence_version_id === id));
  }
  if (head === 'evidence-families' && tail === 'versions') {
    return list(d.evidence_versions.filter((e: any) => e.evidence_id === id));
  }
  if (head === 'configurations' && !id) return list(d.configurations);
  if (head === 'configurations') {
    const key = (c: any) => c.configuration.configuration_revision_id;
    return found(d.configurations.find((c: any) => key(c) === id));
  }
  if (head === 'result-sources') return { data: { items: d.result_sources, next_cursor: null } };
  if (head === 'runs' && !id) return list(d.runs);
  if (head === 'runs' && tail === 'modified-run-seed') {
    // Declared: no modified-run seed is recorded for this study.
    return { status: 409, code: 'source_result_unavailable' };
  }
  if (head === 'runs' && !tail) return found(d.run_details[id]);
  if (head === 'run-status') return list(query.getAll('run_id').map((run) => d.run_status[run]));
  return null;
}

/** The foundry double plus the attribution reads. A study's attribution page holds at most
 * three entries and a page of created studies one, so every multi-entry read follows its
 * cursor. `attribution.reads` lists the study of each attribution read (first pages only) and
 * `attribution.created` counts the pages of created studies served. */
export async function agentHarness(page: Page, options: AgentOptions = {}) {
  const state = await harness(page);
  const studies: Study[] = [
    {
      study_id: agentStudy,
      revision: 'study-a-r2',
      name: 'Heat exchanger sizing',
      description: 'Size the exchanger for the stated duty.',
      boundary: '',
    },
    {
      study_id: humanStudy,
      revision: 'study-h-r2',
      name: 'Pump selection',
      description: 'Choose a pump for the cooling loop.',
      boundary: '',
    },
    {
      study_id: archivedStudy,
      revision: 'study-z-r1',
      name: 'Retired layout study',
      description: '',
      boundary: '',
      archived: true,
    },
    recordedApi.study,
  ];
  state.studies = studies;
  const stored = entries(options);
  const attribution = { reads: [] as string[], created: 0 };
  const pageOf = (items: AgentAttribution1[], cursor: string | null, size: number) => {
    const start = cursor === null ? 0 : Number(cursor);
    const next = start + size < items.length ? String(start + size) : null;
    return { items: items.slice(start, start + size), next_cursor: next };
  };
  await page.route('**/api/1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.slice('/api/1'.length);
    const cursor = url.searchParams.get('cursor');
    const ok = (data: unknown) =>
      route.fulfill({ json: { schema_version: '1', request_id: 'agent-double', data } });
    if (request.method() !== 'GET') return route.fallback();
    if (path === '/studies') {
      const archived = url.searchParams.get('archived') === 'true';
      return ok(studies.filter((study) => !!study.archived === archived));
    }
    if (path === '/agent/attribution/studies') {
      attribution.created++;
      const created = [archivedStudy, agentStudy].flatMap((id) =>
        stored[id].filter((item) => item.record_kind === 'study'),
      );
      return ok(pageOf(created, cursor, 1));
    }
    const match = /^\/studies\/([^/]+)\/agent\/attribution$/.exec(path);
    if (match && match[1] in stored) {
      if (cursor === null) attribution.reads.push(match[1]);
      return ok(pageOf(stored[match[1]], cursor, 3));
    }
    const served = serveRecorded(path, url.searchParams);
    if (served && 'status' in served) {
      const error = { code: served.code, message: 'Unavailable in this double', fields: [] };
      return route.fulfill({
        status: served.status,
        json: { error: { ...error, outcome: 'unchanged' } },
      });
    }
    if (served) {
      return route.fulfill({
        json: { schema_version: '1', request_id: 'agent-double', ...served },
      });
    }
    // The model version's assumption evidence: none, so the version view reads cleanly.
    if (/^\/studies\/[^/]+\/models\/[^/]+\/assumption-evidence$/.test(path)) {
      return ok({
        schema_version: '1',
        model_digest: 'digest-fixture',
        draft_revision: null,
        model_revision_id: version,
        links: [],
        evidence: [],
      });
    }
    return route.fallback();
  });
  return Object.assign(state, { attribution });
}

/** The chip of `names` inside `scope`: exactly one, with the hidden assistant prefix. */
export async function expectChip(scope: Locator, names: AgentNames) {
  const chip = scope.locator('.hf-attr');
  await expect(chip).toHaveCount(1);
  await expect(chip).toHaveText(`Assistant: ${names.agent} for ${names.user}`);
  await expect(chip.locator('.hf-visually-hidden')).toHaveText('Assistant: ');
  await expect(chip.locator('.hf-attr__mark')).toHaveAttribute('aria-hidden', 'true');
  await expect(chip).not.toHaveAttribute('tabindex');
  return chip;
}

/** The chip shows both names whole: nothing clipped inside it, nothing past the viewport and no
 * horizontal page scroll. */
export async function expectWhole(page: Page, chip: Locator, names: AgentNames) {
  await chip.scrollIntoViewIfNeeded();
  const fit = await chip.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const text = element.querySelector('.hf-attr__text') as HTMLElement;
    return {
      clipped:
        element.scrollWidth > element.clientWidth + 1 || text.scrollWidth > text.clientWidth + 1,
      left: box.left,
      right: box.right,
      width: innerWidth,
      scroll: document.documentElement.scrollWidth,
      whiteSpace: getComputedStyle(element).whiteSpace,
    };
  });
  expect(fit.clipped, JSON.stringify(fit)).toBe(false);
  expect(fit.left, JSON.stringify(fit)).toBeGreaterThanOrEqual(0);
  expect(fit.right, JSON.stringify(fit)).toBeLessThanOrEqual(fit.width + 1);
  expect(fit.scroll, JSON.stringify(fit)).toBeLessThanOrEqual(fit.width + 1);
  expect(fit.whiteSpace).toBe('normal');
  await expect(chip).toHaveText(`Assistant: ${names.agent} for ${names.user}`);
  return fit;
}

/** Genuine 200 % browser zoom: Chromium's own tab zoom set through a local extension at the
 * 1440 × 1000 reference window, never viewport emulation. The page is 720 CSS px wide after. */
export async function genuineZoom(evidence: string, origin: string) {
  const extension = join(evidence, 'agent-zoom-extension');
  await mkdir(extension, { recursive: true });
  await writeFile(
    join(extension, 'manifest.json'),
    JSON.stringify({
      manifest_version: 3,
      name: 'HYPRN MVP local fixture zoom',
      version: '1.0',
      permissions: ['tabs'],
      background: { service_worker: 'worker.js' },
    }),
  );
  await writeFile(
    join(extension, 'worker.js'),
    'chrome.runtime.onInstalled.addListener(() => {});',
  );
  const context = await chromium.launchPersistentContext(join(evidence, 'agent-zoom-profile'), {
    executablePath: chromiumExecutable(),
    headless: true,
    viewport: null,
    args: [
      '--disable-extensions-except=' + extension,
      '--load-extension=' + extension,
      '--window-size=1440,1000',
      '--no-first-run',
    ],
  });
  const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker'));
  const page = context.pages()[0] ?? (await context.newPage());
  await guardOrigin(page);
  return {
    context,
    page,
    /** Capture Chromium's surface directly: Playwright's CSS clip is wrong at tab zoom. */
    async screenshot(name: string) {
      const cdp = await context.newCDPSession(page);
      try {
        const result = await cdp.send('Page.captureScreenshot', {
          format: 'png',
          fromSurface: true,
          captureBeyondViewport: false,
        });
        await writeFile(join(evidence, name), Buffer.from(result.data, 'base64'));
      } finally {
        await cdp.detach();
      }
    },
    /** Sets the reference window, then the tab zoom; call after the page shows the UI. */
    async zoom(factor: number) {
      const cdp = await context.newCDPSession(page);
      const window = await cdp.send('Browser.getWindowForTarget');
      for (let attempt = 0; attempt < 3; attempt++) {
        const css = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
        if (css.width === 1440 && css.height === 1000) break;
        const current = await cdp.send('Browser.getWindowBounds', { windowId: window.windowId });
        await cdp.send('Browser.setWindowBounds', {
          windowId: window.windowId,
          bounds: {
            width: current.bounds.width! + 1440 - css.width,
            height: current.bounds.height! + 1000 - css.height,
          },
        });
      }
      await expect
        .poll(() => page.evaluate(() => ({ width: innerWidth, height: innerHeight })))
        .toEqual({ width: 1440, height: 1000 });
      const applied = await worker.evaluate(
        async ([fixture, zoom]) => {
          const chrome = (globalThis as any).chrome;
          const tabs = await chrome.tabs.query({});
          const tab = tabs.find((candidate: any) => candidate.url?.startsWith(fixture + '/ui/'));
          if (!tab?.id) throw new Error('Exact isolated fixture tab absent');
          await chrome.tabs.setZoomSettings(tab.id, { mode: 'automatic', scope: 'per-tab' });
          await chrome.tabs.setZoom(tab.id, zoom);
          return chrome.tabs.getZoom(tab.id);
        },
        [origin, factor] as const,
      );
      expect(applied).toBe(factor);
      await expect.poll(() => page.evaluate(() => innerWidth)).toBe(1440 / factor);
      expect(page.viewportSize()).toBeNull();
    },
  };
}
