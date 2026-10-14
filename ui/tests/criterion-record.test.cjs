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
  mod.require = id => id === './components' ? sourceModule('components.tsx') : id === './numbers' ? sourceModule('numbers.ts') : nativeRequire(id);
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
