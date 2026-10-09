/**
 * @file fixtures.ts
 * @description Complete, typed API objects for tests, based on the demo
 * data the backend seeds (CUST001 / MTR001). Override only what a test
 * cares about.
 */

import type {
  AnomalyFlag,
  AnomalyResult,
  BillSummary,
  CalculateBillResponse,
  ConfirmReadingResponse,
  CustomerInfo,
} from '../api/types';

/** A fetch Response with only what the API client reads: ok, status, json(). */
export function jsonResponse(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as unknown as Response;
}

export function makeCustomer(overrides: Partial<CustomerInfo> = {}): CustomerInfo {
  return {
    customer_id: 'CUST001',
    name: 'Uwimana Jean Pierre',
    phone: '+250788123456',
    sector: 'Kacyiru',
    meter_id: 'MTR001',
    last_reading: 464,
    last_reading_date: '2026-09-09T09:38:11',
    avg_consumption: 20,
    anomaly_flagged: false,
    ...overrides,
  };
}

export function makeBill(overrides: Partial<BillSummary> = {}): BillSummary {
  return {
    bill_id: 19,
    consumption_m3: 20.5,
    amount_due: 12400.5,
    payment_status: 'unpaid',
    created_at: '2026-10-09T10:26:25',
    ...overrides,
  };
}

export function makeFlag(overrides: Partial<AnomalyFlag> = {}): AnomalyFlag {
  return {
    id: 1,
    household_id: 'MTR001',
    reading_id: 20,
    anomaly_type: 'MISREAD_SUSPECTED',
    anomaly_score: null,
    features: null,
    requires_staff_review: true,
    message_for_household: 'WASAC: backend English text',
    status: 'open',
    created_at: '2026-10-09T10:39:57',
    resolved_at: null,
    ...overrides,
  };
}

/** The real /calculate-bill response for 20.5 m3. */
export function makeCalculatedBill(): CalculateBillResponse {
  return {
    consumption_m3: 20.5,
    breakdown: {
      tier1: { units: 5, rate_rwf: 350, amount: 1750 },
      tier2: { units: 10, rate_rwf: 530, amount: 5300 },
      tier3: { units: 5.5, rate_rwf: 791, amount: 4350.5 },
      tier4: { units: 0, rate_rwf: 1000, amount: 0 },
    },
    service_charge: 1000,
    total_amount_due: 12400.5,
    currency: 'RWF',
  };
}

export function makeAnomalyResult(overrides: Partial<AnomalyResult> = {}): AnomalyResult {
  return {
    household_id: 'MTR001',
    reading_m3: 0.444,
    daily_consumption: null,
    anomaly_score: null,
    is_anomaly: true,
    anomaly_type: 'MISREAD_SUSPECTED',
    needs_retake: false,
    message_for_household: 'WASAC: backend English text',
    features: {},
    model_used: false,
    flag_id: 2,
    pending_review: true,
    actions: [],
    ...overrides,
  };
}

/** A reading that created a bill; override for held or retake outcomes. */
export function makeConfirmResponse(overrides: Partial<ConfirmReadingResponse> = {}): ConfirmReadingResponse {
  return {
    success: true,
    bill_amount: 12400.5,
    consumption_m3: 20.5,
    tariff_breakdown: null,
    validation_status: 'valid',
    anomaly_flagged: false,
    anomaly_score: null,
    error_message: null,
    bill_id: 19,
    anomaly: null,
    ...overrides,
  };
}
