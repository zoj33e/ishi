import pytest

from ishi.rules.board import Color
from ishi.rules.coords import Point
from ishi.rules.game import (
    IllegalMoveError,
    Legality,
    check_move,
    legal_moves,
    new_game,
    play,
    replay,
)

from .helpers import moves, position, pt

E = "........."

# -- basics ------------------------------------------------------------------------------


def test_new_game_defaults() -> None:
    g = new_game()
    assert g.size == 9 and g.komi == 7 and g.to_move is Color.BLACK
    assert g.move_number == 0 and g.last_move is None and not g.is_over
    assert len(legal_moves(g)) == 81


def test_colors_alternate_and_history_recorded() -> None:
    g = moves(new_game(), "E5", "D4", "pass")
    assert [m.color for m in g.moves] == [Color.BLACK, Color.WHITE, Color.BLACK]
    assert g.last_move is not None and g.last_move.point is None
    assert g.to_move is Color.WHITE
    assert g.move_number == 3


def test_occupied_is_illegal() -> None:
    g = moves(new_game(), "E5")
    assert check_move(g, pt("E5")) is Legality.OCCUPIED
    with pytest.raises(IllegalMoveError) as e:
        play(g, pt("E5"))
    assert e.value.reason is Legality.OCCUPIED


def test_off_board_is_illegal() -> None:
    assert check_move(new_game(), Point(9, 0)) is Legality.OFF_BOARD


def test_setup_position_and_white_to_move() -> None:
    g = position(["X....", ".....", ".....", ".....", "....O"], to_move=Color.WHITE)
    assert g.to_move is Color.WHITE
    assert g.initial_board is not None and g.initial_player is Color.WHITE
    assert check_move(g, pt("A5", 5)) is Legality.OCCUPIED


# -- captures ----------------------------------------------------------------------------


def test_center_capture() -> None:
    g = position([E, E, E, "....X....", "...XOX...", E, E, E, E])
    g = moves(g, "E4")
    assert g.board[pt("E5")] is None
    assert g.captures_black == 1 and g.captures_white == 0
    assert g.last_move is not None and g.last_move.captured == {pt("E5")}


def test_edge_capture() -> None:
    g = position([E, E, E, "X........", "OX.......", E, E, E, E])
    g = moves(g, "A4")
    assert g.board[pt("A5")] is None and g.captures_black == 1


def test_corner_capture() -> None:
    g = position([E, E, E, E, E, E, E, E, "OX......."])
    g = moves(g, "A2")
    assert g.board[pt("A1")] is None and g.captures_black == 1


def test_multi_stone_chain_capture() -> None:
    g = position([E, E, E, "...XX....", "..XOOX...", "...X.....", E, E, E])
    g = moves(g, "E4")
    assert g.board[pt("D5")] is None and g.board[pt("E5")] is None
    assert g.captures_black == 2


def test_one_move_captures_two_separate_chains() -> None:
    g3 = position(["XO.OX", ".X.X.", ".....", ".....", "....."])
    g3 = moves(g3, "C5")
    assert g3.board[pt("B5", 5)] is None and g3.board[pt("D5", 5)] is None
    assert g3.captures_black == 2


def test_white_capture_counts_for_white() -> None:
    g = position([E, E, E, "....O....", "...OXO...", E, E, E, E], to_move=Color.WHITE)
    g = moves(g, "E4")
    assert g.captures_white == 1 and g.captures_black == 0


# -- suicide -----------------------------------------------------------------------------


def test_single_stone_suicide_is_illegal() -> None:
    g = position([".X...", "X....", ".....", ".....", "....."], to_move=Color.WHITE)
    assert check_move(g, pt("A5", 5)) is Legality.SUICIDE
    assert pt("A5", 5) not in legal_moves(g)


def test_multi_stone_suicide_is_illegal() -> None:
    g = position(["OX...", ".X...", "XX...", ".....", "....."], to_move=Color.WHITE)
    assert check_move(g, pt("A4", 5)) is Legality.SUICIDE


