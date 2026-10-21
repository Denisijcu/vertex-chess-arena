import { BACKEND } from '../../core/backend-config';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideCopy,
  LucideDownload,
  LucideFlag,
  LucidePause,
  LucidePlay,
  LucideRefreshCcw,
  LucideRepeat,
  LucideX,
} from '@lucide/angular';
import { GameSession } from '../../core/game-session.service';
import { LiveGame } from '../../core/live-game';
import { Side, TERMINATION_LABEL } from '../../core/models';
import { tcLabel, CATEGORY_LABEL, categoryOf } from '../../core/time-controls';
import { BoardMove, ChessboardComponent } from '../../shared/chessboard';
import { downloadText, kingSquare, slug } from '../../shared/board-utils';
import { MoveListComponent } from '../../shared/move-list';
import { PlayerStripComponent } from '../../shared/player-strip';

@Component({
  selector: 'vx-play',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    ChessboardComponent,
    MoveListComponent,
    PlayerStripComponent,
    LucideCopy,
    LucideDownload,
    LucideFlag,
    LucidePause,
    LucidePlay,
    LucideRefreshCcw,
    LucideRepeat,
    LucideX,
  ],
  host: { '(document:keydown)': 'onKey($event)' },
  template: `
    @if (game(); as g) {
      <div class="grid lg:grid-cols-[minmax(0,640px)_1fr] gap-4 sm:gap-6 items-start">
        <section aria-label="Tablero" class="glass p-2 sm:p-3 md:p-4 min-w-0">
          <vx-player-strip
            [contender]="g.contender(topSide())" [side]="topSide()" [timeMs]="g.clock.time()[topSide()]"
            [baseMs]="g.timeControl.baseMs" [active]="g.clock.active() === topSide()"
            [thinking]="g.thinking() === topSide()" [stats]="g.stats()[topSide()]" />
          <div class="relative my-2">
            <vx-chessboard
              [fen]="g.fen()" [orientation]="orientation()" [interactive]="interactiveSide()"
              [lastMove]="g.lastMove()" [checkSquare]="checkSquare()"
              [legalTargets]="legalTargets" [isPromotion]="isPromotion" [tryMove]="tryMove"
              [ariaLabel]="'Tablero. Turno de ' + (g.turn() === 'w' ? 'blancas' : 'negras')" />
            @if (g.status() === 'finished' && !hideResult()) {
              <div class="absolute inset-0 grid place-items-center bg-black/45 rounded-lg" role="dialog" aria-modal="true" aria-label="Fin de la partida">
                <div class="glass !bg-zinc-900/95 w-72 p-6 text-center shadow-2xl relative">
                  <button type="button" class="absolute top-2 right-2 btn btn-ghost !p-1.5" (click)="hideResult.set(true)" aria-label="Cerrar">
                    <svg lucideX class="size-4"></svg>
                  </button>
                  <p class="text-2xl font-extrabold">{{ headline() }}</p>
                  <p class="text-sm text-zinc-400 mt-1">{{ terminationText() }}</p>
                  <p class="font-mono text-3xl font-bold mt-3">{{ g.result() }}</p>
                  <div class="grid grid-cols-2 gap-2 mt-5">
                    <a routerLink="/" class="btn btn-ghost">Nueva</a>
                    <button type="button" class="btn btn-primary" (click)="rematch()">Revancha</button>
                  </div>
                </div>
              </div>
            }
            @if (g.status() === 'ready') {
              <div class="absolute inset-0 grid place-items-center bg-black/55 backdrop-blur-[2px] rounded-lg">
                <div class="text-center px-6">
                  <p class="text-sm text-zinc-300 mb-1">{{ g.white.label }} <span class="text-zinc-500">vs</span> {{ g.black.label }}</p>
                  <p class="font-mono text-2xl font-bold mb-4">{{ tc() }} <span class="text-cyan-300 text-base font-sans">{{ category() }}</span></p>
                  <button type="button" class="btn btn-primary !px-8 !py-3 text-base" (click)="g.start()">
                    <svg lucidePlay class="size-5"></svg> Empezar
                  </button>
                </div>
              </div>
            }
          </div>
          <vx-player-strip
            [contender]="g.contender(bottomSide())" [side]="bottomSide()" [timeMs]="g.clock.time()[bottomSide()]"
            [baseMs]="g.timeControl.baseMs" [active]="g.clock.active() === bottomSide()"
            [thinking]="g.thinking() === bottomSide()" [stats]="g.stats()[bottomSide()]" />
        </section>

        <aside class="space-y-4 min-w-0">
          @if (g.status() === 'finished') {
            <div class="glass p-5 border-cyan-400/30" role="status">
              <p class="text-xs uppercase tracking-widest text-zinc-400">Resultado</p>
              <p class="text-3xl font-extrabold font-mono mt-1">{{ g.result() }}</p>
              <p class="mt-1 text-lg">{{ winnerText() }}</p>
              <p class="text-sm text-zinc-400">{{ terminationText() }} · {{ g.moves().length }} medias jugadas</p>
              <p class="text-xs mt-2" [class]="saveTone()">{{ saveText() }}</p>
            </div>
          }
          @if (g.status() === 'error') {
            <div class="glass p-4 border-rose-500/40 bg-rose-500/10" role="alert">
              <p class="font-semibold text-rose-200">Partida detenida</p>
              <p class="text-sm text-rose-100/80 mt-1">{{ g.error() }}</p>
              <p class="text-xs text-zinc-400 mt-1">Los relojes están congelados.</p>
              <button type="button" class="btn btn-ghost mt-3" (click)="g.resume()">
                <svg lucideRefreshCcw class="size-4"></svg> Reintentar
              </button>
            </div>
          }

          <div class="glass p-4">
            <div class="flex flex-wrap gap-2">
              @if (g.status() === 'running') {
                <button type="button" class="btn btn-ghost" (click)="g.pause()"><svg lucidePause class="size-4"></svg> Pausar</button>
              }
              @if (g.status() === 'paused') {
                <button type="button" class="btn btn-primary" (click)="g.resume()"><svg lucidePlay class="size-4"></svg> Reanudar</button>
              }
              <button type="button" class="btn btn-ghost" (click)="flipped.set(!flipped())" title="Girar tablero (F)">
                <svg lucideRepeat class="size-4"></svg> Girar
              </button>
              @if (humanSide() && g.status() !== 'finished' && g.status() !== 'ready') {
                <button type="button" class="btn btn-danger" (click)="resign()"><svg lucideFlag class="size-4"></svg> Abandonar</button>
              }
              @if (g.status() !== 'finished') {
                <button type="button" class="btn btn-ghost" (click)="g.abort()"><svg lucideX class="size-4"></svg> Anular</button>
              } @else {
                <button type="button" class="btn btn-primary" (click)="rematch()"><svg lucideRefreshCcw class="size-4"></svg> Revancha</button>
                <a routerLink="/" class="btn btn-ghost">Nueva partida</a>
              }
            </div>
            @if (confirmResign()) {
              <div class="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm flex items-center gap-3">
                <span class="flex-1">¿Seguro que abandonas?</span>
                <button type="button" class="btn btn-danger !py-1.5" (click)="resign()">Sí</button>
                <button type="button" class="btn btn-ghost !py-1.5" (click)="confirmResign.set(false)">No</button>
              </div>
            }
          </div>

          <div class="glass">
            <div class="flex items-center justify-between px-4 pt-3 pb-2">
              <h2 class="font-semibold text-sm">Jugadas</h2>
              <div class="flex gap-1">
                <button type="button" class="btn btn-ghost !p-2" (click)="copyPgn(g)" title="Copiar PGN" aria-label="Copiar PGN"><svg lucideCopy class="size-4"></svg></button>
                <button type="button" class="btn btn-ghost !p-2" (click)="download(g)" title="Descargar PGN" aria-label="Descargar PGN"><svg lucideDownload class="size-4"></svg></button>
              </div>
            </div>
            <vx-move-list [moves]="g.moves()" maxHeight="20rem" />
            @if (copied()) { <p class="text-xs text-emerald-300 px-4 pb-2">PGN copiado al portapapeles.</p> }
          </div>

          @if (g.lastAiOutput(); as out) {
            <div class="glass p-4">
              <h2 class="font-semibold text-sm mb-2">Salida del modelo ({{ g.contender(out.side).label }})</h2>
              <p class="text-xs text-zinc-400 mb-1">
                Jugó <span class="font-mono text-white">{{ out.san }}</span> ·
                @if (out.clean) { <span class="text-emerald-300">respuesta válida</span> }
                @else { <span class="text-amber-300">respuesta inválida → jugada aleatoria</span> }
              </p>
              <pre class="text-xs font-mono bg-black/50 rounded-lg p-3 whitespace-pre-wrap break-words text-zinc-300 max-h-32 overflow-y-auto">{{ out.raw }}</pre>
            </div>
          }
        </aside>
      </div>
    } @else {
      <div class="glass p-10 text-center max-w-lg mx-auto">
        <h1 class="text-2xl font-bold">No hay ninguna partida en curso</h1>
        <p class="text-zinc-400 mt-2">Configura una partida en la arena: contra la IA o IA contra IA, con el ritmo que quieras.</p>
        <a routerLink="/" class="btn btn-primary mt-6">Ir a la arena</a>
      </div>
    }
  `,
})
export class PlayPage {
  readonly session = inject(GameSession);
  readonly game = this.session.game;
  readonly flipped = signal(false);
  readonly confirmResign = signal(false);
  readonly copied = signal(false);
  readonly hideResult = signal(false);

