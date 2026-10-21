import { ChangeDetectionStrategy, Component, computed, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TimeControl } from '../core/models';
import { CATEGORY_LABEL, TIME_PRESETS, categoryOf, tcLabel } from '../core/time-controls';

/** Selector de ritmo: rejilla de ritmos estándar + personalizado (minutos + incremento). */
@Component({
  selector: 'vx-time-control-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  template: `
    <div class="grid grid-cols-3 sm:grid-cols-4 gap-2" role="radiogroup" aria-label="Ritmo de juego">
      @for (p of presets; track p.id) {
        <button
          type="button"
          role="radio"
          [attr.aria-checked]="isSelected(p)"
          (click)="pick(p)"
          class="rounded-xl border px-2 py-3 text-center transition-colors"
          [class]="isSelected(p) ? 'border-cyan-400/70 bg-cyan-400/10 text-white shadow-[0_0_18px_rgb(34_211_238/0.2)]' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.07] text-zinc-200'"
        >
          <div class="font-mono text-lg font-bold">{{ p.id }}</div>
          <div class="text-[11px] text-zinc-400">{{ categoryName(p) }}</div>
        </button>
      }
      <button
        type="button"
        role="radio"
        [attr.aria-checked]="custom()"
        (click)="custom.set(true); applyCustom()"
        class="rounded-xl border px-2 py-3 text-center transition-colors"
        [class]="custom() ? 'border-violet-400/70 bg-violet-400/10 text-white' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.07] text-zinc-200'"
      >
        <div class="font-semibold">Personalizado</div>
        <div class="text-[11px] text-zinc-400">min + seg</div>
      </button>
    </div>

    @if (custom()) {
      <div class="mt-3 grid grid-cols-2 gap-3">
        <label>
          <span class="label">Minutos por jugador</span>
          <input class="field font-mono" type="number" min="0.25" max="180" step="0.25" [ngModel]="customMin()" (ngModelChange)="customMin.set(+$event); applyCustom()" />
        </label>
        <label>
          <span class="label">Incremento (segundos)</span>
          <input class="field font-mono" type="number" min="0" max="180" step="1" [ngModel]="customInc()" (ngModelChange)="customInc.set(+$event); applyCustom()" />
        </label>
      </div>
    }
    <p class="mt-3 text-sm text-zinc-400">
      Ritmo: <span class="font-mono text-white">{{ label() }}</span> · <span class="text-cyan-300">{{ category() }}</span>
    </p>
    <p class="mt-1 text-xs text-zinc-500">{{ explain() }}</p>
  `,
})
export class TimeControlPickerComponent {
  readonly value = model.required<TimeControl>();
  readonly presets = TIME_PRESETS;
  readonly custom = signal(false);
  readonly customMin = signal(3);
  readonly customInc = signal(2);

  readonly label = computed(() => tcLabel(this.value()));
  readonly category = computed(() => CATEGORY_LABEL[categoryOf(this.value())]);
  readonly explain = computed(() => {
    const v = this.value();
    const min = tcLabel({ baseMs: v.baseMs, incMs: 0 }).replace('+0', '');
    return v.incMs > 0
      ? `${min} min por jugador. Reloj Bronstein: cada jugada te devuelve lo que pensaste, hasta ${v.incMs / 1000} s; el reloj nunca sube. A 0:00 pierdes.`
      : `${min} min por jugador, sin devolución: el reloj solo baja. A 0:00 pierdes.`;
  });

  categoryName(tc: TimeControl): string {
    return CATEGORY_LABEL[categoryOf(tc)];
  }

  isSelected(p: TimeControl): boolean {
    const v = this.value();
    return !this.custom() && v.baseMs === p.baseMs && v.incMs === p.incMs;
  }

  pick(p: TimeControl): void {
    this.custom.set(false);
    this.value.set({ baseMs: p.baseMs, incMs: p.incMs });
  }

  applyCustom(): void {
    const min = Math.min(180, Math.max(0.25, this.customMin() || 0.25));
    const inc = Math.min(180, Math.max(0, Math.round(this.customInc() || 0)));
    this.value.set({ baseMs: Math.round(min * 60_000), incMs: inc * 1000 });
  }
}
