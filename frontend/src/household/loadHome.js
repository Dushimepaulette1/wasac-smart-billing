/**
 * @file loadHome.js
 * @description What the home screen needs to decide the household's next
 * action. Flags are optional: if they fail to load, home still works.
 */

import { api } from '../api/client';

/** Anomaly types that mean "check for a leak" to a household. */
export const HIGH_USE_TYPES = ['SPIKE', 'SUSTAINED_HIGH'];

export default async function loadHome(customerId, meterId) {
  const [customer, bills, flags] = await Promise.all([
    api.getCustomer(customerId),
    api.getBills(customerId),
    api.getHouseholdFlags(meterId).catch(() => []),
  ]);
  const open = flags.filter((f) => f.status === 'open');
  return {
    customer,
    newestBill: bills[0] ?? null,
    checking: open.some((f) => f.requires_staff_review),
    highUse: open.some((f) => HIGH_USE_TYPES.includes(f.anomaly_type)),
  };
}
