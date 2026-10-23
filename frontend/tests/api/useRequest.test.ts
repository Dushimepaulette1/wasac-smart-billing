import { act, renderHook } from '@testing-library/react';
import useRequest from '../../src/api/useRequest';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

describe('useRequest', () => {
  it('when an older request answers after a newer one, should keep the newer answer', async () => {
    const slow = deferred<string>();
    const fast = deferred<string>();
    const fn = vi.fn((which: string) => (which === 'slow' ? slow.promise : fast.promise));
    const { result } = renderHook(() => useRequest(fn));

    let first: Promise<string | undefined>;
    let second: Promise<string | undefined>;
    act(() => {
      first = result.current.run('slow');
      second = result.current.run('fast');
    });
    await act(async () => {
      fast.resolve('meter B');
      await second;
    });
    expect(result.current.data).toBe('meter B');

    await act(async () => {
      slow.resolve('meter A');
      await first;
    });
    expect(result.current.status).toBe('success');
    expect(result.current.data).toBe('meter B');
  });
});
