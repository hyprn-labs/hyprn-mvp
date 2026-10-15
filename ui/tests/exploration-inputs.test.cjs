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
