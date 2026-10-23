// Render smoke for the HYPRN MVP Foundry design layer (ui/src/design).
// Builds src/design/index.ts with the Vite SSR build API into a fresh scratch directory outside
// the repository, renders every component with react-dom/server and asserts the
// scientific-state rules. Uses installed dependencies only. Run: node ui/design_smoke.mjs
// HYPRN_MVP_UI_EVIDENCE_ROOT, when set, keeps the build there as evidence; it must be an
// absolute directory outside the repository. Otherwise the build goes to a temporary
// directory that is removed when the smoke finishes.
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from 'vite';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const uiDir = dirname(fileURLToPath(import.meta.url));
const repoDir = resolve(uiDir, '..');
const evidenceRoot = process.env.HYPRN_MVP_UI_EVIDENCE_ROOT;
if (evidenceRoot !== undefined) {
  const fromRepo = relative(repoDir, resolve(evidenceRoot));
  const outside = fromRepo === '..' || fromRepo.startsWith('..' + sep) || isAbsolute(fromRepo);
  if (!isAbsolute(evidenceRoot) || !outside) {
    throw new Error(
      'HYPRN_MVP_UI_EVIDENCE_ROOT must be an absolute directory outside the repository',
    );
  }
  mkdirSync(evidenceRoot, { recursive: true });
}
const outDir = mkdtempSync(join(evidenceRoot ?? tmpdir(), 'hyprn-mvp-design-smoke-'));
console.log('Design smoke build: ' + outDir);

await build({
  configFile: false,
  root: uiDir,
  logLevel: 'warn',
  build: {
    ssr: 'src/design/index.ts',
    outDir,
    emptyOutDir: true,
    rollupOptions: { output: { format: 'es', entryFileNames: 'design.mjs' } },
  },
});
// One React instance: the bundle resolves react through this symlink, the smoke through ui/node_modules;
// Node resolves both to the same realpath.
symlinkSync(join(uiDir, 'node_modules'), join(outDir, 'node_modules'));
const F = await import(pathToFileURL(join(outDir, 'design.mjs')).href);

let failures = 0;
function check(name, ok, detail) {
  if (ok) console.log('PASS ' + name);
  else {
    failures += 1;
    console.log('FAIL ' + name + (detail ? ' :: ' + detail : ''));
  }
}
const markups = [];
function render(name, el) {
  const html = renderToStaticMarkup(el);
  markups.push([name, html]);
  return html;
}

const helpCenter = render('Help center', h(F.HelpCenter));
check('Help teaches a navigable workflow without an unavailable placeholder',
  helpCenter.includes('aria-label="Help topics"') &&
  helpCenter.includes('aria-label="Study workflow"') &&
  helpCenter.includes('From a question to a supported answer') &&
  !helpCenter.includes('not implemented yet'));

const tableControls = render('Single table control row', h(F.TableControls,
  { label: 'Results pagination', itemLabel: 'Points', page: 1, pageSize: 10, total: 23,
    onPage() {}, columns: h(F.Button, null, 'Columns') }));
check('Table controls keep columns before one pagination range',
  tableControls.indexOf('Columns') < tableControls.indexOf('Points 11–20 of 23') &&
  (tableControls.match(/<nav/g) ?? []).length === 1);
const emptyTableControls = render('Empty table control row', h(F.TableControls,
  { label: 'Results pagination', itemLabel: 'Points', page: 0, pageSize: 10, total: 0,
    onPage() {} }));
check('Empty table does not invent a first point', emptyTableControls.includes('Points 0–0 of 0'));

const sectionHelp = JSON.parse(readFileSync(join(uiDir, 'src/design/section-help.json'), 'utf8'));
for (const [topic, content] of Object.entries(sectionHelp)) {
  const html = render('SectionHelp ' + topic, h(F.SectionHelp, { topic }));
  check('Section help has an accessible trigger: ' + topic,
    html.includes('aria-label="Help: ' + content.title + '"') && content.paragraphs.length > 0);
}
for (const [units, absolute, relative] of [['Pa', 3, .01], ['W', .5, 0], ['', 0, .02]]) {
  const html = render('Error allowance ' + units, h(F.ErrorAllowance,
    { units, absolute, relative, reference: 'calculated output' }));
  check('Allowance names its dimensional reference: ' + units,
    html.includes('|calculated output|') && html.includes('% ×') && html.includes(units));
}
const unknownAllowance = render('Unknown allowance unit', h(F.ErrorAllowance,
  { absolute: 1, relative: .02, reference: 'calculated output' }));
check('Unknown units do not become dimensionless', unknownAllowance.includes('Allowance unavailable'));
const navigation = render('Inert status with navigation', h(F.RecordNavigation,
  { label: 'Open run', onOpen() {} }, h(F.StatusTag, { tone: 'ok' }, 'Completed')));
