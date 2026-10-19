from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import chess
from engine_arbiter import ChessArbiter

ARENA_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Vertex Chess Arena API",
    description="Motor de enfrentamiento Qwen vs. Gemma y Humano vs. IA — Vertex Coders LLC",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

arbiter = ChessArbiter()

class AIMoveRequest(BaseModel):
    fen: str = Field(..., description="Estado actual del tablero en formato FEN")
    model_name: str = Field("vertexqwen", pattern="^(vertexqwen|vertexgemma)$")

class HumanMoveRequest(BaseModel):
    fen: str = Field(..., description="Estado actual del tablero en formato FEN")
    move_san_or_uci: str = Field(..., description="Jugada del usuario en formato e2e4 o Nf3")
    ai_opponent: str = Field("vertexqwen", pattern="^(vertexqwen|vertexgemma)$")

@app.get("/")
def serve_arena_ui():
    """Sirve el tablero interactivo directamente en http://127.0.0.1:8000"""
    index_file = ARENA_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="No se encontró arena/index.html")
    return FileResponse(index_file)

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "arena": "Vertex Chess Arena",
        "models": ["vertexqwen", "vertexgemma"],
    }

@app.post("/api/ai-move")
def get_ai_move(req: AIMoveRequest):
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="FEN inválido.")

    if board.is_game_over():
        return {"game_over": True, "result": board.result(), "fen": board.fen()}

    res = arbiter.request_model_move(req.model_name, board)
    board.push(res["move_obj"])

    return {
        "model": req.model_name,
        "played_san": res["move_san"],
        "played_uci": res["move_uci"],
        "clean_hit": res["clean_hit"],
        "raw_output": res["raw_output"],
        "new_fen": board.fen(),
        "game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
    }

@app.post("/api/human-play")
def play_human_turn(req: HumanMoveRequest):
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="FEN inválido.")

    move = None
    try:
        move = board.parse_san(req.move_san_or_uci)
    except ValueError:
        try:
            candidate = chess.Move.from_uci(req.move_san_or_uci.lower())
            if candidate in board.legal_moves:
                move = candidate
        except ValueError:
            pass

    if move is None:
        raise HTTPException(status_code=400, detail=f"Movimiento ilegal: {req.move_san_or_uci}")

    human_san = board.san(move)
    board.push(move)

    if board.is_game_over():
        return {
            "human_move": human_san,
            "ai_move_san": None,
            "new_fen": board.fen(),
            "game_over": True,
            "result": board.result(),
        }

    ai_res = arbiter.request_model_move(req.ai_opponent, board)
    board.push(ai_res["move_obj"])

    return {
        "human_move": human_san,
        "ai_model": req.ai_opponent,
        "ai_move_san": ai_res["move_san"],
        "ai_move_uci": ai_res["move_uci"],
        "ai_clean_hit": ai_res["clean_hit"],
        "new_fen": board.fen(),
        "game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
    }