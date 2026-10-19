/**
 * @file location.ts
 * @description The location check on a held reading (backend
 * app/anomaly/location.py), read from the flag's features. Shared by the
 * household's Messages and the staff review queue.
 */

/** The location check's outcome on a held reading (backend app/anomaly/location.py), if it needs a look. */
export interface LocationFinding {
  reason: 'far' | 'no_location' | 'imprecise' | 'upload';
  distanceM: number | null;
  accuracyM: number | null;
}

export function locationFinding(features: Record<string, unknown> | null | undefined): LocationFinding | null {
  const reason = features?.location_check;
  if (reason !== 'far' && reason !== 'no_location' && reason !== 'imprecise' && reason !== 'upload') return null;
  const num = (v: unknown) => (typeof v === 'number' ? v : null);
  return { reason, distanceM: num(features?.distance_m), accuracyM: num(features?.accuracy_m) };
}
