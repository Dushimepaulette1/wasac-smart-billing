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
  '/submit-photo',
  '/confirm-reading',
  '/calculate-bill',
  '/customers',
  '/bills/',
  '/submit-ussd',
  '/health',
  '/api/',
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // The project lives on the Windows drive under WSL (/mnt/c), where file
    // change events never arrive; poll so edits show up without a restart.
    watch: { usePolling: true, interval: 300 },
    proxy: Object.fromEntries(API_PATHS.map((path) => [path, { target: BACKEND, changeOrigin: true }])),
  },
  build: {
    outDir: 'build',
    // Low-cost Android phones may run older Chrome versions.
    target: ['es2020', 'chrome80', 'safari14'],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    // Few workers: on the Windows drive under WSL, many jsdom workers start
    // too slowly and time out.
    maxWorkers: 2,
    // Plain class names in tests ("cell", "active"), as CRA's Jest setup gave.
    css: { include: [/\.module\.css$/], modules: { classNameStrategy: 'non-scoped' } },
  },
});
