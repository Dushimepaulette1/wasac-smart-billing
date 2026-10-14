/**
 * @file config.ts
 * @description Runtime configuration from VITE_* environment variables.
 *
 * API_URL is empty by default: in development, requests go to the Vite dev
 * server, which proxies them to the backend (see vite.config.mjs),
 * so the backend's CORS list does not need the dev port.
 *
 * The household comes from sign-in (household/session.tsx), not from config.
 */

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

/** A request that takes longer than this fails with a retry option. */
export const REQUEST_TIMEOUT_MS = 20000;

