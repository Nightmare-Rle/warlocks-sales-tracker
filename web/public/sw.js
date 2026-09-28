/* Warlocks Sales Tracker - service worker (offline cache) */
const CACHE = 'warlocks-sales-v1';
const ASSETS = [
  'index.html',
  'verify.html',
  'manifest.json',
  'icon.svg',
  'icon-192.png',
  'icon-512.png',
  'css/style.css',
  'js/app.js',
  'js/verify.js'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Network-first for the API, cache-first for static assets.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  if (url.pathname.includes('/api/')) {
    e.respondWith(fetch(e.request).catch(() => {
      return e.request.method === 'GET'
        ? caches.match(e.request)
        : new Response(JSON.stringify({ error: 'offline' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
    }));
    return;
  }

  e.respondWith(
    caches.match(e.request).then(
      (hit) => hit || fetch(e.request).then((res) => {
        const clone = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, clone));
        return res;
      })
    )
  );
});