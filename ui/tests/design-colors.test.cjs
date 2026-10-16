const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const catalog = JSON.parse(
  readFileSync(join(__dirname, '../../design-system/tokens.json'), 'utf8'),
);
const colors = Object.fromEntries(catalog.color.tokens.map((item) => [item.name, item.value]));
function luminance(hex) {
  const channels = hex
    .slice(1)
    .match(/../g)
    .map((channel) => parseInt(channel, 16) / 255);
  const linear = channels.map((value) =>
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
  );
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}
function contrast(a, b) {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
}
for (const theme of ['light', 'dark']) {
  test(`${theme}: text, controls and keyboard focus remain legible across semantic grounds`, () => {
    const pairs = [];
    for (const ground of [
      'canvas',
      'surface',
      'surface-sunken',
      'surface-raised',
      'shell-ground',
    ]) {
      for (const text of [
        'ink',
        'ink-2',
        'ink-muted',
        'syntax-keyword',
        'syntax-string',
        'syntax-number',
      ]) {
        pairs.push([text, ground, 4.5]);
      }
      pairs.push(
        ['focus', ground, 3],
        ['line-strong', ground, 3],
        ['plot-calculated', ground, 3],
        ['plot-estimated', ground, 3],
      );
    }
    for (const role of ['alarm', 'warning', 'advisory', 'ok', 'trace', 'ai']) {
      pairs.push([role, `${role}-soft`, 4.5]);
    }
    pairs.push(
      ['on-accent', 'accent', 4.5],
      ['on-accent', 'accent-hover', 4.5],
      ['accent', 'accent-soft', 4.5],
      ['focus-on-record', 'record', 3],
    );
    for (const [foreground, background, minimum] of pairs) {
      const ratio = contrast(colors[foreground][theme], colors[background][theme]);
      assert.ok(ratio >= minimum, `${foreground}/${background}: ${ratio.toFixed(2)} < ${minimum}`);
    }
  });
}
