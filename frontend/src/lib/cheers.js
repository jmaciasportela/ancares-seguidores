/**
 * Ánimos: los toques se suman al momento en pantalla y se envían agrupados
 * (cada ~1,2 s o al salir de la app) para no lanzar una petición por toque.
 */
import { writable } from 'svelte/store';
import { deviceId } from './usage.js';

export const KINDS = [
  { id: 'vamos', emoji: '💚', label: '¡Vamos Ancares!' },
  { id: 'aporellas', emoji: '🔥', label: '¡A por ellas!' },
  { id: 'defensa', emoji: '🛡️', label: '¡Defensa!' },
  { id: 'bloqueo', emoji: '🧱', label: '¡Bloqueo!' },
  { id: 'saque', emoji: '🎯', label: '¡Ese saque!' },
];

/** Totales conocidos por partido (los del servidor más los toques pendientes). */
export const cheerTotals = writable({});

const pending = new Map(); // "clave|kind" -> {match, kind, n}
let timer = null;

export const matchKey = (m) => `${m.category_id}|${m.round_no}|${m.home}|${m.away}`;

export function cheer(match, kind) {
  const key = matchKey(match);
  const id = `${key}|${kind}`;
  const item = pending.get(id) || { match, kind, n: 0 };
  item.n += 1;
  pending.set(id, item);
  cheerTotals.update((t) => {
    const cur = t[key] || { total: match.cheers?.total || 0, by_kind: { ...(match.cheers?.by_kind || {}) } };
    return { ...t, [key]: { total: cur.total + 1, by_kind: { ...cur.by_kind, [kind]: (cur.by_kind[kind] || 0) + 1 } } };
  });
  clearTimeout(timer);
  timer = setTimeout(flush, 1200);
}

export function flush() {
  clearTimeout(timer);
  const batch = [...pending.values()];
  pending.clear();
  for (const { match, kind, n } of batch) {
    fetch('/api/cheers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category_id: match.category_id, round_no: match.round_no, home: match.home, away: match.away,
        kind, n, device: deviceId(),
      }),
      keepalive: true,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        // El servidor manda (por si otros también están animando)
        cheerTotals.update((t) => ({ ...t, [matchKey(match)]: { total: data.total, by_kind: data.by_kind } }));
      })
      .catch(() => {});
  }
}

document.addEventListener('visibilitychange', () => document.visibilityState === 'hidden' && flush());
