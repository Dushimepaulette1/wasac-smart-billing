import { GuidanceLoop, type LoopDeps } from '../../src/household/guidanceLoop';
import { makeGuideFrame } from '../support/fixtures';
import type { GuideFrameResponse } from '../../src/api/types';

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
  it('when running, should send one frame at a time, the next only after the answer', async () => {
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

  it('when two OK answers come in a row, should be ready and stop', async () => {
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

  it('when framed answers are not in a row, should not be ready yet', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    await answer(makeGuideFrame(['OK']));
    await answer(makeGuideFrame(['TOO_FAR']));
    await answer(makeGuideFrame(['OK']));
    expect(deps.onReady).not.toHaveBeenCalled();
    await answer(makeGuideFrame(['OK']));
    expect(deps.onReady).toHaveBeenCalledTimes(1);
  });

  it('when the window is framed with a lighting hint, should count it towards the automatic photo', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    await answer(makeGuideFrame(['GLARE']));
    await answer(makeGuideFrame(['TOO_DARK']));
    expect(deps.onReady).toHaveBeenCalledTimes(1);
  });

  it('when the time limit passes, should stop', async () => {
    const { loop, deps, answer, advance } = setup({ limitMs: 30_000 });
    loop.start();
    await flush();
    advance(30_000);
    await answer(makeGuideFrame(['TOO_FAR']));
    expect(deps.onEnd).toHaveBeenCalledWith('timeLimit');
    expect(deps.send).toHaveBeenCalledTimes(1);
  });

  it('when the tab is hidden, should pause, and continue when it is shown', async () => {
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

  it('when the network fails, should give up quietly', async () => {
    const { loop, deps, pending } = setup();
    loop.start();
    await flush();
    pending.shift()?.reject(new Error('offline'));
    await flush();
    expect(deps.onEnd).toHaveBeenCalledWith('error');
    expect(loop.active).toBe(false);
  });

  it('when the backend has no window detector, should give up', async () => {
    const { loop, deps, answer } = setup();
    loop.start();
    await flush();
    await answer({ ...makeGuideFrame(['OK']), available: false });
    expect(deps.onEnd).toHaveBeenCalledWith('unavailable');
    expect(deps.onResult).not.toHaveBeenCalled();
  });

  it('when no camera frame is ready, should wait before sending', async () => {
    const grab = vi.fn().mockResolvedValueOnce(null).mockResolvedValue(new Blob(['frame']));
    const { loop, deps } = setup({ grab });
    loop.start();
    await flush();
    expect(grab).toHaveBeenCalledTimes(2);
    expect(deps.send).toHaveBeenCalledTimes(1);
    loop.stop();
  });
});
