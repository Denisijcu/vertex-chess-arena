import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Chess } from 'chess.js';
import {
  LucideChevronLeft,
  LucideChevronRight,
  LucideChevronsLeft,
  LucideChevronsRight,
  LucideDownload,
  LucideX,
} from '@lucide/angular';
import { ApiError, ApiService } from '../../core/api.service';
import { PlayedMove, SavedGameRecord, Side, TERMINATION_LABEL, Termination } from '../../core/models';
import { tcLabel, parsePgnTc } from '../../core/time-controls';
import { ChessboardComponent } from '../../shared/chessboard';
import { downloadText, kingSquare, slug } from '../../shared/board-utils';
import { MoveListComponent } from '../../shared/move-list';

interface Replay {
  record: SavedGameRecord;
  startFen: string;
  moves: PlayedMove[];
}

/** Convierte un PGN guardado en jugadas reproducibles (con los relojes de los comentarios %clk). */
export function parseReplay(record: SavedGameRecord): Replay | null {
  const chess = new Chess();
  try {
    chess.loadPgn(record.pgn);
  } catch {
    return null;
  }
  const comments = new Map(chess.getComments().map((c) => [c.fen, c.comment]));
  const history = chess.history({ verbose: true });
  const moves: PlayedMove[] = history.map((m, i) => {
    const comment = comments.get(m.after) ?? '';
    const clk = /\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]/.exec(comment);
    const emt = /\[%emt (\d+):(\d+):(\d+(?:\.\d+)?)\]/.exec(comment);
    const toMs = (r: RegExpExecArray | null) => (r ? ((+r[1] * 60 + +r[2]) * 60 + +r[3]) * 1000 : 0);
    return {
      ply: i + 1,
      side: m.color as Side,
      san: m.san,
      uci: m.from + m.to + (m.promotion ?? ''),
      from: m.from,
      to: m.to,
      fenAfter: m.after,
      clockAfterMs: toMs(clk),
      thinkMs: toMs(emt),
    };
  });
  return { record, startFen: history[0]?.before ?? new Chess().fen(), moves };
}

