/**
 * Aviso anónimo de uso: cuántos dispositivos usan la app, si está instalada y con qué frecuencia.
 * El identificador es aleatorio y solo vive en este móvil; no se envían datos personales.
 */
import { isIOS, isStandalone } from './install.js';

const ID_KEY = 'ancares:device';
const LAST_KEY = 'ancares:last-ping';
const EVERY = 30 * 60 * 1000;

function randomId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function platform() {
  if (isIOS) return 'ios';
  if (/android/i.test(navigator.userAgent)) return 'android';
  if (/mobi/i.test(navigator.userAgent)) return 'otro';
  return 'desktop';
}

export function ping() {
  try {
    if (Date.now() - Number(localStorage.getItem(LAST_KEY) || 0) < EVERY) return;
    let id = localStorage.getItem(ID_KEY);
    if (!id) {
      id = randomId();
      localStorage.setItem(ID_KEY, id);
    }
    localStorage.setItem(LAST_KEY, String(Date.now()));
    fetch('/api/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device: id, installed: isStandalone, platform: platform(), version: __APP_VERSION__ }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* sin almacenamiento (modo privado): no se cuenta */
  }
}

export function startUsagePings() {
  ping();
  document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && ping());
}
