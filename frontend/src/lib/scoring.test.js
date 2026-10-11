import { describe, expect, it } from 'vitest';
import {
  PRESETS,
  adjust,
  currentSet,
  describeFormat,
  finish,
  isCourtChange,
  isMatchPoint,
  isSetPoint,
  matchWinner,
  newMatch,
  nextSet,
  point,
  presetOf,
  setTarget,
  setWinner,
  setsWon,
  toResult,
  undo,
} from './scoring.js';

const fmt = (id) => PRESETS.find((p) => p.id === id).format;
const start = (format = fmt('bo5')) => newMatch({ format, home: { name: 'Ancares' }, away: { name: 'Rival' }, oursSide: 'home' });

/** Juega puntos: 'hhaah' = home, home, away, away, home */
function play(state, seq) {
  for (const c of seq) state = point(state, c === 'h' ? 'home' : 'away');
  return state;
}

/** Lleva el set actual hasta h-a respetando el orden (sin cerrarlo antes de tiempo). */
function playSet(state, h, a) {
  const common = Math.min(h, a);
  state = play(state, 'ha'.repeat(common));
  return play(state, (h > a ? 'h' : 'a').repeat(Math.abs(h - a)));
}

describe('fin de set', () => {
  it('25 con 2 de diferencia, sin tope', () => {
    expect(setWinner(25, 23, 25)).toBe('home');
    expect(setWinner(25, 24, 25)).toBe(null);
    expect(setWinner(26, 24, 25)).toBe('home');
    expect(setWinner(29, 31, 25)).toBe('away');
    expect(setWinner(24, 22, 25)).toBe(null);
  });

  it('el set decisivo va a 15', () => {
    expect(setTarget(fmt('bo5'), 4)).toBe(15);
    expect(setTarget(fmt('bo5'), 3)).toBe(25);
    expect(setTarget(fmt('bo3'), 2)).toBe(15);
    expect(setTarget(fmt('fixed3'), 2)).toBe(25);
  });

  it('al cerrar un set propone el siguiente', () => {
    let s = playSet(start(), 25, 23);
    expect(s.status).toBe('set_over');
    expect(currentSet(s)).toEqual({ home: 25, away: 23, done: true });
    expect(point(s, 'home')).toBe(s); // no se suman puntos con el set cerrado
    s = nextSet(s);
    expect(s.status).toBe('playing');
    expect(s.sets).toHaveLength(2);
  });

  it('a 24-24 hay que seguir hasta tener 2 de ventaja', () => {
    let s = playSet(start(), 24, 24);
    s = play(s, 'h');
    expect(s.status).toBe('playing');
    expect(isSetPoint(s, 'home')).toBe(true);
    s = play(s, 'h');
    expect(s.status).toBe('set_over');
  });
});

describe('fin de partido', () => {
  it('al mejor de 3 acaba con 2 sets', () => {
    let s = playSet(start(fmt('bo3')), 25, 20);
    s = playSet(nextSet(s), 25, 18);
    expect(s.status).toBe('match_over');
    expect(matchWinner(s)).toBe('home');
  });

  it('al mejor de 5 el 5º set va a 15 y avisa del cambio de campo a 8', () => {
    let s = start();
    for (const [h, a] of [[25, 20], [20, 25], [25, 22], [23, 25]]) s = nextSet(playSet(s, h, a));
    expect(setsWon(s)).toEqual({ home: 2, away: 2 });
    s = playSet(s, 7, 5);
    const before = s;
    s = play(s, 'h');
    expect(isCourtChange(before, s)).toBe(true);
    expect(isCourtChange(s, play(s, 'a'))).toBe(false);
    s = playSet(s, 6, 3); // 14-8 en total -> punto de partido
    expect(isMatchPoint(s, 'home')).toBe(true);
    s = play(s, 'h');
    expect(s.status).toBe('match_over');
    expect(toResult(s)).toMatchObject({ home_sets: 3, away_sets: 2, finished_early: false });
  });

  it('con sets fijos se juegan todos y puede haber empate', () => {
    let s = playSet(start({ mode: 'fixed', sets: 2, points: 25, tiebreak: null }), 25, 20);
    expect(s.status).toBe('set_over'); // aunque ya vaya ganando, se juega el 2º
    s = playSet(nextSet(s), 20, 25);
    expect(s.status).toBe('match_over');
    expect(matchWinner(s)).toBe('draw');
  });

  it('se puede terminar a mitad de set', () => {
    let s = playSet(start(), 25, 20);
    s = playSet(nextSet(s), 12, 8);
    s = finish(s);
    expect(s.status).toBe('finished');
    expect(toResult(s)).toEqual({
      home_sets: 1,
      away_sets: 0,
      partials: [[25, 20, true], [12, 8, false]],
      finished_early: true,
    });
  });

  it('terminar justo tras empezar un set no deja un 0-0 colgando', () => {
    const s = finish(nextSet(playSet(start(), 25, 20)));
    expect(toResult(s).partials).toEqual([[25, 20, true]]);
  });
});

describe('correcciones', () => {
  it('deshacer quita el último punto, también al cerrar un set', () => {
    let s = playSet(start(), 24, 20);
    s = play(s, 'h');
    expect(s.status).toBe('set_over');
    s = undo(s);
    expect(s.status).toBe('playing');
    expect(currentSet(s)).toEqual({ home: 24, away: 20, done: false });
  });

  it('deshacer el paso a un set nuevo vuelve al set cerrado', () => {
    const closed = playSet(start(), 25, 20);
    const s = undo(nextSet(closed));
    expect(s.sets).toHaveLength(1);
    expect(s.status).toBe('set_over');
  });

  it('el saque pasa a quien gana la jugada', () => {
    let s = play(start(), 'h');
    expect(s.serve).toBe('home');
    s = play(s, 'a');
    expect(s.serve).toBe('away');
  });

  it('corregir puede cerrar o reabrir el set', () => {
    let s = playSet(start(), 24, 20);
    s = adjust(s, 'home', +1);
    expect(s.status).toBe('set_over');
    s = adjust(s, 'home', -1);
    expect(s.status).toBe('playing');
    expect(adjust(start(), 'away', -1).history).toHaveLength(0); // no baja de 0
  });
});

describe('formatos', () => {
  it('reconoce los presets y describe el formato', () => {
    expect(presetOf({ mode: 'best_of', sets: 3, points: 25, tiebreak: 15 })).toBe('bo3');
    expect(presetOf({ mode: 'best_of', sets: 7, points: 21, tiebreak: 15 })).toBe('custom');
    expect(describeFormat(fmt('bo5'))).toBe('Mejor de 5 · sets a 25 (5º a 15)');
    expect(describeFormat(fmt('fixed3'))).toBe('3 sets fijos a 25');
  });
});
