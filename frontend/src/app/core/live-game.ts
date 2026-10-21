import { computed, signal } from '@angular/core';
import { Chess, Move } from 'chess.js';
import { ApiError, ApiService } from './api.service';
import { ChessClock } from './chess-clock';
import {
  Contender,
  GameResult,
  PlayedMove,
  Side,
  SideStats,
  Termination,
  TimeControl,
} from './models';
import { pgnClock, tcPgn } from './time-controls';

export type GameStatus = 'ready' | 'running' | 'paused' | 'error' | 'finished';

export interface LiveGameOptions {
  white: Contender;
  black: Contender;
  timeControl: TimeControl;
  api: ApiService;
  /** Límite de medias jugadas antes de adjudicar tablas (IA vs IA). 0 = sin límite. */
  maxPlies?: number;
  /** Pausa visual entre jugadas de IA. No consume reloj. */
  moveDelayMs?: number;
  event?: string;
  round?: number;
  onFinish?: (game: LiveGame) => void;
}

const other = (s: Side): Side => (s === 'w' ? 'b' : 'w');

export function newId(len = 12): string {
  const bytes = new Uint8Array(len);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => 'abcdefghijklmnopqrstuvwxyz0123456789'[b % 36]).join('');
}

/**
 * Una partida en vivo: reglas (chess.js), relojes, turnos de IA contra la API, fin de partida
 * según las reglas FIDE y exportación a PGN con relojes.
 */
export class LiveGame {
  readonly id = newId();
  readonly white: Contender;
  readonly black: Contender;
  readonly timeControl: TimeControl;
  readonly clock: ChessClock;
  readonly startedAt = new Date();

  private readonly chess = new Chess();
  private readonly api: ApiService;
  private readonly maxPlies: number;
  private readonly moveDelayMs: number;
  private readonly event: string;
  private readonly round?: number;
  private readonly onFinish?: (game: LiveGame) => void;
  private aiAbort: AbortController | null = null;
  private delayTimer: ReturnType<typeof setTimeout> | null = null;

  readonly fen = signal(this.chess.fen());
  readonly moves = signal<PlayedMove[]>([]);
  readonly status = signal<GameStatus>('ready');
  readonly result = signal<GameResult | null>(null);
  readonly termination = signal<Termination | null>(null);
  readonly error = signal<string | null>(null);
  readonly thinking = signal<Side | null>(null);
  readonly lastAiOutput = signal<{ side: Side; raw: string; clean: boolean; san: string } | null>(null);

  readonly turn = computed<Side>(() => this.fen().split(' ')[1] as Side);
  readonly lastMove = computed(() => {
    const mv = this.moves();
    return mv.length ? mv[mv.length - 1] : null;
  });
  readonly inCheck = computed(() => {
    this.fen();
    return this.chess.inCheck();
  });
  readonly stats = computed<Record<Side, SideStats>>(() => {
    const out: Record<Side, SideStats> = {
      w: { moves: 0, clean: 0, fallback: 0, thinkMs: 0 },
      b: { moves: 0, clean: 0, fallback: 0, thinkMs: 0 },
    };
    for (const m of this.moves()) {
      const s = out[m.side];
      s.moves++;
      s.thinkMs += m.thinkMs;
      if (m.clean === true) s.clean++;
      if (m.clean === false) s.fallback++;
    }
    return out;
  });

  constructor(opts: LiveGameOptions) {
    this.white = opts.white;
    this.black = opts.black;
    this.timeControl = opts.timeControl;
    this.api = opts.api;
    this.maxPlies = opts.maxPlies ?? 0;
    this.moveDelayMs = opts.moveDelayMs ?? 0;
    this.event = opts.event ?? 'Vertex Chess Arena';
    this.round = opts.round;
    this.onFinish = opts.onFinish;
    this.clock = new ChessClock(opts.timeControl, (side) => this.onFlag(side));
  }

  contender(side: Side): Contender {
    return side === 'w' ? this.white : this.black;
  }

  isHumanTurn(): boolean {
    return this.status() === 'running' && this.contender(this.turn()).kind === 'human';
  }

  /** Jugadas legales desde una casilla (para resaltar destinos en el tablero). */
  legalTargets(square: string): string[] {
    return this.chess.moves({ square: square as never, verbose: true }).map((m) => m.to);
  }

