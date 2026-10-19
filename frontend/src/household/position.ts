/**
 * @file position.ts
 * @description Where the phone is while the camera is open, so a reading can
 * be checked against the meter's location (backend app/anomaly/location.py).
 * Asking is the browser's own prompt; refusing is fine: the reading is still
 * sent, and an officer checks it before it is billed.
 */

import { useEffect, useState } from 'react';
import type { PhotoEvidence } from '../api/types';

export type Position = NonNullable<PhotoEvidence['location']>;
export type PositionStatus = 'waiting' | 'found' | 'off';

/** A fix older than this is not "where the photo was taken". */
const MAX_AGE_MS = 60_000;

export function usePosition(active: boolean): { position: Position | null; status: PositionStatus } {
  const [position, setPosition] = useState<Position | null>(null);
  const [status, setStatus] = useState<PositionStatus>('waiting');

  useEffect(() => {
    if (!active) return undefined;
    if (!navigator.geolocation) {
      setStatus('off');
      return undefined;
    }
    const id = navigator.geolocation.watchPosition(
      (p) => {
        setPosition({ lat: p.coords.latitude, lng: p.coords.longitude, accuracyM: Math.round(p.coords.accuracy) });
        setStatus('found');
      },
      (err) => {
        // Refused, or switched off in the phone's settings. A timeout keeps waiting for the next fix.
        if (err.code === err.PERMISSION_DENIED || err.code === err.POSITION_UNAVAILABLE) setStatus('off');
      },
      { enableHighAccuracy: true, maximumAge: MAX_AGE_MS, timeout: 30_000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [active]);

  return { position, status };
}
