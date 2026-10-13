import { defineConfig } from 'vite';
export default defineConfig({ base: '/ui/', build: { outDir: process.env.HYPRN_MVP_UI_OUT ?? 'dist', emptyOutDir: true, sourcemap: false } });
