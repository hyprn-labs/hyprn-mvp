import { defineConfig } from 'playwright/test';
import { mkdirSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { isAbsolute, join, resolve, sep } from 'node:path';
import { servedBaseUrl } from './tests/support/served';

// Served-installation specs: the installation is named explicitly (HYPRN_MVP_UI_BASE_URL and
// HYPRN_MVP_UI_PASSWORD_FILE, see tests/support/served.ts); there is no default origin.
// Browser evidence stays in a scoped test folder or below the development evidence root
// (HYPRN_MVP_EVIDENCE_ROOT, else <HYPRN_MVP_DATA_ROOT>/evidence; deployment/local_paths.py).
function absolute(name: string): string | undefined {
  const value = process.env[name];
  if (value === undefined || value === '') return undefined;
  if (!isAbsolute(value)) throw new Error(name + ' must be an absolute path');
  return resolve(value);
}
const scope = absolute('HYPRN_MVP_TEST_SCOPE_ROOT');
const dataRoot = absolute('HYPRN_MVP_DATA_ROOT');
const developmentEvidence = absolute('HYPRN_MVP_EVIDENCE_ROOT') ?? (dataRoot && join(dataRoot, 'evidence'));
const evidenceRoots = [scope && join(scope, 'evidence'), developmentEvidence && join(developmentEvidence, 'ui')]
  .filter((root): root is string => Boolean(root)).map(root => root + sep);
if (!evidenceRoots.length) throw new Error('Browser evidence needs a scoped test folder, HYPRN_MVP_EVIDENCE_ROOT or HYPRN_MVP_DATA_ROOT');
const evidenceRoot = resolve(process.env.HYPRN_MVP_UI_EVIDENCE_ROOT ?? join(evidenceRoots[0], 'runs', `${Date.now()}-${randomUUID()}`));
if (!evidenceRoots.some(root => evidenceRoot.startsWith(root))) throw new Error('Browser evidence must stay in a scoped or development evidence folder');
process.env.HYPRN_MVP_UI_EVIDENCE_ROOT = evidenceRoot;
const snapshots = process.env.HYPRN_MVP_FOUNDRY_SNAPSHOTS;
if (snapshots && !evidenceRoots.some(root => resolve(snapshots).startsWith(root))) throw new Error('Foundry snapshots must stay in a scoped or development evidence folder');
mkdirSync(evidenceRoot, { recursive: true });
console.log(`Browser evidence: ${evidenceRoot}`);
export default defineConfig({
  snapshotPathTemplate: (snapshots ?? evidenceRoot + '/regressions') + '/{arg}{ext}',
  testDir: './tests', timeout: 45000, expect: { timeout: 8000 }, workers: 1,
  outputDir: `${evidenceRoot}/browser-${randomUUID()}`,
  reporter: [['list']],
  use: { baseURL: servedBaseUrl(), actionTimeout: 8000, viewport: { width: 1440, height: 1000 },
    // No traces containing login credentials. Screenshots are taken after login.
    trace: 'off', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium', channel: 'chrome' } }],
});
