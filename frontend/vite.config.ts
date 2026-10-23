/**
 * Vite config for the WASAC frontend (replaces Create React App).
 *
 * Dev server on port 3000, the origin the backend's CORS list allows.
 * Backend routes are proxied to FastAPI on :8000, as CRA's "proxy" did, so
 * VITE_API_URL can stay empty in development.
 */
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const BACKEND = 'http://localhost:8000';
// Backend paths only; the app's own routes (/bill, /payment, ...) are not proxied.
const API_PATHS = [
  '/auth',
  '/household',
  '/submit-photo',
  '/guide-frame',
  '/confirm-reading',
  '/calculate-bill',
  '/customers',
  '/bills/',
  '/payments/',
  '/ussd',
  '/health',
  '/api/',
];

const proxy = Object.fromEntries(API_PATHS.map((path) => [path, { target: BACKEND, changeOrigin: true }]));
// Testing on a phone through a Cloudflare quick tunnel (see tools/phone_test.sh).
const allowedHosts = ['.trycloudflare.com'];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // The project lives on the Windows drive under WSL (/mnt/c), where file
    // change events never arrive; poll so edits show up without a restart.
    watch: { usePolling: true, interval: 300 },
    proxy,
    allowedHosts,
  },
  // `vite preview` serves the production build the same way: same proxy, same tunnel hosts.
  preview: { port: 3000, strictPort: true, proxy, allowedHosts },
  build: {
    outDir: 'build',
    // Low-cost Android phones may run older Chrome versions.
    target: ['es2020', 'chrome80', 'safari14'],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // Tests live in tests/, mirroring src/ (tests/pages, tests/components, ...);
    // shared helpers are in tests/support/. Names read "when ..., should ...".
    include: ['tests/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    // One thread at a time: on the Windows drive under WSL, jsdom workers start
    // so slowly that two or more time out before they answer ("Failed to start").
    pool: 'threads',
    maxWorkers: 1,
    // Plain class names in tests ("cell", "active"), as CRA's Jest setup gave.
    css: { include: [/\.module\.css$/], modules: { classNameStrategy: 'non-scoped' } },
  },
});
