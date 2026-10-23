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
  GuideFrameResponse,
  LoginResponse,
  Payment,
  PhotoSubmitResponse,
  ResolveFlagResponse,
  ReviewItem,
  CodeSent,
  HouseholdAccount,
  HouseholdSession,
  PhotoEvidence,
  SmsOutboxEntry,
  StaffAccount,
  StaffAction,
  StaffRole,
  StaffUser,
  TemporaryPassword,
} from './types';

/** A live tip that arrives late is useless; give up quickly and keep the shutter usable. */
const GUIDE_FRAME_TIMEOUT_MS = 8000;

export type ApiErrorKind =
  | 'offline'
  | 'timeout'
  | 'notFound'
  | 'server'
  | 'invalid'
  | 'unauthorized'
  /** Signed in, but the role does not allow it. */
  | 'forbidden'
  | 'locked'
  | 'conflict'
  /** Too many requests in a short time (photo endpoints). */
  | 'tooMany'
  /** Upload over the size limit. */
  | 'tooLarge';

/** Who a request is made as: the household signed in on this phone, or a staff member. */
type Auth = 'household' | 'staff';

interface Session {
  token: string | null;
  /** Called when the backend rejects the token (expired or revoked). */
  onExpired: (() => void) | null;
}

/** One token per kind of session: a staff member may use the same browser as a household. */
const sessions: Record<Auth, Session> = {
  household: { token: null, onExpired: null },
  staff: { token: null, onExpired: null },
};

export function setStaffToken(token: string | null, onExpired?: () => void): void {
  sessions.staff = { token, onExpired: onExpired ?? null };
}

export function setHouseholdToken(token: string | null, onExpired?: () => void): void {
  sessions.household = { token, onExpired: onExpired ?? null };
}

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
  /** Which session's token to send; household unless the endpoint is staff only. */
  auth?: Auth;
}

