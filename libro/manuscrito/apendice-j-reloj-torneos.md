# Apéndice J — El reloj y la lógica de torneos

Dos archivos TypeScript de la aplicación Angular, sin dependencias de interfaz: se pueden
probar y reutilizar por separado.

**`chess-clock.ts`** es el reloj Bronstein del capítulo 10. El estado vive en *signals* de
Angular. La línea clave está en `press`: al terminar una jugada se devuelve lo pensado, **hasta**
el incremento, así que el reloj nunca sube. `tick` detecta la caída de bandera.

**`tournament-logic.ts`** contiene todo el reglamento de los torneos:

- `bergerRounds`: el calendario de todos contra todos con el método del círculo de Berger, con
  un "descanso" ficticio si el número de jugadores es impar.
- `buildPairings`: convierte las rondas en partidas y reparte los colores de forma voraz para
  que cada jugador tenga blancas y negras equilibradas.
- `standings`: puntos, partidas, victorias, tablas, derrotas, desempate **Sonneborn-Berger**,
  porcentaje de jugadas válidas, tiempo medio y caídas de bandera.
- `crosstable`: la tabla cruzada.

### `frontend/src/app/core/chess-clock.ts`

```{.typescript .numberLines}
import { computed, signal } from '@angular/core';
import { Side, TimeControl } from './models';

/**
 * Reloj de ajedrez con demora Bronstein (la de los torneos de la US Chess).
 *
 * Ritmo "3+2" = 3 minutos por jugador y hasta 2 s de devolución por jugada: al terminar
 * una jugada se le devuelve al jugador lo que pensó, con un tope de 2 s. Por eso el reloj
 * NUNCA sube por encima de lo que tenía al empezar su turno, y si llega a 0:00 pierde.
 * (Con Fischer, el sistema de la FIDE, se suman siempre los 2 s y el reloj puede subir si
 * se juega rápido; con modelos que responden en ~1.5 s eso confundía.)
 *
 * - El tiempo se mide con un reloj monotónico (performance.now) y se refresca cada 100 ms;
 *   el valor exacto se calcula siempre a partir de la marca de inicio, así el redondeo del
 *   intervalo nunca acumula error.
 * - press(side): el jugador `side` terminó su jugada → se le descuenta lo que pensó, se le
 *   devuelve hasta `incMs` de ese tiempo y empieza a correr el reloj del rival.
 * - pause()/resume() congelan el reloj (pausas visuales del modo IA vs IA, errores de red).
 */
export class ChessClock {
  private readonly remaining = signal<Record<Side, number>>({ w: 0, b: 0 });
  private readonly runningSide = signal<Side | null>(null);
  private readonly now = signal(0);
  private startedAt = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private flagged = false;

  static readonly MODE = 'Bronstein';

  /** Tiempo restante en vivo de cada lado. */
  readonly time = computed<Record<Side, number>>(() => {
    const rem = this.remaining();
    const side = this.runningSide();
    if (!side) return rem;
    const elapsed = this.now() - this.startedAt;
    return { ...rem, [side]: Math.max(0, rem[side] - elapsed) } as Record<Side, number>;
  });

  readonly active = this.runningSide.asReadonly();

  constructor(
    readonly control: TimeControl,
    private readonly onFlag: (side: Side) => void,
    private readonly clockFn: () => number = () => performance.now(),
    private readonly tickMs = 100,
  ) {
    this.remaining.set({ w: control.baseMs, b: control.baseMs });
  }

  /** Arranca el reloj de `side` (inicio de partida o reanudación). */
  start(side: Side): void {
    if (this.flagged) return;
    this.startedAt = this.clockFn();
    this.now.set(this.startedAt);
    this.runningSide.set(side);
    this.ensureTimer();
  }

  /**
   * `side` completó su jugada. Devuelve el tiempo que pensó y el reloj que le queda
   * (ya con la devolución Bronstein: min(lo pensado, demora)).
   */
  press(side: Side): { thinkMs: number; remainingMs: number } {
    const t = this.clockFn();
    const rem = { ...this.remaining() };
    let thinkMs = 0;
    if (this.runningSide() === side) {
      thinkMs = t - this.startedAt;
      rem[side] = Math.max(0, rem[side] - thinkMs);
    }
    rem[side] += Math.min(thinkMs, this.control.incMs);
    this.remaining.set(rem);
    const other: Side = side === 'w' ? 'b' : 'w';
    this.startedAt = t;
    this.now.set(t);
    this.runningSide.set(other);
    this.ensureTimer();
    return { thinkMs: Math.round(thinkMs), remainingMs: rem[side] };
  }

  /** Congela el reloj y devuelve el lado que estaba corriendo. */
  pause(): Side | null {
    const side = this.runningSide();
    if (side) {
      const rem = { ...this.remaining() };
      rem[side] = Math.max(0, rem[side] - (this.clockFn() - this.startedAt));
      this.remaining.set(rem);
    }
    this.runningSide.set(null);
    this.clearTimer();
    return side;
  }

  stop(): void {
    this.pause();
  }

  /** Para pruebas y para forzar la comprobación de bandera. */
  tick(): void {
    const side = this.runningSide();
    if (!side) return;
    const t = this.clockFn();
    this.now.set(t);
    if (!this.flagged && this.remaining()[side] - (t - this.startedAt) <= 0) {
      this.flagged = true;
      this.pause();
      const rem = { ...this.remaining() };
      rem[side] = 0;
      this.remaining.set(rem);
      this.onFlag(side);
    }
  }

  get hasFlagged(): boolean {
    return this.flagged;
  }

  destroy(): void {
    this.clearTimer();
    this.runningSide.set(null);
  }

  private ensureTimer(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.tick(), this.tickMs);
  }

  private clearTimer(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
```

### `frontend/src/app/core/tournament-logic.ts`

```{.typescript .numberLines}
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
```
