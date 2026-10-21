import { Contender, GameResult, Pairing, Side, Tournament, TournamentFormat } from './models';
import { newId } from './live-game';

/**
 * Emparejamientos round robin con las tablas de Berger (método del círculo).
 * Con n impar se añade un "descanso" (null) y quien lo toca no juega esa ronda.
 * Los colores se asignan para que cada jugador termine con ±1 blancas respecto a negras
 * (gana blancas quien lleva menos; a igualdad, quien jugó con negras la ronda anterior).
 */
export function bergerRounds(ids: string[]): Array<Array<[string, string]>> {
  const players: Array<string | null> = [...ids];
  if (players.length % 2 === 1) players.push(null);
  const n = players.length;
  const rounds: Array<Array<[string, string]>> = [];
  const rot = players.slice(1);
  // Balance de colores: diff = blancas - negras; last = color de la ronda anterior.
  const diff = new Map<string, number>(ids.map((id) => [id, 0]));
  const last = new Map<string, 'w' | 'b' | null>(ids.map((id) => [id, null]));
  for (let r = 0; r < n - 1; r++) {
    const circle = [players[0], ...rot];
    const games: Array<[string, string]> = [];
    for (let i = 0; i < n / 2; i++) {
      const a = circle[i];
      const b = circle[n - 1 - i];
      if (a === null || b === null) continue;
      const da = diff.get(a)!;
      const db = diff.get(b)!;
      let aWhite: boolean;
      if (da !== db) aWhite = da < db;
      else if (last.get(a) !== last.get(b)) aWhite = last.get(a) === 'b' || last.get(b) === 'w';
      else aWhite = (r + i) % 2 === 0;
      const [w, bl] = aWhite ? [a, b] : [b, a];
      diff.set(w, diff.get(w)! + 1);
      diff.set(bl, diff.get(bl)! - 1);
      last.set(w, 'w');
      last.set(bl, 'b');
      games.push([w, bl]);
    }
    rounds.push(games);
    rot.unshift(rot.pop()!);
  }
  return rounds;
}

export function buildPairings(format: TournamentFormat, participants: Contender[], matchGames = 2): Pairing[] {
  const ids = participants.map((p) => p.id);
  const pairings: Pairing[] = [];
  if (format === 'match') {
    const [a, b] = ids;
    for (let g = 0; g < matchGames; g++) {
      pairings.push({ id: newId(8), round: g + 1, white: g % 2 === 0 ? a : b, black: g % 2 === 0 ? b : a });
    }
    return pairings;
  }
  const single = bergerRounds(ids);
  single.forEach((games, r) => games.forEach(([w, b]) => pairings.push({ id: newId(8), round: r + 1, white: w, black: b })));
  if (format === 'double-round-robin') {
    const offset = single.length;
    single.forEach((games, r) =>
      games.forEach(([w, b]) => pairings.push({ id: newId(8), round: offset + r + 1, white: b, black: w })),
    );
  }
  return pairings;
}

export function scoreFor(result: GameResult, side: Side): number {
  if (result === '1/2-1/2') return 0.5;
  return (result === '1-0') === (side === 'w') ? 1 : 0;
}

export interface StandingRow {
  id: string;
  contender: Contender;
  rank: number;
  points: number;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  sonnebornBerger: number;
  whiteGames: number;
  validMovePct: number | null;
  avgThinkMs: number | null;
  timeLosses: number;
}

/**
 * Clasificación: puntos → Sonneborn-Berger → victorias → enfrentamiento directo implícito
 * (no se calcula) → nombre. SB = suma de puntos de los rivales vencidos + mitad de los empatados.
 */
export function standings(t: Tournament): StandingRow[] {
  const rows = new Map<string, StandingRow>();
  const telemetry = new Map<string, { clean: number; fallback: number; thinkMs: number; moves: number }>();
  for (const c of t.participants) {
    rows.set(c.id, {
      id: c.id, contender: c, rank: 0, points: 0, played: 0, wins: 0, draws: 0, losses: 0,
      sonnebornBerger: 0, whiteGames: 0, validMovePct: null, avgThinkMs: null, timeLosses: 0,
    });
    telemetry.set(c.id, { clean: 0, fallback: 0, thinkMs: 0, moves: 0 });
  }
  const finished = t.pairings.filter((p) => p.result && p.termination !== 'aborted');
  for (const p of finished) {
    const res = p.result!;
    for (const side of ['w', 'b'] as Side[]) {
      const id = side === 'w' ? p.white : p.black;
      const row = rows.get(id);
      if (!row) continue;
      const pts = scoreFor(res, side);
      row.points += pts;
      row.played++;
      if (side === 'w') row.whiteGames++;
      if (pts === 1) row.wins++;
      else if (pts === 0.5) row.draws++;
      else row.losses++;
      if (p.stats?.timeouts === side) row.timeLosses++;
      const st = p.stats?.[side];
      const tel = telemetry.get(id)!;
      if (st) {
        tel.clean += st.clean;
        tel.fallback += st.fallback;
        tel.thinkMs += st.thinkMs;
        tel.moves += st.moves;
      }
    }
  }
  for (const p of finished) {
    const res = p.result!;
    const w = rows.get(p.white);
    const b = rows.get(p.black);
    if (!w || !b) continue;
    w.sonnebornBerger += scoreFor(res, 'w') * b.points;
    b.sonnebornBerger += scoreFor(res, 'b') * w.points;
  }
  for (const [id, row] of rows) {
    const tel = telemetry.get(id)!;
    const judged = tel.clean + tel.fallback;
    // El motor no usa LLM: el % de respuestas válidas no aplica.
    row.validMovePct = judged && row.contender.mode !== 'engine' ? (100 * tel.clean) / judged : null;
    row.avgThinkMs = tel.moves ? tel.thinkMs / tel.moves : null;
  }
  const sorted = [...rows.values()].sort(
    (a, b) =>
      b.points - a.points ||
      b.sonnebornBerger - a.sonnebornBerger ||
      b.wins - a.wins ||
      a.contender.label.localeCompare(b.contender.label),
  );
  sorted.forEach((r, i) => {
    const prev = sorted[i - 1];
    r.rank = prev && prev.points === r.points && prev.sonnebornBerger === r.sonnebornBerger && prev.wins === r.wins ? prev.rank : i + 1;
  });
  return sorted;
}

/** Tabla cruzada: celdas con los resultados de la fila contra la columna ("1", "½", "0"). */
export function crosstable(t: Tournament): Map<string, Map<string, string[]>> {
  const table = new Map<string, Map<string, string[]>>();
  for (const a of t.participants) {
    const row = new Map<string, string[]>();
    for (const b of t.participants) row.set(b.id, []);
    table.set(a.id, row);
  }
  const symbol = (x: number) => (x === 1 ? '1' : x === 0.5 ? '½' : '0');
  for (const p of t.pairings) {
    if (!p.result || p.termination === 'aborted') continue;
    table.get(p.white)?.get(p.black)?.push(symbol(scoreFor(p.result, 'w')));
    table.get(p.black)?.get(p.white)?.push(symbol(scoreFor(p.result, 'b')));
  }
  return table;
}

export function progress(t: Tournament): { done: number; total: number } {
  return { done: t.pairings.filter((p) => !!p.result).length, total: t.pairings.length };
}

export const FORMAT_LABEL: Record<TournamentFormat, string> = {
  'round-robin': 'Todos contra todos',
  'double-round-robin': 'Todos contra todos (ida y vuelta)',
  match: 'Match',
};
