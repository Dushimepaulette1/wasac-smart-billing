/**
 * @file bills.js
 * @description Mock billing data for the WASAC Smart Billing Platform.
 * Six months of bills for the current customer (Uwimana Clarisse) using
 * the official WASAC tiered tariff rates.
 *
 * WASAC Tariff Tiers (2024 schedule):
 *   Tier 1: 0–5 m³   @ RWF 350/m³
 *   Tier 2: 6–15 m³  @ RWF 530/m³
 *   Tier 3: 16–30 m³ @ RWF 791/m³
 *   Tier 4: >30 m³   @ RWF 1,000/m³
 *   Service charge: RWF 1,000/month
 */

function buildTiers(consumption) {
  const tiers = [];

  const t1Units = Math.min(consumption, 5);
  if (t1Units > 0) {
    tiers.push({ name: 'Tier 1', from: 0, to: 5, units: t1Units, ratePerUnit: 350, cost: t1Units * 350 });
  }

  const t2Units = Math.min(Math.max(consumption - 5, 0), 10);
  if (t2Units > 0) {
    tiers.push({ name: 'Tier 2', from: 5, to: 15, units: t2Units, ratePerUnit: 530, cost: t2Units * 530 });
  }

  const t3Units = Math.min(Math.max(consumption - 15, 0), 15);
  if (t3Units > 0) {
    tiers.push({ name: 'Tier 3', from: 15, to: 30, units: t3Units, ratePerUnit: 791, cost: t3Units * 791 });
  }

  const t4Units = Math.max(consumption - 30, 0);
  if (t4Units > 0) {
    tiers.push({ name: 'Tier 4', from: 30, to: null, units: t4Units, ratePerUnit: 1000, cost: t4Units * 1000 });
  }

  return tiers;
}

function computeTotal(consumption) {
  const tiers = buildTiers(consumption);
  const tierTotal = tiers.reduce((sum, t) => sum + t.cost, 0);
  return { tiers, serviceCharge: 1000, totalAmount: tierTotal + 1000 };
}

// Realistic residential consumption: 18–26 m³/month (avg ~21.8 m³)
// Readings cascade backwards from customer.previousReading = 2791
const sep = computeTotal(22); // 2791 → 2813
const aug = computeTotal(22); // 2769 → 2791
const jul = computeTotal(24); // 2745 → 2769
const jun = computeTotal(19); // 2726 → 2745
const may = computeTotal(23); // 2703 → 2726 (anomaly-flagged — just above normal)
const apr = computeTotal(21); // 2682 → 2703

export const mockBills = [
  {
    id: 'bill-006',
    period: 'September 2025',
    billingDate: '2025-09-18',
    dueDate: '2025-10-05',
    previousReading: 2791,
    currentReading: 2813,
    consumption: 22,
    tiers: sep.tiers,
    serviceCharge: sep.serviceCharge,
    totalAmount: sep.totalAmount,
    status: 'unpaid',
    paymentDate: null,
    transactionRef: null,
  },
  {
    id: 'bill-005',
    period: 'August 2025',
    billingDate: '2025-08-19',
    dueDate: '2025-09-05',
    previousReading: 2769,
    currentReading: 2791,
    consumption: 22,
    tiers: aug.tiers,
    serviceCharge: aug.serviceCharge,
    totalAmount: aug.totalAmount,
    status: 'paid',
    paymentDate: '2025-08-28',
    transactionRef: 'TXN-MOMO-20250828-7741',
  },
  {
    id: 'bill-004',
    period: 'July 2025',
    billingDate: '2025-07-17',
    dueDate: '2025-08-05',
    previousReading: 2745,
    currentReading: 2769,
    consumption: 24,
    tiers: jul.tiers,
    serviceCharge: jul.serviceCharge,
    totalAmount: jul.totalAmount,
    status: 'paid',
    paymentDate: '2025-07-30',
    transactionRef: 'TXN-MOMO-20250730-5509',
  },
  {
    id: 'bill-003',
    period: 'June 2025',
    billingDate: '2025-06-19',
    dueDate: '2025-07-05',
    previousReading: 2726,
    currentReading: 2745,
    consumption: 19,
    tiers: jun.tiers,
    serviceCharge: jun.serviceCharge,
    totalAmount: jun.totalAmount,
    status: 'paid',
    paymentDate: '2025-06-27',
    transactionRef: 'TXN-MOMO-20250627-3302',
  },
  {
    id: 'bill-002',
    period: 'May 2025',
    billingDate: '2025-05-17',
    dueDate: '2025-06-05',
    previousReading: 2703,
    currentReading: 2726,
    consumption: 23,
    tiers: may.tiers,
    serviceCharge: may.serviceCharge,
    totalAmount: may.totalAmount,
    status: 'review',
    paymentDate: null,
    transactionRef: null,
  },
  {
    id: 'bill-001',
    period: 'April 2025',
    billingDate: '2025-04-18',
    dueDate: '2025-05-05',
    previousReading: 2682,
    currentReading: 2703,
    consumption: 21,
    tiers: apr.tiers,
    serviceCharge: apr.serviceCharge,
    totalAmount: apr.totalAmount,
    status: 'paid',
    paymentDate: '2025-04-29',
    transactionRef: 'TXN-MOMO-20250429-1187',
  },
];

export const mockCurrentBill = mockBills[0];
