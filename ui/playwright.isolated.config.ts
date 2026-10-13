import { defineConfig } from 'playwright/test';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { isAbsolute, resolve } from 'node:path';

// Validate the same marker, paths and allowlisted environment before any output
// creation or test discovery. No default endpoint and no production server start.
const repo = fileURLToPath(new URL('..', import.meta.url));
// The scoped fixture hands its children the resolved native development interpreter
// (HYPRN_MVP_NATIVE_PYTHON, documented in deployment/local_paths.py); nothing is derived here.
const python = process.env.HYPRN_MVP_NATIVE_PYTHON;
if (!python || !isAbsolute(python) || !existsSync(python)) {
  throw new Error('HYPRN_MVP_NATIVE_PYTHON must name the native development interpreter (deployment/local_paths.py)');
}
// Exactly the scoped child environment (deployment/tests/scoped_fixture.py clean_environment):
// the guard compares the whole environment for equality, so nothing else may pass.
const allowed = ['PATH', 'HOME', 'TMPDIR', 'AIIDA_PATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE',
  'LC_CTYPE', '__CF_USER_TEXT_ENCODING', 'HYPRN_MVP_TEST_SCOPE_ROOT', 'HYPRN_MVP_TEST_SCOPE_PROFILE',
  'HYPRN_MVP_TEST_SCOPE_URL', 'HYPRN_MVP_DATA_ROOT', 'HYPRN_MVP_TOOLS_DIR',
  'HYPRN_MVP_SCRATCH_ROOT', 'HYPRN_MVP_LIVE_ROOTS',
  'HYPRN_MVP_NATIVE_PYTHON', 'HYPRN_MVP_CONTRACT_PYTHON', 'HYPRN_MVP_NATIVE_INVENTORY',
  'HYPRN_MVP_TEST_FIXTURES_ROOT', 'HYPRN_MVP_UPSTREAM_CACHE', 'HYPRN_MVP_EVIDENCE_ROOT', 'HYPRN_MVP_CHROMIUM'];
const env = Object.fromEntries(allowed.flatMap(key => process.env[key] === undefined ? [] : [[key, process.env[key]!]]));
const checked = spawnSync(python, ['-B', resolve(repo, 'deployment/checks.py'), '--validate-browser'], {
  cwd: repo, env, encoding: 'utf8',
});
if (checked.status !== 0) throw new Error('Scoped browser fixture guard refused the environment');
const scope = JSON.parse(checked.stdout) as { root: string; url: string };

export default defineConfig({
  testDir: './tests',
  testMatch: ['result-bindings.spec.ts', 'modified-runs.spec.ts', 'computational-records.spec.ts'],
  forbidOnly: true, workers: 1, retries: 0,
  timeout: 45000, expect: { timeout: 8000 },
  outputDir: `${scope.root}/evidence/browser`,
  snapshotPathTemplate: `${scope.root}/evidence/snapshots/{arg}{ext}`,
  reporter: [['list']],
  use: { baseURL: scope.url, actionTimeout: 8000, viewport: { width: 1440, height: 1000 },
    trace: 'off', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium', channel: 'chrome' } }],
});
