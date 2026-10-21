import { Injectable, inject, signal } from '@angular/core';
import { ApiError, ApiService } from './api.service';
import { LiveGame } from './live-game';
import { Contender, TimeControl } from './models';
import { tcPgn } from './time-controls';

export interface QuickGameSetup {
  white: Contender;
  black: Contender;
  timeControl: TimeControl;
  maxPlies: number;
  moveDelayMs: number;
}

/** Partida rápida (fuera de torneo). Sobrevive a la navegación entre pantallas. */
@Injectable({ providedIn: 'root' })
export class GameSession {
  private readonly api = inject(ApiService);
  readonly game = signal<LiveGame | null>(null);
  readonly lastSetup = signal<QuickGameSetup | null>(null);
  readonly saveState = signal<'idle' | 'saving' | 'saved' | 'error'>('idle');
  readonly saveError = signal<string | null>(null);

  newGame(setup: QuickGameSetup): LiveGame {
    this.game()?.destroy();
    this.lastSetup.set(setup);
    this.saveState.set('idle');
    const g = new LiveGame({
      ...setup,
      api: this.api,
      event: 'Vertex Chess Arena — Partida libre',
      onFinish: (done) => void this.save(done),
    });
    this.game.set(g);
    return g;
  }

  rematch(): LiveGame | null {
    const s = this.lastSetup();
    if (!s) return null;
    // Revancha con colores invertidos.
    return this.newGame({ ...s, white: s.black, black: s.white });
  }

  private async save(g: LiveGame): Promise<void> {
    if (g.termination() === 'aborted' || g.moves().length === 0) return;
    this.saveState.set('saving');
    try {
      const st = g.stats();
      await this.api.saveGame({
        pgn: g.pgn(),
        white: g.white.label,
        black: g.black.label,
        result: g.result()!,
        termination: g.termination()!,
        time_control: tcPgn(g.timeControl),
        plies: g.moves().length,
        stats: { w: st.w, b: st.b },
      });
      this.saveState.set('saved');
    } catch (e) {
      this.saveState.set('error');
      this.saveError.set(e instanceof ApiError ? e.message : 'No se pudo guardar la partida.');
    }
  }
}
