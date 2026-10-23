/* Mubazi service worker: the app opens fast and works on a weak connection, and shows phone
 * alerts (web push) when an officer decides a reading.
 *
 *   pages      network first, but after NAV_TIMEOUT_MS (or offline) the saved copy of the app
 *              is shown, so the app always opens; a fresh copy replaces it when it arrives
 *   /assets/   cache first: Vite gives every build's files new names, so a saved file is never
 *              stale; the newest ASSET_LIMIT are kept
 *   icons      saved at install, refreshed in the background
 *   API data   never touched: bills, readings and sign-in always come from the server (the API
 *              is on another origin; on the laptop tunnel it is same-origin, so those paths are
 *              listed and skipped too)
 *
 *   push       { title, body, url } from the server (backend/app/services/push.py): shown as a
 *              notification; tapping it opens or focuses the app at url
 *
 * Bump VERSION when the precache list changes. Registered from src/pwa/registerServiceWorker.ts.
 */
const VERSION = 'v2';
const SHELL = `wasac-shell-${VERSION}`;
const ASSETS = 'wasac-assets';
const ASSET_LIMIT = 80;
const NAV_TIMEOUT_MS = 4000;
const PRECACHE = ['/', '/manifest.webmanifest', '/favicon.svg', '/favicon-32.png', '/icon-192.png', '/icon-512.png'];
const API_PATHS = ['/auth', '/household', '/submit-photo', '/guide-frame', '/confirm-reading', '/calculate-bill',
  '/customers', '/bills/', '/payments/', '/ussd', '/health', '/api/'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n !== SHELL && n !== ASSETS).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'Mubazi', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/favicon-32.png',
      tag: data.tag || 'mubazi',
      renotify: true,
      data: { url: data.url || '/messages' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || '/messages', self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      const open = windows.find((w) => w.url.startsWith(self.location.origin));
      if (open) {
        open.navigate(url);
        return open.focus();
      }
      return self.clients.openWindow(url);
    }),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (API_PATHS.some((p) => url.pathname.startsWith(p))) return;

  if (request.mode === 'navigate') {
    event.respondWith(page(request));
  } else if (url.pathname.startsWith('/assets/')) {
    event.respondWith(asset(request));
  } else if (PRECACHE.includes(url.pathname)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});

/** The app shell: every route is the same index.html, saved under '/'. */
async function page(request) {
  const cache = await caches.open(SHELL);
  const network = fetch(request).then((response) => {
    if (response.ok) cache.put('/', response.clone());
    return response;
  });
  const saved = await cache.match('/');
  if (!saved) return network;
  const timeout = new Promise((resolve) => setTimeout(() => resolve(saved), NAV_TIMEOUT_MS));
  return Promise.race([network.catch(() => saved), timeout]);
}

async function asset(request) {
  const cache = await caches.open(ASSETS);
  const saved = await cache.match(request);
  if (saved) return saved;
  const response = await fetch(request);
  if (response.ok) {
    await cache.put(request, response.clone());
    trim(cache);
  }
  return response;
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(SHELL);
  const saved = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => saved);
  return saved || network;
}

async function trim(cache) {
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - ASSET_LIMIT)).map((key) => cache.delete(key)));
}
