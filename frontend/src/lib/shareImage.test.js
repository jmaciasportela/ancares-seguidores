import { describe, expect, it } from 'vitest';
import { dataFromGame, dataFromMatch } from './shareData.js';
import { fileName, fitFont, headline, wrapLines } from './shareImage.js';

/** Contexto de medida simulado: cada carácter mide medio tamaño de fuente. */
function fakeCtx() {
  return {
    font: '700 40px x',
    measureText(t) {
      const size = Number(/(\d+)px/.exec(this.font)[1]);
      return { width: t.length * size * 0.5 };
    },
  };
}

const OURS = 'CDF Voleibol Ancares UVa';
const match = (over = {}) => ({
  id: 1, round_name: 'Jornada 3', home: OURS, away: 'VCV Castilla', home_logo: null, away_logo: '/logos/6.webp',
  starts_at: '2026-10-18T08:30:00+00:00', venue: 'Fuente la Mora', played: false, provisional: null, is_ours: true,
  home_sets: null, away_sets: null, partials: [], ...over,
});

describe('titular desde el punto de vista de Ancares', () => {
  it('victoria, derrota y empate, en casa o fuera', () => {
    const win = dataFromMatch(match({ played: true, home_sets: 3, away_sets: 1, partials: [[25, 20]] }), 'Infantil');
    expect(headline(win)).toBe('¡VICTORIA!');
    const awayLoss = dataFromMatch(match({ home: 'VCV Castilla', away: OURS, played: true, home_sets: 3, away_sets: 2 }), 'Infantil');
    expect(headline(awayLoss)).toBe('DERROTA');
    const awayWin = dataFromMatch(match({ home: 'VCV Castilla', away: OURS, played: true, home_sets: 0, away_sets: 3 }), 'Infantil');
    expect(headline(awayWin)).toBe('¡VICTORIA!');
  });

  it('previa con fecha completa (sin "Hoy") y el partido para el tiempo', () => {
    const d = dataFromMatch(match(), 'Infantil');
    expect(d.kind).toBe('preview');
    expect(headline(d)).toBe('PRÓXIMO PARTIDO');
    expect(d.whenDate).toBe('Domingo, 18 de octubre');
    expect(d.whenTime).toBe('10:30');
    expect(d.weatherMatch.id).toBe(1);
  });

  it('resultado provisional', () => {
    const d = dataFromMatch(match({ provisional: { home_sets: 3, away_sets: 0, partials: [[25, 10, true]], by: 'Ana' } }), 'Infantil');
    expect(d.kind).toBe('result');
    expect(d.provisional).toBe(true);
    expect(headline(d)).toBe('¡VICTORIA!');
  });

  it('desde el marcador, con Ancares visitante o partido libre', () => {
    const game = { home: { name: 'Rival' }, away: { name: OURS }, oursSide: 'away', startedAt: Date.parse('2026-10-18T08:30:00Z') };
    expect(headline(dataFromGame(game, { home_sets: 1, away_sets: 3, partials: [] }, 'X', true))).toBe('¡VICTORIA!');
    expect(headline(dataFromGame({ ...game, oursSide: null }, { home_sets: 1, away_sets: 3, partials: [] }, 'X', false))).toBe('RESULTADO');
    expect(headline(dataFromGame(game, { home_sets: 1, away_sets: 1, partials: [] }, 'X', false))).toBe('EMPATE');
    // Terminado a mitad del primer set: no es un empate
    expect(headline(dataFromGame(game, { home_sets: 0, away_sets: 0, partials: [[6, 3, false]] }, 'X', false))).toBe('RESULTADO');
  });
});

describe('texto en el lienzo', () => {
  it('reduce la fuente hasta que el texto cabe', () => {
    const ctx = fakeCtx();
    expect(fitFont(ctx, 'abcdefghij', 1000, 60)).toBe(60); // 10 × 30 = 300
    const s = fitFont(ctx, 'abcdefghij', 200, 60); // necesita ≤ 40
    expect(s).toBeLessThanOrEqual(40);
    expect(ctx.measureText('abcdefghij').width).toBeLessThanOrEqual(200);
  });

  it('reparte en líneas y corta la última con puntos suspensivos', () => {
    const ctx = fakeCtx(); // 20 px por carácter
    expect(wrapLines(ctx, 'uno dos tres', 1000, 2)).toEqual(['uno dos tres']);
    const lines = wrapLines(ctx, 'Polideportivo Municipal Pisuerga Ciudad Deportiva Fuente la Mora', 500, 2);
    expect(lines).toHaveLength(2);
    expect(lines[1].endsWith('…')).toBe(true);
    lines.forEach((l) => expect(ctx.measureText(l).width).toBeLessThanOrEqual(500));
  });

  it('nombre de fichero legible', () => {
    expect(fileName(dataFromMatch(match(), 'Infantil'))).toBe('ancares-previa-ancares-uva-vcv-castilla.png');
  });
});
