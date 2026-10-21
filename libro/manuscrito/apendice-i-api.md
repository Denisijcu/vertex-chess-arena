# Apéndice I — La API del backend

`api_server.py` es la API V3 con FastAPI que usa la aplicación de torneos (capítulo 10). Se
configura con variables de entorno (`OLLAMA_URL`, `ALLOWED_ORIGINS`, `ARENA_DATA_DIR`,
`FRONTEND_DIST`), lo que la deja lista para desplegarse fuera de la máquina de desarrollo.

Tres detalles para leerla:

- **`arbiter_for`** guarda un árbitro por partida (`game_id`), porque el árbitro recuerda las
  posiciones recientes para su filtro anti-repetición. Dos partidas simultáneas no se mezclan.
- **`ai_move`** devuelve, además de la jugada, si salió limpia o fue respaldo, las opciones
  ofrecidas y el tiempo de respuesta. Si Ollama no contesta, responde **503** con el código
  `LLM_UNAVAILABLE`: nunca inventa una jugada.
- **Los errores** salen siempre con la misma forma, `{"error": {"code", "message"}}`, gracias a
  los tres manejadores de excepciones del principio.

Al final, la ruta comodín sirve la aplicación Angular compilada, y `/legacy` la página antigua.

### `arena/api_server.py`

