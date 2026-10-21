import { computed, signal } from '@angular/core';
import { Side, TimeControl } from './models';

/**
 * Reloj de ajedrez con demora Bronstein (la de los torneos de la US Chess).
 *
 * Ritmo "3+2" = 3 minutos por jugador y hasta 2 s de devolución por jugada: al terminar
 * una jugada se le devuelve al jugador lo que pensó, con un tope de 2 s. Por eso el reloj
 * NUNCA sube por encima de lo que tenía al empezar su turno, y si llega a 0:00 pierde.
 * (Con Fischer, el sistema de la FIDE, se suman siempre los 2 s y el reloj puede subir si
 * se juega rápido; con modelos que responden en ~1.5 s eso confundía.)
 *
 * - El tiempo se mide con un reloj monotónico (performance.now) y se refresca cada 100 ms;
 *   el valor exacto se calcula siempre a partir de la marca de inicio, así el redondeo del
 *   intervalo nunca acumula error.
 * - press(side): el jugador `side` terminó su jugada → se le descuenta lo que pensó, se le
 *   devuelve hasta `incMs` de ese tiempo y empieza a correr el reloj del rival.
 * - pause()/resume() congelan el reloj (pausas visuales del modo IA vs IA, errores de red).
 */
export class ChessClock {
  private readonly remaining = signal<Record<Side, number>>({ w: 0, b: 0 });
  private readonly runningSide = signal<Side | null>(null);
  private readonly now = signal(0);
  private startedAt = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private flagged = false;

  static readonly MODE = 'Bronstein';

  /** Tiempo restante en vivo de cada lado. */
  readonly time = computed<Record<Side, number>>(() => {
    const rem = this.remaining();
    const side = this.runningSide();
    if (!side) return rem;
    const elapsed = this.now() - this.startedAt;
    return { ...rem, [side]: Math.max(0, rem[side] - elapsed) } as Record<Side, number>;
  });

  readonly active = this.runningSide.asReadonly();

  constructor(
    readonly control: TimeControl,
    private readonly onFlag: (side: Side) => void,
    private readonly clockFn: () => number = () => performance.now(),
    private readonly tickMs = 100,
  ) {
    this.remaining.set({ w: control.baseMs, b: control.baseMs });
  }

  /** Arranca el reloj de `side` (inicio de partida o reanudación). */
  start(side: Side): void {
    if (this.flagged) return;
    this.startedAt = this.clockFn();
    this.now.set(this.startedAt);
    this.runningSide.set(side);
    this.ensureTimer();
  }

  /**
   * `side` completó su jugada. Devuelve el tiempo que pensó y el reloj que le queda
   * (ya con la devolución Bronstein: min(lo pensado, demora)).
   */
  press(side: Side): { thinkMs: number; remainingMs: number } {
    const t = this.clockFn();
    const rem = { ...this.remaining() };
    let thinkMs = 0;
    if (this.runningSide() === side) {
      thinkMs = t - this.startedAt;
      rem[side] = Math.max(0, rem[side] - thinkMs);
    }
    rem[side] += Math.min(thinkMs, this.control.incMs);
    this.remaining.set(rem);
    const other: Side = side === 'w' ? 'b' : 'w';
    this.startedAt = t;
    this.now.set(t);
    this.runningSide.set(other);
    this.ensureTimer();
    return { thinkMs: Math.round(thinkMs), remainingMs: rem[side] };
  }

  /** Congela el reloj y devuelve el lado que estaba corriendo. */
  pause(): Side | null {
    const side = this.runningSide();
    if (side) {
      const rem = { ...this.remaining() };
      rem[side] = Math.max(0, rem[side] - (this.clockFn() - this.startedAt));
      this.remaining.set(rem);
    }
    this.runningSide.set(null);
    this.clearTimer();
    return side;
  }

  stop(): void {
    this.pause();
  }

  /** Para pruebas y para forzar la comprobación de bandera. */
  tick(): void {
    const side = this.runningSide();
    if (!side) return;
    const t = this.clockFn();
    this.now.set(t);
    if (!this.flagged && this.remaining()[side] - (t - this.startedAt) <= 0) {
      this.flagged = true;
      this.pause();
      const rem = { ...this.remaining() };
      rem[side] = 0;
      this.remaining.set(rem);
      this.onFlag(side);
    }
  }

  get hasFlagged(): boolean {
    return this.flagged;
  }

  destroy(): void {
    this.clearTimer();
    this.runningSide.set(null);
  }

  private ensureTimer(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.tick(), this.tickMs);
  }

  private clearTimer(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
