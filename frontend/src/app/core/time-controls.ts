import { TimeCategory, TimeControl } from './models';

export interface TimePreset extends TimeControl {
  id: string;
}

const m = (min: number) => min * 60_000;
const s = (sec: number) => sec * 1000;

/** Ritmos estándar (estilo Lichess/FIDE). */
export const TIME_PRESETS: TimePreset[] = [
  { id: '½+0', baseMs: s(30), incMs: 0 },
  { id: '1+0', baseMs: m(1), incMs: 0 },
  { id: '2+1', baseMs: m(2), incMs: s(1) },
  { id: '3+0', baseMs: m(3), incMs: 0 },
  { id: '3+2', baseMs: m(3), incMs: s(2) },
  { id: '5+0', baseMs: m(5), incMs: 0 },
  { id: '5+3', baseMs: m(5), incMs: s(3) },
  { id: '10+0', baseMs: m(10), incMs: 0 },
  { id: '10+5', baseMs: m(10), incMs: s(5) },
  { id: '15+10', baseMs: m(15), incMs: s(10) },
  { id: '30+0', baseMs: m(30), incMs: 0 },
  { id: '30+20', baseMs: m(30), incMs: s(20) },
];

export const CATEGORY_LABEL: Record<TimeCategory, string> = {
  bullet: 'Bullet',
  blitz: 'Blitz',
  rapid: 'Rápidas',
  classical: 'Clásicas',
};

/**
 * Categoría según la duración estimada de la partida: base + 40 × incremento
 * (criterio de Lichess). < 3 min bullet, < 8 min blitz, < 25 min rápidas, resto clásicas.
 */
export function categoryOf(tc: TimeControl): TimeCategory {
  const estimatedSec = tc.baseMs / 1000 + 40 * (tc.incMs / 1000);
  if (estimatedSec < 179) return 'bullet';
  if (estimatedSec < 479) return 'blitz';
  if (estimatedSec < 1499) return 'rapid';
  return 'classical';
}

/** "3+2" (minutos + segundos de incremento). Bases no enteras se muestran como "½+0", "¼+0". */
export function tcLabel(tc: TimeControl): string {
  const min = tc.baseMs / 60_000;
  const fractions: Record<string, string> = { '0.25': '¼', '0.5': '½', '0.75': '¾' };
  const base = Number.isInteger(min) ? String(min) : (fractions[String(min)] ?? min.toFixed(1));
  return `${base}+${tc.incMs / 1000}`;
}

/** Campo TimeControl del PGN: "180+2" (segundos). */
export function tcPgn(tc: TimeControl): string {
  return `${Math.round(tc.baseMs / 1000)}+${Math.round(tc.incMs / 1000)}`;
}

/** "180+2" (PGN, segundos) → TimeControl. Devuelve null si no se puede leer. */
export function parsePgnTc(tc: string): TimeControl | null {
  const m = /^(\d+)\+(\d+)$/.exec(tc.trim());
  return m ? { baseMs: +m[1] * 1000, incMs: +m[2] * 1000 } : null;
}

/** Formato de reloj: 1:05:03, 4:59, y décimas por debajo de 20 s (0:09.4). */
export function formatClock(ms: number): string {
  const clamped = Math.max(0, ms);
  const totalSec = clamped / 1000;
  const h = Math.floor(totalSec / 3600);
  const min = Math.floor((totalSec % 3600) / 60);
  const sec = Math.floor(totalSec % 60);
  if (h > 0) return `${h}:${pad(min)}:${pad(sec)}`;
  if (clamped < 20_000) {
    const tenths = Math.floor((clamped % 1000) / 100);
    return `${min}:${pad(sec)}.${tenths}`;
  }
  return `${min}:${pad(sec)}`;
}

/** Comentario de reloj PGN: [%clk 0:02:58.4] */
export function pgnClock(ms: number): string {
  const clamped = Math.max(0, ms);
  const totalSec = clamped / 1000;
  const h = Math.floor(totalSec / 3600);
  const min = Math.floor((totalSec % 3600) / 60);
  const sec = Math.floor(totalSec % 60);
  const tenths = Math.floor((clamped % 1000) / 100);
  return `${h}:${pad(min)}:${pad(sec)}.${tenths}`;
}

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}
