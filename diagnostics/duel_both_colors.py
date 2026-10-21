"""Dos partidas con colores invertidos usando el mismo árbitro que la arena.
Correr desde E:\\vertex-chess-arena\\arena :  python ..\\diagnostics\\duel_both_colors.py"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "arena"))
import chess, chess.pgn
from engine_arbiter import ChessArbiter
OUT = Path(__file__).resolve().parent / "duel_results.txt"
OUT.write_text("", encoding="utf-8")
for white, black in (("vertexqwen", "vertexgemma"), ("vertexgemma", "vertexqwen")):
    arb = ChessArbiter(); board = chess.Board(); game = chess.pgn.Game()
    game.headers.update(White=white, Black=black)
    node = game; st = {white: [0, 0, 0], black: [0, 0, 0]}  # clean, fallback, eligio_candidata_0
    while not board.is_game_over() and board.ply() < 160:
        m = white if board.turn else black
        cands = arb._get_candidate_moves(board)
        res = arb.request_model_move(m, board)
        st[m][0 if res["clean_hit"] else 1] += 1
        st[m][2] += int(res["move_obj"] == cands[0])
        board.push(res["move_obj"]); node = node.add_variation(res["move_obj"])
    game.headers["Result"] = board.result(claim_draw=True)
    txt = f"{white} (W) vs {black} (B): {board.result(claim_draw=True)} plies={board.ply()} outcome={board.outcome(claim_draw=True)}\n  stats [clean, fallback, top1]: {st}\n{game}\n\n"
    print(txt, flush=True)
    with open(OUT, "a", encoding="utf-8") as f: f.write(txt)
print("DONE")
