import { describe, expect, it } from 'vitest';
import { ChessClock } from './chess-clock';
import { Side } from './models';

function fakeClock(baseMs: number, incMs: number) {
  let t = 0;
  const flags: Side[] = [];
  const clock = new ChessClock({ baseMs, incMs }, (s) => flags.push(s), () => t, 1_000_000);
  return { clock, flags, advance: (ms: number) => (t += ms) };
}

describe('ChessClock', () => {
  it('descuenta el tiempo pensado y suma el incremento (Fischer)', () => {
    const { clock, advance } = fakeClock(60_000, 2_000);
    clock.start('w');
    advance(5_000);
    const r = clock.press('w');
    expect(r.thinkMs).toBe(5_000);
    expect(r.remainingMs).toBe(57_000);
    expect(clock.active()).toBe('b');
    advance(1_000);
    clock.tick();
    expect(clock.time().b).toBe(59_000);
    clock.destroy();
  });

  it('pausa congela el reloj', () => {
    const { clock, advance } = fakeClock(10_000, 0);
    clock.start('w');
    advance(3_000);
    clock.pause();
    advance(50_000);
    clock.tick();
    expect(clock.time().w).toBe(7_000);
    clock.start('w');
    advance(1_000);
    clock.tick();
    expect(clock.time().w).toBe(6_000);
    clock.destroy();
  });

  it('cae la bandera exactamente una vez', () => {
    const { clock, flags, advance } = fakeClock(1_000, 0);
    clock.start('b');
    advance(1_200);
    clock.tick();
    clock.tick();
    expect(flags).toEqual(['b']);
    expect(clock.time().b).toBe(0);
    clock.destroy();
  });
});
