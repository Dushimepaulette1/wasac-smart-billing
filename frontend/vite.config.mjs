/**
 * Vite config for the WASAC frontend (replaces Create React App).
 *
 * Dev server on port 3000, the origin the backend's CORS list allows.
 * Backend routes are proxied to FastAPI on :8000, as CRA's "proxy" did, so
 * VITE_API_URL can stay empty in development.
 */
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = 'http://localhost:8000';
// Backend paths only; the app's own routes (/bill, /payment, ...) are not proxied.
const API_PATHS = [
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
    setupFiles: ['./src/setupTests.js'],
    // Plain class names in tests ("cell", "active"), as CRA's Jest setup gave.
    css: { include: [/\.module\.css$/], modules: { classNameStrategy: 'non-scoped' } },
  },
});
