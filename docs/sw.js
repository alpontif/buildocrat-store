// Buildocrat service worker, edition 19456c55c1
const V = "bdc-19456c55c1";
const SHELL = ["/", "/buy/", "/stockpile/", "/sell/", "/source/", "/risk-control/", "/help/", "/requests/",
  "/assets/app.css?v=19456c55c1", "/assets/app.js?v=19456c55c1", "/data/catalog.json?v=19456c55c1", "/icons/icon-192.png"];
self.addEventListener("install", ev => { ev.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", ev => { ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", ev => {
  const u = new URL(ev.request.url);
  if (ev.request.method !== "GET" || u.origin !== location.origin) return;
  if (ev.request.mode === "navigate") {
    ev.respondWith(fetch(ev.request).then(r => { const c = r.clone(); caches.open(V).then(x => x.put(ev.request, c)); return r; })
      .catch(() => caches.match(ev.request).then(r => r || caches.match("/"))));
    return;
  }
  ev.respondWith(caches.match(ev.request).then(r => r || fetch(ev.request).then(res => {
    if (res.ok) { const c = res.clone(); caches.open(V).then(x => x.put(ev.request, c)); } return res; })));
});
