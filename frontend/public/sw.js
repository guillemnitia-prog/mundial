// Service worker mínimo de la PWA. La caché de assets es básica; el push real llega en la Fase 13.
const CACHE = "mundial-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/manifest.webmanifest", "/icon.svg"])));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

// Network-first para navegación; cae a caché si no hay red.
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  event.respondWith(fetch(request).catch(() => caches.match(request).then((r) => r || caches.match("/"))));
});

// Web Push (Fase 13): muestra la notificación recibida.
self.addEventListener("push", (event) => {
  if (!event.data) return;
  let data = {};
  try {
    data = event.data.json();
  } catch {
    data = { title: "Mundial", body: event.data.text() };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Mundial", {
      body: data.body || "",
      icon: "/icon.svg",
      badge: "/icon.svg",
      data: data.url || "/",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data || "/"));
});
