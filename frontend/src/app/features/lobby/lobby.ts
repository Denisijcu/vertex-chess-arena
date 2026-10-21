import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  LucideArrowLeftRight,
  LucideBot,
  LucideCpu,
  LucidePlay,
  LucideRefreshCw,
  LucideTrophy,
  LucideUser,
} from '@lucide/angular';
import { GameSession } from '../../core/game-session.service';
import { Contender, EngineMode, TimeControl } from '../../core/models';
import { ApiService } from '../../core/api.service';
import { HUMAN, MODE_HINT, MODE_LABEL, PlayersStore } from '../../core/players.store';
import { TimeControlPickerComponent } from '../../shared/time-control-picker';

type Kind = 'human-ai' | 'ai-ai';

@Component({
  selector: 'vx-lobby',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    RouterLink,
    TimeControlPickerComponent,
    LucideArrowLeftRight,
    LucideBot,
    LucideCpu,
    LucidePlay,
    LucideRefreshCw,
    LucideTrophy,
    LucideUser,
  ],
  template: `
    <section class="grid lg:grid-cols-[1.1fr_1fr] gap-6 items-start">
      <!-- Presentación + plantel -->
      <div class="space-y-6">
        <div class="pt-2">
          <span class="chip text-cyan-300 border-cyan-400/30">Laboratorio Vertex Coders</span>
          <h1 class="mt-4 text-4xl md:text-5xl font-extrabold tracking-tight leading-tight">
            Modelos afinados, <span class="bg-gradient-to-r from-cyan-300 to-violet-400 bg-clip-text text-transparent">reloj en marcha</span>.
          </h1>
          <p class="mt-4 text-zinc-400 max-w-xl">
            Qwen 2.5 y Gemma 2, afinados con el mismo dataset de ajedrez, compitiendo en bullet, blitz,
            rápidas y clásicas. Juega contra ellos o ponlos a pelear en un torneo con clasificación oficial.
          </p>
        </div>

        <div class="glass p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="font-semibold">Plantel</h2>
            <button type="button" class="btn btn-ghost !py-1.5 !px-3 text-xs" (click)="players.load(true)" [disabled]="players.loading()">
              <svg lucideRefreshCw class="size-3.5"></svg> Actualizar
            </button>
          </div>
          @if (players.loading() && !players.players().length) {
            <div class="grid sm:grid-cols-2 gap-3">
              @for (i of [1, 2, 3, 4]; track i) { <div class="skeleton h-20"></div> }
            </div>
          } @else if (players.error()) {
            <div class="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
              <p>{{ players.error() }}</p>
              <button type="button" class="btn btn-ghost mt-3" (click)="players.load(true)">Reintentar</button>
            </div>
          } @else {
            <div class="grid sm:grid-cols-2 gap-3">
              @for (p of players.players(); track p.model) {
                <div class="rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
                  <div class="flex items-center gap-2">
                    @if (p.kind === 'engine') { <svg lucideCpu class="size-4 text-amber-300"></svg> }
                    @else { <svg lucideBot class="size-4" [class]="p.family === 'gemma' ? 'text-violet-300' : 'text-cyan-300'"></svg> }
                    <span class="font-semibold text-sm">{{ p.name }}</span>
                    <span class="chip ml-auto" [class]="p.available ? 'text-emerald-300 border-emerald-400/30' : 'text-zinc-500'">
                      {{ p.available ? 'listo' : 'no instalado' }}
                    </span>
                  </div>
                  <p class="text-xs text-zinc-400 mt-2 leading-relaxed">{{ p.description }}</p>
                  <p class="text-[11px] text-zinc-500 mt-1 font-mono">{{ p.model }}</p>
                </div>
              }
            </div>
          }
        </div>

        <div class="glass p-5">
          <h2 class="font-semibold mb-3">Modos de juego de la IA</h2>
          <dl class="space-y-2 text-sm">
            @for (m of modes; track m) {
              <div class="flex gap-3">
                <dt class="w-32 shrink-0 text-cyan-300 font-medium">{{ modeLabel[m] }}</dt>
                <dd class="text-zinc-400">{{ modeHint[m] }}</dd>
              </div>
            }
          </dl>
        </div>
      </div>

      <!-- Configuración de partida -->
      <form class="glass p-5 md:p-6 space-y-6 order-first lg:order-none" (submit)="$event.preventDefault(); start()">
        <div class="grid grid-cols-2 gap-2 p-1 rounded-xl bg-black/40 border border-white/10" role="tablist">
          <button type="button" role="tab" [attr.aria-selected]="kind() === 'human-ai'" (click)="kind.set('human-ai')"
            class="rounded-lg py-2 text-sm font-semibold flex items-center justify-center gap-2"
            [class]="kind() === 'human-ai' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white'">
            <svg lucideUser class="size-4"></svg> Tú vs IA
          </button>
          <button type="button" role="tab" [attr.aria-selected]="kind() === 'ai-ai'" (click)="kind.set('ai-ai')"
            class="rounded-lg py-2 text-sm font-semibold flex items-center justify-center gap-2"
            [class]="kind() === 'ai-ai' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white'">
            <svg lucideBot class="size-4"></svg> IA vs IA
          </button>
        </div>

        @if (options().length === 0 && !players.loading()) {
          <p class="text-sm text-amber-200 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3">
            @if (api.isPublic) {
              El servidor de los modelos en Hugging Face está arrancando. Espera un minuto y recarga la página.
            } @else {
              No hay modelos disponibles. Arranca Ollama y crea los modelos (ver README); el motor del árbitro siempre está disponible si la API corre.
            }
          </p>
        }
        @if (api.isPublic) {
          <p class="text-xs text-zinc-400 rounded-xl border border-white/10 p-3">
            Los modelos corren en una GPU compartida de Hugging Face con una cuota diaria por visitante
            (unos 2 minutos sin cuenta). Una partida contra una IA cabe de sobra; una entre dos IA gasta el doble.
            El <strong>Motor del árbitro</strong> no usa GPU.
          </p>
        }

        @if (kind() === 'human-ai') {
          <div class="grid sm:grid-cols-2 gap-4">
            <label class="sm:col-span-2">
              <span class="label">Rival</span>
              <select class="field" [ngModel]="rivalId()" (ngModelChange)="rivalId.set($event)" name="rival">
                @for (o of options(); track o.id) { <option [value]="o.id">{{ o.label }}</option> }
              </select>
            </label>
            <fieldset class="sm:col-span-2">
              <legend class="label">Tu color</legend>
              <div class="grid grid-cols-3 gap-2">
                @for (c of colorChoices; track c.value) {
                  <button type="button" (click)="color.set(c.value)" class="rounded-lg border py-2 text-sm"
                    [class]="color() === c.value ? 'border-cyan-400/60 bg-cyan-400/10 text-white' : 'border-white/10 text-zinc-300 hover:bg-white/5'">
                    {{ c.label }}
                  </button>
                }
              </div>
            </fieldset>
          </div>
        } @else {
          <div class="grid grid-cols-[1fr_auto_1fr] items-end gap-3">
            <label>
              <span class="label">Blancas</span>
              <select class="field" [ngModel]="whiteId()" (ngModelChange)="whiteId.set($event)" name="white">
                @for (o of options(); track o.id) { <option [value]="o.id">{{ o.label }}</option> }
              </select>
            </label>
            <button type="button" class="btn btn-ghost !px-2.5 mb-0.5" (click)="swap()" aria-label="Intercambiar colores">
              <svg lucideArrowLeftRight class="size-4"></svg>
            </button>
            <label>
              <span class="label">Negras</span>
              <select class="field" [ngModel]="blackId()" (ngModelChange)="blackId.set($event)" name="black">
                @for (o of options(); track o.id) { <option [value]="o.id">{{ o.label }}</option> }
              </select>
            </label>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <label>
              <span class="label">Límite de jugadas</span>
              <select class="field" [ngModel]="maxPlies()" (ngModelChange)="maxPlies.set(+$event)" name="maxPlies">
                <option [value]="200">100 jugadas</option>
                <option [value]="300">150 jugadas</option>
                <option [value]="400">200 jugadas</option>
                <option [value]="0">Sin límite</option>
              </select>
            </label>
            <label>
              <span class="label">Pausa visual</span>
              <select class="field" [ngModel]="delay()" (ngModelChange)="delay.set(+$event)" name="delay">
                <option [value]="0">Sin pausa</option>
                <option [value]="400">0,4 s</option>
                <option [value]="1000">1 s</option>
              </select>
            </label>
          </div>
        }

        <div>
          <span class="label">Ritmo</span>
          <vx-time-control-picker [(value)]="timeControl" />
        </div>

        <button type="submit" class="btn btn-primary w-full !py-3 text-base" [disabled]="!canStart()">
          <svg lucidePlay class="size-5"></svg> Empezar partida
        </button>
        <a routerLink="/torneos" class="btn btn-ghost w-full">
          <svg lucideTrophy class="size-4"></svg> Organizar un torneo
        </a>
      </form>
    </section>
  `,
})
export class LobbyPage implements OnInit {
  readonly players = inject(PlayersStore);
  readonly api = inject(ApiService);
  private readonly session = inject(GameSession);
  private readonly router = inject(Router);

