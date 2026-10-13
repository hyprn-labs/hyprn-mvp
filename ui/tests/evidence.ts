import { join } from 'node:path';

// playwright.config assigns a fresh off-cloud directory before spawning workers.
// An explicit root lets the guarded offline read inspect an earlier journey.
const root = process.env.HYPRN_MVP_UI_EVIDENCE_ROOT;
if (!root) throw new Error('Missing isolated browser evidence root');
export const evidenceRoot = root;
export const evidencePath = (name: string) => join(root, name);
