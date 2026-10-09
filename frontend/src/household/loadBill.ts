/**
 * @file loadBill.ts
 * @description Everything the bill screen shows, from three API calls.
 *
 * The bills list has no reading values or tariff lines, so:
 * - the tariff lines come from POST /calculate-bill for the bill's volume;
 * - the meter reading is known only for the newest bill (the meter's
 *   last accepted reading); the reading before it is that minus the volume;
 * - the period runs from the previous bill's date to this bill's date.
 * There is no due date in the API, so none is shown.
 */

import { api, ApiError } from '../api/client';
import type { BillSummary, CalculatedTier } from '../api/types';
import { cellsFromCubicMetres, type Cells } from '../utils/reading';

export interface TariffLine {
  units: number;
  rate: number;
  amount: number;
}

export interface BillView {
  bill: BillSummary;
  /** Tiers that apply to this volume, cheapest first. */
  tiers: TariffLine[];
  serviceCharge: number;
  /** Date of the bill before this one, if any. */
  periodStart: string | null;
  /** This bill's meter reading and the one before it; newest bill only. */
  reading: { cells: Cells; previous: number } | null;
  /** Up to six bills, oldest first, ending with this one. */
  history: BillSummary[];
}

/** @param billId - null for the newest bill */
export default async function loadBill(customerId: string, billId: number | null): Promise<BillView> {
  const [bills, customer] = await Promise.all([api.getBills(customerId), api.getCustomer(customerId)]);
  if (!bills.length) throw new ApiError('notFound', 404, 'No bills');

  const index = billId == null ? 0 : bills.findIndex((b) => b.bill_id === billId);
  if (index === -1) throw new ApiError('notFound', 404, `Bill ${billId} not found`);
  const bill = bills[index];
  if (!bill) throw new ApiError('notFound', 404, `Bill ${billId} not found`);
  const tariff = await api.calculateBill(bill.consumption_m3);

  const isNewest = index === 0;
  return {
    bill,
    // /calculate-bill nests tiers: { breakdown: { tier1: { units, rate_rwf, amount } } }
    // Object.keys is typed string[]; these are the breakdown's own keys.
    tiers: (Object.keys(tariff.breakdown).sort() as Array<keyof typeof tariff.breakdown>)
      .map((key): CalculatedTier => tariff.breakdown[key])
      .filter((tier) => tier.units > 0)
      .map((tier) => ({ units: tier.units, rate: tier.rate_rwf, amount: tier.amount })),
    serviceCharge: tariff.service_charge,
    periodStart: bills[index + 1]?.created_at ?? null,
    reading: isNewest
      ? {
          cells: cellsFromCubicMetres(customer.last_reading),
          previous: customer.last_reading - bill.consumption_m3,
        }
      : null,
    // Oldest first, ending with this bill, for the usage bars.
    history: bills.slice(index, index + 6).reverse(),
  };
}
