import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { toast } from './lib/toast.js';

const VERSION = __APP_VERSION__;
const app = mount(App, { target: document.getElementById('app') });

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  const startedAt = performance.now();
  const hadController = !!navigator.serviceWorker.controller;
  let pendingReload = false;
  let reloading = false;

  const reload = () => {
    if (reloading) return;
    reloading = true;
    location.reload();
  };

  // El SW nuevo toma el control solo (skipWaiting + clientsClaim). Si la app
  // acaba de abrirse se recarga ya; si no, al volver a ella, para no perder
  // lo que se esté escribiendo.
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController) return; // primera instalación: nada que actualizar
    if (performance.now() - startedAt < 10_000) reload();
    else pendingReload = true;
  });

  addEventListener('load', async () => {
    const reg = await navigator.serviceWorker.register('/sw.js');
    // Las PWA instaladas (sobre todo en iOS) apenas buscan versiones nuevas solas
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState !== 'visible') return;
      if (pendingReload) reload();
      else reg.update().catch(() => {});
    });
    setInterval(() => reg.update().catch(() => {}), 60 * 60 * 1000);
  });
}

// Aviso tras una actualización
try {
  const previous = localStorage.getItem('ancares:version');
  localStorage.setItem('ancares:version', VERSION);
  if (previous && previous !== VERSION) {
    setTimeout(() => toast(`App actualizada a la versión ${VERSION}`, 'ok', 4000), 1200);
  }
} catch {
  /* sin almacenamiento: sin aviso */
}

export default app;
