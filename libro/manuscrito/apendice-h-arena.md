# Apéndice H — La arena por consola y los diagnósticos

Tres scripts cortos que hicieron más por este libro que cualquier otro:

- **`match_runner.py`** juega partidas entre dos modelos, **alternando colores**, reclamando la
  triple repetición (`claim_draw`) y guardando cada resultado en `logs/arena_results.jsonl`. El
  modo (`--mode pure` o `--mode arbiter`) es un argumento, no una constante escondida.
- **`probe_bias.py`** es el sondeo del capítulo 9: las mismas posiciones del dataset para cada
  modelo, con su prompt de entrenamiento exacto, y dos contadores (formato y acierto). Sin
  tablero, sin árbitro, sin respaldo.
- **`duel_both_colors.py`** es el duelo del capítulo 8: dos partidas con el árbitro original y
  colores cambiados. Fue el que produjo la tabla que cambió la historia.

### `arena/match_runner.py`

```{.python .numberLines}
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
```

### `diagnostics/probe_bias.py`

```{.python .numberLines}
"""
Diagnóstico Vertex Chess Arena — ¿quién decide realmente las jugadas?
Correr desde E:\\vertex-chess-arena\\arena :
    ..\\venv\\Scripts\\python.exe ..\\diagnostics\\probe_bias.py 40 vertexqwen-v3 vertexgemma
Requiere Ollama corriendo con vertexqwen y vertexgemma.
"""
import json, random, sys, time, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "arena"))
import chess
from engine_arbiter import ChessArbiter, SYSTEM_PROMPT
import urllib.request

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "diagnostics" / "probe_results.jsonl"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
MODELS = sys.argv[2:] or ["vertexqwen", "vertexgemma"]
random.seed(7)
recs = [json.loads(l) for l in open(BASE / "dataset/processed/train_chess_elite.jsonl", encoding="utf-8")]
sample = random.sample(recs, N)
TRAIN_SYS = recs[0]["messages"][0]["content"]

def chat(model, messages):
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": 0.05, "top_p": 0.9, "repeat_penalty": 1.15, "num_predict": 48}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["message"]["content"]

def msgs(model, sys_p, user):
    if "gemma" in model:
        return [{"role": "user", "content": f"{sys_p}\n\n{user}"}]
    return [{"role": "system", "content": sys_p}, {"role": "user", "content": user}]

arb = ChessArbiter()
OUT.write_text("", encoding="utf-8")
for i, r in enumerate(sample):
    board = chess.Board(r["fen"])
    cands = arb._get_candidate_moves(board)
    arena_prompt = arb.build_prompt(board, cands)
    train_prompt = r["messages"][1]["content"]   # prompt EXACTO del entrenamiento (todas las legales)
    row = {"i": i, "fen": r["fen"], "label": r["san"], "source": r["source"],
           "cands": [board.san(m) for m in cands]}
    for model in MODELS:
        t = time.time()
        raw_a = chat(model, msgs(model, SYSTEM_PROMPT, arena_prompt))
        mv, ok = arb.parse_llm_move(board, raw_a, cands)
        raw_t = chat(model, msgs(model, TRAIN_SYS, train_prompt))
        legal = list(board.legal_moves)
        mv_t, ok_t = arb.parse_llm_move(board, raw_t, legal)
        row[model] = {"arena_raw": raw_a[:120], "arena_ok": ok, "arena_idx": cands.index(mv) if ok else -1,
                      "train_raw": raw_t[:120], "train_ok": ok_t, "train_hit": ok_t and board.san(mv_t) == r["san"],
                      "secs": round(time.time() - t, 1)}
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(i, row["label"], "|", " | ".join(row[m]["train_raw"][:40] for m in MODELS), flush=True)
print("\nRESUMEN (posiciones del dataset de entrenamiento)")
rows = [json.loads(l) for l in open(OUT, encoding="utf-8")]
for m in MODELS:
    fmt = sum(r[m]["train_raw"].startswith("Best move:") for r in rows)
    hit = sum(r[m]["train_hit"] for r in rows)
    print(f"  {m:<16} formato 'Best move:' {fmt}/{len(rows)} | acierta la jugada del dataset {hit}/{len(rows)}")
print("DONE")
```

### `diagnostics/duel_both_colors.py`

```{.python .numberLines}
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
```