check('Status is outside the navigation button',
  navigation.indexOf('Completed') < navigation.indexOf('<button') &&
  navigation.includes('aria-label="Open run"') && navigation.includes('<svg'));

const openLink = render('Named reader link', h(F.OpenLink, { onClick() {} }, 'Open model'));
check('Named reader has one target, underlined label and shared arrow',
  (openLink.match(/<button/g) ?? []).length === 1 &&
  openLink.includes('hf-open-link__label') && openLink.includes('M6 18 18 6M6 6h12v12'));
const returnLink = render('Named return', h(F.ReturnLink,
  { label: 'Return to all models', onClick() {} }));
check('Returns carry the shared back arrow', returnLink.includes('M20 12H4m7-7-7 7 7 7'));
const urlLink = render('Native URL reader', h(F.OpenLink,
  { href: '/ui/THIRD_PARTY_NOTICES.txt' }, 'Third-party software notices'));
check('URL navigation preserves anchor semantics', urlLink.includes('<a ') && urlLink.includes('href="/ui/THIRD_PARTY_NOTICES.txt"') && !urlLink.includes('<button'));
const disabledLink = render('Unavailable reader', h(F.OpenLink,
  { disabled: true, onClick() {} }, 'Open model'));
check('Unavailable reader preserves native disabled semantics', disabledLink.includes('disabled=""'));

for (const [name, state, expected] of [
  ['prerequisite', { status: 'idle', reason: 'Save a model version first.' }, 'Save a model version first.'],
  ['initial', { status: 'loading' }, 'Loading runs'],
  ['partial', { status: 'ready', count: 20, more: true }, '20 runs shown · More available'],
  ['complete', { status: 'ready', count: 23, more: false }, '23 runs'],
  [
    'failure without detail',
    { status: 'ready', count: 20, more: true, operation: 'append', error: '' },
    'Retry loading more runs',
  ],
  [
    'append failure',
    { status: 'ready', count: 20, more: true, operation: 'append', error: 'Offline' },
    'Retry loading more runs',
  ],
]) {
  const html = render(
    'CollectionStatus ' + name,
    h(F.CollectionStatus, {
      entity: { singular: 'run', plural: 'runs' },
      state,
      onMore: () => {},
      onRetry: () => {},
    }),
  );
  check('Collection ' + name + ' has truthful coverage and named action', html.includes(expected));
  if (name === 'prerequisite')
    check('Idle collection does not invent a pending request',
      !html.includes('Loading runs') && !html.includes('0 runs') && !html.includes('No runs')
      && html.includes('aria-busy="false"'));
  if (name === 'initial')
    check(
      'Initial collection never claims zero or emptiness',
      !html.includes('0 runs') && !html.includes('No runs'),
    );
}
const versionChoices = [
  { id: 'later', number: 3 },
  { id: 'earlier', number: 1 },
];
const versionsMarkup = render(
  'Recorded version identity',
  h(F.VersionSelect, {
    label: 'Analysis version',
    value: 'later',
    versions: versionChoices,
    onChange: () => {},
  }),
);
check(
  'Version numbers preserve metadata despite reordered lists',
  versionsMarkup.includes('Version 3') &&
    versionsMarkup.includes('Version 1') &&
    !versionsMarkup.includes('Version later'),
);
check(
  'Model ordinal follows complete ancestry',
  F.lineageVersions([
    { id: 'b', parent: 'a' },
    { id: 'a', parent: null },
  ])[0].number === 2,
);
for (const rows of [
  [{ id: 'b', parent: 'missing' }],
  [
    { id: 'a', parent: 'b' },
    { id: 'b', parent: 'a' },
  ],
  [
    { id: 'a', parent: null },
    { id: 'b', parent: 'a' },
    { id: 'c', parent: 'a' },
  ],
])
  check(
    'Incomplete or ambiguous model ancestry never fabricates ordinals',
    F.lineageVersions(rows).every((row) => row.number === undefined),
  );
const savedMarkup = render('Immutable saved record', h(F.RecordState, { state: 'saved' }));
check(
  'Read-only is neutral with a lock, never scientific success',
  savedMarkup.includes('Read-only') &&
    savedMarkup.includes('hf-tag--inert') &&
    savedMarkup.includes('<svg') &&
    !savedMarkup.includes('hf-tag--ok'),
);

