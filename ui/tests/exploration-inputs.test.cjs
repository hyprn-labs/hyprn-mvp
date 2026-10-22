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

test('prediction arrival and clearing cannot shift prepared slider coordinates', () => {
  const axis = { instance_id: 'loop', port_id: 'load' };
  const other = { instance_id: 'loop', port_id: 'flow' };
  const out = { instance_id: 'loop', port_id: 'rise' };
  const dimensions = [
    { target: axis, lower: 10, upper: 20, step: null, covary_group: null },
    { target: other, lower: 1, upper: 3, step: null, covary_group: null },
  ];
  const vector = [
    { target: axis, value: 15, units: 'kW' },
    { target: other, value: 2, units: 'kg/s' },
  ];
  const prepared = [10, 20].map((value) => [{ ...vector[0], value }, vector[1]]);
  const prediction = [11, 13, 15, 17].map((value) => ({
    inputs: [{ ...vector[0], value }, vector[1]],
    outputs: [{ target: out, value: value / 2, units: 'K', kind: 'estimated' }],
  }));
  const stops = (points, selected = vector) =>
    mod.exports.preparedSliderStops(points, selected, dimensions, axis, [out], prepared);
  assert.deepEqual(
    stops([]).map((p) => p.value),
    [10, 15, 20],
  );
  assert.deepEqual(
    stops(prediction).map((p) => p.value),
    [10, 15, 20],
  );
  assert.equal(stops(prediction)[1].kind, 'estimated');
  const changed = [vector[0], { ...vector[1], value: 2.5 }];
  assert.deepEqual(stops(prediction, changed), stops([], changed));
  assert.equal(stops(prediction, changed)[1].kind, 'unavailable');
});

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

test('slider stops require complete outputs on the exact fixed-input slice', () => {
  const { availableStops } = mod.exports;
  const fixed = { instance_id: 'sink', port_id: 'temperature' };
  const output = { instance_id: 'sink', port_id: 'rise' };
  const vector = [
    { target, value: 12, units: 'kW' },
    { target: fixed, value: 20, units: 'K' },
  ];
  const dimensions = [{ target, lower: 10, upper: 15, step: null, covary_group: null }];
  const point = (value, kind = 'estimated', result = 3) => ({
    inputs: [{ ...vector[0], value }, vector[1]],
    outputs: [{ target: output, value: result, units: 'K', kind }],
  });
  const wrongSlice = point(11);
  wrongSlice.inputs[1] = { ...vector[1], value: 21 };
  const wrongUnits = point(13);
  wrongUnits.inputs[0].units = 'W';
  const points = [
    point(14),
    point(12),
    point(12, 'calculated'),
    point(10, 'estimated', null),
    point(16),
    point(13, 'unavailable'),
    wrongSlice,
    wrongUnits,
  ];
  assert.deepEqual(availableStops(points, vector, dimensions, target, [output]), [
    { value: 12, kind: 'calculated' },
    { value: 14, kind: 'estimated' },
  ]);
  assert.deepEqual(availableStops(points, vector, dimensions, target, [output, fixed]), []);
  assert.equal(vector[0].value, 12);
});

test('discrete stops respect steps and every declared covary coordinate', () => {
  const { availableStops } = mod.exports;
  const companion = { instance_id: 'other', port_id: 'heat' };
  const out = { instance_id: 'other', port_id: 'result' };
  const dimensions = [target, companion].map((target) => ({
    target,
    lower: 0,
    upper: 20,
    step: 1,
    covary_group: 'heat',
  }));
  const vector = dimensions.map((d) => ({ target: d.target, value: 12, units: 'kW' }));
  const point = (a, b) => ({
    inputs: [
      { ...vector[0], value: a },
      { ...vector[1], value: b },
    ],
    outputs: [{ target: out, value: 1, units: 'K', kind: 'calculated' }],
  });
  assert.deepEqual(
    availableStops([point(13, 13), point(14, 12), point(13.5, 13.5)], vector, dimensions, target, [
      out,
    ]),
    [{ value: 13, kind: 'calculated' }],
  );
});

