/**
 * @file submission.tsx
 * @description State of one meter reading on its way from the camera to a
 * bill: the photo, what the digit reader returned, and the digits the
 * household confirmed. Kept in sessionStorage so a dropped connection or a
 * page reload loses nothing; cleared when the reading is accepted.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { normalizeReading, type Cells } from '../utils/reading';

const STORAGE_KEY = 'wasac.submission';

export interface Submission {
  /** JPEG data URL, or null when typing by hand. */
  photo: string | null;
  /** Digit reader output, as returned. */
  raw: string | null;
  /** Digit reader confidence, 0..1. */
  confidence: number | null;
  /** The 8 counter cells the household sees. */
  cells: Cells | null;
  /** Reader output was not usable as is. */
  needsCheck: boolean;
  /** The household chose to type the numbers. */
  manual: boolean;
}

export interface SubmissionValue extends Submission {
  setPhoto: (photo: string) => void;
  /** Store a /submit-photo result; pads short readings, flags wrong ones. */
  setReadResult: (predicted: string | null, confidence: number | null) => void;
  /** Typing by hand, with or without a photo. */
  startManual: () => void;
  setCells: (cells: Cells) => void;
  reset: () => void;
}

const EMPTY: Submission = { photo: null, raw: null, confidence: null, cells: null, needsCheck: false, manual: false };

function load(): Submission {
  try {
    const saved: unknown = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? 'null');
    // Written by this module; merged over EMPTY so a missing field is safe.
    return saved && typeof saved === 'object' ? { ...EMPTY, ...(saved as Partial<Submission>) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

const SubmissionContext = createContext<SubmissionValue | null>(null);

export function SubmissionProvider({ children, initial }: { children: ReactNode; initial?: Submission }) {
  const [state, setState] = useState<Submission>(() => initial ?? load());

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Storage full or blocked (a large photo): the flow still works in memory.
    }
  }, [state]);

  const setPhoto = useCallback((photo: string) => setState({ ...EMPTY, photo }), []);

  const setReadResult = useCallback((predicted: string | null, confidence: number | null) => {
    const { cells, needsCheck, raw } = normalizeReading(predicted);
    setState((s) => ({ ...s, raw, confidence, cells, needsCheck, manual: false }));
  }, []);

  const startManual = useCallback(() => {
    setState((s) => ({ ...s, cells: normalizeReading(null).cells, needsCheck: false, manual: true }));
  }, []);

  const setCells = useCallback((cells: Cells) => setState((s) => ({ ...s, cells })), []);
  const reset = useCallback(() => setState(EMPTY), []);

  const value = useMemo<SubmissionValue>(
    () => ({ ...state, setPhoto, setReadResult, startManual, setCells, reset }),
    [state, setPhoto, setReadResult, startManual, setCells, reset],
  );
  return <SubmissionContext.Provider value={value}>{children}</SubmissionContext.Provider>;
}

export function useSubmission(): SubmissionValue {
  const ctx = useContext(SubmissionContext);
  if (!ctx) throw new Error('useSubmission must be used inside <SubmissionProvider>');
  return ctx;
}
