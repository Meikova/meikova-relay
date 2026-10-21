// Meikova Relay PWA Service Worker (v1.0.23)
const CACHE_NAME = 'meikova-relay-cache-v1.0.42';
const APP_SHELL = [
  '/',
  '/index.html',
  '/manifest.json',
  '/favicon.svg',
  '/css/tokens.css',
  '/css/style.css',
  '/js/app.js',
  '/js/sync_engine.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL).catch((err) => {
        console.warn('[SW] Cache addAll warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Không cache WebSocket, API REST, hoặc Google Auth
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/ws') ||
    url.hostname.includes('googleapis.com') ||
    url.hostname.includes('accounts.google.com') ||
    event.request.method !== 'GET'
  ) {
    return;
  }

  // Chiến lược Stale-While-Revalidate cho App Shell và static assets
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(event.request).then((cachedResponse) => {
        const fetchPromise = fetch(event.request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        }).catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      });
    })
  );
});
