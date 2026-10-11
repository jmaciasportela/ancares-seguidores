import { writable } from 'svelte/store';
import { api } from './api.js';

/** Estado de anotador del dispositivo: {scorer, name, admin, can_publish}. */
export const scorer = writable({ scorer: false, name: null, admin: false, can_publish: false, loaded: false });

export async function refreshScorer() {
  try {
    scorer.set({ ...(await api('/api/scorer/me')), loaded: true });
  } catch {
    scorer.update((s) => ({ ...s, loaded: true }));
  }
}

export async function joinScorer(code) {
  const res = await api('/api/scorer/join', { method: 'POST', json: { code } });
  await refreshScorer();
  return res;
}

export async function leaveScorer() {
  await api('/api/scorer/logout', { method: 'POST' });
  await refreshScorer();
}
