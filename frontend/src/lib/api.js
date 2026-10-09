import { writable } from 'svelte/store';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

/** fetch JSON con mensajes de error legibles. */
export async function api(path, { method = 'GET', json, form } = {}) {
  const opts = { method, credentials: 'same-origin', headers: {} };
  if (json !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(json);
  } else if (form) {
    opts.body = form;
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new ApiError('Sin conexión. Inténtalo de nuevo.', 0);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join('. ');
    throw new ApiError(msg || `Error ${res.status}`, res.status);
  }
  return data;
}

// --- Datos públicos: se pintan al instante desde localStorage y se refrescan en segundo plano ---

const stores = new Map();
const KEY = (p) => 'ancares:' + p;

function readCache(path) {
  try {
    return JSON.parse(localStorage.getItem(KEY(path)));
  } catch {
    return null;
  }
}

function writeCache(path, data) {
  try {
    localStorage.setItem(KEY(path), JSON.stringify(data));
  } catch {
    /* almacenamiento lleno o bloqueado: no pasa nada */
  }
}

/**
 * Store {data, loading, error} para un GET público.
 * Devuelve datos cacheados inmediatamente y luego los frescos.
 */
export function resource(path) {
  if (stores.has(path)) return stores.get(path);
  const cached = readCache(path);
  const store = writable({ data: cached, loading: true, error: null });
  let inflight = null;

  async function refresh() {
    if (inflight) return inflight;
    store.update((s) => ({ ...s, loading: true }));
    inflight = api(path)
      .then((data) => {
        writeCache(path, data);
        store.set({ data, loading: false, error: null });
      })
      .catch((err) => store.update((s) => ({ ...s, loading: false, error: err })))
      .finally(() => (inflight = null));
    return inflight;
  }

  refresh();
  const res = { subscribe: store.subscribe, refresh };
  stores.set(path, res);
  return res;
}

/** Al volver a la app (p. ej. desde WhatsApp) se refresca lo que haya en pantalla. */
let lastRefresh = Date.now();
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && Date.now() - lastRefresh > 60_000) {
    lastRefresh = Date.now();
    for (const s of stores.values()) s.refresh();
  }
});
