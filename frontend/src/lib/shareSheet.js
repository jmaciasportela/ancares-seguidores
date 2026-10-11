import { writable } from 'svelte/store';

/**
 * Panel de compartir único para toda la app.
 * request = { data (para la imagen, ver shareImage.js), text (para "Solo texto") }
 */
export const shareRequest = writable(null);

export function openShare(data, text) {
  shareRequest.set({ data, text, id: Date.now() });
}

export function closeShare() {
  shareRequest.set(null);
}