const partialMatches = render(
  'CollectionStatus partial filter',
  h(F.CollectionStatus, {
    entity: { singular: 'run', plural: 'runs' },
    state: { status: 'ready', count: 20, more: true },
    matches: 0,
    onMore: () => {},
  }),
);
check(
  'Partial filter scopes absence to shown rows',
  partialMatches.includes('No matches in the runs shown.'),
);
const exhaustedMatches = render(
  'CollectionStatus complete filter',
  h(F.CollectionStatus, {
    entity: { singular: 'run', plural: 'runs' },
    state: { status: 'ready', count: 23, more: false },
    matches: 0,
  }),
);
check(
  'Complete filter never recommends unavailable paging',
  exhaustedMatches.includes('No runs match these filters.') &&
    !exhaustedMatches.includes('Load more'),
);
const pendingExploration = render(
  'QuantityResult pending',
  h(F.QuantityResult, {
    value: null,
    units: 'm',
    state: 'unavailable',
    pending: true,
  }),
);
check(
  'Pending prediction is a loading state, never an unavailable result',
  pendingExploration.includes('aria-busy="true"') &&
    pendingExploration.includes('Updating') &&
    !pendingExploration.includes('Not computed'),
);
const pendingCurve = render(
  'ResponseCurve pending',
  h(F.ResponseCurve, {
    label: 'Distance',
    axis: 'Time',
    units: 'm',
    points: [],
    selected: 1,
    pending: true,
  }),
);
check(
  'Pending curve does not claim a missing calculation',
  pendingCurve.includes('Updating') && !pendingCurve.includes('Not computed'),
);
const missingExploration = render(
  'QuantityResult unavailable',
  h(F.QuantityResult, {
    value: null,
    units: 'm',
    state: 'unavailable',
  }),
);
render(
  'AnswerExplorationPanel',
  h(F.AnswerExplorationPanel, {
    settings: h(F.Button, {}, 'Sample settings'),
    categories: 'Illustrative category',
    footer: h(F.Button, {}, 'Open model'),
    children: 'Illustrative graph slot',
  }),
);
render('InterpretationPanel', h(F.InterpretationPanel, {}, 'Illustrative saved prose'));
render(
  'QualitativeChoice',
  h(F.QualitativeChoice, {
    label: 'Material',
    value: 'A',
    options: [{ value: 'A' }, { value: 'B', disabled: true }],
    onChange: () => {},
  }),
);
check(
  'Unavailable exploration output never becomes zero',
  missingExploration.includes('Not computed') && !missingExploration.includes('>0'),
);
const explorationCurve = render(
  'ResponseCurve gap',
  h(F.ResponseCurve, {
    label: 'Illustrative response',
    axis: 'x (m)',
    units: 'm',
    selected: 1,
    points: [
      { x: 0, y: 0 },
      { x: 1, y: null },
      { x: 2, y: 2 },
    ],
    calculated: [{ x: 0, y: 0 }],
  }),
);
check(
  'Unavailable curve intervals are not connected',
  !explorationCurve.includes('hf-response-curve__estimate'),
);
check(
  'Calculated curve points are distinct filled markers',
  explorationCurve.includes('hf-response-curve__calculated'),
);
check(
  'Isolated estimates remain visible across unavailable intervals',
  (explorationCurve.match(/class="hf-response-curve__sample"/g) ?? []).length === 1,
);
const repeatedCurve = render(
  'ResponseCurve discrete repeats',
  h(F.ResponseCurve, {
    label: 'Count response',
    axis: 'Count',
    units: '',
    selected: 100,
    points: [],
    calculated: [
      { x: 99, y: 4 },
      { x: 100, y: 4 },
      { x: 100, y: 4 },
      { x: 101, y: 4 },
    ],
  }),
);
check(
  'Repeated API coordinates do not stack duplicate calculated markers',
  (repeatedCurve.match(/class="hf-response-curve__calculated"/g) ?? []).length === 3,
);
const flatCurve = render(
  'ResponseCurve near constant',
  h(F.ResponseCurve, {
    label: 'Response',
    axis: 'x',
    units: '',
    selected: 0,
    points: [
      { x: 0, y: 1000 },
      { x: 1, y: 1000.00001 },
    ],
  }),
);
check(
  'Near-constant response uses distinct scale labels without altering values',
  flatCurve.includes('999.94') && flatCurve.includes('1000.06'),
);
const selectedCurve = render(
  'ResponseCurve selected API value',
  h(F.ResponseCurve, {
    label: 'Illustrative response',
    axis: 'x (m)',
    units: 'm',
    selected: 0.3,
    selectedResult: { value: 0.7, state: 'estimated' },
    points: [
      { x: 0, y: -1 },
      { x: 1, y: 1 },
    ],
  }),
);
check(
  'Selected API output is marked between curve samples and zero is explicit',
  selectedCurve.includes('hf-response-curve__cursor') &&
    selectedCurve.includes('aria-label="Zero"'),
);
const selectedEstimate = render(
  'ResponseCurve selected estimate at a calculated abscissa',
  h(F.ResponseCurve, {
    label: 'Response',
    axis: 'Input (m)',
    units: 'm',
    selected: 1,
    selectedResult: { value: 1.9, state: 'estimated' },
    points: [
      { x: 0, y: 0 },
      { x: 1, y: 1.9 },
    ],
    calculated: [{ x: 1, y: 2 }],
    referenceLines: [{ value: 3, label: 'Limit' }],
  }),
);
check(
  'Selection halo never changes the authoritative selected result basis',
  selectedEstimate.includes('hf-response-curve__selection') &&
    selectedEstimate.includes('hf-response-curve__cursor'),
);
check(
  'A declared reference has its value and units without inventing a criterion outcome',
  selectedEstimate.includes('aria-label="Limit: 3 m"') &&
    !selectedEstimate.includes('Criterion met'),
);
check(
  'Undeclared limits are not drawn and axis captions omit redundant prefixes',
  !selectedCurve.includes('hf-response-curve__reference') &&
    selectedCurve.includes('<figcaption>x (m)</figcaption>'),
);
const singlePoint = render(
  'ResponseCurve single point',
  h(F.ResponseCurve, {
    label: 'Illustrative response',
    axis: 'x (m)',
    units: 'm',
    selected: 1,
    points: [
      { x: 0, y: null },
      { x: 2, y: null },
    ],
    calculated: [{ x: 1, y: 4 }],
  }),
);
check(
  'One available result does not imply a response curve',
  !singlePoint.includes('<svg') && singlePoint.includes('No curve for this input combination.'),
);
const countedProgress = render(
  'Progress explicit sample count',
  h(F.Progress, {
    label: 'Completed sample points',
    count: { completed: 3, total: 8 },
  }),
);
check(
  'Only explicit work counts create determinate progress',
  countedProgress.includes('value="3"') && countedProgress.includes('max="8"'),
);
const declaredSlider = render(
  'QuantitySlider declared integer range',
  h(F.QuantitySlider, {
    label: 'Count',
    units: '',
    value: 7,
    lower: 0,
    upper: 10,
    step: 1,
    onChange() {},
  }),
);
check(
  'Declared integer slider shares its number and native range',
  declaredSlider.includes('type="range"') &&
    declaredSlider.includes('step="1"') &&
    declaredSlider.includes('value="7"'),
);
const missingRange = render(
  'QuantitySlider missing declaration',
  h(F.QuantitySlider, {
    label: 'Length',
    units: 'm',
    value: 7,
    lower: null,
    upper: null,
    step: null,
    onChange() {},
  }),
);
check(
  'Missing range remains an actionable declaration gap',
  missingRange.includes('Declare a range in Sample settings.') && missingRange.includes('disabled'),
);