  readonly modes: EngineMode[] = ['pure', 'arbiter', 'engine'];
  readonly modeLabel = MODE_LABEL;
  readonly modeHint = MODE_HINT;
  readonly colorChoices = [
    { value: 'w' as const, label: 'Blancas' },
    { value: 'random' as const, label: 'Al azar' },
    { value: 'b' as const, label: 'Negras' },
  ];

  readonly kind = signal<Kind>('human-ai');
  readonly rivalId = signal('');
  readonly whiteId = signal('');
  readonly blackId = signal('');
  readonly color = signal<'w' | 'b' | 'random'>('w');
  readonly maxPlies = signal(300);
  readonly delay = signal(400);
  // 3 minutos sin incremento: el reloj solo baja (como "3 min" en chess.com).
  readonly timeControl = signal<TimeControl>({ baseMs: 180_000, incMs: 0 });

  readonly options = computed(() => this.players.contenderOptions());
  readonly canStart = computed(() => {
    const ids = new Set(this.options().map((o) => o.id));
    return this.kind() === 'human-ai'
      ? ids.has(this.rivalId())
      : ids.has(this.whiteId()) && ids.has(this.blackId());
  });

  async ngOnInit(): Promise<void> {
    await this.players.load();
    this.applyDefaults();
  }

  private applyDefaults(): void {
    const opts = this.options();
    if (!opts.length) return;
    const byId = (id: string) => opts.find((o) => o.id === id)?.id;
    const qwen = byId('vertexqwen-v3:pure') ?? byId('vertexqwen:pure');
    const gemma = byId('vertexgemma:pure');
    if (!this.rivalId()) this.rivalId.set(qwen ?? gemma ?? opts[0].id);
    if (!this.whiteId()) this.whiteId.set(qwen ?? opts[0].id);
    if (!this.blackId()) this.blackId.set(gemma ?? opts[Math.min(1, opts.length - 1)].id);
  }

  swap(): void {
    const w = this.whiteId();
    this.whiteId.set(this.blackId());
    this.blackId.set(w);
  }

  start(): void {
    if (!this.canStart()) return;
    const find = (id: string) => this.options().find((o) => o.id === id) as Contender;
    let white: Contender;
    let black: Contender;
    if (this.kind() === 'human-ai') {
      const rival = find(this.rivalId());
      const side = this.color() === 'random' ? (Math.random() < 0.5 ? 'w' : 'b') : this.color();
      [white, black] = side === 'w' ? [HUMAN, rival] : [rival, HUMAN];
    } else {
      white = find(this.whiteId());
      black = { ...find(this.blackId()) };
      if (white.id === black.id) black = { ...black, id: black.id + ':2' };
    }
    this.session.newGame({
      white,
      black,
      timeControl: this.timeControl(),
      maxPlies: this.kind() === 'ai-ai' ? this.maxPlies() : 0,
      moveDelayMs: this.kind() === 'ai-ai' ? this.delay() : 0,
    });
    void this.router.navigate(['/partida']);
  }
}
