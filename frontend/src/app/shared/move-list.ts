import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, computed, effect, input, output, viewChild } from '@angular/core';
import { PlayedMove } from '../core/models';
import { formatClock } from '../core/time-controls';

interface Row {
  n: number;
  w?: PlayedMove;
  b?: PlayedMove;
}

/** Lista de jugadas en pares, con reloj restante y marca de fallback de la IA. */
@Component({
  selector: 'vx-move-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #scroller class="overflow-y-auto font-mono text-sm" [style.max-height]="maxHeight()">
      @if (rows().length === 0) {
        <p class="text-zinc-500 text-sm font-sans px-3 py-6 text-center">Todavía no hay jugadas.</p>
      }
      <table class="w-full">
        <tbody>
          @for (r of rows(); track r.n) {
            <tr class="odd:bg-white/[0.02]">
              <td class="w-10 text-right pr-2 text-zinc-500 py-1">{{ r.n }}.</td>
              <td class="py-0.5">
                @if (r.w) { <ng-container *ngTemplateOutlet="cell; context: { $implicit: r.w }" /> }
              </td>
              <td class="py-0.5">
                @if (r.b) { <ng-container *ngTemplateOutlet="cell; context: { $implicit: r.b }" /> }
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    <ng-template #cell let-m>
      <button
        type="button"
        class="w-full flex items-baseline justify-between gap-2 rounded-md px-2 py-0.5 text-left hover:bg-white/5"
        [attr.data-ply]="m.ply"
        [class.bg-cyan-400/15]="selectedPly() === m.ply"
        [class.text-cyan-200]="selectedPly() === m.ply"
        (click)="select.emit(m.ply)"
        [attr.aria-label]="'Jugada ' + m.san"
      >
        <span>
          {{ m.san }}
          @if (m.clean === false) {
            <span class="text-amber-400 text-xs" title="Respuesta inválida: jugada aleatoria (fallback)">⚑</span>
          }
        </span>
        <span class="text-[11px] text-zinc-500">{{ clock(m.clockAfterMs) }}</span>
      </button>
    </ng-template>
  `,
  imports: [NgTemplateOutlet],
})
export class MoveListComponent {
  readonly moves = input.required<PlayedMove[]>();
  readonly selectedPly = input<number | null>(null);
  readonly maxHeight = input('22rem');
  readonly autoScroll = input(true);
  readonly select = output<number>();
  private readonly scroller = viewChild.required<ElementRef<HTMLDivElement>>('scroller');

  readonly rows = computed<Row[]>(() => {
    const out: Row[] = [];
    for (const m of this.moves()) {
      const n = Math.ceil(m.ply / 2);
      let row = out[out.length - 1];
      if (!row || row.n !== n) {
        row = { n };
        out.push(row);
      }
      row[m.side] = m;
    }
    return out;
  });

  constructor() {
    effect(() => {
      const ply = this.selectedPly();
      if (ply === null) return;
      queueMicrotask(() => {
        const el = this.scroller().nativeElement;
        const btn = el.querySelector<HTMLElement>(`[data-ply="${ply}"]`);
        if (btn) el.scrollTop = btn.offsetTop - el.clientHeight / 2;
      });
    });
    effect(() => {
      this.moves();
      if (!this.autoScroll()) return;
      queueMicrotask(() => {
        const el = this.scroller().nativeElement;
        el.scrollTop = el.scrollHeight;
      });
    });
  }

  clock(ms: number): string {
    return formatClock(ms);
  }
}

