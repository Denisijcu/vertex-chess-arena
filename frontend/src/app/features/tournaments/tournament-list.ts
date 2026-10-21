import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { LucidePlus, LucideTrophy } from '@lucide/angular';
import { ApiError, ApiService } from '../../core/api.service';
import { TimeControl, Tournament, TournamentFormat } from '../../core/models';
import { PlayersStore } from '../../core/players.store';
import { CATEGORY_LABEL, categoryOf, tcLabel } from '../../core/time-controls';
import { FORMAT_LABEL } from '../../core/tournament-logic';
import { TournamentRunner } from '../../core/tournament-runner.service';
import { TimeControlPickerComponent } from '../../shared/time-control-picker';

type Summary = Pick<Tournament, 'id' | 'name' | 'format' | 'status' | 'createdAt' | 'timeControl'> & { players: number };

@Component({
  selector: 'vx-tournament-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, DatePipe, TimeControlPickerComponent, LucidePlus, LucideTrophy],
  template: `
    <div class="grid lg:grid-cols-[1fr_1.1fr] gap-6 items-start">
      <section>
        <h1 class="text-3xl font-extrabold tracking-tight flex items-center gap-3">
          <svg lucideTrophy class="size-7 text-amber-300"></svg> Torneos
        </h1>
        <p class="text-zinc-400 mt-2">Match a varias partidas o todos contra todos, con relojes y clasificación con desempate Sonneborn-Berger.</p>

        <div class="mt-6 space-y-3">
          @if (loading()) {
            @for (i of [1, 2, 3]; track i) { <div class="skeleton h-20"></div> }
          } @else if (error()) {
            <div class="glass p-4 border-rose-500/30 text-sm text-rose-200">
              {{ error() }} <button type="button" class="btn btn-ghost ml-2" (click)="load()">Reintentar</button>
            </div>
          } @else if (list().length === 0) {
            <div class="glass p-8 text-center text-zinc-400">Todavía no hay torneos. Crea el primero con el formulario.</div>
          } @else {
            @for (t of list(); track t.id) {
              <a [routerLink]="['/torneos', t.id]" class="glass p-4 flex items-center gap-4 hover:border-cyan-400/40 transition-colors">
                <div class="flex-1 min-w-0">
                  <p class="font-semibold truncate">{{ t.name }}</p>
                  <p class="text-xs text-zinc-400 mt-1">
                    {{ formatLabel[t.format] }} · {{ t.players }} jugadores ·
                    <span class="font-mono">{{ tc(t.timeControl) }}</span> {{ cat(t.timeControl) }} ·
                    {{ t.createdAt | date: 'd MMM y, HH:mm' }}
                  </p>
                </div>
                <span class="chip" [class]="statusTone(t.status)">{{ statusLabel[t.status] }}</span>
              </a>
            }
          }
        </div>
      </section>

      <form class="glass p-5 md:p-6 space-y-5" (submit)="$event.preventDefault(); create()">
        <h2 class="text-lg font-semibold flex items-center gap-2"><svg lucidePlus class="size-5 text-cyan-300"></svg> Nuevo torneo</h2>
        <label class="block">
          <span class="label">Nombre</span>
          <input class="field" name="name" maxlength="80" [ngModel]="name()" (ngModelChange)="name.set($event)" placeholder="Copa Vertex — Qwen vs Gemma" />
        </label>
        <div>
          <span class="label">Formato</span>
          <div class="grid grid-cols-3 gap-2">
            @for (f of formats; track f) {
              <button type="button" (click)="format.set(f)" class="rounded-lg border px-2 py-2 text-sm"
                [class]="format() === f ? 'border-cyan-400/60 bg-cyan-400/10 text-white' : 'border-white/10 text-zinc-300 hover:bg-white/5'">
                {{ formatLabel[f] }}
              </button>
            }
          </div>
        </div>

        @if (format() === 'match') {
          <label class="block">
            <span class="label">Partidas del match (colores alternos)</span>
            <select class="field" name="games" [ngModel]="matchGames()" (ngModelChange)="matchGames.set(+$event)">
              @for (n of [2, 4, 6, 8, 10, 20]; track n) { <option [value]="n">{{ n }} partidas</option> }
            </select>
          </label>
        }

        <fieldset>
          <legend class="label">Participantes {{ format() === 'match' ? '(exactamente 2)' : '(mínimo 2)' }}</legend>
          @if (players.loading() && !options().length) {
            <div class="skeleton h-24"></div>
          } @else if (!options().length) {
            <p class="text-sm text-amber-200">No hay jugadores disponibles. ¿Está corriendo la API?</p>
          }
          <div class="grid sm:grid-cols-2 gap-2">
            @for (o of options(); track o.id) {
              <label class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer"
                [class]="selected().has(o.id) ? 'border-cyan-400/50 bg-cyan-400/10' : 'border-white/10 hover:bg-white/5'">
                <input type="checkbox" class="accent-cyan-400" [checked]="selected().has(o.id)" (change)="toggle(o.id)" />
                <span class="truncate">{{ o.label }}</span>
              </label>
            }
          </div>
        </fieldset>

        <div>
          <span class="label">Ritmo</span>
          <vx-time-control-picker [(value)]="timeControl" />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <label>
            <span class="label">Límite de jugadas</span>
            <select class="field" name="maxPlies" [ngModel]="maxPlies()" (ngModelChange)="maxPlies.set(+$event)">
              <option [value]="200">100 jugadas</option>
              <option [value]="300">150 jugadas</option>
              <option [value]="400">200 jugadas</option>
              <option [value]="0">Sin límite</option>
            </select>
          </label>
          <label>
            <span class="label">Pausa visual</span>
            <select class="field" name="delay" [ngModel]="delay()" (ngModelChange)="delay.set(+$event)">
              <option [value]="0">Sin pausa</option>
              <option [value]="300">0,3 s</option>
              <option [value]="800">0,8 s</option>
            </select>
          </label>
        </div>

        <p class="text-sm text-zinc-400">{{ summary() }}</p>
        @if (api.isPublic) {
          <p class="text-xs text-amber-200/90">
            Cada partida entre modelos gasta tu cuota diaria de GPU en Hugging Face (unos 2 minutos sin cuenta):
            un torneo largo no cabe en un día. Para verlos completos, abre la Copa Vertex Verano 2026 de la lista,
            que ya está jugada. Con el Motor del árbitro no se gasta GPU.
          </p>
        }
        @if (createError()) { <p class="text-sm text-rose-300" role="alert">{{ createError() }}</p> }
        <button type="submit" class="btn btn-primary w-full !py-3" [disabled]="!valid() || creating()">
          {{ creating() ? 'Creando…' : 'Crear torneo' }}
        </button>
      </form>
    </div>
  `,
})
export class TournamentListPage implements OnInit {
  readonly api = inject(ApiService);
  private readonly runner = inject(TournamentRunner);
  private readonly router = inject(Router);
  readonly players = inject(PlayersStore);

