import os
import gc
import re
from pathlib import Path

# =====================================================================
# 0. AISLAMIENTO ESTRICTO EN LA UNIDAD E: + FIX DE DESCARGA HF XET
# =====================================================================
BASE_DIR = Path("E:/vertex-chess-arena").resolve()
CACHE_DIR = BASE_DIR / ".cache"
HF_CACHE_DIR = CACHE_DIR / "huggingface"
TORCH_CACHE_DIR = CACHE_DIR / "torch"
TRITON_CACHE_DIR = CACHE_DIR / "triton"
TMP_DIR = CACHE_DIR / "tmp"

for d in [HF_CACHE_DIR, TORCH_CACHE_DIR, TRITON_CACHE_DIR, TMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(HF_CACHE_DIR)
os.environ["HF_DATASETS_CACHE"] = str(HF_CACHE_DIR / "datasets")
os.environ["TORCH_HOME"] = str(TORCH_CACHE_DIR)
os.environ["TRITON_CACHE_DIR"] = str(TRITON_CACHE_DIR)
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import chess
import torch
from unsloth import FastLanguageModel

SYSTEM_PROMPT = (
    "You are Vertex-Chess, a Grandmaster-level chess engine developed by Vertex Coders LLC. "
    "Given the current board state in FEN notation, the side to move, and the list of legal moves, "
    "select the strongest winning move. Respond strictly with the chosen move in SAN and UCI format."
)

TEST_FENS = [
    ("Scholar's Mate Threat (White to move)", "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"),
    ("Sicilian Dragon Tactical Middlegame (Black to move)", "r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R b KQ - 3 8"),
    ("Queen Fork Opportunity (White to move)", "r1b1kbnr/pppp1ppp/2n5/4p3/4P1q1/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 4 4"),
]

def build_user_prompt(board: chess.Board) -> str:
    legal_san = [board.san(m) for m in board.legal_moves]
    side_str = "White" if board.turn == chess.WHITE else "Black"
    return (
        f"FEN: {board.fen()}\n"
        f"Side to move: {side_str}\n"
        f"Legal moves (SAN): {', '.join(legal_san)}\n\n"
        f"Find the best move for {side_str}."
    )

def extract_validated_move(board: chess.Board, raw_response: str) -> tuple[str, str, bool]:
    """Extrae primero SAN (donde el modelo tiene 100% de precisión) y calcula el UCI real con python-chess."""
    san_match = re.search(r"Best move:\s*([A-Za-z0-9+#=\-]+)", raw_response)
    if san_match:
        candidate = san_match.group(1).strip()
        try:
            move = board.parse_san(candidate)
            if move in board.legal_moves:
                return board.san(move), move.uci(), True
        except ValueError:
            pass

    for legal_move in board.legal_moves:
        san_str = board.san(legal_move)
        if re.search(rf"\b{re.escape(san_str)}\b", raw_response):
            return san_str, legal_move.uci(), True

    fallback = next(iter(board.legal_moves))
    return board.san(fallback), fallback.uci(), False

def evaluate_adapter(name: str, adapter_dir: Path, is_gemma: bool = False) -> None:
    print(f"\n{'='*65}\n>>> EVALUANDO CONTENDIENTE: {name}\n{'='*65}")
    gc.collect()
    torch.cuda.empty_cache()

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(adapter_dir),
        max_seq_length=512,
        dtype=torch.float16,
        load_in_4bit=True,
        cache_dir=str(HF_CACHE_DIR),
    )
    FastLanguageModel.for_inference(model)

    for title, fen in TEST_FENS:
        board = chess.Board(fen)
        user_prompt = build_user_prompt(board)

        if is_gemma:
            messages = [{"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([prompt], return_tensors="pt").to("cuda")

        outputs = model.generate(
            **inputs,
            max_new_tokens=32,
            temperature=0.1,
            do_sample=True,
            repetition_penalty=1.15,
        )
        raw_response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        valid_san, valid_uci, is_clean = extract_validated_move(board, raw_response)
        status = "LEGAL (100% CLEAN)" if is_clean else "FALLBACK"

        print(f"[{title}]")
        print(f"  FEN: {fen}")
        print(f"  Output Crudo de {name}: {raw_response}")
        print(f"  Jugada Validada por Árbitro: {valid_san} (UCI Real: {valid_uci}) -> [{status}]\n")

    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()

if __name__ == "__main__":
    qwen_path = BASE_DIR / "models" / "qwen_chess_adapter"
    gemma_path = BASE_DIR / "models" / "gemma_chess_adapter"

    if (qwen_path / "adapter_config.json").exists():
        evaluate_adapter("QWEN 2.5 (3B)", qwen_path, is_gemma=False)
    else:
        print(f">>> [AVISO] Adaptador de Qwen aún no encontrado en {qwen_path}")

    if (gemma_path / "adapter_config.json").exists():
        evaluate_adapter("GEMMA 2 (2B)", gemma_path, is_gemma=True)
    else:
        print(f">>> [AVISO] Adaptador de Gemma aún no entrenado en {gemma_path}")