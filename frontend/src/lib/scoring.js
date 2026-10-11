/**
 * Lógica del marcador de voleibol (normativa FIVB/RFEVB), sin dependencias.
 *
 * - Punto por jugada: cada jugada da un punto y saca quien la gana.
 * - Un set lo gana quien llega a `points` con 2 de diferencia, sin tope.
 * - Al mejor de N (`best_of`): gana quien llega a ceil(N/2) sets y el set
 *   decisivo se juega a `tiebreak`. Al llegar a 8 en él, cambio de campo.
 * - Sets fijos (`fixed`): se juegan siempre los N sets; puede haber empate.
 *
 * Todas las funciones son puras: reciben un estado y devuelven otro nuevo.
 */

export const PRESETS = [
  { id: 'bo5', label: 'Mejor de 5', detail: 'Sets a 25 · 5º a 15', format: { mode: 'best_of', sets: 5, points: 25, tiebreak: 15 } },
  { id: 'bo3', label: 'Mejor de 3', detail: 'Sets a 25 · 3º a 15', format: { mode: 'best_of', sets: 3, points: 25, tiebreak: 15 } },
  { id: 'bo3_15', label: 'Mejor de 3 a 15', detail: 'Todos los sets a 15', format: { mode: 'best_of', sets: 3, points: 15, tiebreak: 15 } },
  { id: 'fixed3', label: '3 sets fijos', detail: 'Se juegan los 3 · a 25', format: { mode: 'fixed', sets: 3, points: 25, tiebreak: null } },
];

export const DEFAULT_FORMAT = PRESETS[0].format;
const MAX_HISTORY = 800;

export function presetOf(format) {
  const same = (a, b) => a.mode === b.mode && a.sets === b.sets && a.points === b.points && (a.tiebreak ?? null) === (b.tiebreak ?? null);
  return PRESETS.find((p) => same(p.format, format))?.id ?? 'custom';
}

export function describeFormat(f) {
  if (f.mode === 'fixed') return `${f.sets} sets fijos a ${f.points}`;
  const tb = f.tiebreak && f.tiebreak !== f.points ? ` (${f.sets}º a ${f.tiebreak})` : '';
  return `Mejor de ${f.sets} · sets a ${f.points}${tb}`;
}

/** Puntos para ganar el set `index` (0 = primero). */
export function setTarget(format, index) {
  const decisive = format.mode === 'best_of' && format.tiebreak && index === format.sets - 1;
  return decisive ? format.tiebreak : format.points;
}

export function isDecidingSet(format, index) {
  return format.mode === 'best_of' && index === format.sets - 1;
}

/** 'home' | 'away' | null */
export function setWinner(home, away, target) {
  if (Math.max(home, away) < target || Math.abs(home - away) < 2) return null;
  return home > away ? 'home' : 'away';
}

export function setsWon(state) {
  const won = { home: 0, away: 0 };
  for (const s of state.sets) if (s.done) won[s.home > s.away ? 'home' : 'away']++;
  return won;
}

export function setsToWin(format) {
  return format.mode === 'best_of' ? Math.ceil(format.sets / 2) : null;
}

export function isMatchOver(state) {
  const won = setsWon(state);
  if (state.format.mode === 'best_of') return Math.max(won.home, won.away) >= setsToWin(state.format);
  return state.sets.filter((s) => s.done).length >= state.format.sets;
}

/** Ganador del partido: 'home' | 'away' | 'draw' | null (sin terminar o sin sets). */
export function matchWinner(state) {
  const won = setsWon(state);
  if (won.home === won.away) return won.home === 0 ? null : 'draw';
  return won.home > won.away ? 'home' : 'away';
}

export const currentSet = (state) => state.sets[state.sets.length - 1];
export const other = (side) => (side === 'home' ? 'away' : 'home');

export function newMatch({ format = DEFAULT_FORMAT, home, away, match = null, oursSide = null }) {
  const now = Date.now();
  return {
    v: 1,
    format: { ...format },
    home: { ...home },
    away: { ...away },
    match,
    oursSide,
    sets: [{ home: 0, away: 0, done: false }],
    serve: null,
    status: 'playing', // playing | set_over | match_over | finished
    finishedEarly: false,
    swapped: false,
    history: [],
    startedAt: now,
    updatedAt: now,
  };
}

