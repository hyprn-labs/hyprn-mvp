import { test, expect, type Page } from 'playwright/test';
import { createServer, type Server } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { createHash } from 'node:crypto';
import type { ModelDraft, Study } from '../src/contract';

// Isolated connected-model regression only. Every API request is a controlled fixture;
// this must never contact the live application or claim real API acceptance.
const build = process.env.HYPRN_MVP_NAV_BUILD;
// The closed isolated browser groups (deployment/checks.py) build into their guarded scope.
// Scoped roots are <scratch root>/hyprn-mvp-test-<uuid>; the scoped environment always names the
// scratch root (deployment/local_paths.py).
const scopeRoot = process.env.HYPRN_MVP_TEST_SCOPE_ROOT ?? '';
const scratchRoot = process.env.HYPRN_MVP_SCRATCH_ROOT ?? '';
const scoped = scratchRoot.startsWith('/') && scopeRoot.startsWith(scratchRoot + sep)
  && /^hyprn-mvp-test-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(scopeRoot.slice(scratchRoot.length + 1))
  && build === scopeRoot + '/artifacts/nav-dist';
if (build && !scoped) throw new Error('HYPRN_MVP_NAV_BUILD must point to the isolated build of the current scoped test folder.');
/** The scoped isolated UI build; unset outside the closed isolated browser groups. */
export const isolatedBuild = build;

