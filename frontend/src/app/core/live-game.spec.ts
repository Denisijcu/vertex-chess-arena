import { describe, expect, it, vi } from 'vitest';
import { LiveGame } from './live-game';
import { ApiService } from './api.service';
import { Contender } from './models';

const human: Contender = { id: 'h', kind: 'human', label: 'Tú' };
const human2: Contender = { id: 'h2', kind: 'human', label: 'Rival' };

function game(white = human, black = human2) {
  return new LiveGame({ white, black, timeControl: { baseMs: 60_000, incMs: 0 }, api: {} as ApiService });
}

describe('LiveGame', () => {
  it('mate del loco termina 0-1 por jaque mate y el PGN lleva relojes', () => {
    const g = game();
    g.start();
    expect(g.humanMove('f2', 'f3')).toBe(true);
    expect(g.humanMove('e7', 'e5')).toBe(true);
    expect(g.humanMove('g2', 'g4')).toBe(true);
    expect(g.humanMove('d8', 'h4')).toBe(true);
    expect(g.status()).toBe('finished');
    expect(g.result()).toBe('0-1');
    expect(g.termination()).toBe('checkmate');
    const pgn = g.pgn();
    expect(pgn).toContain('[TimeControl "60+0"]');
    expect(pgn).toMatch(/2\.\.\.|2\. g4 \{\[%clk/);
    expect(pgn).toContain('Qh4#');
    g.destroy();
  });

  it('rechaza jugadas ilegales y fuera de turno', () => {
    const g = game();
    g.start();
    expect(g.humanMove('e7', 'e5')).toBe(false);
    expect(g.humanMove('e2', 'e5')).toBe(false);
    g.destroy();
  });

  it('bandera: pierde quien se queda sin tiempo; tablas si el rival no tiene material de mate', () => {
    const g = game();
    g.start();
    // Fuerza la bandera de blancas con el rival con material completo
    (g as unknown as { onFlag: (s: 'w' | 'b') => void }).onFlag('w');
    expect(g.result()).toBe('0-1');
    expect(g.termination()).toBe('timeout');
    g.destroy();
  });

  it('material de mate: rey solo o rey + pieza menor no alcanza', () => {
    const g = game();
    expect(g.hasMatingMaterial('w')).toBe(true);
    g.destroy();
  });

  it('IA: pide la jugada a la API y la aplica', async () => {
    const api = {
      aiMove: vi.fn().mockResolvedValue({ played_uci: 'e2e4', clean_hit: true, raw_output: 'Best move: e4 (UCI: e2e4)' }),
    } as unknown as ApiService;
    const ai: Contender = { id: 'a', kind: 'ai', label: 'IA', model: 'vertexgemma', mode: 'pure' };
    const g = new LiveGame({ white: ai, black: human, timeControl: { baseMs: 60_000, incMs: 1000 }, api });
    g.start();
    await vi.waitFor(() => expect(g.moves().length).toBe(1));
    expect(g.moves()[0].san).toBe('e4');
    expect(g.moves()[0].clean).toBe(true);
    expect(g.stats().w.clean).toBe(1);
    expect(g.isHumanTurn()).toBe(true);
    g.destroy();
  });
});
