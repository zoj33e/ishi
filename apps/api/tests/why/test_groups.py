"""Golden positions for the eye helpers (CLAUDE.md rule 7)."""

from ishi.rules.board import Board, Group
from ishi.rules.coords import Point, point_to_gtp
from ishi.why.groups import eye_points, false_eyes, true_eyes
from tests.rules.helpers import pt


def _group(board: Board, gtp: str) -> Group:
    g = board.group_at(pt(gtp, board.size))
    assert g is not None
    return g


def _gtp(points: set[Point], size: int) -> set[str]:
    return {point_to_gtp(p, size) for p in points}


def test_two_true_eyes_on_the_edge() -> None:
    board = Board.from_rows(
        [
            ".....",
            ".....",
            "OOOOO",
            "XXXXX",
            ".X.X.",
        ]
    )
    g = _group(board, "A2")
    assert _gtp(true_eyes(board, g), 5) == {"A1", "C1", "E1"}
    assert false_eyes(board, g) == set()


def test_edge_eye_with_enemy_diagonal_is_false() -> None:
    # C1 is bordered by two white chains; D2 (black) spoils it.
    board = Board.from_rows(
        [
            ".....",
            ".....",
            "OOOX.",
            "OOOXX",
            ".O.OO",
        ]
    )
    g = _group(board, "A2")
    assert _gtp(eye_points(board, g), 5) == {"A1", "C1"}
    assert _gtp(false_eyes(board, g), 5) == {"C1"}
    assert _gtp(true_eyes(board, g), 5) == {"A1"}


def test_center_eye_needs_two_enemy_diagonals_to_be_false() -> None:
    one = Board.from_rows(
        [
            ".....",
            ".XOO.",
            ".O.O.",
            "..OO.",
            ".....",
        ]
    )
    g = _group(one, "C4")
    assert _gtp(true_eyes(one, g), 5) == {"C3"}
    two = Board.from_rows(
        [
            ".....",
            ".XOO.",
            ".O.O.",
            "..OX.",
            ".....",
        ]
    )
    g2 = _group(two, "C4")
    assert _gtp(false_eyes(two, g2), 5) == {"C3"}


def test_point_touching_empty_is_not_an_eye() -> None:
    board = Board.from_rows(
        [
            ".....",
            ".....",
            "OOOOO",
            "XXXXX",
            ".X...",
        ]
    )
    g = _group(board, "A2")
    assert _gtp(eye_points(board, g), 5) == {"A1"}