let server: Server, origin: string;
export async function startFixture() {
  server = createServer(async (request, response) => {
    response.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'");
    const path = new URL(request.url!, 'http://localhost').pathname;
    const file = resolve(build!, path === '/ui/' ? 'index.html' : path.replace(/^\/ui\//, ''));
    if (!path.startsWith('/ui/') || !file.startsWith(resolve(build!) + sep)) { response.writeHead(404).end(); return; }
    try { const bytes = await readFile(file); response.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html'); response.end(bytes); }
    catch { response.writeHead(404).end(); }
  });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address(); if (!address || typeof address === 'string') throw new Error('Isolated server unavailable');
  origin = `http://127.0.0.1:${address.port}`;
  return origin;
}
export async function guardOrigin(page: Page) {
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort('blockedbyclient'));
}
export async function stopFixture() { if (server?.listening) await new Promise<void>((done, reject) => server.close(error => error ? reject(error) : done())); }

// Pinned public unit catalog (identical to application/tests/test_unit_guidance_api.py CATALOG).
// Model and configuration editors read it; this is a declared browser double.
export const unitCatalog = { schema_version: '1',
  catalog_digest: 'f9278b0e59aa2d410dcd14a2abc1306d3d18adcf9edbb433002f6466489939f3',
  engine: 'OpenMDAO', engine_version: '3.45.1',
  engine_source_sha256: '9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92',
  supported_units: ['m','km','cm','mm','s','min','h','kg','g','N','Pa','kPa','MPa','K','degC','degF','rad','deg','m/s','km/h','J/kg','kJ/kg','MJ/kg','kg/m**3','g/cm**3','m**2','cm**2','mm**2'],
  affine_conversion: false };

export const sid = '10000000-0000-4000-8000-000000000001';
export const sid2 = '10000000-0000-4000-8000-000000000002';
export const mid = '20000000-0000-4000-8000-000000000001';
export const version = '30000000-0000-4000-8000-000000000001';
export function latch() { let release!: () => void; const promise = new Promise<void>(resolve => { release = resolve; }); return { promise, release }; }
export async function harness(page: Page) {
  const state = { configurations: [] as any[], runs: [] as any[], detail: null as any, ready: false, outage: false,
    studies: [{ study_id: sid, revision: 'study-r1', name: 'Thermal study', description: 'A retained description', boundary: 'Retained boundary must survive' }] as Study[],
    model: modelFixture() as ModelDraft,
    stale: false, uncertain: false,
    writes: [] as Array<{ path: string; method: string; body: any }>,
    unknown: [] as string[],
    delayStudy: null as ReturnType<typeof latch> | null,
    uncertainCreate: false,
    expire: false,
    actor: 'owner',
  };
  await page.route('**/api/1/**', async route => {
    if (new URL(route.request().url()).origin !== origin) return route.abort('blockedbyclient');
    const request = route.request(), path = new URL(request.url()).pathname.slice('/api/1'.length), method = request.method();
    const body = method === 'GET' ? undefined : request.postDataJSON();
    const ok = (data: unknown) => route.fulfill({ json: { schema_version: '1', data, next_cursor: null } });
    if (path === '/session') { if (method === 'POST') state.actor = body.username; return ok({ actor_id: state.actor, csrf_token: 'isolated-fixture-token' }); }
    if (state.expire) { state.expire = false; return route.fulfill({ status: 401, json: { error: { code: 'unauthenticated', message: 'Session expired', fields: [], outcome: 'unchanged' } } }); }
    if (method !== 'GET') state.writes.push({ path, method, body });
    if (path === '/capabilities') return ok({engineering: []});
    if (path.endsWith('/model-imports')) return route.fulfill({status:409,json:{error:{code:'stale_revision',message:'Study changed; import preview preserved',fields:[],outcome:'unchanged'}}});
    if (path === '/studies') {
      if (method === 'GET') return ok(state.actor === 'owner' && new URL(request.url()).searchParams.get('archived') !== 'true' ? state.studies : []); // this double has no archived studies
      if (state.uncertainCreate) return route.abort('failed');
      const study = { study_id: sid2, revision: 'new-study-r1', name: body.name, description: '', boundary: '' };
      state.studies.push(study); return ok(study);
    }
    if (path.includes('/commands/')) return ok({ state: 'rejected', result: null });
    const id = path.split('/')[2], study = state.studies.find(s => s.study_id === id);
    if (path === `/studies/${id}` && study) {
      if (method === 'PATCH') Object.assign(study, { name: body.name, description: body.description, boundary: body.boundary, revision: 'study-r2' });
      if (state.delayStudy) await state.delayStudy.promise;
      return ok(study);
    }
    if (path === `/studies/${id}/unit-catalog` && study && method === 'GET') return ok(unitCatalog);
    // The model view reads the latest saved approach to explain components. These legacy
    // presentation studies have no approach; the declared double says so explicitly.
    if (path === `/studies/${id}/approach` && study && method === 'GET') return ok({ draft: null, latest_version: null });
    if (path === `/studies/${id}/models`) {
      if (method === 'GET') return ok(state.model ? [{ model_id: mid }] : []);
      state.model = { schema_version: '1', model_id: mid, study_id: id, name: body.name, root_instance_id: 'root', draft_revision: 'draft-r1', definitions: [], instances: [], ports: [], connections: [], boundary_mappings: [], annotations: [], source_files: [], required_capabilities: [] };
      return ok(state.model);
    }
    if (path === `/studies/${id}/models/${mid}/preview` || path === `/studies/${id}/models/${mid}/edits`) {
      if (state.stale) return route.fulfill({ status: 409, json: { error: { code: 'stale_revision', message: 'Draft changed; proposal preserved', fields: [], outcome: 'unchanged' } } });
      if (path.endsWith('/edits') && state.uncertain) return route.abort('failed');
      const next = structuredClone(state.model);
      for (const edit of body.edits) {
        if (edit.kind === 'rename_instance') next.instances.find(i => i.instance_id === edit.instance_id)!.name = edit.name;
        if (edit.kind === 'rename_model') next.name = edit.name;
        if (edit.kind === 'set_annotation') next.annotations = [{ element_ref: edit.element_ref, text: edit.text }];
        if (edit.kind === 'instantiate') next.instances.push({ ...next.instances[0], instance_id: 'repeated-new', definition_version_id: edit.version_ref.definition_version_id });
      }
      if (path.endsWith('/edits')) { next.draft_revision = 'draft-r2'; state.model = next; }
      return ok(next);
    }
    if (path === `/studies/${id}/models/${mid}`) return state.outage ? route.fulfill({status:503,json:{error:{code:'modeling_unavailable',message:'Modeling unavailable',fields:[],outcome:'unchanged'}}}) : ok(state.model);
    if (path === `/studies/${id}/models/${mid}/revisions`) return ok([{ model_revision_id: version, parent_model_revision_id: null, originating_draft_revision: 'draft-r1', digest: 'digest-fixture' }]);
    if (path === `/studies/${id}/models/${mid}/revisions/${version}`) return ok({ ...state.model, model_revision_id: version, parent_model_revision_id: null, originating_draft_revision: 'draft-r1', digest: 'digest-fixture' });
    if (path.endsWith('/commits')) return ok({ ...state.model, model_revision_id: version, originating_draft_revision: state.model.draft_revision, digest: 'fixture-digest' });
    // Legacy Foundry fixtures have no assumption closure or modified-run seed.
    // Explicit unavailable reads exercise honest recovery, never fabricated evidence.
    if (method === 'GET' && (path.endsWith('/assumption-evidence') || path.endsWith('/modified-run-seed'))) return route.fulfill({status:409,json:{error:{code:'source_result_unavailable',message:'Unavailable in this legacy presentation fixture',fields:[],outcome:'unchanged'}}});
    // Request3 (new configurations since 02-13) previews and saves server-resolved shapes:
    // context_override becomes context_snapshot and literal inputs gain result_binding null.
    // Declared presentation double only; no compatibility or digest is computed here.
    const resolved3 = (candidate: any) => { const { context_override, notes, ...rest } = candidate;
      return { ...rest, inputs: candidate.inputs.map(({ kind: _kind, ...input }: any) => ({ ...input, result_binding: null })),
        context_snapshot: { description: context_override.description, boundary: context_override.boundary, notes },
        evidence_snapshots: [], required_capabilities: [] }; };
    if (path.endsWith('/configurations/preview')) {
      if (body.schema_version !== '3') return ok({ compatible: true, diagnostics: [] });
      return ok({ schema_version: '3', request_digest: 'request-fixture', resolved_candidate: resolved3(body), candidate_digest: 'candidate-fixture', model_digest: 'fixture-digest',
        compatibility: { schema_version: '1', model_revision_id: version, model_digest: 'fixture-digest', candidate_digest: 'candidate-fixture', compatible: true, diagnostics: [], required_capabilities: [], validator_identity: 'foundry-fixture' },
        changes: [], runtime_comparison: null });
    }
    if (path.endsWith('/configurations')) {
      if (method === 'POST') { const configuration = body.configuration.schema_version === '3' ? { ...resolved3(body.configuration), configuration_id: '50000000-0000-4000-8000-000000000001', parent_revision_id: null } : body.configuration;
        const value = { configuration: { ...configuration, configuration_revision_id: '40000000-0000-4000-8000-000000000001', digest: 'config-fixture' }, model_snapshot: { ...state.model, model_revision_id: version, originating_draft_revision: state.model.draft_revision, digest: 'fixture-digest' } }; state.configurations.push(value); return ok(value); }
      return ok(state.configurations);
    }
    if (path.endsWith('/configurations/40000000-0000-4000-8000-000000000001')) return ok(state.configurations[0]);
    if (path.endsWith('/runs')) { if (method === 'POST') { if (state.uncertain) return route.abort('failed'); return ok({run_id:'run-fixture',state:'recorded',command_id:body.command_id}); } return ok(state.runs); }
    if (path.endsWith('/runs/run-fixture')) return ok(state.detail);
    if (path.endsWith('/evidence')) return ok([{ evidence_id:'e1', evidence_version_id:'evidence-v1', study_id:sid, evidence_schema_version:'2', resource_scope:{scope_version:'1',kind:'study',study_id:sid}, kind:'note', content:'For x = 2 and z = 3, u = 2x + z = 7 and y = u² = 49. This checks the arithmetic, not its suitability for a physical system.',source_refs:['Analytical reference'] }]);
    if (path.endsWith('/execution-readiness')) return ok({ readiness_schema_version: '1', capability: 'flat_explicit_scalar', status: state.ready ? 'ready' : 'unavailable', reasons: state.ready ? [] : ['executor_unavailable'], observed_at: new Date().toISOString(), expires_at: new Date(Date.now()+60000).toISOString() });
    state.unknown.push(method + ' ' + path);
    return route.fulfill({ status: 500, json: { error: { message: 'Unexpected isolated request', code: 'internal_error', fields: [], outcome: 'unchanged' } } });
  });
  return state;
}
export async function login(page: Page, hash = '', name = 'owner') {
  await page.goto(origin + '/ui/' + hash);
  await page.getByLabel('Username', { exact: true }).fill(name);
  await page.getByLabel('Password', { exact: true }).fill('isolated-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Profile', exact: true })).toBeVisible();
}
export async function openStudy(page: Page) { await page.getByRole('button', { name: 'Open study Thermal study' }).click(); await expect(page.getByRole('heading', { name: 'About this study' })).toBeVisible(); }


