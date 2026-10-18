import { writable } from 'svelte/store';

export class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.status = status;
    this.data = data; // detalle estructurado, si el servidor lo manda (p. ej. quién retransmite)
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
  // Sincronizar, subir Excel, publicar o borrar resultados... cambia los datos públicos:
  // lo que haya en memoria se vuelve a pedir en cuanto se vuelva a mirar
  if (res.ok && method !== 'GET' && /^\/api\/(admin|scoring)\//.test(path)) invalidateAll();
  if (!res.ok) {
    let msg = data?.detail;
    const extra = msg && typeof msg === 'object' && !Array.isArray(msg) ? msg : null;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join('. ');
    else if (extra) msg = extra.message;
    throw new ApiError(msg || `Error ${res.status}`, res.status, extra);
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
  const existing = stores.get(path);
  if (existing) {
    // Al volver a una página se comprueba si hay datos nuevos (sin esperar a recargar la app)
    existing.revalidate();
    return existing;
  }
  const cached = readCache(path);
  const store = writable({ data: cached, loading: true, error: null });
  let inflight = null;
  let fetchedAt = 0;
  let stale = false;

  async function refresh() {
    if (inflight) return inflight;
    fetchedAt = Date.now();
    stale = false;
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
  const res = {
    subscribe: store.subscribe,
    refresh,
    /** Pide los datos otra vez si están marcados como viejos o hace más de 15 s que se pidieron. */
    revalidate: () => (stale || Date.now() - fetchedAt > REVALIDATE_MS) && refresh(),
    invalidate: () => (stale = true),
  };
  stores.set(path, res);
  return res;
}

const REVALIDATE_MS = 15_000;

/** Marca como viejos todos los datos en memoria: se vuelven a pedir al mirarlos. */
export function invalidateAll() {
  for (const s of stores.values()) s.invalidate();
}

/** Al volver a la app (p. ej. desde WhatsApp) se refresca lo que haya en pantalla. */
let lastRefresh = Date.now();
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && Date.now() - lastRefresh > 60_000) {
    lastRefresh = Date.now();
    for (const s of stores.values()) s.refresh();
  }
});
