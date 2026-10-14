/**
 * @file time.ts
 * @description Audit times: the backend stores naive UTC; staff read them in
 * their own time zone, as DD/MM/YYYY HH:MM (24-hour, as the dates elsewhere).
 */

import { parseUtc } from '../household/status';

const two = (n: number) => String(n).padStart(2, '0');

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const ms = parseUtc(iso);
  if (Number.isNaN(ms)) return '';
  const d = new Date(ms);
  return `${two(d.getDate())}/${two(d.getMonth() + 1)}/${d.getFullYear()} ${two(d.getHours())}:${two(d.getMinutes())}`;
}
