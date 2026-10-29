/**
 * @file issues.ts
 * @description Anomaly types in plain words for staff ("Much higher than
 * usual", not "SPIKE"), and the numbers a decision rests on.
 */

import type { AnomalyFlag, AnomalyType, HistoryPoint } from '../api/types';

export const ISSUE_KEY: Record<AnomalyType, string> = {
  SPIKE: 'issue.spike',
  SUSTAINED_HIGH: 'issue.sustainedHigh',
  MISREAD_SUSPECTED: 'issue.misread',
  METER_STUCK: 'issue.stuck',
  UNUSUAL: 'issue.unusual',
  BASELINE: 'issue.baseline',
  NORMAL: 'issue.normal',
  LOCATION_CHECK: 'issue.location',
  NO_BASELINE: 'issue.noBaseline',
};

/** The plain-words label for a flag: a suspected misread is either a reading lower than the last
 *  one or about 10x/100x the usual use (a shifted digit, features.digit_shift). */
export function issueKey(flag: Pick<AnomalyFlag, 'anomaly_type' | 'features'>): string {
  if (flag.anomaly_type === 'MISREAD_SUSPECTED' && flag.features?.digit_shift) return 'issue.digitShift';
  return ISSUE_KEY[flag.anomaly_type];
}

/** Median of the household's accepted monthly use; null with no history. */
export function usualUse(history: HistoryPoint[]): number | null {
  const values = history.map((h) => h.consumption_m3).filter((v): v is number => v !== null && v > 0);
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const middle = sorted[mid] ?? 0;
  return sorted.length % 2 ? middle : ((sorted[mid - 1] ?? middle) + middle) / 2;
}

/** The last accepted reading before this one. */
export function previousReading(history: HistoryPoint[]): number | null {
  return history.length ? (history[history.length - 1]?.reading_m3 ?? null) : null;
}
