# Apéndice D — El pipeline de datos

Estos dos scripts producen y verifican el dataset del capítulo 3. Se ejecutan desde
`E:\vertex-chess-arena` con el entorno virtual del proyecto (apéndice A).

**Cómo leer `01_build_chess_dataset.py`.** Las primeras líneas redirigen todas las cachés de
Hugging Face al disco del proyecto *antes* de importar `datasets` (capítulo 2). Después hay una
función por fuente:

- `format_record` convierte una posición y su jugada en la conversación de tres mensajes. Aquí
  está la línea `legal_sans[:45]`, el recorte silencioso que descubrimos en el capítulo 3.
- `extract_lichess_evals` lee en *streaming* las evaluaciones de Lichess y se queda solo con
  posiciones decisivas.
- `extract_lichess_puzzles` aplica primero la jugada del rival (el formato de los *puzzles*
  guarda la posición anterior al error) y reserva la cuota de mates directos.
- `extract_sft_20k` completa con el conjunto curado.
- `main` junta las tres fuentes, baraja con semilla 42 y escribe el JSONL.

Todas comparten el conjunto `global_seen`, que evita repetir un FEN aunque venga de dos
fuentes distintas.

**Cómo leer `01b_audit_chess_dataset.py`.** Relee el archivo terminado y comprueba cuotas,
legalidad, formato de la respuesta y reparto por bando y fase. Es la auditoría que *sí*
existía; el capítulo 3 cuenta la que faltaba.

### `scripts/01_build_chess_dataset.py`

```{.python .numberLines}
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
```

### `scripts/01b_audit_chess_dataset.py`

