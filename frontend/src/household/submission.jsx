/**
 * @file submission.jsx
 * @description State of one meter reading on its way from the camera to a
 * bill: the photo, what the digit reader returned, and the digits the
 * household confirmed. Kept in sessionStorage so a dropped connection or a
 * page reload loses nothing; cleared when the reading is accepted.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { normalizeReading } from '../utils/reading';

const STORAGE_KEY = 'wasac.submission';

/**
 * @typedef {Object} Submission
 * @property {string|null} photo - JPEG data URL, or null when typing by hand
 * @property {string|null} raw - digit reader output, as returned
 * @property {number|null} confidence - digit reader confidence, 0..1
 * @property {string[]|null} cells - the 8 counter cells the household sees
 * @property {boolean} needsCheck - reader output was not usable as is
 * @property {boolean} manual - the household chose to type the numbers
 */

const EMPTY = { photo: null, raw: null, confidence: null, cells: null, needsCheck: false, manual: false };

function load() {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY));
    return saved && typeof saved === 'object' ? { ...EMPTY, ...saved } : EMPTY;
  } catch {
    return EMPTY;
  }
}

const SubmissionContext = createContext(null);

export function SubmissionProvider({ children, initial }) {
  const [state, setState] = useState(() => initial || load());

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Storage full or blocked (a large photo): the flow still works in memory.
    }
  }, [state]);

  const setPhoto = useCallback((photo) => setState({ ...EMPTY, photo }), []);

  /** Store a /submit-photo result; pads short readings, flags wrong ones. */
  const setReadResult = useCallback((predicted, confidence) => {
    const { cells, needsCheck, raw } = normalizeReading(predicted);
    setState((s) => ({ ...s, raw, confidence: confidence ?? null, cells, needsCheck, manual: false }));
  }, []);

  /** Typing by hand, with or without a photo. */
  const startManual = useCallback(() => {
    setState((s) => ({ ...s, cells: normalizeReading(null).cells, needsCheck: false, manual: true }));
  }, []);

  const setCells = useCallback((cells) => setState((s) => ({ ...s, cells })), []);
  const reset = useCallback(() => setState(EMPTY), []);

  const value = useMemo(
    () => ({ ...state, setPhoto, setReadResult, startManual, setCells, reset }),
    [state, setPhoto, setReadResult, startManual, setCells, reset],
  );
  return <SubmissionContext.Provider value={value}>{children}</SubmissionContext.Provider>;
}

export function useSubmission() {
  const ctx = useContext(SubmissionContext);
  if (!ctx) throw new Error('useSubmission must be used inside <SubmissionProvider>');
  return ctx;
}
