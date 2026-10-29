/**
 * @file types.ts
 * @description Response and request models for the FastAPI backend.
 * Each type mirrors backend/app/schemas/ (or the dict a route returns, where
 * there is no schema). FastAPI sends Optional fields as null, not missing,
 * so they are `T | null`. Datetimes are ISO strings without a time zone
 * (naive UTC), e.g. "2026-10-09T10:26:25.008260".
 */

/** ISO 8601 datetime string as FastAPI serialises a naive datetime. */
export type IsoDateTime = string;

// ---------------------------------------------------------------------------
// Statuses and enums (backend constants)
// ---------------------------------------------------------------------------

/** app/anomaly/rules.py AnomalyType */
export type AnomalyType =
  | 'NORMAL'
  | 'BASELINE'
  | 'MISREAD_SUSPECTED'
  | 'SPIKE'
  | 'SUSTAINED_HIGH'
  | 'METER_STUCK'
  | 'UNUSUAL'
  /** The photo's location or source needs an officer's look (app/anomaly/location.py). */
  | 'LOCATION_CHECK'
  /** No starting value yet: the first reading becomes the starting point, without a bill. */
  | 'NO_BASELINE';

/** app/models/anomaly_flag.py FLAG_STATUS_* */
export type FlagStatus = 'open' | 'resolved';

/** app/anomaly/statuses.py READING_* */
export type ReadingStatus = 'valid' | 'anomaly_flagged' | 'pending_review' | 'rejected';

/** app/models/ Bill.payment_status */
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

/**
 * Photo guidance codes, most important first in every response. None of them
 * blocks a submission; NO_METER only means no reading is suggested.
 * (BLURRY is turned off in the backend's calibrated config.)
 */
export type GuidanceCode =
  | 'NO_METER'
  | 'TOO_FAR'
  | 'CUT_OFF'
  | 'TOO_DARK'
  | 'GLARE'
  | 'BLURRY'
  | 'HARD_TO_READ'
  | 'CHECK_NUMBERS'
  | 'OK';

/** schemas.PhotoSubmitResponse */
export interface PhotoSubmitResponse {
  /** Send back with /confirm-reading so the officer checking the reading sees this photo. */
  photo_id?: string | null;
  /** "unreadable": no reading suggested; offer typing the numbers. */
  status: 'readable' | 'unreadable';
  /** Raw digit-reader output, e.g. "565846"; null when no reading. */
  predicted_reading: string | null;
  /** Lowest digit confidence. */
  confidence: number | null;
  quality_gate_score: number | null;
  guidance_message: string | null;
  models_ready: boolean;
  offer_manual_entry: boolean;
  guidance: GuidanceCode[];
  raw_digits: string | null;
  /** 8 digits, or null when the read is impossible. */
  reading_digits: string | null;
  reading_m3: number | null;
  confidence_min: number | null;
  confidence_mean: number | null;
  needs_check: boolean;
  quality_score: number | null;
  crop_method: string;
  /** The number window as a small JPEG, for the confirm screen. */
  thumbnail_jpeg_base64: string | null;
  timings_ms: Record<string, number>;
}

/** schemas.NormalizedBox: 0-1 image coordinates */
export interface NormalizedBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/** schemas.GuideFrameResponse (POST /guide-frame) */
export interface GuideFrameResponse {
  /** false when the window detector is not loaded: no live tips. */
  available: boolean;
  guidance: GuidanceCode[];
  box: NormalizedBox | null;
  box_method: string;
  elapsed_ms: number;
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

/** app/api/routes/readings.py calculate_bill (dict, no schema) */
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
  /** A reading is waiting for an officer: no new one until the decision. */
  reading_pending: boolean;
  /** This period's reading is in; the next one opens on this date (else null). */
  next_reading_from: IsoDateTime | null;
  /** Bills not paid yet (for the staff overview). */
  unpaid_count: number;
  unpaid_amount: number;
  /** The maker's serial number printed on the meter, if WASAC has it. */
  serial_number?: string | null;
  /** A DEMO- test household. */
  is_demo?: boolean;
}

/** POST /customers: staff add a household. The server checks and cleans every field. */
export interface HouseholdInput {
  name: string;
  phone: string;
  meter_id: string;
  sector: string;
  serial_number?: string;
  /** Cubic metres as typed, e.g. "120.5"; empty for none. */
  first_reading?: string;
  /** WASAC's customer number; the server makes one if empty. */
  customer_id?: string;
}

/** PATCH /customers/{id}: the meter number never changes. */
export interface HouseholdEdit {
  name: string;
  phone: string;
  sector: string;
  serial_number?: string;
}

export interface HouseholdImportRow {
  /** Line in the file (1 is the header). */
  line: number;
  meter_id: string;
  name: string;
  action: 'new' | 'update' | 'unchanged' | 'error';
  /** Error codes, e.g. "phone" or "dup_meter:5" (the same meter as line 5). */
  errors: string[];
  /** For an update: name, phone, sector, serial. */
  changes: string[];
}

/** POST /customers/import: a preview, or (applied) what was saved. */
export interface HouseholdImportResult {
  new: number;
  update: number;
  unchanged: number;
  error: number;
  applied: boolean;
  rows: HouseholdImportRow[];
}

