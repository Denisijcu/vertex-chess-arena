import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { LucideBot, LucideCpu, LucideUser } from '@lucide/angular';
import { Contender, SideStats } from '../core/models';
import { MODE_LABEL } from '../core/players.store';
import { ClockComponent } from './clock';

/** Franja de un jugador: avatar, nombre, modo, telemetría y reloj. */
@Component({
  selector: 'vx-player-strip',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ClockComponent, DecimalPipe, LucideBot, LucideCpu, LucideUser],
  template: `
    <div class="flex items-center gap-3 py-2">
      <div class="size-11 shrink-0 rounded-xl grid place-items-center border" [class]="avatarTone()">
        @switch (avatarKind()) {
          @case ('human') { <svg lucideUser class="size-5"></svg> }
          @case ('engine') { <svg lucideCpu class="size-5"></svg> }
          @default { <svg lucideBot class="size-5"></svg> }
        }
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 min-w-0">
          <span class="size-3 rounded-full border border-white/30 shrink-0" [class]="side() === 'w' ? 'bg-zinc-100' : 'bg-zinc-900'" [attr.aria-label]="side() === 'w' ? 'Blancas' : 'Negras'"></span>
          <span class="font-semibold truncate">{{ contender().label }}</span>
          @if (thinking()) {
            <span class="chip text-cyan-300 border-cyan-400/30">
              <span class="size-1.5 rounded-full bg-cyan-300 animate-ping"></span> pensando
            </span>
          }
        </div>
        <div class="text-xs text-zinc-400 mt-0.5 flex flex-wrap gap-x-3">
          @if (contender().kind === 'ai') {
            <span>{{ modeLabel() }}</span>
            @if (stats().moves > 0) {
              @if (contender().mode !== 'engine') {
                <span>Válidas {{ validPct() | number: '1.0-0' }}%</span>
              }
              <span>Media {{ avgSec() | number: '1.1-1' }} s</span>
            }
          } @else {
            <span>Humano</span>
          }
        </div>
      </div>
      <vx-clock [ms]="timeMs()" [active]="active()" [baseMs]="baseMs()" [sideName]="side() === 'w' ? 'blancas' : 'negras'" />
    </div>
  `,
})
export class PlayerStripComponent {
  readonly contender = input.required<Contender>();
  readonly side = input.required<'w' | 'b'>();
  readonly timeMs = input.required<number>();
  readonly baseMs = input(60_000);
  readonly active = input(false);
  readonly thinking = input(false);
  readonly stats = input<SideStats>({ moves: 0, clean: 0, fallback: 0, thinkMs: 0 });

  readonly avatarKind = computed(() =>
    this.contender().kind === 'human' ? 'human' : this.contender().mode === 'engine' ? 'engine' : 'ai',
  );
  readonly avatarTone = computed(() => {
    const fam = this.contender().family;
    if (this.contender().kind === 'human') return 'bg-emerald-400/10 border-emerald-400/30 text-emerald-300';
    if (fam === 'gemma') return 'bg-violet-400/10 border-violet-400/30 text-violet-300';
    if (fam === 'engine') return 'bg-amber-400/10 border-amber-400/30 text-amber-300';
    return 'bg-cyan-400/10 border-cyan-400/30 text-cyan-300';
  });
  readonly modeLabel = computed(() => MODE_LABEL[this.contender().mode ?? 'pure']);
  readonly validPct = computed(() => {
    const s = this.stats();
    const judged = s.clean + s.fallback;
    return judged ? (100 * s.clean) / judged : 0;
  });
  readonly avgSec = computed(() => (this.stats().moves ? this.stats().thinkMs / this.stats().moves / 1000 : 0));
}
