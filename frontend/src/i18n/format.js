/**
 * @file format.js
 * @description Money, volume and date formats from the design brief:
 * "RWF 4,500" (no decimals), "12.4 m³", dates DD/MM/YYYY.
 * Digit grouping and the decimal sign follow the locale; month names come
 * from the translation files so they are reviewed with everything else.
 */

/** "2026-09-14T10:00:00" -> { y, m, d }, read from the string itself so a
 *  naive UTC timestamp from the backend never shifts a day. */
function dateParts(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''));
  if (!match) return null;
  return { y: match[1], m: match[2], d: match[3] };
}

export function makeFormatters(locale, t) {
  const whole = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const oneDecimal = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  return {
    /** RWF, no decimals: "RWF 4,500". */
    rwf: (amount) => `RWF ${whole.format(Math.round(Number(amount) || 0))}`,

    /** Volume to one decimal: "12.4 m³". */
    volume: (m3) => `${oneDecimal.format(Number(m3) || 0)} m³`,

    /** DD/MM/YYYY, or '' for a missing date. */
    date: (iso) => {
      const p = dateParts(iso);
      return p ? `${p.d}/${p.m}/${p.y}` : '';
    },

    /** "September 2026". */
    monthYear: (iso) => {
      const p = dateParts(iso);
      return p ? `${t(`month.${Number(p.m)}`)} ${p.y}` : '';
    },

    /** "September". */
    month: (iso) => {
      const p = dateParts(iso);
      return p ? t(`month.${Number(p.m)}`) : '';
    },
  };
}

/** Today in the device's own time zone as YYYY-MM-DD, for dates we create. */
export function localDateIso(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
