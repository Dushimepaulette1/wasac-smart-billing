/**
 * @file guidance.ts
 * @description What the household sees for the backend's photo guidance codes.
 * Codes arrive most important first. One hint is shown at a time, and none of
 * them blocks: NO_METER only means no reading is suggested.
 */

import type { GuidanceCode, PhotoSubmitResponse } from '../api/types';

/** i18n key for each code that has a message. BLURRY is off in the backend, so it has none. */
const MESSAGE_KEYS: Partial<Record<GuidanceCode, string>> = {
  NO_METER: 'guidance.noMeter',
  TOO_FAR: 'guidance.tooFar',
  CUT_OFF: 'guidance.cutOff',
  TOO_DARK: 'guidance.tooDark',
  GLARE: 'guidance.glare',
  HARD_TO_READ: 'guidance.hardToRead',
  CHECK_NUMBERS: 'guidance.checkNumbers',
};

/** Codes worth a "Retake" / "Use this photo anyway" prompt after the photo is taken. */
const SOFT_RETAKE: ReadonlySet<GuidanceCode> = new Set(['TOO_FAR', 'CUT_OFF', 'TOO_DARK', 'GLARE', 'HARD_TO_READ']);

export function messageKey(code: GuidanceCode): string | null {
  return MESSAGE_KEYS[code] ?? null;
}

/** Codes that mean the number window is not properly in the picture. */
const NOT_FRAMED: ReadonlySet<GuidanceCode> = new Set(['NO_METER', 'CUT_OFF', 'TOO_FAR']);

/**
 * The number window is found and fully in the picture. Lighting hints (dark,
 * glare) do not stop an automatic photo; they are checked again after it.
 */
export function isFramed(codes: readonly GuidanceCode[]): boolean {
  return codes.length > 0 && !codes.some((code) => NOT_FRAMED.has(code));
}

/** Shown before the first steady answer, so the screen never opens with a warning. */
export const AIM_HINT = 'guidance.aim';

/**
 * The one live hint to show for a /guide-frame answer: "hold still" when the
 * window is framed (the photo is about to be taken), else the first code with
 * a message, or null (nothing to say).
 */
export function liveHint(codes: readonly GuidanceCode[]): string | null {
  if (isFramed(codes)) return 'guidance.holdStill';
  for (const code of codes) {
    const key = messageKey(code);
    if (key && code !== 'CHECK_NUMBERS') return key;
  }
  return null;
}

export type PhotoOutcome =
  /** Go to the confirm screen; checkNumbers adds "Please check the numbers." */
  | { kind: 'confirm'; checkNumbers: boolean }
  /** No meter found: "Retake" or "Type the numbers instead". */
  | { kind: 'noMeter' }
  /** A fixable problem: "Retake" or "Use this photo anyway". */
  | { kind: 'soft'; code: GuidanceCode }
  /** No reading for another reason (e.g. the reader is not available): retake, upload or type. */
  | { kind: 'unreadable' };

export function photoOutcome(result: PhotoSubmitResponse): PhotoOutcome {
  // Older backends sent no guidance list; fall back to the status field.
  const codes = result.guidance ?? [];
  if (codes.includes('NO_METER')) return { kind: 'noMeter' };
  const soft = codes.find((code) => SOFT_RETAKE.has(code));
  if (soft) return { kind: 'soft', code: soft };
  if (result.status === 'unreadable' && !result.raw_digits) return { kind: 'unreadable' };
  return { kind: 'confirm', checkNumbers: codes.includes('CHECK_NUMBERS') || result.needs_check };
}

/** The crop thumbnail as an image URL, or null. */
export function thumbnailUrl(result: PhotoSubmitResponse): string | null {
  return result.thumbnail_jpeg_base64 ? `data:image/jpeg;base64,${result.thumbnail_jpeg_base64}` : null;
}