test('independent selections retain coordinates without borrowing another slice result', () => {
  const { selectableStops, selectInput } = mod.exports;
  const other = { instance_id: 'coolant', port_id: 'flow' };
  const out = { instance_id: 'coolant', port_id: 'rise' };
  const baseline = [
    { target, value: 12, units: 'kW' },
    { target: other, value: 0.3, units: 'kg/s' },
  ];
  const dimensions = [
    { target, lower: 10, upper: 15, step: null, covary_group: null },
    { target: other, lower: 0.2, upper: 0.4, step: null, covary_group: null },
  ];
  const points = [10, 12, 15].map((value) => ({
    inputs: [{ ...baseline[0], value }, baseline[1]],
    outputs: [{ target: out, value: value / 1.26, units: 'K', kind: 'calculated' }],
  }));
  const selected = selectInput(
    selectInput(baseline, dimensions, target, 15),
    dimensions,
    other,
    0.25,
  );
  assert.deepEqual(
    selected.map((p) => p.value),
    [15, 0.25],
  );
  assert.deepEqual(
    selectableStops(points, selected, dimensions, target, [out]),
    [10, 12, 15].map((value) => ({ value, kind: 'unavailable' })),
  );
  const restored = selectInput(selected, dimensions, other, 0.3);
  assert.deepEqual(
    selectableStops(points, restored, dimensions, target, [out]),
    [10, 12, 15].map((value) => ({ value, kind: 'calculated' })),
  );
  assert.deepEqual(
    baseline.map((p) => p.value),
    [12, 0.3],
  );
});

test('joint sample coordinates enable every input without borrowing unqueried results', () => {
  const { selectableStops, selectInput } = mod.exports;
  const other = { instance_id: 'coolant', port_id: 'flow' };
  const out = { instance_id: 'coolant', port_id: 'rise' };
  const vector = [
    { target, value: 12, units: 'kW' },
    { target: other, value: 0.3, units: 'kg/s' },
  ];
  const dimensions = [
    { target, lower: 10, upper: 15, step: 1, covary_group: null },
    { target: other, lower: 0.2, upper: 0.4, step: null, covary_group: null },
  ];
  const baseline = {
    inputs: vector,
    outputs: [{ target: out, value: 9.5, units: 'K', kind: 'calculated' }],
  };
  const samples = Array.from({ length: 5 }, (_, i) => [
    { ...vector[0], value: 10 + i },
    { ...vector[1], value: 0.2 + i * 0.04 },
  ]);
  for (const axis of [target, other]) {
    const stops = selectableStops([baseline], vector, dimensions, axis, [out], samples);
    assert.ok(stops.length >= 5);
    assert.equal(stops.filter((s) => s.kind === 'calculated').length, 1);
    assert.equal(stops.filter((s) => s.kind === 'estimated').length, 0);
  }
  const selected = selectInput(
    selectInput(vector, dimensions, target, 14),
    dimensions,
    other,
    0.24,
  );
  const prediction = {
    inputs: selected,
    outputs: [{ target: out, value: 13.9, units: 'K', kind: 'estimated' }],
  };
  assert.equal(
    selectableStops([baseline, prediction], selected, dimensions, other, [out], samples).find(
      (s) => s.value === 0.24,
    ).kind,
    'estimated',
  );
  const invalid = [
    [{ ...vector[0], value: 13.5 }],
    [{ ...vector[0], value: 16 }],
    [{ ...vector[0], value: 11, units: 'W' }],
    [{ ...vector[0], value: NaN }],
  ];
  assert.deepEqual(selectableStops([baseline], vector, dimensions, target, [out], invalid), [
    { value: 12, kind: 'calculated' },
  ]);
});

test('compact focus shows all independent inputs despite legacy display selection and preserves connections', () => {
  const { focusQuantities } = mod.exports;
  const alias = { instance_id: 'other', port_id: 'heat' };
  const fixed = { instance_id: 'other', port_id: 'capacity' };
  const intermediate = { instance_id: 'coolant', port_id: 'transfer' };
  const terminal = { instance_id: 'other', port_id: 'temperature' };
  const independent = [target, alias, fixed].map((target) => ({
    target,
    binding: { kind: 'free' },
  }));
  const basis = {
    inputs: [...independent, { target: intermediate, binding: { kind: 'connected' } }],
    outputs: [intermediate, terminal].map((target) => ({ target })),
  };
  const dims = [target, alias].map((target) => ({
    target,
    lower: 1,
    upper: 10,
    covary_group: 'shared',
  }));
  const connections = [{ source_ref: intermediate, target_ref: alias }];
  const before = JSON.stringify(basis);
  const view = focusQuantities(basis, dims, connections, []);
  assert.deepEqual(
    view.inputs.map((p) => p.target),
    [target, fixed],
  );
  assert.deepEqual(
    view.outputs.map((p) => p.target),
    [terminal],
  );
  assert.deepEqual(
    focusQuantities(basis, dims, connections, [intermediate]).outputs.map((p) => p.target),
    [intermediate, terminal],
  );
  const authored = focusQuantities(basis, dims, connections, [], {
    input_targets: [alias],
    output_targets: [intermediate],
  });
  assert.deepEqual(
    authored.inputs.map((p) => p.target),
    [alias, fixed],
  );
  assert.deepEqual(
    authored.outputs.map((p) => p.target),
    [intermediate],
  );
  assert.equal(JSON.stringify(basis), before);
});

