/**
 * @file useRequest.js
 * @description Loading, failed and retry state for one API call, so every
 * screen handles a slow or dropped connection the same way.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * @template T
 * @param {(...args: any[]) => Promise<T>} fn - the API call
 * @param {{ immediate?: boolean, args?: any[] }} [options]
 *   immediate: run on mount with `args` (for loading screen data).
 * @returns {{
 *   status: 'idle'|'loading'|'success'|'failed',
 *   data: T|null,
 *   error: import('./client').ApiError|null,
 *   run: (...args: any[]) => Promise<T|undefined>,
 *   retry: () => Promise<T|undefined>,
 * }}
 */
export default function useRequest(fn, { immediate = false, args = [] } = {}) {
  const [state, setState] = useState({
    status: immediate ? 'loading' : 'idle',
    data: null,
    error: null,
  });
  const lastArgs = useRef(args);
  const mounted = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async (...callArgs) => {
    lastArgs.current = callArgs;
    setState((s) => ({ ...s, status: 'loading', error: null }));
    try {
      const data = await fnRef.current(...callArgs);
      if (mounted.current) setState({ status: 'success', data, error: null });
      return data;
    } catch (error) {
      if (mounted.current) setState((s) => ({ ...s, status: 'failed', error }));
      return undefined;
    }
  }, []);

  const retry = useCallback(() => run(...lastArgs.current), [run]);

  useEffect(() => {
    if (immediate) run(...lastArgs.current);
    // Run once on mount; later runs go through run() or retry().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { ...state, run, retry };
}
