/**
 * @file bills.js
 * @description Mock billing data — tariff rates pending verification.
 *
 * Rates used (to be confirmed against official WASAC schedule):
 *   Tier 1: 0-5 m3  @ RWF 329
 *   Tier 2: 5-15 m3 @ RWF 496
 *   Tier 3: 15-30 m3 @ RWF 629
 *   Tier 4: >30 m3  @ RWF 870
 *   Service charge: RWF 2,000
 */

function buildTiers(consumption) {
  const tiers = [];
  const t1 = Math.min(consumption, 5);
  if (t1 > 0) tiers.push({ name: 'Tier 1', from: 0, to: 5, units: t1, ratePerUnit: 329, cost: t1 * 329 });
  const t2 = Math.min(Math.max(consumption - 5, 0), 10);
  if (t2 > 0) tiers.push({ name: 'Tier 2', from: 5, to: 15, units: t2, ratePerUnit: 496, cost: t2 * 496 });
  const t3 = Math.min(Math.max(consumption - 15, 0), 15);
  if (t3 > 0) tiers.push({ name: 'Tier 3', from: 15, to: 30, units: t3, ratePerUnit: 629, cost: t3 * 629 });
  const t4 = Math.max(consumption - 30, 0);
  if (t4 > 0) tiers.push({ name: 'Tier 4', from: 30, to: null, units: t4, ratePerUnit: 870, cost: t4 * 870 });
  return tiers;
}
function computeTotal(c) {
  const tiers = buildTiers(c);
  return { tiers, serviceCharge: 2000, totalAmount: tiers.reduce((s, t) => s + t.cost, 0) + 2000 };
}

const sep = computeTotal(56), aug = computeTotal(55), jul = computeTotal(58);
const jun = computeTotal(57), may = computeTotal(63), apr = computeTotal(56);

export const mockBills = [
  { id: 'bill-006', period: 'September 2025', billingDate: '2025-09-18', dueDate: '2025-10-05', previousReading: 2791, currentReading: 2847, consumption: 56, tiers: sep.tiers, serviceCharge: sep.serviceCharge, totalAmount: sep.totalAmount, status: 'unpaid', paymentDate: null, transactionRef: null },
  { id: 'bill-005', period: 'August 2025', billingDate: '2025-08-19', dueDate: '2025-09-05', previousReading: 2736, currentReading: 2791, consumption: 55, tiers: aug.tiers, serviceCharge: aug.serviceCharge, totalAmount: aug.totalAmount, status: 'paid', paymentDate: '2025-08-28', transactionRef: 'TXN-MOMO-20250828-7741' },
  { id: 'bill-004', period: 'July 2025', billingDate: '2025-07-17', dueDate: '2025-08-05', previousReading: 2678, currentReading: 2736, consumption: 58, tiers: jul.tiers, serviceCharge: jul.serviceCharge, totalAmount: jul.totalAmount, status: 'paid', paymentDate: '2025-07-30', transactionRef: 'TXN-MOMO-20250730-5509' },
  { id: 'bill-003', period: 'June 2025', billingDate: '2025-06-19', dueDate: '2025-07-05', previousReading: 2621, currentReading: 2678, consumption: 57, tiers: jun.tiers, serviceCharge: jun.serviceCharge, totalAmount: jun.totalAmount, status: 'paid', paymentDate: '2025-06-27', transactionRef: 'TXN-MOMO-20250627-3302' },
  { id: 'bill-002', period: 'May 2025', billingDate: '2025-05-17', dueDate: '2025-06-05', previousReading: 2558, currentReading: 2621, consumption: 63, tiers: may.tiers, serviceCharge: may.serviceCharge, totalAmount: may.totalAmount, status: 'review', paymentDate: null, transactionRef: null },
  { id: 'bill-001', period: 'April 2025', billingDate: '2025-04-18', dueDate: '2025-05-05', previousReading: 2502, currentReading: 2558, consumption: 56, tiers: apr.tiers, serviceCharge: apr.serviceCharge, totalAmount: apr.totalAmount, status: 'paid', paymentDate: '2025-04-29', transactionRef: 'TXN-MOMO-20250429-1187' },
];
export const mockCurrentBill = mockBills[0];
