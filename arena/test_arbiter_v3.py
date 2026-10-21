"""Tests del árbitro V3 (parser estricto, modos, fallback, prompt de entrenamiento).
No necesitan Ollama. Correr desde E:\\vertex-chess-arena\\arena :
    ..\\venv\\Scripts\\python.exe -m unittest -v test_arbiter_v3.py
"""
import json
import unittest
from pathlib import Path

import chess

from engine_arbiter import ChessArbiter, SYSTEM_PROMPT

DATASET = Path(__file__).resolve().parents[1] / "dataset" / "processed" / "train_chess_elite.jsonl"


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.arb = ChessArbiter(fallback="random", seed=1)
        # 1...Bd5 b3 Kg6: negras juegan; Bxb3 es captura legal
        self.board = chess.Board("8/3B4/6k1/p2b1p2/5P1p/PP5K/6P1/8 b - - 0 1")
        self.opts = list(self.board.legal_moves)

    def test_best_move_format(self):
        mv, ok = self.arb.parse_llm_move(self.board, "Best move: Bxb3 (UCI: d5b3)", self.opts)
        self.assertTrue(ok)
        self.assertEqual(self.board.san(mv), "Bxb3")

    def test_bare_san(self):
        mv, ok = self.arb.parse_llm_move(self.board, "Bxb3", self.opts)
        self.assertTrue(ok)

    def test_fake_capture_is_rejected(self):
        # Antes parse_san aceptaba "Bxf7" como Bf7 aunque no hay nada que capturar
        _, ok = self.arb.parse_llm_move(self.board, "Best move: Bxf7 (UCI: g4f7)", self.opts)
        self.assertFalse(ok)

    def test_prose_is_rejected(self):
        raw = "The strongest tactical move in this position is **Kf6** (UCI: g6) with a SAN of Kf6."
        _, ok = self.arb.parse_llm_move(self.board, raw, self.opts)
        self.assertFalse(ok)

    def test_uci_only(self):
        mv, ok = self.arb.parse_llm_move(self.board, "UCI: g6f6", self.opts)
        self.assertTrue(ok)
        self.assertEqual(mv.uci(), "g6f6")

    def test_check_suffix_ignored(self):
        b = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
        mv, ok = self.arb.parse_llm_move(b, "Best move: Ra8 (UCI: a1a8)", list(b.legal_moves))
        self.assertTrue(ok)
        self.assertEqual(b.san(mv), "Ra8#")

    def test_option_outside_candidates_rejected(self):
        only = [chess.Move.from_uci("g6f6")]
        _, ok = self.arb.parse_llm_move(self.board, "Best move: Bxb3", only)
        self.assertFalse(ok)


class FallbackTests(unittest.TestCase):
    def test_random_fallback_not_always_first(self):
        arb = ChessArbiter(fallback="random", seed=3)
        b = chess.Board()
        opts = list(b.legal_moves)
        picks = {arb.parse_llm_move(b, "garbage", opts)[0] for _ in range(30)}
        self.assertGreater(len(picks), 1)

    def test_engine_fallback_is_first(self):
        arb = ChessArbiter(fallback="engine")
        b = chess.Board()
        opts = list(b.legal_moves)
        self.assertEqual(arb.parse_llm_move(b, "garbage", opts)[0], opts[0])


class PromptAndModeTests(unittest.TestCase):
    def test_prompt_matches_training_format(self):
        rec = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])
        board = chess.Board(rec["fen"])
        arb = ChessArbiter(mode="pure")
        prompt = arb.build_prompt(board, arb.get_options(board))
        self.assertEqual(rec["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(rec["messages"][1]["content"].split("\n")[0], prompt.split("\n")[0])
        self.assertEqual(rec["messages"][1]["content"].split("\n")[-1], prompt.split("\n")[-1])
        self.assertEqual(
            set(rec["messages"][1]["content"].split("\n")[1].split(": ", 1)[1].split(", ")),
            set(prompt.split("\n")[1].split(": ", 1)[1].split(", ")),
        )

    def test_pure_mode_offers_all_legal(self):
        b = chess.Board()
        self.assertEqual(len(ChessArbiter(mode="pure").get_options(b)), 20)

    def test_arbiter_mode_offers_at_most_4(self):
        b = chess.Board()
        self.assertLessEqual(len(ChessArbiter(mode="arbiter").get_options(b)), 4)

    def test_repetition_filter(self):
        arb = ChessArbiter()
        b = chess.Board("6k1/5ppp/8/8/8/8/5PPP/1R4K1 w - - 0 1")
        # marcamos como recientes las posiciones tras Rb2 y Rb3
        for u in ("b1b2", "b1b3"):
            b.push(chess.Move.from_uci(u)); arb.recent_positions.append(arb._pos_key(b)); b.pop()
        opts = arb.get_options(b)
        self.assertNotIn(chess.Move.from_uci("b1b2"), opts)
        self.assertNotIn(chess.Move.from_uci("b1b3"), opts)

    def test_mop_up_kq_vs_k_mates(self):
        """KQ vs K: con el ranking de mop-up el árbitro debe dar mate sin ahogar."""
        arb = ChessArbiter(fallback="engine")
        b = chess.Board("8/8/8/4k3/8/8/8/3QK3 w - - 0 1")
        for _ in range(60):
            if b.is_game_over(claim_draw=True):
                break
            arb.recent_positions.append(arb._pos_key(b))
            if b.turn == chess.WHITE:
                mv = arb.get_options(b)[0]
                arb.last_piece_squares[b.turn].append(mv.to_square)
            else:
                mv = next(iter(b.legal_moves))
            b.push(mv)
        self.assertTrue(b.is_checkmate(), f"No hubo mate: {b.fen()} {b.outcome(claim_draw=True)}")


if __name__ == "__main__":
    unittest.main()
