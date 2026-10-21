import re
import json
import random
import urllib.request
from collections import deque
import chess

# V3 (2026-10-20): la arena usa EXACTAMENTE el system prompt y el formato de usuario del
# dataset de entrenamiento (dataset/processed/train_chess_elite.jsonl). Antes la arena usaba
# otro system prompt, una línea extra "Side to move" y solo 4 candidatas, y eso sacaba a los
# modelos de la distribución que aprendieron.
SYSTEM_PROMPT = (
    "You are an elite chess grandmaster engine created by Vertex Coders. Analyze the FEN board "
    "state and the list of legal moves, then output the single strongest tactical move in both "
    "SAN and UCI formats."
)
LEGACY_SYSTEM_PROMPT = (
    "You are Vertex-Chess, a Grandmaster-level chess engine developed by Vertex Coders LLC. "
    "Given the current board state in FEN notation, the side to move, and the list of legal moves, "
    "select the strongest winning move. Respond strictly with the chosen move in SAN and UCI format."
)

# Modos de juego:
#   "arbiter" -> el motor (alpha-beta prof. 2 + quiescencia) filtra hasta 4 candidatas y el LLM elige.
#                Mide al sistema híbrido motor+LLM.
#   "pure"    -> el LLM recibe TODAS las jugadas legales, igual que en el entrenamiento.
#                Mide al modelo. Es el modo justo para el duelo de arquitecturas.
MODES = ("arbiter", "pure")
# Fallback cuando la respuesta no se puede validar:
#   "random" -> jugada aleatoria entre las opciones ofrecidas (fallar NO se premia)
#   "engine" -> la mejor del motor (comportamiento viejo: fallar = jugar como el motor)
FALLBACKS = ("random", "engine")

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 950,
    chess.KING: 20000,
}

CENTER_CORE = {chess.E4, chess.D4, chess.E5, chess.D5}
CENTER_EXT = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.F4,
    chess.C5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}
RIM_SQUARES = {
    chess.A1, chess.A2, chess.A3, chess.A4, chess.A5, chess.A6, chess.A7, chess.A8,
    chess.H1, chess.H2, chess.H3, chess.H4, chess.H5, chess.H6, chess.H7, chess.H8,
}

STARTING_MINORS = {
    chess.WHITE: (chess.B1, chess.G1, chess.C1, chess.F1),
    chess.BLACK: (chess.B8, chess.G8, chess.C8, chess.F8),
}
OPTIMAL_CASTLED_KING = {
    chess.WHITE: (chess.G1, chess.C1, chess.B1),
    chess.BLACK: (chess.G8, chess.C8, chess.B8),
}
CORNER_CASTLED_KING = {
    chess.WHITE: (chess.H1, chess.A1),
    chess.BLACK: (chess.H8, chess.A8),
}


