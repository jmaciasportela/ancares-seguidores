import { describe, expect, it } from 'vitest';
import { isToday, matchState, timeUntil, todayMatches } from './format.js';

describe('día de partido (hora de Madrid)', () => {
  // 17 oct 2026, 10:00 en Madrid (08:00 UTC, horario de verano)
  const now = new Date('2026-10-17T08:00:00Z');

  it('isToday usa la fecha de Madrid, no la UTC', () => {
    expect(isToday('2026-10-17T15:00:00Z', now)).toBe(true);
    expect(isToday('2026-10-17T22:30:00Z', now)).toBe(false); // 00:30 del 18 en Madrid
    expect(isToday('2026-10-16T22:30:00Z', now)).toBe(true); // 00:30 del 17 en Madrid
    expect(isToday(null, now)).toBe(false);
  });

  it('estado: antes, en juego (2 h) y terminado', () => {
    const start = '2026-10-17T15:00:00Z';
    expect(matchState(start, Date.parse('2026-10-17T14:00:00Z'))).toBe('upcoming');
    expect(matchState(start, Date.parse('2026-10-17T16:30:00Z'))).toBe('live');
    expect(matchState(start, Date.parse('2026-10-17T17:30:00Z'))).toBe('done');
  });

  it('cuenta atrás legible', () => {
    const start = '2026-10-17T15:00:00Z';
    expect(timeUntil(start, Date.parse('2026-10-17T14:35:00Z'))).toBe('en 25 min');
    expect(timeUntil(start, Date.parse('2026-10-17T13:20:00Z'))).toBe('en 1 h 40 min');
    expect(timeUntil(start, Date.parse('2026-10-17T08:00:00Z'))).toBe('en 7 h');
  });

  it('los partidos de hoy salen por hora, aunque sean de competiciones distintas', () => {
    const m = (id, iso, ours = true) => ({ id, starts_at: iso, is_ours: ours });
    const cats = [
      { name: 'Liga Cadete', next_match: m(1, '2026-10-17T16:00:00Z'), after_match: m(2, '2026-10-18T09:00:00Z') },
      { name: 'Liga Infantil', next_match: m(3, '2026-10-17T09:30:00Z'), after_match: m(4, '2026-10-17T18:00:00Z') },
      { name: 'Torneo', next_match: m(5, '2026-10-17T12:00:00Z'), after_match: null },
      { name: 'Otra', next_match: m(6, '2026-10-17T11:00:00Z', false), after_match: null },
    ];
    const out = todayMatches(cats, now);
    expect(out.map((x) => x.match.id)).toEqual([3, 5, 1, 4]); // mañana (2) y no-Ancares (6) fuera
    expect(out[0].category).toBe('Liga Infantil');
  });
});
