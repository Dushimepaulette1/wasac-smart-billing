/**
 * @file loadOverview.ts
 * @description Everything the staff overview shows, in one load.
 */

import { api } from '../api/client';
import type { AnomalyFlag, CustomerInfo, ReviewItem } from '../api/types';

export interface HouseholdRow extends CustomerInfo {
  unpaidCount: number;
  unpaidAmount: number;
}

export interface OverviewView {
  queue: ReviewItem[];
  openFlags: AnomalyFlag[];
  households: HouseholdRow[];
  unpaidAmount: number;
  unpaidCount: number;
}

export default async function loadOverview(): Promise<OverviewView> {
  const [customers, queue, openFlags] = await Promise.all([
    api.listCustomers(),
    api.reviewQueue(),
    api.listFlags('open'),
  ]);
  const bills = await Promise.all(customers.map((c) => api.getBills(c.customer_id).catch(() => [])));
  const households = customers.map((c, i) => {
    const unpaid = (bills[i] ?? []).filter((b) => b.payment_status !== 'paid');
    return {
      ...c,
      unpaidCount: unpaid.length,
      unpaidAmount: unpaid.reduce((sum, b) => sum + b.amount_due, 0),
    };
  });
  return {
    queue,
    openFlags,
    households,
    unpaidAmount: households.reduce((sum, h) => sum + h.unpaidAmount, 0),
    unpaidCount: households.reduce((sum, h) => sum + h.unpaidCount, 0),
  };
}
