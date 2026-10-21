import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideDownload, LucidePause, LucidePlay, LucideRotateCcw, LucideTrophy } from '@lucide/angular';
import { ApiError } from '../../core/api.service';
import { GameResult, Pairing, TERMINATION_LABEL, Termination } from '../../core/models';
import { CATEGORY_LABEL, categoryOf, tcLabel } from '../../core/time-controls';
import { FORMAT_LABEL, crosstable, progress, standings } from '../../core/tournament-logic';
import { TournamentRunner } from '../../core/tournament-runner.service';
import { ChessboardComponent } from '../../shared/chessboard';
import { downloadText, kingSquare, slug } from '../../shared/board-utils';
import { MoveListComponent } from '../../shared/move-list';
import { PlayerStripComponent } from '../../shared/player-strip';

@Component({
  selector: 'vx-tournament-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    DecimalPipe,
    ChessboardComponent,
    MoveListComponent,
    PlayerStripComponent,
    LucideDownload,
    LucidePause,
    LucidePlay,
    LucideRotateCcw,
    LucideTrophy,
  ],
  template: `
    @if (loading()) {
      <div class="space-y-4"><div class="skeleton h-24"></div><div class="skeleton h-96"></div></div>
    } @else if (loadError()) {
      <div class="glass p-8 max-w-xl mx-auto text-center">
        <p class="text-rose-200">{{ loadError() }}</p>
        <div class="mt-4 flex justify-center gap-2">
          @if (runner.tournament(); as active) {
            <a class="btn btn-primary" [routerLink]="['/torneos', active.id]">Ir al torneo en curso</a>
          }
          <a class="btn btn-ghost" routerLink="/torneos">Volver a torneos</a>
        </div>
      </div>
    } @else if (t(); as t) {
      <!-- Cabecera -->
      <header class="glass p-5 md:p-6 flex flex-col md:flex-row md:items-center gap-4">
        <div class="flex-1 min-w-0">
          <p class="text-xs uppercase tracking-widest text-zinc-400">{{ formatLabel[t.format] }} · <span class="font-mono">{{ tc() }}</span> {{ category() }}</p>
          <h1 class="text-2xl md:text-3xl font-extrabold tracking-tight mt-1 flex items-center gap-3">
            <svg lucideTrophy class="size-7 text-amber-300 shrink-0"></svg><span class="truncate">{{ t.name }}</span>
          </h1>
          <div class="mt-3 flex items-center gap-3">
            <div class="h-2 flex-1 max-w-md rounded-full bg-white/10 overflow-hidden" role="progressbar"
              [attr.aria-valuenow]="prog().done" aria-valuemin="0" [attr.aria-valuemax]="prog().total">
              <div class="h-full bg-gradient-to-r from-cyan-400 to-violet-500 transition-all" [style.width.%]="prog().total ? (100 * prog().done) / prog().total : 0"></div>
            </div>
            <span class="text-sm text-zinc-400 font-mono">{{ prog().done }}/{{ prog().total }}</span>
            <span class="chip" [class]="statusTone()">{{ statusLabel[t.status] }}</span>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          @switch (t.status) {
            @case ('running') {
              <button type="button" class="btn btn-ghost" (click)="runner.pause()"><svg lucidePause class="size-4"></svg> Pausar</button>
              <button type="button" class="btn btn-ghost" (click)="runner.restartCurrentGame()" title="Anula la partida en curso y la repite">
                <svg lucideRotateCcw class="size-4"></svg> Repetir partida
              </button>
            }
            @case ('finished') {}
            @default {
              <button type="button" class="btn btn-primary" (click)="runner.start()">
                <svg lucidePlay class="size-4"></svg> {{ t.status === 'pending' ? 'Iniciar torneo' : 'Reanudar' }}
              </button>
            }
          }
          <button type="button" class="btn btn-ghost" (click)="downloadAll()" [disabled]="!prog().done">
            <svg lucideDownload class="size-4"></svg> PGN del torneo
          </button>
        </div>
      </header>

      @if (runner.error()) {
        <p class="mt-4 glass p-3 text-sm text-rose-200 border-rose-500/30" role="alert">{{ runner.error() }}</p>
      }

      @if (t.status === 'finished' && rows().length) {
        <div class="mt-6 glass p-6 text-center border-amber-400/30">
          @if (leaders().length === 1) {
            <p class="text-xs uppercase tracking-widest text-amber-300">Campeón</p>
            <p class="text-3xl font-extrabold mt-1">{{ leaders()[0].contender.label }}</p>
          } @else {
            <p class="text-xs uppercase tracking-widest text-amber-300">Empate en el primer puesto</p>
            <p class="text-2xl font-extrabold mt-1">{{ leaderNames() }}</p>
          }
          <p class="text-zinc-400 mt-1">{{ rows()[0].points | number: '1.0-1' }} {{ rows()[0].points === 1 ? 'punto' : 'puntos' }} de {{ rows()[0].played }} partidas</p>
        </div>
      }

      <div [class]="showLive() ? 'mt-6 grid gap-6 items-start xl:grid-cols-[minmax(0,520px)_1fr]' : 'mt-6 grid gap-6 items-start'">
        <!-- Partida en vivo -->
        @if (showLive()) {
        <section class="glass p-3 md:p-4" aria-label="Partida en vivo">
          @if (runner.live(); as g) {
            <p class="text-xs text-zinc-400 px-1 pb-1">Ronda {{ livePairing()?.round }} · en vivo</p>
            <vx-player-strip [contender]="g.black" side="b" [timeMs]="g.clock.time().b" [baseMs]="g.timeControl.baseMs"
              [active]="g.clock.active() === 'b'" [thinking]="g.thinking() === 'b'" [stats]="g.stats().b" />
            <vx-chessboard [fen]="g.fen()" [lastMove]="g.lastMove()" [checkSquare]="g.inCheck() ? king(g.fen(), g.turn()) : null" />
            <vx-player-strip [contender]="g.white" side="w" [timeMs]="g.clock.time().w" [baseMs]="g.timeControl.baseMs"
              [active]="g.clock.active() === 'w'" [thinking]="g.thinking() === 'w'" [stats]="g.stats().w" />
            @if (g.status() === 'error') {
              <div class="mt-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm" role="alert">
                <p class="text-rose-200">{{ g.error() }}</p>
                <button type="button" class="btn btn-ghost mt-2" (click)="g.resume()">Reintentar</button>
              </div>
            }
            @if (g.status() === 'finished') {
              <p class="mt-2 text-center text-sm text-zinc-300">
                <span class="font-mono font-bold">{{ g.result() }}</span> · {{ termLabel(g.termination()) }} — siguiente partida en un momento…
              </p>
            }
            <div class="mt-3 border-t border-white/10 pt-2">
              <vx-move-list [moves]="g.moves()" maxHeight="12rem" />
            </div>
          } @else {
            <div class="aspect-square grid place-items-center text-center text-zinc-400 p-8">
              @if (t.status === 'finished') { <p>Torneo terminado.</p> }
              @else if (t.status === 'pending') { <p>Pulsa <b class="text-white">Iniciar torneo</b> para empezar la primera partida.</p> }
              @else { <p>Torneo en pausa. Pulsa <b class="text-white">Reanudar</b> para seguir.</p> }
            </div>
          }
        </section>
        }

        <div class="space-y-6 min-w-0">
          <!-- Clasificación -->
          <section class="glass overflow-x-auto">
            <h2 class="font-semibold px-4 pt-4 pb-2">Clasificación</h2>
            <table class="w-full text-sm">
              <thead class="text-xs text-zinc-400 text-left">
                <tr class="border-b border-white/10">
                  <th class="px-4 py-2 w-10">#</th><th class="py-2">Jugador</th>
                  <th class="py-2 text-right">Pts</th><th class="py-2 text-right">J</th>
                  <th class="py-2 text-right">G</th><th class="py-2 text-right">T</th><th class="py-2 text-right">P</th>
                  <th class="py-2 text-right" title="Sonneborn-Berger">SB</th>
                  <th class="py-2 text-right" title="Respuestas válidas del modelo">Válidas</th>
                  <th class="py-2 text-right" title="Tiempo medio por jugada">t/jug</th>
                  <th class="px-4 py-2 text-right" title="Derrotas por tiempo">⏱</th>
                </tr>
              </thead>
              <tbody>
                @for (r of rows(); track r.id) {
                  <tr class="border-b border-white/5 last:border-0">
                    <td class="px-4 py-2 font-mono text-zinc-400">{{ r.rank }}</td>
                    <td class="py-2 font-medium">{{ r.contender.label }}</td>
                    <td class="py-2 text-right font-mono font-bold text-white">{{ r.points | number: '1.0-1' }}</td>
                    <td class="py-2 text-right font-mono">{{ r.played }}</td>
                    <td class="py-2 text-right font-mono text-emerald-300">{{ r.wins }}</td>
                    <td class="py-2 text-right font-mono">{{ r.draws }}</td>
                    <td class="py-2 text-right font-mono text-rose-300">{{ r.losses }}</td>
                    <td class="py-2 text-right font-mono">{{ r.sonnebornBerger | number: '1.0-2' }}</td>
                    <td class="py-2 text-right font-mono">{{ r.validMovePct === null ? '—' : (r.validMovePct | number: '1.0-0') + '%' }}</td>
                    <td class="py-2 text-right font-mono">{{ r.avgThinkMs === null ? '—' : (r.avgThinkMs / 1000 | number: '1.1-1') + ' s' }}</td>
                    <td class="px-4 py-2 text-right font-mono">{{ r.timeLosses }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>

          <!-- Tabla cruzada -->
          @if (t.participants.length > 2) {
            <section class="glass overflow-x-auto">
              <h2 class="font-semibold px-4 pt-4 pb-2">Tabla cruzada</h2>
              <table class="text-sm mx-4 mb-4">
                <thead>
                  <tr>
                    <th></th>
                    @for (c of t.participants; track c.id; let i = $index) { <th class="px-3 py-1 text-xs text-zinc-400 font-mono" [title]="c.label">{{ i + 1 }}</th> }
                  </tr>
                </thead>
                <tbody>
                  @for (a of t.participants; track a.id; let i = $index) {
                    <tr>
                      <th class="pr-3 py-1 text-left text-xs font-medium whitespace-nowrap"><span class="text-zinc-500 font-mono">{{ i + 1 }}.</span> {{ a.label }}</th>
                      @for (b of t.participants; track b.id) {
                        <td class="px-3 py-1 text-center font-mono border border-white/5" [class.bg-white/10]="a.id === b.id">
                          {{ a.id === b.id ? '' : cross().get(a.id)?.get(b.id)?.join(' ') }}
                        </td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </section>
          }

          <!-- Rondas -->
          <section class="glass">
            <h2 class="font-semibold px-4 pt-4 pb-2">Partidas</h2>
            <ul class="divide-y divide-white/5">
              @for (p of t.pairings; track p.id) {
                <li class="px-4 py-2.5 flex items-center gap-3 text-sm">
                  <span class="w-14 text-xs text-zinc-500">R{{ p.round }}</span>
                  <span class="flex-1 min-w-0 truncate">
                    <span class="inline-block size-2.5 rounded-full bg-zinc-100 mr-1 align-middle"></span>{{ name(p.white) }}
                    <span class="text-zinc-500 mx-1">vs</span>
                    <span class="inline-block size-2.5 rounded-full bg-zinc-900 border border-white/30 mr-1 align-middle"></span>{{ name(p.black) }}
                  </span>
                  @if (p.result) {
                    <span class="font-mono font-bold w-16 text-right" [class]="resultTone(p.result)">{{ p.result }}</span>
                    <span class="hidden sm:inline w-40 text-xs text-zinc-400 truncate">{{ termLabel(p.termination) }} · {{ p.plies }} pl</span>
                    <button type="button" class="btn btn-ghost !p-1.5" (click)="downloadOne(p)" aria-label="Descargar PGN de la partida">
                      <svg lucideDownload class="size-3.5"></svg>
                    </button>
                  } @else if (runner.livePairingId() === p.id) {
                    <span class="chip text-amber-300 border-amber-400/30"><span class="size-1.5 rounded-full bg-amber-300 animate-pulse"></span> en juego</span>
                  } @else {
                    <span class="text-xs text-zinc-500">pendiente</span>
                  }
                </li>
              }
            </ul>
          </section>
        </div>
      </div>
    }
  `,
})
export class TournamentDetailPage {
  readonly id = input.required<string>();
  readonly runner = inject(TournamentRunner);

  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly formatLabel = FORMAT_LABEL;
  readonly statusLabel = { pending: 'Pendiente', running: 'En curso', paused: 'Pausado', finished: 'Terminado' };

