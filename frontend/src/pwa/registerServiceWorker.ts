/**
 * @file registerServiceWorker.ts
 * @description Register public/sw.js (offline app shell, fast start on weak
 * data). Production builds only: in development a cached app would hide edits.
 */

export function registerServiceWorker(
  isProduction: boolean = import.meta.env.PROD,
  nav: Navigator = navigator,
): boolean {
  if (!isProduction || !('serviceWorker' in nav)) return false;
  window.addEventListener('load', () => {
    nav.serviceWorker.register('/sw.js').catch(() => {
      // No service worker (private mode, old browser): the app still works online.
    });
  });
  return true;
}
