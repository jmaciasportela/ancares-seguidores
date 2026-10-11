import { formatWhen, partialsText, scoreOf } from './format.js';
import { toast } from './toast.js';

const APP_URL = location.origin;

export function matchText(category, m) {
  const score = scoreOf(m);
  if (score) {
    const partials = partialsText(score);
    return [
      `🏐 ${category} · ${m.round_name}`,
      `${m.home} ${score.home} - ${score.away} ${m.away}`,
      partials ? `(${partials})` : '',
      score.provisional ? '⏳ Resultado provisional, pendiente de la federación' : '',
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

/** Comparte texto con la hoja nativa del móvil; si no existe, abre WhatsApp. */
export async function shareText(text) {
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

/** Texto del resultado del marcador: {title, home, away, homeSets, awaySets, partials, provisional} */
export function scoreText(r) {
  const lines = [
    `🏐 ${r.title}`,
    `${r.home} ${r.homeSets} - ${r.awaySets} ${r.away}`,
    r.partials ? `(${r.partials})` : '',
    r.provisional ? '⏳ Resultado provisional, pendiente de la federación' : '',
    '',
    '¡Vamos Ancares! 💚🖤',
  ];
  return lines.filter((l, i, a) => l || a[i - 1]).join('\n');
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
