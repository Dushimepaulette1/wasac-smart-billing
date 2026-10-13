/**
 * @file guidanceLoop.ts
 * @description Live framing checks while the camera is open.
 *
 * One request at a time: the next frame is only sent after the previous
 * answer arrives. Pauses while the tab is hidden, gives up after a time limit
 * or a network error (the shutter button always works), and reports "ready"
 * after enough OK answers in a row so the screen can take the photo itself.
 */

import type { GuideFrameResponse } from '../api/types';

export const LIVE_CHECK_LIMIT_MS = 30_000;
export const OK_IN_A_ROW = 2;
/** Breathing room between requests on slow phones and networks. */
const GAP_MS = 250;

export type LoopEnd = 'timeLimit' | 'error' | 'unavailable';

export interface LoopDeps {
  /** A small JPEG of the current camera frame, or null if there is no frame yet. */
  grab: () => Promise<Blob | null>;
  send: (frame: Blob) => Promise<GuideFrameResponse>;
  onResult: (result: GuideFrameResponse) => void;
  /** OK_IN_A_ROW good frames: take the photo. The loop has stopped. */
  onReady: () => void;
  /** Live checks are over for this camera session; the shutter still works. */
  onEnd: (reason: LoopEnd) => void;
  limitMs?: number;
  now?: () => number;
  wait?: (ms: number) => Promise<void>;
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export class GuidanceLoop {
  private readonly deps: Required<LoopDeps>;
  private running = false;
  private paused = false;
  private busy = false;
  private okStreak = 0;
  private startedAt = 0;

  constructor(deps: LoopDeps) {
    this.deps = { limitMs: LIVE_CHECK_LIMIT_MS, now: Date.now, wait: sleep, ...deps };
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.paused = false;
    this.okStreak = 0;
    this.startedAt = this.deps.now();
    void this.run();
  }

  stop(): void {
    this.running = false;
  }

  /** The tab was hidden: stop sending until it is visible again. */
  pause(): void {
    this.paused = true;
  }

  resume(): void {
    if (!this.running || !this.paused) return;
    this.paused = false;
    void this.run();
  }

  get active(): boolean {
    return this.running;
  }

  private finish(reason: LoopEnd): void {
    this.running = false;
    this.deps.onEnd(reason);
  }

  private async run(): Promise<void> {
    if (this.busy) return; // a request is already in flight; it continues the loop
    this.busy = true;
    try {
      while (this.running && !this.paused) {
        if (this.deps.now() - this.startedAt >= this.deps.limitMs) {
          this.finish('timeLimit');
          return;
        }
        const frame = await this.deps.grab();
        if (!this.running || this.paused) return;
        if (!frame) {
          await this.deps.wait(GAP_MS);
          continue;
        }
        let result: GuideFrameResponse;
        try {
          result = await this.deps.send(frame);
        } catch {
          if (this.running) this.finish('error');
          return;
        }
        if (!this.running) return;
        if (!result.available) {
          this.finish('unavailable');
          return;
        }
        this.deps.onResult(result);
        this.okStreak = result.guidance[0] === 'OK' ? this.okStreak + 1 : 0;
        if (this.okStreak >= OK_IN_A_ROW) {
          this.running = false;
          this.deps.onReady();
          return;
        }
        await this.deps.wait(GAP_MS);
      }
    } finally {
      this.busy = false;
    }
  }
}
