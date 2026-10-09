/**
 * @file config.ts
 * @description Runtime configuration from VITE_* environment variables.
 *
 * API_URL is empty by default: in development, requests go to the Vite dev
 * server, which proxies them to the backend (see vite.config.mjs),
 * so the backend's CORS list does not need the dev port.
 *
 * There is no household sign-in yet, so the household is fixed by config,
 * matching the demo customer seeded by backend/database.py.
 */

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export const CUSTOMER_ID = import.meta.env.VITE_CUSTOMER_ID || 'CUST001';
export const METER_ID = import.meta.env.VITE_METER_ID || 'MTR001';

/** A request that takes longer than this fails with a retry option. */
export const REQUEST_TIMEOUT_MS = 20000;
