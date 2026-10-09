import { writable } from 'svelte/store';

export const toasts = writable([]);
let id = 0;

export function toast(message, kind = 'info', ms = 3200) {
  const t = { id: ++id, message, kind };
  toasts.update((all) => [...all, t]);
  setTimeout(() => toasts.update((all) => all.filter((x) => x.id !== t.id)), ms);
}