export const source = "outputs['heat'] = inputs['temperature']\r\noutputs['flow'] = inputs['pressure']\r\n";
export function modelFixture(): ModelDraft {
  const bytes = Buffer.from(source), sha256 = createHash('sha256').update(bytes).digest('hex');
  const ports = ['temperature', 'pressure', 'heat', 'flow'].map((name, i) => ({ port_id: name, name, code_symbol: name, direction: i < 2 ? 'input' : 'output', units: '', value_type: 'real_scalar' }));
  return { schema_version: '1', model_id: mid, study_id: sid, name: 'Connected thermal model', root_instance_id: 'root', draft_revision: 'draft-r1',
    definitions: [{ definition_id: 'definition', definition_version_id: 'definition-v1', definition_kind: 'explicit_component', name: 'Thermal component', ports, source_refs: [sha256], annotations: [] }],
    instances: ['a', 'b', 'c'].map(instance_id => ({ instance_id, definition_version_id: 'definition-v1', name: 'Thermal component' })),
    connections: [['ab1', 'a', 'heat', 'b', 'temperature'], ['ab2', 'a', 'flow', 'b', 'pressure'], ['ac', 'a', 'heat', 'c', 'temperature']].map(([connection_id, producer, output, consumer, input]) => ({ connection_id, source_ref: { instance_id: producer, port_id: output }, target_ref: { instance_id: consumer, port_id: input } })),
    boundary_mappings: [], annotations: [], source_files: [{ encoding: 'base64', media_type: 'text/x-python', bytes: bytes.toString('base64'), sha256 }], required_capabilities: [] } as unknown as ModelDraft;
}
export async function openModel(page: Page) { await login(page, `#v=1&study=${sid}&model=${mid}&view=model`); await expect(page.getByRole('heading', { name: 'Connected thermal model', exact: true })).toBeVisible(); }
export const components = (page: Page) => page.getByRole('region', { name: 'Model components', exact: true });
export const details = (page: Page) => page.getByRole('region', { name: 'Selection inspector', exact: true });
export const mutations = (state: Awaited<ReturnType<typeof harness>>) => state.writes.filter(w => w.path.endsWith('/edits'));


