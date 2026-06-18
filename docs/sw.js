const CACHE = "veille-apl-v4";
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./data.json", "./presentation.html"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // data.json : reseau d'abord (frais), cache en secours
  if (url.pathname.endsWith("data.json") || url.pathname.endsWith("digest.json")) {
    e.respondWith(fetch(e.request).then((r) => {
      const cp = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, cp)); return r;
    }).catch(() => caches.match(e.request)));
    return;
  }
  // reste : cache d'abord
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