  readonly formatLabel = FORMAT_LABEL;
  readonly formats: TournamentFormat[] = ['match', 'round-robin', 'double-round-robin'];
  readonly statusLabel = { pending: 'Pendiente', running: 'En curso', paused: 'Pausado', finished: 'Terminado' };

  readonly list = signal<Summary[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly name = signal('Copa Vertex');
  readonly format = signal<TournamentFormat>('match');
  readonly matchGames = signal(4);
  readonly selected = signal<Set<string>>(new Set());
  readonly timeControl = signal<TimeControl>({ baseMs: 60_000, incMs: 0 });
  readonly maxPlies = signal(300);
  readonly delay = signal(0);
  readonly creating = signal(false);
  readonly createError = signal<string | null>(null);

  readonly options = computed(() => this.players.contenderOptions());
  readonly valid = computed(() => {
    const n = this.selected().size;
    return this.format() === 'match' ? n === 2 : n >= 2;
  });
  readonly summary = computed(() => {
    const n = this.selected().size;
    if (n < 2) return 'Elige los participantes.';
    const games =
      this.format() === 'match' ? this.matchGames() : this.format() === 'round-robin' ? (n * (n - 1)) / 2 : n * (n - 1);
    return `${games} partidas en total.`;
  });

  async ngOnInit(): Promise<void> {
    void this.players.load();
    await this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      this.list.set(await this.api.tournaments());
    } catch (e) {
      this.error.set(e instanceof ApiError ? e.message : 'No se pudieron cargar los torneos.');
    } finally {
      this.loading.set(false);
    }
  }

  toggle(id: string): void {
    const s = new Set(this.selected());
    if (s.has(id)) s.delete(id);
    else s.add(id);
    this.selected.set(s);
  }

  tc(t: TimeControl): string {
    return tcLabel(t);
  }
  cat(t: TimeControl): string {
    return CATEGORY_LABEL[categoryOf(t)];
  }
  statusTone(s: string): string {
    return (
      { running: 'text-amber-300 border-amber-400/30', finished: 'text-emerald-300 border-emerald-400/30', paused: 'text-cyan-300 border-cyan-400/30' } as Record<string, string>
    )[s] ?? 'text-zinc-400';
  }

  async create(): Promise<void> {
    if (!this.valid()) return;
    this.creating.set(true);
    this.createError.set(null);
    let created: { id: string } | null = null;
    try {
      const participants = this.options().filter((o) => this.selected().has(o.id));
      created = await this.runner.create({
        name: this.name(),
        format: this.format(),
        participants,
        timeControl: this.timeControl(),
        maxPlies: this.maxPlies(),
        moveDelayMs: this.delay(),
        matchGames: this.matchGames(),
      });
    } catch (e) {
      this.createError.set(
        e instanceof ApiError ? e.message : `No se pudo crear el torneo: ${e instanceof Error ? e.message : String(e)}`,
      );
    } finally {
      this.creating.set(false);
    }
    if (!created) return;
    // El torneo ya está guardado: un fallo al cambiar de pantalla no es un fallo al crearlo.
    const ok = await this.router.navigate(['/torneos', created.id]).catch(() => false);
    if (!ok) window.location.assign(`/torneos/${created.id}`);
  }
}
