import { Injectable, computed, inject, signal } from '@angular/core';
import { ApiError, ApiService } from './api.service';
import { Contender, EngineMode, PlayerInfo } from './models';

export const MODE_LABEL: Record<EngineMode, string> = {
  pure: 'LLM puro',
  arbiter: 'LLM + árbitro',
  engine: 'Motor',
};

export const MODE_HINT: Record<EngineMode, string> = {
  pure: 'El modelo elige entre todas las jugadas legales. Mide al modelo.',
  arbiter: 'El motor filtra 4 candidatas y el modelo elige. Mide al sistema híbrido.',
  engine: 'Solo el motor alpha-beta del árbitro, sin LLM. Línea base.',
};

export function aiContender(p: PlayerInfo, mode: EngineMode): Contender {
  const m: EngineMode = p.kind === 'engine' ? 'engine' : mode;
  return {
    id: `${p.model}:${m}`,
    kind: 'ai',
    model: p.model,
    mode: m,
    family: p.family,
    label: p.kind === 'engine' ? p.name : `${p.name} · ${MODE_LABEL[m]}`,
  };
}

export const HUMAN: Contender = { id: 'human', kind: 'human', label: 'Tú' };

@Injectable({ providedIn: 'root' })
export class PlayersStore {
  private readonly api = inject(ApiService);
  readonly players = signal<PlayerInfo[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly available = computed(() => this.players().filter((p) => p.available));

  async load(force = false): Promise<void> {
    if (this.loading() || (this.players().length && !force)) return;
    this.loading.set(true);
    this.error.set(null);
    try {
      const r = await this.api.players();
      this.players.set(r.players);
    } catch (e) {
      this.error.set(e instanceof ApiError ? e.message : 'No se pudo cargar la lista de jugadores.');
    } finally {
      this.loading.set(false);
    }
  }

  /** Todas las combinaciones jugador × modo disponibles (para torneos). */
  contenderOptions(): Contender[] {
    const out: Contender[] = [];
    for (const p of this.available()) {
      if (p.kind === 'engine') out.push(aiContender(p, 'engine'));
      else {
        out.push(aiContender(p, 'pure'));
        out.push(aiContender(p, 'arbiter'));
      }
    }
    return out;
  }
}
