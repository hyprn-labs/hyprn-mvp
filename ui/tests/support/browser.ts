import { chromium } from 'playwright/test';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { userInfo } from 'node:os';
import { isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

let resolved: string | undefined;

/**
 * Chromium executable for the genuine-zoom checks (persistent context with an extension).
 *
 * Resolution: HYPRN_MVP_CHROMIUM (absolute path to an existing executable), else Playwright's own
 * resolution of its installed Chromium. Scoped test fixtures replace HOME with a scope folder,
 * and Playwright locates its browser cache from HOME, so when the direct resolution does not
 * exist it is repeated in a child process with the account's home folder (read from the
 * password database, not from HOME). No browser location is written into the tests.
 */
export function chromiumExecutable(): string {
  if (resolved) return resolved;
  const configured = process.env.HYPRN_MVP_CHROMIUM;
  if (configured) {
    if (!isAbsolute(configured) || !existsSync(configured)) throw new Error('HYPRN_MVP_CHROMIUM must name an existing Chromium executable');
    return (resolved = configured);
  }
  const direct = chromium.executablePath();
  if (existsSync(direct)) return (resolved = direct);
  const child = spawnSync(process.execPath, ['-e', "process.stdout.write(require('playwright').chromium.executablePath())"], {
    cwd: fileURLToPath(new URL('../..', import.meta.url)),
    env: { HOME: userInfo().homedir, PATH: process.env.PATH ?? '' },
    encoding: 'utf8',
  });
  const path = child.status === 0 ? child.stdout.trim() : '';
  if (!path || !isAbsolute(path) || !existsSync(path)) {
    throw new Error('Playwright Chromium not found; install it (npx playwright install chromium) or set HYPRN_MVP_CHROMIUM');
  }
  return (resolved = path);
}
