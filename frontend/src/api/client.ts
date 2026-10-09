/**
 * @file client.ts
 * @description The one place the frontend talks to the FastAPI backend.
 * Every call returns its typed model (see ./types) or throws an ApiError
 * whose `kind` tells the screen what to say.
 */

import { API_URL, REQUEST_TIMEOUT_MS } from '../config';
import { CUBIC_METRE_DIGITS, type Cells } from '../utils/reading';
import type {
  AnomalyFlag,
  ApiErrorBody,
  BillSummary,
  CalculateBillResponse,
  ConfirmReadingResponse,
  CustomerInfo,
  PayBillResponse,
  PhotoSubmitResponse,
} from './types';

export type ApiErrorKind = 'offline' | 'timeout' | 'notFound' | 'server' | 'invalid';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | undefined;
  /** Backend `detail`, for logs; never shown to people as is. */
  readonly detail: string | undefined;

  constructor(kind: ApiErrorKind, status?: number, detail?: string) {
    super(detail || kind);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH';
  json?: unknown;
  body?: BodyInit;
  timeout?: number;
}

async function request<T>(
  path: string,
  { method = 'GET', json, body, timeout = REQUEST_TIMEOUT_MS }: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const init: RequestInit = { method, signal: controller.signal };
  if (json !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(json);
  } else if (body !== undefined) {
    init.body = body;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw new ApiError('timeout');
    throw new ApiError('offline');
  } finally {
    clearTimeout(timer);
  }

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON body: fall through to the status check.
  }

  if (!response.ok) {
    const detail = (data as ApiErrorBody | null)?.detail;
    const text = typeof detail === 'string' ? detail : undefined;
    if (response.status === 404) throw new ApiError('notFound', 404, text);
    if (response.status === 422) throw new ApiError('invalid', 422, text);
    throw new ApiError('server', response.status, text);
  }
  if (data === null) throw new ApiError('server', response.status, 'Response was not JSON');
  // Trust point: our own backend's JSON matches the models in ./types.
  return data as T;
}

/**
 * The 8 wheel digits as cubic metres for /confirm-reading, which reads the
 * value with float(): "02813450" -> "02813.450".
 */
export function cellsToCubicMetreString(cells: Cells): string {
  const digits = cells.join('');
  return `${digits.slice(0, CUBIC_METRE_DIGITS)}.${digits.slice(CUBIC_METRE_DIGITS)}`;
}

export const api = {
  /** POST /submit-photo */
  submitPhoto(blob: Blob): Promise<PhotoSubmitResponse> {
    const form = new FormData();
    form.append('file', blob, 'meter.jpg');
    return request('/submit-photo', { method: 'POST', body: form, timeout: 60000 });
  },

  /** POST /confirm-reading */
  confirmReading({
    customerId,
    meterId,
    cells,
  }: {
    customerId: string;
    meterId: string;
    cells: Cells;
  }): Promise<ConfirmReadingResponse> {
    return request('/confirm-reading', {
      method: 'POST',
      json: {
        customer_id: customerId,
        meter_id: meterId,
        confirmed_reading: cellsToCubicMetreString(cells),
      },
    });
  },

  /** POST /calculate-bill: tariff breakdown for a volume. */
  calculateBill(consumptionM3: number): Promise<CalculateBillResponse> {
    return request('/calculate-bill', { method: 'POST', json: { consumption_m3: consumptionM3 } });
  },

  /** GET /customers, then the one household. There is no single-customer route. */
  async getCustomer(customerId: string): Promise<CustomerInfo> {
    const customers = await request<CustomerInfo[]>('/customers');
    const customer = customers.find((c) => c.customer_id === customerId);
    if (!customer) throw new ApiError('notFound', 404, `Customer ${customerId} not found`);
    return customer;
  },

  /** GET /customers/{id}/bills: newest first, at most 12. */
  getBills(customerId: string): Promise<BillSummary[]> {
    return request(`/customers/${encodeURIComponent(customerId)}/bills`);
  },

  /** POST /bills/{id}/pay */
  payBill(billId: number): Promise<PayBillResponse> {
    return request(`/bills/${encodeURIComponent(billId)}/pay`, { method: 'POST' });
  },

  /** GET /api/anomaly/flags?household_id= (the household id is the meter id). */
  getHouseholdFlags(meterId: string): Promise<AnomalyFlag[]> {
    return request(`/api/anomaly/flags?household_id=${encodeURIComponent(meterId)}`);
  },
};
