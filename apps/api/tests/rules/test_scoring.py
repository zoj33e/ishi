import pytest

from ishi.rules.board import Board, Color
from ishi.rules.scoring import area_score

from .helpers import pt


def test_empty_board_is_all_neutral() -> None:
    s = area_score(Board.empty(9), komi=7)
    assert (s.black_area, s.white_area) == (0, 0)
    assert s.result == "W+7.0"
    assert all(o is None for o in s.territory.values())


def test_stones_plus_surrounded_territory() -> None:
    b = Board.from_rows([".XO..", ".XO..", ".XO..", ".XO..", ".XO.."])
    s = area_score(b, komi=0)
    assert (s.black_area, s.white_area) == (10, 15)
    assert s.margin == -5
    assert s.result == "W+5.0"
    assert s.winner is Color.WHITE


def test_komi_decides() -> None:
    b = Board.from_rows(["..XO.", "..XO.", "..XO.", "..XO.", "..XO."])
    s = area_score(b, komi=0.5)
    assert (s.black_area, s.white_area) == (15, 10)
    assert s.result == "B+4.5"


def test_dame_is_neutral() -> None:
    b = Board.from_rows(["X.O", "X.O", "X.O"])
    s = area_score(b, komi=0)
    assert (s.black_area, s.white_area) == (3, 3)
    assert s.territory[pt("B2", 3)] is None
    assert s.result == "0"  # jigo
    assert s.winner is None


def test_dead_stones_count_for_the_surrounder() -> None:
    b = Board.from_rows([".XO..", ".XO..", ".XOX.", ".XO..", ".XO.."])
    alive = area_score(b, komi=0)
    assert alive.territory[pt("E3", 5)] is None  # region touches both colors
    s = area_score(b, komi=0, dead=[pt("D3", 5)])
    assert (s.black_area, s.white_area) == (10, 15)
    assert s.territory[pt("D3", 5)] is Color.WHITE


def test_dead_list_must_name_stones() -> None:
    with pytest.raises(ValueError):
        area_score(Board.empty(5), komi=0, dead=[pt("A1", 5)])


def test_open_area_touching_both_colors_is_neutral() -> None:
    b = Board.from_rows(
        [
            "..X.O..",
            "..X.O..",
            "..X.O..",
            "XXX.OOO",
            ".......",
            ".......",
            ".......",
        ]
    )
    s = area_score(b, komi=0)
    # The open bottom area and the D column touch both colors -> neutral.
    assert s.territory[pt("A7", 7)] is Color.BLACK
    assert s.territory[pt("G7", 7)] is Color.WHITE
    assert s.territory[pt("D7", 7)] is None
    assert s.territory[pt("A1", 7)] is None
    assert (s.black_area, s.white_area) == (12, 12)
