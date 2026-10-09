/**
 * @file useRequest.ts
 * @description Loading, failed and retry state for one API call, so every
 * screen handles a slow or dropped connection the same way.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export type RequestStatus = 'idle' | 'loading' | 'success' | 'failed';

/**
 * Checking `status === 'success'` narrows `data` to R, so screens never
 * need a non-null assertion. Data from an earlier run stays while
 * reloading or after a failure.
 */
type RequestState<R> =
  | { status: 'success'; data: R; error: null }
  | { status: 'idle' | 'loading'; data: R | null; error: null }
  | { status: 'failed'; data: R | null; error: unknown };

interface RequestActions<A extends unknown[], R> {
  /** Run the call; resolves to the data, or undefined if it failed. */
  run: (...args: A) => Promise<R | undefined>;
  /** Run again with the last arguments; does nothing before the first run. */
  retry: () => Promise<R | undefined>;
}

export type RequestHandle<A extends unknown[], R> = RequestState<R> & RequestActions<A, R>;

/** Load on mount (immediate, with these args), or wait for run(). */
export type RequestOptions<A> = { immediate: true; args: A } | { immediate?: false };

export default function useRequest<A extends unknown[], R>(
  fn: (...args: A) => Promise<R>,
  options: RequestOptions<A> = {},
): RequestHandle<A, R> {
  const [state, setState] = useState<RequestState<R>>({
    status: options.immediate ? 'loading' : 'idle',
    data: null,
    error: null,
  });
  const lastArgs = useRef<A | null>(options.immediate ? options.args : null);
  const mounted = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async (...args: A): Promise<R | undefined> => {
    lastArgs.current = args;
    setState((s) => ({ status: 'loading', data: s.data, error: null }));
    try {
      const data = await fnRef.current(...args);
      if (mounted.current) setState({ status: 'success', data, error: null });
      return data;
    } catch (error) {
      if (mounted.current) setState((s) => ({ status: 'failed', data: s.data, error }));
      return undefined;
    }
  }, []);

  const retry = useCallback(
    () => (lastArgs.current ? run(...lastArgs.current) : Promise.resolve(undefined)),
    [run],
  );

  useEffect(() => {
    if (lastArgs.current && options.immediate) run(...lastArgs.current);
    // Run once on mount only; later runs go through run() or retry().
  }, []);

  return { ...state, run, retry };
}
