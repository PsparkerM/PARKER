// P.A.R.K.E.R. Service Worker — PWA shell cache
const CACHE = 'parker-v1';

const SHELL = [
  '/',
  '/static/icon-192.png',
  '/static/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Never intercept: API, webhook, external resources
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/webhook/') ||
    url.pathname.startsWith('/admin') ||
    url.origin !== self.location.origin
  ) return;

  if (e.request.destination === 'document') {
    // Network-first for HTML — always fresh app
    e.respondWith(
      fetch(e.request)
        .catch(() => caches.match('/'))
    );
    return;
  }

  // Cache-first for static assets
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
      if (res && res.status === 200 && e.request.method === 'GET') {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return res;
    }))
  );
});
