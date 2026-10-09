/**
 * @file reading.ts
 * @description Meter reading helpers for the MeterCounter.
 * A WASAC meter shows 8 wheels: 5 for cubic metres, 3 for litres.
 * A reading is held as an array of 8 cells, each a digit string or ''
 * (blank, only while the household is typing).
 */

export const READING_LENGTH = 8;
export const LITRE_DIGITS = 3;
export const CUBIC_METRE_DIGITS = READING_LENGTH - LITRE_DIGITS;

/** One wheel: a single digit "0"-"9", or "" while blank. */
export type Cell = string;
/** The 8 wheels, cubic metres first. */
export type Cells = Cell[];

export interface NormalizedReading {
  cells: Cells;
  /** The reader's output was unusable; open the counter for typing. */
  needsCheck: boolean;
  /** The reader's own output, trimmed, so it can be shown. */
  raw: string;
}

const blankCells = (): Cells => Array<Cell>(READING_LENGTH).fill('');

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
 */
export function normalizeReading(raw: string | null | undefined): NormalizedReading {
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
 */
export function cellsFromCubicMetres(m3: number): Cells {
  const litres = Math.round(Number(m3) * 1000);
  if (!Number.isFinite(litres) || litres < 0 || litres >= 10 ** READING_LENGTH) {
    return blankCells();
  }
  return String(litres).padStart(READING_LENGTH, '0').split('');
}

export function isComplete(cells: Cells): boolean {
  return cells.length === READING_LENGTH && cells.every((c) => /^\d$/.test(c));
}

/** The 8 wheel digits as one string. */
export function cellsToDigits(cells: Cells): string {
  return cells.join('');
}

/**
 * A complete reading as plain text in the given locale, without the unit:
 * "2,813.450" (en), "2 813,450" (fr). Returns '' while cells are blank.
 *
 */
export function formatReading(cells: Cells, locale = 'en'): string {
  if (!isComplete(cells)) return '';
  const whole = Number(cells.slice(0, CUBIC_METRE_DIGITS).join(''));
  const litres = cells.slice(CUBIC_METRE_DIGITS).join('');
  const format = new Intl.NumberFormat(locale);
  const decimal = format.formatToParts(1.1).find((p) => p.type === 'decimal')?.value ?? '.';
  return `${format.format(whole)}${decimal}${litres}`;
}
