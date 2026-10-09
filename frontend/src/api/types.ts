/**
 * @file types.ts
 * @description Response and request models for the FastAPI backend.
 * Each type mirrors backend/schemas.py (or the dict a route returns, where
 * there is no schema). FastAPI sends Optional fields as null, not missing,
 * so they are `T | null`. Datetimes are ISO strings without a time zone
 * (naive UTC), e.g. "2026-10-09T10:26:25.008260".
 */

/** ISO 8601 datetime string as FastAPI serialises a naive datetime. */
export type IsoDateTime = string;

// ---------------------------------------------------------------------------
// Statuses and enums (backend constants)
// ---------------------------------------------------------------------------

/** anomaly/rules.py AnomalyType */
export type AnomalyType =
  | 'NORMAL'
  | 'BASELINE'
  | 'MISREAD_SUSPECTED'
  | 'SPIKE'
  | 'SUSTAINED_HIGH'
  | 'METER_STUCK'
  | 'UNUSUAL';

/** anomaly/db_models.py FLAG_STATUS_* */
export type FlagStatus = 'open' | 'resolved';

/** anomaly/statuses.py READING_* */
export type ReadingStatus = 'valid' | 'anomaly_flagged' | 'pending_review' | 'rejected';

/** database.py Bill.payment_status */
export type PaymentStatus = 'paid' | 'unpaid';

/**
 * Feature values the anomaly detector computed (ratios, streaks, the raw
 * digits...). Free-form on the backend (a plain dict), so values are
 * unknown here and must be narrowed before use.
 */
export type AnomalyFeatures = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Meter reading: POST /submit-photo, POST /confirm-reading
// ---------------------------------------------------------------------------

/** schemas.PhotoSubmitResponse */
export interface PhotoSubmitResponse {
  status: 'readable' | 'unreadable';
  /** Raw digit-reader output, e.g. "00444"; null when unreadable. */
  predicted_reading: string | null;
  confidence: number | null;
  quality_gate_score: number | null;
  guidance_message: string | null;
}

/** schemas.ConfirmReadingRequest */
export interface ConfirmReadingRequest {
  customer_id: string;
  meter_id: string;
  /** Cubic metres as a decimal string; the backend reads it with float(). */
  confirmed_reading: string;
}

/** schemas.TariffBreakdown (flat tiers, as /confirm-reading returns them) */
export interface TariffBreakdown {
  tier1_units: number;
  tier1_rate: number;
  tier1_amount: number;
  tier2_units: number;
  tier2_rate: number;
  tier2_amount: number;
  tier3_units: number;
  tier3_rate: number;
  tier3_amount: number;
  tier4_units: number;
  tier4_rate: number;
  tier4_amount: number;
  service_charge: number;
  total: number;
}

/** schemas.AnomalyResultSchema */
export interface AnomalyResult {
  household_id: string;
  reading_m3: number | null;
  daily_consumption: number | null;
  anomaly_score: number | null;
  is_anomaly: boolean;
  anomaly_type: AnomalyType;
  needs_retake: boolean;
  /** English SMS text; the frontend shows its own translated copy instead. */
  message_for_household: string;
  features: AnomalyFeatures;
  model_used: boolean;
  flag_id: number | null;
  pending_review: boolean;
  actions: string[];
}

/** schemas.ConfirmReadingResponse */
export interface ConfirmReadingResponse {
  success: boolean;
  bill_amount: number | null;
  consumption_m3: number | null;
  tariff_breakdown: TariffBreakdown | null;
  validation_status: ReadingStatus;
  anomaly_flagged: boolean;
  anomaly_score: number | null;
  error_message: string | null;
  /** Null when the reading is held for review (no bill yet). */
  bill_id: number | null;
  anomaly: AnomalyResult | null;
}

// ---------------------------------------------------------------------------
// Billing: POST /calculate-bill, GET /customers, GET /customers/{id}/bills,
// POST /bills/{id}/pay
// ---------------------------------------------------------------------------

