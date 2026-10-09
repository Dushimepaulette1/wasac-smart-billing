/**
 * @file client.js
 * @description The one place the frontend talks to the FastAPI backend.
 * Every call returns parsed JSON or throws an ApiError whose `kind` tells
 * the screen what to say: offline, timeout, notFound, server or invalid.
 */

import { API_URL, REQUEST_TIMEOUT_MS } from '../config';
import { CUBIC_METRE_DIGITS } from '../utils/reading';

export class ApiError extends Error {
  /**
   * @param {'offline'|'timeout'|'notFound'|'server'|'invalid'} kind
   * @param {number} [status]
   * @param {string} [detail] - backend `detail`, for logs, never shown as is
   */
  constructor(kind, status, detail) {
    super(detail || kind);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = 'GET', json, body, timeout = REQUEST_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const headers = json !== undefined ? { 'Content-Type': 'application/json' } : undefined;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : body,
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw new ApiError('timeout');
    throw new ApiError('offline');
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON body: fall through to the status check.
  }

  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : undefined;
    if (response.status === 404) throw new ApiError('notFound', 404, detail);
    if (response.status === 422) throw new ApiError('invalid', 422, detail);
    throw new ApiError('server', response.status, detail);
  }
  if (data === null) throw new ApiError('server', response.status, 'Response was not JSON');
  return data;
}

/**
 * The 8 wheel digits as cubic metres for /confirm-reading, which reads the
 * value with float(): "02813450" -> "02813.450".
 * @param {string[]} cells
 */
export function cellsToCubicMetreString(cells) {
  const digits = cells.join('');
  return `${digits.slice(0, CUBIC_METRE_DIGITS)}.${digits.slice(CUBIC_METRE_DIGITS)}`;
}

export const api = {
  /** POST /submit-photo. Resolves to PhotoSubmitResponse. */
  submitPhoto(blob) {
    const form = new FormData();
    form.append('file', blob, 'meter.jpg');
    return request('/submit-photo', { method: 'POST', body: form, timeout: 60000 });
  },

  /** POST /confirm-reading. Resolves to ConfirmReadingResponse. */
  confirmReading({ customerId, meterId, cells }) {
    return request('/confirm-reading', {
      method: 'POST',
      json: {
        customer_id: customerId,
        meter_id: meterId,
        confirmed_reading: cellsToCubicMetreString(cells),
      },
    });
  },

  /** POST /calculate-bill. Tariff breakdown for a volume. */
  calculateBill(consumptionM3) {
    return request('/calculate-bill', { method: 'POST', json: { consumption_m3: consumptionM3 } });
  },

  /** GET /customers, then the one household. There is no single-customer route. */
  async getCustomer(customerId) {
    const customers = await request('/customers');
    const customer = customers.find((c) => c.customer_id === customerId);
    if (!customer) throw new ApiError('notFound', 404, `Customer ${customerId} not found`);
    return customer;
  },

  /** GET /customers/{id}/bills. Newest first, at most 12. */
  getBills(customerId) {
    return request(`/customers/${encodeURIComponent(customerId)}/bills`);
  },

  /** POST /bills/{id}/pay. */
  payBill(billId) {
    return request(`/bills/${encodeURIComponent(billId)}/pay`, { method: 'POST' });
  },

  /** GET /api/anomaly/flags?household_id= (the household id is the meter id). */
  getHouseholdFlags(meterId) {
    return request(`/api/anomaly/flags?household_id=${encodeURIComponent(meterId)}`);
  },
};
