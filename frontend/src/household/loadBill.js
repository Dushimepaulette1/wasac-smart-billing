/**
 * @file loadBill.js
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
import { cellsFromCubicMetres } from '../utils/reading';

/**
 * @param {string} customerId
 * @param {number|null} billId - null for the newest bill
 */
export default async function loadBill(customerId, billId) {
  const [bills, customer] = await Promise.all([api.getBills(customerId), api.getCustomer(customerId)]);
  if (!bills.length) throw new ApiError('notFound', 404, 'No bills');

  const index = billId == null ? 0 : bills.findIndex((b) => b.bill_id === billId);
  if (index === -1) throw new ApiError('notFound', 404, `Bill ${billId} not found`);
  const bill = bills[index];
  const tariff = await api.calculateBill(bill.consumption_m3);

  const isNewest = index === 0;
  return {
    bill,
    // /calculate-bill nests tiers: { breakdown: { tier1: { units, rate_rwf, amount } } }
    tiers: Object.keys(tariff.breakdown || {})
      .sort()
      .map((key) => tariff.breakdown[key])
      .filter((tier) => tier.units > 0)
      .map((tier) => ({ units: tier.units, rate: tier.rate_rwf, amount: tier.amount })),
    serviceCharge: tariff.service_charge,
    periodStart: bills[index + 1]?.created_at ?? null,
    reading: isNewest ? cellsFromCubicMetres(customer.last_reading) : null,
    previousReading: isNewest ? customer.last_reading - bill.consumption_m3 : null,
    // Oldest first, ending with this bill, for the usage bars.
    history: bills.slice(index, index + 6).reverse(),
  };
}