test('sample centre is an explicit joint vector with preserved units, steps and linked inputs', () => {
  const { sampleCentre } = mod.exports;
  const second = { instance_id: 'linked', port_id: 'copy' };
  const discrete = { instance_id: 'system', port_id: 'count' };
  const dimensions = [
    { target, lower: 0, upper: 10, units: 'kW', step: 1, covary_group: 'pair' },
    { target: second, lower: 10, upper: 30, units: 'W', step: 2, covary_group: 'pair' },
    { target: discrete, lower: 0, upper: 10, units: 'dimensionless', step: 1, covary_group: null },
  ];
  const vectors = [
    [2, 14, 3],
    [7, 24, 6],
  ].map((values) =>
    dimensions.map((d, i) => ({ target: d.target, value: values[i], units: d.units })),
  );
  const centre = sampleCentre(vectors, dimensions);
  assert.deepEqual(
    centre.map((v) => v.value),
    [5, 20, 5],
  );
  assert.deepEqual(
    centre.map((v) => v.units),
    ['kW', 'W', 'dimensionless'],
  );
  assert.equal(sampleCentre([], dimensions), undefined);
  assert.equal(sampleCentre([vectors[0], vectors[1].slice(1)], dimensions), undefined);
  const differentUnit = structuredClone(vectors);
  differentUnit[1][0].units = 'W';
  assert.equal(sampleCentre(differentUnit, dimensions), undefined);
});

test('sample centre preserves fixed input values exactly and refuses inconsistent fixed values', () => {
  const { sampleCentre } = mod.exports;
  const fixed = { instance_id: 'system', port_id: 'capacity' };
  const dimensions = [{ target, lower: 0, upper: 20, units: 'kW', step: null, covary_group: null }];
  const vectors = Array.from({ length: 17 }, (_, i) => [
    { target, value: i, units: 'kW' },
    { target: fixed, value: 12, units: 'kW' },
  ]);
  const centre = sampleCentre(vectors, dimensions);
  assert.equal(centre.find((v) => v.target.port_id === 'capacity').value, 12);
  vectors[16][1].value = 13;
  assert.equal(sampleCentre(vectors, dimensions), undefined);
});

const recoveryFile = resolve(__dirname, '../src/predictionRecovery.ts');
const recovery = new Module(recoveryFile, module);
recovery._compile(
  ts.transpileModule(readFileSync(recoveryFile, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText,
  recoveryFile,
);
const { recoverPrediction } = recovery.exports;

test('pure prediction recovers transient failure without replacing the pinned request', async () => {
  const signal = new AbortController().signal;
  const estimate = Object.freeze({ id: 'saved-estimate', inputs: [2, 3] });
  const seen = [];
  const result = await recoverPrediction(
    async () => {
      seen.push(estimate);
      if (seen.length < 3) throw new Error('temporary');
      return { value: 5, kind: 'estimated' };
    },
    (e) => e.message === 'temporary',
    signal,
  );
  assert.deepEqual(result, { value: 5, kind: 'estimated' });
  assert.equal(seen.length, 3);
  assert.ok(seen.every((v) => v === estimate));
});

test('prediction recovery stops on a changed selection, refusal or persistent failure', async () => {
  const controller = new AbortController();
  let calls = 0;
  await assert.rejects(
    recoverPrediction(
      async () => {
        calls++;
        controller.abort(new Error('selection changed'));
        throw new Error('temporary');
      },
      () => true,
      controller.signal,
    ),
    /selection changed/,
  );
  assert.equal(calls, 1);
  calls = 0;
  await assert.rejects(
    recoverPrediction(
      async () => {
        calls++;
        throw new Error('invalid input');
      },
      () => false,
      new AbortController().signal,
    ),
    /invalid input/,
  );
  assert.equal(calls, 1);
  calls = 0;
  await assert.rejects(
    recoverPrediction(
      async () => {
        calls++;
        throw new Error('unavailable');
      },
      () => true,
      new AbortController().signal,
    ),
    /unavailable/,
  );
  assert.equal(calls, 3);
});

test('changing selection during recovery backoff prevents another prediction', async () => {
  const controller = new AbortController();
  let calls = 0;
  const pending = recoverPrediction(
    async () => {
      calls++;
      throw new Error('temporary');
    },
    () => true,
    controller.signal,
  );
  setTimeout(() => controller.abort(new Error('new selection')), 10);
  await assert.rejects(pending, /new selection/);
  assert.equal(calls, 1);
});
