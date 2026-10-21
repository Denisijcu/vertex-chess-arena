import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { LucideHistory, LucideSwords, LucideTrophy, LucideZap } from '@lucide/angular';
import { ApiService } from './core/api.service';
import { TournamentRunner } from './core/tournament-runner.service';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, LucideSwords, LucideTrophy, LucideHistory, LucideZap],
  template: `
    <a href="#contenido" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 btn btn-primary">Saltar al contenido</a>
    <header class="sticky top-0 z-30 border-b border-white/10 bg-black/70 backdrop-blur-md">
      <nav class="mx-auto max-w-7xl px-4 h-14 sm:h-16 flex items-center gap-3 sm:gap-6" aria-label="Principal">
        <a routerLink="/" class="flex items-center gap-2 sm:gap-2.5 font-extrabold tracking-tight text-base sm:text-lg shrink-0">
          <img src="favicon.svg" alt="" width="30" height="30" class="rounded-lg" />
          <span>Vertex <span class="bg-gradient-to-r from-cyan-300 to-violet-400 bg-clip-text text-transparent">Chess Arena</span></span>
        </a>
        <div class="hidden md:flex items-center gap-1 text-sm">
          @for (l of links; track l.path) {
            <a [routerLink]="l.path" routerLinkActive="bg-white/10 text-white" [routerLinkActiveOptions]="{ exact: l.path === '/' }"
               class="px-3 py-2 rounded-lg text-zinc-300 hover:text-white hover:bg-white/5 flex items-center gap-2">
              @switch (l.icon) {
                @case ('zap') { <svg lucideZap class="size-4"></svg> }
                @case ('swords') { <svg lucideSwords class="size-4"></svg> }
                @case ('trophy') { <svg lucideTrophy class="size-4"></svg> }
                @case ('history') { <svg lucideHistory class="size-4"></svg> }
              }
              {{ l.label }}
            </a>
          }
        </div>
        <div class="ml-auto flex items-center gap-3 text-xs">
          @if (runner.tournament()?.status === 'running') {
            <a [routerLink]="['/torneos', runner.tournament()!.id]" class="chip text-amber-300 border-amber-400/30 hover:bg-amber-400/10">
              <span class="size-1.5 rounded-full bg-amber-300 animate-pulse"></span> Torneo en curso
            </a>
          }
          <span class="chip whitespace-nowrap" [class]="ollamaTone()" role="status" [attr.aria-label]="label + ' ' + ollamaText()">
            <span class="size-1.5 rounded-full" [class]="ollamaDot()"></span>
            <span class="hidden sm:inline">{{ label }} {{ ollamaText() }}</span><span class="sm:hidden">{{ label }}</span>
          </span>
        </div>
      </nav>
      <div class="md:hidden flex border-t border-white/5 text-xs">
        @for (l of links; track l.path) {
          <a [routerLink]="l.path" routerLinkActive="text-cyan-300" [routerLinkActiveOptions]="{ exact: l.path === '/' }" class="flex-1 text-center py-2 text-zinc-400">{{ l.label }}</a>
        }
      </div>
    </header>

    <main id="contenido" class="mx-auto max-w-7xl px-4 py-6 md:py-8">
      <router-outlet />
    </main>

    <footer class="mx-auto max-w-7xl px-4 py-8 mt-8 border-t border-white/10 text-xs text-zinc-500 flex flex-col md:flex-row gap-2 md:items-center md:justify-between">
      <span>© {{ year }} Vertex Coders LLC — Miami, FL · Vertex Chess Arena</span>
      <span>
        Tablero <a class="underline hover:text-zinc-300" href="https://github.com/shaack/cm-chessboard" target="_blank" rel="noopener">cm-chessboard</a> (MIT) ·
        Piezas <a class="underline hover:text-zinc-300" href="https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces/Standard" target="_blank" rel="noopener">Cburnett</a>
        (<a class="underline hover:text-zinc-300" href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener">CC BY-SA 3.0</a>) ·
        Reglas <a class="underline hover:text-zinc-300" href="https://github.com/jhlywa/chess.js" target="_blank" rel="noopener">chess.js</a>
      </span>
    </footer>
  `,
})
export class App implements OnInit {
  private readonly api = inject(ApiService);
  readonly runner = inject(TournamentRunner);
  private readonly destroyRef = inject(DestroyRef);
  readonly year = new Date().getFullYear();
  readonly label = this.api.backendLabel;

  readonly links = [
    { path: '/', label: 'Arena', icon: 'zap' },
    { path: '/partida', label: 'Partida', icon: 'swords' },
    { path: '/torneos', label: 'Torneos', icon: 'trophy' },
    { path: '/historial', label: 'Historial', icon: 'history' },
  ];

  readonly ollamaText = computed(() => ({ up: 'conectado', down: 'apagado', unknown: 'sin API' })[this.api.ollamaStatus()]);
  readonly ollamaTone = computed(
    () =>
      ({
        up: 'text-emerald-300 border-emerald-400/30',
        down: 'text-rose-300 border-rose-400/30',
        unknown: 'text-zinc-400',
      })[this.api.ollamaStatus()],
  );
  readonly ollamaDot = computed(
    () => ({ up: 'bg-emerald-400', down: 'bg-rose-400', unknown: 'bg-zinc-500' })[this.api.ollamaStatus()],
  );

  ngOnInit(): void {
    const poll = () => void this.api.health().catch(() => undefined);
    poll();
    // En la versión pública /health no gasta GPU, pero no hace falta preguntar tan seguido.
    const id = setInterval(poll, this.api.isPublic ? 60_000 : 15_000);
    this.destroyRef.onDestroy(() => clearInterval(id));
  }
}
