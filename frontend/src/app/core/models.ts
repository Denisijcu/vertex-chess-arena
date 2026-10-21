export type Side = 'w' | 'b';
export type EngineMode = 'pure' | 'arbiter' | 'engine';
export type GameResult = '1-0' | '0-1' | '1/2-1/2';

export type Termination =
  | 'checkmate'
  | 'stalemate'
  | 'insufficient'
  | 'threefold'
  | 'fifty-move'
  | 'timeout'
  | 'timeout-vs-insufficient'
  | 'resignation'
  | 'adjudication'
  | 'aborted';

export const TERMINATION_LABEL: Record<Termination, string> = {
  checkmate: 'Jaque mate',
  stalemate: 'Ahogado',
  insufficient: 'Material insuficiente',
  threefold: 'Triple repetición',
  'fifty-move': 'Regla de 50 jugadas',
  timeout: 'Tiempo agotado',
  'timeout-vs-insufficient': 'Tiempo agotado vs. material insuficiente',
  resignation: 'Abandono',
  adjudication: 'Adjudicada (límite de jugadas)',
  aborted: 'Anulada',
};

/** Jugador disponible según la API (modelo de Ollama o el motor del árbitro). */
export interface PlayerInfo {
  model: string;
  name: string;
  family: 'qwen' | 'gemma' | 'engine' | string;
  kind: 'llm' | 'engine';
  description: string;
  available: boolean;
}

export interface PlayersResponse {
  ollama: 'up' | 'down';
  players: PlayerInfo[];
}

/** Quien se sienta frente al tablero: una persona o una IA con un modo de juego. */
export interface Contender {
  id: string;
  kind: 'human' | 'ai';
  label: string;
  model?: string;
  mode?: EngineMode;
  family?: string;
}

export type TimeCategory = 'bullet' | 'blitz' | 'rapid' | 'classical';

export interface TimeControl {
  baseMs: number;
  incMs: number;
}

export interface AiMoveResponse {
  model: string;
  mode: EngineMode;
  played_san: string;
  played_uci: string;
  clean_hit: boolean;
  raw_output: string;
  options_count: number;
  think_ms: number;
  new_fen: string;
  game_over: boolean;
  result: string | null;
}

/** Una jugada ya hecha, con su reloj y su telemetría. */
export interface PlayedMove {
  ply: number;
  side: Side;
  san: string;
  uci: string;
  from: string;
  to: string;
  fenAfter: string;
  clockAfterMs: number;
  thinkMs: number;
  /** Solo IA: si la respuesta del modelo fue válida (false = fallback aleatorio). */
  clean?: boolean;
  raw?: string;
}

export interface SideStats {
  moves: number;
  clean: number;
  fallback: number;
  thinkMs: number;
}

export interface SavedGameRecord {
  id: string;
  saved_at: string;
  pgn: string;
  white: string;
  black: string;
  result: GameResult | '*';
  termination: string;
  time_control: string;
  plies: number;
  tournament_id?: string | null;
  round?: number | null;
  stats?: Record<string, unknown>;
}

export type TournamentFormat = 'round-robin' | 'double-round-robin' | 'match';
export type TournamentStatus = 'pending' | 'running' | 'paused' | 'finished';

export interface Pairing {
  id: string;
  round: number;
  white: string; // Contender.id
  black: string;
  result?: GameResult;
  termination?: Termination;
  plies?: number;
  pgn?: string;
  stats?: { w: SideStats; b: SideStats; timeouts?: Side | null };
  savedGameId?: string;
}

export interface Tournament {
  id: string;
  name: string;
  format: TournamentFormat;
  timeControl: TimeControl;
  participants: Contender[];
  pairings: Pairing[];
  status: TournamentStatus;
  createdAt: string;
  finishedAt?: string;
  settings: {
    maxPlies: number;
    moveDelayMs: number;
    matchGames?: number;
  };
}
