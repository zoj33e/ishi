import pytest

from ishi.rules.board import Color
from ishi.rules.game import new_game
from ishi.rules.sgf import parse_sgf, to_sgf

from .helpers import moves, position, pt


def test_export_simple_game() -> None:
    g = moves(new_game(9, 7), "E5", "C3", "pass")
    assert to_sgf(g, result="W+R") == (
        "(;GM[1]FF[4]CA[UTF-8]AP[Ishi:0.1]SZ[9]KM[7]RU[Chinese]RE[W+R];B[ee];W[cg];B[])"
    )


def test_roundtrip_preserves_position_and_captures() -> None:
    g = moves(new_game(9, 7), "E5", "E4", "D4", "F5", "E3", "pass", "F4")
    parsed = parse_sgf(to_sgf(g))
    assert parsed.size == 9 and parsed.komi == 7
    g2 = parsed.to_state()
    assert g2.board == g.board
    assert g2.captures_black == g.captures_black == 1
    assert [m.point for m in g2.moves] == [m.point for m in g.moves]


def test_roundtrip_setup_stones_and_player() -> None:
    g = position(["X....", ".....", ".....", ".....", "....O"], to_move=Color.WHITE)
    g = moves(g, "C3")
    parsed = parse_sgf(to_sgf(g))
    assert parsed.black_setup == (pt("A5", 5),)
    assert parsed.white_setup == (pt("E1", 5),)
    assert parsed.player_to_start is Color.WHITE
    assert parsed.to_state().board == g.board


def test_parse_follows_main_line_and_handles_escapes() -> None:
    sgf = r"""(;GM[1]SZ[9]KM[6.5]PB[A \] B]C[note: x\\y]
      ;B[ee](;W[dd];B[cc])(;W[ff];B[gg]))"""
    p = parse_sgf(sgf)
    assert p.komi == 6.5
    assert p.properties["PB"] == "A ] B"
    assert [pt_ for _, pt_ in p.moves] == [pt("E5"), pt("D6"), pt("C7")]


def test_parse_tt_pass_and_result() -> None:
    p = parse_sgf("(;GM[1]FF[4]SZ[19]RE[B+0.5];B[pd];W[tt];B[])")
    assert [m for _, m in p.moves][1:] == [None, None]
    assert p.result == "B+0.5"
    assert p.to_state().is_over


def test_out_of_turn_moves_rejected() -> None:
    with pytest.raises(ValueError, match="out of turn"):
        parse_sgf("(;GM[1]SZ[9];B[ee];B[dd])").to_state()


def test_illegal_move_in_sgf_rejected() -> None:
    with pytest.raises(ValueError):
        parse_sgf("(;GM[1]SZ[9];B[ee];W[ee])").to_state()


@pytest.mark.parametrize("bad", ["", "(;GM[2]SZ[9])", "(;GM[1]SZ[9];B[ee]", "(;GM[1]SZ[9:7])"])
def test_bad_sgf(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_sgf(bad)
