import datetime
from pathlib import Path
import chess
import chess.pgn
from engine_arbiter import ChessArbiter

BASE_DIR = Path("E:/vertex-chess-arena").resolve()
PGN_LOG = BASE_DIR / "logs" / "matches_history.pgn"

def run_ai_vs_ai_match(white_model: str = "vertexqwen", black_model: str = "vertexgemma", max_moves: int = 80) -> None:
    arbiter = ChessArbiter()
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Vertex Chess Arena: Architecture Duel"
    game.headers["Site"] = "Miami, FL (Vertex Coders Lab)"
    game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    game.headers["White"] = white_model
    game.headers["Black"] = black_model
    node = game

    stats = {white_model: {"clean": 0, "fallback": 0}, black_model: {"clean": 0, "fallback": 0}}

    print(f"\n{'='*65}")
    print(f">>> INICIANDO DUELO: BLANCAS ({white_model}) vs NEGRAS ({black_model})")
    print(f"{'='*65}\n")

    ply = 0
    while not board.is_game_over() and ply < (max_moves * 2):
        ply += 1
        current_model = white_model if board.turn == chess.WHITE else black_model
        side_label = "BLANCAS" if board.turn == chess.WHITE else "NEGRAS"

        res = arbiter.request_model_move(current_model, board)
        move = res["move_obj"]
        san_str = res["move_san"]

        if res["clean_hit"]:
            stats[current_model]["clean"] += 1
            tag = "OK"
        else:
            stats[current_model]["fallback"] += 1
            tag = "FALLBACK"

        print(f"Jugada {(ply+1)//2} [{side_label} - {current_model}]: {san_str} ({res['move_uci']}) [{tag}]")
        board.push(move)
        node = node.add_variation(move)

    result = board.result()
    game.headers["Result"] = result

    print(f"\n{'='*65}")
    print(f">>> PARTIDA FINALIZADA | Resultado: {result} ({board.outcome().termination.name if board.outcome() else 'MAX_MOVES'})")
    print(f">>> Precisión de jugadas limpias:")
    print(f"    - {white_model}: {stats[white_model]['clean']} limpias / {stats[white_model]['fallback']} fallbacks")
    print(f"    - {black_model}: {stats[black_model]['clean']} limpias / {stats[black_model]['fallback']} fallbacks")
    print(f"{'='*65}\n")

    with open(PGN_LOG, "a", encoding="utf-8") as f:
        f.write(str(game) + "\n\n")
    print(f">>> Partida guardada en PGN: {PGN_LOG}")

if __name__ == "__main__":
    run_ai_vs_ai_match(white_model="vertexqwen", black_model="vertexgemma")