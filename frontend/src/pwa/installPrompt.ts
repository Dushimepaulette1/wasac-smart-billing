/**
 * @file installPrompt.ts
 * @description "Install the app": Android browsers fire `beforeinstallprompt`
 * when the app can be installed; we keep that event and show our own button.
 * iPhone Safari has no such event, so there we show how to add it by hand.
 * Nothing is shown once the app runs installed (standalone).
 */

import { useCallback, useEffect, useState } from 'react';

/** Chrome's event (not in the TypeScript DOM types). */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let deferred: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

// Listen from the first moment: the event can fire before any component mounts.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault(); // our button instead of the browser's mini-bar
    deferred = event as BeforeInstallPromptEvent;
    notify();
  });
  window.addEventListener('appinstalled', () => {
    deferred = null;
    notify();
  });
}

export function isStandalone(): boolean {
  const nav = navigator as Navigator & { standalone?: boolean };
  return window.matchMedia?.('(display-mode: standalone)').matches === true || nav.standalone === true;
}

export function isIosSafari(userAgent: string = navigator.userAgent): boolean {
  return /iphone|ipad|ipod/i.test(userAgent) && !/crios|fxios|edgios/i.test(userAgent);
}

export interface InstallPrompt {
  /** The browser can install the app now: show the button. */
  canInstall: boolean;
  /** iPhone: show the "Share, then Add to Home Screen" hint instead. */
  showIosHint: boolean;
  install: () => Promise<void>;
}

export function useInstallPrompt(): InstallPrompt {
  const [, setTick] = useState(0);
  useEffect(() => {
    const update = () => setTick((n) => n + 1);
    listeners.add(update);
    return () => {
      listeners.delete(update);
    };
  }, []);

  const install = useCallback(async () => {
    const event = deferred;
    if (!event) return;
    deferred = null; // the event can be used once
    notify();
    await event.prompt();
    await event.userChoice.catch(() => undefined);
  }, []);

  const standalone = isStandalone();
  return {
    canInstall: !standalone && deferred !== null,
    showIosHint: !standalone && deferred === null && isIosSafari(),
    install,
  };
}

/** For tests: forget a kept event. */
export function resetInstallPrompt(): void {
  deferred = null;
  notify();
}