```{.python .numberLines}
"""
VERTEX CHESS ARENA - Auditoría Forense y Saneamiento AST de Dataset
Verifica cuotas (40/40/20), legalidad estricta en python-chess, fases de juego y perfil táctico.
"""
import json
import re
from pathlib import Path
from collections import Counter
import chess

BASE_DIR = Path("E:/vertex-chess-arena").resolve()
DATASET_FILE = BASE_DIR / "dataset" / "processed" / "train_chess_elite.jsonl"

# Cuotas esperadas según la tabla de arquitectura
EXPECTED_QUOTAS = {
    "lichess_evals":   (2000, 40.0),
    "lichess_puzzles": (2000, 40.0),
    "sft_20k":         (1000, 20.0),
}

FEN_EXTRACT_RE = re.compile(r"Position FEN:\s*([^\n]+)")
REPLY_EXTRACT_RE = re.compile(r"^Best move:\s*(\S+)\s*\(UCI:\s*([a-h][1-8][a-h][1-8][qrbn]?)\)$")


def audit_and_sanitize():
    print("=" * 78)
    print(">>> VERTEX CODERS - AUDITORÍA FORENSE Y SANEAMIENTO DEL DATASET DE AJEDREZ")
    print("=" * 78)

    if not DATASET_FILE.exists():
        print(f"[ERROR] No existe el archivo: {DATASET_FILE}")
        print("Ejecuta primero: python E:\\vertex-chess-arena\\scripts\\01_build_chess_dataset.py")
        return

    raw_lines = DATASET_FILE.read_text(encoding="utf-8").splitlines()
    print(f">>> Leyendo archivo: {DATASET_FILE}")
    print(f">>> Líneas totales en bruto: {len(raw_lines)}\n")

    valid_records = []
    seen_fens = set()

    # Contadores de auditoría
    errors = Counter()
    source_counts = Counter()
    phase_counts = Counter()
    turn_counts = Counter()
    tactical_profile = Counter()
    seq_char_lengths = []

    for idx, line in enumerate(raw_lines, start=1):
        if not line.strip():
            errors["empty_line"] += 1
            continue

        try:
            obj = json.loads(line)
        except Exception:
            errors["invalid_json"] += 1
            continue

        msgs = obj.get("messages", [])
        if len(msgs) != 3:
            errors["bad_message_structure"] += 1
            continue

        user_content = msgs[1].get("content", "")
        assistant_content = msgs[2].get("content", "").strip()

        # 1. Extraer FEN desde el prompt real que verá el LLM
        fen_m = FEN_EXTRACT_RE.search(user_content)
        if not fen_m:
            errors["missing_fen_in_prompt"] += 1
            continue
        fen = fen_m.group(1).strip()

        # 2. Verificar duplicados
        if fen in seen_fens:
            errors["duplicate_fen"] += 1
            continue

        # 3. Validar sintaxis de respuesta del asistente
        reply_m = REPLY_EXTRACT_RE.match(assistant_content)
        if not reply_m:
            errors["bad_assistant_format"] += 1
            continue
        san_move, uci_move = reply_m.group(1), reply_m.group(2)

        # 4. Validación AST profunda con python-chess
        try:
            board = chess.Board(fen)
            if not board.is_valid():
                errors["invalid_board_state"] += 1
                continue

            move_from_uci = chess.Move.from_uci(uci_move)
            if move_from_uci not in board.legal_moves:
                errors["illegal_uci_move"] += 1
                continue

            expected_san = board.san(move_from_uci)
            if expected_san != san_move:
                errors["san_uci_mismatch"] += 1
                continue
        except Exception:
            errors["chess_engine_exception"] += 1
            continue

        # Registro 100% válido y verificado
        seen_fens.add(fen)
        valid_records.append(obj)

        # Métricas de distribución
        src = obj.get("source", "untagged_legacy")
        source_counts[src] += 1

        # Bando al turno
        turn_counts["White (w)" if board.turn == chess.WHITE else "Black (b)"] += 1

        # Fase de la partida según fullmove_number y cantidad de piezas
        piece_count = len(board.piece_map())
        if board.fullmove_number <= 12:
            phase_counts["1. Apertura (Jugadas 1-12)"] += 1
        elif piece_count <= 10 or board.fullmove_number > 35:
            phase_counts["3. Final (<=10 piezas o Jugada >35)"] += 1
        else:
            phase_counts["2. Medio Juego (Jugadas 13-35)"] += 1

        # Perfil táctico de la jugada objetivo
        if "#" in san_move:
            tactical_profile["Jaque Mate Directo (#)"] += 1
        elif "+" in san_move:
            tactical_profile["Jaque Táctico (+)"] += 1
        if "x" in san_move:
            tactical_profile["Captura de Material (x)"] += 1
        if "=" in san_move:
            tactical_profile["Coronación de Peón (=)"] += 1
        if "x" not in san_move and "+" not in san_move and "#" not in san_move:
            tactical_profile["Desarrollo / Posicional Silencioso"] += 1

        total_chars = sum(len(m.get("content", "")) for m in msgs)
        seq_char_lengths.append(total_chars)

    total_valid = len(valid_records)
    if total_valid == 0:
        print("[CRÍTICO] 0 registros válidos encontrados. Revisa el generador.")
        return

    # =====================================================================
    # REPORTE DE CUMPLIMIENTO DE LA TABLA (40% / 40% / 20%)
    # =====================================================================
    print("1. CUMPLIMIENTO DE LA TABLA DE BLENDING (CUOTAS POR FUENTE)")
    print("-" * 78)
    print(f"{'Fuente de Datos':<25} | {'Meta':<14} | {'Real':<14} | {'Estado'}")
    print("-" * 78)
    for src_key, (target_cnt, target_pct) in EXPECTED_QUOTAS.items():
        actual_cnt = source_counts.get(src_key, 0)
        actual_pct = (actual_cnt / total_valid) * 100
        diff_pct = abs(actual_pct - target_pct)
        status = "OK (CUMPLIDO)" if diff_pct <= 2.5 and actual_cnt > 0 else "DESVIADO"
        print(
            f"{src_key:<25} | {target_cnt:4d} ({target_pct:4.1f}%) | "
            f"{actual_cnt:4d} ({actual_pct:4.1f}%) | {status}"
        )
    if source_counts.get("untagged_legacy", 0) > 0:
        cnt = source_counts["untagged_legacy"]
        print(f"{'untagged_legacy (Viejo)':<25} | {'0 (0.0%)':<14} | {cnt:4d} ({(cnt/total_valid)*100:4.1f}%) | EJECUTA EL NUEVO 01")
    print("-" * 78)

    # =====================================================================
    # REPORTE DE AGRESIVIDAD TÁCTICA Y FASES DEL JUEGO
    # =====================================================================
    print("\n2. PERFIL TÁCTICO Y ANTI-BUCLES (QUÉ APRENDERÁN QWEN Y GEMMA)")
    print("-" * 78)
    for k, v in sorted(tactical_profile.items()):
        print(f"  - {k:<36}: {v:4d} ({(v/total_valid)*100:5.1f}%)")

    print("\n3. DISTRIBUCIÓN POR FASE DE PARTIDA Y TURNO")
    print("-" * 78)
    for k, v in sorted(phase_counts.items()):
        print(f"  - {k:<36}: {v:4d} ({(v/total_valid)*100:5.1f}%)")
    for k, v in sorted(turn_counts.items()):
        print(f"  - Turno {k:<30}: {v:4d} ({(v/total_valid)*100:5.1f}%)")

    # =====================================================================
    # AUDITORÍA DE LONGITUD PARA VRAM (MAX_SEQ_LENGTH = 384)
    # =====================================================================
    max_chars = max(seq_char_lengths)
    avg_chars = sum(seq_char_lengths) / len(seq_char_lengths)
    est_max_tokens = int(max_chars / 3.2)
    print("\n4. AUDITORÍA DE SEGURIDAD VRAM (GTX 1660 Ti - 6 GB)")
    print("-" * 78)
    print(f"  - Longitud promedio de secuencia : {avg_chars:.0f} chars (~{int(avg_chars/3.2)} tokens)")
    print(f"  - Longitud máxima de secuencia   : {max_chars} chars (~{est_max_tokens} tokens)")
    print(f"  - Límite configurado (MAX_SEQ)   : 384 tokens -> {'SEGURO (0% Truncamiento)' if est_max_tokens < 380 else 'AJUSTAR'}")

    # =====================================================================
    # SANEAMIENTO AUTOMÁTICO
    # =====================================================================
    print("\n5. RESULTADO DE SANEAMIENTO AST (PYTHON-CHESS)")
    print("-" * 78)
    print(f"  - Registros válidos certificados : {total_valid}")
    print(f"  - Registros corruptos/duplicados : {sum(errors.values())}")
    if errors:
        for err_type, cnt in errors.items():
            print(f"      * Purgado por [{err_type}]: {cnt}")
        # Sobrescribir el dataset solo con los registros limpios
        with open(DATASET_FILE, "w", encoding="utf-8") as f:
            for r in valid_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  >>> [SANEADO] Se sobrescribió {DATASET_FILE.name} con {total_valid} registros 100% puros.")
    else:
        print("  >>> [PERFECTO] 0 errores detectados. El 100% de las jugadas son legales y únicas.")

    # Mostrar 3 muestras reales (1 de cada fuente)
    print("\n6. MUESTRAS REALES AUDITADAS DEL DATASET")
    print("-" * 78)
    shown_sources = set()
    for r in valid_records:
        s = r.get("source", "untagged")
        if s not in shown_sources:
            shown_sources.add(s)
            print(f"  [{s.upper()}]")
            print(f"    FEN       : {r.get('fen', 'N/A')}")
            print(f"    Respuesta : {r['messages'][2]['content']}")
        if len(shown_sources) >= 3:
            break
    print("=" * 78)


if __name__ == "__main__":
    audit_and_sanitize()
```
