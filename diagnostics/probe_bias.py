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
