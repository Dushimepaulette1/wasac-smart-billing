/**
 * @file format.ts
 * @description Money, volume and date formats from the design brief:
 * "RWF 4,500" (no decimals), "12.4 m³", dates DD/MM/YYYY.
 * Numbers look the same in every language, as on WASAC bills: comma for
 * thousands, point for decimals. Kinyarwanda's own convention ("4.500",
 * "565,846") would make a reading of 565.846 m³ look like 565 thousand.
 * Month names come from the translation files so they are reviewed with
 * everything else.
 */

import type { Translate } from './I18nProvider';

/** The one number format used in every language (see above). */
export const NUMBER_LOCALE = 'en';

export interface Formatters {
  /** RWF, no decimals: "RWF 4,500". */
  rwf: (amount: number) => string;
  /** Volume to one decimal: "12.4 m³". */
  volume: (m3: number) => string;
  /** DD/MM/YYYY, or '' for a missing date. */
  date: (iso: string | null | undefined) => string;
  /** "September 2026". */
  monthYear: (iso: string | null | undefined) => string;
  /** "September". */
  month: (iso: string | null | undefined) => string;
}

/** "2026-09-14T10:00:00" -> { y, m, d }, read from the string itself so a
 *  naive UTC timestamp from the backend never shifts a day. */
function dateParts(iso: string | null | undefined): { y: string; m: string; d: string } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''));
  if (!match) return null;
  const [, y = '', m = '', d = ''] = match;
  return { y, m, d };
}

export function makeFormatters(t: Translate): Formatters {
  const whole = new Intl.NumberFormat(NUMBER_LOCALE, { maximumFractionDigits: 0 });
  const oneDecimal = new Intl.NumberFormat(NUMBER_LOCALE, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  return {
    rwf: (amount) => `RWF ${whole.format(Math.round(Number(amount) || 0))}`,

    volume: (m3) => `${oneDecimal.format(Number(m3) || 0)} m³`,

    date: (iso) => {
      const p = dateParts(iso);
      return p ? `${p.d}/${p.m}/${p.y}` : '';
    },

    monthYear: (iso) => {
      const p = dateParts(iso);
      return p ? `${t(`month.${Number(p.m)}`)} ${p.y}` : '';
    },

    month: (iso) => {
      const p = dateParts(iso);
      return p ? t(`month.${Number(p.m)}`) : '';
    },
  };
}

/** Today in the device's own time zone as YYYY-MM-DD, for dates we create. */
export function localDateIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
