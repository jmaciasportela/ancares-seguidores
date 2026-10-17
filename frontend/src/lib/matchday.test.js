import { describe, expect, it } from 'vitest';
import { isToday, matchState, timeUntil } from './format.js';

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
});
