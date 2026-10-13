import { readFileSync } from 'node:fs';
import { isAbsolute } from 'node:path';

/**
 * The served installation a served-installation spec talks to, named explicitly and never
 * defaulted (documented in deployment/local_paths.py):
 *
 * - HYPRN_MVP_UI_BASE_URL: base URL of the served installation (its origin; the UI is below /ui/);
 * - HYPRN_MVP_UI_PASSWORD_FILE: absolute path of a file holding the owner password.
 *
 * Served-installation specs write studies, so they run only against an installation created
 * for testing (the runner's opt-in groups refuse the development installation's port).
 */
export function servedBaseUrl(): string {
  const value = process.env.HYPRN_MVP_UI_BASE_URL;
  if (!value) throw new Error('HYPRN_MVP_UI_BASE_URL is not set: export the base URL of the served installation to test');
  const url = new URL(value);
  if ((url.protocol !== 'http:' && url.protocol !== 'https:') || url.username || url.password || url.search || url.hash
      || (url.pathname !== '/' && url.pathname !== '')) {
    throw new Error('HYPRN_MVP_UI_BASE_URL must be an http(s) origin without credentials, path, query or fragment');
  }
  return url.origin;
}

/** Origin header value for explicit API requests to the served installation. */
export const servedOrigin = servedBaseUrl;

export function ownerPassword(): string {
  const file = process.env.HYPRN_MVP_UI_PASSWORD_FILE;
  if (!file || !isAbsolute(file)) {
    throw new Error('HYPRN_MVP_UI_PASSWORD_FILE is not set: export the absolute path of the owner password file');
  }
  const password = readFileSync(file, 'utf8').trim();
  if (!password) throw new Error('HYPRN_MVP_UI_PASSWORD_FILE names an empty file');
  return password;
}
