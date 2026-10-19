
import asyncio
import json
import os
import sys
from pathlib import Path

import chess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------
# Configuración de rutas
# ---------------------------------------------------------

# Añadir la raíz del proyecto al path de Python.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arena.engine_arbiter import ChessArbiter

# ---------------------------------------------------------
# Inicialización
# ---------------------------------------------------------

app = Server("vertex-chess-mcp")

arbiter = ChessArbiter(
    ollama_url=os.getenv(
        "OLLAMA_URL",
        "http://127.0.0.1:11434"
    )
)

ALLOWED_MODELS = {"vertexqwen", "vertexgemma"}


def json_response(payload: dict) -> list[TextContent]:
    """Devuelve una respuesta JSON compatible con MCP."""
    return [
        TextContent(
            type="text",
            text=json.dumps(payload, indent=2, ensure_ascii=False)
        )
    ]


def parse_board(fen: str) -> chess.Board:
    """Construye un tablero y comprueba la validez de su posición."""
    if not isinstance(fen, str) or not fen.strip():
        raise ValueError("Debes proporcionar una posición FEN.")

    board = chess.Board(fen)

    if not board.is_valid():
        raise ValueError(
            f"Posición FEN inválida. Código de validación: "
            f"{board.status()}"
        )

    return board


def parse_legal_move(
    board: chess.Board,
    move_text: str
) -> chess.Move | None:
    """Acepta SAN o UCI, pero únicamente movimientos legales."""
    if not isinstance(move_text, str) or not move_text.strip():
        return None

    move_text = move_text.strip()

    # Primero intentamos SAN: Nf3, O-O, Qxd5, etc.
    try:
        return board.parse_san(move_text)
    except ValueError:
        pass

    # Después intentamos UCI: e2e4, e7e8q, etc.
    try:
        move = chess.Move.from_uci(move_text.lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass

    return None


# ---------------------------------------------------------
# Herramientas disponibles para los agentes MCP
# ---------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_ai_chess_move",
            description=(
                "Solicita una jugada a un modelo de Vertex Chess "
                "mediante Ollama. Acepta vertexqwen o vertexgemma "
                "y devuelve la jugada, el FEN resultante y el estado "
                "de la partida."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "fen": {
                        "type": "string",
                        "description": "Posición actual del tablero en FEN."
                    },
                    "model_name": {
                        "type": "string",
                        "enum": ["vertexqwen", "vertexgemma"],
                        "description": "Modelo de Vertex Chess."
                    }
                },
                "required": ["fen", "model_name"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="validate_and_push_move",
            description=(
                "Valida un movimiento SAN o UCI, lo ejecuta sobre "
                "el tablero y devuelve el nuevo FEN y el estado "
                "de la partida."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "fen": {
                        "type": "string",
                        "description": "Posición actual del tablero en FEN."
                    },
                    "move": {
                        "type": "string",
                        "description": (
                            "Movimiento SAN o UCI; por ejemplo Nf3, "
                            "O-O o e2e4."
                        )
                    }
                },
                "required": ["fen", "move"],
                "additionalProperties": False
            }
        )
    ]


# ---------------------------------------------------------
# Ejecución de herramientas
# ---------------------------------------------------------

@app.call_tool()
async def call_tool(
    name: str,
    arguments: dict
) -> list[TextContent]:

    if not isinstance(arguments, dict):
        return json_response({"error": "Los argumentos deben ser un objeto."})

    # =====================================================
    # 1. Obtener una jugada de la IA
    # =====================================================

    if name == "get_ai_chess_move":
        try:
            board = parse_board(arguments.get("fen"))
        except (ValueError, TypeError) as exc:
            return json_response({"error": str(exc)})

        model_name = arguments.get("model_name")

        if model_name not in ALLOWED_MODELS:
            return json_response({
                "error": "Modelo no permitido.",
                "allowed_models": sorted(ALLOWED_MODELS)
            })

        if board.is_game_over(claim_draw=True):
            return json_response({
                "game_over": True,
                "result": board.result(claim_draw=True),
                "fen": board.fen()
            })

        try:
            # La inferencia es síncrona. Ejecutarla en un hilo evita
            # bloquear el bucle de eventos del servidor MCP.
            res = await asyncio.to_thread(
                arbiter.request_model_move,
                model_name,
                board
            )

            move = res.get("move_obj")

            # Nunca ejecutar a ciegas una respuesta del modelo.
            if not isinstance(move, chess.Move) or move not in board.legal_moves:
                return json_response({
                    "error": "El árbitro no devolvió una jugada legal.",
                    "model": model_name,
                    "raw_output": res.get("raw_output")
                })

            played_san = board.san(move)
            played_uci = move.uci()
            board.push(move)

            game_over = board.is_game_over(claim_draw=True)

            return json_response({
                "success": True,
                "model": model_name,
                "played_san": played_san,
                "played_uci": played_uci,
                "clean_hit": res.get("clean_hit", False),
                "raw_output": res.get("raw_output", ""),
                "new_fen": board.fen(),
                "game_over": game_over,
                "result": (
                    board.result(claim_draw=True)
                    if game_over else None
                )
            })

        except Exception as exc:
            # No se ocultan los fallos: se devuelven como error MCP.
            return json_response({
                "error": "Falló la obtención de la jugada de IA.",
                "model": model_name,
                "details": str(exc)
            })

    # =====================================================
    # 2. Validar y ejecutar una jugada
    # =====================================================

    if name == "validate_and_push_move":
        try:
            board = parse_board(arguments.get("fen"))
        except (ValueError, TypeError) as exc:
            return json_response({"error": str(exc)})

        move_text = arguments.get("move")

        if board.is_game_over(claim_draw=True):
            return json_response({
                "error": "La partida ya ha terminado.",
                "game_over": True,
                "result": board.result(claim_draw=True),
                "fen": board.fen()
            })

        move = parse_legal_move(board, move_text)

        if move is None:
            return json_response({
                "success": False,
                "error": "Movimiento ilegal o formato no reconocido.",
                "received_move": move_text,
                "fen": board.fen()
            })

        san_played = board.san(move)
        uci_played = move.uci()

        board.push(move)

        game_over = board.is_game_over(claim_draw=True)

        return json_response({
            "success": True,
            "move_san": san_played,
            "move_uci": uci_played,
            "new_fen": board.fen(),
            "game_over": game_over,
            "result": (
                board.result(claim_draw=True)
                if game_over else None
            )
        })

    return json_response({
        "error": f"Herramienta desconocida: {name}"
    })


# ---------------------------------------------------------
# Arranque del servidor MCP por STDIO
# ---------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