async function request<T>(
  path: string,
  { method = 'GET', json, body, timeout = REQUEST_TIMEOUT_MS, auth = 'household' }: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const headers: Record<string, string> = {};
  const session = sessions[auth];
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  const init: RequestInit = { method, signal: controller.signal, headers };
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
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
    // Error responses from FastAPI carry { detail }; anything else has none.
    const detail = (data as ApiErrorBody | null)?.detail;
    const text = typeof detail === 'string' ? detail : undefined;
    if (response.status === 401) {
      if (session.token) session.onExpired?.();
      throw new ApiError('unauthorized', 401, text);
    }
    // 429 means a sign-in lockout on /auth, and a rate limit on the photo endpoints.
    if (response.status === 429) throw new ApiError(path.startsWith('/auth') ? 'locked' : 'tooMany', 429, text);
    if (response.status === 403) throw new ApiError('forbidden', 403, text);
    if (response.status === 400) throw new ApiError('invalid', 400, text);
    if (response.status === 413) throw new ApiError('tooLarge', 413, text);
    if (response.status === 409) throw new ApiError('conflict', 409, text);
    if (response.status === 404) throw new ApiError('notFound', 404, text);
    if (response.status === 422) throw new ApiError('invalid', 422, text);
    throw new ApiError('server', response.status, text);
  }
  if (response.status === 204) return undefined as T;
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

  /** POST /guide-frame: live framing tips for a small (640 px) camera frame. */
  guideFrame(blob: Blob): Promise<GuideFrameResponse> {
    const form = new FormData();
    form.append('file', blob, 'frame.jpg');
    return request('/guide-frame', { method: 'POST', body: form, timeout: GUIDE_FRAME_TIMEOUT_MS });
  },

  /** POST /confirm-reading */
  confirmReading({
    customerId,
    meterId,
    cells,
    evidence,
  }: {
    customerId: string;
    meterId: string;
    cells: Cells;
    /** Where and how the photo was taken, for the location check. */
    evidence?: PhotoEvidence;
  }): Promise<ConfirmReadingResponse> {
    return request('/confirm-reading', {
      method: 'POST',
      json: {
        customer_id: customerId,
        meter_id: meterId,
        confirmed_reading: cellsToCubicMetreString(cells),
        photo_source: evidence?.photoSource ?? 'camera',
        location: evidence?.location
          ? { lat: evidence.location.lat, lng: evidence.location.lng, accuracy_m: evidence.location.accuracyM }
          : null,
      },
    });
  },

  // ---- Household sign-in --------------------------------------------------

  /** POST /household/request-code: the same answer whether or not the number is registered. */
  requestCode(phone: string): Promise<CodeSent> {
    return request('/household/request-code', { method: 'POST', json: { phone } });
  },

  /** POST /household/verify */
  verifyCode(phone: string, code: string): Promise<HouseholdSession> {
    return request('/household/verify', { method: 'POST', json: { phone, code } });
  },

  /** GET /household/me: check a saved session; the accounts on this phone. */
  householdMe(): Promise<HouseholdAccount[]> {
    return request('/household/me');
  },

  /** POST /calculate-bill: tariff breakdown for a volume. */
  calculateBill(consumptionM3: number): Promise<CalculateBillResponse> {
    return request('/calculate-bill', { method: 'POST', json: { consumption_m3: consumptionM3 } });
  },

  /** GET /customers/{id}: the household's own details. */
  getCustomer(customerId: string): Promise<CustomerInfo> {
    return request(`/customers/${encodeURIComponent(customerId)}`);
  },

  /** GET /customers/{id}/bills: newest first, at most 12. */
  getBills(customerId: string): Promise<BillSummary[]> {
    return request(`/customers/${encodeURIComponent(customerId)}/bills`);
  },

  /** POST /bills/{id}/pay: start paying (MTN MoMo sends a PIN prompt; simulated without keys). */
  payBill(billId: number): Promise<Payment> {
    return request(`/bills/${encodeURIComponent(billId)}/pay`, { method: 'POST' });
  },

  /** GET /payments/{id}: where a payment stands (pending, successful, failed). */
  getPayment(paymentId: number): Promise<Payment> {
    return request(`/payments/${encodeURIComponent(paymentId)}`);
  },


  /** GET /api/anomaly/flags?household_id= (the household id is the meter id). */
  getHouseholdFlags(meterId: string): Promise<AnomalyFlag[]> {
    return request(`/api/anomaly/flags?household_id=${encodeURIComponent(meterId)}`);
  },

  // ---- Staff (need a signed-in token) ------------------------------------

  /** POST /auth/login */
  login(username: string, password: string): Promise<LoginResponse> {
    return request('/auth/login', { method: 'POST', json: { username, password }, auth: 'staff' });
  },

  /** GET /auth/me: check a saved session is still valid. */
  me(): Promise<StaffUser> {
    return request('/auth/me', { auth: 'staff' });
  },

  /** POST /auth/password: change your own password. Other sessions end; this one goes on with the new token. */
  changePassword(currentPassword: string, newPassword: string): Promise<LoginResponse> {
    return request('/auth/password', {
      method: 'POST',
      auth: 'staff',
      json: { current_password: currentPassword, new_password: newPassword },
    });
  },

  /** GET /auth/activity: newest first; officers get only their own rows. */
  activity(filters: { username?: string; action?: string } = {}): Promise<StaffAction[]> {
    const params = new URLSearchParams({ limit: '200' });
    if (filters.username) params.set('username', filters.username);
    if (filters.action) params.set('action', filters.action);
    return request(`/auth/activity?${params.toString()}`, { auth: 'staff' });
  },

  /** GET /auth/sms-outbox (admin): messages sent through the SMS sandbox, newest first. */
  smsOutbox(): Promise<SmsOutboxEntry[]> {
    return request('/auth/sms-outbox', { auth: 'staff' });
  },

  /** GET /auth/staff (admin) */
  staffAccounts(): Promise<StaffAccount[]> {
    return request('/auth/staff', { auth: 'staff' });
  },

  /** POST /auth/staff (admin): the new account and its temporary password. */
  createStaffAccount(account: { username: string; full_name: string; role: StaffRole }): Promise<TemporaryPassword> {
    return request('/auth/staff', { method: 'POST', json: account, auth: 'staff' });
  },

  /** PATCH /auth/staff/{username} (admin) */
  updateStaffAccount(
    username: string,
    changes: { full_name?: string; role?: StaffRole; is_active?: boolean },
  ): Promise<StaffAccount> {
    return request(`/auth/staff/${encodeURIComponent(username)}`, { method: 'PATCH', json: changes, auth: 'staff' });
  },

  /** POST /auth/staff/{username}/reset-password (admin) */
  resetStaffPassword(username: string): Promise<TemporaryPassword> {
    return request(`/auth/staff/${encodeURIComponent(username)}/reset-password`, { method: 'POST', auth: 'staff' });
  },

  /** POST /customers/{id}/meter-correction (supervisors, admins): set the meter's current reading. */
  correctMeter(customerId: string, readingM3: number, reason: string): Promise<CustomerInfo> {
    return request(`/customers/${encodeURIComponent(customerId)}/meter-correction`, {
      method: 'POST',
      json: { reading_m3: readingM3, reason },
      auth: 'staff',
    });
  },

  /** GET /customers: every household. */
  listCustomers(): Promise<CustomerInfo[]> {
    return request('/customers', { auth: 'staff' });
  },

  /** GET /api/anomaly/flags: every household's flags. */
  listFlags(status?: 'open' | 'resolved'): Promise<AnomalyFlag[]> {
    return request(`/api/anomaly/flags${status ? `?status=${status}` : ''}`, { auth: 'staff' });
  },

  /** GET /api/anomaly/review-queue: held readings with their context. */
  reviewQueue(): Promise<ReviewItem[]> {
    return request('/api/anomaly/review-queue', { auth: 'staff' });
  },

  /** PATCH /api/anomaly/flags/{id}/resolve: accept or reject a held reading, or (null) close a follow-up. */
  resolveFlag(flagId: number, outcome: 'accept' | 'reject' | null): Promise<ResolveFlagResponse> {
    return request(`/api/anomaly/flags/${encodeURIComponent(flagId)}/resolve`, {
      method: 'PATCH',
      auth: 'staff',
      json: outcome ? { outcome } : {},
    });
  },
};
