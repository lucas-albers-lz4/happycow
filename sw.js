// Happy Cow service worker — offline app shell, fresh data.
// Data (happy_hour_data.json) is network-first so happy hour deals never
// go stale; the shell (index/js/css) uses network-first so deploys take
// effect without a hard-reload.
//
// CACHE-bump-on-shell-change: increment CACHE (e.g. happycow-v2 → happycow-v3)
// whenever you add, remove, or rename a file in SHELL. The activate handler
// deletes all old caches so users immediately get the new shell.
const CACHE = 'happycow-v5';
const SHELL = [
  './',
  './index.html',
  './assets/css/style.css',
  './assets/js/hours.js',
  './assets/js/format.js',
  './assets/js/render.js',
  './assets/js/app.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // Network-first for JSON data — deals must stay current; cached copy as offline fallback.
  if (url.pathname.endsWith('.json')) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Network-first for navigation (HTML) and shell assets (JS/CSS) so deploys
  // take effect without a hard-reload. Falls back to cache when offline.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
