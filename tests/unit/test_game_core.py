"""Oyun motoru birim testleri (FR-05: kurallar, gecerli hamle, kazanma kontrolu)."""

import json

import pytest

from conftest import DRAW_SEQUENCE, P1_VERTICAL_WIN
from game_core import (COLS, EMPTY, PLAYER1_PIECE, PLAYER2_PIECE, ROWS, STATE_DRAW, STATE_PLAYING,
                       STATE_WIN, ConnectFourGame, other_player)


class TestInitialState:
    def test_new_game_is_empty_and_playing(self):
        g = ConnectFourGame()
        assert g.current_player == PLAYER1_PIECE
        assert g.game_state == STATE_PLAYING and not g.game_over
        assert g.winner is None and g.winning_mask == 0
        assert g.get_valid_locations() == list(range(COLS))
        assert all(g.get_cell(c, r) == EMPTY for c in range(COLS) for r in range(ROWS))

    def test_custom_starting_player(self):
        assert ConnectFourGame(PLAYER2_PIECE).current_player == PLAYER2_PIECE

    def test_other_player(self):
        assert other_player(PLAYER1_PIECE) == PLAYER2_PIECE
        assert other_player(PLAYER2_PIECE) == PLAYER1_PIECE


class TestMoves:
    def test_piece_falls_to_lowest_row_and_turn_alternates(self):
        g = ConnectFourGame()
        assert g.make_move(3)
        assert g.get_cell(3, 0) == PLAYER1_PIECE and g.current_player == PLAYER2_PIECE
        assert g.make_move(3)
        assert g.get_cell(3, 1) == PLAYER2_PIECE and g.current_player == PLAYER1_PIECE
        assert g.move_history == [3, 3] and g.move_count == 2
        assert g.next_row(3) == 2

    def test_full_column_is_rejected(self):
        g = ConnectFourGame.from_moves([2] * ROWS)
        assert not g.is_valid_location(2)
        assert 2 not in g.get_valid_locations()
        assert not g.make_move(2)
        assert g.move_count == ROWS

    @pytest.mark.parametrize("col", [-1, COLS, 99, "3", None, 2.0])
    def test_invalid_columns_are_rejected(self, col):
        g = ConnectFourGame()
        assert not g.is_valid_location(col)
        assert not g.make_move(col)
        assert g.move_count == 0

    def test_no_moves_after_game_over(self):
        g = ConnectFourGame.from_moves(P1_VERTICAL_WIN)
        assert g.game_over
        assert not g.make_move(5)
        assert g.move_count == len(P1_VERTICAL_WIN)

    def test_from_moves_raises_on_illegal_sequence(self):
        with pytest.raises(ValueError):
            ConnectFourGame.from_moves([0] * (ROWS + 1))


