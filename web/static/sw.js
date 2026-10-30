// Daftar service worker – scope "/".
// Caches only the app shell (/200.html, hashed JS/CSS under /_app/immutable/, icons) so the installed app starts fast.
// Never touched: /api (patient data!), /healthz, /metrics, anything but GET, other origins.
// Navigations: only SPA routes are handled (network first, offline fallback /200.html); landing pages
// (/, /ar/, /mentions-legales/, …) go straight to the network and are never cached here.
// scripts/stamp-sw.mjs fills in BUILD and ASSETS after `vite build`: every deploy is a new worker ("Recharger").
const BUILD = '__BUILD__';
const ASSETS = [/*__ASSETS__*/];
const SHELL = 'daftar-shell-' + BUILD;
const SHELL_PAGE = '/200.html';
const ICONS = ['icon-192.png', 'icon-512.png', 'maskable-512.png'].map((f) => '/icons/' + f);
const PASS = ['/api', '/healthz', '/metrics'];
const SPA = ['/app', '/connexion', '/invitation', '/reinitialiser'];
const SPA_WITH_TOKEN = ['/salle/', '/ticket/', '/r/', '/rdv/'];

function isSpaRoute(path) {
  const last = path.replace(/\/$/, '').split('/').pop() || '';
  if (last.includes('.')) return false;
  if (SPA.some((p) => path === p || path.startsWith(p + '/'))) return true;
  return SPA_WITH_TOKEN.some((p) => path.startsWith(p) && path.length > p.length);
}

/** On a practice sub-domain "/" is the booking page of the SPA (on the main domain it is the landing). */
function isPracticeHost(hostname) {
  return /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])\.(?:daftar\.omarfourati\.de|localhost)$/.test(hostname);
}

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll([SHELL_PAGE, ...ASSETS, ...ICONS])));
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name.startsWith('daftar-shell-') && name !== SHELL) await caches.delete(name);
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => { if (event.data === 'skip-waiting') self.skipWaiting(); });

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  if (PASS.some((p) => url.pathname === p || url.pathname.startsWith(p + '/'))) return;
  if (req.mode === 'navigate') {
    const spa = isSpaRoute(url.pathname) || (url.pathname === '/' && isPracticeHost(url.hostname));
    if (spa) event.respondWith(networkFirst(req));
    return; // landing pages: the browser handles them
  }
  if (url.pathname.startsWith('/_app/immutable/') || ICONS.includes(url.pathname)) event.respondWith(cacheFirst(req));
});

async function networkFirst(req) {
  const cache = await caches.open(SHELL);
  try {
    const res = await fetch(req);
    if (res.ok && (res.headers.get('Content-Type') || '').includes('text/html')) await cache.put(SHELL_PAGE, res.clone());
    return res;
  } catch (err) {
    const cached = await cache.match(SHELL_PAGE);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(SHELL);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) await cache.put(req, res.clone());
  return res;
}
