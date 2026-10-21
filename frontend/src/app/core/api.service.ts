import { Injectable, signal } from '@angular/core';
import {
  AiMoveResponse,
  EngineMode,
  PlayersResponse,
  SavedGameRecord,
  Tournament,
} from './models';

/** Error de la API con el formato {"error": {"code", "message"}}. */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status = 0,
  ) {
    super(message);
  }
}

/**
 * Cliente de la API de la arena. Usa rutas relativas: en desarrollo `ng serve` las pasa al
 * backend con proxy.conf.json; en producción FastAPI sirve la app y la API en el mismo origen.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly ollamaStatus = signal<'up' | 'down' | 'unknown'>('unknown');

  private async request<T>(
    path: string,
    init: { method?: string; body?: unknown; timeoutMs?: number; signal?: AbortSignal } = {},
  ): Promise<T> {
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(new DOMException('timeout', 'TimeoutError')), init.timeoutMs ?? 10_000);
    const onOuterAbort = () => ctrl.abort(init.signal?.reason);
    init.signal?.addEventListener('abort', onOuterAbort, { once: true });
    try {
      const resp = await fetch(path, {
        method: init.method ?? 'GET',
        headers: init.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
        signal: ctrl.signal,
      });
      const text = await resp.text();
      let data: unknown = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = null;
      }
      if (!resp.ok) {
        const err = (data as { error?: { code?: string; message?: string } } | null)?.error;
        throw new ApiError(err?.code ?? 'HTTP_' + resp.status, err?.message ?? `Error ${resp.status}`, resp.status);
      }
      return data as T;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      if (init.signal?.aborted) throw new ApiError('ABORTED', 'Solicitud cancelada');
      if (ctrl.signal.aborted) throw new ApiError('TIMEOUT', 'El servidor tardó demasiado en responder');
      throw new ApiError('NETWORK', 'No hay conexión con la API de la arena (¿uvicorn corriendo en el puerto 8000?)');
    } finally {
      clearTimeout(timeout);
      init.signal?.removeEventListener('abort', onOuterAbort);
    }
  }

  async health(): Promise<{ status: string; ollama: 'up' | 'down' }> {
    try {
      const h = await this.request<{ status: string; ollama: 'up' | 'down' }>('/health', { timeoutMs: 5000 });
      this.ollamaStatus.set(h.ollama);
      return h;
    } catch (e) {
      this.ollamaStatus.set('unknown');
      throw e;
    }
  }

  async players(): Promise<PlayersResponse> {
    const r = await this.request<PlayersResponse>('/api/players', { timeoutMs: 8000 });
    this.ollamaStatus.set(r.ollama);
    return r;
  }

  aiMove(
    body: { fen: string; model_name: string; mode: EngineMode; game_id: string },
    signal: AbortSignal,
    timeoutMs: number,
  ): Promise<AiMoveResponse> {
    return this.request<AiMoveResponse>('/api/ai-move', { method: 'POST', body, signal, timeoutMs });
  }

  saveGame(body: Omit<SavedGameRecord, 'id' | 'saved_at'>): Promise<{ id: string; saved_at: string }> {
    return this.request('/api/games', { method: 'POST', body });
  }

  games(limit = 100): Promise<SavedGameRecord[]> {
    return this.request(`/api/games?limit=${limit}`);
  }

  tournaments(): Promise<Array<Pick<Tournament, 'id' | 'name' | 'format' | 'status' | 'createdAt' | 'timeControl'> & { players: number }>> {
    return this.request('/api/tournaments');
  }

  tournament(id: string): Promise<Tournament> {
    return this.request(`/api/tournaments/${encodeURIComponent(id)}`);
  }

  saveTournament(t: Tournament): Promise<{ ok: boolean }> {
    return this.request(`/api/tournaments/${encodeURIComponent(t.id)}`, { method: 'PUT', body: t });
  }
}