const discreteSlider = render(
  'QuantitySlider result-backed stops',
  h(F.QuantitySlider, {
    label: 'Length',
    units: 'm',
    value: 7,
    stops: [
      { value: 2, kind: 'calculated' },
      { value: 7, kind: 'estimated' },
      { value: 19, kind: 'calculated' },
    ],
    lower: 2,
    upper: 19,
    onChange() {},
  }),
);
check(
  'Nonuniform prepared values use discrete indices and distinct markers',
  discreteSlider.includes('max="2"') &&
    discreteSlider.includes('step="1"') &&
    discreteSlider.includes('hf-slider-stop--calculated') &&
    discreteSlider.includes('hf-slider-stop--estimated') &&
    discreteSlider.includes('aria-valuetext="7 m"'),
);

const finiteSlider = render(
  'QuantitySlider finite discrete domain',
  h(F.QuantitySlider, {
    label: 'Count',
    units: '',
    value: 2,
    lower: 1,
    upper: 3,
    step: 1,
    onChange() {},
  }),
);
check(
  'A small discrete domain retains exact bounds without invented points',
  finiteSlider.includes('min="1"') &&
    finiteSlider.includes('max="3"') &&
    finiteSlider.includes('step="1"'),
);

const metricGrid = render(
  'MetricGrid',
  h(F.MetricGrid, {
    label: 'Execution summary',
    items: [{ label: 'Duration', value: '0 s', detail: 'Wall time' }],
  }),
);
check(
  'Metric facts preserve zero and never invent status badges',
  metricGrid.includes('<dt>Duration</dt>') &&
    metricGrid.includes('0 s') &&
    !metricGrid.includes('hf-tag'),
);
const ordinaryLegend = render('ExplorationLegend', h(F.ExplorationLegend));
const incompleteLegend = render(
  'ExplorationLegend unavailable',
  h(F.ExplorationLegend, { unavailable: true }),
);
check(
  'No-result legend appears only when needed',
  !ordinaryLegend.includes('no result') && incompleteLegend.includes('no result'),
);

