"""
Vertex Chess Arena — Match Runner V3 (torneo justo).

- Alterna colores en cada partida (antes Qwen siempre jugaba con blancas).
- Modo "pure" por defecto: el LLM elige entre TODAS las jugadas legales (mide al modelo).
  Modo "arbiter": el motor filtra top-4 y el LLM elige (mide al sistema híbrido).
- Fallback aleatorio: una respuesta inválida ya no se convierte en la mejor jugada del motor.
- Cobra tablas por triple repetición y regla de 50 jugadas (claim_draw=True).
- Guarda PGN en logs/matches_history.pgn y un resumen por partida en logs/arena_results.jsonl.

Correr desde E:\\vertex-chess-arena\\arena :
    ..\\venv\\Scripts\\python.exe match_runner.py --games 10 --mode pure
    ..\\venv\\Scripts\\python.exe match_runner.py --games 10 --mode arbiter --qwen vertexqwen
"""
import argparse
import datetime
import json
from pathlib import Path

import chess
import chess.pgn

from engine_arbiter import ChessArbiter

BASE_DIR = Path(__file__).resolve().parents[1]
PGN_LOG = BASE_DIR / "logs" / "matches_history.pgn"
RESULTS_LOG = BASE_DIR / "logs" / "arena_results.jsonl"


def play_game(white: str, black: str, mode: str, max_moves: int, seed: int, verbose: bool) -> dict:
    arbiter = ChessArbiter(mode=mode, fallback="random", seed=seed)
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = f"Vertex Chess Arena V3 ({mode})"
    game.headers["Site"] = "Miami, FL (Vertex Coders Lab)"
    game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    game.headers["White"] = white
    game.headers["Black"] = black
    node = game
    stats = {white: {"clean": 0, "fallback": 0}, black: {"clean": 0, "fallback": 0}}

    while not board.is_game_over(claim_draw=True) and board.ply() < max_moves * 2:
        current = white if board.turn == chess.WHITE else black
        res = arbiter.request_model_move(current, board)
        stats[current]["clean" if res["clean_hit"] else "fallback"] += 1
        if verbose:
            tag = "OK" if res["clean_hit"] else "FALLBACK"
            print(f"  {board.fullmove_number}{'.' if board.turn else '...'} {res['move_san']:<8} [{current} {tag}] {res['raw_output'][:60]!r}")
        board.push(res["move_obj"])
        node = node.add_variation(res["move_obj"])

    outcome = board.outcome(claim_draw=True)
    result = outcome.result() if outcome else "1/2-1/2"  # límite de jugadas = tablas
    termination = outcome.termination.name if outcome else "MAX_MOVES"
    game.headers["Result"] = result
    game.headers["Termination"] = termination
    with open(PGN_LOG, "a", encoding="utf-8") as f:
        f.write(str(game) + "\n\n")
    return {"white": white, "black": black, "mode": mode, "result": result,
            "termination": termination, "plies": board.ply(), "stats": stats}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=10, help="número de partidas (se alternan colores)")
    ap.add_argument("--mode", choices=["pure", "arbiter"], default="pure")
    ap.add_argument("--qwen", default="vertexqwen-v3")
    ap.add_argument("--gemma", default="vertexgemma")
    ap.add_argument("--max-moves", type=int, default=150)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    score = {args.qwen: 0.0, args.gemma: 0.0}
    totals = {args.qwen: {"clean": 0, "fallback": 0}, args.gemma: {"clean": 0, "fallback": 0}}
    for g in range(args.games):
        white, black = (args.qwen, args.gemma) if g % 2 == 0 else (args.gemma, args.qwen)
        print(f">>> Partida {g + 1}/{args.games}: {white} (B) vs {black} (N) | modo {args.mode}")
        r = play_game(white, black, args.mode, args.max_moves, seed=1000 + g, verbose=args.verbose)
        if r["result"] == "1-0":
            score[white] += 1
        elif r["result"] == "0-1":
            score[black] += 1
        else:
            score[white] += 0.5
            score[black] += 0.5
        for m in (white, black):
            for k in ("clean", "fallback"):
                totals[m][k] += r["stats"][m][k]
        r["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
        with open(RESULTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")
        print(f"    {r['result']} ({r['termination']}, {r['plies']} plies) | marcador {score}")

    print("\n" + "=" * 65)
    print(f"RESULTADO FINAL ({args.games} partidas, modo {args.mode})")
    for m in (args.qwen, args.gemma):
        t = totals[m]
        n = t["clean"] + t["fallback"]
        rate = 100 * t["clean"] / n if n else 0
        print(f"  {m:<16} puntos {score[m]:>4} | jugadas válidas {t['clean']}/{n} ({rate:.1f}%)")
    print("=" * 65)


if __name__ == "__main__":
    main()
