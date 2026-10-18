import { describe, expect, it, vi } from 'vitest';

// api.js toca `document` al cargarse: aquí solo se prueba la lógica pura
vi.mock('./api.js', () => ({ api: vi.fn() }));
import { api } from './api.js';
import { createEmitter, flipFor, fromLive, hasProgress, liveEvents, liveScoreText, toLive } from './live.js';
import * as S from './scoring.js';

const FMT = { mode: 'best_of', sets: 3, points: 25, tiebreak: 15 };
const st = (sets, extra = {}) => ({ format: FMT, sets, serve: 'home', status: 'playing', finished_early: false, ...extra });

function linked({ home = 'CDF Voleibol Ancares UVa', away = 'VCV Castilla', oursSide = 'home' } = {}) {
  return S.newMatch({ format: FMT, home: { name: home }, away: { name: away }, oursSide, match: { home, away } });
}

describe('toLive / fromLive', () => {
  it('emite el estado compacto y se reconstruye igual', () => {
    let g = linked();
    g = S.point(S.point(S.point(g, 'home'), 'away'), 'home');
    const live = toLive(g);
    expect(live).toEqual({ format: FMT, sets: [[2, 1, false]], serve: 'home', status: 'playing', finished_early: false });
    const back = fromLive(live, { home: g.home, away: g.away });
    expect(S.currentSet(back)).toEqual({ home: 2, away: 1, done: false });
    expect(S.isSetPoint(back, 'home')).toBe(false);
  });

  it('respeta local y visitante del partido de liga aunque Ancares cambiara de lado', () => {
    // Marcador libre con Ancares como local, asignado a un partido donde Ancares es visitante
    let g = S.newMatch({ format: FMT, home: { name: 'Ancares' }, away: { name: 'Rival' }, oursSide: 'home' });
    g = { ...S.point(g, 'home'), match: { home: 'VCV Castilla', away: 'CDF Voleibol Ancares UVa' } };
    expect(flipFor(g)).toBe(true);
    expect(toLive(g).sets).toEqual([[0, 1, false]]);
    expect(toLive(g).serve).toBe('away');
    expect(flipFor(linked())).toBe(false);
  });

  it('sabe si hay partido empezado y lo resume', () => {
    expect(hasProgress(st([[0, 0, false]]))).toBe(false);
    expect(hasProgress(st([[3, 1, false]]))).toBe(true);
    expect(hasProgress(st([[25, 20, true]], { status: 'finished' }))).toBe(false);
    expect(liveScoreText(st([[25, 20, true], [18, 15, false]]))).toBe('Set 2: 18-15 · sets 1-0');
    expect(liveScoreText(st([[4, 2, false]]))).toBe('Set 1: 4-2');
    expect(liveScoreText(st([[25, 20, true], [25, 15, true]], { status: 'match_over' }))).toBe('2-0');
  });
});

describe('liveEvents', () => {
  it('detecta punto, deshacer y fin de set', () => {
    expect(liveEvents(st([[3, 1, false]]), st([[4, 1, false]]))).toEqual([{ type: 'point', side: 'home' }]);
    expect(liveEvents(st([[3, 1, false]]), st([[3, 2, false]]))).toEqual([{ type: 'point', side: 'away' }]);
    expect(liveEvents(st([[3, 1, false]]), st([[2, 1, false]]))).toEqual([{ type: 'undo' }]);
    expect(liveEvents(st([[24, 20, false]]), st([[25, 20, true]], { status: 'set_over' }))).toEqual([
      { type: 'point', side: 'home' },
      { type: 'set', side: 'home' },
    ]);
    expect(liveEvents(st([[25, 20, true]], { status: 'set_over' }), st([[25, 20, true], [0, 0, false]]))).toEqual([
      { type: 'newset', no: 2 },
    ]);
    expect(liveEvents(null, st([[1, 0, false]]))).toEqual([]);
  });

  it('avisa del cambio de campo en el set decisivo y del final', () => {
    const before = st([[25, 20, true], [20, 25, true], [7, 5, false]]);
    const after = st([[25, 20, true], [20, 25, true], [8, 5, false]]);
    expect(liveEvents(before, after)).toContainEqual({ type: 'court' });
    const end = liveEvents(
      st([[25, 20, true], [20, 25, true], [14, 10, false]]),
      st([[25, 20, true], [20, 25, true], [15, 10, true]], { status: 'match_over' }),
    );
    expect(end).toContainEqual({ type: 'end', side: 'home' });
  });
});

describe('createEmitter', () => {
  const posts = () => api.mock.calls.filter(([path, opts]) => opts?.method === 'POST' && !path.endsWith('/claim'));

  it('el 0-0 inicial se manda con un número mayor que el del servidor', async () => {
    vi.useFakeTimers();
    api.mockReset();
    let answerClaim;
    api.mockImplementation((path, opts) =>
      path.endsWith('/claim')
        ? new Promise((resolve) => (answerClaim = resolve))
        : Promise.resolve({ ok: true, seq: opts.json.seq, viewers: 3 }),
    );
    const infos = [];
    const e = createEmitter('1-1-abcdef12', (i) => infos.push(i));
    e.send(st([[0, 0, false]], { serve: null })); // «Empezar»: el 0-0 sale antes de que conteste el reclamo
    await vi.advanceTimersByTimeAsync(400);
    expect(posts()).toHaveLength(0);
    answerClaim({ seq: 0, viewers: 3 });
    await vi.advanceTimersByTimeAsync(10);
    expect(posts()).toHaveLength(1);
    expect(posts()[0][1].json.seq).toBe(1); // antes salía con 0 y el servidor lo descartaba
    e.send(st([[1, 0, false]]));
    await vi.advanceTimersByTimeAsync(300);
    expect(posts().at(-1)[1].json.seq).toBe(2);
    expect(infos.at(-1)).toMatchObject({ status: 'ok', viewers: 3 });
    e.dispose();
    vi.useRealTimers();
  });

  it('si el servidor iba por delante, se reenvía con un número mayor', async () => {
    vi.useFakeTimers();
    api.mockReset();
    let server = 40;
    api.mockImplementation((path, opts) => {
      if (path.endsWith('/claim')) return Promise.reject(Object.assign(new Error('Sin conexión'), { status: 0 }));
      server = Math.max(server, opts.json.seq);
      return Promise.resolve({ ok: true, seq: server, viewers: 0 });
    });
    const e = createEmitter('1-1-abcdef12');
    e.send(st([[5, 3, false]]));
    await vi.advanceTimersByTimeAsync(2500);
    expect(posts().at(-1)[1].json.seq).toBe(41);
    e.dispose();
    vi.useRealTimers();
  });
});