const expected = [
  'BrandLogo',
  'Button',
  'Field',
  'Tabs',
  'Panel',
  'StatusTag',
  'Readout',
  'Ledger',
  'SourceChip',
  'InferenceBlock',
  'RecordBar',
  'ModelNode',
  'QuantityDirection',
  'DataTable',
  'AttributionChip',
];
check(
  'exports all ' + expected.length + ' components',
  expected.every((n) => typeof F[n] === 'function'),
  expected.filter((n) => typeof F[n] !== 'function').join(','),
);

const brand = render('BrandLogo', h(F.BrandLogo));
check('brand has its accessible product name', brand.includes('aria-label="HYPRN"'));
check('brand remains an external self-origin asset', !brand.includes('data:image'));

// Exact audited self-hosted interface font; scientific values retain system monospace.
const tokensText = readFileSync(join(repoDir, 'design-system/tokens.json'), 'utf8');
const tokens = JSON.parse(tokensText);
const css = readFileSync(join(uiDir, 'src/design/tokens.css'), 'utf8');
const families = {
  sans: '"Manrope", -apple-system, "Segoe UI", system-ui, sans-serif',
  condensed: '"Manrope", -apple-system, "Segoe UI", system-ui, sans-serif',
  mono: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
};
for (const [name, stack] of Object.entries(families)) {
  check(
    name + ' uses the approved font stack',
    tokens.type.families[name] === stack && css.includes('--font-' + name + ': ' + stack + ';'),
  );
}
check(
  'only the audited Manrope family is declared',
  tokens.type.fonts.length === 1 && tokens.type.fonts[0].family === 'Manrope',
);
const fontRoot = join(uiDir, 'src/design/assets/fonts');
const fontHashes = {
  'manrope.ttf': '3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6',
  'OFL.txt': '58172e0c0fac2cda8a37b348164bb55e44b0e69051e557e92b1d3f6910141f7b',
};
for (const [file, hash] of Object.entries(fontHashes)) {
  check(
    file + ' retains its exact audited bytes',
    createHash('sha256')
      .update(readFileSync(join(fontRoot, file)))
      .digest('hex') === hash,
  );
}
const foundryCss = readFileSync(join(uiDir, 'src/design/foundry.css'), 'utf8');
check(
  'Manrope loads through a relative self-origin asset URL',
  foundryCss.includes("url('./assets/fonts/manrope.ttf')"),
);
const executableAssets = [css, foundryCss, readFileSync(join(outDir, 'design.mjs'), 'utf8')];
check(
  'design styles and bundle have no remote font dependency',
  executableAssets.every(
    (text) => !/@import|url\(\s*['"]?https?:|fonts\.(?:googleapis|gstatic)\.com/i.test(text),
  ),
);

const actions = [
  'close',
  'back',
  'add',
  'import',
  'export',
  'chevron-left',
  'chevron-right',
  'chevron-up',
  'chevron-down',
  'search',
];
check('exports ActionIcon', typeof F.ActionIcon === 'function');
for (const name of actions) {
  const html = render('ActionIcon ' + name, h(F.ActionIcon, { name }));
  check(
    name + ' is an inert inline SVG',
    html.startsWith('<svg ') &&
      html.includes('viewBox="0 0 24 24"') &&
      html.includes('aria-hidden="true"') &&
      html.includes('focusable="false"') &&
      html.includes('stroke="currentColor"') &&
      html.includes('<path d="') &&
      !/<(?:title|text|image|use)\b|\b(?:href|tabindex)=/.test(html),
    html,
  );
  const button = render(
    'Icon-only Button ' + name,
    h(F.Button, { icon: h(F.ActionIcon, { name }), 'aria-label': name }),
  );
  check(
    name + ' icon-only Button keeps its accessible label',
    button.includes('aria-label="' + name + '"') &&
      button.includes('type="button"') &&
      button.includes('class="hf-icon" aria-hidden="true"'),
    button,
  );
}
{
  const html = render(
    'Labelled action Button',
    h(F.Button, { icon: h(F.ActionIcon, { name: 'add' }) }, 'Add component'),
  );
  check(
    'action icon also supports a visible Button label',
    html.includes('Add component</button>') && html.includes('<svg '),
    html,
  );
}

// Readout: missing is a word, zero is a value.
for (const [label, value] of [
  ['null', null],
  ['empty string', ''],
]) {
  const html = render('Readout ' + label, h(F.Readout, { label: 'u', value, unit: '1' }));
  check(
    'Readout ' + label + ' renders "not computed"',
    html.includes('not computed') && !html.includes('hf-readout__value'),
    html,
  );
}
{
  const html = render(
    'Readout missingText',
    h(F.Readout, { value: null, missingText: 'not produced' }),
  );
  check(
    'Readout uses missingText',
    html.includes('not produced') && !html.includes('not computed'),
    html,
  );
}
{
  const html = render(
    'Readout zero',
    h(F.Readout, { label: 'u', value: 0, unit: '1', source: 'run-02' }),
  );
  check(
    'Readout 0 renders explicit 0 with its full-precision tooltip',
    html.includes('<span class="hf-readout__value" title="Full precision: 0">0<') &&
      !html.includes('not computed'),
    html,
  );
  check(
    'Readout basis line has glyph and words',
    html.includes('hf-glyph') && html.includes('Computed · run-02'),
    html,
  );
}
{
  const html = render(
    'Readout inferred',
    h(F.Readout, { value: 3.18339, basis: 'inferred', source: 'N-1 §2', size: 'sm' }),
  );
  check(
    'Readout inferred basis is labelled Inference',
    html.includes('hf-readout__basis--inferred') && html.includes('Inference · N-1 §2'),
    html,
  );
}

// Field: blank is unassigned (advisory), zero is assigned.
for (const [label, value] of [
  ['null', null],
  ['empty string', ''],
]) {
  const html = render(
    'Field ' + label,
    h(F.Field, { label: 'Linear response.x', value, unit: '1' }),
  );
  check(
    'Field ' + label + ' shows unassigned placeholder',
    html.includes('placeholder="unassigned"'),
    html,
  );
  check(
    'Field ' + label + ' carries advisory unassigned tag',
    html.includes('hf-tag--advisory') &&
      html.includes('unassigned</span>') &&
      !html.includes('hf-tag--ok'),
    html,
  );
}
{
  const html = render(
    'Field readonly blank',
    h(F.Field, { label: 'z', value: null, state: 'readonly', unit: 'kPa' }),
  );
  check(
    'Field readonly blank words "unassigned"',
    html.includes('hf-field__ro hf-field__ro--missing') &&
      html.includes('>unassigned</span>') &&
      html.includes('hf-tag--advisory'),
    html,
  );
}
{
  const html = render(
    'Field zero',
    h(F.Field, { label: 'z', value: 0, unit: '1', units: ['1', '%'] }),
  );
  check(
    'Field 0 is an assigned explicit value',
    html.includes('value="0"') &&
      html.includes('hf-tag--ok') &&
      html.includes('hf-field--assigned') &&
      !html.includes('hf-tag--advisory'),
    html,
  );
  check(
    'Field multiple units render a labelled select',
    html.includes('<select') && html.includes('aria-label="Unit of z"'),
    html,
  );
}
{
  const html = render(
    'Field readonly zero',
    h(F.Field, { label: 'z', value: 0, state: 'readonly', unit: '1' }),
  );
  check(
    'Field readonly 0 shows 0 and saved tag',
    html.includes('<span class="hf-field__ro" id="hf-z">0</span>') && html.includes('saved'),
    html,
  );
}
{
  const html = render(
    'Field invalid',
    h(F.Field, { label: 'x', value: '12 m', state: 'invalid', message: 'Incompatible unit' }),
  );
  check(
    'Field invalid is alarm with alert message',
    html.includes('hf-tag--alarm') &&
      html.includes('aria-invalid="true"') &&
      html.includes('role="alert"'),
    html,
  );
}

// StatusTag: shape mark plus words for every tone.
for (const tone of ['alarm', 'warning', 'advisory', 'ok', 'inert', 'running']) {
  const html = render('StatusTag ' + tone, h(F.StatusTag, { tone }, 'Word ' + tone));
  check(
    'StatusTag ' + tone + ' has mark and words',
    html.includes('hf-mark hf-mark--' + tone) &&
      html.includes('aria-hidden="true"') &&
      html.includes('Word ' + tone),
    html,
  );
}

// Remaining components: structure and roles.
{
  const html = render(
    'Button',
    h(
      F.Button,
      { variant: 'primary', icon: h('svg', { viewBox: '0 0 24 24' }) },
      'Run this configuration',
    ),
  );
  check(
    'Button primary with ReactNode icon',
    html.includes('hf-btn hf-btn--primary') &&
      html.includes('type="button"') &&
      html.includes('hf-icon'),
    html,
  );
}
{
  const html = render(
    'Tabs',
    h(F.Tabs, {
      items: [
        { id: 'graph', label: 'Graph' },
        { id: 'xdsm', label: 'XDSM', count: 2 },
      ],
      value: 'graph',
      variant: 'segmented',
      label: 'View',
    }),
  );
  check(
    'Tabs roles and roving tabindex',
    html.includes('role="tablist"') &&
      html.includes('aria-selected="true" tabindex="0"') &&
      html.includes('aria-selected="false" tabindex="-1"') &&
      html.includes('hf-tab__count'),
    html,
  );
}
{
  const html = render(
    'Panel',
    h(F.Panel, { title: 'Inputs', actions: h(F.Button, { size: 'sm' }, 'Edit') }, 'Body'),
  );
  check(
    'Panel header and body',
    html.includes('<h2 class="hf-panel__title">Inputs</h2>') && html.includes('hf-panel__body'),
    html,
  );
}
{
  const html = render(
    'Ledger',
    h(F.Ledger, {
      facets: [
        { label: 'Execution', value: 'Completed', tone: 'ok' },
        { label: 'Convergence', value: 'Not applicable' },
      ],
    }),
  );
  check(
    'Ledger list with one tag per facet',
    html.includes('role="list"') &&
      (html.match(/role="listitem"/g) || []).length === 2 &&
      html.includes('hf-mark--inert'),
    html,
  );
}
{
  const html = render(
    'SourceChip',
    h(F.SourceChip, { label: 'N-1', locator: 'p. 2 §2', authority: 'secondary' }),
  );
  check(
    'SourceChip default document glyph and authority',
    html.includes('hf-glyph') &&
      html.includes('hf-chip__auth--secondary') &&
      html.includes('type="button"') && html.includes('hf-open-link hf-chip') &&
      html.includes('M6 18 18 6M6 6h12v12'),
    html,
  );
}
{
  const html = render(
    'InferenceBlock',
    h(
      F.InferenceBlock,
      { title: 'Set z to 0', basis: [h(F.SourceChip, { key: 'a', label: 'N-1' })] },
      'Because',
    ),
  );
  check(
    'InferenceBlock labelled proposal, not applied',
    html.includes('aria-label="Proposal: Set z to 0"') &&
      html.includes('not applied') &&
      html.includes('Rests on'),
    html,
  );
}
// AttributionChip: names who acted for whom and nobody else, wraps instead of truncating, and
// tells screen readers the assistant origin that the hidden mark shows.
{
  const foundryCss = readFileSync(join(uiDir, 'src/design/foundry.css'), 'utf8');
  const noWrapClasses = new Set();
  for (const [, selector, body] of foundryCss.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (/white-space\s*:\s*nowrap/.test(body))
      for (const [, cls] of selector.matchAll(/\.([A-Za-z0-9_-]+)/g)) noWrapClasses.add(cls);
  }
  const attrRule = (foundryCss.match(/(?:^|\n)\.hf-attr\s*\{([^{}]*)\}/) || [])[1] || '';
  const hiddenPrefix = '<span class="hf-visually-hidden">Assistant: </span>';
  const visibleText = (markup) => markup.replace(hiddenPrefix, '').replace(/<[^>]+>/g, '');
  const html = render(
    'AttributionChip',
    h(F.AttributionChip, { agent: 'Codex (local)', user: 'Ada Lovelace' }),
  );
  check(
    'AttributionChip has the visually hidden "Assistant: " prefix before the agent name',
    html.includes(hiddenPrefix + 'Codex (local)'),
    html,
  );
  check(
    'AttributionChip reads "{agent} for {user}" with "for" once',
    visibleText(html) === 'Codex (local) for Ada Lovelace' &&
      (html.match(/ for /g) || []).length === 1 &&
      html.includes('<span class="hf-attr__for"> for </span>'),
    html,
  );
  check(
    'AttributionChip iris mark is aria-hidden',
    /<span class="hf-attr__mark" aria-hidden="true"><svg class="hf-glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false">/.test(
      html,
    ),
    html,
  );
  const visibleClasses = [...html.replace(hiddenPrefix, '').matchAll(/class="([^"]*)"/g)].flatMap(
    (m) => m[1].split(/\s+/),
  );
  check(
    'AttributionChip carries no white-space: nowrap class and wraps long names',
    visibleClasses.length > 0 &&
      visibleClasses.every((c) => !noWrapClasses.has(c)) &&
      /white-space:\s*normal/.test(attrRule) &&
      /overflow-wrap:\s*anywhere/.test(attrRule) &&
      !/text-overflow|ellipsis/.test(attrRule),
    visibleClasses.join(' ') + ' :: ' + attrRule,
  );
  check(
    'AttributionChip is not focusable or interactive',
    !/<(?:a|button|input)\b|\btabindex=|\bhref=|\brole=/.test(html),
    html,
  );
  const hostile = render(
    'AttributionChip markup names',
    h(F.AttributionChip, {
      agent: '<b>Agent</b>',
      user: 'Ann <i>for</i> Bob',
      className: 'row-meta',
    }),
  );
  check(
    'AttributionChip renders names as plain text, never markup',
    hostile.includes('&lt;b&gt;Agent&lt;/b&gt;') &&
      hostile.includes('Ann &lt;i&gt;for&lt;/i&gt; Bob') &&
      !/<(?:b|i)>/.test(hostile) &&
      hostile.startsWith('<span class="hf-attr row-meta">'),
    hostile,
  );
  const long = 'N'.repeat(200);
  const longHtml = render(
    'AttributionChip long names',
    h(F.AttributionChip, { agent: long, user: long }),
  );
  check(
    'AttributionChip never truncates a name',
    visibleText(longHtml) === long + ' for ' + long,
    longHtml,
  );
}
{
  const html = render(
    'RecordBar',
    h(F.RecordBar, { title: 'run-02', detail: 'Model rev-01', onReturn: () => {} }),
  );
  check(
    'RecordBar status role and return button',
    html.includes('role="status"') &&
      html.includes('Return to current model') &&
      html.includes('hf-btn--sm'),
    html,
  );
}
{
  const direction = render(
    'QuantityDirection',
    h(F.QuantityDirection, {
      direction: 'input',
      connected: true,
    }),
  );
  check(
    'Connected quantities retain direction',
    direction.includes('Input') && direction.includes('connected'),
    direction,
  );
  const html = render(
    'ModelNode',
    h(F.ModelNode, {
      name: 'Linear response',
      index: 1,
      selected: true,
      status: 'incomplete',
      ports: [
        { name: 'x', dir: 'in', state: 'unassigned' },
        { name: 'u', dir: 'out' },
      ],
    }),
  );
  check(
    'ModelNode ports and unassigned mark',
    html.includes('aria-pressed="true"') &&
      html.includes('Needs value') &&
      html.includes('hf-mark--advisory') &&
      html.includes('implementation missing'),
    html,
  );
}
{
  const html = render(
    'DataTable',
    h(F.DataTable, {
      caption: 'Outputs',
      columns: [
        { key: 'name', label: 'Name' },
        { key: 'v', label: 'Value', numeric: true },
        { key: 'unit', label: 'Unit', unit: true },
      ],
      rows: [
        { name: 'u', v: 0, unit: '1' },
        { name: 'y', v: null, unit: '1' },
        { name: 'w', v: '', unit: '1' },
      ],
      selected: 0,
    }),
  );
  check(
    'DataTable 0 is a value, blanks are "not computed"',
    /<td\b[^>]*class="num"[^>]*>0<\/td>/.test(html) &&
      (html.match(/class="missing">not computed/g) || []).length === 2,
    html,
  );
  check(
    'DataTable caption hidden by class and numeric header aligned by class',
    html.includes('<caption class="hf-visually-hidden">') && html.includes('class="hf-th--num"'),
    html,
  );
}


const formActions = render('Form completion actions', h(F.FormActions,
  {primary:h(F.Button, {onClick() {}}, 'Save draft')},
  h(F.Button, {onClick() {}}, 'Cancel editing')));
check('Form actions put cancellation before a highlighted primary action',
  formActions.indexOf('Cancel editing') < formActions.indexOf('Save draft') &&
  formActions.includes('hf-btn--primary'));

for (const [name, html] of markups) {
  if (/\sstyle=/.test(html)) check(name + ' has no style attribute', false, html);
  if (/https?:/.test(html)) check(name + ' has no external URL', false, html);
}
check(
  'no rendered markup contains a style attribute or external URL',
  markups.every(([, html]) => !/\sstyle=/.test(html) && !/https?:/.test(html)),
);

const optionalField = render(
  'FormField optional',
  h(
    F.FormField,
    { label: 'Description', optional: true },
    h(F.TextArea, { 'aria-label': 'Description' }),
  ),
);
const requiredField = render(
  'FormField required',
  h(F.FormField, { label: 'Name' }, h(F.TextInput, { 'aria-label': 'Name' })),
);
check(
  'Optional narrative fields are visible labelled controls, not disclosures',
  optionalField.includes('hf-form-field__optional') &&
    optionalField.includes('(optional)') &&
    optionalField.includes('<label') &&
    optionalField.includes('<textarea') &&
    !optionalField.includes('<details') &&
    !optionalField.includes('hidden') &&
    !requiredField.includes('(optional)'),
);

console.log(
  failures
    ? 'design smoke: ' + failures + ' failure(s)'
    : 'design smoke: all checks passed (' + markups.length + ' renders)',
);

if (evidenceRoot === undefined) rmSync(outDir, { recursive: true, force: true });
process.exit(failures ? 1 : 0);