function snapshot(state) {
  const { history, ...rest } = state;
  return structuredClone(rest);
}

function withHistory(state) {
  const history = [...state.history, snapshot(state)];
  if (history.length > MAX_HISTORY) history.shift();
  return { ...state, history, updatedAt: Date.now() };
}

function replaceCurrent(state, set) {
  return { ...state, sets: [...state.sets.slice(0, -1), set] };
}

/** Recalcula si el set actual ha terminado y, con él, el partido. */
function evaluate(state) {
  const index = state.sets.length - 1;
  const cur = currentSet(state);
  const winner = setWinner(cur.home, cur.away, setTarget(state.format, index));
  if (!winner) return { ...replaceCurrent(state, { ...cur, done: false }), status: 'playing' };
  const next = replaceCurrent(state, { ...cur, done: true });
  return { ...next, status: isMatchOver(next) ? 'match_over' : 'set_over' };
}

/** Un toque: punto para `side`, que pasa a sacar. */
export function point(state, side) {
  if (state.status !== 'playing') return state;
  const s = withHistory(state);
  const cur = currentSet(s);
  return evaluate({ ...replaceCurrent(s, { ...cur, [side]: cur[side] + 1 }), serve: side });
}

/** Corrección manual (±1) del set en curso. */
export function adjust(state, side, delta) {
  if (state.status === 'finished') return state;
  const cur = currentSet(state);
  const value = Math.max(0, cur[side] + delta);
  if (value === cur[side]) return state;
  const s = withHistory(state);
  return evaluate(replaceCurrent(s, { ...currentSet(s), [side]: value }));
}

export function nextSet(state) {
  if (state.status !== 'set_over') return state;
  const s = withHistory(state);
  return { ...s, sets: [...s.sets, { home: 0, away: 0, done: false }], status: 'playing', serve: null };
}

/** Termina el partido: por normativa (match_over) o antes de tiempo. */
export function finish(state) {
  if (state.status === 'finished') return state;
  const s = withHistory(state);
  const cur = currentSet(s);
  let sets = s.sets;
  if (!cur.done && cur.home === 0 && cur.away === 0 && sets.length > 1) sets = sets.slice(0, -1);
  const done = { ...s, sets };
  return { ...done, status: 'finished', finishedEarly: !isMatchOver(done) };
}

export function undo(state) {
  if (!state.history.length) return state;
  const history = state.history.slice(0, -1);
  return { ...state.history[state.history.length - 1], history, updatedAt: Date.now() };
}

/** ¿Un punto más para `side` le da el set? */
export function isSetPoint(state, side) {
  if (state.status !== 'playing') return false;
  const cur = currentSet(state);
  const target = setTarget(state.format, state.sets.length - 1);
  return setWinner(cur[side] + 1, cur[other(side)], target) === side;
}

/** ¿Un punto más para `side` le da el partido? */
export function isMatchPoint(state, side) {
  if (!isSetPoint(state, side)) return false;
  const cur = currentSet(state);
  const next = replaceCurrent(state, { ...cur, [side]: cur[side] + 1, done: true });
  return isMatchOver(next) && matchWinner(next) === side;
}

/** Cambio de campo en el set decisivo: cuando el primer equipo llega a 8. */
export function isCourtChange(prev, next) {
  const index = next.sets.length - 1;
  if (prev.sets.length !== next.sets.length || !isDecidingSet(next.format, index)) return false;
  const before = Math.max(currentSet(prev).home, currentSet(prev).away);
  const after = Math.max(currentSet(next).home, currentSet(next).away);
  return before < 8 && after >= 8;
}

/** Datos para publicar: sets ganados y parciales [local, visitante, terminado]. */
export function toResult(state) {
  const sets = state.sets.filter((s) => s.done || s.home || s.away);
  const won = setsWon(state);
  return {
    home_sets: won.home,
    away_sets: won.away,
    partials: sets.map((s) => [s.home, s.away, s.done]),
    finished_early: state.finishedEarly,
  };
}
