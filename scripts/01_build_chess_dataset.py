"""
VERTEX CHESS ARENA - Motor de Ingesta Híbrida V2 (Deduplicación Canónica + Instinto de Mate)
Garantiza exactamente:
  - 2,000 (40.0%) lichess_evals   (0% duplicados canónicos, ventaja clara)
  - 2,000 (40.0%) lichess_puzzles (Incluye cuota dedicada de Mates Directos '#' + Táctica Élite)
  - 1,000 (20.0%) sft_20k         (Posiciones maestras de agi-noobs/chess-sft-20k)
"""
import os
import json
import random
from pathlib import Path

BASE_DIR = Path("E:/vertex-chess-arena").resolve()
CACHE_DIR = BASE_DIR / ".cache" / "huggingface"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(CACHE_DIR)
os.environ["HF_DATASETS_CACHE"] = str(CACHE_DIR / "datasets")
os.environ["HF_HUB_DISABLE_XET"] = "1"

import chess
from datasets import load_dataset

OUTPUT_DIR = BASE_DIR / "dataset" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "train_chess_elite.jsonl"

QUOTA_EVALS = 2000
QUOTA_PUZZLES = 2000
QUOTA_SFT = 1000

SYSTEM_PROMPT = (
    "You are an elite chess grandmaster engine created by Vertex Coders. "
    "Analyze the FEN board state and the list of legal moves, then output "
    "the single strongest tactical move in both SAN and UCI formats."
)


def format_record(board: chess.Board, target_move: chess.Move, source_tag: str) -> dict | None:
    """Valida legalidad en python-chess y devuelve el registro normalizado."""
    if not board.is_valid() or target_move not in board.legal_moves:
        return None

    san_move = board.san(target_move)
    uci_move = target_move.uci()

    legal_sans = [board.san(m) for m in board.legal_moves]
    legal_str = ", ".join(legal_sans[:45])

    user_prompt = (
        f"Position FEN: {board.fen()}\n"
        f"Legal moves (SAN): {legal_str}\n"
        f"Select the best move."
    )
    assistant_reply = f"Best move: {san_move} (UCI: {uci_move})"

    return {
        "source": source_tag,
        "fen": board.fen(),
        "san": san_move,
        "uci": uci_move,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_reply},
        ]
    }


def extract_lichess_evals(quota: int, global_seen: set) -> list[dict]:
    print(f"\n>>> [1/3] Extrayendo {quota} posiciones únicas de Lichess/chess-position-evaluations...")
    records = []
    try:
        ds = load_dataset("Lichess/chess-position-evaluations", split="train", streaming=True)
        for row in ds:
            fen = row.get("fen")
            line = row.get("line")
            cp = row.get("cp")
            mate = row.get("mate")

            if not fen or not line:
                continue

            is_decisive = (mate is not None and mate != 0) or (cp is not None and abs(cp) >= 150)
            if not is_decisive:
                continue

            moves_uci = line.split()
            if not moves_uci:
                continue

            try:
                board = chess.Board(fen)
                if len(board.piece_map()) < 7 or board.fullmove_number > 40:
                    continue

                canonical_fen = board.fen()
                if canonical_fen in global_seen:
                    continue

                move = chess.Move.from_uci(moves_uci[0])
                rec = format_record(board, move, "lichess_evals")
                if rec:
                    records.append(rec)
                    global_seen.add(canonical_fen)
                    if len(records) % 500 == 0:
                        print(f"    -> Evaluaciones únicas recolectadas: {len(records)}/{quota}")
            except Exception:
                continue

            if len(records) >= quota:
                break
    except Exception as e:
        print(f"    [!] Aviso en Evaluaciones: {e}")

    return records


