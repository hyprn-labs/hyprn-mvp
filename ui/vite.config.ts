import { defineConfig } from 'vite';
export default defineConfig({
  base: '/ui/',
  build: {
    assetsInlineLimit: 0,
    outDir: process.env.HYPRN_MVP_UI_OUT ?? 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
});
