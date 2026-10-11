const TZ = 'Europe/Madrid';
const dayFmt = new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short', timeZone: TZ });
const longDayFmt = new Intl.DateTimeFormat('es-ES', { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ });
const timeFmt = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
const keyFmt = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: TZ });

const dayKey = (d) => keyFmt.format(d);

/** "Hoy", "Mañana", "sáb, 17 oct" */
export function formatDay(iso, { long = false } = {}) {
  if (!iso) return 'Fecha por confirmar';
  const d = new Date(iso);
  const today = new Date();
  const tomorrow = new Date(Date.now() + 864e5);
  if (dayKey(d) === dayKey(today)) return 'Hoy';
  if (dayKey(d) === dayKey(tomorrow)) return 'Mañana';
  const s = (long ? longDayFmt : dayFmt).format(d).replace('.', '');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** "Domingo, 18 de octubre" (sin "Hoy"/"Mañana": para imágenes que se ven días después) */
export function formatDateLong(iso) {
  if (!iso) return 'Fecha por confirmar';
  const s = longDayFmt.format(new Date(iso));
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatTime(iso) {
  return iso ? timeFmt.format(new Date(iso)) : '';
}

export function formatWhen(iso) {
  if (!iso) return 'Fecha por confirmar';
  return `${formatDay(iso)} · ${formatTime(iso)}`;
}

/** "hace 5 min", "hace 3 h", "hace 2 días" */
export function timeAgo(iso) {
  if (!iso) return 'nunca';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'ahora mismo';
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  const days = Math.floor(s / 86400);
  return days === 1 ? 'ayer' : `hace ${days} días`;
}

/** Desglose para la cuenta atrás. */
export function countdownParts(iso, now = Date.now()) {
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return null;
  const s = Math.floor(ms / 1000);
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 };
}

export function mapsUrl(venue) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue)}`;
}

/** Nombre corto para pantallas estrechas: quita prefijos de club habituales. */
export function shortTeam(name) {
  if (!name) return '';
  return name.replace(/^(CDF|C\.?D\.?|C\.?V\.?|CV|CD|Club)\s+/i, '').replace(/^Voleibol\s+/i, '');
}

export function initials(name) {
  const words = shortTeam(name).split(/\s+/).filter((w) => /^[\p{L}\d]/u.test(w));
  return (words[0]?.[0] || '?').toUpperCase() + (words[1]?.[0] || '').toUpperCase();
}

/** Color estable por equipo para su avatar. */
export function teamHue(name) {
  let h = 0;
  for (const c of name || '') h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}

/**
 * Resultado a mostrar: el oficial de la FVCL o, si aún no hay, el provisional
 * publicado desde el marcador (marcado con `provisional: true`).
 */
export function scoreOf(m) {
  if (m.played) return { home: m.home_sets, away: m.away_sets, partials: m.partials || [], provisional: false };
  const p = m.provisional;
  if (!p) return null;
  return { home: p.home_sets, away: p.away_sets, partials: p.partials || [], provisional: true, by: p.by, early: p.finished_early };
}

/** "25-20 · 23-25 · 12-8*" (asterisco: set sin terminar) */
export function partialsText(score) {
  return (score?.partials || []).map(([a, b, done = true]) => `${a}-${b}${done ? '' : '*'}`).join(' · ');
}

/** ¿Ganó Ancares? true / false / null (si no es nuestro, no se jugó o hubo empate) */
export function ourOutcome(m, isOurs) {
  const score = scoreOf(m);
  if (!score || !m.is_ours || score.home === score.away) return null;
  const diff = score.home - score.away;
  return isOurs(m.home) ? diff > 0 : diff < 0;
}

export const isOursName = (name) => /ancares/i.test(name || '');
