/**
 * @file loadHome.ts
 * @description What the home screen needs to decide the household's next
 * action. Flags are optional: if they fail to load, home still works.
 */

import { api } from '../api/client';
import type { AnomalyFlag, AnomalyType, BillSummary, CustomerInfo } from '../api/types';

/** Anomaly types that mean "check for a leak" to a household. */
export const HIGH_USE_TYPES: readonly AnomalyType[] = ['SPIKE', 'SUSTAINED_HIGH'];

export interface HomeView {
  customer: CustomerInfo;
  newestBill: BillSummary | null;
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
  return {
    customer,
    newestBill: bills[0] ?? null,
    checking: open.some((f) => f.requires_staff_review),
    highUse: open.some((f) => HIGH_USE_TYPES.includes(f.anomaly_type)),
  };
}
