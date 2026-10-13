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
  GuidanceCode,
  GuideFrameResponse,
  PhotoSubmitResponse,
} from '../api/types';

/** A /submit-photo result for a clear photo; override guidance and digits per case. */
export function makePhotoResponse(overrides: Partial<PhotoSubmitResponse> = {}): PhotoSubmitResponse {
  return {
    status: 'readable',
    predicted_reading: '565846',
    confidence: 0.95,
    quality_gate_score: 0.1,
    guidance_message: null,
    models_ready: true,
    offer_manual_entry: false,
    guidance: ['OK'],
    raw_digits: '565846',
    reading_digits: '00565846',
    reading_m3: 565.846,
    confidence_min: 0.95,
    confidence_mean: 0.97,
    needs_check: false,
    quality_score: 0.1,
    crop_method: 'window',
    thumbnail_jpeg_base64: 'AAAA',
    timings_ms: {},
    ...overrides,
  };
}

/** A /submit-photo result where no meter was found: no reading suggested. */
export function makeNoMeterResponse(): PhotoSubmitResponse {
  return makePhotoResponse({
    status: 'unreadable',
    predicted_reading: null,
    confidence: null,
    offer_manual_entry: true,
    guidance: ['NO_METER'],
    raw_digits: null,
    reading_digits: null,
    reading_m3: null,
    confidence_min: null,
    confidence_mean: null,
    quality_score: null,
    crop_method: 'none',
    thumbnail_jpeg_base64: null,
  });
}

export function makeGuideFrame(guidance: GuidanceCode[] = ['OK']): GuideFrameResponse {
  return { available: true, guidance, box: null, box_method: 'window', elapsed_ms: 300 };
}

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
