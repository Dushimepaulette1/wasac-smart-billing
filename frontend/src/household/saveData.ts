/**
 * @file saveData.ts
 * @description "Save mobile data": no live camera checks; the photo is only checked after it is taken.
 * Remembered on this device.
 */

import { useCallback, useState } from 'react';

export const SAVE_DATA_KEY = 'wasac.saveData';

function read(): boolean {
  try {
    return window.localStorage.getItem(SAVE_DATA_KEY) === '1';
  } catch {
    return false;
  }
}

export function useSaveData(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(read);
  const set = useCallback((next: boolean) => {
    setOn(next);
    try {
      window.localStorage.setItem(SAVE_DATA_KEY, next ? '1' : '0');
    } catch {
      // Storage blocked: the choice still holds for this visit.
    }
  }, []);
  return [on, set];
}