def extract_lichess_puzzles(quota: int, global_seen: set, tag_override: str = "lichess_puzzles") -> list[dict]:
    print(f"\n>>> [2/3] Extrayendo {quota} golpes tácticos y mates de Lichess/chess-puzzles...")
    records = []
    mate_target = quota // 4  # Asegurar al menos 25% (500) de Jaque Mate directo (#)
    mates_collected = 0
    tactics_target = quota - mate_target
    tactics_collected = 0

    try:
        ds = load_dataset("Lichess/chess-puzzles", split="train", streaming=True)
        for row in ds:
            rating = int(row.get("Rating") or 0)
            fen = row.get("FEN")
            moves_str = row.get("Moves")
            if not fen or not moves_str:
                continue

            uci_list = moves_str.split()
            if len(uci_list) < 2:
                continue

            try:
                board = chess.Board(fen)
                opponent_blunder = chess.Move.from_uci(uci_list[0])
                if opponent_blunder not in board.legal_moves:
                    continue
                board.push(opponent_blunder)

                canonical_fen = board.fen()
                if canonical_fen in global_seen:
                    continue

                winning_move = chess.Move.from_uci(uci_list[1])
                if winning_move not in board.legal_moves:
                    continue

                san_candidate = board.san(winning_move)
                is_direct_mate = "#" in san_candidate

                if is_direct_mate and mates_collected < mate_target:
                    rec = format_record(board, winning_move, tag_override)
                    if rec:
                        records.append(rec)
                        global_seen.add(canonical_fen)
                        mates_collected += 1
                        if len(records) % 500 == 0:
                            print(f"    -> Puzzles recolectados: {len(records)}/{quota} (Mates '#': {mates_collected})")
                elif (not is_direct_mate) and rating >= 1900 and tactics_collected < tactics_target:
                    rec = format_record(board, winning_move, tag_override)
                    if rec:
                        records.append(rec)
                        global_seen.add(canonical_fen)
                        tactics_collected += 1
                        if len(records) % 500 == 0:
                            print(f"    -> Puzzles recolectados: {len(records)}/{quota} (Mates '#': {mates_collected})")
            except Exception:
                continue

            if len(records) >= quota:
                break
    except Exception as e:
        print(f"    [!] Aviso en Puzzles: {e}")

    return records


def extract_sft_20k(quota: int, global_seen: set) -> list[dict]:
    print(f"\n>>> [3/3] Extrayendo {quota} posiciones curadas de agi-noobs/chess-sft-20k...")
    records = []
    try:
        ds = load_dataset("agi-noobs/chess-sft-20k", split="train", streaming=True)
        for row in ds:
            fen = row.get("fen") or row.get("FEN")
            move_str = (
                row.get("best_move_uci")
                or row.get("best_move_san")
                or row.get("pv_uci")
                or row.get("best_move")
                or row.get("uci_move")
                or row.get("move")
            )

            if not fen or not move_str:
                continue

            try:
                board = chess.Board(fen)
                canonical_fen = board.fen()
                if canonical_fen in global_seen:
                    continue

                first_token = str(move_str).strip().split()[0]
                try:
                    move = chess.Move.from_uci(first_token)
                except ValueError:
                    move = board.parse_san(first_token)

                rec = format_record(board, move, "sft_20k")
                if rec:
                    records.append(rec)
                    global_seen.add(canonical_fen)
                    if len(records) % 250 == 0:
                        print(f"    -> SFT recolectados: {len(records)}/{quota}")
            except Exception:
                continue

            if len(records) >= quota:
                break
    except Exception as e:
        print(f"    [!] Aviso en SFT-20k: {e}")

    return records


def main():
    print("=" * 70)
    print(">>> INICIANDO VERTEX GRANDMASTER BLEND V2 (0% DUPLICADOS CANÓNICOS)")
    print("=" * 70)

    global_seen_fens = set()

    eval_records = extract_lichess_evals(QUOTA_EVALS, global_seen_fens)
    puzzle_records = extract_lichess_puzzles(QUOTA_PUZZLES, global_seen_fens)
    sft_records = extract_sft_20k(QUOTA_SFT, global_seen_fens)

    all_records = eval_records + puzzle_records + sft_records
    random.seed(42)
    random.shuffle(all_records)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\n" + "=" * 70)
    print(f">>> ¡DATASET HÍBRIDO V2 COMPLETADO CON ÉXITO!")
    print(f"    - Aperturas/Estrategia (Lichess Evals): {len(eval_records)}")
    print(f"    - Táctica Letal (Lichess Puzzles):      {len(puzzle_records)}")
    print(f"    - Refuerzo SFT (Chess-SFT-20k):         {len(sft_records)}")
    print(f"    - TOTAL ÚNICO MEZCLADO:                 {len(all_records)} posiciones")
    print("=" * 70)


if __name__ == "__main__":
    main()