def test_suicide_that_captures_is_legal() -> None:
    g = position([".XO..", "XO...", ".....", ".....", "....."], to_move=Color.WHITE)
    assert check_move(g, pt("A5", 5)) is Legality.OK
    g = play(g, pt("A5", 5))
    assert g.board[pt("B5", 5)] is None and g.captures_white == 1


def test_filling_own_eye_with_other_liberties_is_legal() -> None:
    g = position([".X...", "XX...", ".....", ".....", "....."])
    assert check_move(g, pt("A5", 5)) is Legality.OK


def test_filling_own_last_liberty_is_suicide() -> None:
    g = position([".XO..", "XXO..", "OO...", ".....", "....."])
    assert check_move(g, pt("A5", 5)) is Legality.SUICIDE


# -- ko ----------------------------------------------------------------------------------

KO = [E, E, E, "...XO....", "..X.XO...", "...XO....", E, E, E]


def test_ko_capture_sets_ban_and_immediate_recapture_is_illegal() -> None:
    g = position(KO, to_move=Color.WHITE)
    g = moves(g, "D5")
    assert g.board[pt("E5")] is None
    assert g.ko_point == pt("E5")
    assert check_move(g, pt("E5")) is Legality.KO
    with pytest.raises(IllegalMoveError) as e:
        play(g, pt("E5"))
    assert e.value.reason is Legality.KO


def test_ko_can_be_retaken_after_a_threat_exchange() -> None:
    g = moves(position(KO, to_move=Color.WHITE), "D5", "A1", "A9")
    assert g.ko_point is None
    g = moves(g, "E5")  # black retakes
    assert g.board[pt("D5")] is None
    assert g.ko_point == pt("D5")  # and now white is banned


def test_pass_lifts_ko_ban() -> None:
    g = moves(position(KO, to_move=Color.WHITE), "D5", "pass")
    assert g.ko_point is None
    g = moves(g, "J1")  # white plays elsewhere
    assert check_move(g, pt("E5")) is Legality.OK


def test_capturing_two_stones_is_not_ko() -> None:
    g = position([E, E, E, "...XOO...", "..X.XXO..", "...XOO...", E, E, E], to_move=Color.WHITE)
    g = moves(g, "D5")
    assert g.captures_white == 2
    assert g.ko_point is None


def test_single_capture_by_a_group_is_not_ko() -> None:
    # White D5 connects to D6/D4 (white), so recapturing at E5 is not a ko shape.
    g = position([E, E, E, "...OO....", "..X.XO...", "...OO....", E, E, E], to_move=Color.WHITE)
    g = moves(g, "D5")
    assert g.captures_white == 1
    assert g.ko_point is None


def test_capturing_stone_with_two_liberties_is_not_ko() -> None:
    g = position(["XO...", ".....", ".....", ".....", "....."], to_move=Color.WHITE)
    g = moves(g, "A4")  # captures A5; A4 has liberties B4, A3
    assert g.captures_white == 1 and g.ko_point is None


# -- passes & game end -------------------------------------------------------------------


def test_two_passes_end_the_game() -> None:
    g = moves(new_game(), "E5", "pass", "pass")
    assert g.is_over
    assert legal_moves(g) == set()
    assert check_move(g, pt("A1")) is Legality.GAME_OVER
    assert check_move(g, None) is Legality.GAME_OVER


def test_move_after_single_pass_resets_counter() -> None:
    g = moves(new_game(), "pass", "E5", "pass")
    assert g.consecutive_passes == 1 and not g.is_over


def test_replay_helper() -> None:
    g = replay(new_game(), [pt("E5"), None, pt("D4")])
    assert g.move_number == 3 and g.board[pt("D4")] is Color.BLACK


def test_states_are_immutable_snapshots() -> None:
    g0 = new_game()
    g1 = moves(g0, "E5")
    assert g0.board[pt("E5")] is None and g1.board[pt("E5")] is Color.BLACK
