import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';

const browserLicences = readFileSync(new URL('./licenses/browser.txt', import.meta.url), 'utf8');
export default defineConfig({
  base: '/ui/',
  build: {
    assetsInlineLimit: 0,
    outDir: process.env.HYPRN_MVP_UI_OUT ?? 'dist',
    emptyOutDir: true,
    sourcemap: false,
    rolldownOptions: { output: { comments: { legal: true }, banner: `/*!\n${browserLicences.replaceAll('*/', '* /')}\n*/` } },
  },
});