  readonly t = computed(() => {
    const t = this.runner.tournament();
    return t && t.id === this.id() ? t : null;
  });
  readonly rows = computed(() => (this.t() ? standings(this.t()!) : []));
  readonly cross = computed(() => (this.t() ? crosstable(this.t()!) : new Map<string, Map<string, string[]>>()));
  readonly prog = computed(() => (this.t() ? progress(this.t()!) : { done: 0, total: 0 }));
  readonly tc = computed(() => (this.t() ? tcLabel(this.t()!.timeControl) : ''));
  readonly category = computed(() => (this.t() ? CATEGORY_LABEL[categoryOf(this.t()!.timeControl)] : ''));
  readonly showLive = computed(() => !!this.runner.live() || this.t()?.status !== 'finished');
  readonly leaders = computed(() => this.rows().filter((r) => r.rank === 1));
  readonly leaderNames = computed(() => this.leaders().map((r) => r.contender.label).join(' y '));
  readonly livePairing = computed(() => this.t()?.pairings.find((p) => p.id === this.runner.livePairingId()) ?? null);
  readonly statusTone = computed(
    () =>
      ({ running: 'text-amber-300 border-amber-400/30', finished: 'text-emerald-300 border-emerald-400/30', paused: 'text-cyan-300 border-cyan-400/30', pending: 'text-zinc-300' })[
        this.t()?.status ?? 'pending'
      ],
  );

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.load(id));
    });
  }

  private async load(id: string): Promise<void> {
    this.loading.set(true);
    this.loadError.set(null);
    try {
      await this.runner.load(id);
    } catch (e) {
      this.loadError.set(e instanceof ApiError ? e.message : 'No se pudo cargar el torneo.');
    } finally {
      this.loading.set(false);
    }
  }

  name(id: string): string {
    return this.runner.contender(id)?.label ?? id;
  }

  termLabel(t: Termination | null | undefined): string {
    return t ? TERMINATION_LABEL[t] : '';
  }

  resultTone(r: GameResult): string {
    return r === '1/2-1/2' ? 'text-zinc-300' : 'text-white';
  }

  king(fen: string, side: 'w' | 'b'): string | null {
    return kingSquare(fen, side);
  }

  downloadOne(p: Pairing): void {
    if (p.pgn) downloadText(`${slug(this.t()!.name)}-r${p.round}-${slug(this.name(p.white))}-vs-${slug(this.name(p.black))}.pgn`, p.pgn);
  }

  downloadAll(): void {
    const t = this.t();
    if (!t) return;
    const pgns = t.pairings.filter((p) => p.pgn).map((p) => p.pgn!.trim());
    downloadText(`${slug(t.name)}.pgn`, pgns.join('\n\n') + '\n');
  }
}
