/**
 * @file bill.ts
 * @description What a household still owes on a bill: the balance after corrections, payments and
 * credit, from GET /customers/{id}/bills. amount_due is the bill as issued.
 */
import type { BillSummary } from '../api/types';

export function amountOwed(bill: Pick<BillSummary, 'amount_due' | 'outstanding'>): number {
  return bill.outstanding ?? bill.amount_due;
}
