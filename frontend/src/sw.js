/* Service worker: app shell precacheada, API con red primero y destino de "Compartir". */
import { clientsClaim } from 'workbox-core';
import { ExpirationPlugin } from 'workbox-expiration';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst } from 'workbox-strategies';

const SHARE_CACHE = 'shared-files';

self.skipWaiting();
clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// SPA: cualquier navegación devuelve index.html (salvo la API)
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//, /^\/share-target/] }));

// Datos públicos: red primero (datos frescos) y caché si no hay cobertura
registerRoute(
  ({ url, request }) => request.method === 'GET' && /^\/api\/(home|categories)/.test(url.pathname),
  new NetworkFirst({
    cacheName: 'api',
    networkTimeoutSeconds: 4,
    plugins: [new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 30 })],
  }),
);

// Imágenes estáticas no precacheadas
registerRoute(
  ({ request, url }) => request.destination === 'image' && url.origin === self.location.origin,
  new CacheFirst({ cacheName: 'img', plugins: [new ExpirationPlugin({ maxEntries: 40 })] }),
);

// Web Share Target: guardamos los ficheros y abrimos el panel de admin, que los sube con su sesión
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'POST' || url.pathname !== '/share-target') return;
  event.respondWith(
    (async () => {
      const form = await event.request.formData();
      const files = form.getAll('files').filter((f) => f && typeof f !== 'string');
      const cache = await caches.open(SHARE_CACHE);
      for (const key of await cache.keys()) await cache.delete(key);
      await Promise.all(
        files.map((file, i) =>
          cache.put(
            `/shared/${i}`,
            new Response(file, { headers: { 'X-Filename': encodeURIComponent(file.name || `fichero-${i}.xls`) } }),
          ),
        ),
      );
      return Response.redirect(`/#/admin?shared=${files.length}`, 303);
    })(),
  );
});
