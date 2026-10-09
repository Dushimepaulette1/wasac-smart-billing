/**
 * @file config.js
 * @description Runtime configuration from REACT_APP_* environment variables.
 *
 * API_URL is empty by default: in development, requests go to the CRA dev
 * server, which proxies them to the backend (see "proxy" in package.json),
 * so the backend's CORS list does not need the dev port.
 *
 * There is no household sign-in yet, so the household is fixed by config,
 * matching the demo customer seeded by backend/database.py.
 */

export const API_URL = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
export const CUSTOMER_ID = process.env.REACT_APP_CUSTOMER_ID || 'CUST001';
export const METER_ID = process.env.REACT_APP_METER_ID || 'MTR001';

/** A request that takes longer than this fails with a retry option. */
export const REQUEST_TIMEOUT_MS = 20000;
