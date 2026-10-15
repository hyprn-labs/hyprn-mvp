/* UI quantity identity only: this regression performs no physical conversion. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve, dirname } = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const file = resolve(__dirname, '../src/explorationInputs.ts');
const mod = new Module(file, module);
mod.filename = file;
mod.paths = Module._nodeModulePaths(dirname(file));
mod._compile(
  ts.transpileModule(readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText,
  file,
);
const { explorationInputVector, preparedInputUnitsMatch, savedInputQuantity, sameInputVector } =
  mod.exports;
const target = { instance_id: 'coolant', port_id: 'heat-load' };
const coolant = (units = 'kW') => ({
  target,
  units: 'W',
  name: 'Coolant heat load',
  binding: { kind: 'free', assignment: { target, value: 12, units } },
});

test('saved coolant value retains kW in the displayed quantity and original-run input', () => {
  assert.deepEqual(savedInputQuantity(coolant()), { target, value: 12, units: 'kW' });
  const vector = explorationInputVector([coolant()]);
  assert.deepEqual(vector, [{ target, value: 12, units: 'kW' }]);
  assert.equal(sameInputVector(vector, [{ target, value: 12, units: 'kW' }]), true);
  assert.equal(sameInputVector(vector, [{ target, value: 12, units: 'W' }]), false);
  assert.equal(sameInputVector(vector, [{ target, value: 12000, units: 'W' }]), false);
});

test('prepared axis selection refuses differing saved units without browser conversion', () => {
  assert.equal(preparedInputUnitsMatch([coolant()]), false);
  assert.equal(explorationInputVector([coolant()], target, 14), undefined);
  assert.equal(preparedInputUnitsMatch([coolant('W')]), true);
  assert.deepEqual(explorationInputVector([coolant('W')], target, 14), [
    { target, value: 14, units: 'W' },
  ]);
});

test('connected inputs stay connected and a blank axis remains unassigned', () => {
  const connected = {
    target: { instance_id: 'sink', port_id: 'heat' },
    units: 'W',
    binding: { kind: 'connected', source: target },
  };
  assert.deepEqual(explorationInputVector([coolant(), connected]), [
    { target, value: 12, units: 'kW' },
  ]);
  assert.equal(explorationInputVector([coolant('W')], target, null), undefined);
});

test('selected vector preserves covary groups and rejects blank or off-step inputs', () => {
  const { selectInput, completeVector } = mod.exports;
  const other = { instance_id: 'other', port_id: 'same-name' };
  const dimensions = [target, other].map((target) => ({
    target,
    lower: 0,
    upper: 20,
    step: 1,
    units: 'kW',
    covary_group: null,
    common_key: null,
  }));
  const baseline = [
    { target, value: 12, units: 'kW' },
    { target: other, value: 12, units: 'kW' },
  ];
  assert.equal(selectInput(baseline, dimensions, target, 13)[1].value, 12);
  dimensions.forEach((d) => (d.covary_group = 'declared'));
  assert.deepEqual(
    selectInput(baseline, dimensions, target, 13).map((p) => p.value),
    [13, 13],
  );
  assert.equal(
    completeVector(selectInput(baseline, dimensions, target, 13.5), dimensions),
    undefined,
  );
  assert.equal(
    completeVector(selectInput(baseline, dimensions, target, null), dimensions),
    undefined,
  );
});

test('independent categories resolve supported tuples and clear specific overrides', () => {
  const { supportedCombination, carryCommon } = mod.exports;
  const combos = ['a', 'b'].flatMap((m) =>
    ['low', 'high'].map((r) => ({ categories: [m, r], model_revision_id: m + r })),
  );
  for (const combo of combos) assert.equal(supportedCombination(combos, combo.categories), combo);
  assert.equal(supportedCombination(combos, ['unknown', 'high']), undefined);
  assert.equal(supportedCombination(combos, ['a']), undefined);
  const property = { instance_id: 'model1', port_id: 'property' },
    nextProperty = { instance_id: 'model2', port_id: 'property' },
    nextCommon = { instance_id: 'model2', port_id: 'common' };
  const dimension = (target, common_key) => ({
    target,
    common_key,
    units: 'kW',
    lower: 0,
    upper: 20,
    step: null,
    covary_group: null,
  });
  const before = [dimension(target, 'common'), dimension(property, null)];
  const after = [dimension(nextCommon, 'common'), dimension(nextProperty, null)];
  const next = carryCommon(
    [
      { target, value: 14, units: 'kW' },
      { target: property, value: 9, units: 'kW' },
    ],
    before,
    [
      { target: nextCommon, value: 12, units: 'kW' },
      { target: nextProperty, value: 3, units: 'kW' },
    ],
    after,
  );
  assert.deepEqual(
    next.map((p) => p.value),
    [14, 3],
  );
  after[0].units = 'W';
  assert.equal(carryCommon(next, after, [{ target, value: 12, units: 'kW' }], before)[0].value, 12);
});
