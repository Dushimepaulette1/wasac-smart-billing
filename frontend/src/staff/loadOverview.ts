/**
 * @file loadOverview.ts
 * @description Everything the staff overview shows, in one load. The sector
 * count is optional: the overview still shows if it fails.
 */

import { api } from '../api/client';
import type { AnomalyFlag, CustomerInfo, ReviewItem, SectorSummary } from '../api/types';

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
  /** Sectors with readings to check or possible leaks; null if they did not load. */
  sectorsNeedingAttention: number | null;
}

export default async function loadOverview(): Promise<OverviewView> {
  const [customers, queue, openFlags, sectors] = await Promise.all([
    api.listCustomers(),
    api.reviewQueue(),
    api.listFlags('open'),
    api.listSectors().catch((): SectorSummary[] | null => null),
  ]);
  // The household list carries each household's unpaid bills: one request, not one per household.
  const households = customers.map((c) => ({ ...c, unpaidCount: c.unpaid_count, unpaidAmount: c.unpaid_amount }));
  return {
    queue,
    openFlags,
    households,
    unpaidAmount: households.reduce((sum, h) => sum + h.unpaidAmount, 0),
    unpaidCount: households.reduce((sum, h) => sum + h.unpaidCount, 0),
    sectorsNeedingAttention: sectors ? sectors.filter((s) => s.held_readings + s.possible_leaks > 0).length : null,
  };
}
