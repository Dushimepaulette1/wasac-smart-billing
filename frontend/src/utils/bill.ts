/**
 * @file bill.ts
 * @description What a household still owes on a bill: the balance after corrections, payments and
 * credit, from GET /customers/{id}/bills. amount_due is the bill as issued.
 */
import type { BillSummary } from '../api/types';

export function amountOwed(bill: Pick<BillSummary, 'amount_due' | 'outstanding'>): number {
  return bill.outstanding ?? bill.amount_due;
}

/** The volume a bill stands at after corrections; consumption_m3 is what was billed at the time. */
export function usedVolume(bill: Pick<BillSummary, 'consumption_m3' | 'consumption_current'>): number {
  return bill.consumption_current ?? bill.consumption_m3;
}
