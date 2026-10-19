"""Regression tests for Vertex Chess Arbiter using Denis's two Gemma games.

Run from E:\\vertex-chess-arena (with python-chess installed):
    python -m unittest -v test_vertex_chess_regression.py

These tests validate legal replay, final checkmates, mate-in-one candidate handling,
and the key tactical candidate from game 2. They do not claim engine-strength
validation or replace testing against Stockfish.
"""
from __future__ import annotations

import io
import unittest
import chess
import chess.pgn

from vertex_chess_arbiter_improved import ChessArbiter

GAME_1 = """
[Event "Denis vs Gemma"]
[White "Denis"]
[Black "Gemma"]
[Result "1-0"]

1. d4 e6 2. Nf3 Bb4+ 3. c3 Bd6 4. e3 Nc6 5. Be2 Nf6 6. O-O O-O
7. Nbd2 b6 8. a3 Bb7 9. b4 h5 10. c4 Ng4 11. c5 bxc5 12. bxc5 Be7
13. Rb1 Bc8 14. Bb2 d5 15. Ba1 Re8 16. a4 g6 17. Nb3 Nb4 18. Qd2 Nc6
19. a5 Bf6 20. a6 Re7 21. Na5 Bd7 22. Nb7 Qf8 23. h3 Nh6 24. Rfe1 Kh8
25. Qb2 Ree8 26. Nd2 h4 27. Bf3 Ne7 28. e4 dxe4 29. Nxe4 Bg7 30. Ng5 Rec8
31. Re4 Nhf5 32. g4 Nh6 33. Bg2 Nd5 34. Nf3 Qe7 35. g5 Nf5 36. Rg4 Kh7
37. Nxh4 Rcb8 38. Nxf5 gxf5 39. Rh4+ Kg8 40. Rh5 Bc6 41. Qe2 Bxb7
42. Rxb7 Rc8 43. Bxd5 Qd7 44. Bg2 Kf8 45. c6 Qd6 46. Qf3 f6 47. Bc3 fxg5
48. Rxg5 Rd8 49. Qh5 f4 50. Qg6 Qe7 51. Rg4 e5 52. dxe5 Rd1+ 53. Kh2 Rad8
54. Rxf4+ Bf6 55. exf6 Qd6 56. Qg7+ Ke8 57. f7+ Ke7 58. f8=Q+ Ke6
59. Qxd6+ R1xd6 60. Rxc7 Ra8 61. Rf6# 1-0
"""

GAME_2 = """
[Event "Denis vs Gemma"]
[White "Denis"]
[Black "Gemma"]
[Result "1-0"]

1. d4 d5 2. Nf3 e6 3. e3 h5 4. Be2 g5 5. O-O f6 6. Nbd2 c5 7. c4 dxc4
8. Nxc4 cxd4 9. exd4 Nc6 10. a3 a5 11. Qd3 Kf7 12. Re1 b6 13. Bf1 Bd6
14. Nxd6+ Qxd6 15. Qe4 Qd5 16. Bd3 Rh6 17. Bd2 Bd7 18. Bc3 a4 19. Qe2 h4
20. Bc4 Nxd4 21. Bxd4 Qf5 22. Rad1 Kg7 23. Bxb6 Bc6 24. Nd4 Qf4
25. Nxe6+ Kh7 26. Nxf4 gxf4 27. Bd3+ f5 28. Bxf5+ Kg7 29. Qg4+ Kh8
30. Bd7 Bxd7 31. Rxd7 Ne7 32. Rexe7 Rg8 33. Qxf4 Rh5 34. Rd8 Rxd8
35. Bxd8 Kg8 36. Qg4+ Rg5 37. Qxg5+ Kh8 38. Qg7# 1-0
"""


def load_game(pgn: str):
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise AssertionError("PGN could not be parsed")
    board = game.board()
    before_last = None
    last_move = None
    for move in game.mainline_moves():
        before_last = board.copy()
        last_move = move
        board.push(move)
    return game, board, before_last, last_move


class VertexChessRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arbiter = ChessArbiter()

    def test_game_1_replays_to_checkmate(self):
        _, board, before_last, last_move = load_game(GAME_1)
        self.assertTrue(board.is_checkmate(), board.fen())
        self.assertEqual(last_move, before_last.parse_san("Rf6#"))
        self.assertIn(last_move, self.arbiter._get_candidate_moves(before_last))

    def test_game_2_replays_to_checkmate(self):
        _, board, before_last, last_move = load_game(GAME_2)
        self.assertTrue(board.is_checkmate(), board.fen())
        self.assertEqual(last_move, before_last.parse_san("Qg7#"))
        self.assertIn(last_move, self.arbiter._get_candidate_moves(before_last))

    def test_game_2_knight_tactic_is_legal_and_in_candidate_set(self):
        game, _, _, _ = load_game(GAME_2)
        board = game.board()
        target = None
        for move in game.mainline_moves():
            san = board.san(move)
            if san == "Nxe6+":
                target = (board.copy(), move)
                break
            board.push(move)
        self.assertIsNotNone(target, "Could not locate 25.Nxe6+")
        position, tactical_move = target
        self.assertIn(tactical_move, position.legal_moves)
        candidates = self.arbiter._get_candidate_moves(position)
        # Diagnostic assertion: this is the move played in the supplied game.
        # If it fails, investigate search depth/ordering rather than weakening legality tests.
        self.assertIn(tactical_move, candidates, "Arbiter pruned the game's tactical move Nxe6+")

    def test_quiescence_returns_integer_in_check_position(self):
        game, _, _, _ = load_game(GAME_2)
        board = game.board()
        for move in game.mainline_moves():
            san = board.san(move)
            if san == "Nxe6+":
                board.push(move)
                break
            board.push(move)
        self.assertTrue(board.is_check())
        score = self.arbiter._quiescence(board, -1_000_000, 1_000_000, chess.WHITE, qdepth=0)
        self.assertIsInstance(score, int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