  isPromotion(from: string, to: string): boolean {
    return this.chess
      .moves({ square: from as never, verbose: true })
      .some((m) => m.to === to && !!m.promotion);
  }

  start(): void {
    if (this.status() !== 'ready') return;
    this.status.set('running');
    this.clock.start('w');
    this.scheduleTurn();
  }

  /** Jugada de una persona. Devuelve false si no es legal o no le toca. */
  humanMove(from: string, to: string, promotion?: string): boolean {
    if (!this.isHumanTurn()) return false;
    let move: Move;
    try {
      move = this.chess.move({ from, to, promotion: promotion ?? 'q' });
    } catch {
      return false;
    }
    this.afterMove(move, {});
    return true;
  }

  pause(): void {
    if (this.status() !== 'running') return;
    this.cancelPending();
    this.clock.pause();
    this.status.set('paused');
  }

  resume(): void {
    const st = this.status();
    if (st !== 'paused' && st !== 'error') return;
    this.error.set(null);
    this.status.set('running');
    this.clock.start(this.turn());
    this.scheduleTurn();
  }

  resign(side: Side): void {
    if (this.status() === 'finished') return;
    this.finish(side === 'w' ? '0-1' : '1-0', 'resignation');
  }

  abort(): void {
    if (this.status() === 'finished') return;
    this.finish('1/2-1/2', 'aborted');
  }

  destroy(): void {
    this.cancelPending();
    this.clock.destroy();
  }

  // ---------------------------------------------------------------------------

  private scheduleTurn(): void {
    if (this.status() !== 'running') return;
    const side = this.turn();
    if (this.contender(side).kind === 'ai') void this.requestAiMove(side);
  }

