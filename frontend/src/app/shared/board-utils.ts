import { Side } from '../core/models';

/** Casilla del rey de `side` a partir de un FEN (para marcar el jaque). */
export function kingSquare(fen: string, side: Side): string | null {
  const rows = fen.split(' ')[0].split('/');
  const target = side === 'w' ? 'K' : 'k';
  for (let r = 0; r < 8; r++) {
    let file = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) {
        file += Number(ch);
        continue;
      }
      if (ch === target) return 'abcdefgh'[file] + (8 - r);
      file++;
    }
  }
  return null;
}

/** Descarga un texto como archivo. */
export function downloadText(filename: string, text: string, mime = 'application/x-chess-pgn'): void {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function slug(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 60);
}
