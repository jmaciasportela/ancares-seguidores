import { writable } from 'svelte/store';

export const isStandalone =
  matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

const ua = navigator.userAgent;
export const isIOS = /iphone|ipad|ipod/i.test(ua) || (ua.includes('Mac') && 'ontouchend' in document);

/** Evento beforeinstallprompt guardado (Chrome/Android/Edge). */
export const installPrompt = writable(null);

addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  installPrompt.set(e);
});

addEventListener('appinstalled', () => installPrompt.set(null));

export async function promptInstall(evt) {
  if (!evt) return false;
  evt.prompt();
  const { outcome } = await evt.userChoice;
  installPrompt.set(null);
  return outcome === 'accepted';
}

const DISMISS_KEY = 'ancares:install-dismissed';

export function installDismissed() {
  try {
    const t = Number(localStorage.getItem(DISMISS_KEY) || 0);
    return Date.now() - t < 7 * 864e5; // vuelve a ofrecerse a la semana
  } catch {
    return false;
  }
}

export function dismissInstall() {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch {
    /* ignorado */
  }
}