  readonly humanSide = computed<Side | null>(() => {
    const g = this.game();
    if (!g) return null;
    if (g.white.kind === 'human') return 'w';
    if (g.black.kind === 'human') return 'b';
    return null;
  });
  readonly orientation = computed<Side>(() => {
    const base: Side = this.humanSide() ?? 'w';
    return this.flipped() ? (base === 'w' ? 'b' : 'w') : base;
  });
  readonly bottomSide = computed<Side>(() => this.orientation());
  readonly topSide = computed<Side>(() => (this.orientation() === 'w' ? 'b' : 'w'));
  readonly interactiveSide = computed<Side | null>(() => {
    const g = this.game();
    if (!g || g.status() !== 'running') return null;
    const t = g.turn();
    return g.contender(t).kind === 'human' ? t : null;
  });
  readonly checkSquare = computed(() => {
    const g = this.game();
    return g && g.inCheck() ? kingSquare(g.fen(), g.turn()) : null;
  });
  readonly tc = computed(() => (this.game() ? tcLabel(this.game()!.timeControl) : ''));
  readonly category = computed(() => (this.game() ? CATEGORY_LABEL[categoryOf(this.game()!.timeControl)] : ''));
  readonly winnerText = computed(() => {
    const g = this.game();
    const r = g?.result();
    if (!g || !r) return '';
    if (r === '1/2-1/2') return 'Tablas';
    return `Gana ${r === '1-0' ? g.white.label : g.black.label}`;
  });
  /** Titular del cartel final, al estilo de chess.com: "Ganan las negras". */
  readonly headline = computed(() => {
    const r = this.game()?.result();
    if (!r) return '';
    if (r === '1/2-1/2') return 'Tablas';
    return r === '1-0' ? 'Ganan las blancas' : 'Ganan las negras';
  });
  readonly terminationText = computed(() => {
    const t = this.game()?.termination();
    return t ? TERMINATION_LABEL[t] : '';
  });
  readonly saveText = computed(
    () =>
      ({
        idle: '',
        saving: 'Guardando en el historial…',
        saved: BACKEND.kind === 'space' ? 'Guardada en el historial de este navegador' : 'Guardada en el historial y en logs/matches_history.pgn',
        error: `No se pudo guardar: ${this.session.saveError() ?? ''}`,
      })[this.session.saveState()],
  );
  readonly saveTone = computed(() => (this.session.saveState() === 'error' ? 'text-rose-300' : 'text-zinc-500'));

