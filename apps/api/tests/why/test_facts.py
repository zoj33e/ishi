from ishi.rules.board import Board, Color
from ishi.rules.coords import gtp_to_point, point_to_gtp
from ishi.why.facts import (
    capturable_groups,
    cutting_points,
    eye_facts,
    groups_in_atari,
    groups_with_two_liberties,
    move_diff,
)


def _gtp(points: object) -> list[str]:
    return sorted(point_to_gtp(p, 5) for p in points)  # type: ignore[attr-defined]


def _pt(s: str):
    return gtp_to_point(s, 5)


def test_atari_and_capturable() -> None:
    board = Board.from_rows(["XO...", ".....", ".....", ".....", "....."])
    assert len(groups_in_atari(board, Color.BLACK)) == 1
    caps = capturable_groups(board, Color.WHITE)
    assert [_gtp(g.stones) for g, _ in caps] == [["A5"]]
    assert point_to_gtp(caps[0][1], 5) == "A4"
    assert capturable_groups(board, Color.WHITE, ko_point=_pt("A4")) == []
    assert len(groups_with_two_liberties(board, Color.WHITE)) == 1


def test_cutting_point_needs_a_single_shared_liberty() -> None:
    # Diagonal stones B4/C5 share B5 and C4: two ways to connect, no cutting point.
    miai = Board.from_rows(["..X..", ".X...", ".....", ".....", "....."])
    assert _pt("C4") not in cutting_points(miai, Color.BLACK)
    # Black B4 and D4 share only C4.
    cut = Board.from_rows([".....", ".X.X.", "..O..", ".....", "....."])
    points = cutting_points(cut, Color.BLACK)
    assert list(points) == [_pt("C4")]
    assert sorted(_gtp(g.stones)[0] for g in points[_pt("C4")]) == ["B4", "D4"]


def test_eye_facts() -> None:
    board = Board.from_rows([".X.X.", "XXXXX", ".....", ".....", "....."])
    group = board.group_at(_pt("B4"))  # type: ignore[arg-type]
    assert group is not None
    eyes = eye_facts(board, group)
    assert _gtp(eyes.true_eyes) == ["A5", "C5", "E5"]
    assert not eyes.false_eyes


def test_move_diff_capture_and_new_atari() -> None:
    before = Board.from_rows(["XO...", "X....", ".....", ".....", "....."])
    after, captured = before.place(_pt("A3"), Color.WHITE)  # type: ignore[arg-type]
    assert not captured
    diff = move_diff(before, after, captured)
    assert [_gtp(g.stones) for g in diff.new_atari] == [["A4", "A5"]]
    black = next(c for c in diff.changes if _pt("A5") in c.stones)
    assert _gtp(black.liberties_before) == ["A3", "B4"]
    assert _gtp(black.liberties_after) == ["B4"]
    after2, captured2 = after.place(_pt("B4"), Color.WHITE)  # type: ignore[arg-type]
    diff2 = move_diff(after, after2, captured2)
    assert _gtp(diff2.captured) == ["A4", "A5"]
    assert next(c for c in diff2.changes if _pt("A5") in c.stones).captured
