/* Declaration checks only. Public saving, dispatch and retained points are exercised in browser. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve, dirname } = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const cache = new Map();
function load(name) {
  const file = resolve(__dirname, '../src', name + '.ts');
  if (cache.has(file)) return cache.get(file).exports;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(dirname(file));
  const native = mod.require.bind(mod);
  mod.require = (id) => (id.startsWith('./') ? load(id.slice(2)) : native(id));
  cache.set(file, mod);
  mod._compile(
    ts.transpileModule(readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText,
    file,
  );
  return mod.exports;
}
const { samplingRows, samplingDeclaration } = load('samplingInputs');
const ref = (id) => ({ instance_id: 'component', port_id: id });
const model = {
  instances: [{ instance_id: 'component', definition_version_id: 'definition', name: 'Balance' }],
  definitions: [
    {
      definition_version_id: 'definition',
      ports: [
        {
          port_id: 'x',
          direction: 'input',
          name: 'Load',
          units: { kind: 'physical', expression: 'kW' },
        },
        {
          port_id: 'z',
          direction: 'input',
          name: 'Flow',
          units: { kind: 'physical', expression: 'kg/s' },
        },
        { port_id: 'linked', direction: 'input', name: 'Linked', units: { kind: 'dimensionless' } },
        {
          port_id: 'y',
          direction: 'output',
          name: 'Rise',
          units: { kind: 'physical', expression: 'K' },
        },
      ],
    },
  ],
  connections: [{ target_ref: ref('linked') }],
};
const provenance = {
  kind: 'source',
  statement: 'Specified operating interval.',
  evidence_version_ids: ['evidence'],
};
const saved = {
  configuration: {
    inputs: [
      { target: ref('x'), value: 12, units: 'kW', provenance },
      { target: ref('z'), value: 0.3, units: 'kg/s', provenance },
    ],
  },
};
const dimension = {
  target: ref('x'),
  lower: 10,
  upper: 15,
  units: 'kW',
  step: null,
  covary_group: null,
};
const design = {
  groups: [{ dimensions: [dimension] }],
  rationale: 'Evidence defines the tested load interval.',
};

test('new sampling exposes only independent inputs without configuration values', () => {
  const rows = samplingRows(model, null);
  assert.deepEqual(Object.keys(rows), ['component/x', 'component/z']);
  assert.equal(rows['component/x'].value, '');
  rows['component/x'] = { mode: 'range', lower: '0', upper: '15', step: '', value: '' };
  assert.throws(() => samplingDeclaration(model, rows, null, null), /explicit finite value/);
  rows['component/z'].value = '0';
  const declaration = samplingDeclaration(model, rows, null, null);
  assert.equal(declaration.inputs[0].value, 0);
  assert.equal(declaration.inputs[1].value, 0);
  assert.equal(declaration.inputs[0].units, 'kW');
  assert.equal(declaration.reuseReference, false);
  assert.match(declaration.rationale, /User-declared exploration range/);
});

test('unchanged ranges reuse exact provenance and the existing point anchor', () => {
  const rows = samplingRows(model, saved, [dimension]);
  const declaration = samplingDeclaration(model, rows, saved, design);
  assert.equal(declaration.rationale, design.rationale);
  assert.deepEqual(declaration.inputs[0].provenance, provenance);
  assert.equal(declaration.inputs[0].value, 12);
  assert.equal(declaration.reuseReference, true);
});

test('changed ranges do not borrow evidence; changed fixed inputs invalidate point reuse', () => {
  const rows = samplingRows(model, saved, [dimension]);
  rows['component/x'].upper = '20';
  let declaration = samplingDeclaration(model, rows, saved, design);
  assert.deepEqual(declaration.inputs[0].provenance.evidence_version_ids, []);
  assert.doesNotMatch(declaration.rationale, /Evidence defines/);
  assert.equal(declaration.reuseReference, true);
  rows['component/z'].value = '0.25';
  declaration = samplingDeclaration(model, rows, saved, design);
  assert.equal(declaration.reuseReference, false);
  assert.deepEqual(declaration.inputs[1].provenance.evidence_version_ids, []);
});

test('missing units, invalid ranges, empty values and unsafe numbers fail before writes', () => {
  for (const patch of [
    { lower: '' },
    { upper: '10' },
    { step: '-1' },
    { upper: 'Infinity' },
    { upper: '9007199254740992' },
  ]) {
    const rows = samplingRows(model, saved, [dimension]);
    Object.assign(rows['component/x'], patch);
    assert.throws(() => samplingDeclaration(model, rows, saved, design));
  }
  const unresolved = structuredClone(model);
  unresolved.definitions[0].ports[0].units = { kind: 'unspecified' };
  assert.throws(
    () => samplingDeclaration(unresolved, samplingRows(model, saved, [dimension]), saved, design),
    /specify units/,
  );
});

test('a fixed-only declaration is not silently turned into a sampling range', () => {
  const rows = samplingRows(model, saved);
  assert.throws(() => samplingDeclaration(model, rows, saved, null), /at least one input/);
});

test('unchanged fixed run-result inputs preserve their exact source when another value changes', () => {
  const source = structuredClone(saved);
  source.configuration.inputs[1].result_binding = {
    source_run_id: 'run',
    source_output: ref('source-output'),
    results_digest: 'digest',
  };
  const rows = samplingRows(model, source, [dimension]);
  const declaration = samplingDeclaration(model, rows, source, design);
  assert.deepEqual(declaration.inputs[1], {
    kind: 'run_result',
    target: ref('z'),
    source_run_id: 'run',
    source_output: ref('source-output'),
    expected_results_digest: 'digest',
    provenance,
  });
});
