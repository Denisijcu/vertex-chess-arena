import { Injectable, inject, signal } from '@angular/core';
import { ApiError, ApiService } from './api.service';
import { LiveGame, newId } from './live-game';
import { Contender, Pairing, Side, TimeControl, Tournament, TournamentFormat } from './models';
import { buildPairings } from './tournament-logic';
import { tcPgn } from './time-controls';

export interface NewTournament {
  name: string;
  format: TournamentFormat;
  participants: Contender[];
  timeControl: TimeControl;
  maxPlies: number;
  moveDelayMs: number;
  matchGames: number;
}

/**
 * Corre torneos IA vs IA de forma secuencial. Vive a nivel de aplicación: si navegas a otra
 * pantalla el torneo sigue jugando. Cada partida terminada se guarda en el backend
 * (/api/games) y el estado del torneo en /api/tournaments/{id}.
 */
@Injectable({ providedIn: 'root' })
export class TournamentRunner {
  private readonly api = inject(ApiService);

  readonly tournament = signal<Tournament | null>(null);
  readonly live = signal<LiveGame | null>(null);
  readonly livePairingId = signal<string | null>(null);
  readonly error = signal<string | null>(null);
  private nextTimer: ReturnType<typeof setTimeout> | null = null;

  get isActive(): boolean {
    return this.tournament()?.status === 'running';
  }

  async create(cfg: NewTournament): Promise<Tournament> {
    const t: Tournament = {
      id: newId(10),
      name: cfg.name.trim() || 'Torneo Vertex',
      format: cfg.format,
      timeControl: cfg.timeControl,
      participants: cfg.participants,
      pairings: buildPairings(cfg.format, cfg.participants, cfg.matchGames),
      status: 'pending',
      createdAt: new Date().toISOString(),
      settings: { maxPlies: cfg.maxPlies, moveDelayMs: cfg.moveDelayMs, matchGames: cfg.matchGames },
    };
    await this.api.saveTournament(t);
    return t;
  }

  /** Carga un torneo. Si es el que está corriendo, se queda con el estado vivo. */
  async load(id: string): Promise<void> {
    const current = this.tournament();
    if (current?.id === id && (this.live() || current.status === 'running')) return;
    if (this.isActive && current?.id !== id) {
      throw new ApiError('BUSY', `Ya hay un torneo en curso: “${current?.name}”. Páusalo antes de abrir otro.`);
    }
    this.disposeLive();
    const t = await this.api.tournament(id);
    // Un torneo que quedó "running" de una sesión anterior se reanuda manualmente.
    if (t.status === 'running') t.status = 'paused';
    this.tournament.set(t);
    this.error.set(null);
  }

  start(): void {
    const t = this.tournament();
    if (!t || t.status === 'finished') return;
    const live = this.live();
    this.patch({ status: 'running' });
    if (live && live.status() !== 'finished') {
      if (live.status() === 'paused' || live.status() === 'error') live.resume();
      return;
    }
    this.runNext();
  }

  pause(): void {
    const t = this.tournament();
    if (!t || t.status !== 'running') return;
    if (this.nextTimer) {
      clearTimeout(this.nextTimer);
      this.nextTimer = null;
    }
    this.live()?.pause();
    this.patch({ status: 'paused' });
    void this.persist();
  }

  /** Anula la partida en curso y la vuelve a jugar desde cero. */
  restartCurrentGame(): void {
    const t = this.tournament();
    if (!t) return;
    this.disposeLive();
    if (t.status === 'running') this.runNext();
  }

  contender(id: string): Contender | undefined {
    return this.tournament()?.participants.find((p) => p.id === id);
  }

  // ---------------------------------------------------------------------------

  private runNext(): void {
    const t = this.tournament();
    if (!t || t.status !== 'running') return;
    const next = t.pairings.find((p) => !p.result);
    if (!next) {
      this.patch({ status: 'finished', finishedAt: new Date().toISOString() });
      this.disposeLive();
      void this.persist();
      return;
    }
    const white = this.contender(next.white);
    const black = this.contender(next.black);
    if (!white || !black) {
      this.error.set('Emparejamiento con un jugador que no existe en el torneo.');
      return;
    }
    this.disposeLive();
    const game = new LiveGame({
      white,
      black,
      timeControl: t.timeControl,
      api: this.api,
      maxPlies: t.settings.maxPlies,
      moveDelayMs: t.settings.moveDelayMs,
      event: t.name,
      round: next.round,
      onFinish: (g) => void this.onGameFinished(next.id, g),
    });
    this.live.set(game);
    this.livePairingId.set(next.id);
    game.start();
  }

  private async onGameFinished(pairingId: string, g: LiveGame): Promise<void> {
    const t = this.tournament();
    if (!t || g.termination() === 'aborted') return;
    const termination = g.termination()!;
    const loserOnTime: Side | null =
      termination === 'timeout' ? (g.result() === '1-0' ? 'b' : 'w') : null;
    const stats = g.stats();
    const pgn = g.pgn();
    const pairing = t.pairings.find((p) => p.id === pairingId);
    let savedGameId: string | undefined;
    try {
      const saved = await this.api.saveGame({
        pgn,
        white: g.white.label,
        black: g.black.label,
        result: g.result()!,
        termination,
        time_control: tcPgn(t.timeControl),
        plies: g.moves().length,
        tournament_id: t.id,
        round: pairing?.round ?? null,
        stats: { w: stats.w, b: stats.b },
      });
      savedGameId = saved.id;
    } catch (e) {
      this.error.set(e instanceof ApiError ? `No se pudo guardar la partida: ${e.message}` : 'No se pudo guardar la partida.');
    }
    const update: Partial<Pairing> = {
      result: g.result()!,
      termination,
      plies: g.moves().length,
      pgn,
      stats: { w: stats.w, b: stats.b, timeouts: loserOnTime },
      savedGameId,
    };
    this.tournament.update((cur) =>
      cur ? { ...cur, pairings: cur.pairings.map((p) => (p.id === pairingId ? { ...p, ...update } : p)) } : cur,
    );
    await this.persist();
    // Pausa breve entre partidas para que se vea el resultado.
    this.nextTimer = setTimeout(() => {
      this.nextTimer = null;
      this.runNext();
    }, 2500);
  }

  private patch(p: Partial<Tournament>): void {
    this.tournament.update((t) => (t ? { ...t, ...p } : t));
  }

  private async persist(): Promise<void> {
    const t = this.tournament();
    if (!t) return;
    try {
      await this.api.saveTournament(t);
    } catch (e) {
      this.error.set(e instanceof ApiError ? `No se pudo guardar el torneo: ${e.message}` : 'No se pudo guardar el torneo.');
    }
  }

  private disposeLive(): void {
    this.live()?.destroy();
    this.live.set(null);
    this.livePairingId.set(null);
  }
}
