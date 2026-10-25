import pytest

from ishi.rules.board import Board, Color
from ishi.rules.coords import Point

from .helpers import pt


def test_empty_board() -> None:
    b = Board.empty(9)
    assert len(b.cells) == 81
    assert all(c is None for c in b.cells)
    assert b.groups() == []


@pytest.mark.parametrize(("gtp", "n"), [("A1", 2), ("A5", 3), ("E5", 4), ("J9", 2), ("J4", 3)])
def test_neighbor_counts_center_edge_corner(gtp: str, n: int) -> None:
    assert len(Board.empty(9).neighbors(pt(gtp))) == n


def test_diagram_roundtrip() -> None:
    rows = ["X.O", ".X.", "O.."]
    b = Board.from_rows(rows)
    assert b.to_rows() == rows
    assert b[Point(0, 0)] is Color.BLACK
    assert b[Point(2, 0)] is Color.WHITE


def test_group_and_liberties() -> None:
    b = Board.from_rows(
        [
            ".........",
            ".........",
            ".........",
            "...XX....",
            "...XO....",
            ".........",
            ".........",
            ".........",
            ".........",
        ]
    )
    g = b.group_at(pt("D6"))
    assert g is not None and g.color is Color.BLACK
    assert g.stones == {pt("D6"), pt("E6"), pt("D5")}
    assert g.liberties == {pt("D7"), pt("E7"), pt("C6"), pt("F6"), pt("C5"), pt("D4")}
    w = b.group_at(pt("E5"))
    assert w is not None and w.liberties == {pt("F5"), pt("E4")}
    assert b.group_at(pt("A1")) is None
    assert len(b.groups()) == 2
    assert len(b.groups(Color.WHITE)) == 1


def test_place_removes_captured_chain() -> None:
    b = Board.from_rows(["XO.", ".X.", "..."])
    after, captured = b.place(Point(2, 0), Color.BLACK)
    assert captured == {Point(1, 0)}
    assert after.to_rows() == ["X.X", ".X.", "..."]


def test_place_on_occupied_raises() -> None:
    with pytest.raises(ValueError):
        Board.from_rows(["X..", "...", "..."]).place(Point(0, 0), Color.WHITE)


def test_bad_diagram() -> None:
    with pytest.raises(ValueError):
        Board.from_rows(["X..", ".."])
    with pytest.raises(ValueError):
        Board.from_rows(["X?.", "...", "..."])