  // Funciones que el tablero llama (flechas para conservar `this`).
  readonly legalTargets = (sq: string) => this.game()?.legalTargets(sq) ?? [];
  readonly isPromotion = (from: string, to: string) => this.game()?.isPromotion(from, to) ?? false;
  readonly tryMove = (m: BoardMove) => this.game()?.humanMove(m.from, m.to, m.promotion) ?? false;

  rematch(): void {
    this.hideResult.set(false);
    this.session.rematch();
  }

  resign(): void {
    const side = this.humanSide();
    const g = this.game();
    if (!side || !g) return;
    if (!this.confirmResign()) {
      this.confirmResign.set(true);
      return;
    }
    this.confirmResign.set(false);
    g.resign(side);
  }

  async copyPgn(g: LiveGame): Promise<void> {
    try {
      await navigator.clipboard.writeText(g.pgn());
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    } catch {
      this.download(g);
    }
  }

  download(g: LiveGame): void {
    downloadText(`${slug(g.white.label)}-vs-${slug(g.black.label)}.pgn`, g.pgn());
  }

  onKey(e: KeyboardEvent): void {
    const target = e.target as HTMLElement | null;
    if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return;
    if (e.key === 'f' || e.key === 'F') this.flipped.set(!this.flipped());
  }
}