export function referenceModel(state: Awaited<ReturnType<typeof harness>>) {
  state.studies[0].name = 'Scalar model study'; state.studies[0].description = 'Understand how a linear response propagates through a nonlinear component. Use explicit inputs and compare the results with an analytical reference.';
  state.model.name = 'Response chain';
  state.model.instances = state.model.instances.slice(0, 2).map((i, n) => ({ ...i, name: n ? 'Squared response' : 'Linear response', definition_version_id: n ? 'square-v1' : 'affine-v1' }));
  const port = (code_symbol: string, direction: 'input' | 'output') => ({ port_id: code_symbol, name: code_symbol, code_symbol, direction, units: '', value_type: 'real_scalar' as const });
  state.model.definitions = ['affine', 'square'].map((id, n) => ({ ...state.model.definitions[0], definition_id: id, definition_version_id: id + '-v1', name: n ? 'Square' : 'Affine', ports: n ? [port('u', 'input'), port('y', 'output')] : [port('x','input'),port('z','input'),port('u','output')] }));
  state.model.connections = [{ connection_id: 'edge', source_ref: { instance_id:'a',port_id:'u' }, target_ref:{ instance_id:'b',port_id:'u' } }];
}

export function runFixture(state: Awaited<ReturnType<typeof harness>>) {
  referenceModel(state);
  const configuration = { schema_version: '1', study_id: sid, model_id: mid, configuration_revision_id: '40000000-0000-4000-8000-000000000001', name: 'Baseline', model_revision_id: version, inputs: [{ target: { instance_id: 'a', port_id: 'x' }, value: 0, units: '', provenance: { kind: 'manual', statement: 'Explicit recorded zero' } }], criteria: [], context_snapshot: { description: 'Retained study context', boundary: 'Original boundary', notes: [] }, evidence_snapshots: [], numerical: { mode: 'deterministic', derivatives: { method: 'none' } }, required_capabilities: [], digest: 'config-fixture' };
  state.runs = [{ run_id: 'run-fixture', configuration_revision_id: configuration.configuration_revision_id, state: 'recorded' }];
  state.detail = { run_id: 'run-fixture', state: 'recorded', process_state: 'finished', exit_status: 0, history: { errors: [], model_snapshot: { ...structuredClone(state.model), model_revision_id: version, digest: 'retained-model' }, configuration, context: configuration.context_snapshot, evidence: [{ evidence_version_id: 'retained-note', content: 'Exact retained note <script>inert</script>', source_refs: ['Exact retained reference'] }], artifacts: [], bundle: null, assessment: null, results: { outputs: [{ target: { instance_id: 'a', port_id: 'u' }, value: 0, units: '', availability: 'available', reason: null }, { target: { instance_id: 'b', port_id: 'y' }, value: null, units: '', availability: 'unavailable', reason: 'producer_failed' }], criteria: [], execution: { state: 'failed', exit_code: 1, message: 'Fixture producer failed' }, convergence: { state: 'not_converged' }, optimization: { termination: 'not_applicable', feasibility: 'not_applicable' }, completeness: { available: 1, expected: 2, failed: 1, unavailable: 1 }, applicability: { state: 'unassessed' } } } };
  return state.detail;
}