```{.python .numberLines}
"""
Vertex Chess Arena — API V3 (FastAPI)
Vertex Coders LLC — Denis Sanchez Leyva, Miami FL

Sirve a la app Angular (frontend/) y a la página vieja (arena/index.html).

Endpoints
  GET  /health                     estado de la API y de Ollama
  GET  /api/players                jugadores disponibles (modelos de Ollama + motor del árbitro)
  POST /api/ai-move                jugada de una IA para un FEN (modos pure | arbiter | engine)
  POST /api/human-play             compatibilidad con la página vieja
  GET  /api/games                  historial de partidas guardadas
  POST /api/games                  guardar partida terminada (PGN con relojes)
  GET  /api/tournaments            lista de torneos
  GET  /api/tournaments/{id}       un torneo
  PUT  /api/tournaments/{id}       crear / actualizar un torneo

Configuración por variables de entorno (todas opcionales):
  OLLAMA_URL        http://127.0.0.1:11434
  ALLOWED_ORIGINS   http://localhost:4200,http://127.0.0.1:4200
  ARENA_DATA_DIR    <proyecto>/logs
  FRONTEND_DIST     <proyecto>/frontend/dist/vertex-chess-arena/browser

Correr desde E:\\vertex-chess-arena\\arena :
    ..\\venv\\Scripts\\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import chess
import chess.pgn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from engine_arbiter import ChessArbiter

log = logging.getLogger("vertex.arena")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

ARENA_DIR = Path(__file__).resolve().parent
BASE_DIR = ARENA_DIR.parent
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200").split(",")
    if o.strip()
]
DATA_DIR = Path(os.getenv("ARENA_DATA_DIR", str(BASE_DIR / "logs")))
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", str(BASE_DIR / "frontend" / "dist" / "vertex-chess-arena" / "browser")))

GAMES_LOG = DATA_DIR / "arena_games.jsonl"
PGN_LOG = DATA_DIR / "matches_history.pgn"
TOURNAMENTS_DIR = DATA_DIR / "tournaments"

ENGINE_ID = "vertex-engine"

# Plantel conocido. "available" se calcula en vivo contra Ollama.
ROSTER: list[dict[str, str]] = [
    {"model": "vertexqwen-v3", "name": "Qwen 2.5 · 3B · V3", "family": "qwen",
     "description": "Entrenamiento espejo de Gemma: 5,000 posiciones, pérdida solo en la respuesta, 625 pasos."},
    {"model": "vertexgemma", "name": "Gemma 2 · 2B", "family": "gemma",
     "description": "QLoRA r=8 sobre 5,000 posiciones, 625 pasos."},
    {"model": "vertexqwen", "name": "Qwen 2.5 · 3B · legacy", "family": "qwen",
     "description": "Adaptador viejo de 80 pasos (dataset de 3,000, sin máscara). Se conserva para comparar."},
]
ROSTER_IDS = {p["model"] for p in ROSTER}

app = FastAPI(
    title="Vertex Chess Arena API",
    description="Duelo de modelos afinados (Qwen vs Gemma) con relojes y torneos — Vertex Coders LLC",
    version="3.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Errores con formato único {"error": {"code", "message"}}
# ---------------------------------------------------------------------------
class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail={"code": code, "message": message})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_REQUEST", "message": f"Campo inválido: {where} — {first.get('msg', '')}"}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    log.exception("Error no controlado: %s", exc)
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "Error interno del servidor."}})


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------
def ollama_models(timeout: float = 2.0) -> set[str] | None:
    """Nombres de modelos instalados en Ollama, o None si Ollama no responde."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = set()
        for m in data.get("models", []):
            name = m.get("name", "")
            names.add(name)
            names.add(name.removesuffix(":latest"))
        return names
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Un árbitro por partida (el árbitro guarda historial para el anti-repetición)
# ---------------------------------------------------------------------------
_ARBITERS: "OrderedDict[str, ChessArbiter]" = OrderedDict()
_ARBITERS_LOCK = threading.Lock()
_MAX_ARBITERS = 128


def arbiter_for(game_id: str | None) -> ChessArbiter:
    key = game_id or "__shared__"
    with _ARBITERS_LOCK:
        arb = _ARBITERS.get(key)
        if arb is None:
            arb = ChessArbiter(ollama_url=OLLAMA_URL, fallback="random")
            _ARBITERS[key] = arb
        _ARBITERS.move_to_end(key)
        while len(_ARBITERS) > _MAX_ARBITERS:
            _ARBITERS.popitem(last=False)
        return arb


# ---------------------------------------------------------------------------
# Modelos de request / response
# ---------------------------------------------------------------------------
GAME_ID_PATTERN = r"^[A-Za-z0-9_-]{1,80}$"
TOURNAMENT_ID_PATTERN = r"^[a-z0-9-]{6,64}$"


class AIMoveRequest(BaseModel):
    fen: str = Field(..., max_length=120, description="Tablero en FEN")
    model_name: str = Field("vertexqwen-v3", max_length=60)
    mode: Literal["pure", "arbiter", "engine"] = "pure"
    game_id: str | None = Field(None, pattern=GAME_ID_PATTERN)


class HumanMoveRequest(BaseModel):
    fen: str = Field(..., max_length=120)
    move_san_or_uci: str = Field(..., max_length=12)
    ai_opponent: str = Field("vertexqwen-v3", max_length=60)
    mode: Literal["pure", "arbiter", "engine"] = "pure"


class SavedGame(BaseModel):
    pgn: str = Field(..., max_length=200_000)
    white: str = Field(..., max_length=80)
    black: str = Field(..., max_length=80)
    result: Literal["1-0", "0-1", "1/2-1/2", "*"]
    termination: str = Field(..., max_length=60)
    time_control: str = Field(..., max_length=20)
    plies: int = Field(..., ge=0, le=2000)
    tournament_id: str | None = Field(None, pattern=TOURNAMENT_ID_PATTERN)
    round: int | None = Field(None, ge=1, le=500)
    stats: dict[str, Any] = Field(default_factory=dict)


def _parse_board(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError:
        raise ApiError(400, "INVALID_FEN", "El FEN no es válido.")
    if not board.is_valid():
        raise ApiError(400, "INVALID_FEN", "La posición no es legal.")
    return board


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    models = ollama_models()
    return {"status": "ok", "ollama": "up" if models is not None else "down", "version": app.version}


@app.get("/api/players")
def players():
    installed = ollama_models()
    out = []
    for p in ROSTER:
        out.append({**p, "kind": "llm", "available": bool(installed and p["model"] in installed)})
    out.append({
        "model": ENGINE_ID, "name": "Motor del árbitro", "family": "engine", "kind": "engine",
        "description": "Alpha-beta prof. 2 + quiescencia, sin LLM. Línea base para comparar.",
        "available": True,
    })
    return {"ollama": "up" if installed is not None else "down", "players": out}


@app.post("/api/ai-move")
def ai_move(req: AIMoveRequest):
    board = _parse_board(req.fen)
    if board.is_game_over():
        raise ApiError(409, "GAME_OVER", "La partida ya terminó en esa posición.")

    engine_only = req.mode == "engine" or req.model_name == ENGINE_ID
    if not engine_only and req.model_name not in ROSTER_IDS:
        raise ApiError(400, "UNKNOWN_MODEL", f"Modelo desconocido: {req.model_name}")

    arbiter = arbiter_for(req.game_id)
    t0 = time.perf_counter()
    if engine_only:
        move = arbiter.get_options(board, "arbiter")[0]
        san = board.san(move)
        arbiter.recent_positions.append(arbiter._pos_key(board))
        board.push(move)
        arbiter.recent_positions.append(arbiter._pos_key(board))
        board.pop()
        res = {"move_obj": move, "move_san": san, "move_uci": move.uci(), "clean_hit": True,
               "raw_output": "motor", "mode": "engine", "options": [san]}
    else:
        res = arbiter.request_model_move(req.model_name, board, mode=req.mode)
        if res["raw_output"].startswith("ERROR_OLLAMA"):
            log.warning("Ollama no respondió para %s: %s", req.model_name, res["raw_output"])
            raise ApiError(503, "LLM_UNAVAILABLE", "Ollama no respondió. ¿Está corriendo y el modelo creado?")
    think_ms = int((time.perf_counter() - t0) * 1000)

    board.push(res["move_obj"])
    return {
        "model": req.model_name,
        "mode": res["mode"],
        "played_san": res["move_san"],
        "played_uci": res["move_uci"],
        "clean_hit": res["clean_hit"],
        "raw_output": res["raw_output"][:300],
        "options_count": len(res.get("options", [])),
        "think_ms": think_ms,
        "new_fen": board.fen(),
        "game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
    }


@app.post("/api/human-play")
def human_play(req: HumanMoveRequest):
    """Compatibilidad con arena/index.html (página vieja)."""
    board = _parse_board(req.fen)
    move = None
    try:
        move = board.parse_san(req.move_san_or_uci)
    except ValueError:
        try:
            cand = chess.Move.from_uci(req.move_san_or_uci.lower())
            move = cand if cand in board.legal_moves else None
        except ValueError:
            move = None
    if move is None:
        raise ApiError(400, "ILLEGAL_MOVE", f"Movimiento ilegal: {req.move_san_or_uci}")
    human_san = board.san(move)
    board.push(move)
    if board.is_game_over():
        return {"human_move": human_san, "ai_move_san": None, "new_fen": board.fen(),
                "game_over": True, "result": board.result()}
    ai = ai_move(AIMoveRequest(fen=board.fen(), model_name=req.ai_opponent, mode=req.mode))
    return {"human_move": human_san, "ai_model": req.ai_opponent, "ai_move_san": ai["played_san"],
            "ai_move_uci": ai["played_uci"], "ai_clean_hit": ai["clean_hit"], "new_fen": ai["new_fen"],
            "game_over": ai["game_over"], "result": ai["result"]}


_FILE_LOCK = threading.Lock()


@app.post("/api/games", status_code=201)
def save_game(game: SavedGame):
    if chess.pgn.read_game(__import__("io").StringIO(game.pgn)) is None:
        raise ApiError(400, "INVALID_PGN", "El PGN no se pudo leer.")
    record = game.model_dump()
    record["id"] = uuid.uuid4().hex[:12]
    record["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _FILE_LOCK:
        with open(GAMES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        with open(PGN_LOG, "a", encoding="utf-8") as f:
            f.write(game.pgn.strip() + "\n\n")
    return {"id": record["id"], "saved_at": record["saved_at"]}


@app.get("/api/games")
def list_games(limit: int = Query(50, ge=1, le=500), tournament_id: str | None = None):
    if not GAMES_LOG.exists():
        return []
    rows = []
    with open(GAMES_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if tournament_id and rec.get("tournament_id") != tournament_id:
                continue
            rows.append(rec)
    return list(reversed(rows))[:limit]


def _tournament_path(tid: str) -> Path:
    if not re.fullmatch(TOURNAMENT_ID_PATTERN, tid):
        raise ApiError(400, "INVALID_ID", "Identificador de torneo inválido.")
    return TOURNAMENTS_DIR / f"{tid}.json"


@app.get("/api/tournaments")
def list_tournaments():
    if not TOURNAMENTS_DIR.exists():
        return []
    out = []
    for p in TOURNAMENTS_DIR.glob("*.json"):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({k: t.get(k) for k in ("id", "name", "format", "status", "createdAt", "timeControl")} |
                   {"players": len(t.get("participants", []))})
    return sorted(out, key=lambda t: t.get("createdAt") or "", reverse=True)


@app.get("/api/tournaments/{tid}")
def get_tournament(tid: str):
    path = _tournament_path(tid)
    if not path.exists():
        raise ApiError(404, "NOT_FOUND", "Torneo no encontrado.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/api/tournaments/{tid}")
async def put_tournament(tid: str, request: Request):
    path = _tournament_path(tid)
    raw = await request.body()
    if len(raw) > 2_000_000:
        raise ApiError(413, "TOO_LARGE", "El torneo es demasiado grande.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApiError(400, "INVALID_JSON", "JSON inválido.")
    if not isinstance(data, dict) or data.get("id") != tid:
        raise ApiError(400, "INVALID_TOURNAMENT", "El cuerpo debe ser un torneo con el mismo id de la URL.")
    TOURNAMENTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with _FILE_LOCK:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Frontend: app Angular compilada si existe; si no, la página vieja.
# ---------------------------------------------------------------------------
@app.get("/legacy")
def legacy_ui():
    return FileResponse(ARENA_DIR / "index.html")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise ApiError(404, "NOT_FOUND", "Ruta no encontrada.")
    if FRONTEND_DIST.exists():
        target = (FRONTEND_DIST / full_path).resolve()
        if full_path and target.is_file() and FRONTEND_DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
    return FileResponse(ARENA_DIR / "index.html")
```
