import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { formatClock } from '../core/time-controls';

@Component({
  selector: 'vx-clock',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="font-mono tabular-nums font-bold rounded-xl px-4 py-2 text-3xl md:text-4xl transition-colors border"
      [class]="tone()"
      role="timer"
      [attr.aria-label]="'Reloj de ' + sideName() + ': ' + text()"
      [attr.aria-live]="active() && low() ? 'polite' : 'off'"
    >
      {{ text() }}
    </div>
  `,
})
export class ClockComponent {
  readonly ms = input.required<number>();
  readonly active = input(false);
  readonly sideName = input('');
  readonly baseMs = input(60_000);

  readonly text = computed(() => formatClock(this.ms()));
  /** Poco tiempo: menos de 10 s, o menos del 10 % de la base. */
  readonly low = computed(() => this.ms() < Math.max(10_000, this.baseMs() * 0.1));
  readonly tone = computed(() => {
    if (this.ms() <= 0) return 'bg-rose-500/20 border-rose-500/60 text-rose-200';
    if (this.active() && this.low()) return 'bg-rose-500/15 border-rose-500/50 text-rose-100 animate-pulse';
    if (this.active()) return 'bg-cyan-400/15 border-cyan-400/50 text-white shadow-[0_0_24px_rgb(34_211_238/0.25)]';
    return 'bg-zinc-900/70 border-white/10 text-zinc-400';
  });
}
