/**
 * @file reading.js
 * @description Meter reading helpers for the MeterCounter.
 * A WASAC meter shows 8 wheels: 5 for cubic metres, 3 for litres.
 * A reading is held as an array of 8 cells, each a digit string or ''
 * (blank, only while the household is typing).
 */

export const READING_LENGTH = 8;
export const LITRE_DIGITS = 3;
export const CUBIC_METRE_DIGITS = READING_LENGTH - LITRE_DIGITS;

const blankCells = () => Array(READING_LENGTH).fill('');

/**
 * Turn a raw reading from /submit-photo (`predicted_reading`) into cells.
 *
 * The digit reader often drops leading zeros and sometimes returns the
 * wrong number of digits, so:
 * - 1 to 8 digits are left-padded with zeros ("565846" -> "00565846");
 * - anything else (too long, non-digits, empty) gives blank cells and
 *   `needsCheck: true`, so the screen opens the editable counter instead
 *   of showing an error.
 *
 * `raw` is always the reader's own output (trimmed), so a screen can show
 * what was read ("We read 005162454...") rather than discard it.
 *
 * @param {string|null|undefined} raw
 * @returns {{ cells: string[], needsCheck: boolean, raw: string }}
 */
export function normalizeReading(raw) {
  const text = raw == null ? '' : String(raw).trim();
  if (/^\d{1,8}$/.test(text)) {
    return { cells: text.padStart(READING_LENGTH, '0').split(''), needsCheck: false, raw: text };
  }
  return { cells: blankCells(), needsCheck: true, raw: text };
}

/**
 * Cells for a reading stored in cubic metres (e.g. 2813.45 from the API),
 * as opposed to the raw wheel digits that normalizeReading takes.
 *
 * @param {number} m3
 * @returns {string[]}
 */
export function cellsFromCubicMetres(m3) {
  const litres = Math.round(Number(m3) * 1000);
  if (!Number.isFinite(litres) || litres < 0 || litres >= 10 ** READING_LENGTH) {
    return blankCells();
  }
  return String(litres).padStart(READING_LENGTH, '0').split('');
}

/** @param {string[]} cells */
export function isComplete(cells) {
  return cells.length === READING_LENGTH && cells.every((c) => /^\d$/.test(c));
}

/**
 * The 8 wheel digits as one string, for `confirmed_reading`.
 * @param {string[]} cells
 */
export function cellsToDigits(cells) {
  return cells.join('');
}

/**
 * A complete reading as plain text in the given locale, without the unit:
 * "2,813.450" (en), "2 813,450" (fr). Returns '' while cells are blank.
 *
 * @param {string[]} cells
 * @param {string} [locale]
 */
export function formatReading(cells, locale = 'en') {
  if (!isComplete(cells)) return '';
  const whole = Number(cells.slice(0, CUBIC_METRE_DIGITS).join(''));
  const litres = cells.slice(CUBIC_METRE_DIGITS).join('');
  const format = new Intl.NumberFormat(locale);
  const decimal = format.formatToParts(1.1).find((p) => p.type === 'decimal')?.value ?? '.';
  return `${format.format(whole)}${decimal}${litres}`;
}
