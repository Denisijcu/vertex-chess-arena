import { describe, expect, it } from 'vitest';
import { bergerRounds, buildPairings, standings } from './tournament-logic';
import { Contender, Tournament } from './models';

const players = (n: number): Contender[] =>
  Array.from({ length: n }, (_, i) => ({ id: `p${i}`, kind: 'ai', label: `P${i}`, model: 'm', mode: 'pure' }));

describe('bergerRounds', () => {
  for (const n of [2, 3, 4, 5, 6, 7, 8]) {
    it(`con ${n} jugadores todos se enfrentan una vez y los colores quedan equilibrados`, () => {
      const ids = players(n).map((p) => p.id);
      const rounds = bergerRounds(ids);
      const seen = new Set<string>();
      const whites = new Map(ids.map((id) => [id, 0]));
      for (const round of rounds) {
        const inRound = new Set<string>();
        for (const [w, b] of round) {
          expect(inRound.has(w) || inRound.has(b)).toBe(false);
          inRound.add(w);
          inRound.add(b);
          seen.add([w, b].sort().join('-'));
          whites.set(w, whites.get(w)! + 1);
        }
      }
      expect(seen.size).toBe((n * (n - 1)) / 2);
      const games = n - 1;
      for (const w of whites.values()) expect(Math.abs(w - (games - w))).toBeLessThanOrEqual(1);
    });
  }
});

describe('buildPairings', () => {
  it('match alterna colores', () => {
    const p = buildPairings('match', players(2), 4);
    expect(p.map((x) => x.white)).toEqual(['p0', 'p1', 'p0', 'p1']);
  });
  it('ida y vuelta invierte colores', () => {
    const p = buildPairings('double-round-robin', players(3), 0);
    expect(p.length).toBe(6);
    const key = (w: string, b: string) => `${w}>${b}`;
    const all = new Set(p.map((x) => key(x.white, x.black)));
    for (const x of p) expect(all.has(key(x.black, x.white))).toBe(true);
  });
});

describe('standings', () => {
  it('ordena por puntos y desempata por Sonneborn-Berger', () => {
    const ps = players(3);
    const t: Tournament = {
      id: 'tttttt', name: 'x', format: 'round-robin', timeControl: { baseMs: 1, incMs: 0 }, participants: ps,
      status: 'finished', createdAt: '', settings: { maxPlies: 0, moveDelayMs: 0 },
      pairings: [
        { id: '1', round: 1, white: 'p0', black: 'p1', result: '1-0', termination: 'checkmate' },
        { id: '2', round: 2, white: 'p1', black: 'p2', result: '1-0', termination: 'checkmate' },
        { id: '3', round: 3, white: 'p2', black: 'p0', result: '1-0', termination: 'timeout',
          stats: { w: { moves: 10, clean: 9, fallback: 1, thinkMs: 1000 }, b: { moves: 10, clean: 10, fallback: 0, thinkMs: 2000 }, timeouts: 'b' } },
      ],
    };
    const s = standings(t);
    expect(s.map((r) => r.points)).toEqual([1, 1, 1]);
    expect(s.every((r) => r.sonnebornBerger === 1)).toBe(true);
    expect(s.find((r) => r.id === 'p0')!.timeLosses).toBe(1);
    expect(s.find((r) => r.id === 'p2')!.validMovePct).toBe(90);
    expect(s.every((r) => r.rank === 1)).toBe(true);
  });
});
