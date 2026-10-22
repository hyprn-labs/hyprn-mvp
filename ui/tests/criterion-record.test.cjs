/* Isolated rendering of the shared primitive; no application fixture or scientific computation. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve, dirname } = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const modules = new Map();
function sourceModule(name) {
  const file = resolve(__dirname, '../src/design', name);
  if (modules.has(file)) return modules.get(file).exports;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(dirname(file));
  const nativeRequire = mod.require.bind(mod);
  mod.require = id => id === './navigation' ? sourceModule('navigation.tsx') : id === './icons' ? sourceModule('icons.tsx') : id === './select' ? sourceModule('select.tsx') : id === './components' ? sourceModule('components.tsx') : id === './numbers' ? sourceModule('numbers.ts') : id === '../unitLabels' ? sourceModule('../unitLabels.ts') : nativeRequire(id);
  modules.set(file, mod);
  mod._compile(ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText, file);
  return mod.exports;
}
const { CriterionRecord } = sourceModule('primitives.tsx');
const render = props => renderToStaticMarkup(React.createElement(CriterionRecord, { number: 1, target: 'Pump · pressure', comparison: 'at most', threshold: 12.345678, units: 'Pa', ...props }));

test('numbered saved criterion is structured, exact values available, no invented assessment', () => {
  const html = render({});
  assert.match(html, /Criterion 1/);
  assert.match(html, /Pump · pressure/);
  assert.match(html, /at most/);
  assert.match(html, /12\.346/);
  assert.match(html, /12\.345678/);
  assert.doesNotMatch(html, /Full-precision values/);
  assert.doesNotMatch(html, /Not evaluated|Met|Not met|Actual value/);
});
test('zero is explicit, unset threshold unassigned, tiny nonzero remains nonzero', () => {
  assert.match(render({ threshold: 0 }), />0</);
  assert.match(render({ threshold: null }), /unassigned/);
  assert.match(render({ threshold: 0.0000001 }), /1e-7/);
  assert.match(render({ threshold: null, target: null }), /Choose output/);
});
test('equality tolerances, evidence and real outcome retain separate meanings', () => {
  const html = render({ comparison: 'equal to', tolerances: { absolute: 0, relative: null }, evidence: React.createElement('button', null, 'View evidence'), evaluation: { label: 'Not evaluated', tone: 'advisory', reason: 'Required output unavailable', actual: null } });
  assert.match(html, /Absolute tolerance/);
  assert.match(html, /Relative tolerance/);
  assert.match(html, /unassigned/);
  assert.match(html, /View evidence/);
  assert.match(html, /Not evaluated/);
  assert.match(html, /Required output unavailable/);
  assert.match(html, /not computed/);
  assert.match(html, /hf-tag--advisory/);
});
test('record content is escaped without an extra precision action', () => {
  const html = render({ target: '<script>alert(1)</script>', number: 2 });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /Full-precision values/);
});

test('read-only criterion units share typography while preserving declared expressions', () => {
  const props = { units: 'kg/m**3', evaluation: { label: 'Met', tone: 'ok', actual: 12, units: 'kg/m**3' } };
  const html = render(props);
  assert.match(html, /kg\/m³/);
  assert.doesNotMatch(html, /kg\/m\*\*3/);
  assert.equal(props.units, 'kg/m**3');
});

const { suggestCriterionOutput } = sourceModule('../criterionLabels.ts');
test('criterion suggestions require a unique name and exact units, not units alone', () => {
  const criterion = { name: 'Outlet temperature', units: 'K' };
  const output = { key: 'component/out', name: '  outlet   temperature ', units: 'K' };
  assert.equal(suggestCriterionOutput(criterion, [output]), output.key);
  assert.equal(suggestCriterionOutput(criterion, [output, { ...output, key: 'other/out' }]), '');
  assert.equal(suggestCriterionOutput(criterion, [{ ...output, name: 'Inlet temperature' }]), '');
  assert.equal(suggestCriterionOutput(criterion, [{ ...output, units: 'degC' }]), '');
  assert.equal(suggestCriterionOutput(criterion, [{ ...output, units: undefined }]), '');
  assert.equal(suggestCriterionOutput({ ...criterion, units: '' }, [{ ...output, units: '' }]), output.key);
});

const { criterionOutputLabels } = sourceModule('../criterionLabels.ts');
test('output choices show components only to distinguish repeated quantity names', () => {
  const outputs = [
    { key: 'a', name: 'Temperature', label: 'Cold side · Temperature' },
    { key: 'b', name: 'Flow', label: 'Pump · Flow' },
  ];
  assert.deepEqual(criterionOutputLabels(outputs), { a: 'Temperature', b: 'Flow' });
  assert.deepEqual(criterionOutputLabels([...outputs,
    { key: 'c', name: 'temperature', label: 'Hot side · temperature' },
  ]), { a: 'Cold side · Temperature', b: 'Flow', c: 'Hot side · temperature' });
});
