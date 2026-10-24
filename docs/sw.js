// Buildocrat service worker, edition c9a2831362
const V = "bdc-c9a2831362";
const SHELL = ["/", "/buy/", "/stockpile/", "/sell/", "/source/", "/risk-control/", "/help/", "/requests/", "/materials/", "/offline.html",
  "/assets/app.css?v=c9a2831362", "/assets/app.js?v=c9a2831362", "/assets/pwa.js?v=c9a2831362", "/data/catalog.json?v=c9a2831362", "/icons/icon-192.png", "/manifest.webmanifest"];
self.addEventListener("install", ev => { ev.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", ev => { ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("message", ev => {
  if (ev.data && ev.data.t === "warm") caches.open(V).then(c => Promise.all(ev.data.urls.map(u => c.match(u).then(hit => hit || c.add(u).catch(() => {})))));
});
self.addEventListener("fetch", ev => {
  const u = new URL(ev.request.url);
  if (ev.request.method !== "GET" || u.origin !== location.origin) return;
  if (ev.request.mode === "navigate") {
    ev.respondWith(fetch(ev.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(V).then(x => x.put(ev.request, c)); } return r; })
      .catch(() => caches.match(ev.request, { ignoreSearch: true }).then(r => r || caches.match("/offline.html"))));
    return;
  }
  ev.respondWith(caches.match(ev.request).then(r => r || fetch(ev.request).then(res => {
    if (res.ok) { const c = res.clone(); caches.open(V).then(x => x.put(ev.request, c)); } return res; })));
});