class TestWinDetection:
    @pytest.mark.parametrize("moves, expected_cells", [
        # Dikey: P1 sutun 0
        ([0, 1, 0, 1, 0, 1, 0], {(0, 0), (0, 1), (0, 2), (0, 3)}),
        # Yatay: P1 alt satir 0-3
        ([0, 0, 1, 1, 2, 2, 3], {(0, 0), (1, 0), (2, 0), (3, 0)}),
        # Capraz /: P1 (0,0) (1,1) (2,2) (3,3)
        ([0, 1, 1, 2, 2, 3, 2, 3, 3, 6, 3], {(0, 0), (1, 1), (2, 2), (3, 3)}),
        # Capraz \: P1 (3,0) (2,1) (1,2) (0,3)
        ([3, 2, 2, 1, 1, 0, 1, 0, 0, 6, 0], {(3, 0), (2, 1), (1, 2), (0, 3)}),
    ], ids=["vertical", "horizontal", "diagonal_up", "diagonal_down"])
    def test_four_in_a_row_wins(self, moves, expected_cells):
        g = ConnectFourGame.from_moves(moves)
        assert g.game_over and g.game_state == STATE_WIN
        assert g.winner == PLAYER1_PIECE
        assert set(g.get_winning_positions()) == expected_cells

    def test_player_two_can_win(self):
        g = ConnectFourGame.from_moves([0, 1, 0, 1, 0, 1, 6, 1])
        assert g.winner == PLAYER2_PIECE
        assert set(g.get_winning_positions()) == {(1, r) for r in range(4)}

    def test_three_in_a_row_is_not_a_win(self):
        g = ConnectFourGame.from_moves([0, 1, 0, 1, 0])
        assert not g.game_over and g.winner is None

    def test_no_vertical_wraparound_between_columns(self):
        # Sutun 0'in ust uc hucresi (bit 3,4,5) + sutun 1'in alt hucresi (bit 7):
        # nobetci bit (6) sayesinde dikey dortlu sayilmamali.
        h = ConnectFourGame()
        h.bitboards[PLAYER1_PIECE] = (1 << 3) | (1 << 4) | (1 << 5) | (1 << 7)
        assert not h.check_win(PLAYER1_PIECE)

    def test_no_horizontal_wraparound_across_rows(self):
        h = ConnectFourGame()
        # Sutun 5,6 en ust satir + sutun 0,1 bir alt satir: yatay dortlu degil
        h.bitboards[PLAYER1_PIECE] = sum(1 << i for i in (5 * 7 + 5, 6 * 7 + 5, 0 * 7 + 4, 1 * 7 + 4))
        assert not h.check_win(PLAYER1_PIECE)


class TestDraw:
    def test_full_board_without_winner_is_draw(self):
        g = ConnectFourGame.from_moves(DRAW_SEQUENCE)
        assert g.game_over and g.game_state == STATE_DRAW
        assert g.winner is None and g.get_valid_locations() == []
        assert g.get_winning_positions() == []

    def test_draw_detected_after_network_sync(self):
        """from_dict hamle sayacini geri yuklemeli (onceki surumde hata vardi)."""
        before = ConnectFourGame.from_moves(DRAW_SEQUENCE[:-1])
        synced = ConnectFourGame()
        synced.from_dict(json.loads(json.dumps(before.to_dict())))
        assert synced.move_count == len(DRAW_SEQUENCE) - 1
        assert synced.make_move(DRAW_SEQUENCE[-1])
        assert synced.game_state == STATE_DRAW


class TestCloneAndSerialization:
    def test_clone_is_independent(self):
        g = ConnectFourGame.from_moves([3, 4])
        c = g.clone()
        c.make_move(0)
        assert g.move_history == [3, 4] and c.move_history == [3, 4, 0]
        assert g.bitboards != c.bitboards and g.heights != c.heights
        assert g.current_player == PLAYER1_PIECE

    def test_json_round_trip_preserves_state(self):
        g = ConnectFourGame.from_moves(P1_VERTICAL_WIN)
        restored = ConnectFourGame()
        restored.from_dict(json.loads(json.dumps(g.to_dict())))  # anahtarlar str olur
        assert restored.bitboards == g.bitboards
        assert restored.heights == g.heights
        assert restored.move_history == g.move_history
        assert restored.move_count == g.move_count
        assert (restored.current_player, restored.game_over, restored.winner) == (g.current_player, True, PLAYER1_PIECE)
        assert restored.get_winning_positions() == g.get_winning_positions()

    def test_from_dict_copies_lists(self):
        data = ConnectFourGame.from_moves([1]).to_dict()
        g = ConnectFourGame()
        g.from_dict(data)
        g.make_move(2)
        assert data['history'] == [1]

    def test_board_matrix_and_str(self):
        g = ConnectFourGame.from_moves([3, 3])
        board = g.get_board()
        assert board[0][3] == PLAYER1_PIECE and board[1][3] == PLAYER2_PIECE
        text = str(g)
        assert text.count('X') == 1 and text.count('O') == 1