class ChessArbiter:
    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        mode: str = "arbiter",
        fallback: str = "random",
        seed: int | None = None,
    ):
        if mode not in MODES:
            raise ValueError(f"mode debe ser uno de {MODES}")
        if fallback not in FALLBACKS:
            raise ValueError(f"fallback debe ser uno de {FALLBACKS}")
        self.ollama_url = ollama_url
        self.mode = mode
        self.fallback = fallback
        self.rng = random.Random(seed)
        self.recent_positions: deque[str] = deque(maxlen=80)
        self.last_piece_squares: dict[bool, deque[int]] = {
            chess.WHITE: deque(maxlen=4),
            chess.BLACK: deque(maxlen=4),
        }
        self.consecutive_checks: dict[bool, int] = {
            chess.WHITE: 0,
            chess.BLACK: 0,
        }

    def _pos_key(self, board: chess.Board) -> str:
        parts = board.fen().split(" ")
        return " ".join(parts[:3])

    def _chebyshev_dist(self, sq1: int, sq2: int) -> int:
        return max(
            abs(chess.square_file(sq1) - chess.square_file(sq2)),
            abs(chess.square_rank(sq1) - chess.square_rank(sq2)),
        )

    def _manhattan_dist(self, sq1: int, sq2: int) -> int:
        return (
            abs(chess.square_file(sq1) - chess.square_file(sq2))
            + abs(chess.square_rank(sq1) - chess.square_rank(sq2))
        )

    def _edge_distance_bonus(self, sq: int) -> int:
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        dist_f = min(f, 7 - f)
        dist_r = min(r, 7 - r)
        return (6 - (dist_f + dist_r)) * 60

    def _get_side_material(self, board: chess.Board, color: bool) -> int:
        return sum(
            PIECE_VALUES[pc.piece_type]
            for pc in board.piece_map().values()
            if pc.color == color and pc.piece_type != chess.KING
        )

    def _is_mop_up_mode(self, board: chess.Board, perspective: bool) -> bool:
        piece_map = board.piece_map()
        if len(piece_map) > 10:
            return False
        my_mat = self._get_side_material(board, perspective)
        enemy_mat = self._get_side_material(board, not perspective)
        return (my_mat - enemy_mat) >= 350 and enemy_mat <= 100

    def _king_danger_penalty(self, board: chess.Board, king_sq: int, defender_color: bool) -> int:
        attacker_color = not defender_color
        danger = 0
        for adj_sq in board.attacks(king_sq):
            enemy_attackers = board.attackers(attacker_color, adj_sq)
            if enemy_attackers:
                my_defenders = board.attackers(defender_color, adj_sq)
                if len(enemy_attackers) >= len(my_defenders):
                    danger += 45 * len(enemy_attackers)
        return danger

    def _piece_threat_loss(self, board: chess.Board, sq: int, color: bool) -> int:
        """
        Calcula cuántos puntos estamos en riesgo de perder en la casilla 'sq' si una pieza nuestra
        está atacada por una pieza enemiga de menor valor (ej. Peón ataca Alfil en d6 -> pierde 230;
        Alfil ataca Torre en f8 -> pierde 170) o si está completamente indefensa.
        """
        pc = board.piece_at(sq)
        if not pc or pc.color != color or pc.piece_type == chess.KING:
            return 0
        my_val = PIECE_VALUES[pc.piece_type]
        enemy_color = not color
        attackers = board.attackers(enemy_color, sq)
        if not attackers:
            return 0

        min_attacker_val = min(
            PIECE_VALUES[att_pc.piece_type]
            for att_sq in attackers
            if (att_pc := board.piece_at(att_sq)) is not None
        )

        # Si la pieza no está defendida por nadie, está colgada entera
        if not board.is_attacked_by(color, sq):
            return my_val

        # Si está defendida, pero nos la ataca una pieza más barata (ej. 9.c5 contra Bd6, o 17.Bxd6 contra Rf8)
        if min_attacker_val < my_val:
            return my_val - min_attacker_val

        return 0

    def _has_any_threatened_piece(self, board: chess.Board, color: bool) -> bool:
        for sq, pc in board.piece_map().items():
            if pc.color == color and pc.piece_type != chess.KING:
                if self._piece_threat_loss(board, sq, color) >= 150:
                    return True
        return False

    def _static_material_and_board_eval(
        self,
        board: chess.Board,
        perspective: bool,
        was_winning_before: bool = False,
        allow_mop_up_eval: bool = False,
    ) -> int:
        if board.is_checkmate():
            return -100000 if board.turn == perspective else 100000

        if board.is_stalemate() or board.is_insufficient_material():
            return -80000 if was_winning_before else 0

        piece_map = board.piece_map()
        queens_count = sum(1 for pc in piece_map.values() if pc.piece_type == chess.QUEEN)
        is_endgame = (queens_count == 0) or (len(piece_map) <= 10)

        my_mat = 0
        enemy_mat = 0
        score = 0
        enemy_pawns_squares: list[int] = []

        for sq, pc in piece_map.items():
            if pc.piece_type == chess.KING:
                continue

            val = PIECE_VALUES[pc.piece_type]
            rank = chess.square_rank(sq)
            file_idx = chess.square_file(sq)
            back_rank = 0 if pc.color == chess.WHITE else 7
            seventh_rank = 6 if pc.color == chess.WHITE else 1

            if pc.color == perspective:
                my_mat += val
            else:
                enemy_mat += val
                if pc.piece_type == chess.PAWN:
                    enemy_pawns_squares.append(sq)

            if sq in CENTER_CORE:
                val += 28
            elif sq in CENTER_EXT:
                val += 16
            elif pc.piece_type == chess.KNIGHT and sq in RIM_SQUARES:
                val -= 65
            elif pc.piece_type == chess.BISHOP and sq in RIM_SQUARES:
                val -= 30

            if not is_endgame:
                if pc.piece_type in (chess.KNIGHT, chess.BISHOP) and rank == back_rank:
                    val -= 45
                elif pc.piece_type == chess.QUEEN and rank == back_rank and sq not in (chess.D1, chess.D8, chess.E1, chess.E8):
                    val -= 65

            if not is_endgame and pc.piece_type in (chess.QUEEN, chess.KNIGHT, chess.BISHOP):
                enemy_col = not pc.color
                safe_mobility = 0
                for att_sq in board.attacks(sq):
                    occupant = board.piece_at(att_sq)
                    if occupant and occupant.color == pc.color:
                        continue
                    attacked_by_cheaper = any(
                        (ep := board.piece_at(esq)) and PIECE_VALUES[ep.piece_type] < val
                        for esq in board.attackers(enemy_col, att_sq)
                    )
                    if not attacked_by_cheaper:
                        safe_mobility += 1
                if safe_mobility == 0:
                    val -= 140
                elif safe_mobility == 1:
                    val -= 60

            if pc.piece_type == chess.ROOK:
                if rank == seventh_rank:
                    val += 80
                if file_idx in (3, 4):
                    val += 28

            if pc.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                if not board.is_attacked_by(pc.color, sq):
                    val -= 30

            if pc.piece_type == chess.PAWN and (is_endgame or len(piece_map) <= 14):
                advancement = rank if pc.color == chess.WHITE else (7 - rank)
                val += (advancement * advancement) * 12

            if pc.color == perspective:
                score += val
            else:
                score -= val

        my_king = board.king(perspective)
        enemy_king = board.king(not perspective)

        if not is_endgame and my_king is not None and enemy_king is not None:
            if my_king in OPTIMAL_CASTLED_KING[perspective]:
                score += 60
            elif my_king in CORNER_CASTLED_KING[perspective]:
                score += 20
            elif chess.square_file(my_king) in (3, 4):
                score -= 35

            if enemy_king in OPTIMAL_CASTLED_KING[not perspective]:
                score -= 60
            elif enemy_king in CORNER_CASTLED_KING[not perspective]:
                score -= 20
            elif chess.square_file(enemy_king) in (3, 4):
                score += 35

            score -= self._king_danger_penalty(board, my_king, perspective)
            score += self._king_danger_penalty(board, enemy_king, not perspective)

        if is_endgame and my_king is not None and enemy_king is not None:
            if allow_mop_up_eval:
                score += self._edge_distance_bonus(enemy_king)
                k_cheb = self._chebyshev_dist(my_king, enemy_king)
                k_manh = self._manhattan_dist(my_king, enemy_king)
                score += (8 - k_cheb) * 110 + (14 - k_manh) * 45
            else:
                for sq_k, col_k in ((my_king, perspective), (enemy_king, not perspective)):
                    king_bonus = 0
                    if sq_k in CENTER_CORE:
                        king_bonus = 40
                    elif sq_k in CENTER_EXT:
                        king_bonus = 20
                    elif sq_k in RIM_SQUARES:
                        king_bonus = -30
                    if col_k == perspective:
                        score += king_bonus
                    else:
                        score -= king_bonus

                if enemy_pawns_squares:
                    min_dist_to_pawn = min(self._chebyshev_dist(my_king, psq) for psq in enemy_pawns_squares)
                    score += (8 - min_dist_to_pawn) * 45

        return score

    def _worst_enemy_tactical_reply_loss(self, board: chess.Board, my_color: bool) -> int:
        if board.is_game_over():
            return 0

        worst_delta = 0

        for reply in board.legal_moves:
            is_cap = board.is_capture(reply)
            gives_chk = board.gives_check(reply)
            if not (is_cap or gives_chk):
                continue

            victim = board.piece_at(reply.to_square)
            attacker = board.piece_at(reply.from_square)
            victim_val = PIECE_VALUES.get(victim.piece_type, 100) if victim else 0
            attacker_val = PIECE_VALUES.get(attacker.piece_type, 100) if attacker else 100

            board.push(reply)
            if board.is_checkmate():
                board.pop()
                return -90000

            can_legally_recapture = any(
                m.to_square == reply.to_square for m in board.legal_moves
            )

            fork_loss = 0
            if gives_chk:
                for attacked_sq in board.attacks(reply.to_square):
                    target_pc = board.piece_at(attacked_sq)
                    if (
                        target_pc
                        and target_pc.color == my_color
                        and target_pc.piece_type != chess.KING
                    ):
                        if not board.is_attacked_by(my_color, attacked_sq):
                            fork_loss = max(fork_loss, PIECE_VALUES[target_pc.piece_type] - 80)
                        elif attacker_val < PIECE_VALUES[target_pc.piece_type]:
                            fork_loss = max(fork_loss, PIECE_VALUES[target_pc.piece_type] - attacker_val)

            board.pop()

            if is_cap:
                if can_legally_recapture:
                    net_loss = max(0, victim_val - attacker_val)
                else:
                    net_loss = victim_val
                if gives_chk and net_loss > 0:
                    net_loss += 180
            else:
                net_loss = 0

            # Factor 1.45x para que perder un Alfil por un peón (9...exd4?? 10.cxd6) o una Torre por un Alfil
            # (17...Rc8?? 18.Bxf8) jamás pueda ser compensado por comer un peón suelto en otro lado.
            total_tactical_loss = int((net_loss + fork_loss) * 1.45)
            if -total_tactical_loss < worst_delta:
                worst_delta = -total_tactical_loss

        return worst_delta

    def _is_move_checkmate(self, board: chess.Board, mv: chess.Move) -> bool:
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        return is_mate

    def _mop_up_endgame_bonus(
        self,
        board_before: chess.Board,
        mv: chess.Move,
        board_after: chess.Board,
        my_color: bool,
    ) -> int:
        if board_after.is_stalemate():
            return -95000

        my_king_before = board_before.king(my_color)
        my_king_after = board_after.king(my_color)
        enemy_king = board_after.king(not my_color)
        if my_king_before is None or my_king_after is None or enemy_king is None:
            return 0

        bonus = 0
        piece = board_before.piece_at(mv.from_square)
        dist_before = self._chebyshev_dist(my_king_before, enemy_king)
        dist_after = self._chebyshev_dist(my_king_after, enemy_king)
        manh_before = self._manhattan_dist(my_king_before, enemy_king)
        manh_after = self._manhattan_dist(my_king_after, enemy_king)

        enemy_replies = list(board_after.legal_moves)
        if enemy_replies:
            all_lead_to_mate = True
            mate_in_next_count = 0
            for rep in enemy_replies:
                board_after.push(rep)
                has_mate = any(
                    board_after.gives_check(m2) and self._is_move_checkmate(board_after, m2)
                    for m2 in board_after.legal_moves
                )
                board_after.pop()
                if has_mate:
                    mate_in_next_count += 1
                else:
                    all_lead_to_mate = False

            if all_lead_to_mate:
                return 50000
            bonus += mate_in_next_count * 120

        if piece and piece.piece_type == chess.KING:
            if dist_after < dist_before:
                bonus += 320
            elif dist_after == dist_before and manh_after < manh_before:
                bonus += 180
            elif dist_after > dist_before:
                bonus -= 300

        elif piece and piece.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP):
            gives_chk = board_after.is_check()
            if gives_chk and dist_after > 2:
                bonus -= 350

            if piece.piece_type == chess.QUEEN and not gives_chk:
                df = abs(chess.square_file(mv.to_square) - chess.square_file(enemy_king))
                dr = abs(chess.square_rank(mv.to_square) - chess.square_rank(enemy_king))
                if (df == 1 and dr == 2) or (df == 2 and dr == 1):
                    bonus += 240

            num_escapes = len(enemy_replies)
            if 1 <= num_escapes <= 3 and not gives_chk:
                bonus += (5 - num_escapes) * 65

        return bonus

    def _evaluate_move(self, board: chess.Board, mv: chess.Move) -> int:
        my_color = board.turn
        ply = board.fullmove_number
        piece = board.piece_at(mv.from_square)
        if not piece:
            return -99999

        my_mat_before = self._get_side_material(board, my_color)
        enemy_mat_before = self._get_side_material(board, not my_color)
        mat_diff = my_mat_before - enemy_mat_before
        was_winning_before = mat_diff >= 200

        mop_up = self._is_mop_up_mode(board, my_color)
        before_eval = self._static_material_and_board_eval(
            board, my_color, was_winning_before, allow_mop_up_eval=mop_up
        )

        # Cuánto material estaba en riesgo en mv.from_square antes de mover (ej. 9.c5 contra Bd6 -> 230 pts; 17.Bxd6 contra Rf8 -> 170 pts)
        threat_loss_here = self._piece_threat_loss(board, mv.from_square, my_color)
        was_threatened_here = threat_loss_here >= 120

        victim_before = board.piece_at(mv.to_square)
        my_piece_val = PIECE_VALUES.get(piece.piece_type, 100)
        victim_before_val = PIECE_VALUES.get(victim_before.piece_type, 0) if victim_before else 0

        simplification_bonus = 0
        if victim_before and victim_before.piece_type == piece.piece_type and piece.piece_type in (chess.QUEEN, chess.ROOK):
            if mat_diff >= 250:
                simplification_bonus = 180
            elif mat_diff <= -250:
                simplification_bonus = -240

        promotion_bonus = 600 if mv.promotion == chess.QUEEN else 0

        back_rank = 0 if my_color == chess.WHITE else 7
        retreat_penalty = 0
        if (
            not mop_up
            and not was_threatened_here  # Si la pieza está amenazada, permitirle retroceder a la 1ra fila si hace falta
            and piece.piece_type in (chess.KNIGHT, chess.BISHOP)
            and chess.square_rank(mv.from_square) != back_rank
            and chess.square_rank(mv.to_square) == back_rank
            and not board.is_capture(mv)
        ):
            retreat_penalty = -165

        recent_squares = self.last_piece_squares[my_color]
        same_piece_penalty = 0
        if (
            mv.from_square in recent_squares
            and not board.is_capture(mv)
            and not was_threatened_here
            and not (mop_up and piece.piece_type == chess.KING)
        ):
            if board.gives_check(mv):
                if self.consecutive_checks[my_color] >= 1:
                    same_piece_penalty = -280 * self.consecutive_checks[my_color]
                else:
                    same_piece_penalty = -90
            else:
                same_piece_penalty = -220

        opening_bonus = 0
        my_king_sq = board.king(my_color)
        is_king_castled = (
            my_king_sq in OPTIMAL_CASTLED_KING[my_color] or my_king_sq in CORNER_CASTLED_KING[my_color]
            if my_king_sq is not None
            else False
        )
        undeveloped_minors = sum(
            1
            for sq in STARTING_MINORS[my_color]
            if (pc := board.piece_at(sq)) and pc.color == my_color and pc.piece_type in (chess.KNIGHT, chess.BISHOP)
        )

        if ply <= 14 and not mop_up:
            if piece.piece_type == chess.PAWN:
                if mv.to_square in CENTER_CORE:
                    opening_bonus += 85
                elif mv.to_square in (chess.C4, chess.C5, chess.E3, chess.D3, chess.E6, chess.D6):
                    opening_bonus += 35
                elif chess.square_file(mv.from_square) in (0, 1, 5, 6, 7) and not board.is_capture(mv):
                    if not is_king_castled or undeveloped_minors >= 2:
                        opening_bonus -= 220

            elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                if mv.from_square in STARTING_MINORS[my_color]:
                    opening_bonus += 105
                if mv.to_square in CENTER_EXT or mv.to_square in CENTER_CORE:
                    opening_bonus += 45
                if mv.to_square in RIM_SQUARES:
                    opening_bonus -= 180

            elif piece.piece_type == chess.ROOK and not board.is_castling(mv) and not board.is_capture(mv):
                opening_bonus -= 300
            elif piece.piece_type == chess.KING and not board.is_castling(mv):
                opening_bonus -= 350
            elif piece.piece_type == chess.QUEEN and ply <= 6 and not board.is_capture(mv):
                opening_bonus -= 140

        if board.is_castling(mv):
            opening_bonus += 160

        board.push(mv)
        if board.is_checkmate():
            board.pop()
            return 100000

        is_rep = self._pos_key(board) in self.recent_positions
        after_eval = self._static_material_and_board_eval(
            board, my_color, was_winning_before, allow_mop_up_eval=mop_up
        )
        material_gain = after_eval - before_eval

        enemy_can_recapture_landing = any(
            r.to_square == mv.to_square for r in board.legal_moves
        )
        bad_trade_penalty = 0
        if enemy_can_recapture_landing and my_piece_val > victim_before_val + 50:
            bad_trade_penalty = -int((my_piece_val - victim_before_val) * 1.35)

        # Bono proporcional por salvar la pieza amenazada (ej. salvar Bd6 de 9.c5 o salvar Rf8 de 17.Bxd6)
        evacuation_bonus = 0
        if was_threatened_here and self._piece_threat_loss(board, mv.to_square, my_color) == 0 and bad_trade_penalty == 0:
            evacuation_bonus = int(threat_loss_here * 0.85) + 60

        # Seguridad de la Dama: penalizar poner la Dama a salto de caballo (dist 1,2) de un Caballo enemigo activo
        # que pueda meterle un jaque doble al Rey (corrige 49...Qe3?? permitiendo 51.Nf5+!)
        queen_fork_danger = 0
        if piece.piece_type == chess.QUEEN and not mop_up:
            enemy_col = not my_color
            for esq, epc in board.piece_map().items():
                if epc.color == enemy_col and epc.piece_type == chess.KNIGHT:
                    # Si un caballo enemigo puede saltar en 1 o 2 jugadas a una casilla que ataca nuestra Dama y da jaque
                    for knight_jump in board.attacks(esq):
                        if mv.to_square in board.attacks(knight_jump):
                            queen_fork_danger -= 75
                            break

        clean_capture_bonus = 0
        if victim_before_val >= 300:
            if not enemy_can_recapture_landing:
                clean_capture_bonus = 140
            elif my_piece_val <= victim_before_val:
                clean_capture_bonus = 95

        enemy_punishment = self._worst_enemy_tactical_reply_loss(board, my_color)
        gives_chk = board.is_check()
        board.pop()

        mop_up_bonus = 0
        if mop_up and enemy_punishment == 0 and bad_trade_penalty == 0:
            b_after = board.copy()
            b_after.push(mv)
            mop_up_bonus = self._mop_up_endgame_bonus(board, mv, b_after, my_color)

        total_score = (
            material_gain
            + enemy_punishment
            + bad_trade_penalty
            + clean_capture_bonus
            + evacuation_bonus
            + queen_fork_danger
            + simplification_bonus
            + promotion_bonus
            + retreat_penalty
            + opening_bonus
            + same_piece_penalty
            + mop_up_bonus
        )

        if gives_chk and is_rep:
            total_score -= 12000
        elif is_rep:
            total_score -= 10000

        return total_score

    def _search_eval(self, board: chess.Board, perspective: bool) -> int:
        """Evaluación ligera para búsqueda táctica; positiva favorece a perspective."""
        if board.is_checkmate():
            return -100000 if board.turn == perspective else 100000
        if board.is_stalemate() or board.is_insufficient_material() or board.is_fivefold_repetition():
            return 0

        score = 0
        for sq, pc in board.piece_map().items():
            if pc.piece_type == chess.KING:
                continue
            value = PIECE_VALUES[pc.piece_type]
            rank = chess.square_rank(sq)
            file_idx = chess.square_file(sq)
            if pc.piece_type == chess.PAWN:
                advance = rank if pc.color == chess.WHITE else 7 - rank
                value += advance * 8
            if sq in CENTER_CORE:
                value += 18
            elif sq in CENTER_EXT:
                value += 8
            if pc.piece_type == chess.KNIGHT and sq in RIM_SQUARES:
                value -= 25
            sign = 1 if pc.color == perspective else -1
            score += sign * value

        # Preferimos seguridad del rey y penalizamos el jaque al bando evaluado.
        if board.is_check():
            score += -35 if board.turn == perspective else 35
        return score

    def _quiescence(self, board: chess.Board, alpha: int, beta: int,
                    perspective: bool, qdepth: int = 4) -> int:
        """Extiende la búsqueda en posiciones tácticas con capturas y promociones."""
        stand_pat = self._search_eval(board, perspective)
        maximizing = board.turn == perspective
        if board.is_game_over():
            if board.is_checkmate():
                return -100000 if board.turn == perspective else 100000
            return 0
        if qdepth <= 0:
            return stand_pat

        in_check = board.is_check()
        # En jaque no existe "stand pat": hay que buscar TODAS las evasiones legales,
        # incluidas las que no capturan ni dan jaque.
        if not in_check:
            if maximizing:
                if stand_pat >= beta:
                    return beta
                alpha = max(alpha, stand_pat)
            else:
                if stand_pat <= alpha:
                    return alpha
                beta = min(beta, stand_pat)

        tactical = (
            list(board.legal_moves) if in_check else [
                m for m in board.legal_moves
                if board.is_capture(m) or m.promotion is not None or board.gives_check(m)
            ]
        )
        if not tactical:
            return stand_pat
        tactical.sort(
            key=lambda m: (
                1 if m.promotion else 0,
                PIECE_VALUES.get(
                    board.piece_at(m.to_square).piece_type, 0
                ) if board.is_capture(m) and board.piece_at(m.to_square) else 0,
                1 if board.gives_check(m) else 0,
            ),
            reverse=True,
        )

        if maximizing:
            value = stand_pat
            for move in tactical:
                board.push(move)
                value = max(value, self._quiescence(board, alpha, beta, perspective, qdepth - 1))
                board.pop()
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = stand_pat
            for move in tactical:
                board.push(move)
                value = min(value, self._quiescence(board, alpha, beta, perspective, qdepth - 1))
                board.pop()
                beta = min(beta, value)
                if beta <= alpha:
                    break
            return value

    def _search_root_moves(self, board: chess.Board, depth: int = 2) -> list[tuple[int, chess.Move]]:
        """Búsqueda minimax con poda alpha-beta; devuelve las jugadas mejor puntuadas."""
        perspective = board.turn
        scored = []
        moves = list(board.legal_moves)

        # Primero mate en una; no permitimos que las heurísticas lo oculten.
        for move in moves:
            board.push(move)
            mate = board.is_checkmate()
            board.pop()
            if mate:
                return [(100000, move)]

        # Orden táctico para encontrar antes capturas, jaques y promociones.
        def order_key(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            capture_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 100) if attacker else 100
            return (
                1 if move.promotion else 0,
                1 if board.gives_check(move) else 0,
                capture_value - attacker_value // 10 if board.is_capture(move) else 0,
            )

        moves.sort(key=order_key, reverse=True)
        for move in moves:
            board.push(move)
            if board.is_checkmate():
                value = 100000
            elif board.is_game_over():
                value = 0
            else:
                value = self._search_minimax(
                    board, depth - 1, -1000000, 1000000, perspective
                )
            board.pop()
            scored.append((value, move))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    def _search_minimax(self, board: chess.Board, depth: int, alpha: int,
                        beta: int, perspective: bool) -> int:
        if board.is_game_over():
            if board.is_checkmate():
                return -100000 if board.turn == perspective else 100000
            return 0
        if depth <= 0:
            return self._quiescence(board, alpha, beta, perspective)

        maximizing = board.turn == perspective
        moves = list(board.legal_moves)
        moves.sort(
            key=lambda m: (
                1 if m.promotion else 0,
                1 if board.is_capture(m) else 0,
                1 if board.gives_check(m) else 0,
            ),
            reverse=True,
        )

        if maximizing:
            value = -1000000
            for move in moves:
                board.push(move)
                child = self._search_minimax(board, depth - 1, alpha, beta, perspective)
                board.pop()
                value = max(value, child)
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = 1000000
            for move in moves:
                board.push(move)
                child = self._search_minimax(board, depth - 1, alpha, beta, perspective)
                board.pop()
                value = min(value, child)
                beta = min(beta, value)
                if beta <= alpha:
                    break
            return value

    def _get_candidate_moves(self, board: chess.Board) -> list[chess.Move]:
        """Combina heurísticas existentes con una búsqueda táctica independiente."""
        all_legal = list(board.legal_moves)
        if len(all_legal) <= 1:
            return all_legal

        # Mate inmediato siempre tiene prioridad absoluta.
        for move in all_legal:
            board.push(move)
            is_mate = board.is_checkmate()
            board.pop()
            if is_mate:
                return [move]

        # La búsqueda evita que las bonificaciones manuales dominen tácticas evidentes.
        # Profundidad 2 + quiescencia: coste moderado para una partida interactiva.
        search_scores = self._search_root_moves(board, depth=2)
        if not search_scores:
            return all_legal[:1]

        best_search = search_scores[0][0]
        # Conservamos hasta 4 candidatas cercanas a la mejor puntuación táctica.
        # El LLM decide entre opciones razonables, pero no entre jugadas claramente inferiores.
        acceptable = [move for score, move in search_scores if score >= best_search - 180]

        # V3: en finales ganados (mop-up) la búsqueda de profundidad 2 no ve el plan de mate,
        # así que ordenamos las jugadas aceptables con _evaluate_move (caja de la Dama, marcha
        # del Rey, mate en 2, anti-ahogado). Antes _evaluate_move no se llamaba en ningún sitio.
        if self._is_mop_up_mode(board, board.turn):
            acceptable.sort(key=lambda m: self._evaluate_move(board, m), reverse=True)

        # V3: anti-bucles. Si hay alternativas, descartamos jugadas que repiten una posición
        # reciente (evita series tipo Ra7+ Ra8+ Ra7+ ... o Nf8+ Nd7+ ...).
        fresh = [m for m in acceptable if not self._repeats_recent(board, m)]
        search_candidates = (fresh or acceptable)[:4]

        # Si la búsqueda detecta que todas las opciones pierden material, no recortamos
        # a una sola jugada por heurísticas ruidosas: mantenemos varias defensas.
        return search_candidates or [search_scores[0][1]]

    def _repeats_recent(self, board: chess.Board, mv: chess.Move) -> bool:
        board.push(mv)
        key = self._pos_key(board)
        board.pop()
        return key in self.recent_positions

    def get_options(self, board: chess.Board, mode: str | None = None) -> list[chess.Move]:
        """Jugadas que se le ofrecen al LLM según el modo."""
        mode = mode or self.mode
        if mode == "pure":
            return list(board.legal_moves)
        return self._get_candidate_moves(board)

    def build_prompt(self, board: chess.Board, candidate_moves: list[chess.Move]) -> str:
        """Formato idéntico al del dataset de entrenamiento."""
        legal_san = [board.san(m) for m in candidate_moves]
        return (
            f"Position FEN: {board.fen()}\n"
            f"Legal moves (SAN): {', '.join(legal_san)}\n"
            f"Select the best move."
        )

    @staticmethod
    def _norm_san(san: str) -> str:
        return san.strip().rstrip(".,;:)").replace("0", "O").replace("+", "").replace("#", "").replace("!", "").replace("?", "")

    def parse_llm_move(
        self,
        board: chess.Board,
        raw_response: str,
        candidate_moves: list[chess.Move],
    ) -> tuple[chess.Move, bool]:
        """Parser ESTRICTO (V3).

        Solo cuenta como acierto limpio si el modelo nombra una de las opciones ofrecidas:
          1. "Best move: <SAN>"  con el SAN exacto (se ignoran +, #, !, ?), o
          2. "UCI: <uci>" exacto, o
          3. la respuesta completa es un SAN exacto (p. ej. "Kxe2").
        Ya no se usa board.parse_san() (aceptaba "Bxf7" sin captura) ni se escanea la prosa
        buscando cualquier cosa con forma de jugada.
        """
        clean_text = raw_response.replace("*", "").replace("`", "").strip()
        san_map = {self._norm_san(board.san(m)): m for m in candidate_moves}
        candidate_set = set(candidate_moves)

        best = re.search(r"Best\s+move\s*:\s*(\S+)", clean_text, re.IGNORECASE)
        if best:
            mv = san_map.get(self._norm_san(best.group(1)))
            if mv is not None:
                return mv, True

        uci = re.search(r"UCI\s*:\s*([a-h][1-8][a-h][1-8][qrbn]?)\b", clean_text, re.IGNORECASE)
        if uci:
            try:
                mv = chess.Move.from_uci(uci.group(1).lower())
                if mv in candidate_set:
                    return mv, True
            except ValueError:
                pass

        mv = san_map.get(self._norm_san(clean_text))
        if mv is not None:
            return mv, True

        return self._fallback_move(candidate_moves), False

    def _fallback_move(self, candidate_moves: list[chess.Move]) -> chess.Move:
        if self.fallback == "engine" or len(candidate_moves) == 1:
            return candidate_moves[0]
        return self.rng.choice(candidate_moves)

    def _chat_ollama(self, model_name: str, messages: list[dict]) -> str:
        """Pide la respuesta a Ollama. Devuelve el texto, o 'ERROR_OLLAMA: ...' si falla."""
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.05,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "num_predict": 48,
                "num_ctx": 1024,  # V3: en modo "pure" la lista completa de legales es más larga
            },
        }
        req = urllib.request.Request(
            f"{self.ollama_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "")
        except Exception as e:
            return f"ERROR_OLLAMA: {e}"

    @staticmethod
    def build_messages(model_name: str, user_prompt: str) -> list[dict]:
        """Mensajes en el formato del entrenamiento. Gemma no tiene rol de sistema."""
        if "gemma" in model_name.lower():
            return [{"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}]
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def request_model_move(self, model_name: str, board: chess.Board, mode: str | None = None,
                           chat_fn=None) -> dict:
        """chat_fn(model_name, messages) -> texto. Por defecto, Ollama (V4: inyectable para el Space de HF)."""
        if board.fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"):
            self.recent_positions.clear()
            self.last_piece_squares[chess.WHITE].clear()
            self.last_piece_squares[chess.BLACK].clear()
            self.consecutive_checks[chess.WHITE] = 0
            self.consecutive_checks[chess.BLACK] = 0

        turn = board.turn
        self.recent_positions.append(self._pos_key(board))
        mode = mode or self.mode
        candidate_moves = self.get_options(board, mode)
        user_prompt = self.build_prompt(board, candidate_moves)

        messages = self.build_messages(model_name, user_prompt)
        raw_text = (chat_fn or self._chat_ollama)(model_name, messages)

        move, is_valid_llm = self.parse_llm_move(board, raw_text, candidate_moves)
        san_played = board.san(move)

        if board.gives_check(move) and not board.is_capture(move):
            self.consecutive_checks[turn] += 1
        else:
            self.consecutive_checks[turn] = 0

        self.last_piece_squares[turn].append(move.to_square)

        board.push(move)
        self.recent_positions.append(self._pos_key(board))
        board.pop()

        return {
            "move_uci": move.uci(),
            "move_san": san_played,
            "raw_output": raw_text.strip(),
            "clean_hit": is_valid_llm,
            "move_obj": move,
            "mode": mode,
            "options": [board.san(m) for m in candidate_moves][:40],
            "picked_first_option": move == candidate_moves[0],
        }