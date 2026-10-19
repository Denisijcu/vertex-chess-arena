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