/** app/api/routes/billing.py customer_bills (dict per bill, no schema) */
export interface BillSummary {
  bill_id: number;
  consumption_m3: number;
  /** Can carry half-francs, e.g. 12400.5; shown rounded to whole francs. */
  amount_due: number;
  payment_status: PaymentStatus;
  created_at: IsoDateTime;
}

/** app/api/routes/billing.py pay_bill: a new payment. */
/** schemas.PaymentOut: one attempt to pay a bill (POST /bills/{id}/pay, GET /payments/{id}). */
export interface Payment {
  id: number;
  bill_id: number;
  /** momo, momo_sandbox (test money), momo_pay (USSD, checked by WASAC), simulated (no money moves). */
  provider: string;
  /** pending: waiting for the payer's PIN, or (momo_pay) for WASAC to check the transaction ID. */
  status: 'pending' | 'successful' | 'failed';
  amount: number;
  currency: string;
  transaction_id: string | null;
  /** Why it failed, in MTN's words. */
  reason: string | null;
  /** The bill was already paid before this request. */
  already_paid: boolean;
  /** momo_pay: what to dial (null until WASAC's code is set), the merchant code, the bill reference. */
  ussd_code?: string | null;
  pay_code?: string | null;
  reference?: string | null;
}

/** GET /api/payments/to-check: a MoMo Pay payment waiting for an officer. */
export interface PaymentToCheck {
  id: number;
  bill_id: number;
  customer_id: string;
  customer_name: string;
  meter_id: string | null;
  amount: number;
  transaction_id: string | null;
  created_at: IsoDateTime;
  submitted_at: IsoDateTime;
}

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
  /** The flagged reading's status: 'pending_review', 'valid' (accepted), 'rejected', 'anomaly_flagged'. */
  reading_status?: ReadingStatus | null;
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

/** schemas.HistoryPoint */
export interface HistoryPoint {
  date: IsoDateTime;
  reading_m3: number;
  consumption_m3: number | null;
}

/** schemas.ReviewItem: a held reading with what a decision needs. */
export interface ReviewItem {
  flag: AnomalyFlag;
  reading_m3: number | null;
  submitted_at: IsoDateTime | null;
  reading_confidence: number | null;
  customer_id: string | null;
  customer_name: string | null;
  sector: string | null;
  /** Up to six accepted readings, oldest first. */
  history: HistoryPoint[];
  reading_id?: number | null;
  /** The photo is kept: GET /api/anomaly/readings/{reading_id}/photo. */
  photo_available?: boolean;
  /** What the photo reader read, 8 digits. */
  reader_digits?: string | null;
  /** The household changed the reader's digits before sending. */
  edited_by_household?: boolean | null;
}

// ---------------------------------------------------------------------------
// Staff sign-in: /auth/*
// ---------------------------------------------------------------------------

/** schemas.StaffUserOut */
export interface StaffUser {
  username: string;
  full_name: string;
  role: string;
  /** Signed in with a password an admin set: choose a new one before anything else. */
  must_change_password?: boolean;
}

// ---------------------------------------------------------------------------
// Household sign-in (app/api/routes/household_auth.py)
// ---------------------------------------------------------------------------

/** CodeSent */
export interface CodeSent {
  /** The number as the backend reads it: +2507XXXXXXXX. */
  phone: string;
  expires_in: number;
  resend_after: number;
  /** Only for DEMO- households while SMS is not wired: the code, to show on screen. */
  demo_code: string | null;
}

/** HouseholdAccount: one account registered to the signed-in phone. */
export interface HouseholdAccount {
  customer_id: string;
  name: string;
  meter_id: string | null;
  sector: string | null;
  is_demo: boolean;
}

/** HouseholdSession */
export interface HouseholdSession {
  access_token: string;
  /** Unix seconds. */
  expires_at: number;
  phone: string;
  accounts: HouseholdAccount[];
}

/** Where and how the meter photo was taken (app/anomaly/location.py). */
export interface PhotoEvidence {
  photoSource: 'camera' | 'upload';
  location: { lat: number; lng: number; accuracyM: number | null } | null;
}

export type StaffRole = 'officer' | 'supervisor' | 'admin';

/** schemas.StaffAccountOut (admin only) */
export interface StaffAccount extends StaffUser {
  is_active: boolean;
  created_at: string;
  last_sign_in: string | null;
}

/** schemas.SmsOutboxOut: one message sent through the Africa's Talking sandbox (admins only). */
export interface SmsOutboxEntry {
  id: number;
  at: string;
  phone: string;
  message: string;
  /** "sent", or Africa's Talking's reason it was not. */
  status: string;
}

/** schemas.TemporaryPasswordResponse: shown once, for the admin to pass on. */
export interface TemporaryPassword {
  account: StaffAccount;
  temporary_password: string;
}

/** schemas.StaffActionOut: one row of the audit log. */
export interface StaffAction {
  id: number;
  at: string;
  username: string;
  /** sign_in, sign_in_failed, accept, reject, close, account_created, account_updated, password_reset, password_changed */
  action: string;
  target: string | null;
  detail: string | null;
}

/** schemas.LoginResponse */
export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  /** Unix seconds. */
  expires_at: number;
  user: StaffUser;
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

/** USSD is served to Africa's Talking (backend app/api/routes/ussd.py), not to this app. */

/** FastAPI error body. `detail` is a string for HTTPException, a list for validation errors. */
export interface ApiErrorBody {
  detail?: string | Array<{ loc: Array<string | number>; msg: string; type: string }>;
}
