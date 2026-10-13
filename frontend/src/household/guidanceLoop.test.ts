import { GuidanceLoop, type LoopDeps } from './guidanceLoop';
import { makeGuideFrame } from '../test/fixtures';
import type { GuideFrameResponse } from '../api/types';

/** Let pending promise callbacks run. */
const flush = async () => {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
};

interface Pending {
  resolve: (r: GuideFrameResponse) => void;
  reject: (e: unknown) => void;
}

/** A loop whose /guide-frame answers the test releases one by one. */
function setup(overrides: Partial<LoopDeps> = {}) {
  const pending: Pending[] = [];
  let clock = 0;
  const deps = {
    grab: vi.fn(() => Promise.resolve(new Blob(['frame']))),
    send: vi.fn(
      () => new Promise<GuideFrameResponse>((resolve, reject) => pending.push({ resolve, reject })),
    ),
    onResult: vi.fn(),
    onReady: vi.fn(),
    onEnd: vi.fn(),
    now: () => clock,
    wait: () => Promise.resolve(),
    ...overrides,
  };
  const loop = new GuidanceLoop(deps);
  const answer = async (frame: GuideFrameResponse) => {
    pending.shift()?.resolve(frame);
    await flush();
  };
  return { loop, deps, pending, answer, advance: (ms: number) => (clock += ms) };
}

describe('GuidanceLoop', () => {
  it('sends one frame at a time: the next only after the answer', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    expect(deps.send).toHaveBeenCalledTimes(1);
    await flush();
    expect(deps.send).toHaveBeenCalledTimes(1); // still waiting for the first answer
    await answer(makeGuideFrame(['TOO_FAR']));
    expect(deps.send).toHaveBeenCalledTimes(2);
    expect(deps.onResult).toHaveBeenCalledWith(makeGuideFrame(['TOO_FAR']));
    loop.stop();
  });

  it('is ready after two OK answers in a row, and stops', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    await answer(makeGuideFrame(['OK']));
    expect(deps.onReady).not.toHaveBeenCalled();
    await answer(makeGuideFrame(['OK']));
    expect(deps.onReady).toHaveBeenCalledTimes(1);
    expect(loop.active).toBe(false);
    expect(deps.send).toHaveBeenCalledTimes(2);
  });

  it('needs the two OK answers to be in a row', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    await answer(makeGuideFrame(['OK']));
    await answer(makeGuideFrame(['GLARE']));
    await answer(makeGuideFrame(['OK']));
    expect(deps.onReady).not.toHaveBeenCalled();
    await answer(makeGuideFrame(['OK']));
    expect(deps.onReady).toHaveBeenCalledTimes(1);
  });

  it('stops after the time limit', async () => {
    const { loop, deps, answer, advance } = setup({ limitMs: 30_000 });
    loop.start();
    await flush();
    advance(30_000);
    await answer(makeGuideFrame(['TOO_FAR']));
    expect(deps.onEnd).toHaveBeenCalledWith('timeLimit');
    expect(deps.send).toHaveBeenCalledTimes(1);
  });

  it('pauses while the tab is hidden and continues when it is shown', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    loop.pause();
    await answer(makeGuideFrame(['TOO_FAR']));
    expect(deps.send).toHaveBeenCalledTimes(1);
    loop.resume();
    await flush();
    expect(deps.send).toHaveBeenCalledTimes(2);
    loop.stop();
  });

  it('gives up quietly on a network error', async () => {
    const { loop, deps, pending } = setup();
    loop.start();
    await flush();
    pending.shift()?.reject(new Error('offline'));
    await flush();
    expect(deps.onEnd).toHaveBeenCalledWith('error');
    expect(loop.active).toBe(false);
  });

  it('gives up when the backend has no window detector', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    await answer({ ...makeGuideFrame(['OK']), available: false });
    expect(deps.onEnd).toHaveBeenCalledWith('unavailable');
    expect(deps.onResult).not.toHaveBeenCalled();
  });

  it('waits for a camera frame before sending', async () => {
    const grab = vi.fn().mockResolvedValueOnce(null).mockResolvedValue(new Blob(['frame']));
    const { loop, deps } = setup({ grab });
    loop.start();
    await flush();
    expect(grab).toHaveBeenCalledTimes(2);
    expect(deps.send).toHaveBeenCalledTimes(1);
    loop.stop();
  });
});