  private async requestAiMove(side: Side): Promise<void> {
    const who = this.contender(side);
    const ctrl = new AbortController();
    this.aiAbort = ctrl;
    this.thinking.set(side);
    const fenBefore = this.fen();
    // La IA no puede pensar más que lo que le queda en el reloj (+ margen de red).
    const timeoutMs = Math.min(180_000, this.clock.time()[side] + 5_000);
    try {
      const res = await this.api.aiMove(
        { fen: fenBefore, model_name: who.model ?? '', mode: who.mode ?? 'pure', game_id: this.id },
        ctrl.signal,
        timeoutMs,
      );
      if (ctrl.signal.aborted || this.status() !== 'running' || this.fen() !== fenBefore) return;
      const uci = res.played_uci;
      let move: Move;
      try {
        move = this.chess.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] });
      } catch {
        this.fail(`La API devolvió una jugada ilegal (${uci}).`);
        return;
      }
      this.lastAiOutput.set({ side, raw: res.raw_output, clean: res.clean_hit, san: move.san });
      this.afterMove(move, { clean: res.clean_hit, raw: res.raw_output });
    } catch (e) {
      if (ctrl.signal.aborted || this.status() !== 'running') return;
      const msg = e instanceof ApiError ? e.message : 'Error desconocido pidiendo la jugada.';
      this.fail(msg);
    } finally {
      if (this.aiAbort === ctrl) {
        this.aiAbort = null;
        this.thinking.set(null);
      }
    }
  }

  private afterMove(move: Move, meta: { clean?: boolean; raw?: string }): void {
    const side = move.color as Side;
    const { thinkMs, remainingMs } = this.clock.press(side);
    const ply = this.moves().length + 1;
    this.moves.update((list) => [
      ...list,
      {
        ply,
        side,
        san: move.san,
        uci: move.from + move.to + (move.promotion ?? ''),
        from: move.from,
        to: move.to,
        fenAfter: this.chess.fen(),
        clockAfterMs: remainingMs,
        thinkMs,
        clean: meta.clean,
        raw: meta.raw,
      },
    ]);
    this.fen.set(this.chess.fen());

    if (this.checkGameEnd(side)) return;

    const next = other(side);
    const bothAi = this.white.kind === 'ai' && this.black.kind === 'ai';
    if (bothAi && this.moveDelayMs > 0) {
      // Pausa visual: congelamos relojes para que no le cueste tiempo a nadie.
      this.clock.pause();
      this.delayTimer = setTimeout(() => {
        this.delayTimer = null;
        if (this.status() !== 'running') return;
        this.clock.start(next);
        this.scheduleTurn();
      }, this.moveDelayMs);
    } else {
      this.scheduleTurn();
    }
  }

  private checkGameEnd(mover: Side): boolean {
    const c = this.chess;
    if (c.isCheckmate()) {
      this.finish(mover === 'w' ? '1-0' : '0-1', 'checkmate');
    } else if (c.isStalemate()) {
      this.finish('1/2-1/2', 'stalemate');
    } else if (c.isInsufficientMaterial()) {
      this.finish('1/2-1/2', 'insufficient');
    } else if (c.isThreefoldRepetition()) {
      this.finish('1/2-1/2', 'threefold');
    } else if (c.isDrawByFiftyMoves()) {
      this.finish('1/2-1/2', 'fifty-move');
    } else if (this.maxPlies > 0 && this.moves().length >= this.maxPlies) {
      this.finish('1/2-1/2', 'adjudication');
    } else {
      return false;
    }
    return true;
  }

  /** Bandera: pierde quien se quedó sin tiempo, salvo que el rival no pueda dar mate (FIDE 6.9). */
  private onFlag(side: Side): void {
    if (this.status() === 'finished') return;
    const opp = other(side);
    if (this.hasMatingMaterial(opp)) {
      this.finish(opp === 'w' ? '1-0' : '0-1', 'timeout');
    } else {
      this.finish('1/2-1/2', 'timeout-vs-insufficient');
    }
  }

  hasMatingMaterial(side: Side): boolean {
    let minors = 0;
    for (const row of this.chess.board()) {
      for (const sq of row) {
        if (!sq || sq.color !== side) continue;
        if (sq.type === 'p' || sq.type === 'r' || sq.type === 'q') return true;
        if (sq.type === 'n' || sq.type === 'b') minors++;
      }
    }
    return minors >= 2;
  }

  private fail(message: string): void {
    this.clock.pause();
    this.error.set(message);
    this.status.set('error');
  }

  private cancelPending(): void {
    this.aiAbort?.abort();
    this.aiAbort = null;
    this.thinking.set(null);
    if (this.delayTimer) {
      clearTimeout(this.delayTimer);
      this.delayTimer = null;
    }
  }

  private finish(result: GameResult, termination: Termination): void {
    this.cancelPending();
    this.clock.stop();
    this.result.set(result);
    this.termination.set(termination);
    this.status.set('finished');
    this.onFinish?.(this);
  }

  // ---------------------------------------------------------------------------
  // PGN con relojes: 1. e4 {[%clk 0:02:58.4] [%emt 0:00:01.6]} e5 {...}
  // ---------------------------------------------------------------------------
  pgn(): string {
    const d = this.startedAt;
    const date = `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
    const result = this.result() ?? '*';
    const headers: Array<[string, string]> = [
      ['Event', this.event],
      ['Site', 'Vertex Coders Lab, Miami FL'],
      ['Date', date],
      ['Round', this.round ? String(this.round) : '-'],
      ['White', this.white.label],
      ['Black', this.black.label],
      ['Result', result],
      ['TimeControl', tcPgn(this.timeControl)],
      ['Termination', this.termination() ?? 'unterminated'],
      ['WhiteMode', this.white.kind === 'human' ? 'human' : (this.white.mode ?? 'pure')],
      ['BlackMode', this.black.kind === 'human' ? 'human' : (this.black.mode ?? 'pure')],
    ];
    const head = headers.map(([k, v]) => `[${k} "${v.replace(/"/g, "'")}"]`).join('\n');
    const parts: string[] = [];
    for (const m of this.moves()) {
      if (m.side === 'w') parts.push(`${Math.ceil(m.ply / 2)}.`);
      else if (parts.length === 0) parts.push(`${Math.ceil(m.ply / 2)}...`);
      parts.push(m.san);
      parts.push(`{[%clk ${pgnClock(m.clockAfterMs)}] [%emt ${pgnClock(m.thinkMs)}]}`);
    }
    parts.push(result);
    return `${head}\n\n${wrap(parts.join(' '), 80)}\n`;
  }
}

function wrap(text: string, width: number): string {
  const words = text.split(' ');
  const lines: string[] = [];
  let line = '';
  for (const w of words) {
    if (line && line.length + 1 + w.length > width) {
      lines.push(line);
      line = w;
    } else {
      line = line ? `${line} ${w}` : w;
    }
  }
  if (line) lines.push(line);
  return lines.join('\n');
}
