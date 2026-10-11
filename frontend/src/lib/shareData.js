/** Datos para la imagen de compartir (ver shareImage.js, que se carga bajo demanda). */
import { formatDateLong, formatTime, isOursName, ourOutcome, scoreOf } from './format.js';

const whenOf = (iso) => (iso ? `${formatDateLong(iso)} · ${formatTime(iso)}` : 'Fecha por confirmar');

/** Partido de liga (resultado oficial/provisional o previa). */
export function dataFromMatch(m, category) {
  const score = scoreOf(m);
  const outcome = ourOutcome(m, isOursName);
  return {
    kind: score ? 'result' : 'preview',
    title: `${category} · ${m.round_name}`,
    when: whenOf(m.starts_at),
    whenDate: formatDateLong(m.starts_at),
    whenTime: m.starts_at ? formatTime(m.starts_at) : '',
    venue: m.venue || '',
    home: { name: m.home, logo: m.home_logo },
    away: { name: m.away, logo: m.away_logo },
    homeSets: score?.home,
    awaySets: score?.away,
    partials: score?.partials || [],
    provisional: !!score?.provisional,
    outcome: outcome === null ? (score && score.home === score.away ? 'draw' : null) : outcome ? 'win' : 'loss',
    weatherMatch: score ? null : m, // la previa lleva el tiempo
  };
}

/** Partido llevado con el marcador (esté o no publicado). */
export function dataFromGame(game, result, title, provisional) {
  const winner = result.home_sets === result.away_sets ? 'draw' : result.home_sets > result.away_sets ? 'home' : 'away';
  let outcome = null;
  if (winner === 'draw') outcome = result.home_sets > 0 ? 'draw' : null; // 0-0: ningún set terminado
  else if (game.oursSide) outcome = winner === game.oursSide ? 'win' : 'loss';
  return {
    kind: 'result',
    title,
    when: whenOf(new Date(game.startedAt).toISOString()),
    venue: '',
    home: game.home,
    away: game.away,
    homeSets: result.home_sets,
    awaySets: result.away_sets,
    partials: result.partials,
    provisional,
    outcome,
  };
}
