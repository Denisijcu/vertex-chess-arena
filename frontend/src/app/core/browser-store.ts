import { SavedGameRecord, Tournament } from './models';

type Summary = Pick<Tournament, 'id' | 'name' | 'format' | 'status' | 'createdAt' | 'timeControl'> & { players: number };

const GAMES_KEY = 'vca.games.v1';
const TOURNAMENTS_KEY = 'vca.tournaments.v1';
const MAX_GAMES = 300;

/** Partidas y torneos oficiales que vienen con la app (la Copa Vertex Verano 2026). */
interface Showcase {
  games: SavedGameRecord[];
  tournaments: Tournament[];
}

/**
 * Almacén en el navegador para la versión pública: cada visitante guarda sus partidas y
 * torneos en su propio navegador (localStorage), y además ve los oficiales del libro, que
 * vienen en showcase.json y no se pueden modificar.
 */
export class BrowserStore {
  private showcase: Promise<Showcase> | null = null;

  private read<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
      return fallback;
    }
  }

  private write(key: string, value: unknown): boolean {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  }

  private loadShowcase(): Promise<Showcase> {
    this.showcase ??= fetch('showcase.json')
      .then((r) => (r.ok ? (r.json() as Promise<Showcase>) : { games: [], tournaments: [] }))
      .catch(() => ({ games: [], tournaments: [] }));
    return this.showcase;
  }

  async isOfficial(tournamentId: string): Promise<boolean> {
    return (await this.loadShowcase()).tournaments.some((t) => t.id === tournamentId);
  }

  saveGame(body: Omit<SavedGameRecord, 'id' | 'saved_at'>): { id: string; saved_at: string } {
    const rec: SavedGameRecord = {
      ...body,
      id: Math.random().toString(16).slice(2, 14).padEnd(12, '0'),
      saved_at: new Date().toISOString().slice(0, 19) + '+00:00',
    };
    const games = this.read<SavedGameRecord[]>(GAMES_KEY, []);
    games.push(rec);
    this.write(GAMES_KEY, games.slice(-MAX_GAMES));
    return { id: rec.id, saved_at: rec.saved_at };
  }

  async games(limit: number): Promise<SavedGameRecord[]> {
    const mine = this.read<SavedGameRecord[]>(GAMES_KEY, []);
    const all = [...(await this.loadShowcase()).games, ...mine];
    return all.reverse().slice(0, limit);
  }

  async tournaments(): Promise<Summary[]> {
    const all = [...(await this.loadShowcase()).tournaments, ...Object.values(this.read<Record<string, Tournament>>(TOURNAMENTS_KEY, {}))];
    return all
      .map((t) => ({
        id: t.id, name: t.name, format: t.format, status: t.status, createdAt: t.createdAt,
        timeControl: t.timeControl, players: t.participants.length,
      }))
      .sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''));
  }

  async tournament(id: string): Promise<Tournament | null> {
    const official = (await this.loadShowcase()).tournaments.find((t) => t.id === id);
    if (official) return structuredClone(official);
    return this.read<Record<string, Tournament>>(TOURNAMENTS_KEY, {})[id] ?? null;
  }

  async saveTournament(t: Tournament): Promise<boolean> {
    if (await this.isOfficial(t.id)) return true; // los oficiales son de solo lectura
    const all = this.read<Record<string, Tournament>>(TOURNAMENTS_KEY, {});
    all[t.id] = t;
    return this.write(TOURNAMENTS_KEY, all);
  }
}
