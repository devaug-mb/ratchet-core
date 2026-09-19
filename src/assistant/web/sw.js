// Service worker mínimo: da instalabilidad (PWA) y un shell offline, SIN
// arriesgar páginas viejas. Estrategia network-first para la navegación: usa la
// red cuando hay (siempre fresco) y solo tira del caché si no hay conexión.
const CACHE = "asistente-shell-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((c) => c.add("/")));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // no tocar POST/SSE (el chat)
  if (req.mode !== "navigate") return; // solo el shell; la API va directa a red
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put("/", copy));
        return res;
      })
      .catch(() => caches.match("/"))
  );
});
