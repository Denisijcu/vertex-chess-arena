import { Injectable, signal } from '@angular/core';
import {
  AiMoveResponse,
  EngineMode,
  PlayersResponse,
  SavedGameRecord,
  Tournament,
} from './models';
import { BACKEND } from './backend-config';
import { BrowserStore } from './browser-store';

/** Cliente de Gradio (solo se descarga en la versión pública). */
type GradioClient = { predict: (endpoint: string, data?: Record<string, unknown>) => Promise<{ data: unknown }> };

const QUOTA_MESSAGE =
  'Se acabó tu cuota diaria de GPU gratis en Hugging Face. Juega contra el Motor del árbitro (no usa GPU) o vuelve mañana.';

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
 * Cliente de la API de la arena.
 * - Modo local: rutas relativas; en desarrollo `ng serve` las pasa al backend con proxy.conf.json
 *   y en producción FastAPI sirve la app y la API en el mismo origen.
 * - Modo space (Netlify): las jugadas van al Space de Hugging Face con @gradio/client; las
 *   partidas y los torneos se guardan en el navegador (BrowserStore).
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly ollamaStatus = signal<'up' | 'down' | 'unknown'>('unknown');
  /** Nombre del backend para la cabecera ("Ollama" en local, "Servidor" en la versión pública). */
  readonly backendLabel = BACKEND.label;
  readonly isPublic = BACKEND.kind === 'space';
  private readonly store = new BrowserStore();
  private client: Promise<GradioClient> | null = null;

  private gradio(): Promise<GradioClient> {
    this.client ??= import('@gradio/client')
      .then(({ Client }) => Client.connect(BACKEND.space!) as unknown as Promise<GradioClient>)
      .catch((e) => {
        this.client = null;
        throw e;
      });
    return this.client;
  }

  /** Llama a un endpoint del Space y traduce sus errores ("CODIGO: mensaje") a ApiError. */
  private async space<T>(endpoint: string, data: Record<string, unknown> = {}, timeoutMs = 60_000, signal?: AbortSignal): Promise<T> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const guard = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new ApiError('TIMEOUT', 'El servidor tardó demasiado en responder')), timeoutMs);
      signal?.addEventListener('abort', () => reject(new ApiError('ABORTED', 'Solicitud cancelada')), { once: true });
    });
    try {
      const call = this.gradio().then((c) => c.predict(endpoint, data));
      const res = await Promise.race([call, guard]);
      return (res.data as unknown[])[0] as T;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      const msg = String((e as { message?: string })?.message ?? e);
      if (/quota|zerogpu|gpu task aborted|exceeded/i.test(msg)) throw new ApiError('GPU_QUOTA', QUOTA_MESSAGE, 429);
      const m = /^([A-Z_]{3,}):\s*(.*)$/s.exec(msg);
      if (m) throw new ApiError(m[1], m[2], 400);
      throw new ApiError('NETWORK', 'No hay conexión con el servidor de la arena en Hugging Face. Puede estar arrancando: prueba en un minuto.');
    } finally {
      clearTimeout(timer);
    }
  }

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
      const h = this.isPublic
        ? await this.space<{ status: string; ollama: 'up' | 'down' }>('/health', {}, 90_000)
        : await this.request<{ status: string; ollama: 'up' | 'down' }>('/health', { timeoutMs: 5000 });
      this.ollamaStatus.set(h.ollama);
      return h;
    } catch (e) {
      this.ollamaStatus.set('unknown');
      throw e;
    }
  }

  async players(): Promise<PlayersResponse> {
    const r = this.isPublic
      ? await this.space<PlayersResponse>('/players', {}, 90_000)
      : await this.request<PlayersResponse>('/api/players', { timeoutMs: 8000 });
    this.ollamaStatus.set(r.ollama);
    return r;
  }

  aiMove(
    body: { fen: string; model_name: string; mode: EngineMode; game_id: string },
    signal: AbortSignal,
    timeoutMs: number,
  ): Promise<AiMoveResponse> {
    if (this.isPublic) {
      // En el Space la primera jugada puede esperar a que se asigne una GPU: margen extra.
      return this.space<AiMoveResponse>('/ai_move', { ...body }, Math.max(timeoutMs, 60_000), signal);
    }
    return this.request<AiMoveResponse>('/api/ai-move', { method: 'POST', body, signal, timeoutMs });
  }

  async saveGame(body: Omit<SavedGameRecord, 'id' | 'saved_at'>): Promise<{ id: string; saved_at: string }> {
    if (this.isPublic) return this.store.saveGame(body);
    return this.request('/api/games', { method: 'POST', body });
  }

  async games(limit = 100): Promise<SavedGameRecord[]> {
    if (this.isPublic) return this.store.games(limit);
    return this.request(`/api/games?limit=${limit}`);
  }

  async tournaments(): Promise<Array<Pick<Tournament, 'id' | 'name' | 'format' | 'status' | 'createdAt' | 'timeControl'> & { players: number }>> {
    if (this.isPublic) return this.store.tournaments();
    return this.request('/api/tournaments');
  }

  async tournament(id: string): Promise<Tournament> {
    if (this.isPublic) {
      const t = await this.store.tournament(id);
      if (!t) throw new ApiError('NOT_FOUND', 'Torneo no encontrado en este navegador.', 404);
      return t;
    }
    return this.request(`/api/tournaments/${encodeURIComponent(id)}`);
  }

  async saveTournament(t: Tournament): Promise<{ ok: boolean }> {
    if (this.isPublic) {
      if (!(await this.store.saveTournament(t))) {
        throw new ApiError('STORAGE_FULL', 'No se pudo guardar el torneo en este navegador (almacenamiento lleno o bloqueado).');
      }
      return { ok: true };
    }
    return this.request(`/api/tournaments/${encodeURIComponent(t.id)}`, { method: 'PUT', body: t });
  }
}