/** schemas.BillCalculateRequest */
export interface BillCalculateRequest {
  consumption_m3: number;
}

/** One tier as /calculate-bill returns it (nested, unlike TariffBreakdown). */
export interface CalculatedTier {
  units: number;
  rate_rwf: number;
  amount: number;
}

/** routes/reading.py calculate_bill (dict, no schema) */
export interface CalculateBillResponse {
  consumption_m3: number;
  breakdown: {
    tier1: CalculatedTier;
    tier2: CalculatedTier;
    tier3: CalculatedTier;
    tier4: CalculatedTier;
  };
  service_charge: number;
  total_amount_due: number;
  currency: 'RWF';
}

/** schemas.CustomerInfo */
export interface CustomerInfo {
  customer_id: string;
  name: string;
  /** "+250788123456" */
  phone: string;
  sector: string;
  meter_id: string;
  /** Last accepted reading, cubic metres. */
  last_reading: number;
  last_reading_date: IsoDateTime | null;
  avg_consumption: number | null;
  anomaly_flagged: boolean;
}

/** routes/billing.py customer_bills (dict per bill, no schema) */
export interface BillSummary {
  bill_id: number;
  consumption_m3: number;
  /** Can carry half-francs, e.g. 12400.5; shown rounded to whole francs. */
  amount_due: number;
  payment_status: PaymentStatus;
  created_at: IsoDateTime;
}

/** routes/billing.py pay_bill: a new payment. */
export interface PayBillSuccess {
  success: true;
  bill_id: number;
  transaction_id: string;
  amount_paid: number;
  message: string;
}

/** routes/billing.py pay_bill: the bill was paid before (no transaction). */
export interface PayBillAlreadyPaid {
  message: 'Bill already paid';
  bill_id: number;
}

export type PayBillResponse = PayBillSuccess | PayBillAlreadyPaid;

// ---------------------------------------------------------------------------
// Anomaly flags: /api/anomaly/*
// ---------------------------------------------------------------------------

/** schemas.AnomalyScoreRequest */
export interface AnomalyScoreRequest {
  household_id: string;
  reading_digits: string;
  reading_date?: IsoDateTime | null;
}

/** schemas.AnomalyFlagOut. household_id is the meter id. */
export interface AnomalyFlag {
  id: number;
  household_id: string;
  reading_id: number | null;
  anomaly_type: AnomalyType;
  anomaly_score: number | null;
  features: AnomalyFeatures | null;
  requires_staff_review: boolean;
  message_for_household: string | null;
  status: FlagStatus;
  created_at: IsoDateTime;
  resolved_at: IsoDateTime | null;
}

/** schemas.ResolveFlagRequest */
export interface ResolveFlagRequest {
  outcome?: 'accept' | 'reject' | null;
}

/** schemas.ResolveFlagResponse */
export interface ResolveFlagResponse extends AnomalyFlag {
  outcome: 'accept' | 'reject' | null;
  reading_status: ReadingStatus | null;
  bill_id: number | null;
  amount_due: number | null;
  actions: string[];
}

// ---------------------------------------------------------------------------
// System and USSD
// ---------------------------------------------------------------------------

/** schemas.HealthResponse */
export interface HealthResponse {
  status: string;
  database: string;
  quality_gate_model: string;
  crnn_model: string;
  anomaly_detector: string;
  timestamp: IsoDateTime;
}

/** schemas.USSDRequest */
export interface UssdRequest {
  phone_number: string;
  reading_value: string;
  session_id?: string | null;
}

/** routes/ussd.py submit_ussd (dict, no schema) */
export interface UssdResponse {
  /** Text for the phone screen, starting "END ". */
  response: string;
  anomaly?: AnomalyResult;
}

/** FastAPI error body. `detail` is a string for HTTPException, a list for validation errors. */
export interface ApiErrorBody {
  detail?: string | Array<{ loc: Array<string | number>; msg: string; type: string }>;
}