@Component({
  selector: 'vx-history',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DatePipe,
    RouterLink,
    ChessboardComponent,
    MoveListComponent,
    LucideChevronLeft,
    LucideChevronRight,
    LucideChevronsLeft,
    LucideChevronsRight,
    LucideDownload,
    LucideX,
  ],
  host: { '(document:keydown)': 'onKey($event)' },
  template: `
    <h1 class="text-3xl font-extrabold tracking-tight">Historial</h1>
    @if (api.isPublic) {
      <p class="text-zinc-400 mt-2">Tus partidas se guardan en este navegador. Las de la Copa Vertex Verano 2026 vienen incluidas.</p>
    } @else {
      <p class="text-zinc-400 mt-2">Todas las partidas terminadas (también quedan en <span class="font-mono text-zinc-300">logs/matches_history.pgn</span>).</p>
    }

    @if (replay(); as r) {
      <section class="mt-6 grid lg:grid-cols-[minmax(0,560px)_1fr] gap-6 items-start" aria-label="Visor de partida">
        <div class="glass p-2 sm:p-3 md:p-4 min-w-0">
          <div class="flex items-center justify-between px-1 pb-2 text-sm">
            <span class="truncate flex gap-1.5"><b>{{ r.record.white }}</b><span class="text-zinc-500">vs</span><b>{{ r.record.black }}</b></span>
            <button type="button" class="btn btn-ghost !p-1.5" (click)="close()" aria-label="Cerrar visor"><svg lucideX class="size-4"></svg></button>
          </div>
          <vx-chessboard [fen]="fenAt()" [lastMove]="lastAt()" [checkSquare]="checkAt()" />
          <div class="flex justify-center gap-2 mt-3">
            <button type="button" class="btn btn-ghost" (click)="ply.set(0)" aria-label="Inicio"><svg lucideChevronsLeft class="size-4"></svg></button>
            <button type="button" class="btn btn-ghost" (click)="step(-1)" aria-label="Anterior"><svg lucideChevronLeft class="size-4"></svg></button>
            <span class="font-mono text-sm self-center w-20 text-center">{{ ply() }}/{{ r.moves.length }}</span>
            <button type="button" class="btn btn-ghost" (click)="step(1)" aria-label="Siguiente"><svg lucideChevronRight class="size-4"></svg></button>
            <button type="button" class="btn btn-ghost" (click)="ply.set(r.moves.length)" aria-label="Final"><svg lucideChevronsRight class="size-4"></svg></button>
          </div>
          <p class="text-center text-xs text-zinc-500 mt-2">Usa ← y → para moverte por la partida.</p>
        </div>
        <div class="glass min-w-0">
          <div class="px-4 pt-4 pb-2 text-sm">
            <p class="font-mono text-xl font-bold">{{ r.record.result }}</p>
            <p class="text-zinc-400">{{ term(r.record.termination) }} · <span class="font-mono">{{ tc(r.record.time_control) }}</span> · {{ r.record.plies }} medias jugadas</p>
          </div>
          <vx-move-list [moves]="r.moves" [selectedPly]="ply()" [autoScroll]="false" maxHeight="28rem" (select)="ply.set($event)" />
        </div>
      </section>
    }

    <section class="mt-6 glass overflow-x-auto">
      @if (loading()) {
        <div class="p-4 space-y-2">@for (i of [1, 2, 3, 4]; track i) { <div class="skeleton h-10"></div> }</div>
      } @else if (error()) {
        <div class="p-6 text-sm text-rose-200">{{ error() }} <button type="button" class="btn btn-ghost ml-2" (click)="load()">Reintentar</button></div>
      } @else if (!games().length) {
        <div class="p-10 text-center text-zinc-400">Aún no hay partidas guardadas. <a routerLink="/" class="text-cyan-300 underline">Juega una</a>.</div>
      } @else {
        <table class="w-full text-sm">
          <thead class="text-xs text-zinc-400 text-left">
            <tr class="border-b border-white/10">
              <th class="px-4 py-2">Fecha</th><th class="py-2">Blancas</th><th class="py-2">Negras</th>
              <th class="py-2 text-center">Resultado</th><th class="py-2">Final</th><th class="py-2">Ritmo</th>
              <th class="py-2 text-right">Pl</th><th class="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            @for (g of games(); track g.id) {
              <tr class="border-b border-white/5 last:border-0 hover:bg-white/[0.03]">
                <td class="px-4 py-2 text-zinc-400 whitespace-nowrap">{{ g.saved_at | date: 'd MMM, HH:mm' }}</td>
                <td class="py-2">{{ g.white }}</td>
                <td class="py-2">{{ g.black }}</td>
                <td class="py-2 text-center font-mono font-bold">{{ g.result }}</td>
                <td class="py-2 text-zinc-400">{{ term(g.termination) }}</td>
                <td class="py-2 font-mono">{{ tc(g.time_control) }}</td>
                <td class="py-2 text-right font-mono">{{ g.plies }}</td>
                <td class="px-4 py-2 text-right whitespace-nowrap">
                  <button type="button" class="btn btn-ghost !py-1 !px-2.5 text-xs" (click)="open(g)">Ver</button>
                  <button type="button" class="btn btn-ghost !p-1.5 ml-1" (click)="download(g)" aria-label="Descargar PGN"><svg lucideDownload class="size-3.5"></svg></button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      }
    </section>
  `,
})
export class HistoryPage implements OnInit {
  readonly api = inject(ApiService);
  readonly games = signal<SavedGameRecord[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly replay = signal<Replay | null>(null);
  readonly ply = signal(0);

  readonly fenAt = computed(() => {
    const r = this.replay();
    if (!r) return new Chess().fen();
    const p = this.ply();
    return p === 0 ? r.startFen : r.moves[p - 1].fenAfter;
  });
  readonly lastAt = computed(() => {
    const r = this.replay();
    const p = this.ply();
    return r && p > 0 ? { from: r.moves[p - 1].from, to: r.moves[p - 1].to } : null;
  });
  readonly checkAt = computed(() => {
    const fen = this.fenAt();
    const c = new Chess(fen);
    return c.inCheck() ? kingSquare(fen, c.turn() as Side) : null;
  });

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      this.games.set(await this.api.games(200));
    } catch (e) {
      this.error.set(e instanceof ApiError ? e.message : 'No se pudo cargar el historial.');
    } finally {
      this.loading.set(false);
    }
  }

  open(g: SavedGameRecord): void {
    const r = parseReplay(g);
    if (!r) {
      this.error.set('No se pudo leer el PGN de esa partida.');
      return;
    }
    this.replay.set(r);
    this.ply.set(r.moves.length);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  close(): void {
    this.replay.set(null);
  }

  step(d: number): void {
    const r = this.replay();
    if (!r) return;
    this.ply.set(Math.max(0, Math.min(r.moves.length, this.ply() + d)));
  }

  tc(pgnTc: string): string {
    const t = parsePgnTc(pgnTc);
    return t ? tcLabel(t) : pgnTc;
  }

  term(t: string): string {
    return TERMINATION_LABEL[t as Termination] ?? t;
  }

  download(g: SavedGameRecord): void {
    downloadText(`${slug(g.white)}-vs-${slug(g.black)}-${g.id}.pgn`, g.pgn);
  }

  onKey(e: KeyboardEvent): void {
    if (!this.replay()) return;
    if (e.key === 'ArrowLeft') this.step(-1);
    if (e.key === 'ArrowRight') this.step(1);
  }
}
