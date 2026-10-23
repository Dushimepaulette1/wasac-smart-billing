/**
 * @file submission.tsx
 * @description State of one meter reading on its way from the camera to a
 * bill: the photo, what the digit reader returned, and the digits the
 * household confirmed. Kept in sessionStorage so a dropped connection or a
 * page reload loses nothing; cleared when the reading is accepted.
 *
 * A draft belongs to the account it was started for: after switching meter,
 * signing out, or another household signing in on the same phone, it is
 * dropped, never sent for the wrong meter.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { normalizeReading, type Cells } from '../utils/reading';
import type { PhotoEvidence } from '../api/types';
import { useAccountId } from './session';

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
  /** The meter's number window cut from the photo (data URL), shown above the counter. */
  crop: string | null;
  /** The reader was unsure: say "Please check the numbers." */
  checkNumbers: boolean;
  /** Camera or gallery, and where the phone was, sent with the reading for the location check. */
  evidence: PhotoEvidence | null;
  /** The customer the draft was started for. */
  owner?: string | null;
  /** /submit-photo's id for the photo, sent with the reading for the officer who may check it. */
  photoId?: string | null;
}

export interface ReadExtras {
  crop?: string | null;
  checkNumbers?: boolean;
  photoId?: string | null;
}

export interface SubmissionValue extends Submission {
  setPhoto: (photo: string, evidence: PhotoEvidence) => void;
  /** Store a /submit-photo result; pads short readings, flags wrong ones. */
  setReadResult: (predicted: string | null, confidence: number | null, extras?: ReadExtras) => void;
  /** Typing by hand, with or without a photo. */
  startManual: () => void;
  setCells: (cells: Cells) => void;
  reset: () => void;
}

const EMPTY: Submission = {
  photo: null,
  raw: null,
  confidence: null,
  cells: null,
  needsCheck: false,
  manual: false,
  crop: null,
  checkNumbers: false,
  evidence: null,
};

function load(owner: string | null): Submission {
  try {
    const saved: unknown = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? 'null');
    // Written by this module; merged over EMPTY so a missing field is safe.
    const draft = saved && typeof saved === 'object' ? { ...EMPTY, ...(saved as Partial<Submission>) } : EMPTY;
    return draft.owner === owner ? draft : { ...EMPTY, owner };
  } catch {
    return { ...EMPTY, owner };
  }
}

const SubmissionContext = createContext<SubmissionValue | null>(null);

export function SubmissionProvider({ children, initial }: { children: ReactNode; initial?: Submission }) {
  const owner = useAccountId();
  const [saved, setState] = useState<Submission>(() => (initial ? { ...initial, owner } : load(owner)));
  const own = useCallback((s: Submission) => (s.owner === owner ? s : { ...EMPTY, owner }), [owner]);
  // Another account's draft is never shown, not even for the one render before it is dropped.
  const state = useMemo(() => own(saved), [own, saved]);

  useEffect(() => {
    if (saved.owner !== owner) setState(own);
  }, [saved.owner, owner, own]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Storage full or blocked (a large photo): the flow still works in memory.
    }
  }, [state]);

  const setPhoto = useCallback(
    (photo: string, evidence: PhotoEvidence) => setState({ ...EMPTY, photo, evidence, owner }),
    [owner],
  );

  const setReadResult = useCallback((predicted: string | null, confidence: number | null, extras: ReadExtras = {}) => {
    const { cells, needsCheck, raw } = normalizeReading(predicted);
    setState((s) => ({
      ...own(s),
      raw,
      confidence,
      cells,
      needsCheck,
      manual: false,
      crop: extras.crop ?? null,
      checkNumbers: extras.checkNumbers ?? false,
      photoId: extras.photoId ?? null,
    }));
  }, [own]);

  const startManual = useCallback(() => {
    setState((s) => ({
      ...own(s),
      cells: normalizeReading(null).cells,
      needsCheck: false,
      manual: true,
      crop: null,
      checkNumbers: false,
    }));
  }, [own]);

  const setCells = useCallback((cells: Cells) => setState((s) => ({ ...own(s), cells })), [own]);
  const reset = useCallback(() => setState({ ...EMPTY, owner }), [owner]);

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
