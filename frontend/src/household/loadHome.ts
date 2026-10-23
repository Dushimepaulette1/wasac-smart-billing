/**
 * @file loadHome.ts
 * @description What the home screen needs to decide the household's next
 * action. Flags are optional: if they fail to load, home still works.
 */

import { api } from '../api/client';
import type { AnomalyFlag, AnomalyType, BillSummary, CustomerInfo } from '../api/types';
import { parseUtc } from './status';

const DECISION_DAYS = 14;

/** Anomaly types that mean "check for a leak" to a household. */
export const HIGH_USE_TYPES: readonly AnomalyType[] = ['SPIKE', 'SUSTAINED_HIGH'];

export interface HomeView {
  customer: CustomerInfo;
  newestBill: BillSummary | null;
  /** Newest first, as the API sends them (the usage chart takes the last six). */
  bills: BillSummary[];
  /** The latest decision on one of the household's readings, from the last 14 days. */
  decision: AnomalyFlag | null;
  /** A reading the household sent is waiting for staff. */
  checking: boolean;
  /** An open high-use (possible leak) flag. */
  highUse: boolean;
}

export default async function loadHome(customerId: string, meterId: string): Promise<HomeView> {
  const [customer, bills, flags] = await Promise.all([
    api.getCustomer(customerId),
    api.getBills(customerId),
    api.getHouseholdFlags(meterId).catch((): AnomalyFlag[] => []),
  ]);
  const open = flags.filter((f) => f.status === 'open');
  const since = Date.now() - DECISION_DAYS * 24 * 3600 * 1000;
  const decision =
    flags
      .filter((f) => f.status === 'resolved' && f.resolved_at && (f.reading_status === 'valid' || f.reading_status === 'rejected'))
      .filter((f) => parseUtc(f.resolved_at as string) > since)
      .sort((a, b) => parseUtc(b.resolved_at as string) - parseUtc(a.resolved_at as string))[0] ?? null;
  return {
    customer,
    newestBill: bills[0] ?? null,
    bills,
    decision,
    checking: customer.reading_pending,
    highUse: open.some((f) => HIGH_USE_TYPES.includes(f.anomaly_type)),
  };
}
