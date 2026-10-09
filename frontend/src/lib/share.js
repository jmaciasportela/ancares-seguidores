import { formatWhen, partialsText } from './format.js';
import { toast } from './toast.js';

const APP_URL = location.origin;

function matchText(category, m) {
  if (m.played) {
    const partials = partialsText(m);
    return [
      `🏐 ${category} · ${m.round_name}`,
      `${m.home} ${m.home_sets} - ${m.away_sets} ${m.away}`,
      partials ? `(${partials})` : '',
      '',
      '¡Vamos Ancares! 💚🖤',
    ]
      .filter((l, i, a) => l || a[i - 1])
      .join('\n');
  }
  return [
    `🏐 ${category} · ${m.round_name}`,
    `${m.home} vs ${m.away}`,
    `📅 ${formatWhen(m.starts_at)}`,
    m.venue ? `📍 ${m.venue}` : '',
    '',
    '¡Vamos Ancares! 💚🖤',
  ]
    .filter((l, i, a) => l || a[i - 1])
    .join('\n');
}

/** Comparte con la hoja nativa del móvil; si no existe, abre WhatsApp. */
export async function shareMatch(category, m) {
  const text = matchText(category, m);
  if (navigator.share) {
    try {
      await navigator.share({ title: 'Ancares Seguidores', text, url: APP_URL });
      return;
    } catch (err) {
      if (err?.name === 'AbortError') return;
    }
  }
  const wa = `https://wa.me/?text=${encodeURIComponent(`${text}\n\n${APP_URL}`)}`;
  const win = window.open(wa, '_blank', 'noopener');
  if (!win) {
    try {
      await navigator.clipboard.writeText(`${text}\n\n${APP_URL}`);
      toast('Copiado al portapapeles', 'ok');
    } catch {
      toast('No se pudo compartir', 'error');
    }
  }
}

export async function shareApp() {
  const data = { title: 'Ancares Seguidores', text: 'Sigue la clasificación y los resultados del Voleibol Ancares 🏐', url: APP_URL };
  if (navigator.share) {
    try {
      await navigator.share(data);
      return;
    } catch (err) {
      if (err?.name === 'AbortError') return;
    }
  }
  try {
    await navigator.clipboard.writeText(APP_URL);
    toast('Enlace copiado', 'ok');
  } catch {
    window.open(`https://wa.me/?text=${encodeURIComponent(`${data.text}\n${APP_URL}`)}`, '_blank', 'noopener');
  }
}
